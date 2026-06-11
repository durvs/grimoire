import posixpath
from dataclasses import dataclass

from .chunker import DEFINITION_TYPES, _node_children, _node_symbol

IDENTIFIER_TYPES = {
    "identifier", "type_identifier", "property_identifier",
    "field_identifier", "shorthand_property_identifier",
}

PY_IMPORT_NODES = {"import_statement", "import_from_statement"}
TS_LANGS = {"typescript", "tsx", "javascript"}


@dataclass
class Ref:
    name: str
    line: int       # 1-based
    kind: str       # "def" | "use"
    container: str  # símbolo qualificado envolvente ("" em nível de módulo)


@dataclass
class RawImport:
    module: str
    line: int


def _text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte():node.end_byte()].decode(errors="replace")


def extract(rel_path: str, tree, source_bytes: bytes, lang: str) -> tuple[list[Ref], list[RawImport]]:
    """Anda na árvore UMA vez coletando identificadores (def/use) e imports crus.

    Identificadores dentro de statements de import não viram refs — a tabela
    `imports` é a representação deles.
    """
    refs: list[Ref] = []
    imports: list[RawImport] = []
    _walk(tree.root_node(), "", frozenset(), refs, imports, source_bytes, lang)
    return refs, imports


def _walk(node, container, def_name_spans, refs, imports, source_bytes, lang):
    kind = node.kind()

    if kind in IDENTIFIER_TYPES:
        span = (node.start_byte(), node.end_byte())
        refs.append(Ref(
            name=_text(node, source_bytes),
            line=node.start_position().row + 1,
            kind="def" if span in def_name_spans else "use",
            container=container,
        ))
        return

    if lang == "python" and kind in PY_IMPORT_NODES:
        imports.extend(_python_imports(node, source_bytes))
        return

    if lang in TS_LANGS:
        if kind == "import_statement":
            imports.extend(_ts_import_source(node, source_bytes))
            return
        if kind == "export_statement":
            # re-export (`export { x } from "./y"`) tem um filho string;
            # export de definição não tem — segue o walk normal
            re_export = _ts_import_source(node, source_bytes)
            if re_export:
                imports.extend(re_export)
                return
        if kind == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None and _text(fn, source_bytes) == "require":
                imports.extend(_ts_import_source(node, source_bytes))
                return

    new_container = container
    new_spans = def_name_spans
    if kind in DEFINITION_TYPES:
        sym = _node_symbol(node, source_bytes)
        new_container = f"{container}.{sym}" if container else sym
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            new_spans = def_name_spans | {(name_node.start_byte(), name_node.end_byte())}

    for child in _node_children(node):
        _walk(child, new_container, new_spans, refs, imports, source_bytes, lang)


def _python_imports(node, source_bytes) -> list[RawImport]:
    line = node.start_position().row + 1
    text = _text(node, source_bytes)
    if node.kind() == "import_from_statement":
        # "from ..a.b import x" -> "..a.b"
        module = text.split("import", 1)[0].removeprefix("from").strip()
        return [RawImport(module, line)]
    # "import a.b, c as d" -> ["a.b", "c"]
    body = text.removeprefix("import").strip()
    return [
        RawImport(part.strip().split(" as ")[0].strip(), line)
        for part in body.split(",") if part.strip()
    ]


def _ts_import_source(node, source_bytes) -> list[RawImport]:
    """Acha o primeiro filho string (specifier) em import/export/require."""
    for child in _node_children(node):
        if child.kind() == "string":
            spec = _text(child, source_bytes).strip("'\"`")
            return [RawImport(spec, node.start_position().row + 1)]
        # require("..."): a string está dentro de `arguments`
        if child.kind() == "arguments":
            for arg in _node_children(child):
                if arg.kind() == "string":
                    spec = _text(arg, source_bytes).strip("'\"`")
                    return [RawImport(spec, node.start_position().row + 1)]
    return []


def resolve_import(module: str, importer_rel_path: str, lang: str, files: set[str]) -> tuple[str | None, str]:
    """-> (target_rel_path | None, status: "resolved" | "external" | "unresolved")."""
    if lang == "python":
        return _resolve_python(module, importer_rel_path, files)
    if lang in TS_LANGS:
        return _resolve_ts(module, importer_rel_path, files)
    return None, "external"


def _resolve_python(module: str, importer: str, files: set[str]) -> tuple[str | None, str]:
    if module.startswith("."):
        dots = len(module) - len(module.lstrip("."))
        rest = module.lstrip(".")
        base = posixpath.dirname(importer)
        for _ in range(dots - 1):
            base = posixpath.dirname(base)
        prefix = posixpath.normpath(posixpath.join(base, rest.replace(".", "/")) if rest else base)
    else:
        prefix = module.replace(".", "/")
    for cand in (f"{prefix}.py", f"{prefix}/__init__.py"):
        cand = posixpath.normpath(cand)
        if cand in files:
            return cand, "resolved"
    if module.startswith("."):
        return None, "unresolved"
    first = module.split(".")[0]
    looks_local = any(f == f"{first}.py" or f.startswith(f"{first}/") for f in files)
    return None, ("unresolved" if looks_local else "external")


def _resolve_ts(spec: str, importer: str, files: set[str]) -> tuple[str | None, str]:
    if not spec.startswith("."):
        return None, "external"  # inclui aliases tsconfig (@/...) na V1.1
    base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
    if base in files:
        return base, "resolved"
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        if f"{base}{ext}" in files:
            return f"{base}{ext}", "resolved"
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        cand = f"{base}/index{ext}"
        if cand in files:
            return cand, "resolved"
    return None, "unresolved"
