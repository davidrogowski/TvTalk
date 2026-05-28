# Workflow — Adding a new show

## "The Playbook" (TL;DR)

When Dave says **"run the playbook"** for a show (usually with a 101soundboards link, sometimes two), it means: do this end-to-end, reporting concisely, without stopping for confirmation between steps.

1. **Inspect the board** via the JSON API (`/api/v1/boards/{id}?limit=2000`) to decide config. Two of the three "usual" behaviors are automatic and need no decision: **hashtag removal** (always) and the **1s ding-trim** (auto, when board ID < 1M). The judgment calls are:
   - **Quotes or not?** Read the transcripts. If they're user-supplied *titles/labels* (`"April Ludgate Wine Tasting"`, `"Pickle Rick"`, `"AHHHH!"`) → set `text_style: "title"` (no quote marks). If they're real *spoken dialogue* (`"A strong force of attraction"`) → leave default (quotes). NOTE: this is about content, not board age — Breaking Bad and Peaky Blinders are legacy boards but real captions, so they kept quotes. Most community `-soundboard` boards are title-style; most modern `-YYYY` boards are captions.
   - **ALL-CAPS?** → `case_style: "fix_all_caps"`.
   - **Paren stage-directions / disclaimers?** → `exclude_prefix: "("` or `exclude_prefix: "CAPTIONING MADE POSSIBLE BY"` etc.
   - **Long monologues?** → scrape with `--max-length 50`.
   - (Optionally pull one clip to a temp file so Dave can confirm the ding, but auto-trim handles it regardless.)
2. **Add to `scripts/shows.yaml`**: `id`, `name`, `board_url`, a `theme` matched to the show's cover-art hue, plus any flags the board needs — `text_style: "title"` (no quote marks for title-style boards), `case_style: "fix_all_caps"`, `exclude_prefix: "..."`, `board_url_2` (merge a second board), `dedup: true` (drop repeated transcripts, e.g. when a board lists the same line twice under different audio files).
3. **Scrape**: `python3 scripts/scrape_soundboard.py --show <id>` (auto-strips hashtags; auto-trims the 1s ding if board ID < 1M). Add `--max-length 50` for long-dialogue prestige dramas.
4. **Rebuild**: `python3 scripts/build_shows.py`.
5. **Deploy**: `npm_config_cache=/tmp/npm-cache npx wrangler deploy` (see [[05 - Deployment]]).
6. **Commit + push**: `git add -A && git commit -m "..." && git push` (env-var author identity — see [[05 - Deployment]]).

The numbered sections below are the detailed version of each step.

## 1. Find a 101soundboards board

Browse https://www.101soundboards.com/ and copy the URL. It looks like:

```
https://www.101soundboards.com/boards/1234567-show-name-year
```

The board ID (the number) matters; the slug after it isn't load-bearing for scraping.

**Heads up — ding poisoning**: 101soundboards serves a poisoned MP3 (1-second notification chime at the start) to non-browser scrapers on **legacy community boards** (board ID < 1,000,000, slug ends in `-soundboard`). Modern official boards (board ID >= 1,000,000, slug ends in a year like `-2019`) are clean.

The scraper auto-detects this from the URL and trims the ding. But if you want to confirm before committing to a full scrape, do a quick poison test (step 2 below).

## 2. (Optional) Poison test — one clip

Download just the first clip from the board to your project root and play it:

```python
python3 -c "
import urllib.request, ssl, certifi, json
ctx = ssl.create_default_context(cafile=certifi.where())
BOARD_ID = '<board_id>'
req = urllib.request.Request(f'https://www.101soundboards.com/api/v1/boards/{BOARD_ID}?limit=2000',
                              headers={'User-Agent': 'Mozilla/5.0 (personal soundboard project)'})
with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
    sounds = json.loads(r.read().decode('utf-8'))['data']['sounds']
url = sounds[0]['sound_file_url']
if url.startswith('/'): url = 'https://www.101soundboards.com' + url
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (personal soundboard project)'})
with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open('poison_test.mp3', 'wb') as f:
    f.write(r.read())
print('saved poison_test.mp3 — play it')
"
```

If you hear a notification ding at the start, the board is poisoned. The auto-trim will fix it during real scraping.

## 3. Add the show to `scripts/shows.yaml`

Minimum:

```yaml
shows:
  - id: short-slug                # used as folder name + show id in JS
    name: "Show Name"
    board_url: "https://www.101soundboards.com/boards/..."
    status: pending
    theme:
      primary: "#hex"             # button color, main accents
      accent:  "#hex"             # secondary accent
      bg:      "#hex"             # darkest background
```

Optional per-show fields (add any that apply):

