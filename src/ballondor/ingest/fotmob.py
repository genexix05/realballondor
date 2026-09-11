"""FotMob ingestion: one unauthenticated request per match, all competitions.

FotMob is a Next.js app. Every page has a JSON sibling at
``/_next/data/{buildId}/{locale}/{route}.json`` that needs no auth and no
signed header (unlike ``apigw.fotmob.com``, which requires the obfuscated
``x-mas`` token). One match request returns lineups, per-player stats with
ratings, shotmaps and match context.

The build id rotates on every FotMob deploy; a 404 means a deploy landed
mid-run, so the client refreshes it and retries once.
"""

from __future__ import annotations

import gzip
import json
import random
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "cache" / "fotmob"

BASE = "https://www.fotmob.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class League:
    """A FotMob competition, mapped onto our own competition codes."""

    fotmob_id: int
    slug: str
    code: str          # matches config/competitions.yml
    kind: str          # club | national


LEAGUES: dict[str, League] = {
    "laliga": League(87, "laliga", "ESP-La Liga", "club"),
    "premier-league": League(47, "premier-league", "ENG-Premier League", "club"),
    "bundesliga": League(54, "bundesliga", "GER-Bundesliga", "club"),
    "serie-a": League(55, "serie-a", "ITA-Serie A", "club"),
    "ligue-1": League(53, "ligue-1", "FRA-Ligue 1", "club"),
    "champions-league": League(42, "champions-league", "UEFA-Champions League", "club"),
    "europa-league": League(73, "europa-league", "UEFA-Europa League", "club"),
    "conference-league": League(10216, "conference-league", "UEFA-Conference League", "club"),
    # National cups
    "copa-del-rey": League(138, "copa-del-rey", "ESP-Copa del Rey", "club"),
    "fa-cup": League(132, "fa-cup", "ENG-FA Cup", "club"),
    "efl-cup": League(133, "efl-cup", "ENG-EFL Cup", "club"),
    "dfb-pokal": League(209, "dfb-pokal", "GER-DFB-Pokal", "club"),
    "coppa-italia": League(141, "coppa-italia", "ITA-Coppa Italia", "club"),
    "coupe-de-france": League(134, "coupe-de-france", "FRA-Coupe de France", "club"),
    # Super cups
    "supercopa": League(139, "supercopa-de-espana", "ESP-Supercopa", "club"),
    "community-shield": League(247, "community-shield", "ENG-Community Shield", "club"),
    "dfl-supercup": League(8924, "super-cup", "GER-DFL-Supercup", "club"),
    "supercoppa-italiana": League(11015, "supercoppa", "ITA-Supercoppa", "club"),
    "trophee-des-champions": League(207, "trophee-des-champions", "FRA-Trophee des Champions", "club"),
    "uefa-super-cup": League(74, "super-cup", "UEFA-Super Cup", "club"),
    # Intercontinental
    "intercontinental-cup": League(10703, "intercontinental-cup", "FIFA-Intercontinental Cup", "club"),
    "club-world-cup": League(78, "club-world-cup", "FIFA-Club World Cup", "club"),
    # National teams
    "world-cup": League(77, "world-cup", "INT-World Cup", "national"),
    "euro": League(50, "euro", "INT-Euro", "national"),
    "copa-america": League(44, "copa-america", "INT-Copa America", "national"),
}

# FotMob round names -> our stage keys in config/competitions.yml. Fixture
# lists use readable names; match payloads use fraction notation for the same
# rounds, so both spellings are mapped.
STAGE_MAP = {
    "final": "final",
    "bronze final": "third_place",
    "third place play-off": "third_place",
    "semi-finals": "semi_final",
    "semi-final": "semi_final",
    "1/2": "semi_final",
    "quarter-finals": "quarter_final",
    "quarter-final": "quarter_final",
    "1/4": "quarter_final",
    "round of 16": "round_of_16",
    "1/8": "round_of_16",
    "round of 32": "round_of_32",
    "playoff": "playoff",
    "play-offs": "playoff",
    "knockout play-offs": "playoff",
    "1/16": "playoff",
    "group stage": "group_stage",
}

# usualPlayingPositionId -> coarse group used by the position-specific weights
POSITION_GROUP = {0: "GK", 1: "DEF", 2: "MID", 3: "FWD"}

