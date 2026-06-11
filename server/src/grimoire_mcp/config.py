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
