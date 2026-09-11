"""FBref player match-log scraper (worldfootballR strategy).

One HTTP page per player×stat_type = all matches of the season.
Default: scrape the full outfield pack and merge into one wide CSV so
subsequent leagues don't start with an incomplete schema.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "cache" / "fbref_player_logs"
OUT_DIR = ROOT / "data" / "raw" / "fbref"

# Full pack for the Ballon d'Or index (outfield). Keepers is optional.
DEFAULT_STAT_TYPES = (
    "summary",
    "passing",
    "passing_types",
    "gca",
    "defense",
    "possession",
    "misc",
)

JOIN_KEYS = ("player_id", "Date", "Comp", "Opponent")
META_COLS = (
    "player",
    "squad_season",
    "season",
    "Day",
    "Round",
    "Venue",
    "Result",
    "Squad",
    "Start",
    "Pos",
    "Min",
    "Match Report",
)


@dataclass
class PlayerRef:
    player_id: str
    name: str
    url: str
    squad: str | None = None
    minutes: float | None = None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            "_".join(str(x) for x in col if "Unnamed" not in str(x)).strip("_")
            for col in df.columns
        ]
    return df


def _parse_matchlogs_table(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="matchlogs_all")
    if table is None:
        raise ValueError("matchlogs_all table not found")
    df = pd.read_html(StringIO(str(table)))[0]
    df = _flatten_columns(df)
    if "Date" in df.columns:
        df = df[df["Date"].notna()]
        df = df[~df["Date"].astype(str).str.contains("Matches|Total|Avg", case=False, na=False)]
    if "Min" in df.columns:
        min_str = df["Min"].astype(str)
        df = df[~min_str.str.contains("did not play|On matchday", case=False, na=False)]
        df["Min"] = pd.to_numeric(df["Min"], errors="coerce")
        df = df[df["Min"].notna()]
    return df.reset_index(drop=True)


def season_label(season_end_year: int) -> str:
    return f"{season_end_year - 1}-{season_end_year}"


def matchlog_url(player_url: str, season_end_year: int, stat_type: str = "summary") -> str:
    m = re.search(r"/players/([a-f0-9]+)/([^/?#]+)", player_url)
    if not m:
        raise ValueError(f"Cannot parse player url: {player_url}")
    pid, slug = m.group(1), m.group(2)
    season = season_label(season_end_year)
    return (
        f"https://fbref.com/en/players/{pid}/matchlogs/{season}/"
        f"{stat_type}/{slug}-Match-Logs"
    )


def _with_browser(fn):
    from seleniumbase import SB

    with SB(uc=True, headless=True) as sb:
        return fn(sb)


def fetch_html(sb, url: str, pause: float = 2.5) -> str:
    sb.open(url)
    time.sleep(pause)
    return sb.get_page_source()


def cache_path(player_id: str, season_end_year: int, stat_type: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{player_id}_{season_end_year}_{stat_type}.html"


def get_or_fetch_html(
    sb,
    player_id: str,
    url: str,
    season_end_year: int,
    stat_type: str,
    pause: float,
    force: bool = False,
) -> str:
    path = cache_path(player_id, season_end_year, stat_type)
    if path.exists() and not force and path.stat().st_size > 10_000:
        return path.read_text(encoding="utf-8", errors="ignore")
    html = fetch_html(sb, url, pause=pause)
    path.write_text(html, encoding="utf-8")
    return html


LA_LIGA_PLAYERS_URL = {
    2026: "https://fbref.com/en/comps/12/2025-2026/stats/players/2025-2026-La-Liga-Stats",
    2025: "https://fbref.com/en/comps/12/2024-2025/stats/players/2024-2025-La-Liga-Stats",
}

BIG5_PLAYERS_URL = {
    2026: "https://fbref.com/en/comps/Big5/2025-2026/stats/players/2025-2026-Big-5-European-Leagues-Stats",
    2025: "https://fbref.com/en/comps/Big5/2024-2025/stats/players/2024-2025-Big-5-European-Leagues-Stats",
}


def discover_players_from_league_stats(
    sb,
    season_end_year: int,
    scope: str = "laliga",
    min_minutes: float = 0,
    pause: float = 2.5,
) -> list[PlayerRef]:
    if scope == "big5":
        url = BIG5_PLAYERS_URL[season_end_year]
    else:
        url = LA_LIGA_PLAYERS_URL[season_end_year]

    cache = CACHE_DIR / f"league_players_{scope}_{season_end_year}.html"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 20_000:
        html = cache.read_text(encoding="utf-8", errors="ignore")
    else:
        html = fetch_html(sb, url, pause=pause)
        cache.write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=re.compile(r"stats_standard"))
    if table is None:
        commented = re.findall(r"<!--\s*(<table.*?</table>)\s*-->", html, flags=re.S)
        for block in commented:
            if "stats_standard" in block or "Player" in block:
                table = BeautifulSoup(block, "lxml").find("table")
                break
    if table is None:
        raise RuntimeError("Could not find players stats table on league page")

    players: list[PlayerRef] = []
    for row in table.select("tbody tr"):
        if row.get("class") and "thead" in row.get("class", []):
            continue
        a = row.select_one('td[data-stat="player"] a')
        if not a or not a.get("href"):
            continue
        href = urljoin("https://fbref.com", a["href"])
        m = re.search(r"/players/([a-f0-9]+)/", href)
        if not m:
            continue
        pid = m.group(1)
        name = a.get_text(strip=True)
        squad_el = row.select_one('td[data-stat="team"] a, td[data-stat="squad"] a')
        squad = squad_el.get_text(strip=True) if squad_el else None
        min_el = row.select_one('td[data-stat="minutes"]')
        minutes = None
        if min_el:
            raw = min_el.get_text(strip=True).replace(",", "")
            try:
                minutes = float(raw) if raw else 0.0
            except ValueError:
                minutes = 0.0
        if minutes is not None and minutes < min_minutes:
            continue
        players.append(PlayerRef(player_id=pid, name=name, url=href, squad=squad, minutes=minutes))

    uniq: dict[str, PlayerRef] = {}
    for p in players:
        prev = uniq.get(p.player_id)
        if prev is None or (p.minutes or 0) > (prev.minutes or 0):
            uniq[p.player_id] = p
    return list(uniq.values())


def _prefix_stat_columns(df: pd.DataFrame, stat_type: str) -> pd.DataFrame:
    """Prefix non-key / non-meta columns so merges don't collide."""
    df = df.copy()
    keep = set(JOIN_KEYS) | set(META_COLS)
    rename = {c: f"{stat_type}__{c}" for c in df.columns if c not in keep}
    return df.rename(columns=rename)


