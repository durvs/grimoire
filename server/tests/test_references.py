from grimoire_mcp.chunker import parse_tree
from grimoire_mcp.references import extract
from tests.conftest import SAMPLE_PY, SAMPLE_TS, SAMPLE_API_PY


def _extract(text: str, lang: str, rel: str):
    tree = parse_tree(text, lang)
    return extract(rel, tree, text.encode(), lang)


def test_python_defs_and_uses():
    refs, _ = _extract(SAMPLE_PY, "python", "src/users.py")
    defs = {r.name for r in refs if r.kind == "def"}
    assert {"validate_cpf", "format_document", "UserService", "get_user_by_id"} <= defs
    # CPF_RE é atribuição de módulo: aparece como uso, nunca como def
    cpf_kinds = {r.kind for r in refs if r.name == "CPF_RE"}
    assert cpf_kinds == {"use"}
    # uso de CPF_RE dentro de validate_cpf tem container qualificado
    inner = [r for r in refs if r.name == "CPF_RE" and r.container == "validate_cpf"]
    assert inner


def test_method_container_is_qualified():
    refs, _ = _extract(SAMPLE_PY, "python", "src/users.py")
    d = next(r for r in refs if r.name == "get_user_by_id" and r.kind == "def")
    assert d.container == "UserService.get_user_by_id"


def test_ts_use_inside_method():
    refs, _ = _extract(SAMPLE_TS, "typescript", "src/orders.ts")
    use = [r for r in refs if r.name == "formatMoney" and r.kind == "use"]
    assert any(r.container == "OrderService.calculateDiscount" for r in use)


def test_import_statement_identifiers_are_not_refs():
    refs, _ = _extract(SAMPLE_API_PY, "python", "src/api.py")
    names = {r.name for r in refs}
    assert "fastapi" not in names  # imports viram entradas da tabela imports, não refs


def test_python_raw_imports():
    _, imports = _extract(SAMPLE_API_PY, "python", "src/api.py")
    modules = {i.module for i in imports}
    assert {"src.users", ".users", "src.missing", "fastapi"} <= modules


def test_ts_raw_imports():
    _, imports = _extract(SAMPLE_TS, "typescript", "src/orders.ts")
    modules = {i.module for i in imports}
    assert {"./utils", "react"} <= modules


def test_lang_without_import_extractor_still_has_refs():
    go = "func Soma(a int, b int) int {\n\treturn a + b\n}\n"
    refs, imports = _extract(go, "go", "main.go")
    assert any(r.name == "Soma" and r.kind == "def" for r in refs)
    assert imports == []


def test_python_import_module_containing_word_import():
    src = "from importlib import metadata\nfrom .importutils import helper\nfrom src.importers import load\n"
    _, imports = _extract(src, "python", "src/api.py")
    modules = {i.module for i in imports}
    assert modules == {"importlib", ".importutils", "src.importers"}


def test_ts_dynamic_import_captured():
    src = 'const page = import("./dyn");\nasync function go() {\n  const m = await import("./dyn2");\n}\n'
    _, imports = _extract(src, "typescript", "src/app.ts")
    modules = {i.module for i in imports}
    assert {"./dyn", "./dyn2"} <= modules
