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


async def test_extract_rules_returns_candidates_and_instructions(sample_repo):
    async with Client(mcp) as client:
        out = (await client.call_tool("extract_rules", {
            "project_path": str(sample_repo), "batch": 2,
        })).data
        assert "save_rules" in out["instructions"]
        assert 0 < len(out["chunks"]) <= 2
        chunk = out["chunks"][0]
        assert {"file", "start_line", "end_line", "symbol", "kind", "text"} <= set(chunk)
        # candidato óbvio: calculateDiscount tem condicional e comparação
        all_chunks = out["chunks"]
        cursor = out["next_cursor"]
        while cursor is not None:
            page = (await client.call_tool("extract_rules", {
                "project_path": str(sample_repo), "batch": 2, "cursor": cursor,
            })).data
            all_chunks += page["chunks"]
            cursor = page["next_cursor"]
        assert any(c["symbol"] == "OrderService.calculateDiscount" for c in all_chunks)
        # paginação não repete
        keys = [(c["file"], c["start_line"]) for c in all_chunks]
        assert len(keys) == len(set(keys))


async def test_save_rules_validates_per_item(sample_repo):
    async with Client(mcp) as client:
        good = {
            "rule": "Desconto de 10% para totais acima de 100",
            "category": "calculation", "file": "src/orders.ts",
            "start_line": 10, "end_line": 12, "confidence": 0.9,
        }
        bad_category = {**good, "rule": "x", "category": "banana"}
        bad_lines = {**good, "rule": "y", "start_line": 9, "end_line": 3}
        bad_file = {**good, "rule": "z", "file": "src/nao_existe.ts"}
        out = (await client.call_tool("save_rules", {
            "project_path": str(sample_repo),
            "rules": [good, bad_category, bad_lines, bad_file],
        })).data
        assert len(out["saved"]) == 1
        reasons = " | ".join(r["reason"] for r in out["rejected"])
        assert len(out["rejected"]) == 3
        assert "category" in reasons and "line" in reasons.lower()
        # amendment 1: rejected items echo full original item
        assert out["rejected"][0]["item"]["category"] == "banana"


async def test_rules_listing_and_delete(sample_repo):
    async with Client(mcp) as client:
        save = (await client.call_tool("save_rules", {
            "project_path": str(sample_repo),
            "rules": [{
                "rule": "CPF deve ter 11 dígitos", "category": "validation",
                "file": "src/users.py", "start_line": 6, "end_line": 8,
                "confidence": 0.95,
            }],
        })).data
        rid = save["saved"][0]

        listed = (await client.call_tool("rules", {"project_path": str(sample_repo)})).data
        mine = next(r for r in listed if r["id"] == rid)
        assert mine["stale"] is False and mine["file"] == "src/users.py"

        results = (await client.call_tool("search", {
            "query": "CPF deve ter 11 dígitos", "project_path": str(sample_repo),
        })).data
        assert any(r["kind"] == "rule" for r in results)

        out = (await client.call_tool("delete_rule", {
            "project_path": str(sample_repo), "rule_id": rid,
        })).data
        assert out["deleted"] is True
        out = (await client.call_tool("delete_rule", {
            "project_path": str(sample_repo), "rule_id": rid,
        })).data
        assert out["deleted"] is False


async def test_extract_rules_scope_guard(sample_repo):
    import pytest as _pytest
    async with Client(mcp) as client:
        with _pytest.raises(Exception):
            await client.call_tool("extract_rules", {
                "project_path": str(sample_repo), "scope": "../../etc",
            })


async def test_memory_full_flow(sample_repo):
    async with Client(mcp) as client:
        saved = (await client.call_tool("remember", {
            "project_path": str(sample_repo),
            "text": "Desconto é calculado em OrderService",
            "kind": "learning",
            "files": ["src/orders.ts"],
        })).data
        assert saved["updated"] is False

        recalled = (await client.call_tool("recall", {
            "project_path": str(sample_repo),
            "query": "onde calcula desconto",
        })).data
        assert any(m["id"] == saved["id"] for m in recalled)
        mine = next(m for m in recalled if m["id"] == saved["id"])
        assert mine["anchors"][0] == {"file": "src/orders.ts", "status": "ok"}

        results = (await client.call_tool("search", {
            "query": "Desconto é calculado em OrderService",
            "project_path": str(sample_repo),
        })).data
        assert any(r["kind"] == "memory" for r in results)

        listed = (await client.call_tool("memories", {"project_path": str(sample_repo)})).data
        assert any(m["id"] == saved["id"] for m in listed)

        out = (await client.call_tool("forget", {
            "project_path": str(sample_repo), "memory_id": saved["id"],
        })).data
        assert out["deleted"] is True


async def test_remember_validations(sample_repo):
    import pytest as _pytest
    async with Client(mcp) as client:
        with _pytest.raises(Exception):  # kind inválido
            await client.call_tool("remember", {
                "project_path": str(sample_repo), "text": "x", "kind": "banana",
            })
        with _pytest.raises(Exception):  # âncora fora do projeto
            await client.call_tool("remember", {
                "project_path": str(sample_repo), "text": "y",
                "files": ["../../etc/passwd"],
            })
        with _pytest.raises(Exception):  # âncora não indexada
            await client.call_tool("remember", {
                "project_path": str(sample_repo), "text": "z",
                "files": ["src/nao_existe.py"],
            })
