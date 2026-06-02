# Clock The Quote — Design Spec

> Captured from the brainstorming session on 2026-06-02. Design only — no code yet.
> Companion notes: `00 - Overview.md`, `02 - Decisions & Open Questions.md`.

## One-line concept

A daily, Pinpoint-style audio quote-guessing game on top of the TvTalk catalog:
hear a clip, name the show/movie, fewer clues = better score, share a spoiler-free
result strip.

## Architecture

- New page **`clock-the-quote.html`** at the repo root, sibling to `index.html`.
  (Name not final — see open questions.)
- Loads the **same** `shows.js` and the **same** `audio/` clips. **Zero data
  duplication.** Adding a show via the existing playbook feeds the game too.
- **Pure client-side, no build step, no backend.** Deploys identically through
  wrangler (just another static file).
- **The soundboard (`index.html`) is never touched.**
- A small link between the two pages (soundboard ⇄ game) for discoverability.

## The good-clips pool

Not every clip is fair game material (muddy audio, unrecognizable, etc.), so the
game draws from a **curated pool**, not all ~6,400 clips.

- A clip becomes game-eligible via a marker in `transcripts.txt` — proposed
  **`GAME:`** prefix on blessed lines, round-tripped by the scraper exactly like
  the existing `REPEAT:` / character curation.
- That carries a `"game": true` flag through into each quote object in `shows.js`.
- `clock-the-quote.html` builds its pool by filtering all quotes where
  `game === true`.
- **Why this way:** reuses the existing transcript-curation habit (one workflow,
  not a new file) and keeps one-offs isolated, consistent with how curation is
  already kept from leaking into the main scrapes.

## The daily puzzle

- **One mystery title per day**, chosen **deterministically**: a day index derived
  from a fixed start date seeds a PRNG that picks one clip from the *sorted* pool.
  Everyone gets the same clip.
- **Rollover at local midnight**, keyed to the calendar date, so the shared `#N`
  lines up with friends.
- **5 guesses.** Each guess is typed into an **autocomplete box that only accepts
  one of the 64 real titles** (Pinpoint-style — no free-text misfires).

### Clue ladder (audio-first, words revealed gradually)

Revealed as the player guesses wrong / skips:

1. **Audio only** — hear it, name it. A clue-1 solve is the flex.
2. Audio + **~⅓ of the quote words**
3. Audio + **~⅔ of the quote words**
4. Audio + **full quote text**
5. **Title hint** — show-vs-movie + character (where present)

Then: solve, or exhaust 5 guesses → **reveal screen** (title, clip still playable,
full quote, result strip).

- **Reveals scale by *fraction* of the caption, not fixed word counts**, because
  many captions are very short ("Stabs you in the back" = 4 words). A fixed
  "1–2 then 3–5 words" ladder would dump the whole line by clue 2; fractional
  reveals degrade gracefully (min 1 word per step).

## Scoring & sharing

- **Score = the clue you solved on** (1 best → 5), or ✗ if missed.
- **Spoiler-free share string**, e.g. solved on clue 3:
  `Clock The Quote #42 ⬛⬛🟩`
  One-tap **Copy results** button. No title or quote text leaks.

## Stats (localStorage)

- Current streak, max streak, games played, win %, and a guess-distribution
  histogram (how often solved on 1 / 2 / 3 / 4 / 5 / fail).
- **Today's progress is persisted** — a refresh resumes mid-puzzle; once finished
  you see your result, not a replay. One-and-done, like Pinpoint.

## Title-hint data (clue 5)

- **v1 uses existing data:** `type` (show/movie) + `character` where present.
- **Optional follow-up (not v1):** add a one-word `genre` and/or `year` per title
  in `shows.yaml` (64 entries) for a richer clue 5. Skippable.

## Known limitation (carried forward)

- The clip's `audio/<show>/…` path **names the title in devtools**. For
  friends-casual play we **accept this in v1**. If it ever matters, the fix is
  opaque/renamed paths for the daily clip. Logged, not solved.

## Testing

- Extract the deterministic core into **pure, unit-tested functions**:
  - `dayIndex(date)` — calendar-date → integer day index
  - `seededPick(pool, dayIndex)` — deterministic daily clip
  - `revealFraction(text, stage)` — fractional word reveal (handles short captions)
  - `resultToShareString(result)` — the emoji strip
  - the stats reducer (streak/histogram update)
- **No framework** — a tiny no-build test runner, in keeping with the project.
- Manual/visual checks via **headless screenshots** (refresh-in-place workflow).

## Build-pipeline changes (additive, safe — do NOT disturb the soundboard)

- `scripts/scrape_soundboard.py`: recognize the `GAME:` marker on transcript
  round-trip and set the per-clip `game` flag.
- `scripts/build_shows.py`: carry the `game` flag through into `shows.js`.

## Out of scope for v1 (explicitly deferred)

- **Party mode** (same-screen host/guess) — architect daily so this can bolt on
  later, but don't build it now.
- **Live multiplayer rooms** — would require a backend (CF Workers / Durable
  Objects); not happening in v1.
- **Unlimited practice mode** — daily-only on purpose, for the come-back-daily pull.
- Genre/year hint data, opaque audio paths — see above.
