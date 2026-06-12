"""Grimoire MCP server — fastmcp 3.4.x.

API notes:
- @mcp.tool (no parentheses) is the correct decorator form in fastmcp >= 2.0.
  The plan template uses @mcp.tool without parentheses; this matches the live
  3.4.2 API where `FastMCP.tool` can be used as a plain decorator.
- result.data in tests returns the structured Python value directly from
  CallToolResult.data (fastmcp 3.4.2 wraps return values in structured_content
  and surfaces them via `.data`).

Security / robustness additions beyond the plan template:
1. outline() rejects file_path arguments that escape the project root via path
   traversal (e.g. "../../etc/passwd"). After resolving `full`, it checks
   `full.is_relative_to(root)` and raises ValueError if the path is outside.
2. status() wraps each per-directory manifest read in try/except (OSError,
   json.JSONDecodeError, KeyError) so a single corrupt manifest directory does
   not crash the whole listing.
"""

import json
import threading
from pathlib import Path

from fastmcp import FastMCP

from . import config
from .chunker import chunk_file
from .memory import MEMORY_KINDS, memory_id, now_iso
from .rules import EXTRACTION_INSTRUCTIONS, RULE_CATEGORIES, is_test_path, rule_id, rule_signal_score
from .search import hybrid_search, recall_memories
from .store import IndexStore, _quote

mcp = FastMCP(
    "grimoire",
    instructions=(
        "Busca semântica local em projetos de código. Use `search` em vez de ler "
        "arquivos inteiros: ela retorna só os trechos relevantes com file:line. "
        "Use `outline` para ver a estrutura de um arquivo sem carregar os corpos. "
        "Use `find_references` para 'quem usa/chama X', `dependencies_of`/`dependents_of` "
        "para navegar o grafo de imports. "
        "Para regras de negócio: `extract_rules` → você extrai → `save_rules`; "
        "consulte com `rules` ou via `search`. "
        "Memória de projeto: chame `recall` com o tema ao começar a trabalhar; "
        "grave decisões não-óbvias e aprendizados com `remember`."
    ),
)

_EMBED_FN = None  # testes injetam fake; produção usa o default do IndexStore
_STORES: dict[str, IndexStore] = {}
_stores_lock = threading.Lock()


def _store_for(project_path: str) -> IndexStore:
    if not Path(project_path).is_dir():
        raise ValueError(f"projeto não encontrado: {project_path}")
    root = str(Path(project_path).resolve())
    with _stores_lock:
        if root not in _STORES:
            _STORES[root] = IndexStore(Path(root), embed_fn=_EMBED_FN)
        return _STORES[root]


def _rel_inside(project_path: str, file_path: str) -> str:
    root = Path(project_path).resolve()
    full = (root / file_path).resolve()
    if not full.is_relative_to(root):
        raise ValueError("file_path fora do projeto")
    return full.relative_to(root).as_posix()


@mcp.tool
def index_project(project_path: str) -> dict:
    """Indexa (ou atualiza incrementalmente) um projeto para busca semântica."""
    return _store_for(project_path).sync()


@mcp.tool
def search(
    query: str,
    project_path: str,
    top_k: int = 8,
    language: str | None = None,
    path_prefix: str | None = None,
) -> list[dict]:
    """Busca híbrida (semântica + texto exato) no projeto.

    Retorna trechos com file, start_line/end_line, symbol e score.
    Aceita consultas conceituais ("onde valida CPF") e identificadores exatos.

    Valores aceitos para `language`: python, typescript, tsx, javascript, java,
    go, ruby, rust, php, kotlin, c, cpp, c_sharp, swift, markdown, text
    (fallback para extensões não reconhecidas).
    Atenção: arquivos `.tsx` têm language "tsx", não "typescript".
    """
    return hybrid_search(
        _store_for(project_path), query,
        top_k=top_k, language=language, path_prefix=path_prefix,
    )


@mcp.tool
def outline(project_path: str, file_path: str) -> list[dict]:
    """Estrutura de símbolos de um arquivo (sem corpos) — barato em tokens."""
    rel = _rel_inside(project_path, file_path)
    root = Path(project_path).resolve()
    full = root / rel
    text = full.read_text(encoding="utf-8", errors="replace")
    return [
        {
            "symbol": c.symbol,
            "kind": c.kind,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "signature": c.text.splitlines()[0].strip() if c.text else "",
        }
        for c in chunk_file(rel, text)
    ]


