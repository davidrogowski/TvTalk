# Workflow — Adding a new show

## "The Playbook" (TL;DR)

When Dave says **"run the playbook"** for a show (usually with a 101soundboards link, sometimes two), it means: do this end-to-end, reporting concisely, without stopping for confirmation between steps.

1. **Inspect the board** via the JSON API (`/api/v1/boards/{id}?limit=2000`) to decide config. **hashtag removal** is always automatic. The **1s ding-trim** is automatic for boards matching **ID < 1M AND slug ending in `-soundboard`**. For other boards set `no_trim: true` so the scraper doesn't chop 1s of real audio. ⚠️ **Do NOT** judge poisoning by comparing the downloaded file's duration to the API `sound_duration` — they match even when poisoned (the API reports the *with-ding* length). ⚠️ **The slug rule governs the blunt 1s cut ONLY — it does NOT tell you whether a board is poisoned.** It is not a poison test and never was; see [Poison: three different artifacts](#poison-three-different-artifacts). The content-aware passes now run on *every* scrape regardless of classification, so you no longer have to get this right. The judgment calls are:
   - **Quotes or not?** Read the transcripts. If they're user-supplied *titles/labels* (`"April Ludgate Wine Tasting"`, `"Pickle Rick"`, `"AHHHH!"`) → set `text_style: "title"` (no quote marks). If they're real *spoken dialogue* (`"A strong force of attraction"`) → leave default (quotes). NOTE: this is about content, not board age — Breaking Bad and Peaky Blinders are legacy boards but real captions, so they kept quotes. Most community `-soundboard` boards are title-style; most modern `-YYYY` boards are captions.
   - **ALL-CAPS?** → `case_style: "fix_all_caps"`.
   - **Paren stage-directions / disclaimers?** → `exclude_prefix: "("` or `exclude_prefix: "CAPTIONING MADE POSSIBLE BY"` etc.
   - **Long monologues?** → scrape with `--max-length 50`.
2. **Add to `scripts/shows.yaml`**: `id`, `name`, `board_url`, a `theme` matched to the show's cover-art hue, plus any flags the board needs — `text_style: "title"` (no quote marks for title-style boards), `case_style: "fix_all_caps"`, `exclude_prefix: "..."`, `board_url_2` (merge a second board), `dedup: true` (drop repeated transcripts, e.g. when a board lists the same line twice under different audio files), `no_trim: true` (clean board — see step 1), and `preserve_transcripts: true` (**always set this when you'll clean captions in step 4**, so your labels survive re-scrapes).
3. **Scrape**: `python3 scripts/scrape_soundboard.py --show <id>` (auto-strips hashtags; auto-trims the 1s ding on poisoned `-soundboard` boards). Add `--max-length 50` for long-dialogue prestige dramas.
4. **De-poison — now fully automatic during scrape.** As of 2026-07-13 `scrape_soundboard.py` runs **all three** content-aware passes after download, on **every** board (no longer gated on the slug rule — that gating is what let Happy Gilmore stay poisoned for months). Sanity-check with `python3 scripts/verify_residual_ding.py --show <id>` **and** `python3 scripts/strip_lead_artifact.py --show <id>` (dry run; should plan 0 cuts) **and** `python3 scripts/strip_tts_watermark.py --show <id>` (should report 0). See [Poison: three different artifacts](#poison-three-different-artifacts).
5. **Clean the captions (MANDATORY — do not skip).** Every clip's on-screen text must be a short **1–5 word label**, not the full transcript, **and** must follow the [caption style rules](#caption-style-the-cleanup-methodology) (sentence case, proper nouns preserved, no show-name prefix, no chat abbreviations, no texting shorthand). Edit the quoted label lines in `audio/<id>/transcripts.txt`, then regenerate. This step is the one most easily forgotten; it is not optional.
6. **Rebuild**: `python3 scripts/build_shows.py` — this also **stamps the TV Talk artwork** on any clip still carrying the 101soundboards banner (see [Artwork and tags](#artwork-and-tags-the-shared-file-cover)). Automatic since 2026-07-13; you don't run `tag_audio.py` by hand. Watch its output for the "could not be tagged" warning — that means a **corrupt clip** (a dead button on the site), which you must fix or drop.
7. **Deploy**: `npm_config_cache=/tmp/npm-cache npx --yes wrangler@4.40.0 deploy` (see [[05 - Deployment]]).
8. **Commit + push**: `git add -A && git commit -m "..." && git push` (env-var author identity — see [[05 - Deployment]]).

> **The standing rules that keep getting missed:** (a) **trim the ding** on poisoned `-soundboard` boards (and *only* those — set `no_trim` elsewhere) — the scraper does this **and** the content-aware residual de-ding automatically now, so just verify with `verify_residual_ding.py`; and (b) **clean the captions** into short labels. Both are part of *every* add, not optional polish. The **artwork stamp** used to belong on this list; it is now enforced in code by `build_shows.py`, which is where the other two should end up too.

The numbered sections below are the detailed version of each step.

## 1. Find a 101soundboards board

Browse https://www.101soundboards.com/ and copy the URL. It looks like:

```
https://www.101soundboards.com/boards/1234567-show-name-year
```

The board ID (the number) matters; the slug after it isn't load-bearing for scraping.

**Heads up — ding poisoning**: 101soundboards serves a poisoned MP3 (1-second notification chime at the start) to non-browser scrapers on **legacy community boards** — **board ID < 1,000,000 AND the slug ends in `-soundboard`**. `scrape_soundboard.should_trim_board()` encodes this, and the scraper auto-trims those boards. For other boards set `no_trim: true` in `shows.yaml`.

⚠️ **What this rule is NOT:** it is *not* a test for whether a board is poisoned. It decides one thing only — whether to apply the blunt 1s cut. Boards it calls "clean" can still be poisoned, just differently: Happy Gilmore (`119588-happy-gilmore-1996`) passes as modern and every one of its watermarked clips opens with 2s of spoken "101soundboards dot com". Treat the slug as a hint about the *chime*, nothing more, and let the content-aware passes (which now run on every scrape) decide what is actually there. See [Poison: three different artifacts](#poison-three-different-artifacts).

⚠️ **The other trap:** do **not** verify cleanliness by comparing the downloaded file's duration to the API `sound_duration` — they match even when poisoned, because the API reports the *with-ding* length.

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

## Residual ding cleanup (the de-ding pass)

**This now runs automatically inside `scrape_soundboard.py`** (as of 2026-06) — you normally don't run it by hand. Background: the scraper trims a *fixed* 1.0s to remove the ding, but the ding isn't exactly 1.0s — it's a variable stretch of leading near-silence + a ~repeating-beep chime, often totaling >1.0s, and an MP3 `-c copy` cut only lands on frame boundaries. So a flat 1.0s cut alone leaves a **non-uniform sliver of the chime** ("tail end of a ding"). (Discovered 2026-06; ~1,446 clips across 85 shows had it.) The scraper now follows the 1s cut with the content-aware pass below, so scraped audio is fully de-dinged.

How the de-ding works: the ding is the **only** audio byte-identical across *distinct* clips (different dialogue never shares an identical opening), so each clip's residual = the longest leading PCM prefix it shares with another clip. It trims exactly that (sample-accurate re-encode), looping to convergence. Guards keep it safe: only trims a region that's **loud at t=0** (the chime — not clips merely sharing leading *silence*), caps the amount, and leaves ≥0.6s of audio so genuine **duplicate clips** aren't gutted. A per-clip fallback (`_leading_chime_ms`) also catches a lone chime tail (loud monotonic decay to silence) on **tiny boards** where a stranded clip has no same-alignment partner to match against. Logic lives in `scrape_soundboard.strip_residual_ding`.

Standalone tools (for re-cleaning *previously*-scraped shows, or sweeping the catalog):

```sh
python3 scripts/strip_residual_ding.py --show <id>      # or --all (skips no_trim boards)
python3 scripts/verify_residual_ding.py --show <id>     # sanity check -> "0 clip(s)"
```

If `verify` lists clips after a clean run, they're almost always **within-show duplicate clips** that start with the same loud word/SFX (not ding) — confirm by ear/waveform (a ding is a tonal chime) and leave them, or drop them as dupes.

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

## Poison: three different artifacts

**Added 2026-07-13.** "Poisoned" was treated for months as one thing (the ding) detected by one rule (the slug). Both were wrong. There are **three** artifacts, they are independent, and a board can carry any of them:

| # | Artifact | What it sounds like | Why it hid |
|---|----------|--------------------|------------|
| 1 | **Ding chime** | ~1s notification chime before the line | Handled since day one (`trim_mp3_inplace` + `strip_residual_ding.py`). |
| 2 | **Quiet ding tail** | ~100ms of the chime's *decay*, then dead air | Peak ~564 (≈1.7% of full scale) — far below `verify_residual_ding.py`'s `LOUD=2000` gate, so every "0 clips" report was a false all-clear. Audible as a click + dead air before the line. Found on **2,553 clips**. |
| 3 | **Spoken TTS watermark** | ~2s of *"101soundboards dot com"* read aloud | Not a chime at all, so the ding detectors were structurally blind to it. Worst on Ted Lasso (40/54) and Role Models (44/65). |

### The detection principle that actually works

Do **not** threshold on loudness, and do **not** trust the board slug. Use this instead:

> **Two different quotes cannot legitimately share their opening audio.**

So any lead-in a clip shares with a *different* clip in the same show is an artifact — whatever it sounds like. That single rule catches all three types. `strip_lead_artifact.py` implements it (shared lead-in → cut it, then walk through the dead air behind it to the real speech onset). Safety rails: never cut > 2.6s, never leave a clip < 0.35s.

### The watermark is re-rendered per clip

The site renders the TTS watermark **separately for each clip**, so two watermarked clips are *not* byte-identical (r≈0.91, not 1.0). Worse, two different *renditions* are nearly **uncorrelated with each other** (r≈0.02). Consequences:

- Shared-prefix detection alone misses any clip whose rendition is unique — it has no byte-identical twin. Happy Gilmore's `603_okay_as_long_as_you_re_willing_to_admit_that_now.mp3` hid this way through a full cleanup pass.
- A single reference template is not enough. `strip_tts_watermark.py` keeps **one template per rendition family**; add a new one if a survivor turns up.
- Once you strip the twins, you destroy the evidence that would have exposed the survivor. If you re-hunt after a cleanup, pull the reference audio from **git HEAD**, not the working tree.

### Traps

- **A duplicate clip pair looks exactly like a watermark family** (they share everything). The rails are what stop you butchering them — Arrested Development `006/007 "come on"` and Pulp Fiction `002/003` are duplicate pairs, not poison. **Never call `trim_mp3_inplace` by hand to "just apply" a detected cut; go through the scripts so the rails apply.** Doing it by hand cut a 1.93s Seinfeld clip down to 0.13s.
- **A clean-looking `-YYYY` slug means nothing.** Happy Gilmore is `119588-happy-gilmore-1996` and is watermarked.

## Caption style (the cleanup methodology)

**Added 2026-07-13. Applies to every new show/movie, and is part of playbook step 5.**

Captions are short labels (see below), and on top of that they follow these rules:

1. **Sentence case.** First letter capitalized, the rest lowercase — *except*:
   - **"I"** and its contractions (I'm, I'll, I've, I'd) stay capitalized.
   - **Proper nouns** stay capitalized: character names (Peter, Quagmire, Ron Swanson), real people (Miley Cyrus), places (Atlanta), brands, and titles of works ("Werewolf Bar Mitzvah").
   - **Acronyms** stay uppercase (DEA, FBI, TV).
   - So: `PETER AND QUAGMIRE DANCING` → `Peter and Quagmire dancing`; `Three Keys of Coolness` → `Three keys of coolness`.
2. **No show-name prefix.** The show is already known from context, so the label describes the *line*, not the show. `The Wire this is BS` → `This is bullshit`. `Family Guy bad joke` → `Bad joke`.
3. **No chat abbreviations** — expand to the words actually spoken. `BS` → `bullshit`, `OMG` → `oh my god`, `WTF` → `what the fuck`.
4. **Fix texting shorthand and missing apostrophes**: `u`→`you`, `ur`→`your`, `cuz`→`because`, `dont`→`don't`, `thats`→`that's`, `im`→`I'm`.
5. **Leave dialect alone.** `gonna`, `gotta`, `ain't`, `nah`, `'em`, `y'all` are how the line is actually said — never "correct" them.
6. **Never change profanity or existing censoring.** If a caption has `s**t`, keep the asterisks.
7. **Fix wrong names.** e.g. Simpsons `Looking for Mister Smith` → `Looking for Mr. Smithers`.

At catalog scale this is best done by fanning the captions out to subagents with the show name for context — proper-noun decisions need show knowledge, and a pure regex will happily turn `Nah, I'm good man` into `Nah, i'm good man` and lowercase every character name.

## Curating a board down (music, hashtags, dupes, minimum length)

### 🔴 STANDING RULE: never include music clips (set 2026-07-13)

**Applies to every new show/movie, no exceptions, no need to ask.** Boards are littered with theme songs, score, and musical numbers — they are not quotable lines and they don't belong in the game. Drop any clip whose caption carries a music marker:

```python
MUSIC = re.compile(r"[♪♫🎵🎶]|\[music\]|\(music\)|addic7ed|sync\s*&\s*correction", re.I)
```

The `addic7ed` / `sync & correction` patterns catch subtitle-ripper credit lines, which are the same kind of junk (a clip captioned `Sync & correction by f1nc0 ~ Addic7ed.com ~ [music]` is not a quote). Also drop fansub credits like `Original Sub By ViKramJS` when you spot them, and named theme clips (`"Theme music"`, `"Office Theme"`).

Music clips dropped so far: F is for Family 8, Jojo Rabbit 11, Barbie 13.

### The other filters

Some boards need more. The Friends rebuild (2026-07-13) used all three:

- **Hashtag filter.** On some boards, clips that aren't actually from the show are mixed in; the real ones carry hashtags (`... #friends #joey`). ⚠️ **The scraper strips hashtags before you ever see them** (`fetch_sounds`), so you cannot filter on `transcripts.txt` — you must read the **raw API** `sound_transcript` and join back by `sound_file_url`. On the Friends board this dropped 120 of 418 clips.
- **Dupes.** Set `dedup_transcripts: true` (board lists the same line under several mp3 urls). Dropped 17 more.
- **Minimum duration — measure it AFTER de-poisoning.** A clip padded with a ding tail and ~0.9s of dead air measures well over the bar while carrying under 3s of actual audio. Filtering on raw durations keeps clips that don't really clear it. (Silicon Valley was cut at 3s on padded durations; re-measuring after the strip dropped 15 more clips.)

To curate before download, **pre-generate `transcripts.txt`** with the scraper's own `fetch_sounds`/`safe_filename` (so filenames match what the scraper will compute — the index is its position in the *full, deduped* board enumeration), then run a normal curate-scrape: with `preserve_transcripts: true` and a transcripts file present, the scraper treats it as the authoritative set and only downloads what's listed.

## Captions are short labels, not full quotes (the labeling pass)

**This is playbook step 4 and is MANDATORY for every add** (it is not a one-time historical pass). Every clip's on-screen text is a **short 1-5 word label**, not the full transcript — the *audio* is the payload, the button is just a scannable handle (think Borat: "Great success", "My name-a Borat"). All shows use `text_style: "title"` (no quote marks).

For the labeling work itself, **dispatching one agent per show in parallel** (each rewriting only the quoted lines in that show's `audio/<id>/transcripts.txt`, leaving `.mp3`/`CHARACTER:`/`REPEAT:` lines and entry order untouched) is the fast path for a batch; split very large files (e.g. 300+ clips) into chunks so a single agent's write doesn't blow up. Always set `preserve_transcripts: true` first so the labels survive re-scrapes, then regenerate `quotes.js` from the edited file.

**The rule for writing a label:**
- Lines **≤10 words** that are already clean → **keep verbatim** (preserves iconic phrasing like "Say my name", "You're God damn right", "I am the one who knocks").
- Lines **>10 words** → **summarize to ~1-5 words** capturing the gist or the punchline.
- **Messy/garbled** auto-captions → rewrite into a clean short label (this doubles as the fix for bad captions).
- **SFX-only / music / network-promo** clips → label by what's happening (e.g. "Door opens", "Mariachi music", "FX promo: Legion"), or flag for dropping.

**How the labels persist (`preserve_transcripts` + the "curate" rule):** the scraper normally re-fetches transcripts from the API every run, which would wipe hand-written labels. So labeled shows set `preserve_transcripts: true`. Once a curated `transcripts.txt` exists, it becomes the **authoritative clip set**: on re-run the scraper includes **exactly** the clips listed there (by filename, with your label text) and **skips the length filter entirely** — so short labels are never dropped, and clips you removed from the file stay gone. (On the very first scrape, before the file exists, it behaves normally: download all, apply the length filter, write the raw transcripts for you to edit.)

**To (re)label a show:**
1. `text_style: "title"` + `preserve_transcripts: true` in its `shows.yaml` entry.
2. Edit the quoted text lines in `audio/<id>/transcripts.txt` — labels only; **leave the `.mp3` filename lines untouched** (filenames stay keyed to the original API text so they keep matching the audio).
3. `python3 scripts/scrape_soundboard.py --show <id>` to regenerate `quotes.js` from your labels (no re-download).

**Gotcha — board drift:** re-running fetches the live board to map filenames. If a board has changed since the audio was downloaded (mostly an issue for **modern `-YYYY` boards**, which get updated), the recomputed filenames won't match your `transcripts.txt` and clips silently drop. Legacy `-soundboard` boards are archival and stable. If a re-run's "Total kept" is suddenly low, regenerate `quotes.js` directly from `transcripts.txt` instead of via the scraper.

## Weighting a clip & adding local (non-board) clips

Two durable curation features, both driven from `audio/<id>/transcripts.txt` so they **survive re-scrapes** (they live in the curated file, not in the generated `quotes.js`):

**Play a clip more often — `REPEAT: N`.** Add a `REPEAT:` line to any entry. The scraper emits the clip `N` times into `quotes.js`, so it lands in the random pool `N` times and plays ~`N`× as often. Omit the line (or `REPEAT: 1`) for normal weight.

```
015_who_dis_n_on_dat_nag.mp3
  "Who dis n**** on dat nag?"
  CHARACTER:
  REPEAT: 2
```

**Add a clip that isn't on any board (a local MP3 you have).**
1. Drop the file into `audio/<id>/` (any filename, e.g. `like_a_baby_miss_mammys_titty.mp3`).
2. Add a normal block for it in `transcripts.txt` (filename / label / `CHARACTER:` / optional `REPEAT:`).
3. Re-run `python3 scripts/scrape_soundboard.py --show <id>`.

On re-run (curate mode) the scraper **preserves** any clip listed in `transcripts.txt` whose MP3 exists on disk but isn't produced by a board — you'll see `Preserving N hand-added clip(s) not on any board.` Stale entries whose file is missing are skipped. (Pure helpers for both features are covered by `scripts/test_scrape_soundboard.py`.)

**These one-offs never impact main scrapes.** Both features are scoped entirely to a single show's own `audio/<id>/` directory and `transcripts.txt`:
- **No cross-show effect.** Scraping or adding *another* show (`--show <other>`, a fresh board, or a full `--all` run) reads only that show's files. A one-off clip or `REPEAT:` in one show is invisible to every other show.
- **Idempotent on the owning show.** Re-running the scraper on the show that *has* the one-offs reproduces the exact same `quotes.js` every time — board clips and hand-added clips alike — with no duplication or drift. (Verified: re-scraping `django-unchained` with 2 weighted board clips + 2 local clips regenerates the identical 174-entry `quotes.js`.)
- **No fragile board-matching for local clips.** Hand-added clips are kept by *file existence*, not by matching a board, so the board-drift gotcha above can't drop them.

In short: one-offs live with their show, survive that show's re-scrapes, and are inert to everything else.

## 7. Rebuild the aggregated data

```sh
python3 scripts/build_shows.py
```

Writes `shows.js` at the project root with every show's data combined (including the `text_style` field that controls quote-wrapping in the UI).

## Artwork and tags (the shared-file cover)

**This runs automatically inside `build_shows.py`** (since 2026-07-13) — you don't normally run it by hand.

Clips arrive from soundboard.com carrying a **101soundboards.com banner as their embedded cover art**, and the string `101soundboards.com` in every ID3 field (artist, comment, copyright, lyrics, …). That art is the thumbnail a phone shows when someone shares a clip out of the site — it was the photo on every clip we shipped until 2026-07-13. `tag_audio.py` swaps in `scripts/cover_tvtalk.jpg` (the red TV Talk button, 400×400) and retags: **title** = the clip's cleaned caption, **artist** = the show, **album** = TV Talk, **comment** = tvtalk.fun.

**This is a *different* poison from the ding/watermark.** Those live in the audio and are stripped by the scraper (see [Poison: three different artifacts](#poison-three-different-artifacts)). This one lives in the metadata. `tag_audio.py` stream-copies the audio (`-c:a copy`), so the sound is byte-identical and it can **never** fix or harm a ding — the two passes don't overlap.

Why it hangs off `build_shows.py` rather than the scraper: each clip's title is its **cleaned caption**, which only exists once `shows.js` is rebuilt. Hooking it there also means a re-scrape can't quietly reintroduce the banner — the next build takes it back out. The check is a cheap byte-scan of each file's ID3 header (no ffprobe per clip), so a clean rebuild costs ~3s and stamps nothing.

Manual use, for a single show or to check:

```sh
python3 scripts/tag_audio.py <id>            # force a re-stamp
python3 scripts/tag_audio.py --verify <id>   # check, write nothing (omit <id> for all)
```

- `--verify` fails on a clip with no art, wrong-size art, a missing audio stream, or any surviving `101soundboards` tag.
- Both `build_shows.py` and `--verify` surface **corrupt clips** — a file ffmpeg can't read is a dead button on the live site. Three such clips (1.5 KB stubs, no decodable frames) were found and dropped this way on 2026-07-13. Fix or drop them; to drop, delete the entry from the show's curated `transcripts.txt` (not `quotes.js`) so a re-scrape can't resurrect it, then re-run the scraper and rebuild.
- Adds ~14 KB per clip. To regenerate the cover art itself from `icon-tvtalk.svg`: `node scripts/render_cover.mjs` (needs network — the SVG pulls the Nunito webfont).

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
