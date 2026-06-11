import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path

import lancedb
import pyarrow as pa

from . import config
from .chunker import chunk_file, detect_language, parse_tree
from .references import extract, resolve_import
from .scanner import scan

logger = logging.getLogger(__name__)

EmbedFn = Callable[[list[str]], list[list[float]]]


def _default_embed(texts: list[str]) -> list[list[float]]:
    from .embedder import embed_texts  # import tardio: não carrega onnx em testes
    return embed_texts(texts)


def _schema() -> pa.Schema:
    return pa.schema([
        pa.field("vector", pa.list_(pa.float32(), config.EMBEDDING_DIM)),
        pa.field("text", pa.string()),
        pa.field("file_path", pa.string()),
        pa.field("start_line", pa.int32()),
        pa.field("end_line", pa.int32()),
        pa.field("symbol", pa.string()),
        pa.field("kind", pa.string()),
        pa.field("language", pa.string()),
    ])


INDEX_VERSION = 2


def _refs_schema() -> pa.Schema:
    return pa.schema([
        pa.field("file_path", pa.string()),
        pa.field("name", pa.string()),
        pa.field("line", pa.int32()),
        pa.field("kind", pa.string()),        # def | use
        pa.field("container", pa.string()),
        pa.field("line_text", pa.string()),
    ])


def _imports_schema() -> pa.Schema:
    return pa.schema([
        pa.field("file_path", pa.string()),
        pa.field("module", pa.string()),
        pa.field("line", pa.int32()),
        pa.field("target", pa.string()),      # rel path resolvido ou ""
        pa.field("status", pa.string()),      # resolved | external | unresolved
    ])


