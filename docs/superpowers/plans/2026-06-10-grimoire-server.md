# Grimoire MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MCP server local (`grimoire-mcp` no PyPI) que indexa projetos com chunking estrutural e expõe busca híbrida (vetor + BM25) para agentes, com índice incremental zero-infra.

**Architecture:** Python package em `server/` no monorepo. Pipeline: `scanner` (arquivos + hashes, respeita .gitignore) → `chunker` (tree-sitter por símbolo, fallbacks markdown/blocos) → `embedder` (fastembed local) → `store` (LanceDB embedded em `~/.grimoire/indexes/<hash>/` + manifest JSON, sync incremental) → `search` (vetor + FTS fundidos por RRF) → `server` (fastmcp, stdio, 4 tools). Embeddings são injetáveis (`embed_fn`) para testes rápidos sem modelo real.

**Tech Stack:** Python 3.11+, fastmcp 2.x, fastembed (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dims), LanceDB, tree-sitter-language-pack, pathspec, pytest + pytest-asyncio.

**File structure:**

```
server/
  pyproject.toml
  src/grimoire_mcp/
    __init__.py        # versão
    config.py          # paths, modelo, limites
    scanner.py         # walk + gitignore + hash
    chunker.py         # chunking estrutural + fallbacks; também serve o outline
    embedder.py        # wrapper fastembed (lazy singleton)
    store.py           # LanceDB + manifest, sync incremental
    search.py          # busca híbrida + RRF
    server.py          # fastmcp tools + main()
  tests/
    conftest.py        # fixture de repo sintético + fake embedder
    test_scanner.py
    test_chunker.py
    test_store.py
    test_search.py
    test_server.py
.github/workflows/ci.yml
```

---

### Task 1: Scaffold do pacote Python

**Files:**
- Create: `server/pyproject.toml`
- Create: `server/src/grimoire_mcp/__init__.py`
- Create: `server/tests/test_smoke.py`

- [ ] **Step 1: Criar pyproject.toml**

```toml
[project]
name = "grimoire-mcp"
version = "0.1.0"
description = "Local semantic code search MCP server - surgical context retrieval for AI agents"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
dependencies = [
    "fastmcp>=2.0",
    "fastembed>=0.6",
    "lancedb>=0.21",
    "tree-sitter>=0.23",
    "tree-sitter-language-pack>=0.7",
    "pathspec>=0.12",
]

[project.scripts]
grimoire-mcp = "grimoire_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/grimoire_mcp"]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = ["slow: testes que baixam o modelo de embedding real"]
addopts = "-m 'not slow'"
```

- [ ] **Step 2: Criar `server/src/grimoire_mcp/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Criar teste de fumaça `server/tests/test_smoke.py`**

```python
import grimoire_mcp


def test_version():
    assert grimoire_mcp.__version__ == "0.1.0"
```

- [ ] **Step 4: Instalar e rodar**

Run: `cd server && uv sync && uv run pytest -v`
Expected: `test_version PASSED`

- [ ] **Step 5: Commit**

```bash
git add server/
git commit -m "feat(server): scaffold do pacote grimoire-mcp"
```

---

### Task 2: Config

**Files:**
- Create: `server/src/grimoire_mcp/config.py`
- Test: `server/tests/test_config.py`

- [ ] **Step 1: Teste falhando**

```python
from pathlib import Path

from grimoire_mcp.config import index_dir, GRIMOIRE_HOME


def test_index_dir_is_deterministic_per_path():
    a = index_dir(Path("/tmp/proj-a"))
    b = index_dir(Path("/tmp/proj-b"))
    assert a != b
    assert a == index_dir(Path("/tmp/proj-a"))
    assert a.is_relative_to(GRIMOIRE_HOME / "indexes")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError` ou `ImportError`)

- [ ] **Step 3: Implementar `config.py`**

```python
import hashlib
import os
from pathlib import Path

GRIMOIRE_HOME = Path(os.environ.get("GRIMOIRE_HOME", Path.home() / ".grimoire"))
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
MAX_FILE_SIZE = 1_000_000  # bytes; arquivos maiores são ignorados
MAX_CHUNK_LINES = 120
BLOCK_CHUNK_LINES = 60