```yaml
    board_url_2: "https://..."           # second board to merge into the same show
    text_style: "title"                  # if transcripts are user-titles, not real captions — no quote marks in UI
    case_style: "fix_all_caps"           # if board has ALL-CAPS legacy captioning, normalize to sentence case
    exclude_prefix: "CAPTIONING MADE"    # drop clips whose transcripts start with this prefix (case-insensitive)
    dedup: true                          # drop clips whose transcript repeats one already kept (same line, different audio file)
    preserve_transcripts: true           # keep hand-edited transcript text in transcripts.txt across re-scrapes (for boards with bad/smushed captions)
    censor_nword: true                   # blur the n-word in captions: keep first letter, star the rest (e.g. n*****)
    min_length: 6                        # per-show word-count floor (overrides the --min-length default of 1)
    max_length: 9999                     # per-show word-count ceiling (overrides the --max-length default of 25; use a big number to keep everything)
    min_length_2: 6                      # board_url_2 only: its own floor (falls back to min_length)
    max_length_2: 9999                   # board_url_2 only: its own ceiling (falls back to max_length)
```

**Per-board length filters (`min_length`/`max_length` + `_2`):** length limits can live in `shows.yaml` so they survive re-scrapes (no need to remember a CLI flag). `min_length`/`max_length` apply to `board_url`; `min_length_2`/`max_length_2` apply to `board_url_2` and fall back to the board-1 values. This lets a merge keep *all* of one board while trimming short clips from another (e.g. Django: board 1 keeps everything, board 2 omits captions of ≤5 words). CLI `--min-length`/`--max-length` still set the default when the yaml fields are absent.

**Fixing bad captions (`preserve_transcripts`):** the scraper normally re-fetches every transcript from the API on each run, so hand-edits to `transcripts.txt` get overwritten. If a board's captions are garbage (e.g. words run together with no spaces — `"Canisayfirst"`), set `preserve_transcripts: true`, then: scrape once (downloads audio + writes the bad transcripts), hand-fix the quoted transcript lines in `audio/<id>/transcripts.txt` (leave the `.mp3` filename lines untouched — filenames stay keyed to the original API text), then re-run the scraper to regenerate `quotes.js` from your corrected text. Your edits now survive future re-scrapes.

**Merging a legacy + modern board:** the 1s ding-trim is applied **per board** — only clips that came from a legacy board (ID < 1M) are trimmed. Clips from a modern board in the same merge are left intact, so you can safely merge e.g. a legacy `-soundboard` with a clean `-YYYY` board without chopping real audio off the modern clips.

Theme colors: pick anything that fits the show's vibe. The page interpolates a glow color from `primary` + `bg`, so you don't need to set that separately.

## 4. Scrape

```sh
python3 scripts/scrape_soundboard.py --show <id>
```

What this does, in order:

1. Calls 101soundboards' JSON API at `/api/v1/boards/{board_id}` (the API returns all clips regardless of pagination).
2. For each clip: strips hashtags off the transcript, applies `case_style`/`exclude_prefix` if configured, drops clips outside the length filter.
3. Downloads each MP3 with a 1.5s polite delay between requests.
4. **For each legacy board (auto-detected)**: trims 1.0s off the front of newly-downloaded MP3s from that board with ffmpeg (`-c copy`, no re-encode). In a legacy + modern merge, only the legacy board's clips are trimmed; modern-board clips are left intact. Already-on-disk files are skipped.
5. Writes `audio/<id>/transcripts.txt` and `audio/<id>/quotes.js`.

Flags:
- `--min-length N` / `--max-length N` — word-count filter on transcripts. Default `1`–`25`.
- `--all` — re-scrape every show in `shows.yaml`, even ones already done.

For long-monologue shows (prestige dramas) bump `--max-length 50` to keep more clips.

## 5. (Optional) Curate

Open `audio/<id>/transcripts.txt`:

```
001_oi_cunt.mp3
  "Oi, cunt."
  CHARACTER:

002_diabolical.mp3
  "Diabolical."
  CHARACTER:
```

Fill in `CHARACTER:` lines for the ones you want. Delete entire blocks for clips you want to drop. Save.

## 6. (Optional) Re-run the scraper

```sh
python3 scripts/scrape_soundboard.py --show <id>
```

Reads your edited `transcripts.txt`, preserves the `CHARACTER:` values, regenerates `quotes.js` with character names baked in. Already-downloaded MP3s are not re-downloaded; already-trimmed files are not re-trimmed.

## 7. Rebuild the aggregated data

```sh
python3 scripts/build_shows.py
```

Writes `shows.js` at the project root with every show's data combined (including the `text_style` field that controls quote-wrapping in the UI).

## 8. Open the app

Safari/Firefox:
```sh
open index.html
```

Chrome (blocks `file://` script loads):
```sh
python3 -m http.server 8000
# open http://localhost:8000
```

Hard-refresh (Cmd+Shift+R) if you're swapping MP3 contents while the server has been running — Chrome aggressively caches audio.
