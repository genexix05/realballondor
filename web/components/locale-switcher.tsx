"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import type { Locale } from "@/lib/i18n/config";
import { locales } from "@/lib/i18n/config";
import { stripLocale } from "@/lib/i18n";

type LangLabels = { label: string } & Record<Locale, string>;

function SwitcherInner({
  locale,
  labels,
}: {
  locale: Locale;
  labels: LangLabels;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const rest = stripLocale(pathname);
  const qs = searchParams.toString();
  const suffix = qs ? `?${qs}` : "";

  return (
    <div className="lang-switch" aria-label={labels.label}>
      {locales.map((code) => {
        const href = `/${code}${rest === "/" ? "" : rest}${suffix}`;
        return (
          <Link
            key={code}
            href={href}
            hrefLang={code}
            className={code === locale ? "is-active" : ""}
            prefetch={false}
          >
            {labels[code]}
          </Link>
        );
      })}
    </div>
  );
}

export function LocaleSwitcher(props: {
  locale: Locale;
  labels: LangLabels;
}) {
  return (
    <Suspense fallback={<div className="lang-switch" aria-hidden />}>
      <SwitcherInner {...props} />
    </Suspense>
  );
}
