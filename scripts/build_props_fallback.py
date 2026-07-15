import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LINES_PATH = Path("data/lines.json")
PROPS_PATH = Path("data/props.json")
ET = ZoneInfo("America/New_York")


def team_abbreviation(name: str) -> str:
    mapping = {
        "Atlanta Dream": "ATL",
        "Chicago Sky": "CHI",
        "Connecticut Sun": "CON",
        "Dallas Wings": "DAL",
        "Golden State Valkyries": "GSV",
        "Indiana Fever": "IND",
        "Las Vegas Aces": "LVA",
        "Los Angeles Sparks": "LAS",
        "Minnesota Lynx": "MIN",
        "New York Liberty": "NYL",
        "Phoenix Mercury": "PHX",
        "Seattle Storm": "SEA",
        "Washington Mystics": "WAS",
        "Toronto Tempo": "TOR",
        "Portland Fire": "POR",
    }
    return mapping.get(name, name[:3].upper())


def main():
    if not LINES_PATH.exists():
        raise SystemExit("Missing data/lines.json")

    lines_data = json.loads(LINES_PATH.read_text(encoding="utf-8"))
    lines = lines_data.get("props", [])

    props = []
    games_by_id = {}

    for line in lines:
        home_name = line.get("home_team_name", "")
        away_name = line.get("away_team_name", "")
        home = team_abbreviation(home_name)
        away = team_abbreviation(away_name)
        event_id = line.get("event_id")

        if event_id:
            games_by_id[event_id] = {
                "id": event_id,
                "date": lines_data.get("slate_date"),
                "datetime": line.get("commence_time"),
                "home_team": home,
                "away_team": away,
            }

        props.append({
            **line,
            "team": "",
            "opponent": "",
            "home": None,
            "game_id": event_id,
            "game_date": lines_data.get("slate_date"),
            "game_datetime": line.get("commence_time"),
            "matchup": f"{away} @ {home}",
            "position": "",
            "projection": None,
            "edge": None,
            "last10": [],
            "h2h": [],
            "stats_available": False,
        })

    payload = {
        "updated_at": datetime.now(ET).isoformat(timespec="minutes"),
        "slate_date": lines_data.get("slate_date"),
        "stats_status": "unavailable",
        "games": list(games_by_id.values()),
        "props": props,
    }

    PROPS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote fallback props.json with {len(props)} sportsbook lines.")


if __name__ == "__main__":
    main()