def index_dir(project_path: Path) -> Path:
    digest = hashlib.sha256(str(project_path.resolve()).encode()).hexdigest()[:16]
    return GRIMOIRE_HOME / "indexes" / digest
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/grimoire_mcp/config.py server/tests/test_config.py
git commit -m "feat(server): config com index_dir determinístico e GRIMOIRE_HOME"
```

---

### Task 3: Scanner (walk + gitignore + hash)

**Files:**
- Create: `server/src/grimoire_mcp/scanner.py`
- Create: `server/tests/conftest.py`
- Test: `server/tests/test_scanner.py`

- [ ] **Step 1: Criar fixture de repo sintético em `conftest.py`**

```python
import pytest

SAMPLE_PY = '''import re

CPF_RE = re.compile(r"\\d{11}")


def validate_cpf(cpf: str) -> bool:
    """Valida formato de CPF (11 dígitos)."""
    return bool(CPF_RE.fullmatch(cpf))


def format_document(doc: str) -> str:
    return doc.strip().replace(".", "").replace("-", "")


class UserService:
    def __init__(self, repo):
        self.repo = repo

    def get_user_by_id(self, user_id: int):
        return self.repo.find(user_id)
'''

SAMPLE_TS = '''export function getUserById(id: number): Promise<User> {
  return api.get(`/users/${id}`);
}

export class OrderService {
  calculateDiscount(total: number): number {
    return total > 100 ? total * 0.1 : 0;
  }
}
'''

SAMPLE_MD = '''# Projeto

Visão geral do projeto.

## Regras de negócio

Desconto de 10% acima de 100 reais.

## Setup

Rode npm install.
'''


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "users.py").write_text(SAMPLE_PY)
    (tmp_path / "src" / "orders.ts").write_text(SAMPLE_TS)
    (tmp_path / "README.md").write_text(SAMPLE_MD)
    (tmp_path / ".gitignore").write_text("secret.txt\n")
    (tmp_path / "secret.txt").write_text("senha123")
    (tmp_path / "logo.bin").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("ignored")
    return tmp_path
```

- [ ] **Step 2: Teste falhando `test_scanner.py`**

```python
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
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_scanner.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: Implementar `scanner.py`**

```python
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pathspec

from .config import MAX_FILE_SIZE

ALWAYS_IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".grimoire",
    "dist", "build", ".next", "target", ".idea", ".vscode",
}


@dataclass
class ScannedFile:
    path: Path      # absoluto
    rel_path: str   # relativo à raiz, com /
    digest: str     # sha256 do conteúdo


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _is_text(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" not in f.read(8192)
    except OSError:
        return False


def scan(root: Path) -> list[ScannedFile]:
    root = root.resolve()
    spec = _load_gitignore(root)
    result: list[ScannedFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in ALWAYS_IGNORE_DIRS
            and not spec.match_file(str(Path(dirpath, d).relative_to(root)) + "/")
        ]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if spec.match_file(rel):
                continue
            try:
                if path.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            if not _is_text(path):
                continue
            result.append(ScannedFile(
                path=path,
                rel_path=rel,
                digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            ))
    return result
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_scanner.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add server/src/grimoire_mcp/scanner.py server/tests/conftest.py server/tests/test_scanner.py
git commit -m "feat(server): scanner com gitignore, filtro binário e hash por arquivo"
```

---

### Task 4: Chunker estrutural

**Files:**
- Create: `server/src/grimoire_mcp/chunker.py`
- Test: `server/tests/test_chunker.py`

- [ ] **Step 1: Teste falhando**

```python
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
```

Nota: o import `from tests.conftest import ...` exige `server/tests/__init__.py` vazio — crie-o neste step.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_chunker.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementar `chunker.py`**

