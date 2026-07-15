import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from nba_api.stats.endpoints import playergamelogs

ET = ZoneInfo("America/New_York")
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ET).date().isoformat()
SEASON = TARGET_DATE[:4]
LINES_PATH = Path("data/lines.json")
OUT_PATH = Path("data/props.json")

TEAM_ABBR = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Las Vegas Aces": "LVA", "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX", "Seattle Storm": "SEA",
    "Washington Mystics": "WAS", "Toronto Tempo": "TOR", "Portland Fire": "POR",
}


def norm(value):
    value = str(value or "").replace("’", "'").lower().strip()
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return " ".join(value.split())


def fetch_logs():
    last_error = None
    for attempt in range(3):
        try:
            endpoint = playergamelogs.PlayerGameLogs(
                league_id_nullable="10",
                season_nullable=SEASON,
                season_type_nullable="Regular Season",
                timeout=60,
            )
            frames = endpoint.get_data_frames()
            if not frames:
                return pd.DataFrame()
            return frames[0]
        except Exception as exc:
            last_error = exc
            print(f"NBA Stats request attempt {attempt + 1} failed: {exc}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"NBA Stats failed after 3 attempts: {last_error}")


def parse_opponent(matchup):
    text = str(matchup or "")
    if " vs. " in text:
        return text.split(" vs. ", 1)[1].strip()
    if " @ " in text:
        return text.split(" @ ", 1)[1].strip()
    return ""


def main():
    payload = json.loads(LINES_PATH.read_text(encoding="utf-8"))
    lines = [p for p in payload.get("props", []) if p.get("market") == "pts"]

    games_map = {}
    for p in lines:
        game_id = p.get("event_id")
        away = TEAM_ABBR.get(p.get("away_team_name"), p.get("away_team_name", "")[:3].upper())
        home = TEAM_ABBR.get(p.get("home_team_name"), p.get("home_team_name", "")[:3].upper())
        games_map[game_id] = {
            "id": game_id,
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
        print("No lines to enrich.")
        return

    logs_df = fetch_logs()
    print(f"Downloaded {len(logs_df)} WNBA player-game rows for {SEASON}.")
    if logs_df.empty:
        raise RuntimeError("NBA Stats returned no WNBA player game logs.")

    logs_df["_name"] = logs_df["PLAYER_NAME"].map(norm)
    logs_df["GAME_DATE_DT"] = pd.to_datetime(logs_df["GAME_DATE"], errors="coerce")
    logs_df = logs_df.sort_values("GAME_DATE_DT", ascending=False)

    out = []
    missing = []
    for p in lines:
        player_rows = logs_df[logs_df["_name"] == norm(p.get("player"))]
        if player_rows.empty:
            missing.append(p.get("player"))
            print("Player not found in NBA Stats logs:", p.get("player"))
            continue

        team_abbr = str(player_rows.iloc[0].get("TEAM_ABBREVIATION", ""))
        away = TEAM_ABBR.get(p.get("away_team_name"), p.get("away_team_name", "")[:3].upper())
        home_team = TEAM_ABBR.get(p.get("home_team_name"), p.get("home_team_name", "")[:3].upper())
        home = team_abbr == home_team
        opponent = away if home else home_team

        recent = player_rows.head(10)
        logs = []
        for _, row in recent.iterrows():
            date_value = row.get("GAME_DATE_DT")
            date_text = date_value.strftime("%m/%d") if pd.notna(date_value) else str(row.get("GAME_DATE", ""))
            logs.append({
                "date": date_text,
                "value": float(row.get("PTS", 0) or 0),
                "opponent": parse_opponent(row.get("MATCHUP")),
            })

        h2h_rows = player_rows[player_rows["MATCHUP"].astype(str).str.contains(opponent, regex=False, na=False)].head(10)
        h2h = []
        for _, row in h2h_rows.iterrows():
            date_value = row.get("GAME_DATE_DT")
            date_text = date_value.strftime("%m/%d") if pd.notna(date_value) else str(row.get("GAME_DATE", ""))
            h2h.append({
                "date": date_text,
                "value": float(row.get("PTS", 0) or 0),
                "opponent": opponent,
            })

        values = [x["value"] for x in logs]
        projection = round(sum(values) / len(values), 1) if values else 0
        out.append({
            **p,
            "team": team_abbr,
            "opponent": opponent,
            "home": home,
            "game_id": p.get("event_id"),
            "game_date": TARGET_DATE,
            "game_datetime": p.get("commence_time", ""),
            "position": "",
            "projection": projection,
            "last10": logs,
            "h2h": h2h,
        })

    result = {
        "updated_at": datetime.now(ET).isoformat(timespec="minutes"),
        "slate_date": TARGET_DATE,
        "games": list(games_map.values()),
        "props": out,
        "unmatched_players": sorted(set(x for x in missing if x)),
        "stats_source": "NBA.com stats via nba_api",
        "lines_source": "The Odds API",
    }
    OUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} enriched props across {len(games_map)} games for {TARGET_DATE}.")
    if missing:
        print(f"Unmatched players ({len(set(missing))}): {', '.join(sorted(set(missing)))}")


if __name__ == "__main__":
    main()
