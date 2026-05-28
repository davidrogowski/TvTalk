# Troubleshooting

## "Audio plays but starts with a notification-ding sound"

101soundboards serves a poisoned MP3 (a 1-second notification chime prepended) to non-browser User-Agents on **legacy community boards**. Modern official boards are unaffected.

**Detection rule** (works in practice for all observed boards):
- Board ID < 1,000,000 (5-6 digit IDs, slug ends in `-soundboard`) → **legacy / poisoned**
- Board ID >= 1,000,000 (7-digit IDs, slug ends in a year like `-2019`) → **clean**

**Fix**: the scraper auto-detects legacy boards from the URL and trims 1.0s off the front of every newly-downloaded MP3 using ffmpeg (`-c copy`, no re-encode). If you ever scrape a board that needs trimming but isn't auto-detected, the manual one-liner is:

```sh
for f in audio/<show>/*.mp3; do
  tmp="${f%.mp3}.trimming.mp3"
  ffmpeg -y -ss 1.0 -i "$f" -c copy "$tmp" 2>/dev/null && mv "$tmp" "$f"
done
```

Existing already-trimmed files are skipped on re-scrape — only newly-downloaded files get trimmed.

## "SSL: CERTIFICATE_VERIFY_FAILED"

Homebrew Python on macOS often points at an empty openssl CA bundle (`/opt/homebrew/etc/openssl@3/cert.pem` is missing or empty). The scraper uses `certifi`'s bundle explicitly to dodge this. If `import certifi` fails, install it:

```sh
pip3 install certifi
```

## "Page loads but no shows in the picker"

`shows.js` is missing, empty, or didn't get rebuilt after a scrape.
Run `python3 scripts/build_shows.py`.

If you're in Chrome and the file *exists*, Chrome blocks the `<script src>` load over `file://`. Use a local server:

```sh
python3 -m http.server 8000
```

## "Button does nothing when I click"

Browsers gate autoplay behind a user gesture; the button click satisfies that, so this is rarely the audio. More likely: `audioUrl` is `null` (transcript was kept but the MP3 download failed), or the path is wrong. Check the browser console.

## "Scraper finds 0 clips"

The scraper uses 101soundboards' JSON API at `/api/v1/boards/{board_id}` (discovered from their Vue/Vite bundle). If they ever rename it or change the response shape, this is the failure mode. Confirm by:

```sh
curl -s 'https://www.101soundboards.com/api/v1/boards/<board_id>?limit=2000' | python3 -m json.tool | head
```

Should return `{"success": true, "data": {"sounds": [...], "sounds_count": N}}`. If it does but the scraper still gets 0, check `fetch_sounds()` in `scripts/scrape_soundboard.py`.

## "Hit the 25-word length filter, lost long monologues"

The default `--max-length` is 25 words. For prestige-drama shows with long scenes (Narcos, Succession, Ozark, Atlanta, etc.) bump it:

```sh
python3 scripts/scrape_soundboard.py --show <id> --max-length 50
```

`--max-length 100` keeps essentially everything. Already-downloaded MP3s aren't re-downloaded on re-scrape, so increasing the cap is cheap.

## "Too many short clips that sound like blips"

Some boards (especially title-style community boards like Family Guy, Sopranos, The Wire) have lots of sub-2-second clips. After the 1s auto-trim, some end up sub-second. If they bother you, either:

- Hand-delete the offenders from `audio/<show>/transcripts.txt` and re-run the scraper (their entries get pruned from `quotes.js`).
- Bump `--min-length` on the next scrape (won't help retroactively without deleting the files first).

## "My CHARACTER: edits disappeared"

You ran the scraper from a different working directory and it wrote to a different `transcripts.txt`. The scraper computes paths relative to its own location (`<repo>/audio/<id>/`), so running it from anywhere with `python3 /path/to/scripts/scrape_soundboard.py --show ...` is safe, but the ad-hoc mode (passing a board URL directly) writes to whatever output dir you pass — don't mix the two for the same show.

## "PyYAML not installed"

You don't need it. The scraper falls back to a small parser tailored to the shape of `shows.yaml` (supports the standard fields including `text_style`, `case_style`, `exclude_prefix`, `board_url_2`). Install it (`pip install pyyaml`) only if you want to add nested lists or non-standard YAML structures.

## "Audio plays but feels muffled / inconsistent"

Source-board clips vary in encoding. Not fixable from this app — re-rip from the show if you care.
