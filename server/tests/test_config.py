from pathlib import Path

from grimoire_mcp.config import index_dir, GRIMOIRE_HOME


def test_index_dir_is_deterministic_per_path():
    a = index_dir(Path("/tmp/proj-a"))
    b = index_dir(Path("/tmp/proj-b"))
    assert a != b
    assert a == index_dir(Path("/tmp/proj-a"))
    assert a.is_relative_to(GRIMOIRE_HOME / "indexes")