@mcp.tool
def find_references(symbol: str, project_path: str, limit: int = 50) -> list[dict]:
    """Encontra definições e usos exatos de um identificador no projeto inteiro.

    Léxico-estrutural: toda ocorrência do nome, anotada com def/use e com o
    símbolo (função/classe/método) onde ocorre. Definições vêm primeiro.
    """
    store = _store_for(project_path)
    store.sync()
    try:
        rows = store.refs.search().where(f"name = {_quote(symbol)}").limit(10000).to_list()
    except Exception:  # noqa: BLE001 - LanceDB version may not accept search() without query
        rows = [r for r in store.refs.to_arrow().to_pylist() if r["name"] == symbol]
    rows.sort(key=lambda r: (r["kind"] != "def", r["file_path"], r["line"]))
    return [
        {"file": r["file_path"], "line": r["line"], "kind": r["kind"],
         "container": r["container"], "line_text": r["line_text"]}
        for r in rows[:limit]
    ]


@mcp.tool
def dependencies_of(file_path: str, project_path: str) -> dict:
    """Do que este arquivo depende: arquivos do repo, pacotes externos e imports não resolvidos."""
    rel = _rel_inside(project_path, file_path)
    store = _store_for(project_path)
    store.sync()
    try:
        rows = store.imports.search().where(f"file_path = {_quote(rel)}").limit(10000).to_list()
    except Exception:  # noqa: BLE001 - LanceDB version may not accept search() without query
        rows = [r for r in store.imports.to_arrow().to_pylist() if r["file_path"] == rel]
    return {
        "files": sorted({r["target"] for r in rows if r["status"] == "resolved"}),
        "external": sorted({r["module"] for r in rows if r["status"] == "external"}),
        "unresolved": sorted({r["module"] for r in rows if r["status"] == "unresolved"}),
    }


@mcp.tool
def dependents_of(file_path: str, project_path: str) -> list[str]:
    """Quem importa este arquivo — o que pode quebrar se ele mudar."""
    rel = _rel_inside(project_path, file_path)
    store = _store_for(project_path)
    store.sync()
    try:
        rows = store.imports.search().where(f"target = {_quote(rel)}").limit(10000).to_list()
    except Exception:  # noqa: BLE001 - LanceDB version may not accept search() without query
        rows = [r for r in store.imports.to_arrow().to_pylist() if r["target"] == rel]
    return sorted({r["file_path"] for r in rows})


@mcp.tool
def status() -> list[dict]:
    """Lista projetos indexados com contagem de arquivos."""
    indexes = config.GRIMOIRE_HOME / "indexes"
    out = []
    if indexes.exists():
        for d in indexes.iterdir():
            manifest = d / "manifest.json"
            # Robustness: skip corrupt or incomplete manifest entries gracefully.
            try:
                data = json.loads(manifest.read_text())
                out.append({
                    "project_path": data["project_path"],
                    "files": len(data["files"]),
                })
            except (OSError, json.JSONDecodeError, KeyError):
                continue
    return out


CANDIDATE_KINDS = {"function", "method", "section"}


@mcp.tool
def extract_rules(
    project_path: str, scope: str | None = None, batch: int = 10, cursor: int = 0,
) -> dict:
    """Prepara a extração de regras de negócio: retorna chunks candidatos + instruções.

    Você (o agente) extrai as regras dos chunks e as persiste via `save_rules`.
    Use `scope` (arquivo ou diretório) para limitar; siga `next_cursor` até null.
    """
    store = _store_for(project_path)
    store.sync()
    prefix = _rel_inside(project_path, scope) if scope else None
    rows = store.chunks.to_arrow().to_pylist()
    candidates = sorted(
        (
            (rule_signal_score(r["text"]), r)
            for r in rows
            if r["kind"] in CANDIDATE_KINDS
            and not is_test_path(r["file_path"])
            and (prefix is None or r["file_path"] == prefix
                 or r["file_path"].startswith(prefix.rstrip("/") + "/"))
            and rule_signal_score(r["text"]) > 0
        ),
        key=lambda sr: (-sr[0], sr[1]["file_path"], sr[1]["start_line"]),
    )
    page = candidates[cursor:cursor + batch]
    next_cursor = cursor + batch if cursor + batch < len(candidates) else None
    return {
        "instructions": EXTRACTION_INSTRUCTIONS,
        "chunks": [
            {"file": r["file_path"], "start_line": r["start_line"],
             "end_line": r["end_line"], "symbol": r["symbol"], "kind": r["kind"],
             "text": r["text"]}
            for _, r in page
        ],
        "next_cursor": next_cursor,
        "remaining": max(0, len(candidates) - (cursor + batch)),
    }


