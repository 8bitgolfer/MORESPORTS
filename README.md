# WNBA Prop Lab — Automatic Sportsbook Version

This version imports WNBA **player points** lines from DraftKings and FanDuel through The Odds API, matches players to the current WNBA slate, and builds Last 5, Last 10, and head-to-head results.

## GitHub secrets required

Create these under **Settings → Secrets and variables → Actions**:

- `ODDS_API_KEY` — key from The Odds API
- `BALLDONTLIE_API_KEY` — key from BALLDONTLIE WNBA API

## Automatic update

The workflow is `.github/workflows/update-wnba.yml`. It runs four times per day and can also be started manually from the Actions tab. Use the optional date input to rebuild a particular slate.

## Important coverage note

The site displays every DraftKings/FanDuel WNBA player-points line returned by the odds provider at update time. A book may post lines late, remove a player, suspend a market, or provide incomplete coverage. The updater cannot display a line that the provider/book has not published.
