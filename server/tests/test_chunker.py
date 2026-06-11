from grimoire_mcp.chunker import chunk_file
from tests.conftest import SAMPLE_PY, SAMPLE_TS, SAMPLE_MD


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
