# Workflow — Adding a new show

## "The Playbook" (TL;DR)

When Dave says **"run the playbook"** for a show (usually with a 101soundboards link, sometimes two), it means: do this end-to-end, reporting concisely, without stopping for confirmation between steps.

1. **Inspect the board** via the JSON API (`/api/v1/boards/{id}?limit=2000`) to decide config. Two of the three "usual" behaviors are automatic and need no decision: **hashtag removal** (always) and the **1s ding-trim** (auto, when board ID < 1M). The judgment calls are:
   - **Quotes or not?** Read the transcripts. If they're user-supplied *titles/labels* (`"April Ludgate Wine Tasting"`, `"Pickle Rick"`, `"AHHHH!"`) → set `text_style: "title"` (no quote marks). If they're real *spoken dialogue* (`"A strong force of attraction"`) → leave default (quotes). NOTE: this is about content, not board age — Breaking Bad and Peaky Blinders are legacy boards but real captions, so they kept quotes. Most community `-soundboard` boards are title-style; most modern `-YYYY` boards are captions.
   - **ALL-CAPS?** → `case_style: "fix_all_caps"`.
   - **Paren stage-directions / disclaimers?** → `exclude_prefix: "("` or `exclude_prefix: "CAPTIONING MADE POSSIBLE BY"` etc.
   - **Long monologues?** → scrape with `--max-length 50`.
   - (Optionally pull one clip to a temp file so Dave can confirm the ding, but auto-trim handles it regardless.)
2. **Add to `scripts/shows.yaml`**: `id`, `name`, `board_url`, a `theme` matched to the show's cover-art hue, plus any flags the board needs — `text_style: "title"` (no quote marks for title-style boards), `case_style: "fix_all_caps"`, `exclude_prefix: "..."`, `board_url_2` (merge a second board).
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
```

Theme colors: pick anything that fits the show's vibe. The page interpolates a glow color from `primary` + `bg`, so you don't need to set that separately.

## 4. Scrape

```sh
python3 scripts/scrape_soundboard.py --show <id>
```

What this does, in order:

1. Calls 101soundboards' JSON API at `/api/v1/boards/{board_id}` (the API returns all clips regardless of pagination).
2. For each clip: strips hashtags off the transcript, applies `case_style`/`exclude_prefix` if configured, drops clips outside the length filter.
3. Downloads each MP3 with a 1.5s polite delay between requests.
4. **If the board is legacy (auto-detected)**: trims 1.0s off the front of every newly-downloaded MP3 with ffmpeg (`-c copy`, no re-encode). Already-on-disk files are skipped.
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
