from grimoire_mcp.scanner import scan


def test_scan_respects_gitignore_and_skips_binary(sample_repo):
    files = scan(sample_repo)
    rel_paths = {f.rel_path for f in files}
    assert "src/users.py" in rel_paths
    assert "src/orders.ts" in rel_paths
    assert "README.md" in rel_paths
    assert "secret.txt" not in rel_paths        # .gitignore
    assert "logo.bin" not in rel_paths          # binário
    assert "node_modules/lib.js" not in rel_paths  # always-ignore


def test_scan_digest_changes_with_content(sample_repo):
    before = {f.rel_path: f.digest for f in scan(sample_repo)}
    (sample_repo / "src" / "users.py").write_text("# changed\n")
    after = {f.rel_path: f.digest for f in scan(sample_repo)}
    assert before["src/users.py"] != after["src/users.py"]
    assert before["README.md"] == after["README.md"]