```python
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


def _chunk_code(rel_path: str, text: str, lang: str) -> list[Chunk]:
    parser = get_parser(lang)
    tree = parser.parse(text.encode())
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

    for node in tree.root_node.children:
        start, end = node.start_point[0] + 1, node.end_point[0] + 1
        if node.type in DEFINITION_TYPES:
            flush_misc(start - 1)
            chunks.extend(_chunk_definition(node, rel_path, lines, lang))
        elif misc_start is None:
            misc_start = start
    flush_misc(len(lines))
    return [c for c in chunks if c.text.strip()]


def _node_symbol(node) -> str:
    name = node.child_by_field_name("name")
    return name.text.decode() if name is not None else node.type


def _chunk_definition(node, rel_path: str, lines: list[str], lang: str, parent: str = "") -> list[Chunk]:
    start, end = node.start_point[0] + 1, node.end_point[0] + 1
    symbol = f"{parent}.{_node_symbol(node)}" if parent else _node_symbol(node)
    kind = DEFINITION_TYPES[node.type]
    if node.type in CONTAINER_TYPES and end - start + 1 > MAX_CHUNK_LINES:
        # classe grande: header + cada método como chunk próprio
        methods = [
            d for child in node.children for d in _find_definitions(child)
        ]
        out: list[Chunk] = []
        first_method_line = min((m.start_point[0] + 1 for m in methods), default=end)
        out.append(Chunk(rel_path, start, first_method_line - 1, symbol, "class",
                         lang, _slice(lines, start, first_method_line - 1)))
        for m in methods:
            out.extend(_chunk_definition(m, rel_path, lines, lang, parent=symbol))
        return out
    return [Chunk(rel_path, start, end, symbol, kind, lang, _slice(lines, start, end))]


def _find_definitions(node) -> list:
    """Acha definições diretamente em node ou um nível abaixo (cobre body/block)."""
    if node.type in DEFINITION_TYPES:
        return [node]
    return [c for c in node.children if c.type in DEFINITION_TYPES]


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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_chunker.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add server/src/grimoire_mcp/chunker.py server/tests/test_chunker.py server/tests/__init__.py
git commit -m "feat(server): chunking estrutural via tree-sitter com fallbacks markdown/blocos"
```

---

### Task 5: Embedder + fake para testes

**Files:**
- Create: `server/src/grimoire_mcp/embedder.py`
- Modify: `server/tests/conftest.py` (adicionar fake_embed)
- Test: `server/tests/test_embedder.py`

- [ ] **Step 1: Implementar `embedder.py`** (wrapper fino; teste real é marcado slow)

```python
from fastembed import TextEmbedding

from .config import EMBEDDING_MODEL

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [e.tolist() for e in _get_model().embed(texts)]
```

- [ ] **Step 2: Adicionar fake embedder determinístico ao `conftest.py`**

```python
import hashlib
import math


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Embedding determinístico por hash de trigramas — rápido, sem modelo.

    Textos iguais -> vetores iguais; textos parecidos -> vetores próximos.
    """
    out = []
    for text in texts:
        vec = [0.0] * 384
        for i in range(len(text) - 2):
            tri = text[i:i + 3].lower()
            idx = int(hashlib.md5(tri.encode()).hexdigest(), 16) % 384
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out
```

- [ ] **Step 3: Teste do embedder real, marcado slow, em `test_embedder.py`**

```python
import pytest


@pytest.mark.slow
def test_real_model_embeds_384_dims():
    from grimoire_mcp.embedder import embed_texts

    vecs = embed_texts(["onde valida CPF?", "def validate_cpf(cpf):"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
```

- [ ] **Step 4: Verificar que a suíte padrão não roda o slow**

Run: `cd server && uv run pytest -v`
Expected: todos PASSED, `test_real_model_embeds_384_dims` **deselected**

- [ ] **Step 5: Commit**

```bash
git add server/src/grimoire_mcp/embedder.py server/tests/test_embedder.py server/tests/conftest.py
git commit -m "feat(server): embedder fastembed com fake determinístico para testes"
```

---

### Task 6: Store (LanceDB + manifest + sync incremental)

**Files:**
- Create: `server/src/grimoire_mcp/store.py`
- Test: `server/tests/test_store.py`

- [ ] **Step 1: Teste falhando**

```python
import json

from grimoire_mcp.store import IndexStore
from tests.conftest import fake_embed


def make_store(repo, monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "grimoire-home")
    monkeypatch.setattr("grimoire_mcp.store.GRIMOIRE_HOME", tmp_path / "grimoire-home", raising=False)
    return IndexStore(repo, embed_fn=fake_embed)


def test_initial_sync_indexes_all_files(sample_repo, monkeypatch, tmp_path):
    store = make_store(sample_repo, monkeypatch, tmp_path)
    stats = store.sync()
    assert stats["files_indexed"] == 3   # users.py, orders.ts, README.md
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementar `store.py`**

```python
import json
from collections.abc import Callable
from pathlib import Path

import lancedb
import pyarrow as pa

from . import config
from .chunker import chunk_file
from .scanner import scan

EmbedFn = Callable[[list[str]], list[list[float]]]


def _default_embed(texts: list[str]) -> list[list[float]]:
    from .embedder import embed_texts  # import tardio: não carrega onnx em testes
    return embed_texts(texts)


