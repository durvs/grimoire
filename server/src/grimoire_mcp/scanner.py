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
    # Apenas o .gitignore da raiz é carregado; .gitignore aninhados não são suportados.
    gi = root / ".gitignore"
    try:
        lines = gi.read_text().splitlines()
    except OSError:
        lines = []
    return pathspec.PathSpec.from_lines("gitignore", lines)


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
            and not spec.match_file(Path(dirpath, d).relative_to(root).as_posix() + "/")
        ]
        for name in filenames:
            if name.startswith("."):
                continue  # skip hidden/dotfiles (e.g. .gitignore, .env) — not useful for semantic search
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
