import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ET).date().isoformat()
SEASON = int(TARGET_DATE[:4])
LINES_PATH = Path("data/lines.json")
OUT_PATH = Path("data/props.json")
CACHE_PATH = Path("data/espn_boxscore_cache.json")

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"

TEAM_ABBR = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Las Vegas Aces": "LVA", "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX", "Seattle Storm": "SEA",
    "Washington Mystics": "WAS", "Toronto Tempo": "TOR", "Portland Fire": "POR",
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; WNBA-Prop-Lab/3.0)",
    "Accept": "application/json,text/plain,*/*",
})


def norm(value):
    value = str(value or "").replace("’", "'").replace("-", " ").lower().strip()
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return " ".join(value.split())


def get_json(url, params=None, attempts=4, timeout=40):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = SESSION.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            print(f"Request attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Request failed after {attempts} attempts: {last_error}")


def season_start():
    # WNBA regular seasons normally begin in May. Starting April 15 also captures unusual early games.
    return date(SEASON, 4, 15)


def compact(d):
    return d.strftime("%Y%m%d")


def load_cache():
    if not CACHE_PATH.exists():
        return {"season": SEASON, "events": {}}
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cache.get("season") != SEASON:
            return {"season": SEASON, "events": {}}
        cache.setdefault("events", {})
        return cache
    except Exception:
        return {"season": SEASON, "events": {}}


def event_info(event):
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status_type = ((competition.get("status") or {}).get("type") or {})
    return {
        "id": str(event.get("id") or ""),
        "date": event.get("date") or competition.get("date") or "",
        "completed": bool(status_type.get("completed")),
        "home_team": ((home.get("team") or {}).get("abbreviation") or "").upper(),
        "away_team": ((away.get("team") or {}).get("abbreviation") or "").upper(),
    }


def parse_summary(summary, event):
    event_id = event["id"]
    event_date = event["date"][:10]
    home_abbr = event["home_team"]
    away_abbr = event["away_team"]
    rows = []

    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        team = team_block.get("team") or {}
        team_abbr = (team.get("abbreviation") or "").upper()
        opponent = away_abbr if team_abbr == home_abbr else home_abbr
        home = team_abbr == home_abbr

        for stat_group in team_block.get("statistics") or []:
            names = stat_group.get("names") or []
            try:
                pts_index = names.index("points")
            except ValueError:
                # ESPN occasionally uses short labels in an alternate payload.
                labels = [str(x).lower() for x in (stat_group.get("labels") or [])]
                pts_index = labels.index("pts") if "pts" in labels else -1
            if pts_index < 0:
                continue

            for athlete_row in stat_group.get("athletes") or []:
                athlete = athlete_row.get("athlete") or {}
                stats = athlete_row.get("stats") or []
                if pts_index >= len(stats):
                    continue
                try:
                    points = float(stats[pts_index] or 0)
                except (TypeError, ValueError):
                    points = 0.0
                rows.append({
                    "event_id": event_id,
                    "date": event_date,
                    "player": athlete.get("displayName") or athlete.get("fullName") or "",
                    "team": team_abbr,
                    "opponent": opponent,
                    "home": home,
                    "points": points,
                    "position": ((athlete.get("position") or {}).get("abbreviation") or ""),
                })
    return rows


def average(values):
    return round(sum(values) / len(values), 1) if values else 0.0


def over_rate(values, line):
    return round(100 * sum(v > line for v in values) / len(values)) if values else 0


