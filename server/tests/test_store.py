from grimoire_mcp.store import IndexStore
from tests.conftest import fake_embed


def test_initial_sync_indexes_all_files(sample_repo, monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=fake_embed)
    stats = store.sync()
    assert stats["files_indexed"] == 5   # users.py, orders.ts, utils.ts, api.py, README.md
    assert stats["chunks_total"] > 0
    assert store.chunks.count_rows() == stats["chunks_total"]


def test_incremental_sync_only_reembeds_changed(sample_repo, monkeypatch, tmp_path):
    calls = []

    def counting_embed(texts):
        calls.append(len(texts))
        return fake_embed(texts)

    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=counting_embed)
    store.sync()
    first_calls = sum(calls)
    calls.clear()

    stats = store.sync()  # nada mudou
    assert stats["files_indexed"] == 0
    assert sum(calls) == 0

    (sample_repo / "src" / "users.py").write_text("def only_one():\n    return 1\n")
    stats = store.sync()
    assert stats["files_indexed"] == 1
    assert 0 < sum(calls) < first_calls
    rows = store.chunks.to_arrow().to_pylist()
    users_chunks = [r for r in rows if r["file_path"] == "src/users.py"]
    assert {c["symbol"] for c in users_chunks} == {"only_one"}


def test_deleted_file_removes_chunks(sample_repo, monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=fake_embed)
    store.sync()
    (sample_repo / "README.md").unlink()
    store.sync()
    rows = store.chunks.to_arrow().to_pylist()
    assert not any(r["file_path"] == "README.md" for r in rows)


def test_concurrent_syncs_do_not_duplicate_chunks(sample_repo, monkeypatch, tmp_path):
    import threading

    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=fake_embed)
    store.sync()
    baseline = store.chunks.count_rows()

    (sample_repo / "src" / "users.py").write_text("def changed():\n    return 2\n")

    errors = []

    def worker():
        try:
            store.sync()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    rows = store.chunks.to_arrow().to_pylist()
    users = [r for r in rows if r["file_path"] == "src/users.py"]
    assert {r["symbol"] for r in users} == {"changed"}
    assert len(users) == 1