@mcp.tool
def save_rules(project_path: str, rules: list[dict]) -> dict:
    """Valida e persiste regras de negócio extraídas; itens inválidos voltam em rejected."""
    store = _store_for(project_path)
    store.sync()
    manifest_files = json.loads(store._manifest_path.read_text())["files"]
    valid_rows, rejected = [], []
    for item in rules:
        reason = _validate_rule(item, project_path, manifest_files)
        if reason is not None:
            rejected.append({"item": item, "reason": reason})
            continue
        rel = _rel_inside(project_path, item["file"])
        valid_rows.append({
            "id": rule_id(rel, item["rule"]), "file_path": rel,
            "start_line": int(item["start_line"]), "end_line": int(item["end_line"]),
            "rule": item["rule"], "category": item["category"],
            "confidence": float(item["confidence"]),
            "file_digest": manifest_files[rel],
        })
    saved = store.save_rules_rows(valid_rows)
    return {"saved": saved, "rejected": rejected}


def _validate_rule(item: dict, project_path: str, manifest_files: dict) -> str | None:
    rule = item.get("rule") or ""
    if not rule.strip():
        return "rule vazio"
    if item.get("category") not in RULE_CATEGORIES:
        return f"category inválida: {item.get('category')!r} (use {sorted(RULE_CATEGORIES)})"
    try:
        confidence = float(item.get("confidence", -1))
    except (TypeError, ValueError):
        return "confidence não numérico"
    if not 0.0 <= confidence <= 1.0:
        return "confidence fora de [0, 1]"
    try:
        start, end = int(item["start_line"]), int(item["end_line"])
    except (KeyError, TypeError, ValueError):
        return "start_line/end_line ausentes ou não inteiros"
    if not 1 <= start <= end:
        return f"start_line/end_line inválidos: {start}..{end}"
    try:
        rel = _rel_inside(project_path, item.get("file", ""))
    except ValueError:
        return "file fora do projeto"
    if rel not in manifest_files:
        return f"file não indexado: {rel}"
    return None


@mcp.tool
def rules(project_path: str, file_path: str | None = None) -> list[dict]:
    """Lista regras de negócio extraídas, com flag stale (código mudou desde a extração)."""
    store = _store_for(project_path)
    store.sync()
    rel = _rel_inside(project_path, file_path) if file_path else None
    return store.list_rules(rel)


@mcp.tool
def delete_rule(project_path: str, rule_id: str) -> dict:
    """Remove uma regra (tabela + espelho na busca)."""
    store = _store_for(project_path)
    return {"deleted": store.delete_rule_row(rule_id)}


@mcp.tool
def remember(
    project_path: str, text: str, kind: str = "context", files: list[str] | None = None,
) -> dict:
    """Grava uma memória do projeto (decisão, aprendizado, contexto, todo).

    Use ao tomar uma decisão não-óbvia ou aprender algo que não está no código —
    a memória persiste entre sessões e aparece no `recall` e no `search`.
    `files` opcional ancora a memória em arquivos (ganha aviso de stale se mudarem).
    Re-gravar o mesmo texto atualiza (upsert) em vez de duplicar.
    """
    if not text.strip():
        raise ValueError("text vazio")
    if kind not in MEMORY_KINDS:
        raise ValueError(f"kind inválido: {kind!r} (use {sorted(MEMORY_KINDS)})")
    store = _store_for(project_path)
    store.sync()
    manifest_files = json.loads(store._manifest_path.read_text())["files"]
    anchors = []
    for f in files or []:
        rel = _rel_inside(project_path, f)
        if rel not in manifest_files:
            raise ValueError(f"âncora não indexada: {rel}")
        anchors.append({"file": rel, "digest": manifest_files[rel]})
    row = {
        "id": memory_id(text), "text": text.strip(), "kind": kind,
        "created_at": now_iso(), "anchors_json": json.dumps(anchors),
    }
    updated = store.save_memory_row(row)
    return {"id": row["id"], "updated": updated}


@mcp.tool
def recall(project_path: str, query: str, top_k: int = 5, kind: str | None = None) -> list[dict]:
    """Recupera memórias do projeto por relevância semântica (+ boost de recência).

    Chame ao começar a trabalhar num projeto, com o tema da tarefa.
    """
    store = _store_for(project_path)
    store.sync()
    return recall_memories(store, query, top_k=top_k, kind=kind)


@mcp.tool
def memories(project_path: str, kind: str | None = None) -> list[dict]:
    """Lista todas as memórias do projeto, mais recentes primeiro."""
    store = _store_for(project_path)
    store.sync()
    return store.list_memories(kind)


@mcp.tool
def forget(project_path: str, memory_id: str) -> dict:
    """Remove uma memória (tabela + espelho na busca)."""
    store = _store_for(project_path)
    return {"deleted": store.forget_memory_row(memory_id)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
