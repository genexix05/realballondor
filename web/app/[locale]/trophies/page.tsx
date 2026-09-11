import { notFound } from "next/navigation";
import { apiGet } from "@/lib/api";
import { isLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, t } from "@/lib/i18n";

type Trophy = {
  code: string;
  name: string;
  winner: string | null;
  runner_up: string | null;
  decided_by: string | null;
};

export default async function TrophiesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw as Locale;
  const dict = await getDictionary(locale);
  const data = await apiGet<{ season: string; items: Trophy[] }>(
    "/api/trophies?season=2025/2026",
  );

  return (
    <div>
      <p className="kicker">{t(dict.trophies.kicker, { season: data.season })}</p>
      <h1 className="display">{dict.trophies.title}</h1>
      <p className="lede">{dict.trophies.lede}</p>
      <div className="trophy-grid" style={{ marginTop: "2rem" }}>
        {data.items.map((item) => (
          <article key={item.code} className="trophy-card">
            <div className="comp">{item.name}</div>
            <div className="winner">{item.winner}</div>
            <div className="runner">
              {dict.common.runnerUp} · {item.runner_up}
            </div>
            <div className="runner" style={{ marginTop: "0.45rem", fontSize: "0.75rem" }}>
              {item.decided_by}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
