# TvTalk

A personal soundboard web app. Press a button → random quote from a TV show plays + appears on screen. Multiple shows with a picker; "Random (all shows)" is the default.

## Status (2026-05-27)

- ✅ Scaffolded and working
- ✅ **19 shows scraped, 2,756 quotes total** (~340 MB on disk)
- Auto-trim for "ding-poisoned" legacy 101soundboards boards (see [[04 - Troubleshooting]])
- Per-show config in `shows.yaml`: `text_style`, `case_style`, `exclude_prefix`, `board_url_2` — see [[03 - Workflow]]

## Where things live

| Thing | Location |
|---|---|
| Spec (source of truth) | [[01 - Spec]] |
| Implementation plan | [[02 - Implementation Plan]] |
| Adding a new show | [[03 - Workflow]] |
| Common issues | [[04 - Troubleshooting]] |
| Web app | `index.html` |
| Scraper | `scripts/scrape_soundboard.py` |
| Aggregator | `scripts/build_shows.py` |
| Show registry | `scripts/shows.yaml` |
| Audio + per-show data | `audio/<show-id>/` |
| Aggregated data (generated) | `shows.js` |

## Active shows

```dataview
TABLE status, board_url AS "Board", clip_count, curated_count
FROM "Shows"
WHERE type = "show"
SORT file.name
```

## Quick add

```sh
# 1. Add entry to scripts/shows.yaml (id, name, board_url, theme)
# 2. (Optional) Test for ding-poisoning by downloading one clip first
# 3. Scrape — auto-trims if it's a legacy board (id < 1M)
python3 scripts/scrape_soundboard.py --show <id>
# 4. Rebuild aggregated data
python3 scripts/build_shows.py
# 5. Open in browser
python3 -m http.server 8000  # then visit http://localhost:8000
```

Character curation (editing `audio/<id>/transcripts.txt` then re-running the scraper) is optional. See [[03 - Workflow]] for the full version.
