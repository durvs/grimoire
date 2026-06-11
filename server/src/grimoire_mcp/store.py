import json
from collections.abc import Callable
from pathlib import Path

import lancedb
import pyarrow as pa

from . import config
from .chunker import chunk_file
from .scanner import scan

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


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class IndexStore:
    def __init__(self, project_root: Path, embed_fn: EmbedFn | None = None):
        self.root = Path(project_root).resolve()
        self.embed_fn = embed_fn or _default_embed
        self.dir = config.index_dir(self.root)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(self.dir)
        self.chunks = self.db.create_table("chunks", schema=_schema(), exist_ok=True)
        self._manifest_path = self.dir / "manifest.json"

    def _load_manifest(self) -> dict:
        if self._manifest_path.exists():
            return json.loads(self._manifest_path.read_text())
        return {"project_path": str(self.root), "files": {}}

    def _save_manifest(self, manifest: dict) -> None:
        self._manifest_path.write_text(json.dumps(manifest, indent=1))

    def sync(self) -> dict:
        manifest = self._load_manifest()
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
            self.chunks.delete(f"file_path = {_quote(rel)}")
            known.pop(rel, None)

        chunks_added = 0
        for f in changed:
            text = f.path.read_text(errors="replace")
            chunks = chunk_file(f.rel_path, text)
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
            known[f.rel_path] = f.digest

        if changed or deleted:
            # LanceDB 0.33.0: create_fts_index(field_names, *, use_tantivy=False, replace=True)
            # use_tantivy=False activates the native (non-tantivy) FTS backend, which supports
            # query_type="fts" in table.search(...) — required by Task 7.
            self.chunks.create_fts_index("text", use_tantivy=False, replace=True)
        self._save_manifest(manifest)

        return {
            "files_indexed": len(changed),
            "files_deleted": len(deleted),
            "files_total": len(current),
            "chunks_added": chunks_added,
            "chunks_total": self.chunks.count_rows(),
        }
