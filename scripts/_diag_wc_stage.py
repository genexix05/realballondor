import pandas as pd

matches = pd.read_parquet("data/raw/fotmob/matches_full_2025-2026.parquet")
wc = matches[matches.competition_code == "INT-World Cup"]
print("=== WC stages ===")
print(wc.stage.value_counts(dropna=False).to_string())
print("\ncolumns", [c for c in matches.columns if "round" in c.lower() or "stage" in c.lower() or "name" in c.lower()][:30])
print("\nsample WC rows")
cols = [c for c in ["stage", "round", "round_name", "roundName", "home", "away", "home_team", "away_team", "date"] if c in wc.columns]
print("available", list(wc.columns))
print(wc.head(8).to_string(index=False))

print("\n=== stages by competition (group-like) ===")
for code, g in matches.groupby("competition_code"):
    stages = g.stage.value_counts()
    if any(s in stages.index for s in ["group_stage", "league_phase"]):
        print(code, dict(stages))
