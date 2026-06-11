# Roadmap

- **Agora — V1.0**: busca semântica híbrida (vetor + BM25) em qualquer projeto local; chunking estrutural; índice incremental
- **V1.1 — Referências e dependências**: imports/defs extraídos no passe de chunking; `find_references(symbol)` e `dependencies_of(file)`
- **V1.2 — Regras de negócio**: `extract_rules(scope)` via MCP sampling (LLM do próprio cliente); confidence score + rastreabilidade `file:line`
- **V1.3 — Memória de sessão**: `remember()`/`recall()` por projeto
- **V2**: watcher opcional, reranker local, multi-repo, export de documentação
