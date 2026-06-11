import threading

from fastembed import TextEmbedding

from .config import EMBEDDING_MODEL

_model: TextEmbedding | None = None
_lock = threading.Lock()


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        # fastmcp roda tools síncronas em thread pool — sem o lock, chamadas
        # concorrentes na partida carregariam o modelo (~220MB) N vezes.
        with _lock:
            if _model is None:
                _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [e.tolist() for e in _get_model().embed(texts)]
