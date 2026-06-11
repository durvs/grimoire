# Grimoire Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Landing page estática bilíngue (en/pt-BR) em `web/`, publicada na Vercel, com o repo no GitHub do usuário.

**Architecture:** Next.js App Router com rota dinâmica `/[lang]` (en | pt) e `generateStaticParams` — páginas 100% estáticas. A raiz `/` redireciona server-side pelo header `Accept-Language` (sem middleware, evita divergência middleware/proxy entre versões do Next). Dicionários são JSONs simples importados estaticamente — sem lib de i18n (YAGNI para 2 idiomas e 1 página). Estilo via Tailwind, dark, estética dev-tool.

**Tech Stack:** Next.js (latest, App Router), TypeScript, Tailwind CSS, deploy via `vercel` CLI (root directory `web/`), repo via `gh` CLI.

**File structure:**

```
web/
  app/
    page.tsx                 # redirect / -> /en ou /pt por Accept-Language
    layout.tsx               # root layout mínimo (html/body)
    [lang]/
      layout.tsx             # metadata por idioma
      page.tsx               # a landing (seções inline)
  dictionaries/
    en.json
    pt.json
  lib/i18n.ts                # tipos + getDictionary
```

**Nota de execução:** ao implementar a Task 3 (página), invoque o skill `frontend-design:frontend-design` para elevar o acabamento visual — o código abaixo é a baseline funcional e de conteúdo; estrutura e textos devem ser preservados.

---

### Task 1: Scaffold do Next.js em `web/`

- [ ] **Step 1: Criar o app**

Run:
```bash
cd ~/Workspace/grimoire && npx -y create-next-app@latest web \
  --typescript --tailwind --eslint --app --no-src-dir \
  --import-alias "@/*" --use-npm --yes
```
Expected: pasta `web/` criada, `npm run dev` funcional.

- [ ] **Step 2: Limpar boilerplate**

Remover conteúdo default: zerar `web/app/page.tsx` (será substituído na Task 2) e apagar assets não usados (`web/public/*.svg`). Manter `globals.css` com o import do Tailwind.

- [ ] **Step 3: Verificar build**

Run: `cd web && npm run build`
Expected: build sem erros.

- [ ] **Step 4: Commit**

```bash
git add web/
git commit -m "feat(web): scaffold Next.js + Tailwind"
```

---

### Task 2: i18n — dicionários, tipos e redirect por idioma

**Files:**
- Create: `web/dictionaries/en.json`, `web/dictionaries/pt.json`
- Create: `web/lib/i18n.ts`
- Create: `web/app/page.tsx` (redirect), `web/app/[lang]/layout.tsx`

- [ ] **Step 1: Criar `web/dictionaries/en.json`**

```json
{
  "nav": { "github": "GitHub", "switchLang": "Português" },
  "hero": {
    "tagline": "Local semantic search for AI agents",
    "title": "Your context window runs out before your problem does.",
    "subtitle": "Grimoire indexes your codebase on your machine and hands your AI agent only the snippets that matter — file and line included. No cloud, no Docker, no API key.",
    "cta": "Get started",
    "install": "claude mcp add grimoire -- uvx grimoire-mcp"
  },
  "math": {
    "title": "The token math",
    "before": { "label": "Without Grimoire", "value": "~80k tokens", "desc": "Agent re-reads 15 full files to answer one question" },
    "after": { "label": "With Grimoire", "value": "~2k tokens", "desc": "Agent retrieves the 5 snippets that actually matter" },
    "footnote": "Same answer. 40x less context."
  },
  "how": {
    "title": "How it works",
    "items": [
      { "title": "Structural chunking", "desc": "tree-sitter splits code into real units — functions, classes, methods — never blind text blocks." },
      { "title": "Hybrid search", "desc": "Vector search for concepts (\"where is CPF validated?\") plus BM25 for exact identifiers (getUserById). Fused with RRF." },
      { "title": "Zero infrastructure", "desc": "Embeddings run locally. The index is a file on disk. Your code never leaves your machine." },
      { "title": "Always fresh", "desc": "Each search re-indexes only the files that changed. No daemon, no stale results." }
    ]
  },
  "quickstart": {
    "title": "Quickstart",
    "steps": [
      { "label": "Add to Claude Code", "code": "claude mcp add grimoire -- uvx grimoire-mcp" },
      { "label": "Ask your agent", "code": "\"search the project for where discounts are calculated\"" }
    ]
  },
  "roadmap": {
    "title": "Roadmap",
    "items": [
      { "version": "Now", "desc": "Hybrid semantic search over any local project" },
      { "version": "V1.1", "desc": "References & dependency graph — who calls this function?" },
      { "version": "V1.2", "desc": "Business-rule extraction with file:line traceability" },
      { "version": "V1.3", "desc": "Persistent per-project memory for decisions" }
    ]
  },
  "footer": { "text": "Open source, MIT. Built for agents that read too much." }
}
```

