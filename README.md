# Grimoire

> Local semantic search MCP server — surgical context retrieval for AI agents.
> Busca semântica local para agentes de IA. Sem nuvem, sem Docker, sem API key.

| Pasta | O quê |
|---|---|
| [`server/`](./server) | MCP server Python (`grimoire-mcp`) |
| [`web/`](./web) | Landing page (Next.js, en/pt-BR) |
| [`docs/`](./docs) | Specs e planos |

## Quickstart

Quando publicado no PyPI:

```bash
claude mcp add grimoire -- uvx grimoire-mcp
```

Por enquanto, direto do clone:

```bash
claude mcp add grimoire -- uv run --project /caminho/para/grimoire/server grimoire-mcp
```

Docs completos no [`server/README.md`](./server/README.md). Roadmap em [`ROADMAP.md`](./ROADMAP.md).
