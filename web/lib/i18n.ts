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
