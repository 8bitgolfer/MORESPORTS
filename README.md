# WNBA Prop Lab V2

GitHub Pages dashboard for WNBA **Points** props from DraftKings and FanDuel.

## Data flow

1. The Odds API supplies today's WNBA `player_points` lines.
2. `nba_api` accesses NBA.com/WNBA game logs with League ID `10`.
3. The updater calculates Last 5, Last 10, H2H, averages, projection, and edge.
4. GitHub Actions commits `data/lines.json` and `data/props.json` automatically.

## Required GitHub secret

Create one repository Actions secret:

- `ODDS_API_KEY` — your key from The Odds API.

`BALLDONTLIE_API_KEY` is no longer used and may be deleted.

## Installation

Upload every file except the hidden `.github` folder through GitHub's normal uploader. Then create this file directly on GitHub:

`.github/workflows/update-wnba.yml`

Copy its contents from the ZIP into the GitHub editor and commit it.

## Run it

Open **Actions → Update WNBA Sportsbook Points Props → Run workflow**. Leave the date blank for today's Eastern Time slate. A date such as `2026-07-15` may be entered for testing, but The Odds API only returns events/props it currently covers.

## Automation

The workflow runs twice daily to conserve the 500-credit Starter plan. It can also be run manually. Each full refresh uses one events request plus one player-prop request per game on the slate.

## Important reliability note

NBA.com stats endpoints are unofficially accessed through `nba_api` and can occasionally time out or block cloud-hosted requests. The updater retries three times, but no free public endpoint can be guaranteed to remain available forever.
