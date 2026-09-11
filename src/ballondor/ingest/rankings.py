"""Official opponent-strength rankings: UEFA club coefficients and FIFA world ranking.

Both are read *as of* the moment a match kicked off, never after it, so the
scoring engine cannot see information that did not exist at the time.

**UEFA club coefficients** are a rolling five-year window published once per
season. The coefficient in force during 2025/26 is the one computed at the end
of 2024/25, so ``uefa_club_coefficients("2025/2026")`` reads the 2025 table
(window 2020/21..2024/25). Reading the 2026 table would leak the season's own
European results back into the strength of the teams that produced them.

**FIFA rankings** are published several times a year, each with a publication
date, so a match resolves to the latest edition published on or before kickoff.
This matters: before the 2026 World Cup, France led on 1877 points and Spain
were second; Spain then won the tournament and went top. Rating the final with
the post-tournament ranking would score the result using its own outcome.

FIFA's own API only serves editions up to September 2025 — the newer ids return
an empty payload — so the rankings come from Transfermarkt, which mirrors every
edition back to 1992. Spot-checked against FIFA for 2025-09-18: Spain 1875 vs
FIFA's 1875.37, i.e. the same figures rounded to whole points.
"""

from __future__ import annotations

import re
import time
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "cache" / "rankings"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

KASSIESA_URL = "https://kassiesa.net/uefa/data/method5/trank{year}.html"
TRANSFERMARKT_URL = "https://www.transfermarkt.com/statistik/weltrangliste"
FIFA_PAGE_SIZE = 25


def _cached_get(url: str, cache_name: str, params: dict | None = None,
                force: bool = False, delay: float = 0.8) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name
    if path.exists() and not force and path.stat().st_size > 1000:
        return path.read_text(encoding="utf-8", errors="ignore")
    resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    text = resp.text
    path.write_text(text, encoding="utf-8")
    time.sleep(delay)
    return text


# --------------------------------------------------------------------- #
# UEFA club coefficients
# --------------------------------------------------------------------- #


def uefa_club_coefficients(season: str, force: bool = False) -> pd.DataFrame:
    """Club coefficients in force *during* ``season`` (e.g. ``"2025/2026"``)."""
    window_year = int(season.split("/")[0])
    html = _cached_get(
        KASSIESA_URL.format(year=window_year), f"uefa_trank{window_year}.html", force=force
    )
    table = max(pd.read_html(StringIO(html)), key=len)
    season_cols = [c for c in table.columns if re.fullmatch(r"\d\d/\d\d", str(c))]

    named = table.rename(
        columns={
            table.columns[2]: "club",
            table.columns[3]: "country",
            "Total Points": "coefficient",
            "Country Part": "country_coefficient",
        }
    )
    # The table interleaves per-country subtotal rows, which have no country
    # code. The printed rank column is sparse, so rank is derived instead.
    clubs = named[named["country"].notna()].copy()
    clubs["coefficient"] = pd.to_numeric(clubs["coefficient"], errors="coerce").fillna(0.0)
    clubs = clubs.sort_values("coefficient", ascending=False).reset_index(drop=True)
    clubs["rank"] = clubs["coefficient"].rank(ascending=False, method="min").astype(int)
    clubs["season"] = season
    clubs["window"] = f"{season_cols[0]}..{season_cols[-1]}" if season_cols else None
    clubs["source"] = "UEFA"
    return clubs[
        ["season", "source", "rank", "club", "country", "coefficient",
         "country_coefficient", "window"]
    ]


# --------------------------------------------------------------------- #
# FIFA world ranking
# --------------------------------------------------------------------- #


def fifa_ranking_dates(force: bool = False) -> list[date]:
    """Every published FIFA ranking date, oldest first."""
    html = _cached_get(TRANSFERMARKT_URL, "tm_fifa_index.html", force=force)
    found = re.findall(r'<option[^>]*value="(\d{4}-\d{2}-\d{2})"', html)
    return sorted({date.fromisoformat(d) for d in found})


def fifa_ranking(when: date, force: bool = False) -> pd.DataFrame:
    """One FIFA ranking edition: every nation with its rank and points."""
    frames = []
    for page in range(1, 12):
        html = _cached_get(
            TRANSFERMARKT_URL,
            f"tm_fifa_{when}_p{page}.html",
            params={"datum": when.isoformat(), "page": page},
            force=force,
        )
        table = max(pd.read_html(StringIO(html)), key=len)
        table.columns = [str(c).strip() for c in table.columns]
        frames.append(table)
        if len(table) < FIFA_PAGE_SIZE:
            break

    out = pd.concat(frames, ignore_index=True).rename(
        columns={"#": "rank", "Nation": "team", "Points": "points",
                 "Confederation": "confederation"}
    )
    out = out.drop_duplicates("rank")[["rank", "team", "confederation", "points"]]
    out["ranking_date"] = when
    out["source"] = "FIFA"
    return out.reset_index(drop=True)


def fifa_rankings_covering(start: date, end: date, force: bool = False) -> pd.DataFrame:
    """Every edition needed to resolve any kickoff in ``[start, end)``.

    Includes the last edition published before ``start`` so matches early in the
    window still resolve to the ranking that was actually in force.
    """
    published = fifa_ranking_dates(force)
    needed = [d for d in published if start <= d < end]
    earlier = [d for d in published if d < start]
    if earlier:
        needed.insert(0, earlier[-1])
    frames = [fifa_ranking(d, force) for d in needed]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def as_of(rankings: pd.DataFrame, team: str, when: date) -> pd.Series | None:
    """Latest ranking row for ``team`` published on or before ``when``."""
    rows = rankings[(rankings["team"] == team) & (rankings["ranking_date"] <= when)]
    if rows.empty:
        return None
    return rows.sort_values("ranking_date").iloc[-1]