def main():
    lines_payload = json.loads(LINES_PATH.read_text(encoding="utf-8"))
    lines = [p for p in lines_payload.get("props", []) if p.get("market") == "pts"]

    games_map = {}
    for p in lines:
        event_id = p.get("event_id")
        away = TEAM_ABBR.get(p.get("away_team_name"), str(p.get("away_team_name") or "")[:3].upper())
        home = TEAM_ABBR.get(p.get("home_team_name"), str(p.get("home_team_name") or "")[:3].upper())
        games_map[event_id] = {
            "id": event_id,
            "date": TARGET_DATE,
            "datetime": p.get("commence_time", ""),
            "away_team": away,
            "home_team": home,
        }

    if not lines:
        OUT_PATH.write_text(json.dumps({
            "updated_at": datetime.now(ET).isoformat(timespec="minutes"),
            "slate_date": TARGET_DATE,
            "games": list(games_map.values()),
            "props": [],
            "message": "No sportsbook player-points lines are currently posted."
        }, indent=2), encoding="utf-8")
        print("No sportsbook lines to enrich.")
        return

    target = date.fromisoformat(TARGET_DATE)
    scoreboard = get_json(SCOREBOARD_URL, {
        "dates": f"{compact(season_start())}-{compact(target)}",
        "limit": 1000,
    })
    events = [event_info(e) for e in scoreboard.get("events", [])]
    completed = [e for e in events if e["id"] and e["completed"] and e["date"][:10] < TARGET_DATE]
    print(f"Found {len(completed)} completed WNBA games before {TARGET_DATE}.")

    cache = load_cache()
    cache_events = cache["events"]
    missing_events = [e for e in completed if e["id"] not in cache_events]
    print(f"Fetching {len(missing_events)} uncached ESPN box scores.")

    for index, event in enumerate(missing_events, 1):
        try:
            summary = get_json(SUMMARY_URL, {"event": event["id"]}, attempts=3, timeout=35)
            cache_events[event["id"]] = {
                "date": event["date"][:10],
                "rows": parse_summary(summary, event),
            }
            if index % 10 == 0:
                CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            time.sleep(0.15)
        except Exception as exc:
            print(f"Skipping ESPN event {event['id']} after retries: {exc}")

    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    all_rows = []
    for cached in cache_events.values():
        if str(cached.get("date", "")) < TARGET_DATE:
            all_rows.extend(cached.get("rows") or [])

    by_player = {}
    for row in all_rows:
        player_key = norm(row.get("player"))
        if player_key:
            by_player.setdefault(player_key, []).append(row)
    for rows in by_player.values():
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)

    out = []
    unmatched = []
    for p in lines:
        player_name = p.get("player", "")
        rows = by_player.get(norm(player_name), [])
        if not rows:
            unmatched.append(player_name)

        away = TEAM_ABBR.get(p.get("away_team_name"), str(p.get("away_team_name") or "")[:3].upper())
        home_team = TEAM_ABBR.get(p.get("home_team_name"), str(p.get("home_team_name") or "")[:3].upper())
        team_abbr = rows[0].get("team", "") if rows else ""

        if team_abbr == home_team:
            is_home = True
            opponent = away
        elif team_abbr == away:
            is_home = False
            opponent = home_team
        else:
            # Keep the line visible even for rookies/new signings with no prior ESPN log.
            is_home = None
            opponent = ""

        recent_rows = rows[:10]
        h2h_rows = [r for r in rows if opponent and r.get("opponent") == opponent][:10]
        last10 = [{
            "date": datetime.fromisoformat(r["date"]).strftime("%m/%d") if r.get("date") else "",
            "value": r.get("points", 0),
            "opponent": r.get("opponent", ""),
        } for r in recent_rows]
        h2h = [{
            "date": datetime.fromisoformat(r["date"]).strftime("%m/%d") if r.get("date") else "",
            "value": r.get("points", 0),
            "opponent": r.get("opponent", ""),
        } for r in h2h_rows]

        l10_values = [float(x["value"]) for x in last10]
        l5_values = l10_values[:5]
        h2h_values = [float(x["value"]) for x in h2h]
        l10_avg = average(l10_values)
        l5_avg = average(l5_values)
        h2h_avg = average(h2h_values)

        if l10_values:
            projection = round((0.65 * l5_avg) + (0.35 * l10_avg), 1)
            if h2h_values:
                projection = round((0.85 * projection) + (0.15 * h2h_avg), 1)
        else:
            projection = 0.0

        line = float(p.get("line") or 0)
        out.append({
            **p,
            "team": team_abbr,
            "opponent": opponent,
            "home": is_home,
            "game_id": p.get("event_id"),
            "game_date": TARGET_DATE,
            "game_datetime": p.get("commence_time", ""),
            "position": rows[0].get("position", "") if rows else "",
            "projection": projection,
            "edge": round(projection - line, 1),
            "last5_avg": l5_avg,
            "last10_avg": l10_avg,
            "h2h_avg": h2h_avg,
            "last5_over_pct": over_rate(l5_values, line),
            "last10_over_pct": over_rate(l10_values, line),
            "h2h_over_pct": over_rate(h2h_values, line),
            "last10": last10,
            "h2h": h2h,
            "stats_available": bool(last10),
        })

    result = {
        "updated_at": datetime.now(ET).isoformat(timespec="minutes"),
        "slate_date": TARGET_DATE,
        "games": list(games_map.values()),
        "props": out,
        "unmatched_players": sorted(set(x for x in unmatched if x)),
        "stats_status": "available",
        "stats_source": "ESPN WNBA box scores",
        "lines_source": "The Odds API",
    }
    OUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} props with ESPN history for {TARGET_DATE}.")
    if unmatched:
        print(f"Players without historical logs ({len(set(unmatched))}): {', '.join(sorted(set(unmatched)))}")


if __name__ == "__main__":
    main()
