import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_wnba"
BASE = "https://api.the-odds-api.com/v4"
BOOKMAKERS = ["draftkings", "fanduel"]
MARKET = "player_points"
OUT = Path("data/lines.json")

if not API_KEY:
    raise SystemExit("Missing ODDS_API_KEY GitHub secret")


def get_json(path, params=None):
    query = dict(params or {})
    query["apiKey"] = API_KEY
    url = BASE + path + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "WNBA-Prop-Lab/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def normalize_name(name):
    return " ".join(str(name or "").replace("’", "'").split())


def main():
    events = get_json(f"/sports/{SPORT}/events")
    props = []
    seen = set()

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue
        data = get_json(
            f"/sports/{SPORT}/events/{event_id}/odds",
            {
                "regions": "us",
                "markets": MARKET,
                "bookmakers": ",".join(BOOKMAKERS),
                "oddsFormat": "american",
                "dateFormat": "iso",
            },
        )
        for book in data.get("bookmakers", []):
            book_key = book.get("key", "")
            book_title = book.get("title") or book_key
            for market in book.get("markets", []):
                if market.get("key") != MARKET:
                    continue
                for outcome in market.get("outcomes", []):
                    # The Odds API player-prop outcomes use description for player
                    # and name for Over/Under.
                    side = str(outcome.get("name", "")).lower()
                    if side != "over":
                        continue
                    player = normalize_name(outcome.get("description"))
                    point = outcome.get("point")
                    if not player or point is None:
                        continue
                    key = (event_id, book_key, player.lower(), float(point))
                    if key in seen:
                        continue
                    seen.add(key)
                    props.append({
                        "player": player,
                        "market": "pts",
                        "market_label": "Points",
                        "line": float(point),
                        "bookmaker": book_key,
                        "bookmaker_label": book_title,
                        "event_id": event_id,
                        "commence_time": data.get("commence_time") or event.get("commence_time"),
                        "home_team_name": data.get("home_team") or event.get("home_team"),
                        "away_team_name": data.get("away_team") or event.get("away_team"),
                    })

    props.sort(key=lambda p: (p.get("commence_time") or "", p["player"], p["bookmaker"]))
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "The Odds API",
        "sportsbooks": BOOKMAKERS,
        "market": MARKET,
        "props": props,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(props)} WNBA points lines from {len(events)} upcoming events.")
    if not props:
        print("No player-points markets are currently posted by DraftKings or FanDuel.")


if __name__ == "__main__":
    main()
