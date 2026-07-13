# WNBA Prop Lab

A GitHub Pages-ready WNBA prop research dashboard with game-slate filtering, Last 10, Last 5, and head-to-head results.

## How the daily matchup matching works

1. `data/lines.json` contains the current prop board: player, market, and line.
2. The GitHub Action runs `scripts/update_stats.py` each morning.
3. The script fetches the day's WNBA schedule in Eastern Time.
4. It identifies each player's current team and matches that team to its scheduled opponent.
5. Players whose teams do not play that day are removed.
6. The site shows game buttons such as `ATL @ LVA` and only displays props belonging to selected games.

You do **not** need to type the opponent in `lines.json`; the updater matches it automatically.

## Required GitHub secret

Create `BALLDONTLIE_API_KEY` under **Settings → Secrets and variables → Actions**.

## Entering lines

Edit `data/lines.json`:

```json
{"player":"A'ja Wilson","market":"pts","market_label":"Points","line":26.5}
```

Supported markets: `pts`, `reb`, `ast`, `pra`, and `3pm`.

## Deploy

Under **Settings → Pages**, choose **GitHub Actions**. The included workflows deploy the site and update the data daily.

## Important

The demo values are examples. Automatic statistics and schedule updates require the API key. PrizePicks does not provide a supported public feed in this project, so its daily lines must be entered into `data/lines.json` or supplied by a data provider you are authorized to use.
