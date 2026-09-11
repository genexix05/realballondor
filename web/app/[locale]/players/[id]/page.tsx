import Link from "next/link";
import { notFound } from "next/navigation";
import { MatchScoreChart, TrophyBars } from "@/components/charts";
import { Flag, PlayerPhoto } from "@/components/media";
import { apiGet, type MatchRow, type PlayerDetail } from "@/lib/api";
import { fmt } from "@/lib/format";
import { isLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, formatLocale, localePath, t } from "@/lib/i18n";

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale: raw, id } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw as Locale;
  const dict = await getDictionary(locale);
  const detail = await apiGet<PlayerDetail>(`/api/players/${id}?season=2025/2026`);
  const matches = await apiGet<{ items: MatchRow[] }>(
    `/api/players/${id}/matches?season=2025/2026&limit=80`,
  );
  const p = detail.player;
  const chronological = [...matches.items].reverse();
  const series = chronological.map((m) => ({
    label: `${m.competition_name} · ${m.opponent ?? ""}`,
    score: Number((m.match_score ?? 0).toFixed(2)),
    rating: m.rating,
  }));
  const trophyChart = detail.trophies.map((item) => ({
    name: item.name.replace("UEFA ", "").replace("FIFA ", ""),
    points: Number(item.points.toFixed(2)),
  }));
  const consistency =
    p.consistency != null ? `${fmt(p.consistency * 100, 0)}%` : dict.common.dash;
  const numberLocale = formatLocale(locale);

  return (
    <div>
      <Link href={localePath(locale, "/ranking")} className="kicker">
        {dict.player.back}
      </Link>

      <div className="hero-player" style={{ marginTop: "1.4rem" }}>
        <PlayerPhoto id={p.fotmob_player_id} name={p.name} size={180} />
        <div>
          <p className="kicker">
            {p.rank ? `#${p.rank}` : dict.player.unranked} · {p.position_group} · {p.club}
          </p>
          <h1 className="display">{p.name}</h1>
          <div className="leader__meta" style={{ marginTop: "0.45rem" }}>
            <Flag code={p.country_code} title={p.country} />
            {p.country}
            {p.age != null ? ` · ${p.age} ${dict.common.years}` : ""}
          </div>
        </div>
        <div className="leader__index">
          {fmt(p.index_value)}
          <small>{dict.common.index}</small>
        </div>
      </div>

      <dl className="stat-grid" style={{ marginTop: "2rem" }}>
        {[
          [dict.player.individual, fmt(p.individual_score)],
          [dict.player.trophies, fmt(p.trophy_score)],
          [dict.player.seasonScore, fmt(p.season_score, 2)],
          [dict.player.meanMatch, fmt(p.mean_match_score, 2)],
          [dict.player.meanRating, fmt(p.mean_rating, 2)],
          [dict.player.consistency, consistency],
          [dict.player.matches, String(p.matches ?? dict.common.dash)],
          [
            dict.player.minutes,
            p.minutes ? Math.round(p.minutes).toLocaleString(numberLocale) : dict.common.dash,
          ],
          [dict.player.started, String(detail.model_stats.started)],
          [dict.player.goals, String(p.goals ?? dict.common.dash)],
          [dict.player.assists, String(p.assists ?? dict.common.dash)],
        ].map(([label, value]) => (
          <div className="stat" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      {detail.model_stats.used.length > 0 && (
        <section className="section-gap">
          <div className="board__head">
            <h2>{t(dict.player.modelStats, { position: p.position_group ?? "—" })}</h2>
          </div>
          <p className="lede" style={{ marginTop: 0 }}>
            {t(dict.player.modelLede, {
              pct: Math.round(detail.model_stats.rating_weight * 100),
            })}
          </p>
          <div className="sheet">
            <table>
              <thead>
                <tr>
                  <th>{dict.player.thStat}</th>
                  <th className="num">{dict.player.thWeight}</th>
                  <th className="num">{dict.player.thTotal}</th>
                  <th className="num">{dict.player.thPer90}</th>
                </tr>
              </thead>
              <tbody>
                {detail.model_stats.used.map((s) => (
                  <tr key={s.key}>
                    <td>{s.label}</td>
                    <td className="num">{s.weight.toFixed(2)}</td>
                    <td className="num">{fmt(s.total, s.total >= 20 ? 0 : 2)}</td>
                    <td className="num">{fmt(s.per90, 2)}</td>
                  </tr>
                ))}
                {detail.model_stats.penalties.map((s) => (
                  <tr key={s.key}>
                    <td>{s.label}</td>
                    <td className="num">{s.weight.toFixed(2)}</td>
                    <td className="num">{fmt(s.total, 0)}</td>
                    <td className="num">{fmt(s.per90, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="boards section-gap">
        <div className="panel">
          <h2>{dict.player.matchScore}</h2>
          <p className="lede" style={{ marginTop: 0, fontSize: "0.85rem" }}>
            {dict.player.matchScoreLede}
          </p>
          {series.length > 1 ? (
            <MatchScoreChart data={series} />
          ) : (
            <p className="lede">{dict.player.notEnoughMatches}</p>
          )}
        </div>
        <div className="panel">
          <h2>{dict.player.trophies}</h2>
          {trophyChart.length > 0 ? (
            <TrophyBars data={trophyChart} />
          ) : (
            <p className="lede">{dict.player.noTrophies}</p>
          )}
        </div>
      </div>

      {detail.trophies.length > 0 && (
        <ul className="trophy-list" style={{ marginTop: "1.5rem" }}>
          {detail.trophies.map((item) => (
            <li key={`${item.code}-${item.role}`}>
              <span>
                {item.name}
                <span style={{ color: "var(--paper-dim)" }}>
                  {" "}
                  · {item.role === "winner" ? dict.common.champion : dict.common.runnerUp} ·{" "}
                  {Math.round(item.share * 100)}
                  {dict.player.shareMin}
                </span>
              </span>
              <span
                className="index"
                style={{ color: "var(--gold)", fontVariantNumeric: "tabular-nums" }}
              >
                {fmt(item.points, 2)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <section className="section-gap">
        <div className="board__head">
          <h2>{t(dict.player.matchesHeading, { n: matches.items.length })}</h2>
        </div>
        <div className="sheet">
          <table>
            <thead>
              <tr>
                <th>{dict.player.thDate}</th>
                <th>{dict.player.thComp}</th>
                <th>{dict.player.thMatch}</th>
                <th className="num">{dict.player.thMin}</th>
                <th className="num">{dict.player.thGA}</th>
                <th className="num">{dict.player.thRating}</th>
                <th className="num">{dict.player.thOpp}</th>
                <th className="num">{dict.player.thScore}</th>
              </tr>
            </thead>
            <tbody>
              {matches.items.map((m) => (
                <tr key={m.match_id}>
                  <td className="rank" style={{ width: "auto" }}>
                    {m.date?.slice(0, 10)}
                  </td>
                  <td>{m.competition_name}</td>
                  <td>
                    {m.home_team} {m.home_score}-{m.away_score} {m.away_team}
                    <div className="who__meta">{m.stage}</div>
                  </td>
                  <td className="num">{fmt(m.minutes, 0)}</td>
                  <td className="num">
                    {m.goals ?? 0}/{m.assists ?? 0}
                  </td>
                  <td className="num">{fmt(m.rating, 2)}</td>
                  <td className="num">{fmt(m.opponent_strength, 2)}</td>
                  <td className="num index">{fmt(m.match_score, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
