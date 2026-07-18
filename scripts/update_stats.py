import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


ET = ZoneInfo("America/New_York")

TARGET_DATE = (
    os.environ.get("WNBA_DATE")
    or datetime.now(ET).date().isoformat()
)

CURRENT_SEASON = int(TARGET_DATE[:4])

# ESPN historical coverage starts well before this, but 2010 provides
# enough history for nearly every current player's last 10 H2H games.
HISTORY_START_YEAR = int(
    os.environ.get("WNBA_HISTORY_START_YEAR", "2010")
)

LINES_PATH = Path("data/lines.json")
OUT_PATH = Path("data/props.json")
CACHE_PATH = Path("data/espn_boxscore_cache.json")

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/wnba/scoreboard"
)

SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/wnba/summary"
)

TEAM_ABBR = {
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

SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; WNBA-Prop-Lab/4.0)"
        ),
        "Accept": "application/json,text/plain,*/*",
    }
)


def norm(value):
    """
    Normalize names for matching sportsbook players to ESPN players.
    """

    value = (
        str(value or "")
        .replace("’", "'")
        .replace("-", " ")
        .lower()
        .strip()
    )

    value = re.sub(r"[^a-z0-9']+", " ", value)

    return " ".join(value.split())


def get_json(
    url,
    params=None,
    attempts=4,
    timeout=40,
):
    """
    Request JSON with retry handling.
    """

    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            response = SESSION.get(
                url,
                params=params,
                timeout=timeout,
            )

            response.raise_for_status()

            return response.json()

        except Exception as exc:
            last_error = exc

            print(
                f"Request attempt "
                f"{attempt}/{attempts} failed: {exc}"
            )

            if attempt < attempts:
                time.sleep(attempt * 2)

    raise RuntimeError(
        "Request failed after "
        f"{attempts} attempts: {last_error}"
    )


def compact(value):
    """
    Convert a date object to ESPN's YYYYMMDD format.
    """

    return value.strftime("%Y%m%d")


def season_start(year):
    """
    Use April 15 so unusually early games are not missed.
    """

    return date(year, 4, 15)


def season_end(year):
    """
    Include the regular season and postseason.

    For the active season, never request dates after TARGET_DATE.
    """

    end = date(year, 11, 15)

    if year == CURRENT_SEASON:
        target = date.fromisoformat(TARGET_DATE)
        return min(end, target)

    return end


def empty_cache():
    """
    Return the current cache structure.
    """

    return {
        "version": 2,
        "history_start_year": HISTORY_START_YEAR,
        "events": {},
    }


def load_cache():
    """
    Load the ESPN box-score cache.

    The old script used a season-specific cache. This function keeps any
    existing events while converting the cache to a multi-season format.
    """

    if not CACHE_PATH.exists():
        return empty_cache()

    try:
        cache = json.loads(
            CACHE_PATH.read_text(encoding="utf-8")
        )

        events = cache.get("events")

        if not isinstance(events, dict):
            events = {}

        return {
            "version": 2,
            "history_start_year": HISTORY_START_YEAR,
            "events": events,
        }

    except Exception as exc:
        print(f"Could not read cache: {exc}")
        return empty_cache()


def save_cache(cache):
    """
    Save the cache safely.
    """

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = CACHE_PATH.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(cache, indent=2),
        encoding="utf-8",
    )

    temporary_path.replace(CACHE_PATH)


def event_info(event):
    """
    Extract the information needed from an ESPN scoreboard event.
    """

    competition = (
        event.get("competitions") or [{}]
    )[0]

    competitors = (
        competition.get("competitors") or []
    )

    home = next(
        (
            competitor
            for competitor in competitors
            if competitor.get("homeAway") == "home"
        ),
        {},
    )

    away = next(
        (
            competitor
            for competitor in competitors
            if competitor.get("homeAway") == "away"
        ),
        {},
    )

    status_type = (
        (competition.get("status") or {})
        .get("type")
        or {}
    )

    return {
        "id": str(event.get("id") or ""),
        "date": (
            event.get("date")
            or competition.get("date")
            or ""
        ),
        "completed": bool(
            status_type.get("completed")
        ),
        "home_team": (
            ((home.get("team") or {})
             .get("abbreviation") or "")
            .upper()
        ),
        "away_team": (
            ((away.get("team") or {})
             .get("abbreviation") or "")
            .upper()
        ),
    }


