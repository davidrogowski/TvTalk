# Clock The Quote — Design Spec

> Originally captured 2026-06-02 in brainstorming; **updated to as-built once the
> first version shipped live.** Sections marked _(PLANNED)_ are the longer-term
> design, not yet built. Companion notes: `00 - Overview.md`,
> `02 - Decisions & Open Questions.md`.

## One-line concept

A daily, Pinpoint-style audio quote-guessing game on top of the TvTalk catalog:
hear a clip, name the show/movie, fewer clues = better score, share a spoiler-free
result strip.

## Status — LIVE in beta (2026-06-02)

Shipped as **`clockthequote.html`** at the repo root, live at
**https://tvtalk.fun/clockthequote**, deployed by the same Cloudflare Worker as
the soundboard (which has a cross-link to it; the game links back). The throwaway
prototype that drove the iteration is `Clock The Quote/prototype.html`.

**Built and live:** the 5-clue audio ladder (below), guess-by-autocomplete over
all 64 titles, scoring, the spoiler-free share (native share sheet on mobile /
clipboard on desktop), the "Marquee" visual theme, and a shuffle-bag of clips.
**Not yet built:** the real daily-of-1 selection, the curated `GAME:` pool, and
persisted stats — the live beta runs an **endless shuffle of a few hard-coded
clips** (currently a 5-movie test set: Anchorman, Caddyshack, Office Space, The
Other Guys, Tropic Thunder). Clips are picked to be **≥ 8s** so the mid-clip
snippet has audio on both sides (Caddyshack is the exception — its longest is
5.4s).

## Theme — "Marquee" (chosen from 3 mockups)

Refined dark cinema look (the opposite of the original neon prototype): near-black
background, warm **amber** accent, a marquee-bulb masthead in **Anton** (condensed
display), quotes in **Newsreader** serif, UI in **Hanken Grotesk**. Picked over a
light "Newsprint/NYT" option and a light "Pinpoint card" option.

## Architecture

- Page **`clockthequote.html`** at the repo root, sibling to `index.html`, served
  at **`tvtalk.fun/clockthequote`** (Cloudflare serves `.html` without the extension).
- The beta currently **hard-codes a few clips** inline. The intended end state
  loads the **same** `shows.js` and `audio/` and filters the curated pool — zero
  data duplication, fed automatically by the add-a-show playbook.
- **Pure client-side, no build step, no backend.** Deploys identically through
  wrangler (just another static file).
- **The soundboard (`index.html`) is never touched.**
- A small link between the two pages (soundboard ⇄ game) for discoverability.

## The good-clips pool _(PLANNED)_

Not every clip is fair game material (muddy audio, unrecognizable, etc.), so the
game will draw from a **curated pool**, not all ~6,400 clips. (The beta hard-codes
a hand-picked few instead.)

- A clip becomes game-eligible via a marker in `transcripts.txt` — proposed
  **`GAME:`** prefix on blessed lines, round-tripped by the scraper exactly like
  the existing `REPEAT:` / character curation.
- That carries a `"game": true` flag through into each quote object in `shows.js`.
- `clock-the-quote.html` builds its pool by filtering all quotes where
  `game === true`.
- **Why this way:** reuses the existing transcript-curation habit (one workflow,
  not a new file) and keeps one-offs isolated, consistent with how curation is
  already kept from leaking into the main scrapes.

## The daily puzzle _(PLANNED — not yet built)_

- One mystery title per day, chosen **deterministically** (date seed → pick from
  the curated pool), rollover keyed to the calendar date so the shared `#N` lines
  up with friends.
- The live beta instead runs an **endless shuffle** of the hard-coded clips — a
  "shuffle bag" cycles through every clip before any repeat, with no back-to-back
  repeats. `#N` in the share is the round number for now.

## Clue ladder (AS BUILT)

5 clues. Guess at any stage from an **autocomplete list of all 64 titles**; a
wrong guess (or **Skip**) advances to the next clue. **Audio access** escalates
down the ladder; the title hint only appears at the very end:

1. **Short snippet (~2.5s) — 2 listens.** Plays from the **middle** of the clip
   (window centered on its midpoint), not the start — so a clue-1 win means you
   knew it cold. A counter shows `0/2 → 1/2 → 2/2 listens used`.
2. **5-second snippet (also from the middle) — 2 listens.**
3. **Full clip — 2 listens.**
4. **Full clip, unlimited listens + the caption** (the quote text) revealed.
5. **Full clip, unlimited + caption + masked title** — first & last letter of each
   word shown, the rest blanked (e.g. The Office → `T•• O••••e`).

Then: solve, or use all 5 → **reveal screen**: show/movie name + type, the quote as
a description, the full clip freely replayable, a **Download clip** button (reuses
the soundboard's save/share), and the share strip.

Notes:
- Per-stage listen limits are enforced — when a stage's listens are spent the play
  button greys out until you advance.
- The midpoint snippet seeks via **HTTP range requests** (Cloudflare supports them;
  the local Python dev server needed a small range-capable shim to test it).
- Clips should be **≥ 8s** so the centered snippet has audio either side of the
  midpoint; we eyeball bad midpoints (landing on a pause) during curation.

## Scoring & sharing (AS BUILT)

- **Score = the clue you solved on, lower is better** (clue 1 = `1/5` best …
  clue 5 = `5/5`; a miss = `X/5`). Wordle/golf-style. _(This reversed an earlier
  Pinpoint-style "5-best" decision.)_
- **Share message** — spoiler-free (no title or quote leaks), e.g. solved on clue 2:

  ```
  🎬 Clock The Quote #1 — 2/5
  ⬛🟩⬜⬜⬜
  https://tvtalk.fun/clockthequote
  ```

  Strip: ⬛ a clue you used · 🟩 the clue you solved on · ⬜ a clue you didn't need.
  The **Share** button uses the native share sheet on mobile and **clipboard** on
  desktop; the `https://` link is clickable so friends can tap straight in.
  (A win-streak line was tried and removed. The share-sheet `title` field was
  dropped — some apps prepended it as a duplicate top line.)

## Stats (localStorage) _(PLANNED)_

Streak, max streak, games played, win %, guess-distribution histogram, and
persisted today's-progress (resume mid-puzzle; once finished show the result, not
a replay) — all part of the daily build, **not yet in the beta** (which is
endless/replayable).

## Hint data — none needed 🎉

The new ladder's late hints (clues 4–5) are derived purely from the **answer
title string** (masking, then revealing letters), so we need **no extra
metadata** — the earlier genre/year idea is dropped. Clue 3 reuses the existing
`text` caption. This removes a whole curation chore.

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

## Build-pipeline changes _(PLANNED — for the curated pool; additive, safe — do NOT disturb the soundboard)_

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
