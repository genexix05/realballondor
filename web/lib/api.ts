export type RankingRow = {
  rank: number;
  player_id: number;
  player: string;
  club: string | null;
  position_group: string | null;
  matches: number;
  minutes: number;
  goals: number;
  assists: number;
  mean_rating: number | null;
  individual_score: number;
  trophies: number;
  trophy_score: number;
  index_value: number;
  country: string | null;
  country_code: string | null;
  age: number | null;
  fotmob_player_id: string | null;
};

export type RankingResponse = {
  season: string;
  total: number;
  by_position: { position_group: string; n: number; mean_index: number }[];
  items: RankingRow[];
};

export type TrophyCredit = {
  code: string;
  name: string;
  role: string;
  share: number;
  points: number;
};

export type ModelStat = {
  key: string;
  label: string;
  weight: number;
  total: number;
  per90: number;
};

export type ModelStats = {
  position_group: string;
  matches: number;
  minutes: number;
  started: number;
  mean_rating: number | null;
  rating_weight: number;
  used: ModelStat[];
  penalties: ModelStat[];
};

export type PlayerDetail = {
  player: {
    player_id: number;
    name: string;
    country: string | null;
    country_code: string | null;
    club: string | null;
    position_group: string | null;
    rank: number | null;
    matches: number | null;
    minutes: number | null;
    goals: number | null;
    assists: number | null;
    mean_rating: number | null;
    individual_score: number | null;
    trophies: number | null;
    trophy_score: number | null;
    index_value: number | null;
    consistency: number | null;
    season: string | null;
    age: number | null;
    fotmob_player_id: string | null;
    season_score: number | null;
    mean_match_score: number | null;
  };
  trophies: TrophyCredit[];
  model_stats: ModelStats;
};

export type MatchRow = {
  match_id: number;
  kickoff_utc: string | null;
  date: string;
  stage: string | null;
  home_score: number | null;
  away_score: number | null;
  competition_code: string;
  competition_name: string;
  home_team: string;
  away_team: string;
  minutes: number | null;
  rating: number | null;
  goals: number | null;
  assists: number | null;
  opponent: string | null;
  performance: number | null;
  opponent_strength: number | null;
  opponent_multiplier: number | null;
  competition_weight: number | null;
  stage_weight: number | null;
  match_score: number | null;
};

const API = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}
