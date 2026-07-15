import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API_KEY = os.environ.get("ODDS_API_KEY")
TARGET_DATE = os.environ.get("WNBA_DATE") or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
SPORT = "basketball_wnba"
BASE = "https://api.the-odds-api.com/v4"
BOOKMAKERS = ["draftkings", "fanduel"]
MARKET = "player_points"
OUT = Path("data/lines.json")
ET = ZoneInfo("America/New_York")

if not API_KEY:
    raise SystemExit("Missing ODDS_API_KEY GitHub secret")


def get_json(path, params=None):
    query = dict(params or {})
    query["apiKey"] = API_KEY
    url = BASE + path + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "WNBA-Prop-Lab/2.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        remaining = response.headers.get("x-requests-remaining")
        used = response.headers.get("x-requests-used")
        if remaining is not None:
            print(f"Odds API credits — used: {used}, remaining: {remaining}")
        return json.load(response)


def normalize_name(name):
    return " ".join(str(name or "").replace("’", "'").split())


def event_date_et(event):
    raw = event.get("commence_time")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(ET).date().isoformat()


def main():
    all_events = get_json(f"/sports/{SPORT}/events")
    events = [e for e in all_events if event_date_et(e) == TARGET_DATE]
    print(f"Found {len(events)} WNBA events for {TARGET_DATE}.")

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
                    if str(outcome.get("name", "")).lower() != "over":
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
        "slate_date": TARGET_DATE,
        "source": "The Odds API",
        "sportsbooks": BOOKMAKERS,
        "market": MARKET,
        "props": props,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(props)} WNBA points lines from {len(events)} games for {TARGET_DATE}.")
    if not props:
        print("No DraftKings or FanDuel player-points lines are currently posted for this slate.")


if __name__ == "__main__":
    main()