def _schema() -> pa.Schema:
    return pa.schema([
        pa.field("vector", pa.list_(pa.float32(), config.EMBEDDING_DIM)),
        pa.field("text", pa.string()),
        pa.field("file_path", pa.string()),
        pa.field("start_line", pa.int32()),
        pa.field("end_line", pa.int32()),
        pa.field("symbol", pa.string()),
        pa.field("kind", pa.string()),
        pa.field("language", pa.string()),
    ])


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class IndexStore:
    def __init__(self, project_root: Path, embed_fn: EmbedFn | None = None):
        self.root = Path(project_root).resolve()
        self.embed_fn = embed_fn or _default_embed
        self.dir = config.index_dir(self.root)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(self.dir)
        self.chunks = self.db.create_table("chunks", schema=_schema(), exist_ok=True)
        self._manifest_path = self.dir / "manifest.json"

    def _load_manifest(self) -> dict:
        if self._manifest_path.exists():
            return json.loads(self._manifest_path.read_text())
        return {"project_path": str(self.root), "files": {}}

    def _save_manifest(self, manifest: dict) -> None:
        self._manifest_path.write_text(json.dumps(manifest, indent=1))

    def sync(self) -> dict:
        manifest = self._load_manifest()
        known: dict[str, str] = manifest["files"]
        scanned = scan(self.root)
        current = {f.rel_path: f for f in scanned}

        changed = [f for f in scanned if known.get(f.rel_path) != f.digest]
        deleted = [p for p in known if p not in current]

        for rel in deleted + [f.rel_path for f in changed]:
            self.chunks.delete(f"file_path = {_quote(rel)}")
            known.pop(rel, None)

        chunks_added = 0
        for f in changed:
            text = f.path.read_text(errors="replace")
            chunks = chunk_file(f.rel_path, text)
            if chunks:
                vectors = self.embed_fn(
                    [f"{c.symbol} ({c.file_path})\n{c.text}" for c in chunks]
                )
                self.chunks.add([
                    {
                        "vector": vec, "text": c.text, "file_path": c.file_path,
                        "start_line": c.start_line, "end_line": c.end_line,
                        "symbol": c.symbol, "kind": c.kind, "language": c.language,
                    }
                    for c, vec in zip(chunks, vectors)
                ])
                chunks_added += len(chunks)
            known[f.rel_path] = f.digest

        if changed or deleted:
            self.chunks.create_fts_index("text", use_tantivy=False, replace=True)
        self._save_manifest(manifest)

        return {
            "files_indexed": len(changed),
            "files_deleted": len(deleted),
            "files_total": len(current),
            "chunks_added": chunks_added,
            "chunks_total": self.chunks.count_rows(),
        }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_store.py -v`
Expected: 3 PASSED. Se `create_fts_index(use_tantivy=False)` der erro de assinatura na versão instalada, rode `uv run python -c "import lancedb; print(lancedb.__version__)"` e ajuste para a assinatura da versão (em versões novas o FTS nativo é o default e basta `create_fts_index("text", replace=True)`).

- [ ] **Step 5: Commit**

```bash
git add server/src/grimoire_mcp/store.py server/tests/test_store.py
git commit -m "feat(server): IndexStore com LanceDB, manifest e sync incremental"
```

---

### Task 7: Busca híbrida com RRF

**Files:**
- Create: `server/src/grimoire_mcp/search.py`
- Test: `server/tests/test_search.py`

- [ ] **Step 1: Teste falhando**

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_search.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementar `search.py`**

```python
from .store import IndexStore, _quote

RRF_K = 60
CANDIDATES = 30
MAX_SNIPPET_LINES = 40


def _build_where(language: str | None, path_prefix: str | None) -> str | None:
    parts = []
    if language:
        parts.append(f"language = {_quote(language)}")
    if path_prefix:
        parts.append(f"file_path LIKE {_quote(path_prefix + '%')}")
    return " AND ".join(parts) or None


def _ranked(rows: list[dict]) -> dict[str, tuple[int, dict]]:
    return {
        f"{r['file_path']}:{r['start_line']}": (rank, r)
        for rank, r in enumerate(rows)
    }