# Normalised FotMob stat title -> our canonical column name. Anything not
# listed here still reaches the output under its normalised title, so a new
# FotMob stat shows up as a new column instead of being silently dropped.
CANONICAL_STATS = {
    "fotmob_rating": "rating",
    "minutes_played": "minutes",
    "goals": "goals",
    "assists": "assists",
    "expected_goals_xg": "xg",
    "expected_goals_on_target_xgot": "xgot",
    "expected_assists_xa": "xa",
    "xg_non_penalty": "npxg",
    "total_shots": "shots",
    "shots_on_target": "shots_on_target",
    "shots_off_target": "shots_off_target",
    "accurate_passes": "passes_completed",
    "accurate_passes_total": "passes",
    "chances_created": "key_passes",
    "big_chances_created": "big_chances_created",
    "big_chances_missed": "big_chances_missed",
    "touches": "touches",
    "touches_in_opposition_box": "touches_opp_box",
    "passes_into_final_third": "passes_final_third",
    "accurate_long_balls": "long_balls_completed",
    "accurate_long_balls_total": "long_balls",
    "accurate_crosses": "crosses_completed",
    "accurate_crosses_total": "crosses",
    "successful_dribbles": "dribbles_completed",
    "successful_dribbles_total": "dribbles",
    "dribbled_past": "dribbled_past",
    "dispossessed": "dispossessed",
    "defensive_actions": "defensive_actions",
    "tackles": "tackles",
    "tackles_won": "tackles_won",
    "blocks": "blocks",
    "clearances": "clearances",
    "interceptions": "interceptions",
    "recoveries": "recoveries",
    "ground_duels_won": "ground_duels_won",
    "ground_duels_won_total": "ground_duels",
    "aerial_duels_won": "aerial_duels_won",
    "aerial_duels_won_total": "aerial_duels",
    "duels_won": "duels_won",
    "duels_lost": "duels_lost",
    "was_fouled": "fouls_won",
    "fouls_committed": "fouls",
    "error_led_to_goal": "errors_led_to_goal",
    "saves": "saves",
    "goals_conceded": "goals_conceded",
    "goals_prevented": "goals_prevented",
    "penalties_saved": "penalties_saved",
    "diving_save": "diving_saves",
}