def _load_player_stat_frame(
    sb,
    player: PlayerRef,
    season_end_year: int,
    stat_type: str,
    pause: float,
) -> pd.DataFrame | None:
    url = matchlog_url(player.url, season_end_year, stat_type=stat_type)
    try:
        html = get_or_fetch_html(
            sb, player.player_id, url, season_end_year, stat_type, pause=pause
        )
        df = _parse_matchlogs_table(html)
    except Exception as exc:  # noqa: BLE001
        print(f"  skip {stat_type}: {exc}")
        return None

    df.insert(0, "player_id", player.player_id)
    df.insert(1, "player", player.name)
    df.insert(2, "squad_season", player.squad)
    df.insert(3, "season", season_label(season_end_year))
    return df


def _merge_stat_frames(frames_by_type: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "summary" in frames_by_type:
        base_type = "summary"
    else:
        base_type = next(iter(frames_by_type))

    out = frames_by_type[base_type].copy()
    # summary keeps original column names; others get prefixed
    if base_type != "summary":
        out = _prefix_stat_columns(out, base_type)

    for stat_type, frame in frames_by_type.items():
        if stat_type == base_type:
            continue
        right = _prefix_stat_columns(frame, stat_type)
        # Drop meta duplicates from right (keep base meta)
        drop_cols = [c for c in META_COLS if c in right.columns]
        right = right.drop(columns=drop_cols, errors="ignore")
        keys = [k for k in JOIN_KEYS if k in out.columns and k in right.columns]
        out = out.merge(right, on=keys, how="outer")
    return out


def scrape_player_match_logs(
    players: Iterable[PlayerRef],
    season_end_year: int,
    stat_types: tuple[str, ...] | list[str] = DEFAULT_STAT_TYPES,
    pause: float = 2.5,
    limit: int | None = None,
) -> pd.DataFrame:
    """Scrape all requested stat tabs per player and merge to one wide table."""
    players = list(players)
    if limit is not None:
        players = players[:limit]
    stat_types = tuple(stat_types)

    pack_id = "+".join(stat_types)
    progress_path = CACHE_DIR / f"progress_{season_end_year}_{pack_id}.json"
    done = set()
    if progress_path.exists():
        done = set(json.loads(progress_path.read_text()).get("done", []))

    frames: list[pd.DataFrame] = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    partial_csv = OUT_DIR / f"player_match_logs_{season_end_year}_full.partial.csv"

    def player_complete(player_id: str) -> bool:
        return all(
            cache_path(player_id, season_end_year, st).exists()
            and cache_path(player_id, season_end_year, st).stat().st_size > 10_000
            for st in stat_types
        )

    def run(sb):
        nonlocal done
        total = len(players)
        for i, p in enumerate(players, start=1):
            print(f"[{i}/{total}] {p.name} ({p.player_id}) tabs={list(stat_types)}")
            by_type: dict[str, pd.DataFrame] = {}
            for st in stat_types:
                cached = cache_path(p.player_id, season_end_year, st)
                # Reuse summary HTML already downloaded by the running summary job
                frame = _load_player_stat_frame(sb, p, season_end_year, st, pause=pause)
                if frame is not None and not frame.empty:
                    by_type[st] = frame
                elif cached.exists():
                    print(f"  {st}: cached but unparsable")

            if not by_type:
                print("  FAIL: no tabs parsed")
                continue

            merged = _merge_stat_frames(by_type)
            frames.append(merged)

            if player_complete(p.player_id) or set(by_type) >= set(stat_types):
                done.add(p.player_id)
            progress_path.write_text(json.dumps({"done": sorted(done), "stat_types": list(stat_types)}))
            pd.concat(frames, ignore_index=True).to_csv(partial_csv, index=False)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    return _with_browser(run)


def build_dataset(
    season_end_year: int = 2026,
    scope: str = "laliga",
    min_minutes: float = 450,
    pause: float = 2.5,
    limit: int | None = None,
    stat_types: tuple[str, ...] | list[str] | None = None,
) -> Path:
    """Build the FBref player×match dataset (full pack by default)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if stat_types is None:
        stat_types = DEFAULT_STAT_TYPES

    def discover(sb):
        players = discover_players_from_league_stats(
            sb,
            season_end_year=season_end_year,
            scope=scope,
            min_minutes=min_minutes,
            pause=pause,
        )
        print(f"Players after filter (min_minutes>={min_minutes}): {len(players)}")
        print(f"Stat types: {list(stat_types)}")
        return players

    players = _with_browser(discover)
    df = scrape_player_match_logs(
        players,
        season_end_year=season_end_year,
        stat_types=stat_types,
        pause=pause,
        limit=limit,
    )
    tag = "full" if list(stat_types) == list(DEFAULT_STAT_TYPES) else "+".join(stat_types)
    out = OUT_DIR / f"player_match_logs_{scope}_{season_end_year}_{tag}.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows × {len(df.columns)} cols → {out}")
    return out
