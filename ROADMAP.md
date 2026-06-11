# Roadmap

- **Agora — V1.1**: busca semântica híbrida (vetor + BM25); chunking estrutural; índice incremental; referências (`find_references`) e grafo de dependências (`dependencies_of`/`dependents_of`) com imports resolvidos
- **V1.2 — Regras de negócio**: `extract_rules(scope)` via MCP sampling (LLM do próprio cliente); confidence score + rastreabilidade `file:line`
- **V1.3 — Memória de sessão**: `remember()`/`recall()` por projeto
- **V2**: watcher opcional, reranker local, multi-repo, export de documentação; defs para arrow functions TS (`const f = () => {}`)
