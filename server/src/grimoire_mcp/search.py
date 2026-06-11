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
    # LanceDB 0.33.0: vector_column_name must be specified explicitly when the
    # table has a single vector column named "vector".
    vq = store.chunks.search(vec, vector_column_name="vector").limit(CANDIDATES)
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
