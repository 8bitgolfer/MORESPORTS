"""Build data/props.json automatically with free ESPN WNBA data.

No API key is required. The script:
- loads today's WNBA schedule,
- maps every player on the PrizePicks Points board to a team/player ID,
- pulls season game logs,
- calculates Last 10, Last 5 and opponent H2H,
- writes only players whose teams play on today's slate.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ET).date().isoformat()
SEASON = TARGET_DATE[:4]
LINES = Path("data/lines.json")
OUT = Path("data/props.json")
ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba"
ESPN_COMMON = "https://site.api.espn.com/apis/common/v3/sports/basketball/wnba"
HEADERS = {"User-Agent": "Mozilla/5.0 WNBAPropLab/2.0", "Accept": "application/json"}

TEAM_ALIASES = {
    "LV": "LVA", "LAS": "LVA", "LA": "LAS", "WSH": "WAS", "NY": "NYL",
    "PHO": "PHX", "PHOENIX MERCURY": "PHX", "MINNESOTA LYNX": "MIN",
    "ATLANTA DREAM": "ATL", "LAS VEGAS ACES": "LVA", "WASHINGTON MYSTICS": "WAS",
    "NEW YORK LIBERTY": "NYL", "CONNECTICUT SUN": "CON", "INDIANA FEVER": "IND",
    "CHICAGO SKY": "CHI", "DALLAS WINGS": "DAL", "SEATTLE STORM": "SEA",
    "LOS ANGELES SPARKS": "LAS", "GOLDEN STATE VALKYRIES": "GSV",
    "TORONTO TEMPO": "TOR", "PORTLAND FIRE": "POR",
}


def get_json(url: str, params: dict | None = None, retries: int = 3) -> dict:
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=35) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed: {url}: {last}")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = value.replace("’", "'").replace(".", " ")
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def canonical_abbr(value: str) -> str:
    raw = (value or "").strip().upper()
    return TEAM_ALIASES.get(raw, raw)


def parse_schedule() -> list[dict]:
    date_key = TARGET_DATE.replace("-", "")
    payload = get_json(f"{ESPN}/scoreboard", {"dates": date_key, "limit": 100})
    games: list[dict] = []
    for event in payload.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        home = next((x for x in competitors if x.get("homeAway") == "home"), {})
        away = next((x for x in competitors if x.get("homeAway") == "away"), {})
        ht, at = home.get("team", {}), away.get("team", {})
        if not ht or not at:
            continue
        games.append({
            "id": str(event.get("id", "")),
            "date": TARGET_DATE,
            "datetime": event.get("date", ""),
            "home_team": canonical_abbr(ht.get("abbreviation", "")),
            "away_team": canonical_abbr(at.get("abbreviation", "")),
            "home_team_id": str(ht.get("id", "")),
            "away_team_id": str(at.get("id", "")),
            "home_team_slug": ht.get("slug", ""),
            "away_team_slug": at.get("slug", ""),
            "status": event.get("status", {}).get("type", {}).get("description", "Scheduled"),
        })
    return games


def roster(team_id: str) -> list[dict]:
    payload = get_json(f"{ESPN}/teams/{team_id}/roster")
    athletes: list[dict] = []
    for group in payload.get("athletes", []):
        entries = group.get("items", []) if isinstance(group, dict) else []
        for p in entries:
            athletes.append(p)
    # Some versions return a flat athletes list.
    if not athletes:
        for p in payload.get("athletes", []):
            if isinstance(p, dict) and p.get("id"):
                athletes.append(p)
    return athletes


def player_lookup(games: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    lookup: dict[str, dict] = {}
    team_players: dict[str, list[dict]] = {}
    for game in games:
        for side in ("home", "away"):
            team_id = game[f"{side}_team_id"]
            team_abbr = game[f"{side}_team"]
            if team_id in team_players:
                continue
            players = roster(team_id)
            team_players[team_id] = players
            for p in players:
                full = p.get("fullName") or p.get("displayName") or " ".join(
                    x for x in [p.get("firstName", ""), p.get("lastName", "")] if x
                )
                if full:
                    lookup[norm(full)] = {
                        "id": str(p.get("id", "")),
                        "name": full,
                        "team_id": team_id,
                        "team": team_abbr,
                        "position": (p.get("position") or {}).get("abbreviation", ""),
                    }
    return lookup, team_players


def extract_gamelog(athlete_id: str) -> list[dict]:
    payload = get_json(f"{ESPN_COMMON}/athletes/{athlete_id}/gamelog", {"season": SEASON})
    events = payload.get("events") or {}
    if isinstance(events, list):
        event_map = {str(e.get("id", i)): e for i, e in enumerate(events)}
    else:
        event_map = {str(k): v for k, v in events.items()}

    labels: list[str] = []
    for group in payload.get("labels", []) or []:
        if isinstance(group, str):
            labels.append(group)
    if not labels:
        for cat in payload.get("categories", []) or []:
            labels.extend(cat.get("labels", []) or [])

    logs: list[dict] = []
    for season_type in payload.get("seasonTypes", []) or []:
        for category in season_type.get("categories", []) or []:
            names = category.get("labels") or labels
            for stat in category.get("events", []) or []:
                if not isinstance(stat, dict):
                    continue
                eid = str(stat.get("eventId") or stat.get("id") or "")
                event = event_map.get(eid, {})
                values = stat.get("stats") or stat.get("statistics") or []
                stat_map = {str(k).upper(): v for k, v in zip(names, values)}
                pts = stat_map.get("PTS")
                if pts is None:
                    pts = stat.get("points")
                try:
                    pts_num = float(pts)
                except (TypeError, ValueError):
                    continue
                opp = event.get("opponent", {})
                opp_abbr = canonical_abbr(opp.get("abbreviation") or opp.get("shortDisplayName") or "")
                date = event.get("gameDate") or event.get("date") or ""
                logs.append({
                    "date_full": date[:10],
                    "date": date[5:10].replace("-", "/") if len(date) >= 10 else date,
                    "value": pts_num,
                    "opponent": opp_abbr,
                })
    # Alternate response: directly nested statistics by event.
    if not logs:
        for eid, event in event_map.items():
            stats = event.get("stats") or event.get("statistics") or []
            if isinstance(stats, dict):
                pts = stats.get("points") or stats.get("PTS")
            else:
                pts = None
            if pts is None:
                continue
            date = event.get("gameDate") or event.get("date") or ""
            opp = event.get("opponent", {})
            logs.append({"date_full": date[:10], "date": date[5:10].replace("-", "/"), "value": float(pts), "opponent": canonical_abbr(opp.get("abbreviation", ""))})

    unique: dict[tuple[str, str], dict] = {}
    for item in logs:
        unique[(item["date_full"], item["opponent"])] = item
    return sorted(unique.values(), key=lambda x: x["date_full"], reverse=True)


def find_player(name: str, lookup: dict[str, dict]) -> dict | None:
    key = norm(name)
    if key in lookup:
        return lookup[key]
    # Handle suffixes and punctuation differences, but avoid loose matching that can choose wrong players.
    candidates = [v for k, v in lookup.items() if k.endswith(key) or key.endswith(k)]
    return candidates[0] if len(candidates) == 1 else None


def main() -> None:
    games = parse_schedule()
    if not games:
        raise RuntimeError(f"No WNBA games found for {TARGET_DATE}")
    with LINES.open(encoding="utf-8") as f:
        board = json.load(f)
    lines = [x for x in board.get("props", []) if x.get("market") == "pts"]
    if not lines:
        raise RuntimeError("data/lines.json contains no live WNBA Points props")

    lookup, _ = player_lookup(games)
    output: list[dict] = []
    excluded: list[dict] = []
    for line in lines:
        player = find_player(str(line.get("player", "")), lookup)
        if not player:
            excluded.append({"player": line.get("player"), "reason": "not found on a team in today's slate"})
            continue
        game = next((g for g in games if player["team_id"] in {g["home_team_id"], g["away_team_id"]}), None)
        if not game:
            excluded.append({"player": line.get("player"), "reason": "team has no game today"})
            continue
        home = player["team_id"] == game["home_team_id"]
        opponent = game["away_team"] if home else game["home_team"]
        logs = extract_gamelog(player["id"])
        last10 = [{k: v for k, v in x.items() if k != "date_full"} for x in logs[:10]]
        h2h = [{k: v for k, v in x.items() if k != "date_full"} for x in logs if x["opponent"] == opponent]
        values = [float(x["value"]) for x in last10]
        projection = round(sum(values) / len(values), 1) if values else 0
        output.append({
            **line,
            "team": player["team"],
            "opponent": opponent,
            "home": home,
            "game_id": game["id"],
            "game_date": TARGET_DATE,
            "game_datetime": game["datetime"],
            "position": player["position"],
            "projection": projection,
            "last10": last10,
            "h2h": h2h,
        })

    now = datetime.now(ET).isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump({
            "updated_at": now,
            "slate_date": TARGET_DATE,
            "status": "live",
            "sources": {"lines": "PrizePicks", "schedule_and_stats": "ESPN"},
            "games": games,
            "props": sorted(output, key=lambda x: (x["game_datetime"], x["team"], x["player"])),
            "excluded": excluded,
        }, f, indent=2)
    print(f"Wrote {len(output)} live Points props; excluded {len(excluded)}; {len(games)} games.")


if __name__ == "__main__":
    main()