def _slugify_stat(title: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", title.lower())).strip("_")


class FotMobClient:
    """Polite, disk-cached client for the FotMob ``_next/data`` endpoints."""

    def __init__(self, delay: float = 0.6, cache_dir: Path | None = None) -> None:
        self.delay = delay
        self.cache_dir = cache_dir or CACHE_DIR
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "*/*"})
        self._build_id: str | None = None
        self._last_request = 0.0

    @property
    def build_id(self) -> str:
        if self._build_id is None:
            self._build_id = self._resolve_build_id()
        return self._build_id

    def _resolve_build_id(self) -> str:
        html = self._raw_get(BASE + "/").text
        match = re.search(r'"buildId":"([^"]+)"', html)
        if not match:
            raise RuntimeError("Could not find buildId in the FotMob homepage")
        return match.group(1)

    def _raw_get(self, url: str, params: dict | None = None, retries: int = 3) -> requests.Response:
        last: Exception | None = None
        for attempt in range(retries):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait + random.uniform(0, 0.2))
            try:
                resp = self.session.get(url, params=params, timeout=60)
                self._last_request = time.monotonic()
                resp.raise_for_status()
                return resp
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
            except requests.HTTPError as exc:
                # FotMob throws occasional transient 5xx; 4xx is not retryable.
                if exc.response is None or exc.response.status_code < 500:
                    raise
                last = exc
            self._last_request = time.monotonic()
            time.sleep(2**attempt + random.uniform(0, 0.5))
        raise last  # type: ignore[misc]

    def get_json(self, route: str, params: dict | None = None) -> dict[str, Any]:
        """GET a Next.js data route, refreshing the build id if it went stale."""
        for attempt in (1, 2):
            url = f"{BASE}/_next/data/{self.build_id}/en{route}.json"
            try:
                return self._raw_get(url, params=params).json()["pageProps"]
            except requests.HTTPError as exc:
                stale = exc.response is not None and exc.response.status_code == 404
                if stale and attempt == 1:
                    self._build_id = self._resolve_build_id()
                    continue
                raise
        raise AssertionError("unreachable")

    # ------------------------------------------------------------------ #
    # Fixtures
    # ------------------------------------------------------------------ #

    def available_seasons(self, league: League) -> list[str]:
        props = self.get_json(
            f"/leagues/{league.fotmob_id}/matches/{league.slug}",
            {"id": league.fotmob_id, "slug": league.slug, "tab": "matches"},
        )
        return props.get("allAvailableSeasons") or []

    def season_matches(
        self, league: League, season: str | None = None, finished_only: bool = True
    ) -> list[dict[str, Any]]:
        """Fixture list for one FotMob season label, e.g. ``"2025/2026"``."""
        params = {"id": league.fotmob_id, "slug": league.slug, "tab": "matches"}
        if season:
            params["season"] = season
        props = self.get_json(f"/leagues/{league.fotmob_id}/matches/{league.slug}", params)
        matches = (props.get("fixtures") or {}).get("allMatches") or []
        if finished_only:
            matches = [m for m in matches if (m.get("status") or {}).get("finished")]
        return matches

    def matches_in_season(self, league: League, season: str) -> list[dict[str, Any]]:
        """Every finished match that actually falls inside *our* season window.

        Scans the FotMob season labels that could overlap the window and keeps
        fixtures by kickoff date, so mislabelled cups land in the right season.
        Fixture lists are one cheap request each and carry kickoff times, so the
        filtering happens before any match payload is downloaded.
        """
        start, end = season_window(season)
        available = set(self.available_seasons(league))
        first, second = season.split("/")
        candidates = [
            season,
            f"{int(first) - 1}/{first}",
            f"{second}/{int(second) + 1}",
            first,
            second,
        ]

        seen: dict[str, dict[str, Any]] = {}
        for label in candidates:
            if label not in available:
                continue
            for fixture in self.season_matches(league, label):
                kickoff = _kickoff_date((fixture.get("status") or {}).get("utcTime"))
                if kickoff is None or not (start <= kickoff < end):
                    continue
                seen.setdefault(str(fixture["id"]), fixture)
        return sorted(seen.values(), key=lambda f: f["status"]["utcTime"])

    # ------------------------------------------------------------------ #
    # Match payloads
    # ------------------------------------------------------------------ #

    def _match_cache_path(self, match_id: str) -> Path:
        path = self.cache_dir / "matches" / f"{match_id}.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def match_payload(self, fixture: dict[str, Any], force: bool = False) -> dict[str, Any]:
        """Full match payload, cached on disk so re-parsing never re-downloads."""
        match_id = str(fixture["id"])
        cached = self._match_cache_path(match_id)
        if cached.exists() and not force:
            return json.loads(gzip.decompress(cached.read_bytes()).decode("utf-8"))

        # Both legs of a fixture share one /matches/{slug}/{hash} route, which
        # serves whichever leg FotMob considers current. Only /match/{id}
        # resolves a specific match.
        props = self.get_json(f"/match/{match_id}", {"id": match_id})
        returned = str((props.get("general") or {}).get("matchId"))
        if returned != match_id:
            raise RuntimeError(f"FotMob served match {returned} when asked for {match_id}")
        cached.write_bytes(gzip.compress(json.dumps(props).encode("utf-8")))
        return props

    def is_cached(self, match_id: str) -> bool:
        return self._match_cache_path(str(match_id)).exists()

    # ------------------------------------------------------------------ #
    # Results-only view
    # ------------------------------------------------------------------ #

    def season_results(self, league: League, season: str) -> list[dict[str, Any]]:
        """Kickoff, teams and score for a whole season, without match payloads.

        League tables for past seasons only need the scoreline, and the fixture
        list already carries it, so this costs one request per league-season
        instead of one per match.
        """
        rows = []
        for fixture in self.matches_in_season(league, season):
            score = (fixture.get("status") or {}).get("scoreStr")
            if not score or "-" not in score:
                continue
            home_goals, away_goals = (part.strip() for part in score.split("-", 1))
            if not (home_goals.isdigit() and away_goals.isdigit()):
                continue
            rows.append(
                {
                    "match_id": str(fixture["id"]),
                    "competition_code": league.code,
                    "season": season,
                    # Full timestamp, not just the date: as-of joins compare
                    # against kickoff time, and a date would place a match
                    # before its own kickoff and leak its result.
                    "kickoff": fixture["status"]["utcTime"],
                    "home_team_id": str(fixture["home"]["id"]),
                    "home_team": fixture["home"]["name"],
                    "away_team_id": str(fixture["away"]["id"]),
                    "away_team": fixture["away"]["name"],
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                }
            )
        return rows


# ---------------------------------------------------------------------- #
# Parsing
# ---------------------------------------------------------------------- #


SEASON_START_MONTH = 8  # European club season runs August -> July


