# WNBA Prop Lab — Points Only

This version displays **only WNBA Points props that exist on the current PrizePicks board**. It does not generate random players.

## Daily flow

1. `scripts/import_prizepicks.py` reads the live WNBA board and keeps only standard `Points` projections.
2. `scripts/update_stats.py` matches each board player to that day's WNBA game.
3. Players not on the Points board are excluded.
4. Players whose teams do not play on the selected date are excluded.
5. The site displays Last 10, Last 5, and head-to-head results against the exact Points line.

## Required GitHub secret

Add this in **Settings → Secrets and variables → Actions**:

- `BALLDONTLIE_API_KEY`

The workflow attempts to discover the PrizePicks WNBA league automatically. If discovery fails, add:

- `PRIZEPICKS_WNBA_LEAGUE_ID`

## Important

PrizePicks does not publish a supported public developer API for this use. Its website JSON endpoint can change or block automated requests. The importer preserves the previous `data/lines.json` when the request fails. You can also manually place the current Points board in `data/lines.json` and run the workflow.

Manual format:

```json
{
  "props": [
    {"player":"A'ja Wilson","market":"pts","market_label":"Points","line":26.5}
  ]
}
```
