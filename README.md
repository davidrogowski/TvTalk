# TvTalk

A personal soundboard web app. Click a button, hear a random quote from a TV show, see the text. Supports multiple shows with a picker and a "Random (all shows)" mode.

Full docs are in the Obsidian notes alongside this file — see `00 - Project Overview.md`.

## Add a show in 5 commands

```sh
# 1. Edit scripts/shows.yaml — add an entry with id, name, board_url, theme.
$EDITOR scripts/shows.yaml

# 2. Scrape the board.
python3 scripts/scrape_soundboard.py --show <id>

# 3. Curate: open the generated transcripts file and fill in CHARACTER: lines.
$EDITOR audio/<id>/transcripts.txt

# 4. Re-run the scraper to bake character names into quotes.js (no re-downloads).
python3 scripts/scrape_soundboard.py --show <id>

# 5. Rebuild shows.js and open the app.
python3 scripts/build_shows.py && open index.html
```

## Running

Double-click `index.html`. Works in Safari and Firefox over `file://`.

Chrome blocks loading `shows.js` from `file://`. Use a local server:

```sh
python3 -m http.server 8000
# then open http://localhost:8000
```

## Dependencies

- Python 3.9+. Stdlib only is required.
- PyYAML is optional and gives you a real YAML parser if you ever extend `shows.yaml` beyond the simple shape it ships with: `pip install pyyaml`.

## Project layout

See `01 - Spec.md` for the full project layout and design decisions.
