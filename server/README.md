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
| `index_project(project_path)` | Indexa/atualiza um projeto (incremental por hash) |
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
