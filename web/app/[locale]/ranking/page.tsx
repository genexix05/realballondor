import { notFound } from "next/navigation";
import { RankingTable, RankingTabs } from "@/components/ranking";
import { apiGet, type RankingResponse } from "@/lib/api";
import { isLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, formatLocale, t } from "@/lib/i18n";

const SEASON = "2025/2026";

export default async function RankingPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ pos?: string }>;
}) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw as Locale;
  const dict = await getDictionary(locale);
  const { pos } = await searchParams;
  const key = (pos ?? "").toUpperCase();
  const under23 = key === "U23";
  const position = !under23 && key ? key : "";
  const query = under23
    ? "&under23=true"
    : position
      ? `&position=${position}`
      : "";
  const data = await apiGet<RankingResponse>(
    `/api/ranking?season=${SEASON}&limit=100${query}`,
  );
  const listed = Boolean(position || under23);
  const titles = dict.ranking.titles as Record<string, string>;
  const title = titles[key] ?? titles.fallback;
  const numberLocale = formatLocale(locale);

  return (
    <div>
      <p className="kicker">{t(dict.ranking.kicker, { season: data.season })}</p>
      <h1 className="display">{title}</h1>
      <p className="lede">
        {t(dict.ranking.lede, { total: data.total.toLocaleString(numberLocale) })}
      </p>
      <RankingTabs pos={key} locale={locale} labels={dict.ranking.tabs} />
      <section className="section-gap">
        <RankingTable
          rows={data.items}
          listed={listed}
          locale={locale}
          headers={dict.ranking.th}
        />
      </section>
    </div>
  );
}