def parse_summary(summary, event):
    """
    Convert an ESPN game summary into one row per player.
    """

    event_id = event["id"]
    event_date = event["date"][:10]
    home_abbr = event["home_team"]
    away_abbr = event["away_team"]

    rows = []

    player_blocks = (
        (summary.get("boxscore") or {})
        .get("players")
        or []
    )

    for team_block in player_blocks:
        team = team_block.get("team") or {}

        team_abbr = (
            team.get("abbreviation") or ""
        ).upper()

        if team_abbr == home_abbr:
            opponent = away_abbr
            is_home = True
        elif team_abbr == away_abbr:
            opponent = home_abbr
            is_home = False
        else:
            opponent = ""
            is_home = None

        for stat_group in (
            team_block.get("statistics") or []
        ):
            names = [
                str(name).lower()
                for name in (
                    stat_group.get("names") or []
                )
            ]

            labels = [
                str(label).lower()
                for label in (
                    stat_group.get("labels") or []
                )
            ]

            points_index = -1

            if "points" in names:
                points_index = names.index("points")
            elif "pts" in labels:
                points_index = labels.index("pts")

            if points_index < 0:
                continue

            athlete_rows = (
                stat_group.get("athletes") or []
            )

            for athlete_row in athlete_rows:
                athlete = (
                    athlete_row.get("athlete") or {}
                )

                stats = athlete_row.get("stats") or []

                if points_index >= len(stats):
                    continue

                try:
                    points = float(
                        stats[points_index] or 0
                    )
                except (TypeError, ValueError):
                    points = 0.0

                player_name = (
                    athlete.get("displayName")
                    or athlete.get("fullName")
                    or ""
                )

                if not player_name:
                    continue

                rows.append(
                    {
                        "event_id": event_id,
                        "date": event_date,
                        "player": player_name,
                        "player_id": str(
                            athlete.get("id") or ""
                        ),
                        "team": team_abbr,
                        "opponent": opponent,
                        "home": is_home,
                        "points": points,
                        "position": (
                            (
                                athlete.get("position")
                                or {}
                            ).get("abbreviation")
                            or ""
                        ),
                    }
                )

    return rows


def average(values):
    """
    Return a one-decimal average.
    """

    if not values:
        return 0.0

    return round(
        sum(values) / len(values),
        1,
    )


def over_rate(values, line):
    """
    Return the percentage of results strictly over the line.
    Pushes are not counted as overs.
    """

    if not values:
        return 0

    overs = sum(
        value > line
        for value in values
    )

    return round(
        100 * overs / len(values)
    )


def display_date(value):
    """
    Format YYYY-MM-DD as MM/DD.
    """

    if not value:
        return ""

    try:
        return datetime.fromisoformat(
            value
        ).strftime("%m/%d")
    except ValueError:
        return value


def get_team_abbreviation(team_name):
    """
    Convert sportsbook team names into abbreviations.
    """

    if team_name in TEAM_ABBR:
        return TEAM_ABBR[team_name]

    cleaned = str(team_name or "").strip()

    return cleaned[:3].upper()


def collect_historical_events():
    """
    Retrieve completed WNBA event listings from 2010 through TARGET_DATE.

    This only retrieves scoreboard listings. Individual box scores are
    downloaded later and are skipped when already present in the cache.
    """

    all_events = {}

    for year in range(
        CURRENT_SEASON,
        HISTORY_START_YEAR - 1,
        -1,
    ):
        start = season_start(year)
        end = season_end(year)

        if end < start:
            continue

        print(
            f"Checking ESPN WNBA schedule for {year}: "
            f"{start.isoformat()} through "
            f"{end.isoformat()}."
        )

        try:
            scoreboard = get_json(
                SCOREBOARD_URL,
                {
                    "dates": (
                        f"{compact(start)}-"
                        f"{compact(end)}"
                    ),
                    "limit": 1000,
                },
            )
        except Exception as exc:
            print(
                f"Could not retrieve the "
                f"{year} schedule: {exc}"
            )
            continue

        year_events = [
            event_info(event)
            for event in (
                scoreboard.get("events") or []
            )
        ]

        completed_count = 0

        for event in year_events:
            if not event["id"]:
                continue

            if not event["completed"]:
                continue

            if event["date"][:10] >= TARGET_DATE:
                continue

            all_events[event["id"]] = event
            completed_count += 1

        print(
            f"Found {completed_count} completed "
            f"games for {year}."
        )

    return list(all_events.values())