def hybrid_search(
    store: IndexStore,
    query: str,
    top_k: int = 8,
    language: str | None = None,
    path_prefix: str | None = None,
) -> list[dict]:
    store.sync()  # lazy: índice sempre fresco antes de buscar
    if store.chunks.count_rows() == 0:
        return []
    where = _build_where(language, path_prefix)

    vec = store.embed_fn([query])[0]
    vq = store.chunks.search(vec).limit(CANDIDATES)
    fq = store.chunks.search(query, query_type="fts").limit(CANDIDATES)
    if where:
        vq = vq.where(where, prefilter=True)
        fq = fq.where(where)
    vector_rows = vq.to_list()
    try:
        fts_rows = fq.to_list()
    except Exception:
        fts_rows = []  # query FTS inválida (só pontuação etc.) não derruba a busca

    scores: dict[str, float] = {}
    rows_by_key: dict[str, dict] = {}
    for ranked in (_ranked(vector_rows), _ranked(fts_rows)):
        for key, (rank, row) in ranked.items():
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            rows_by_key[key] = row

    ordered = sorted(scores, key=scores.get, reverse=True)[:top_k]
    results = []
    for key in ordered:
        row = rows_by_key[key]
        snippet_lines = row["text"].splitlines()[:MAX_SNIPPET_LINES]
        results.append({
            "file": row["file_path"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "symbol": row["symbol"],
            "kind": row["kind"],
            "language": row["language"],
            "score": round(scores[key], 4),
            "snippet": "\n".join(snippet_lines),
        })
    return results
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_search.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add server/src/grimoire_mcp/search.py server/tests/test_search.py
git commit -m "feat(server): busca híbrida vetor+FTS com fusão RRF e filtros"
```

---

### Task 8: Server fastmcp (tools + entrypoint)

**Files:**
- Create: `server/src/grimoire_mcp/server.py`
- Test: `server/tests/test_server.py`

- [ ] **Step 1: Teste falhando** (usa o client in-memory do fastmcp)

```python
import json

import pytest
from fastmcp import Client

from grimoire_mcp.server import mcp
import grimoire_mcp.server as server_mod
from tests.conftest import fake_embed


@pytest.fixture(autouse=True)
def fast_embeddings(monkeypatch, tmp_path):
    monkeypatch.setattr("grimoire_mcp.config.GRIMOIRE_HOME", tmp_path / "h")
    monkeypatch.setattr(server_mod, "_EMBED_FN", fake_embed)
    server_mod._STORES.clear()


async def test_index_then_search(sample_repo):
    async with Client(mcp) as client:
        stats = (await client.call_tool("index_project", {"path": str(sample_repo)})).data
        assert stats["files_total"] == 3

        results = (await client.call_tool("search", {
            "query": "getUserById",
            "project_path": str(sample_repo),
            "top_k": 3,
        })).data
        assert results[0]["file"] == "src/orders.ts"


async def test_outline(sample_repo):
    async with Client(mcp) as client:
        outline = (await client.call_tool("outline", {
            "project_path": str(sample_repo),
            "file_path": "src/users.py",
        })).data
        symbols = {o["symbol"] for o in outline}
        assert {"validate_cpf", "format_document", "UserService"} <= symbols
        assert all("text" not in o for o in outline)  # outline não carrega corpos


async def test_status_lists_indexed_projects(sample_repo):
    async with Client(mcp) as client:
        await client.call_tool("index_project", {"path": str(sample_repo)})
        status = (await client.call_tool("status", {})).data
        assert any(p["project_path"] == str(sample_repo) for p in status)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd server && uv run pytest tests/test_server.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementar `server.py`**

```python
import json
from pathlib import Path

from fastmcp import FastMCP

from . import config
from .chunker import chunk_file
from .search import hybrid_search
from .store import IndexStore

mcp = FastMCP(
    "grimoire",
    instructions=(
        "Busca semântica local em projetos de código. Use `search` em vez de ler "
        "arquivos inteiros: ela retorna só os trechos relevantes com file:line. "
        "Use `outline` para ver a estrutura de um arquivo sem carregar os corpos."
    ),
)

_EMBED_FN = None  # testes injetam fake; produção usa o default do IndexStore
_STORES: dict[str, IndexStore] = {}


def _store_for(project_path: str) -> IndexStore:
    root = str(Path(project_path).resolve())
    if root not in _STORES:
        _STORES[root] = IndexStore(Path(root), embed_fn=_EMBED_FN)
    return _STORES[root]


@mcp.tool
def index_project(path: str) -> dict:
    """Indexa (ou atualiza incrementalmente) um projeto para busca semântica."""
    return _store_for(path).sync()


@mcp.tool
def search(
    query: str,
    project_path: str,
    top_k: int = 8,
    language: str | None = None,
    path_prefix: str | None = None,
) -> list[dict]:
    """Busca híbrida (semântica + texto exato) no projeto.

    Retorna trechos com file, start_line/end_line, symbol e score.
    Aceita consultas conceituais ("onde valida CPF") e identificadores exatos.
    """
    return hybrid_search(
        _store_for(project_path), query,
        top_k=top_k, language=language, path_prefix=path_prefix,
    )


@mcp.tool
def outline(project_path: str, file_path: str) -> list[dict]:
    """Estrutura de símbolos de um arquivo (sem corpos) — barato em tokens."""
    full = Path(project_path).resolve() / file_path
    text = full.read_text(errors="replace")
    return [
        {
            "symbol": c.symbol, "kind": c.kind,
            "start_line": c.start_line, "end_line": c.end_line,
            "signature": c.text.splitlines()[0].strip() if c.text else "",
        }
        for c in chunk_file(file_path, text)
    ]


@mcp.tool
def status() -> list[dict]:
    """Lista projetos indexados com contagem de chunks."""
    indexes = config.GRIMOIRE_HOME / "indexes"
    out = []
    if indexes.exists():
        for d in indexes.iterdir():
            manifest = d / "manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text())
                out.append({
                    "project_path": data["project_path"],
                    "files": len(data["files"]),
                })
    return out


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

Atenção ao detalhe de teste: `status` lê `config.GRIMOIRE_HOME` no corpo da função (não no import), então o monkeypatch de `grimoire_mcp.config.GRIMOIRE_HOME` funciona. `IndexStore` também referencia `config.index_dir` em runtime — confirme que `store.py` usa `from . import config` + `config.index_dir(...)` (como escrito na Task 6), não `from .config import index_dir`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd server && uv run pytest tests/test_server.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Rodar a suíte inteira**

Run: `cd server && uv run pytest -v`
Expected: todos PASSED (slow deselected)

- [ ] **Step 6: Commit**

```bash
git add server/src/grimoire_mcp/server.py server/tests/test_server.py
git commit -m "feat(server): MCP server fastmcp com index_project, search, outline e status"
```

---

### Task 9: Smoke test end-to-end real + README do server

**Files:**
- Create: `server/README.md`

- [ ] **Step 1: Smoke manual com modelo real (primeira execução baixa ~120MB)**

Run:
```bash
cd server && uv run python -c "
from pathlib import Path
from grimoire_mcp.store import IndexStore
from grimoire_mcp.search import hybrid_search
store = IndexStore(Path('.').resolve())
print(store.sync())
for r in hybrid_search(store, 'como o chunking divide classes grandes?', top_k=3):
    print(r['file'], r['start_line'], r['symbol'], r['score'])
"
```
Expected: stats com `files_total > 0` e 3 resultados apontando para `src/grimoire_mcp/chunker.py`.

- [ ] **Step 2: Testar o servidor via stdio**

Run: `cd server && timeout 5 uv run grimoire-mcp <<< '' ; echo "exit: $?"`
Expected: processo sobe sem traceback (sai por EOF/timeout, não por erro de import).

- [ ] **Step 3: Escrever `server/README.md`**

```markdown
# grimoire-mcp

MCP server local de busca semântica em código. Indexa seu projeto na sua máquina
(embeddings locais via fastembed, índice LanceDB) e expõe busca híbrida
(semântica + BM25) para agentes de IA — trechos certos em vez de arquivos inteiros.

## Instalação (Claude Code)

```bash
claude mcp add grimoire -- uvx grimoire-mcp
```

## Tools

| Tool | Descrição |
|---|---|
| `index_project(path)` | Indexa/atualiza um projeto (incremental por hash) |
| `search(query, project_path, top_k, language, path_prefix)` | Busca híbrida com file:line |
| `outline(project_path, file_path)` | Símbolos de um arquivo sem os corpos |
| `status()` | Projetos indexados |

O índice fica em `~/.grimoire/indexes/` — nada é gravado dentro dos seus repos.

## Desenvolvimento

```bash
cd server
uv sync
uv run pytest            # rápido (embeddings fake)
uv run pytest -m slow    # baixa o modelo real
```
```

- [ ] **Step 4: Commit**

```bash
git add server/README.md
git commit -m "docs(server): README com instalação e tools"
```

---

### Task 10: CI (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Criar workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  server-tests:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: server
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - run: uv sync
      - run: uv run pytest -v
```

- [ ] **Step 2: Validar sintaxe localmente**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: testes do server no GitHub Actions"
```
