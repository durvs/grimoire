# Grimoire — Design Spec

> Data: 2026-06-10 · Status: aprovado em brainstorming
> MCP server local de busca semântica sobre projetos, para economizar janela de contexto de agentes de IA.

## 1. Problema

No workflow com Claude Code (e agentes em geral), a janela de contexto é consumida majoritariamente por arquivos do projeto carregados inteiros. Contextos estouram o limite do modelo rapidamente, encarecendo e degradando as sessões.

O agente não precisa do arquivo inteiro — precisa dos trechos relevantes. Recuperar os 5 trechos certos (~2k tokens) substitui a leitura de 15 arquivos (~80k tokens).

## 2. Visão

**Grimoire** é um MCP server local que indexa projetos e expõe ferramentas de busca cirúrgicas para agentes. Zero infra: sem Docker, sem API key, sem nuvem. Instalou, funciona.

Herança direta do `ai-modernization-pipeline` (chunking hierárquico, RAG, rastreabilidade `file:line`) destilada em dev tool, com inspiração no claude-mem para a camada futura de memória.

## 3. Decisões de arquitetura

| Decisão | Escolha | Racional |
|---|---|---|
| Linguagem/framework | Python 3.11+, `fastmcp` 2.x, transporte stdio | Ecossistema RAG maduro (fastembed, tree-sitter, LanceDB); distribuição via `uvx` |
| Embeddings | Locais, via fastembed; default `intfloat/multilingual-e5-small`, trocável via config | Custo zero, privado, sem API key; multilíngue cobre código em inglês + docs/regras em pt-BR |
| Vector store | LanceDB embedded em `~/.grimoire/indexes/<hash-do-path>/` | Zero infra; vetor + FTS (BM25) no mesmo arquivo; índice fora do repo do usuário |
| Busca | Híbrida: vetorial + BM25 com fusão RRF | Vetor cobre consultas conceituais; BM25 cobre identificadores exatos |
| Chunking | Estrutural via tree-sitter (`tree-sitter-language-pack`): função/classe/método com contexto pai. Fallback: headers (Markdown), blocos (texto/config) | Chunks correspondem a unidades reais de código; não corta funções no meio |
| Atualização do índice | Lazy + incremental: `search` roda re-index incremental antes de responder; hash por arquivo; respeita `.gitignore` | Índice sempre razoavelmente fresco sem daemon/watcher |
| Nome do pacote | PyPI `grimoire-mcp` (livre; `grimoire` está ocupado), marca "Grimoire" | Verificado em 2026-06-10 |

### Schema do chunk

Cada chunk persiste: `file_path, start_line, end_line, symbol, kind, language, hash, text, vector`.
Esses campos preparam o terreno para grafo de referências (V1.1) e regras de negócio (V1.2) sem migração de schema.

## 4. Tools MCP (MVP)

| Tool | Comportamento |
|---|---|
| `index_project(path)` | Indexa na primeira chamada; depois incremental (apenas arquivos com hash alterado) |
| `search(query, top_k, filters)` | Busca híbrida; retorna trechos com `file:line`, símbolo, score. Dispara re-index incremental antes |
| `outline(path)` | Esqueleto de símbolos do arquivo (assinaturas, sem corpos) — estrutura por ~100 tokens |
| `status()` | Projetos indexados, nº de chunks, staleness do índice |

## 5. Roadmap

- **V1.1 — Referências e dependências**: extrair imports/defs via tree-sitter no mesmo passe de chunking; tools `find_references(symbol)` e `dependencies_of(file)`
- **V1.2 — Regras de negócio**: tool `extract_rules(scope)` usando o LLM do próprio cliente via MCP sampling (sem custo de API próprio); regras com confidence score e rastreabilidade `file:line`; buscáveis via `search(filter=rules)`
- **V1.3 — Memória de sessão**: `remember()`/`recall()` estilo claude-mem; decisões persistidas por projeto
- **V2**: watcher opcional, reranker local, multi-repo, export de documentação

## 6. Landing page

- Next.js App Router, estática, deploy na Vercel; repo monorepo: `server/` (Python) + `web/` (Next.js)
- Bilíngue **en/pt-BR** via rotas `/en` e `/pt` com detecção de idioma
- Seções: hero (dor da janela de contexto), comparação antes/depois em tokens, quickstart (`claude mcp add grimoire -- uvx grimoire-mcp`), roadmap, link GitHub

## 7. Testes e qualidade

- pytest com repo-fixture sintético (Python + TypeScript + Markdown)
- Casos: chunking estrutural por símbolo; incremental (arquivo alterado → só ele re-embedado); busca híbrida (query conceitual e query por identificador exato); respeito a `.gitignore`
- CI: GitHub Actions (lint + testes)

## 8. Não-objetivos (MVP)

- Grafo de chamadas/referências (V1.1)
- Extração de regras de negócio (V1.2)
- Daemon/file watcher (V2)
- Qualquer dependência de serviço externo (Qdrant, APIs de embedding)
