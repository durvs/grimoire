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
from .search import hybrid_search
from .store import IndexStore, _quote

mcp = FastMCP(
    "grimoire",
    instructions=(
        "Busca semântica local em projetos de código. Use `search` em vez de ler "
        "arquivos inteiros: ela retorna só os trechos relevantes com file:line. "
        "Use `outline` para ver a estrutura de um arquivo sem carregar os corpos. "
        "Use `find_references` para 'quem usa/chama X', `dependencies_of`/`dependents_of` "
        "para navegar o grafo de imports."
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