- [ ] **Step 2: Criar `web/dictionaries/pt.json`**

```json
{
  "nav": { "github": "GitHub", "switchLang": "English" },
  "hero": {
    "tagline": "Busca semântica local para agentes de IA",
    "title": "Sua janela de contexto acaba antes do seu problema.",
    "subtitle": "O Grimoire indexa seu código na sua máquina e entrega ao agente só os trechos que importam — com arquivo e linha. Sem nuvem, sem Docker, sem API key.",
    "cta": "Comece agora",
    "install": "claude mcp add grimoire -- uvx grimoire-mcp"
  },
  "math": {
    "title": "A conta dos tokens",
    "before": { "label": "Sem Grimoire", "value": "~80 mil tokens", "desc": "O agente relê 15 arquivos inteiros para responder uma pergunta" },
    "after": { "label": "Com Grimoire", "value": "~2 mil tokens", "desc": "O agente recebe os 5 trechos que realmente importam" },
    "footnote": "Mesma resposta. 40x menos contexto."
  },
  "how": {
    "title": "Como funciona",
    "items": [
      { "title": "Chunking estrutural", "desc": "tree-sitter corta o código em unidades reais — funções, classes, métodos — nunca blocos cegos de texto." },
      { "title": "Busca híbrida", "desc": "Busca vetorial para conceitos (\"onde valida CPF?\") + BM25 para identificadores exatos (getUserById). Fundidas com RRF." },
      { "title": "Zero infraestrutura", "desc": "Embeddings rodam localmente. O índice é um arquivo no disco. Seu código nunca sai da sua máquina." },
      { "title": "Sempre fresco", "desc": "Cada busca re-indexa só os arquivos que mudaram. Sem daemon, sem resultado obsoleto." }
    ]
  },
  "quickstart": {
    "title": "Comece em um minuto",
    "steps": [
      { "label": "Adicione ao Claude Code", "code": "claude mcp add grimoire -- uvx grimoire-mcp" },
      { "label": "Pergunte ao agente", "code": "\"busque no projeto onde o desconto é calculado\"" }
    ]
  },
  "roadmap": {
    "title": "Roadmap",
    "items": [
      { "version": "Hoje", "desc": "Busca semântica híbrida em qualquer projeto local" },
      { "version": "V1.1", "desc": "Referências e grafo de dependências — quem chama essa função?" },
      { "version": "V1.2", "desc": "Extração de regras de negócio com rastreabilidade file:line" },
      { "version": "V1.3", "desc": "Memória persistente de decisões por projeto" }
    ]
  },
  "footer": { "text": "Open source, MIT. Feito para agentes que leem demais." }
}
```

- [ ] **Step 3: Criar `web/lib/i18n.ts`**

```ts
import en from "@/dictionaries/en.json";
import pt from "@/dictionaries/pt.json";

export const locales = ["en", "pt"] as const;
export type Locale = (typeof locales)[number];
export type Dictionary = typeof en;

const dictionaries: Record<Locale, Dictionary> = { en, pt };

export function getDictionary(lang: Locale): Dictionary {
  return dictionaries[lang];
}

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}
```

- [ ] **Step 4: Criar `web/app/page.tsx` (redirect por Accept-Language)**

```tsx
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function RootPage() {
  const accept = (await headers()).get("accept-language") ?? "";
  redirect(accept.toLowerCase().includes("pt") ? "/pt" : "/en");
}
```

- [ ] **Step 5: Criar `web/app/[lang]/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { isLocale, locales } from "@/lib/i18n";
import { notFound } from "next/navigation";

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  const pt = lang === "pt";
  return {
    title: pt
      ? "Grimoire — busca semântica local para agentes de IA"
      : "Grimoire — local semantic search for AI agents",
    description: pt
      ? "Indexe seu código na sua máquina e entregue ao agente só os trechos que importam. Sem nuvem, sem Docker, sem API key."
      : "Index your codebase on your machine and hand your AI agent only the snippets that matter. No cloud, no Docker, no API key.",
  };
}

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return children;
}
```

