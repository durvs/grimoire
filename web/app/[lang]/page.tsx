import Link from "next/link";
import { notFound } from "next/navigation";
import { getDictionary, isLocale, type Locale } from "@/lib/i18n";

const GITHUB_URL = "https://github.com/duurval/grimoire";

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-mono text-sm tracking-widest uppercase text-zinc-400">
      <span className="mr-3 text-accent select-none" aria-hidden>
        ::
      </span>
      {children}
    </h2>
  );
}

export default async function Landing({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang);
  const otherLang = lang === "pt" ? "en" : "pt";

  return (
    <div className="relative flex-1 overflow-x-clip">
      {/* atmosphere: phosphor glow + hairline grid fading from the top */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[640px] bg-[radial-gradient(ellipse_75%_60%_at_50%_-12%,rgba(60,233,140,0.14),transparent_70%)]" />
        <div className="absolute inset-x-0 top-0 h-[640px] bg-[linear-gradient(to_right,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:52px_52px] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,black,transparent_75%)]" />
      </div>

      {/* nav */}
      <header className="border-b border-white/[0.06]">
        <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link
            href={`/${lang}`}
            className="font-mono text-[15px] font-medium tracking-tight"
          >
            grimoire
            <span
              className="text-accent [animation:blink_1.1s_steps(1)_infinite]"
              aria-hidden
            >
              _
            </span>
          </Link>
          <div className="flex items-center gap-6 font-mono text-[13px] text-zinc-400">
            <Link
              href={`/${otherLang}`}
              className="transition-colors hover:text-foreground"
            >
              {t.nav.switchLang}
            </Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
            >
              {t.nav.github}
              <span
                aria-hidden
                className="text-zinc-600 transition-colors group-hover:text-accent"
              >
                &#8599;
              </span>
            </a>
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-5xl px-6">
        {/* hero */}
        <section className="pt-20 pb-24 sm:pt-28 sm:pb-32">
          <p className="flex items-baseline gap-3 font-mono text-xs tracking-[0.2em] uppercase text-accent">
            <span aria-hidden className="select-none">
              &#9612;
            </span>
            <span>{t.hero.tagline}</span>
          </p>
          <h1 className="mt-6 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-6xl sm:leading-[1.05]">
            {t.hero.title}
          </h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.hero.subtitle}
          </p>

          <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-stretch">
            {/* terminal install block */}
            <div className="min-w-0 flex-1 overflow-hidden rounded-lg border border-white/10 bg-black/50 shadow-[0_0_40px_-12px_rgba(60,233,140,0.25)] sm:max-w-xl">
              <div className="flex items-center gap-1.5 border-b border-white/[0.06] px-4 py-2.5">
                <span className="size-2.5 rounded-full bg-zinc-700" />
                <span className="size-2.5 rounded-full bg-zinc-700" />
                <span className="size-2.5 rounded-full bg-accent/60" />
              </div>
              <div
                className="overflow-x-auto px-4 py-3.5"
                tabIndex={0}
                aria-label={t.hero.install}
              >
                <code className="font-mono text-[13px] whitespace-nowrap text-zinc-200 sm:text-sm">
                  <span className="mr-2 text-accent select-none" aria-hidden>
                    $
                  </span>
                  {t.hero.install}
                </code>
              </div>
            </div>
            <a
              href="#quickstart"
              className="inline-flex items-center justify-center rounded-lg bg-accent px-6 font-mono text-sm font-medium text-[#08090c] transition-all hover:bg-accent/85 hover:shadow-[0_0_24px_-4px_rgba(60,233,140,0.6)] max-sm:py-3.5"
            >
              {t.hero.cta}
              <span aria-hidden className="ml-2">
                &#8595;
              </span>
            </a>
          </div>
        </section>

        {/* token math */}
        <section className="border-t border-white/[0.06] py-20 sm:py-24">
          <SectionTitle>{t.math.title}</SectionTitle>
          <div className="mt-10 grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
            <div className="rounded-lg border border-rose-500/20 bg-rose-500/[0.04] p-6 sm:p-8">
              <p className="font-mono text-xs tracking-widest uppercase text-rose-400/80">
                {t.math.before.label}
              </p>
              <p className="mt-4 font-mono text-3xl font-semibold text-rose-300 sm:text-4xl">
                {t.math.before.value}
              </p>
              <div
                aria-hidden
                className="mt-5 h-1.5 w-full rounded-full bg-rose-400/50"
              />
              <p className="mt-5 text-sm leading-relaxed text-zinc-400">
                {t.math.before.desc}
              </p>
            </div>
            <div
              aria-hidden
              className="flex items-center justify-center font-mono text-2xl text-zinc-600 select-none max-md:rotate-90"
            >
              &#8594;
            </div>
            <div className="rounded-lg border border-accent/25 bg-accent/[0.05] p-6 shadow-[0_0_60px_-20px_rgba(60,233,140,0.35)] sm:p-8">
              <p className="font-mono text-xs tracking-widest uppercase text-accent/90">
                {t.math.after.label}
              </p>
              <p className="mt-4 font-mono text-3xl font-semibold text-accent sm:text-4xl">
                {t.math.after.value}
              </p>
              <div aria-hidden className="mt-5 h-1.5 w-full">
                <div className="h-full w-[2.5%] min-w-2 rounded-full bg-accent" />
              </div>
              <p className="mt-5 text-sm leading-relaxed text-zinc-400">
                {t.math.after.desc}
              </p>
            </div>
          </div>
          <p className="mt-8 text-center font-mono text-sm text-zinc-400">
            {t.math.footnote}
          </p>
        </section>

        {/* how it works */}
        <section className="border-t border-white/[0.06] py-20 sm:py-24">
          <SectionTitle>{t.how.title}</SectionTitle>
          <div className="mt-10 grid gap-px overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.08] sm:grid-cols-2">
            {t.how.items.map((item, i) => (
              <div
                key={item.title}
                className="group bg-background p-6 transition-colors hover:bg-white/[0.02] sm:p-8"
              >
                <p className="font-mono text-xs text-zinc-500 transition-colors group-hover:text-accent">
                  0{i + 1}
                </p>
                <h3 className="mt-3 text-base font-medium text-foreground">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* quickstart */}
        <section
          id="quickstart"
          className="scroll-mt-10 border-t border-white/[0.06] py-20 sm:py-24"
        >
          <SectionTitle>{t.quickstart.title}</SectionTitle>
          <ol className="mt-10 space-y-6">
            {t.quickstart.steps.map((step, i) => (
              <li key={step.label} className="flex gap-5 sm:gap-8">
                <span
                  className="flex size-9 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/[0.06] font-mono text-sm text-accent"
                  aria-hidden
                >
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1 pt-1.5">
                  <p className="text-sm font-medium text-foreground">
                    {step.label}
                  </p>
                  <div
                    className="mt-3 overflow-x-auto rounded-lg border border-white/10 bg-black/50 px-4 py-3.5"
                    tabIndex={0}
                    aria-label={step.code}
                  >
                    <code className="font-mono text-[13px] whitespace-nowrap text-zinc-200 sm:text-sm">
                      <span
                        className="mr-2 text-accent select-none"
                        aria-hidden
                      >
                        {i === 0 ? "$" : "›"}
                      </span>
                      {step.code}
                    </code>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>

        {/* roadmap */}
        <section className="border-t border-white/[0.06] py-20 sm:py-24">
          <SectionTitle>{t.roadmap.title}</SectionTitle>
          <ol className="relative mt-10 space-y-2 before:absolute before:top-3 before:bottom-3 before:left-[5px] before:w-px before:bg-white/10">
            {t.roadmap.items.map((item, i) => (
              <li key={item.version} className="relative flex gap-6 pl-8">
                <span
                  aria-hidden
                  className={
                    i === 0
                      ? "absolute top-[1.4rem] left-0 size-[11px] rounded-full bg-accent [animation:pulse-dot_2.2s_ease-in-out_infinite]"
                      : "absolute top-[1.4rem] left-0 size-[11px] rounded-full border border-white/20 bg-background"
                  }
                />
                <div
                  className={
                    i === 0
                      ? "flex w-full flex-col gap-1 rounded-lg border border-accent/25 bg-accent/[0.05] px-5 py-4 sm:flex-row sm:items-baseline sm:gap-6"
                      : "flex w-full flex-col gap-1 px-5 py-4 sm:flex-row sm:items-baseline sm:gap-6"
                  }
                >
                  <span
                    className={
                      i === 0
                        ? "w-16 shrink-0 font-mono text-sm font-medium text-accent"
                        : "w-16 shrink-0 font-mono text-sm text-zinc-500"
                    }
                  >
                    {item.version}
                  </span>
                  <span
                    className={
                      i === 0
                        ? "text-sm leading-relaxed text-foreground"
                        : "text-sm leading-relaxed text-zinc-400"
                    }
                  >
                    {item.desc}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>

      {/* footer */}
      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-6 py-10 font-mono text-[13px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
          <p>{t.footer.text}</p>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-accent"
          >
            {GITHUB_URL.replace("https://", "")}
          </a>
        </div>
      </footer>
    </div>
  );
}