def _rules_schema() -> pa.Schema:
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("file_path", pa.string()),
        pa.field("start_line", pa.int32()),
        pa.field("end_line", pa.int32()),
        pa.field("rule", pa.string()),
        pa.field("category", pa.string()),
        pa.field("confidence", pa.float32()),
        pa.field("file_digest", pa.string()),
    ])


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class IndexStore:
    """Índice persistente de um projeto (LanceDB + manifest de digests).

    Sincronizações simultâneas no mesmo processo são serializadas pelo
    `_sync_lock`: apenas uma thread executa `sync()` por vez nesta instância.
    Múltiplos processos apontando para o mesmo diretório de índice continuam
    sendo last-writer-wins (manifest), mas o pior caso é re-indexação
    redundante, nunca corrupção silenciosa (delete-before-add converge).
    Exceção: durante a migração de versão do índice (drop+recreate), outro
    processo com handles antigos pode ver erros de leitura até reiniciar.
    """

    def __init__(self, project_root: Path, embed_fn: EmbedFn | None = None):
        self.root = Path(project_root).resolve()
        self.embed_fn = embed_fn or _default_embed
        self.dir = config.index_dir(self.root)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(self.dir)
        self.chunks = self.db.create_table("chunks", schema=_schema(), exist_ok=True)
        self.refs = self.db.create_table("refs", schema=_refs_schema(), exist_ok=True)
        self.imports = self.db.create_table("imports", schema=_imports_schema(), exist_ok=True)
        self.rules = self.db.create_table("rules", schema=_rules_schema(), exist_ok=True)
        self._manifest_path = self.dir / "manifest.json"
        self._sync_lock = threading.Lock()

    def _load_manifest(self) -> dict:
        # Manifest corrompido (crash no meio do write) → re-index completo, que
        # é o comportamento de autocura do resto do design.
        try:
            manifest = json.loads(self._manifest_path.read_text())
            manifest["files"]
            return manifest
        except (OSError, json.JSONDecodeError, KeyError):
            return {"project_path": str(self.root), "version": INDEX_VERSION, "files": {}}

    def _save_manifest(self, manifest: dict) -> None:
        self._manifest_path.write_text(json.dumps(manifest, indent=1))

    def sync(self) -> dict:
        with self._sync_lock:
            return self._sync_locked()

    def _sync_locked(self) -> dict:
        manifest = self._load_manifest()
        if manifest.get("version") != INDEX_VERSION:
            for name in ("chunks", "refs", "imports", "rules"):
                try:
                    self.db.drop_table(name)
                except Exception:  # noqa: BLE001 - tabela pode não existir
                    pass
            self.chunks = self.db.create_table("chunks", schema=_schema(), exist_ok=True)
            self.refs = self.db.create_table("refs", schema=_refs_schema(), exist_ok=True)
            self.imports = self.db.create_table("imports", schema=_imports_schema(), exist_ok=True)
            self.rules = self.db.create_table("rules", schema=_rules_schema(), exist_ok=True)
            manifest = {"project_path": str(self.root), "version": INDEX_VERSION, "files": {}}
        known: dict[str, str] = manifest["files"]
        all_scanned = scan(self.root)
        # Exclude files that live inside the index directory itself (edge case when
        # GRIMOIRE_HOME happens to be a subdirectory of the project root, e.g. in tests).
        index_dir_resolved = self.dir.resolve()
        scanned = [
            f for f in all_scanned
            if not f.path.resolve().is_relative_to(index_dir_resolved)
        ]
        current = {f.rel_path: f for f in scanned}

        changed = [f for f in scanned if known.get(f.rel_path) != f.digest]
        deleted = [p for p in known if p not in current]

        for rel in deleted + [f.rel_path for f in changed]:
            for tbl in (self.chunks, self.refs, self.imports):
                tbl.delete(f"file_path = {_quote(rel)}")
            known.pop(rel, None)

        for rel in deleted:
            self.rules.delete(f"file_path = {_quote(rel)}")

        chunks_added = 0
        refs_added = 0
        imports_added = 0
        current_paths = set(current)
        for f in changed:
            text = f.path.read_text(encoding="utf-8", errors="replace")
            lang = detect_language(f.rel_path)
            tree = None
            if lang is not None and lang != "markdown":
                try:
                    tree = parse_tree(text, lang)
                except Exception:  # noqa: BLE001 - gramática indisponível
                    tree = None
            chunks = chunk_file(f.rel_path, text, tree=tree)
            if chunks:
                vectors = self.embed_fn(
                    [f"{c.symbol} ({c.file_path})\n{c.text}" for c in chunks]
                )
                self.chunks.add([
                    {
                        "vector": vec, "text": c.text, "file_path": c.file_path,
                        "start_line": c.start_line, "end_line": c.end_line,
                        "symbol": c.symbol, "kind": c.kind, "language": c.language,
                    }
                    for c, vec in zip(chunks, vectors)
                ])
                chunks_added += len(chunks)

            if tree is not None:
                lines = text.splitlines()
                try:
                    refs, raw_imports = extract(f.rel_path, tree, text.encode(), lang)
                except Exception:  # noqa: BLE001 - pathological tree (e.g. RecursionError)
                    logger.debug("extract() failed for %s; skipping refs/imports", f.rel_path)
                    refs, raw_imports = [], []
                if refs:
                    self.refs.add([
                        {
                            "file_path": f.rel_path, "name": r.name, "line": r.line,
                            "kind": r.kind, "container": r.container,
                            "line_text": lines[r.line - 1].strip() if r.line <= len(lines) else "",
                        }
                        for r in refs
                    ])
                    refs_added += len(refs)
                if raw_imports:
                    rows = []
                    for imp in raw_imports:
                        target, status = resolve_import(imp.module, f.rel_path, lang, current_paths)
                        rows.append({
                            "file_path": f.rel_path, "module": imp.module, "line": imp.line,
                            "target": target or "", "status": status,
                        })
                    self.imports.add(rows)
                    imports_added += len(rows)
            known[f.rel_path] = f.digest

            rule_rows = [
                r for r in self.rules.to_arrow().to_pylist()
                if r["file_path"] == f.rel_path
            ]
            if rule_rows:
                self._mirror_rules(rule_rows, current_digests={f.rel_path: f.digest})

        if changed or deleted:
            # LanceDB 0.33.0: create_fts_index(field_names, *, use_tantivy=False, replace=True)
            # use_tantivy=False activates the native (non-tantivy) FTS backend, which supports
            # query_type="fts" in table.search(...) — required by Task 7.
            self.chunks.create_fts_index("text", use_tantivy=False, replace=True)
        manifest["version"] = INDEX_VERSION
        self._save_manifest(manifest)

        return {
            "files_indexed": len(changed),
            "files_deleted": len(deleted),
            "files_total": len(current),
            "chunks_added": chunks_added,
            "chunks_total": self.chunks.count_rows(),
            "refs_added": refs_added,
            "imports_added": imports_added,
        }

    def save_rules_rows(self, rows: list[dict]) -> list[str]:
        """Upsert por id na tabela rules + espelho kind="rule" no índice de busca.

        Persiste na tabela primeiro; se o embedding do espelho falhar, a regra
        não se perde (o re-espelho do próximo sync recupera).
        """
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        for rid in ids:
            self.rules.delete(f"id = {_quote(rid)}")
        self.rules.add(rows)
        self._mirror_rules(rows, current_digests={r["file_path"]: r["file_digest"] for r in rows})
        self.chunks.create_fts_index("text", use_tantivy=False, replace=True)
        return ids

    def _mirror_rules(self, rule_rows: list[dict], current_digests: dict[str, str]) -> None:
        """(Re)emite os chunks kind="rule" para as regras dadas."""
        for rid in (r["id"] for r in rule_rows):
            self.chunks.delete(f"symbol = {_quote('rule:' + rid)}")
        texts = []
        for r in rule_rows:
            stale = current_digests.get(r["file_path"]) != r["file_digest"]
            marker = "[regra de negócio][stale]" if stale else "[regra de negócio]"
            texts.append(f"{marker} {r['rule']}")
        vectors = self.embed_fn(texts)
        self.chunks.add([
            {
                "vector": vec, "text": text, "file_path": r["file_path"],
                "start_line": r["start_line"], "end_line": r["end_line"],
                "symbol": f"rule:{r['id']}", "kind": "rule", "language": "rule",
            }
            for r, vec, text in zip(rule_rows, vectors, texts)
        ])

    def list_rules(self, file_path: str | None = None) -> list[dict]:
        manifest = self._load_manifest()
        digests = manifest["files"]
        rows = self.rules.to_arrow().to_pylist()
        if file_path is not None:
            rows = [r for r in rows if r["file_path"] == file_path]
        out = []
        for r in sorted(rows, key=lambda r: (r["file_path"], r["start_line"])):
            out.append({
                "id": r["id"], "rule": r["rule"], "category": r["category"],
                "confidence": round(r["confidence"], 2), "file": r["file_path"],
                "start_line": r["start_line"], "end_line": r["end_line"],
                "stale": digests.get(r["file_path"]) != r["file_digest"],
            })
        return out

    def delete_rule_row(self, rule_id: str) -> bool:
        existed = bool([r for r in self.rules.to_arrow().to_pylist() if r["id"] == rule_id])
        self.rules.delete(f"id = {_quote(rule_id)}")
        self.chunks.delete(f"symbol = {_quote('rule:' + rule_id)}")
        return existed
