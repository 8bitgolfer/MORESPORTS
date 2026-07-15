"""Import today's WNBA Points projections from the live PrizePicks board.

This uses PrizePicks' web JSON endpoint, which is not an officially documented
public developer API and may change or block automated requests. On failure,
the existing data/lines.json is preserved rather than replaced with bad data.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OUT = "data/lines.json"
BASE = "https://api.prizepicks.com"
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ET).date().isoformat()

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; WNBAPropLab/1.0)",
}

def get_json(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def league_id():
    override = os.environ.get("PRIZEPICKS_WNBA_LEAGUE_ID")
    if override:
        return override
    payload = get_json("/leagues")
    for league in payload.get("data", []):
        attrs = league.get("attributes", {})
        name = str(attrs.get("name", "")).strip().lower()
        if name == "wnba" or "wnba" in name:
            return league.get("id")
    raise RuntimeError("WNBA league was not found in PrizePicks leagues response")

def player_map(included):
    players = {}
    for obj in included:
        if obj.get("type") not in {"new_player", "player"}:
            continue
        attrs = obj.get("attributes", {})
        name = attrs.get("name") or attrs.get("display_name")
        if name:
            players[str(obj.get("id"))] = name
    return players

def projection_player_id(item):
    rel = item.get("relationships", {}).get("new_player", {}).get("data")
    if not rel:
        rel = item.get("relationships", {}).get("player", {}).get("data")
    return str(rel.get("id")) if rel else ""

def is_target_date(attrs):
    raw = attrs.get("start_time") or attrs.get("game_time")
    if not raw:
        return True
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(ET)
        return dt.date().isoformat() == TARGET_DATE
    except ValueError:
        return True

def main():
    lid = league_id()
    payload = get_json("/projections", {
        "league_id": lid,
        "per_page": 500,
        "single_stat": "true",
    })
    players = player_map(payload.get("included", []))
    props = []
    seen = set()
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        stat = str(attrs.get("stat_type", "")).strip().lower()
        if stat not in {"points", "pts"}:
            continue
        if not is_target_date(attrs):
            continue
        # Skip demon/goblin/alternate offerings when the API identifies them.
        odds_type = str(attrs.get("odds_type", "standard")).lower()
        if odds_type not in {"", "standard"}:
            continue
        pid = projection_player_id(item)
        name = players.get(pid) or attrs.get("name")
        line = attrs.get("line_score")
        if not name or line is None:
            continue
        key = (name.lower(), float(line))
        if key in seen:
            continue
        seen.add(key)
        props.append({
            "player": name,
            "market": "pts",
            "market_label": "Points",
            "line": float(line),
        })
    props.sort(key=lambda x: x["player"])
    if not props:
        raise RuntimeError("PrizePicks returned no WNBA Points projections for the selected date")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now(ET).isoformat(timespec="minutes"), "props": props}, f, indent=2)
    print(f"Imported {len(props)} live WNBA Points props for {TARGET_DATE}.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PrizePicks import failed; preserving existing {OUT}: {exc}", file=sys.stderr)
        sys.exit(1)
