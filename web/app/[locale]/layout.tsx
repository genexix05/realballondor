import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { Nav } from "@/components/nav";
import { isLocale, locales, type Locale } from "@/lib/i18n/config";
import { getDictionary, localePath } from "@/lib/i18n";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale: raw } = await params;
  const locale = (isLocale(raw) ? raw : "es") as Locale;
  const dict = await getDictionary(locale);
  return {
    title: dict.meta.title,
    description: dict.meta.description,
    alternates: {
      languages: {
        es: "/es",
        en: "/en",
        pt: "/pt",
        de: "/de",
        fr: "/fr",
        "x-default": "/es",
      },
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw;
  const dict = await getDictionary(locale);

  return (
    <>
      <header className="site-header">
        <div className="site-header__inner">
          <Link href={localePath(locale)} className="masthead">
            <em>{dict.brand.index}</em>
            {dict.brand.name}
            <span>{dict.brand.season}</span>
          </Link>
          <div className="site-header__tools">
            <Nav locale={locale} labels={dict.nav} />
            <LocaleSwitcher locale={locale} labels={dict.lang} />
          </div>
        </div>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-foot">{dict.footer}</footer>
    </>
  );
}
