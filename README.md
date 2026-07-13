# WNBA Prop Lab

A GitHub Pages-ready WNBA player prop research dashboard. Click any row to open an Outlier-style game-log modal with Last 10, Last 5, and H2H tabs. Bars are green when the result is over the line, red when under, and gold on a push.

## Fastest setup
1. Create a new GitHub repository.
2. Upload every file and folder from this project.
3. Commit to `main`.
4. Open **Settings → Pages** and choose **GitHub Actions** as the source.
5. The included workflow deploys the site.

## Put in today's PrizePicks lines
Edit `data/props.json`. Each prop needs the player, team, opponent, market, line, projection, last 10 game values, and H2H values. The site recalculates averages and over rates automatically.

## Automatic stats updater
`scripts/update_stats.py` can pull WNBA player game logs from BALLDONTLIE while leaving your manually entered prop lines in place.

1. Create a BALLDONTLIE API key.
2. In GitHub, open **Settings → Secrets and variables → Actions**.
3. Add a repository secret named `BALLDONTLIE_API_KEY`.
4. In `data/lines.json`, enter today's player names, lines, opponents, and markets.
5. Run the **Update WNBA data** workflow manually or wait for its daily run.

PrizePicks does not provide a public supported API in this project, so lines are intentionally entered manually rather than scraped.
