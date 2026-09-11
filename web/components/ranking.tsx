import Link from "next/link";
import { Flag, PlayerPhoto } from "@/components/media";
import type { RankingRow } from "@/lib/api";
import { fmt } from "@/lib/format";
import type { Locale } from "@/lib/i18n/config";
import { localePath } from "@/lib/i18n";

export function PlayerLine({
  row,
  place,
  locale,
  yearsLabel = "años",
}: {
  row: RankingRow;
  place?: number;
  locale: Locale;
  yearsLabel?: string;
}) {
  const n = place ?? row.rank;
  return (
    <Link href={localePath(locale, `/players/${row.player_id}`)} className="player-line">
      <span className="player-line__rank">{n}</span>
      <PlayerPhoto id={row.fotmob_player_id} name={row.player} size={40} />
      <span className="player-line__id">
        <span className="player-line__name">
          <Flag code={row.country_code} title={row.country} />
          {row.player}
        </span>
        <span className="player-line__meta">
          {row.club ?? "—"}
          {row.age != null ? ` · ${row.age} ${yearsLabel}` : ""}
          {place != null ? ` · #${row.rank}` : ""}
        </span>
      </span>
      <span className="player-line__index">{fmt(row.index_value)}</span>
    </Link>
  );
}

export function Board({
  title,
  href,
  items,
  locale,
  seeList,
  yearsLabel,
}: {
  title: string;
  href: string;
  items: RankingRow[];
  locale: Locale;
  seeList: string;
  yearsLabel: string;
}) {
  return (
    <section className="board">
      <header className="board__head">
        <h2>{title}</h2>
        <Link href={href}>{seeList}</Link>
      </header>
      <ol className="board__list">
        {items.map((row, i) => (
          <li key={row.player_id}>
            <PlayerLine row={row} place={i + 1} locale={locale} yearsLabel={yearsLabel} />
          </li>
        ))}
      </ol>
    </section>
  );
}

export function RankingTabs({
  pos,
  locale,
  labels,
}: {
  pos?: string;
  locale: Locale;
  labels: {
    all: string;
    FWD: string;
    MID: string;
    DEF: string;
    GK: string;
    U23: string;
  };
}) {
  const tabs = [
    { id: "", label: labels.all },
    { id: "FWD", label: labels.FWD },
    { id: "MID", label: labels.MID },
    { id: "DEF", label: labels.DEF },
    { id: "GK", label: labels.GK },
    { id: "U23", label: labels.U23 },
  ];
  return (
    <div className="filters">
      {tabs.map((f) => {
        const active = (pos ?? "") === f.id;
        const href = f.id
          ? localePath(locale, `/ranking?pos=${f.id}`)
          : localePath(locale, "/ranking");
        return (
          <Link key={f.id || "all"} href={href} className={active ? "is-active" : ""}>
            {f.label}
          </Link>
        );
      })}
    </div>
  );
}

export function RankingTable({
  rows,
  listed,
  locale,
  headers,
}: {
  rows: RankingRow[];
  listed?: boolean;
  locale: Locale;
  headers: {
    player: string;
    pos: string;
    apps: string;
    goals: string;
    assists: string;
    rating: string;
    index: string;
  };
}) {
  return (
    <div className="sheet">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>{headers.player}</th>
            <th>{headers.pos}</th>
            <th className="num">{headers.apps}</th>
            <th className="num">{headers.goals}</th>
            <th className="num">{headers.assists}</th>
            <th className="num">{headers.rating}</th>
            <th className="num">{headers.index}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.player_id}>
              <td className="rank">{listed ? i + 1 : row.rank}</td>
              <td>
                <Link href={localePath(locale, `/players/${row.player_id}`)} className="who">
                  <PlayerPhoto id={row.fotmob_player_id} name={row.player} size={36} />
                  <span>
                    <span className="who__name">
                      <Flag code={row.country_code} title={row.country} />
                      {row.player}
                    </span>
                    <span className="who__meta">
                      {row.club ?? "—"}
                      {row.age != null ? ` · ${row.age}` : ""}
                      {listed ? ` · #${row.rank}` : ""}
                    </span>
                  </span>
                </Link>
              </td>
              <td>{row.position_group}</td>
              <td className="num">{row.matches}</td>
              <td className="num">{row.goals}</td>
              <td className="num">{row.assists}</td>
              <td className="num">{fmt(row.mean_rating, 2)}</td>
              <td className="num index">{fmt(row.index_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
