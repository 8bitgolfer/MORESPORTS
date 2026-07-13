"""Import the live PrizePicks WNBA standard Points board.

No API key is required. This uses PrizePicks' public web JSON endpoint. If the
endpoint is unavailable, the script exits non-zero and preserves the last good
board so a temporary outage never wipes the site.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OUT = Path("data/lines.json")
BASE = "https://api.prizepicks.com"
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ET).date().isoformat()

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://app.prizepicks.com",
    "Referer": "https://app.prizepicks.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
}


def get_json(path: str, params: dict | None = None, retries: int = 3) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Request failed after {retries} attempts: {last_error}")


def discover_wnba_league_id() -> str:
    override = os.environ.get("PRIZEPICKS_WNBA_LEAGUE_ID")
    if override:
        return override
    payload = get_json("/leagues")
    for league in payload.get("data", []):
        attrs = league.get("attributes", {})
        name = str(attrs.get("name", "")).strip().lower()
        if name == "wnba" or "wnba" in name:
            return str(league.get("id"))
    raise RuntimeError("WNBA league not found in PrizePicks league list")


def parse_included(included: list[dict]) -> tuple[dict[str, str], dict[str, dict]]:
    players: dict[str, str] = {}
    teams: dict[str, dict] = {}
    for obj in included:
        attrs = obj.get("attributes", {})
        obj_type = obj.get("type", "")
        obj_id = str(obj.get("id", ""))
        if obj_type in {"new_player", "player"}:
            name = attrs.get("name") or attrs.get("display_name")
            if name:
                players[obj_id] = str(name)
        elif obj_type in {"team", "new_team"}:
            teams[obj_id] = attrs
    return players, teams


def relationship_id(item: dict, *names: str) -> str:
    rels = item.get("relationships", {})
    for name in names:
        data = rels.get(name, {}).get("data")
        if isinstance(data, dict) and data.get("id") is not None:
            return str(data["id"])
    return ""


def projection_date(attrs: dict) -> str | None:
    raw = attrs.get("start_time") or attrs.get("game_time") or attrs.get("end_time")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(ET).date().isoformat()
    except ValueError:
        return None


def is_standard(attrs: dict) -> bool:
    # PrizePicks has used several fields over time for alternate/demon/goblin lines.
    odds_type = str(attrs.get("odds_type", "standard") or "standard").lower()
    flash_sale = bool(attrs.get("flash_sale_line_score"))
    projection_type = str(attrs.get("projection_type", "") or "").lower()
    return odds_type in {"", "standard"} and not flash_sale and projection_type not in {"demon", "goblin"}


def main() -> None:
    league_id = discover_wnba_league_id()
    payload = get_json(
        "/projections",
        {
            "league_id": league_id,
            "per_page": 1000,
            "single_stat": "true",
        },
    )
    players, teams = parse_included(payload.get("included", []))

    props: list[dict] = []
    seen: set[tuple[str, float]] = set()
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        stat = str(attrs.get("stat_type", "")).strip().lower()
        if stat not in {"points", "pts"} or not is_standard(attrs):
            continue
        date = projection_date(attrs)
        if date and date != TARGET_DATE:
            continue

        player_id = relationship_id(item, "new_player", "player")
        team_id = relationship_id(item, "team", "new_team")
        name = players.get(player_id) or attrs.get("name")
        line = attrs.get("line_score")
        if not name or line is None:
            continue
        key = (str(name).casefold(), float(line))
        if key in seen:
            continue
        seen.add(key)

        team_attrs = teams.get(team_id, {})
        props.append(
            {
                "player": str(name),
                "market": "pts",
                "market_label": "Points",
                "line": float(line),
                "start_time": attrs.get("start_time") or attrs.get("game_time") or "",
                "prizepicks_projection_id": str(item.get("id", "")),
                "prizepicks_player_id": player_id,
                "team_hint": team_attrs.get("abbreviation") or team_attrs.get("name") or attrs.get("team") or "",
            }
        )

    props.sort(key=lambda x: x["player"])
    if not props:
        raise RuntimeError(f"PrizePicks returned no standard WNBA Points props for {TARGET_DATE}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "updated_at": datetime.now(ET).isoformat(timespec="seconds"),
                "slate_date": TARGET_DATE,
                "source": "PrizePicks web board",
                "props": props,
            },
            f,
            indent=2,
        )
    print(f"Imported {len(props)} live WNBA Points props for {TARGET_DATE}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"PrizePicks import failed; preserving {OUT}: {exc}", file=sys.stderr)
        sys.exit(1)
