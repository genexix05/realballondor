import Link from "next/link";
import { notFound } from "next/navigation";
import { PositionChart, SplitChart } from "@/components/charts";
import { Board, PlayerLine } from "@/components/ranking";
import { Flag, PlayerPhoto } from "@/components/media";
import { apiGet, type RankingResponse } from "@/lib/api";
import { fmt } from "@/lib/format";
import { isLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, formatLocale, localePath, t } from "@/lib/i18n";

const SEASON = "2025/2026";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw as Locale;
  const dict = await getDictionary(locale);

  const [data, fwd, mid, def, gk, u23] = await Promise.all([
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&limit=10`),
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&position=FWD&limit=6`),
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&position=MID&limit=6`),
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&position=DEF&limit=6`),
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&position=GK&limit=6`),
    apiGet<RankingResponse>(`/api/ranking?season=${SEASON}&under23=true&limit=8`),
  ]);

  const leader = data.items[0];
  const rest = data.items.slice(1, 10);
  const split = data.items.slice(0, 8).map((row) => ({
    name: row.player.split(" ").slice(-1)[0],
    rendimiento: Number((row.individual_score * 0.82).toFixed(1)),
    palmares: Number((row.trophy_score * 0.18).toFixed(1)),
  }));
  const numberLocale = formatLocale(locale);

  return (
    <div>
      <p className="kicker">{t(dict.home.kicker, { season: data.season })}</p>
      <h1 className="display">{dict.home.title}</h1>
      <p className="lede">
        {t(dict.home.lede, { total: data.total.toLocaleString(numberLocale) })}
      </p>

      {leader && (
        <div className="leader-grid" style={{ marginTop: "1.75rem" }}>
          <Link href={localePath(locale, `/players/${leader.player_id}`)} className="leader">
            <PlayerPhoto id={leader.fotmob_player_id} name={leader.player} size={148} />
            <div>
              <div className="leader__place">{dict.home.numberOne}</div>
              <h2>{leader.player}</h2>
              <div className="leader__meta">
                <Flag code={leader.country_code} title={leader.country} />
                {leader.club}
                {leader.age != null ? ` · ${leader.age} ${dict.common.years}` : ""}
              </div>
              <div className="leader__index">
                {fmt(leader.index_value)}
                <small>{dict.common.index}</small>
              </div>
            </div>
          </Link>
          <ol className="board__list">
            {rest.map((row) => (
              <li key={row.player_id}>
                <PlayerLine row={row} locale={locale} yearsLabel={dict.common.years} />
              </li>
            ))}
          </ol>
        </div>
      )}

      <section className="method-box" style={{ marginTop: "2.75rem" }}>
        <h2>{dict.home.howTitle}</h2>
        <p>
          <strong>{dict.home.howStrong}</strong> {dict.home.howLead}
        </p>
        <p className="formula">{dict.home.formula}</p>
        <ul>
          <li>{dict.home.how1}</li>
          <li>{dict.home.how2}</li>
          <li>{dict.home.how3}</li>
          <li>{dict.home.how4}</li>
        </ul>
        <p>
          <Link href={localePath(locale, "/metodo")}>{dict.home.howLink}</Link>
        </p>
      </section>

      <div className="section-gap">
        <div className="boards">
          <Board
            title={dict.positions.FWD}
            href={localePath(locale, "/ranking?pos=FWD")}
            items={fwd.items}
            locale={locale}
            seeList={dict.common.seeList}
            yearsLabel={dict.common.years}
          />
          <Board
            title={dict.positions.MID}
            href={localePath(locale, "/ranking?pos=MID")}
            items={mid.items}
            locale={locale}
            seeList={dict.common.seeList}
            yearsLabel={dict.common.years}
          />
          <Board
            title={dict.positions.DEF}
            href={localePath(locale, "/ranking?pos=DEF")}
            items={def.items}
            locale={locale}
            seeList={dict.common.seeList}
            yearsLabel={dict.common.years}
          />
          <Board
            title={dict.positions.GK}
            href={localePath(locale, "/ranking?pos=GK")}
            items={gk.items}
            locale={locale}
            seeList={dict.common.seeList}
            yearsLabel={dict.common.years}
          />
        </div>
        <Board
          title={dict.positions.U23}
          href={localePath(locale, "/ranking?pos=U23")}
          items={u23.items}
          locale={locale}
          seeList={dict.common.seeList}
          yearsLabel={dict.common.years}
        />
      </div>

      <div className="boards section-gap">
        <div className="panel">
          <h2>{dict.home.splitTitle}</h2>
          <p className="lede" style={{ marginTop: 0, fontSize: "0.85rem" }}>
            {dict.home.splitLede}
          </p>
          <SplitChart
            data={split}
            performanceLabel={dict.charts.performance}
            trophiesLabel={dict.charts.trophies}
          />
        </div>
        <div className="panel">
          <h2>{dict.home.rosterTitle}</h2>
          <PositionChart data={data.by_position ?? []} />
        </div>
      </div>
    </div>
  );
}
