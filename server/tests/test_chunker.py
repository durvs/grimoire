from grimoire_mcp.chunker import chunk_file
from tests.conftest import SAMPLE_PY, SAMPLE_TS, SAMPLE_MD


def test_chunk_file_accepts_preparsed_tree():
    from grimoire_mcp.chunker import parse_tree

    tree = parse_tree(SAMPLE_PY, "python")
    with_tree = chunk_file("src/users.py", SAMPLE_PY, tree=tree)
    without = chunk_file("src/users.py", SAMPLE_PY)
    assert [(c.symbol, c.start_line, c.end_line) for c in with_tree] == [
        (c.symbol, c.start_line, c.end_line) for c in without
    ]


def test_python_chunks_by_symbol():
    chunks = chunk_file("src/users.py", SAMPLE_PY)
    symbols = {c.symbol for c in chunks if c.kind != "block"}
    assert "validate_cpf" in symbols
    assert "format_document" in symbols
    assert "UserService" in symbols
    fn = next(c for c in chunks if c.symbol == "validate_cpf")
    assert fn.kind == "function"
    assert "fullmatch" in fn.text
    assert fn.start_line >= 1 and fn.end_line > fn.start_line


def test_typescript_chunks_by_symbol():
    chunks = chunk_file("src/orders.ts", SAMPLE_TS)
    symbols = {c.symbol for c in chunks}
    assert "getUserById" in symbols
    assert "OrderService" in symbols


def test_markdown_chunks_by_header():
    chunks = chunk_file("README.md", SAMPLE_MD)
    symbols = [c.symbol for c in chunks]
    assert "Regras de negócio" in symbols
    rule = next(c for c in chunks if c.symbol == "Regras de negócio")
    assert "Desconto de 10%" in rule.text


def test_unknown_extension_falls_back_to_blocks():
    text = "\n".join(f"line {i}" for i in range(150))
    chunks = chunk_file("notes.txt", text)
    assert all(c.kind == "block" for c in chunks)
    assert len(chunks) >= 2  # 150 linhas / BLOCK_CHUNK_LINES=60


def _make_big_class() -> str:
    lines = ["class Big:", "    ATTR_TOP = 1", ""]
    lines += ["    def m0(self):"] + [f"        x{i} = {i}" for i in range(40)] + [""]
    lines += ["    MIDDLE_ATTR = 2", ""]
    lines += ["    @property", "    def m1(self):"] + [f"        y{i} = {i}" for i in range(40)] + [""]
    lines += ["    def m2(self):"] + [f"        z{i} = {i}" for i in range(40)] + [""]
    lines += ["    TRAILING_ATTR = 3"]
    return "\n".join(lines)


def test_large_class_keeps_decorated_methods():
    chunks = chunk_file("big.py", _make_big_class())
    symbols = {c.symbol for c in chunks}
    assert "Big.m0" in symbols
    assert "Big.m1" in symbols  # decorated — must not vanish
    assert "Big.m2" in symbols
    m1 = next(c for c in chunks if c.symbol == "Big.m1")
    assert "@property" in m1.text  # decorator included in span


def test_large_class_covers_every_line():
    text = _make_big_class()
    chunks = chunk_file("big.py", text)
    covered = set()
    for c in chunks:
        covered.update(range(c.start_line, c.end_line + 1))
    non_blank = {i + 1 for i, line in enumerate(text.splitlines()) if line.strip()}
    assert non_blank <= covered  # nenhuma linha não-vazia fora do índice


def test_large_class_without_methods_keeps_last_line():
    lines = ["class Flat:"] + [f"    A{i} = {i}" for i in range(130)]
    text = "\n".join(lines)
    chunks = chunk_file("flat.py", text)
    covered = set()
    for c in chunks:
        covered.update(range(c.start_line, c.end_line + 1))
    assert len(lines) in covered  # última linha indexada
