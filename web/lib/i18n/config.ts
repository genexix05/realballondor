export const locales = ["es", "en", "pt", "de", "fr"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

export const localeTags: Record<Locale, string> = {
  es: "es",
  en: "en",
  pt: "pt",
  de: "de",
  fr: "fr",
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}