- [ ] **Step 6: Verificar build** (a página `[lang]/page.tsx` ainda não existe; criar um stub temporário que renderiza `<main>{lang}</main>` para o build passar)

Run: `cd web && npm run build`
Expected: build OK, rotas `/en` e `/pt` estáticas (`●` no output), `/` dinâmica.

- [ ] **Step 7: Commit**

```bash
git add web/
git commit -m "feat(web): i18n en/pt-BR com rotas estáticas e redirect por Accept-Language"
```

---

### Task 3: Página da landing

**Files:**
- Create: `web/app/[lang]/page.tsx` (substitui o stub)

> Invoque `frontend-design:frontend-design` neste task para refinar o visual. O código abaixo é a baseline: estrutura de seções e conteúdo dos dicionários são obrigatórios; classes/estética podem ser melhoradas.

- [ ] **Step 1: Implementar a página**

```tsx
import Link from "next/link";
import { getDictionary, isLocale, type Locale } from "@/lib/i18n";
import { notFound } from "next/navigation";

const GITHUB_URL = "https://github.com/duurval/grimoire";

export default async function Landing({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang as Locale);
  const otherLang = lang === "pt" ? "en" : "pt";

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
      {/* Nav */}
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <span className="font-mono text-lg font-bold tracking-tight">
          grimoire<span className="text-violet-400">_</span>
        </span>
        <div className="flex items-center gap-4 text-sm text-zinc-400">
          <Link href={`/${otherLang}`} className="hover:text-zinc-100">
            {t.nav.switchLang}
          </Link>
          <a href={GITHUB_URL} className="hover:text-zinc-100">
            {t.nav.github}
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 pb-20 pt-16 text-center">
        <p className="mb-4 font-mono text-sm uppercase tracking-widest text-violet-400">
          {t.hero.tagline}
        </p>
        <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-tight sm:text-6xl">
          {t.hero.title}
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400">
          {t.hero.subtitle}
        </p>
        <div className="mx-auto mt-10 max-w-xl rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-left">
          <code className="font-mono text-sm text-emerald-400">
            $ {t.hero.install}
          </code>
        </div>
      </section>

      {/* Token math */}
      <section className="border-y border-zinc-900 bg-zinc-900/40 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-10 text-center text-2xl font-bold">{t.math.title}</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {[t.math.before, t.math.after].map((card, i) => (
              <div
                key={card.label}
                className={`rounded-xl border p-8 ${
                  i === 0
                    ? "border-red-900/50 bg-red-950/20"
                    : "border-emerald-900/50 bg-emerald-950/20"
                }`}
              >
                <p className="text-sm uppercase tracking-wide text-zinc-400">{card.label}</p>
                <p className={`mt-2 text-4xl font-bold ${i === 0 ? "text-red-400" : "text-emerald-400"}`}>
                  {card.value}
                </p>
                <p className="mt-3 text-zinc-400">{card.desc}</p>
              </div>
            ))}
          </div>
          <p className="mt-8 text-center font-mono text-zinc-500">{t.math.footnote}</p>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="mb-10 text-center text-2xl font-bold">{t.how.title}</h2>
        <div className="grid gap-6 sm:grid-cols-2">
          {t.how.items.map((item) => (
            <div key={item.title} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
              <h3 className="font-semibold text-violet-300">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-400">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Quickstart */}
      <section className="border-y border-zinc-900 bg-zinc-900/40 py-16">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="mb-8 text-center text-2xl font-bold">{t.quickstart.title}</h2>
          <ol className="space-y-4">
            {t.quickstart.steps.map((step, i) => (
              <li key={step.label} className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <p className="mb-2 text-sm text-zinc-400">
                  <span className="mr-2 font-mono text-violet-400">{i + 1}.</span>
                  {step.label}
                </p>
                <code className="block overflow-x-auto font-mono text-sm text-emerald-400">
                  {step.code}
                </code>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Roadmap */}
      <section className="mx-auto max-w-3xl px-6 py-20">
        <h2 className="mb-10 text-center text-2xl font-bold">{t.roadmap.title}</h2>
        <ul className="space-y-0">
          {t.roadmap.items.map((item, i) => (
            <li key={item.version} className="flex gap-4 border-l border-zinc-800 pb-8 pl-6 last:pb-0">
              <span className={`-ml-[1.85rem] mt-1 h-3 w-3 shrink-0 rounded-full ${i === 0 ? "bg-violet-400" : "bg-zinc-700"}`} />
              <div>
                <p className="font-mono text-sm font-bold text-violet-300">{item.version}</p>
                <p className="text-zinc-400">{item.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-900 py-10 text-center text-sm text-zinc-500">
        <p>{t.footer.text}</p>
        <a href={GITHUB_URL} className="mt-2 inline-block text-zinc-400 hover:text-zinc-100">
          {GITHUB_URL.replace("https://", "")}
        </a>
      </footer>
    </main>
  );
}
```

