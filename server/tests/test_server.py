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
