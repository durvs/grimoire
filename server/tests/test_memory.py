import json
from datetime import datetime, timedelta, timezone

from grimoire_mcp.memory import (
    MEMORY_KINDS,
    age_days,
    memory_id,
    now_iso,
    recency_factor,
)
from grimoire_mcp.store import IndexStore
from tests.conftest import fake_embed


def test_memory_id_deterministic():
    assert memory_id("preferimos uv") == memory_id("  preferimos uv  ")
    assert memory_id("a") != memory_id("b")
    assert len(memory_id("x")) == 12


def test_recency_factor_decays():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=1)).isoformat()
    old = (now - timedelta(days=30)).isoformat()
    assert recency_factor(fresh, now) > recency_factor(old, now)
    assert 1.0 < recency_factor(old, now) < recency_factor(fresh, now) <= 1.25


def _memory_row(text="Decidimos serializar o sync por lock", kind="decision", anchors=None, created=None):
    return {
        "id": memory_id(text), "text": text, "kind": kind,
        "created_at": created or now_iso(),
        "anchors_json": json.dumps(anchors or []),
    }


def _store(sample_repo, monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    store = IndexStore(sample_repo, embed_fn=fake_embed)
    store.sync()
    return store


def test_save_memory_upserts_and_mirrors(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    assert store.save_memory_row(_memory_row()) is False  # não existia
    assert store.save_memory_row(_memory_row()) is True   # upsert
    assert store.memories.count_rows() == 1
    mirror = [c for c in store.chunks.to_arrow().to_pylist() if c["kind"] == "memory"]
    assert len(mirror) == 1
    assert mirror[0]["symbol"] == f"memory:{memory_id('Decidimos serializar o sync por lock')}"
    assert mirror[0]["file_path"] == ""
    assert "serializar o sync" in mirror[0]["text"]


def test_memory_mirror_survives_sync(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    store.save_memory_row(_memory_row())
    (sample_repo / "src" / "users.py").write_text("def changed():\n    return 1\n")
    store.sync()
    mirror = [c for c in store.chunks.to_arrow().to_pylist() if c["kind"] == "memory"]
    assert len(mirror) == 1  # file_path="" fica fora do delete-by-file


def test_anchor_status_ok_stale_missing(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    manifest = json.loads(store._manifest_path.read_text())["files"]
    anchors = [{"file": "src/users.py", "digest": manifest["src/users.py"]}]
    store.save_memory_row(_memory_row(anchors=anchors))

    assert store.list_memories()[0]["anchors"][0]["status"] == "ok"

    (sample_repo / "src" / "users.py").write_text("# mudou\n")
    store.sync()
    assert store.list_memories()[0]["anchors"][0]["status"] == "stale"

    (sample_repo / "src" / "users.py").unlink()
    store.sync()
    listed = store.list_memories()
    assert len(listed) == 1  # memória sobrevive ao arquivo
    assert listed[0]["anchors"][0]["status"] == "missing"


def test_list_memories_filters_and_orders(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    store.save_memory_row(_memory_row("decisão antiga", "decision",
                                      created=(now - timedelta(days=5)).isoformat()))
    store.save_memory_row(_memory_row("aprendizado novo", "learning",
                                      created=now.isoformat()))
    listed = store.list_memories()
    assert [m["text"] for m in listed] == ["aprendizado novo", "decisão antiga"]
    only = store.list_memories(kind="decision")
    assert [m["text"] for m in only] == ["decisão antiga"]


def test_forget_memory_row(sample_repo, monkeypatch, tmp_path):
    store = _store(sample_repo, monkeypatch, tmp_path)
    row = _memory_row()
    store.save_memory_row(row)
    assert store.forget_memory_row(row["id"]) is True
    assert store.forget_memory_row(row["id"]) is False
    assert store.memories.count_rows() == 0
    assert [c for c in store.chunks.to_arrow().to_pylist() if c["kind"] == "memory"] == []


def test_recall_finds_semantically_and_boosts_recent(sample_repo, monkeypatch, tmp_path):
    from grimoire_mcp.search import recall_memories

    store = _store(sample_repo, monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    store.save_memory_row(_memory_row(
        "preferimos lockfiles do uv no repositório", "decision",
        created=(now - timedelta(days=30)).isoformat(),
    ))
    store.save_memory_row(_memory_row(
        "preferimos lockfiles do uv sempre commitados", "decision",
        created=now.isoformat(),
    ))
    out = recall_memories(store, "lockfiles do uv", top_k=2)
    assert len(out) == 2
    assert out[0]["text"] == "preferimos lockfiles do uv sempre commitados"  # recência desempata
    assert out[0]["score"] > out[1]["score"]
    assert {"id", "text", "kind", "created_at", "age_days", "score", "anchors"} <= set(out[0])


def test_recall_kind_filter(sample_repo, monkeypatch, tmp_path):
    from grimoire_mcp.search import recall_memories

    store = _store(sample_repo, monkeypatch, tmp_path)
    store.save_memory_row(_memory_row("usar pt-BR nos commits", "context"))
    store.save_memory_row(_memory_row("pt-BR também na documentação", "decision"))
    out = recall_memories(store, "pt-BR", top_k=5, kind="decision")
    assert [m["kind"] for m in out] == ["decision"]


def test_recall_kind_filter_not_starved_by_other_kinds(sample_repo, monkeypatch, tmp_path):
    from grimoire_mcp.search import recall_memories

    store = _store(sample_repo, monkeypatch, tmp_path)
    for i in range(10):
        store.save_memory_row(_memory_row(f"contexto sobre lockfiles do uv numero {i}", "context"))
    store.save_memory_row(_memory_row("decisão: lockfiles do uv sempre commitados", "decision"))
    store.save_memory_row(_memory_row("decisão: lockfiles do uv revisados em PR", "decision"))
    out = recall_memories(store, "lockfiles do uv", top_k=2, kind="decision")
    assert len(out) == 2
    assert all(m["kind"] == "decision" for m in out)