- [ ] **Step 2: Build e inspeção visual**

Run: `cd web && npm run build && npm run dev`
Abrir `http://localhost:3000` — deve redirecionar para `/en` ou `/pt` conforme o idioma do navegador; conferir as duas rotas e o switch de idioma. Usar o Claude Preview/screenshot para validar visual nas larguras 1280px e 390px.

- [ ] **Step 3: Commit**

```bash
git add web/app
git commit -m "feat(web): landing bilíngue com hero, token math, quickstart e roadmap"
```

---

### Task 4: README raiz e ROADMAP do monorepo

**Files:**
- Create: `README.md`
- Create: `ROADMAP.md`

- [ ] **Step 0: Criar `ROADMAP.md`**

```markdown
# Roadmap

- **Agora — V1.0**: busca semântica híbrida (vetor + BM25) em qualquer projeto local; chunking estrutural; índice incremental
- **V1.1 — Referências e dependências**: imports/defs extraídos no passe de chunking; `find_references(symbol)` e `dependencies_of(file)`
- **V1.2 — Regras de negócio**: `extract_rules(scope)` via MCP sampling (LLM do próprio cliente); confidence score + rastreabilidade `file:line`
- **V1.3 — Memória de sessão**: `remember()`/`recall()` por projeto
- **V2**: watcher opcional, reranker local, multi-repo, export de documentação
```

- [ ] **Step 1: Escrever**

```markdown
# Grimoire

> Local semantic search MCP server — surgical context retrieval for AI agents.
> Busca semântica local para agentes de IA. Sem nuvem, sem Docker, sem API key.

| Pasta | O quê |
|---|---|
| [`server/`](./server) | MCP server Python (`grimoire-mcp` no PyPI) |
| [`web/`](./web) | Landing page (Next.js, en/pt-BR) |
| [`docs/`](./docs) | Specs e planos |

## Quickstart

```bash
claude mcp add grimoire -- uvx grimoire-mcp
```

Docs completos no [`server/README.md`](./server/README.md).
```

- [ ] **Step 2: Commit**

```bash
git add README.md ROADMAP.md
git commit -m "docs: README raiz e ROADMAP do monorepo"
```

---

### Task 5: GitHub + deploy na Vercel

- [ ] **Step 1: Criar repo no GitHub e push**

Run:
```bash
cd ~/Workspace/grimoire
gh repo create grimoire --public --source=. --push \
  --description "Local semantic search MCP server for AI agents - no cloud, no Docker, no API key"
```
Expected: repo criado e branch main publicada. Confirmar a URL real do repo (`gh repo view --json url`) e, se for diferente de `https://github.com/duurval/grimoire`, corrigir `GITHUB_URL` em `web/app/[lang]/page.tsx` e o link no README, commitando em seguida.

- [ ] **Step 2: Deploy preview na Vercel**

Run:
```bash
cd ~/Workspace/grimoire/web
vercel deploy --yes
```
Expected: deploy preview com URL. O projeto Vercel é criado com root em `web/`. Abrir a URL e conferir `/en` e `/pt`.

- [ ] **Step 3: Deploy de produção**

Run: `cd ~/Workspace/grimoire/web && vercel --prod`
Expected: URL de produção funcional.

- [ ] **Step 4: Conectar o projeto Vercel ao repo GitHub** (deploys automáticos por push)

Run: `cd ~/Workspace/grimoire/web && vercel git connect`
Expected: projeto conectado ao repo; pushes em `main` passam a gerar deploys.

- [ ] **Step 5: Verificação final**

Run: `curl -sI <url-producao>/pt | head -3 && curl -s <url-producao>/en | grep -o "<title>[^<]*"`
Expected: HTTP 200 nas duas rotas, title em inglês na `/en`.
