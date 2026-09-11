"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Locale } from "@/lib/i18n/config";
import { localePath, stripLocale } from "@/lib/i18n";

const LINKS = [
  { path: "/", key: "index" as const },
  { path: "/ranking", key: "ranking" as const },
  { path: "/trophies", key: "trophies" as const },
  { path: "/metodo", key: "method" as const },
];

export function Nav({
  locale,
  labels,
}: {
  locale: Locale;
  labels: Record<(typeof LINKS)[number]["key"], string>;
}) {
  const path = stripLocale(usePathname());
  return (
    <nav className="site-nav">
      {LINKS.map((link) => {
        const active = link.path === "/" ? path === "/" : path.startsWith(link.path);
        return (
          <Link
            key={link.path}
            href={localePath(locale, link.path)}
            className={active ? "is-active" : ""}
          >
            {labels[link.key]}
          </Link>
        );
      })}
    </nav>
  );
}