def season_window(season: str) -> tuple[date, date]:
    """``"2025/2026"`` -> the 1 Aug 2025 .. 31 Jul 2026 window."""
    start_year = int(season.split("/")[0])
    return date(start_year, SEASON_START_MONTH, 1), date(start_year + 1, SEASON_START_MONTH, 1)


def season_from_date(when: date) -> str:
    """Our season label for a kickoff date, independent of FotMob's labelling.

    FotMob's own season labels cannot be trusted across competitions: the
    Spanish Supercopa played in January 2026 is filed under "2024/2025", and
    one-off finals use bare years. The kickoff date is unambiguous.
    """
    start = when.year if when.month >= SEASON_START_MONTH else when.year - 1
    return f"{start}/{start + 1}"


def _kickoff_date(utc_time: str | None) -> date | None:
    if not utc_time:
        return None
    return datetime.fromisoformat(utc_time).date()


def _as_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _stage_from_round(*candidates: Any) -> str:
    for candidate in candidates:
        key = str(candidate or "").strip().lower()
        if key in STAGE_MAP:
            return STAGE_MAP[key]
        if key.isdigit():
            return "league_phase"
    return "regular_season"


def parse_match(
    props: dict[str, Any],
    league: League,
    season: str,
    fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Match-level row: teams, score, competition, stage, venue.

    The fixture entry is preferred for the round name because the match payload
    labels knockout rounds as fractions ("1/8") that are ambiguous across
    competitions, while fixture lists spell them out.
    """
    general = props.get("general") or {}
    info = (props.get("content") or {}).get("matchFacts", {}).get("infoBox") or {}
    home, away = general.get("homeTeam") or {}, general.get("awayTeam") or {}
    stadium = info.get("Stadium") or {}

    header_teams = ((props.get("header") or {}).get("teams") or [{}, {}])
    home_score = header_teams[0].get("score") if len(header_teams) > 0 else None
    away_score = header_teams[1].get("score") if len(header_teams) > 1 else None

    kickoff = _kickoff_date(general.get("matchTimeUTCDate"))

    return {
        "fotmob_match_id": str(general.get("matchId")),
        "season": season_from_date(kickoff) if kickoff else season,
        "competition_code": league.code,
        "fotmob_league_id": general.get("parentLeagueId") or general.get("leagueId"),
        "competition_name": general.get("leagueName"),
        # Round labels mix ints ("4") and strings ("Quarter-Finals"); keep text.
        "round": _as_text(general.get("matchRound")),
        "round_name": _as_text(
            (fixture or {}).get("roundName") or general.get("leagueRoundName")
        ),
        "stage": _stage_from_round(
            (fixture or {}).get("roundName"),
            (fixture or {}).get("round"),
            general.get("leagueRoundName"),
            general.get("matchRound"),
        ),
        "kickoff_utc": general.get("matchTimeUTCDate"),
        # "xG" = full advanced stats; "lower" = basic only, no rating/xG; amateur
        # cup rounds carry no per-player data at all.
        "coverage_level": general.get("coverageLevel"),
        "player_rows": len(
            [p for p in ((props.get("content") or {}).get("playerStats") or {}).values()
             if any(grp.get("stats") for grp in (p.get("stats") or []))]
        ),
        "home_team_id": home.get("id"),
        "home_team": home.get("name"),
        "away_team_id": away.get("id"),
        "away_team": away.get("name"),
        "home_score": home_score,
        "away_score": away_score,
        "venue": stadium.get("name"),
        "venue_city": stadium.get("city"),
        "venue_country": stadium.get("country"),
        "venue_capacity": stadium.get("capacity"),
        "attendance": info.get("Attendance"),
        "referee": (info.get("Referee") or {}).get("text"),
    }


def _lineup_index(lineup: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """player_id -> {started, position_group, shirt, minutes_off, cards, ...}."""
    index: dict[int, dict[str, Any]] = {}
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for group, started in (("starters", True), ("subs", False)):
            for player in team.get(group) or []:
                if not isinstance(player, dict) or player.get("id") is None:
                    continue
                perf = player.get("performance") or {}
                events = [e.get("type") for e in (perf.get("events") or [])]
                subs = perf.get("substitutionEvents") or []
                index[int(player["id"])] = {
                    "started": started,
                    "team_formation": team.get("formation"),
                    "shirt_number": player.get("shirtNumber"),
                    "age": player.get("age"),
                    "country": player.get("countryName"),
                    "country_code": player.get("countryCode"),
                    "market_value": player.get("marketValue"),
                    "position_id": player.get("positionId"),
                    "position_group": POSITION_GROUP.get(
                        player.get("usualPlayingPositionId"), None
                    ),
                    "yellow_cards": events.count("yellowCard"),
                    "red_cards": events.count("redCard")
                    + events.count("yellowRedCard"),
                    "sub_in_minute": next(
                        (s.get("time") for s in subs if s.get("type") == "subIn"), None
                    ),
                    "sub_out_minute": next(
                        (s.get("time") for s in subs if s.get("type") == "subOut"), None
                    ),
                }
    return index


def _goal_events(content: dict[str, Any]) -> dict[int, dict[str, int]]:
    """Own and penalty goals per player.

    FotMob's per-player stats count neither, so the sum of ``goals`` sits a few
    percent below the scoreline until own goals are added back.
    """
    events = ((content.get("matchFacts") or {}).get("events") or {}).get("events") or []
    counts: dict[int, dict[str, int]] = {}
    for event in events:
        if event.get("type") != "Goal" or event.get("isPenaltyShootoutEvent"):
            continue
        player_id = (event.get("player") or {}).get("id")
        if player_id is None:
            continue
        bucket = counts.setdefault(int(player_id), {"own_goals": 0, "penalty_goals": 0})
        description = str(event.get("goalDescription") or "").lower()
        if event.get("ownGoal") or description.startswith("own"):
            bucket["own_goals"] += 1
        elif "penalty" in description:
            bucket["penalty_goals"] += 1
    return counts


def parse_player_rows(
    props: dict[str, Any], match: dict[str, Any]
) -> list[dict[str, Any]]:
    """One row per player who appeared, with every stat FotMob exposes."""
    content = props.get("content") or {}
    player_stats = content.get("playerStats") or {}
    lineup = _lineup_index(content.get("lineup") or {})
    goal_events = _goal_events(content)

    rows: list[dict[str, Any]] = []
    for raw_id, player in player_stats.items():
        groups = player.get("stats") or []
        if not any(group.get("stats") for group in groups):
            continue  # unused substitute: on the teamsheet but never played
        player_id = int(player.get("id") or raw_id)
        meta = lineup.get(player_id, {})
        row: dict[str, Any] = {
            "fotmob_match_id": match["fotmob_match_id"],
            "season": match["season"],
            "competition_code": match["competition_code"],
            "stage": match["stage"],
            "kickoff_utc": match["kickoff_utc"],
            "fotmob_player_id": player_id,
            "opta_player_id": player.get("optaId"),
            "player": player.get("name"),
            "fotmob_team_id": player.get("teamId"),
            "team": player.get("teamName"),
            "is_goalkeeper": player.get("isGoalkeeper"),
            **{k: v for k, v in meta.items()},
            **goal_events.get(player_id, {"own_goals": 0, "penalty_goals": 0}),
        }
        row["opponent_team_id"] = (
            match["away_team_id"]
            if str(player.get("teamId")) == str(match["home_team_id"])
            else match["home_team_id"]
        )
        row["is_home"] = str(player.get("teamId")) == str(match["home_team_id"])

        for group in groups:
            for title, entry in (group.get("stats") or {}).items():
                if not isinstance(entry, dict):
                    continue
                value = entry.get("stat", entry)
                key = _slugify_stat(title)
                row[CANONICAL_STATS.get(key, key)] = value.get("value")
                if value.get("total") is not None:
                    total_key = f"{key}_total"
                    row[CANONICAL_STATS.get(total_key, total_key)] = value["total"]

        row.pop("shotmap", None)
        rows.append(row)
    return rows


def iter_season(
    client: FotMobClient,
    league: League,
    season: str,
    limit: int | None = None,
    on_progress=None,
) -> Iterator[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Yield ``(match_row, player_rows)`` for every finished match of a season."""
    fixtures = client.matches_in_season(league, season)
    if limit:
        fixtures = fixtures[:limit]
    for i, fixture in enumerate(fixtures, start=1):
        try:
            props = client.match_payload(fixture)
            match = parse_match(props, league, season, fixture)
            players = parse_player_rows(props, match)
        except Exception as exc:  # noqa: BLE001 - one bad match must not kill a run
            if on_progress:
                on_progress(i, len(fixtures), fixture, None, exc)
            continue
        if on_progress:
            on_progress(i, len(fixtures), fixture, len(players), None)
        yield match, players
