# grimoire-mcp

MCP server local de busca semântica em código. Indexa seu projeto na sua máquina
(embeddings locais via fastembed, índice LanceDB) e expõe busca híbrida
(semântica + BM25) para agentes de IA — trechos certos em vez de arquivos inteiros.

> **Status:** v0.3.0 (alpha) — ainda não publicado no PyPI.
> Enquanto isso, troque `uvx grimoire-mcp` nos comandos abaixo por
> `uv run --project /caminho/para/grimoire/server grimoire-mcp` (direto do clone).

## Instalação

### Claude Code

```bash
claude mcp add grimoire -- uvx grimoire-mcp
```

### VS Code (GitHub Copilot)

```bash
code --add-mcp '{"name":"grimoire","command":"uvx","args":["grimoire-mcp"]}'
```

Ou crie `.vscode/mcp.json` no projeto:

```json
{
  "servers": {
    "grimoire": { "type": "stdio", "command": "uvx", "args": ["grimoire-mcp"] }
  }
}
```

### Cursor

`~/.cursor/mcp.json` (global) ou `.cursor/mcp.json` no projeto:

```json
{
  "mcpServers": {
    "grimoire": { "command": "uvx", "args": ["grimoire-mcp"] }
  }
}
```

### Codex CLI

```bash
codex mcp add grimoire -- uvx grimoire-mcp
```

### Gemini CLI

```bash
gemini mcp add grimoire uvx grimoire-mcp
```

### Windsurf

`~/.codeium/windsurf/mcp_config.json` — mesmo formato `mcpServers` do Cursor.

### Claude Desktop

`claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "grimoire": { "command": "uvx", "args": ["grimoire-mcp"] }
  }
}
```

## Tools

| Tool | Descrição |
|---|---|
| `index_project(project_path)` | Indexa/atualiza um projeto (incremental por hash) |
| `search(query, project_path, top_k, language, path_prefix)` | Busca híbrida com file:line |
| `outline(project_path, file_path)` | Símbolos de um arquivo sem os corpos |
| `status()` | Projetos indexados |
| `find_references(symbol, project_path, limit)` | Definições e usos exatos de um identificador |
| `dependencies_of(file_path, project_path)` | Imports do arquivo: locais resolvidos, externos, não resolvidos |
| `dependents_of(file_path, project_path)` | Quem importa o arquivo (impacto reverso) |
| `extract_rules(project_path, scope, batch, cursor)` | Chunks candidatos + instruções para o agente extrair regras |
| `save_rules(project_path, rules)` | Valida e persiste regras com rastreabilidade file:line |
| `rules(project_path, file_path)` | Lista regras extraídas (com flag stale) |
| `delete_rule(project_path, rule_id)` | Remove uma regra |

O índice fica em `~/.grimoire/indexes/` — nada é gravado dentro dos seus repos.

## Desenvolvimento

```bash
cd server
uv sync
uv run pytest            # rápido (embeddings fake)
uv run pytest -m slow    # baixa o modelo real
```
