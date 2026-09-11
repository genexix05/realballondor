import pandas as pd

idx = pd.read_parquet("data/processed/ballondor_index_2025-2026.parquet")
scored = pd.read_parquet("data/processed/match_scores_2025-2026.parquet")

names = ["Dominik Szoboszlai", "Arda Güler", "Fermín López"]
cols = [
    "rank", "player", "matches", "goals", "assists", "mean_rating",
    "mean_match_score", "season_score", "individual_score",
    "trophy_score", "index",
]
print("=== INDICE ===")
print(idx[idx.player.isin(names)][cols].round(3).to_string(index=False))

print("\n=== WC por jugador (todos los INT-World Cup) ===")
wc = scored[scored.competition_code == "INT-World Cup"]
for name in names + ["Lamine Yamal", "Harry Kane", "Jude Bellingham"]:
    s = scored[scored.player == name]
    w = s[s.competition_code == "INT-World Cup"]
    groups = w[w.stage == "group_stage"]
    ko = w[w.stage != "group_stage"]
    print(
        f"{name:20} n={len(w):2d} sum={w.match_score.sum():5.2f}  "
        f"grupos n={len(groups)} sum={groups.match_score.sum():5.2f}  "
        f"KO n={len(ko)} sum={ko.match_score.sum():5.2f}  "
        f"stage_w grupos={groups.stage_weight.mean() if len(groups) else 0:.2f}"
    )

print("\n=== Arda desglose WC ===")
arda = scored[scored.player == "Arda Güler"]
print(arda[arda.competition_code == "INT-World Cup"][
    ["stage", "minutes", "goals", "assists", "rating", "competition_weight", "stage_weight", "match_score"]
].round(3).to_string(index=False))

print("\n=== MID stats_score medio ===")
for name in names:
    s = scored[scored.player == name]
    print(f"{name:20} stats={s.stats_score.mean():.3f} perf={s.performance.mean():.3f} ms={s.match_score.mean():.3f} sum={s.match_score.sum():.2f}")
