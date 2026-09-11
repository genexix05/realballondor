import { notFound } from "next/navigation";
import { apiGet } from "@/lib/api";
import { isLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, t } from "@/lib/i18n";

type Model = {
  formula: string;
  index: { individual_weight: number; trophy_weight: number; min_matches: number };
  rating: { weight: number; baseline: number; scale: number };
  position_groups: Record<string, Record<string, number>>;
  penalties: Record<string, number>;
  competitions: { code: string; name: string; weight: number }[];
  stages: Record<string, number>;
  trophies: Record<string, { winner: number; runner_up: number }>;
  labels: Record<string, string>;
  opponent: { floor: number; range: number };
};

export default async function MethodPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  const locale = raw as Locale;
  const dict = await getDictionary(locale);
  const model = await apiGet<Model>("/api/model");
  const trophyNames = Object.fromEntries(model.competitions.map((c) => [c.code, c.name]));
  const wcWeight = model.competitions.find((c) => c.code === "INT-World Cup")?.weight ?? 1.5;
  const groupWeight = model.stages.group_stage;
  const finalWeight = model.stages.final;
  const groupLabels: Record<string, string> = {
    FWD: dict.positions.FWD,
    MID: dict.positions.MID_long,
    DEF: dict.positions.DEF,
    GK: dict.positions.GK,
  };

  return (
    <article className="method">
      <p className="kicker">{dict.method.kicker}</p>
      <h1 className="display">{dict.method.title}</h1>
      <p className="lede">{dict.method.lede}</p>

      <h2>{dict.method.formulaTitle}</h2>
      <p>{t(dict.method.formulaIntro, { min: model.index.min_matches })}</p>
      <p className="formula">
        {t(dict.method.formula, {
          ind: Math.round(model.index.individual_weight * 100),
          trophy: Math.round(model.index.trophy_weight * 100),
        })}
      </p>
      <p>{dict.method.formulaNote}</p>
      <p>{dict.method.volumeNote}</p>

      <h2>{dict.method.matchTitle}</h2>
      <p>{dict.method.matchIntro}</p>
      <p className="formula">{model.formula}</p>
      <p>
        <strong>{dict.method.performanceLabel}.</strong>{" "}
        {t(dict.method.performance, {
          pct: Math.round(model.rating.weight * 100),
          baseline: model.rating.baseline.toFixed(1),
          sat: (model.rating.baseline + model.rating.scale).toFixed(1),
        })}
      </p>
      <p>
        <strong>{dict.method.opponentLabel}.</strong>{" "}
        {t(dict.method.opponent, {
          floor: model.opponent.floor.toFixed(2),
          range: model.opponent.range.toFixed(2),
        })}
      </p>
      <p>
        <strong>{dict.method.reliabilityLabel}.</strong> {dict.method.reliability}
      </p>

      <h2>{dict.method.stageTitle}</h2>
      <p>
        {t(dict.method.stageIntro, {
          wc: wcWeight.toFixed(2),
          group: groupWeight.toFixed(2),
          wcGroup: (wcWeight * groupWeight).toFixed(2),
          final: finalWeight.toFixed(2),
          wcFinal: (wcWeight * finalWeight).toFixed(2),
        })}
      </p>
      <div className="boards">
        <table>
          <thead>
            <tr>
              <th>{dict.method.thComp}</th>
              <th className="num">{dict.method.thWeight}</th>
            </tr>
          </thead>
          <tbody>
            {model.competitions.map((c) => (
              <tr key={c.code}>
                <td>{c.name}</td>
                <td className="num">{c.weight.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table>
          <thead>
            <tr>
              <th>{dict.method.thStage}</th>
              <th className="num">{dict.method.thWeight}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(model.stages).map(([key, weight]) => (
              <tr key={key}>
                <td>
                  {dict.method.stages[key as keyof typeof dict.method.stages] ?? key}
                </td>
                <td className="num">{weight.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>{dict.method.statsTitle}</h2>
      <p>{dict.method.statsIntro}</p>
      <div className="boards">
        {Object.entries(model.position_groups).map(([group, stats]) => (
          <table key={group}>
            <thead>
              <tr>
                <th>{groupLabels[group] ?? group}</th>
                <th className="num">{dict.method.thWeight}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stats).map(([stat, weight]) => (
                <tr key={stat}>
                  <td>{model.labels[stat] ?? stat}</td>
                  <td className="num">{weight.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>{dict.method.penalties}</th>
            <th className="num">{dict.method.thWeight}</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(model.penalties).map(([stat, weight]) => (
            <tr key={stat}>
              <td>{model.labels[stat] ?? stat}</td>
              <td className="num">{weight.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>{dict.method.gkNote}</p>

      <h2>{dict.method.trophiesTitle}</h2>
      <p>{dict.method.trophiesIntro}</p>
      <table>
        <thead>
          <tr>
            <th>{dict.method.thTitle}</th>
            <th className="num">{dict.method.thChampion}</th>
            <th className="num">{dict.method.thRunner}</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(model.trophies).map(([code, pts]) => (
            <tr key={code}>
              <td>{trophyNames[code] ?? code}</td>
              <td className="num">{pts.winner.toFixed(2)}</td>
              <td className="num">{pts.runner_up.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>{dict.method.trophiesNote}</p>
    </article>
  );
}
