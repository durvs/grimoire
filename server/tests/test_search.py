from grimoire_mcp.search import hybrid_search
from grimoire_mcp.store import IndexStore
from tests.conftest import fake_embed


def _store(sample_repo, monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=fake_embed)
    store.sync()
    return store


def test_exact_identifier_found_via_fts(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    results = hybrid_search(store, "getUserById", top_k=3)
    assert results
    top = results[0]
    assert top["file"] == "src/orders.ts"
    assert top["symbol"] == "getUserById"


def test_results_have_location_and_score(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    results = hybrid_search(store, "validate_cpf", top_k=5)
    top = results[0]
    assert set(top) >= {"file", "start_line", "end_line", "symbol", "kind", "score", "snippet"}
    assert top["start_line"] >= 1


def test_language_filter(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    results = hybrid_search(store, "service", top_k=10, language="python")
    assert results
    assert all(r["file"].endswith(".py") for r in results)
