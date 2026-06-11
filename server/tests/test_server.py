import pytest
from fastmcp import Client

from grimoire_mcp.server import mcp
import grimoire_mcp.server as server_mod
from tests.conftest import fake_embed


@pytest.fixture(autouse=True)
def fast_embeddings(monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    monkeypatch.setattr(server_mod, "_EMBED_FN", fake_embed)
    server_mod._STORES.clear()


async def test_index_then_search(sample_repo):
    async with Client(mcp) as client:
        stats = (await client.call_tool("index_project", {"project_path": str(sample_repo)})).data
        assert stats["files_total"] == 5

        results = (await client.call_tool("search", {
            "query": "getUserById",
            "project_path": str(sample_repo),
            "top_k": 3,
        })).data
        assert results[0]["file"] == "src/orders.ts"


async def test_outline(sample_repo):
    async with Client(mcp) as client:
        outline = (await client.call_tool("outline", {
            "project_path": str(sample_repo),
            "file_path": "src/users.py",
        })).data
        symbols = {o["symbol"] for o in outline}
        assert {"validate_cpf", "format_document", "UserService"} <= symbols
        assert all("text" not in o for o in outline)  # outline não carrega corpos


async def test_status_lists_indexed_projects(sample_repo):
    async with Client(mcp) as client:
        await client.call_tool("index_project", {"project_path": str(sample_repo)})
        status = (await client.call_tool("status", {})).data
        assert any(p["project_path"] == str(sample_repo) for p in status)


async def test_index_project_rejects_missing_path():
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("index_project", {"project_path": "/caminho/que/nao/existe"})
        assert "não encontrado" in str(exc_info.value)


async def test_find_references(sample_repo):
    async with Client(mcp) as client:
        refs = (await client.call_tool("find_references", {
            "symbol": "validate_cpf",
            "project_path": str(sample_repo),
        })).data
        assert refs[0]["kind"] == "def"          # definições primeiro
        assert refs[0]["file"] == "src/users.py"
        uses = [r for r in refs if r["kind"] == "use"]
        assert any(r["file"] == "src/api.py" for r in uses)
        assert all({"file", "line", "kind", "container", "line_text"} <= set(r) for r in refs)


async def test_dependencies_of(sample_repo):
    async with Client(mcp) as client:
        deps = (await client.call_tool("dependencies_of", {
            "file_path": "src/api.py",
            "project_path": str(sample_repo),
        })).data
        assert "src/users.py" in deps["files"]
        assert "fastapi" in deps["external"]
        assert "src.missing" in deps["unresolved"]


async def test_dependents_of(sample_repo):
    async with Client(mcp) as client:
        dependents = (await client.call_tool("dependents_of", {
            "file_path": "src/users.py",
            "project_path": str(sample_repo),
        })).data
        assert "src/api.py" in dependents


async def test_dependencies_of_rejects_escape(sample_repo):
    import pytest as _pytest
    async with Client(mcp) as client:
        with _pytest.raises(Exception):
            await client.call_tool("dependencies_of", {
                "file_path": "../../etc/passwd",
                "project_path": str(sample_repo),
            })
