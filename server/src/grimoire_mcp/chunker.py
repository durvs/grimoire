from dataclasses import dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

from .config import BLOCK_CHUNK_LINES, MAX_CHUNK_LINES

EXT_LANG = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "javascript", ".java": "java",
    ".go": "go", ".rb": "ruby", ".rs": "rust", ".php": "php",
    ".kt": "kotlin", ".c": "c", ".cpp": "cpp", ".cs": "c_sharp",
    ".swift": "swift", ".md": "markdown", ".markdown": "markdown",
}

DEFINITION_TYPES = {
    "function_definition": "function",      # python, c, cpp
    "class_definition": "class",            # python
    "function_declaration": "function",     # js/ts/go
    "class_declaration": "class",           # js/ts/java/kotlin
    "method_definition": "method",          # js/ts
    "method_declaration": "method",         # java/go/c#
    "interface_declaration": "class",       # java/ts
    "function_item": "function",            # rust
    "struct_item": "class",                 # rust
    "impl_item": "class",                   # rust
    "type_declaration": "class",            # go
}

CONTAINER_TYPES = {"class_definition", "class_declaration", "impl_item", "interface_declaration"}

# Node types that wrap a definition one level deep (export wrappers, decorators, etc.)
WRAPPER_TYPES = {"export_statement", "decorated_definition"}


@dataclass
class Chunk:
    file_path: str
    start_line: int  # 1-based, inclusivo
    end_line: int
    symbol: str
    kind: str        # function | class | method | section | block
    language: str
    text: str


def detect_language(rel_path: str) -> str | None:
    return EXT_LANG.get(Path(rel_path).suffix.lower())


def chunk_file(rel_path: str, text: str) -> list[Chunk]:
    lang = detect_language(rel_path)
    if lang == "markdown":
        return _chunk_markdown(rel_path, text)
    if lang is not None:
        try:
            return _chunk_code(rel_path, text, lang)
        except Exception:
            pass  # gramática indisponível ou parse quebrado -> fallback
    return _chunk_blocks(rel_path, text, lang or "text")


def _slice(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1:end])


def _node_text(node, source_bytes: bytes) -> str:
    """Extract source text for a node using byte offsets."""
    return source_bytes[node.start_byte():node.end_byte()].decode(errors="replace")


def _node_symbol(node, source_bytes: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return source_bytes[name.start_byte():name.end_byte()].decode(errors="replace")
    return node.kind()


def _node_children(node) -> list:
    """Return all direct children of a node as a list."""
    return [node.child(i) for i in range(node.child_count())]


def _unwrap_definition(node):
    """If node is a wrapper (export_statement, decorated_definition), return the
    inner definition node (and the outer node's span), else return node itself.
    Returns (definition_node_or_None, outer_node) where outer_node provides line span."""
    if node.kind() in WRAPPER_TYPES:
        for child in _node_children(node):
            if child.kind() in DEFINITION_TYPES:
                return child, node
    return None, node


def _chunk_code(rel_path: str, text: str, lang: str) -> list[Chunk]:
    parser = get_parser(lang)
    tree = parser.parse(text)
    source_bytes = text.encode()
    root = tree.root_node()
    lines = text.splitlines()
    chunks: list[Chunk] = []
    misc_start: int | None = None

    def flush_misc(until_line: int) -> None:
        nonlocal misc_start
        if misc_start is None:
            return
        block = _slice(lines, misc_start, until_line)
        if block.strip():
            chunks.extend(_split_block(rel_path, block, misc_start, lang))
        misc_start = None

    for node in _node_children(root):
        node_start = node.start_position().row + 1

        # Try to unwrap export_statement / decorated_definition
        def_node, outer_node = _unwrap_definition(node)
        if def_node is not None:
            flush_misc(node_start - 1)
            chunks.extend(_chunk_definition(def_node, outer_node, rel_path, lines, source_bytes, lang))
        elif node.kind() in DEFINITION_TYPES:
            flush_misc(node_start - 1)
            chunks.extend(_chunk_definition(node, node, rel_path, lines, source_bytes, lang))
        elif misc_start is None:
            misc_start = node_start

    flush_misc(len(lines))
    return [c for c in chunks if c.text.strip()]


def _chunk_definition(
    node, outer_node, rel_path: str, lines: list[str], source_bytes: bytes, lang: str,
    parent: str = ""
) -> list[Chunk]:
    # Use outer_node for line span (covers export keyword etc.)
    start = outer_node.start_position().row + 1
    end = outer_node.end_position().row + 1
    raw_symbol = _node_symbol(node, source_bytes)
    symbol = f"{parent}.{raw_symbol}" if parent else raw_symbol
    kind = DEFINITION_TYPES[node.kind()]

    if node.kind() in CONTAINER_TYPES and end - start + 1 > MAX_CHUNK_LINES:
        # large container: header + each method as its own chunk
        methods = _find_definitions(node)
        out: list[Chunk] = []
        first_method_line = min(
            (m.start_position().row + 1 for m in methods), default=end
        )
        out.append(Chunk(rel_path, start, first_method_line - 1, symbol, "class",
                         lang, _slice(lines, start, first_method_line - 1)))
        for m in methods:
            out.extend(_chunk_definition(m, m, rel_path, lines, source_bytes, lang, parent=symbol))
        return out

    return [Chunk(rel_path, start, end, symbol, kind, lang, _slice(lines, start, end))]


def _find_definitions(node) -> list:
    """Find definitions directly in node or one level below (covers body/block)."""
    result = []
    for child in _node_children(node):
        if child.kind() in DEFINITION_TYPES:
            result.append(child)
        else:
            for grandchild in _node_children(child):
                if grandchild.kind() in DEFINITION_TYPES:
                    result.append(grandchild)
    return result


def _chunk_markdown(rel_path: str, text: str) -> list[Chunk]:
    lines = text.splitlines()
    sections: list[tuple[int, str]] = [
        (i + 1, line.lstrip("#").strip())
        for i, line in enumerate(lines) if line.startswith("#")
    ]
    if not sections:
        return _chunk_blocks(rel_path, text, "markdown")
    chunks = []
    for idx, (start, title) in enumerate(sections):
        end = sections[idx + 1][0] - 1 if idx + 1 < len(sections) else len(lines)
        chunks.append(Chunk(rel_path, start, end, title, "section", "markdown",
                            _slice(lines, start, end)))
    return [c for c in chunks if c.text.strip()]


def _chunk_blocks(rel_path: str, text: str, lang: str) -> list[Chunk]:
    lines = text.splitlines()
    block = _slice(lines, 1, len(lines))
    return _split_block(rel_path, block, 1, lang)


def _split_block(rel_path: str, block: str, start_line: int, lang: str) -> list[Chunk]:
    lines = block.splitlines()
    chunks = []
    for i in range(0, len(lines), BLOCK_CHUNK_LINES):
        part = lines[i:i + BLOCK_CHUNK_LINES]
        s = start_line + i
        e = s + len(part) - 1
        text = "\n".join(part)
        if text.strip():
            chunks.append(Chunk(rel_path, s, e, f"{Path(rel_path).name}:{s}", "block", lang, text))
    return chunks