def build_player_index(cache_events):
    """
    Build a newest-to-oldest game-log index for every player.
    """

    all_rows = []

    for cached_event in cache_events.values():
        event_date = str(
            cached_event.get("date") or ""
        )

        if event_date >= TARGET_DATE:
            continue

        rows = cached_event.get("rows") or []

        if isinstance(rows, list):
            all_rows.extend(rows)

    by_player = {}

    for row in all_rows:
        player_key = norm(
            row.get("player")
        )

        if not player_key:
            continue

        by_player.setdefault(
            player_key,
            [],
        ).append(row)

    for rows in by_player.values():
        rows.sort(
            key=lambda row: (
                row.get("date") or ""
            ),
            reverse=True,
        )

    return by_player


def resolve_matchup(prop, rows):
    """
    Determine the player's current opponent from the sportsbook matchup.
    """

    away = get_team_abbreviation(
        prop.get("away_team_name")
    )

    home = get_team_abbreviation(
        prop.get("home_team_name")
    )

    recent_team = (
        rows[0].get("team", "")
        if rows
        else ""
    )

    sportsbook_team = get_team_abbreviation(
        prop.get("team_name")
        or prop.get("team")
        or ""
    )

    if sportsbook_team in {away, home}:
        team_abbr = sportsbook_team
    else:
        team_abbr = recent_team

    if team_abbr == home:
        return team_abbr, away, True

    if team_abbr == away:
        return team_abbr, home, False

    # Last fallback: determine the player's side from a recent game
    # against either team in the current matchup.
    for row in rows:
        row_team = row.get("team", "")

        if row_team == home:
            return row_team, away, True

        if row_team == away:
            return row_team, home, False

    return team_abbr, "", None


def convert_game_rows(rows):
    """
    Convert cached ESPN rows into the frontend game-log structure.
    """

    return [
        {
            "date": display_date(
                row.get("date")
            ),
            "full_date": row.get("date", ""),
            "value": float(
                row.get("points") or 0
            ),
            "opponent": row.get(
                "opponent",
                "",
            ),
            "team": row.get("team", ""),
            "home": row.get("home"),
        }
        for row in rows
    ]


