import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "../globals.css";
import { isLocale, locales } from "@/lib/i18n";
import { notFound } from "next/navigation";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
    metadataBase: new URL("https://grimoire-apeplatform.vercel.app"),
    title: pt
      ? "Grimoire — busca semântica local para agentes de IA"
      : "Grimoire — local semantic search for AI agents",
    description: pt
      ? "Indexe seu código na sua máquina e entregue ao agente só os trechos que importam. Sem nuvem, sem Docker, sem API key."
      : "Index your codebase on your machine and hand your AI agent only the snippets that matter. No cloud, no Docker, no API key.",
    alternates: {
      canonical: `/${lang}`,
      languages: { en: "/en", "pt-BR": "/pt" },
    },
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
  return (
    <html
      lang={lang}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
