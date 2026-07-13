# WNBA Prop Lab — Fully Automatic Points Board

This GitHub Pages project automatically displays **only standard WNBA Points props currently on the PrizePicks board**.

## Automatic flow

Every hour, `.github/workflows/update-wnba.yml`:

1. Reads the current PrizePicks WNBA board.
2. Keeps only standard **Points** projections.
3. Loads today's WNBA schedule from ESPN's public sports data.
4. Matches each board player to the correct team and game.
5. Pulls each player's season game log.
6. Builds Last 5, Last 10, and head-to-head results.
7. Writes `data/lines.json` and `data/props.json`.
8. Commits the updated data, which refreshes GitHub Pages.

No BALLDONTLIE key is required.

## First run

After uploading every file and folder:

1. Open the repository's **Actions** tab.
2. Select **Update live WNBA Points props**.
3. Click **Run workflow**.
4. Leave the optional date blank to use today's Eastern Time date.
5. After the green check, open `data/props.json` to confirm that live props were written.

The workflow then runs hourly by itself.

## Repository structure

```text
.github/workflows/update-wnba.yml
scripts/import_prizepicks.py
scripts/update_stats.py
data/lines.json
data/props.json
index.html
app.js
styles.css
```

## Optional secret

Normally the importer discovers the WNBA league automatically. If PrizePicks league discovery changes, add this repository Actions secret:

```text
PRIZEPICKS_WNBA_LEAGUE_ID
```

## Failure protection

PrizePicks does not provide a supported public developer API for this project. If its public web endpoint temporarily rejects an automated request, the workflow preserves the last successful data instead of erasing the board. The next hourly run tries again.