def main():
    if not LINES_PATH.exists():
        raise FileNotFoundError(
            f"Missing sportsbook file: {LINES_PATH}"
        )

    lines_payload = json.loads(
        LINES_PATH.read_text(
            encoding="utf-8"
        )
    )

    lines = [
        prop
        for prop in (
            lines_payload.get("props") or []
        )
        if prop.get("market") == "pts"
    ]

    games_map = {}

    for prop in lines:
        event_id = str(
            prop.get("event_id") or ""
        )

        away = get_team_abbreviation(
            prop.get("away_team_name")
        )

        home = get_team_abbreviation(
            prop.get("home_team_name")
        )

        if not event_id:
            event_id = (
                f"{TARGET_DATE}-{away}-{home}"
            )

        games_map[event_id] = {
            "id": event_id,
            "date": TARGET_DATE,
            "datetime": prop.get(
                "commence_time",
                "",
            ),
            "away_team": away,
            "home_team": home,
        }

    if not lines:
        OUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUT_PATH.write_text(
            json.dumps(
                {
                    "updated_at": datetime.now(
                        ET
                    ).isoformat(
                        timespec="minutes"
                    ),
                    "slate_date": TARGET_DATE,
                    "games": list(
                        games_map.values()
                    ),
                    "props": [],
                    "message": (
                        "No sportsbook player-points "
                        "lines are currently posted."
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "No sportsbook lines to enrich."
        )

        return

    cache = load_cache()
    cache_events = cache["events"]

    completed_events = (
        collect_historical_events()
    )

    missing_events = [
        event
        for event in completed_events
        if event["id"] not in cache_events
    ]

    missing_events.sort(
        key=lambda event: (
            event.get("date") or ""
        )
    )

    print(
        f"Historical events found: "
        f"{len(completed_events)}"
    )

    print(
        f"Cached events: "
        f"{len(cache_events)}"
    )

    print(
        f"Fetching {len(missing_events)} "
        f"uncached ESPN box scores."
    )

    for index, event in enumerate(
        missing_events,
        start=1,
    ):
        try:
            summary = get_json(
                SUMMARY_URL,
                {"event": event["id"]},
                attempts=3,
                timeout=35,
            )

            rows = parse_summary(
                summary,
                event,
            )

            cache_events[event["id"]] = {
                "date": event["date"][:10],
                "home_team": event[
                    "home_team"
                ],
                "away_team": event[
                    "away_team"
                ],
                "rows": rows,
            }

            if index % 10 == 0:
                save_cache(cache)

                print(
                    f"Cached {index}/"
                    f"{len(missing_events)} "
                    f"new box scores."
                )

            # Small pause reduces the risk of temporary ESPN blocks.
            time.sleep(0.15)

        except Exception as exc:
            print(
                f"Skipping ESPN event "
                f"{event['id']} after retries: "
                f"{exc}"
            )

    save_cache(cache)

    by_player = build_player_index(
        cache_events
    )

    output_props = []
    unmatched_players = []

    for prop in lines:
        player_name = str(
            prop.get("player") or ""
        )

        rows = by_player.get(
            norm(player_name),
            [],
        )

        if not rows:
            unmatched_players.append(
                player_name
            )

        (
            team_abbr,
            opponent,
            is_home,
        ) = resolve_matchup(
            prop,
            rows,
        )

        # Last 10 games overall.
        recent_rows = rows[:10]

        # Last 10 career games against today's opponent.
        # Rows are already sorted newest to oldest.
        h2h_rows = [
            row
            for row in rows
            if (
                opponent
                and row.get("opponent")
                == opponent
            )
        ][:10]

        last10 = convert_game_rows(
            recent_rows
        )

        last5 = last10[:5]

        h2h = convert_game_rows(
            h2h_rows
        )

        last10_values = [
            float(game["value"])
            for game in last10
        ]

        last5_values = [
            float(game["value"])
            for game in last5
        ]

        h2h_values = [
            float(game["value"])
            for game in h2h
        ]

        last10_avg = average(
            last10_values
        )

        last5_avg = average(
            last5_values
        )

        h2h_avg = average(
            h2h_values
        )

        if last10_values:
            projection = round(
                (0.65 * last5_avg)
                + (0.35 * last10_avg),
                1,
            )

            if h2h_values:
                projection = round(
                    (0.85 * projection)
                    + (0.15 * h2h_avg),
                    1,
                )
        else:
            projection = 0.0

        try:
            line = float(
                prop.get("line") or 0
            )
        except (TypeError, ValueError):
            line = 0.0

        output_props.append(
            {
                **prop,
                "team": team_abbr,
                "opponent": opponent,
                "home": is_home,
                "game_id": prop.get(
                    "event_id"
                ),
                "game_date": TARGET_DATE,
                "game_datetime": prop.get(
                    "commence_time",
                    "",
                ),
                "position": (
                    rows[0].get(
                        "position",
                        "",
                    )
                    if rows
                    else ""
                ),
                "projection": projection,
                "edge": round(
                    projection - line,
                    1,
                ),
                "last5_avg": last5_avg,
                "last10_avg": last10_avg,
                "h2h_avg": h2h_avg,
                "last5_over_pct": over_rate(
                    last5_values,
                    line,
                ),
                "last10_over_pct": over_rate(
                    last10_values,
                    line,
                ),
                "h2h_over_pct": over_rate(
                    h2h_values,
                    line,
                ),
                "last5": last5,
                "last10": last10,
                "h2h": h2h,
                "last5_games_count": len(
                    last5
                ),
                "last10_games_count": len(
                    last10
                ),
                "h2h_games_count": len(
                    h2h
                ),
                "h2h_limit": 10,
                "stats_available": bool(
                    last10
                ),
            }
        )

    result = {
        "updated_at": datetime.now(
            ET
        ).isoformat(
            timespec="minutes"
        ),
        "slate_date": TARGET_DATE,
        "games": list(
            games_map.values()
        ),
        "props": output_props,
        "unmatched_players": sorted(
            {
                player
                for player in unmatched_players
                if player
            }
        ),
        "stats_status": "available",
        "stats_source": (
            "ESPN WNBA box scores"
        ),
        "h2h_description": (
            "Most recent 10 career games "
            "against today's opponent"
        ),
        "history_start_year": (
            HISTORY_START_YEAR
        ),
        "lines_source": "The Odds API",
    }

    OUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT_PATH.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Wrote {len(output_props)} props "
        f"with ESPN history for "
        f"{TARGET_DATE}."
    )

    print(
        "H2H now uses the most recent "
        "10 career meetings when available."
    )

    if unmatched_players:
        unique_unmatched = sorted(
            {
                player
                for player in unmatched_players
                if player
            }
        )

        print(
            "Players without historical logs "
            f"({len(unique_unmatched)}): "
            f"{', '.join(unique_unmatched)}"
        )


if __name__ == "__main__":
    main()
