# Clock The Quote — Overview

> **Status:** 🟢 **LIVE in beta** at **https://tvtalk.fun/clockthequote** (deployed 2026-06-02; **daily-of-1 shipped 2026-06-05**). The shipped game is `clockthequote.html` at the repo root + a soundboard cross-link; this folder holds the design docs and the throwaway `prototype.html`. It now runs a **real daily-of-1**: one clip per US-Eastern day from a hand-curated **30-day queue** (#1 = 2026-06-05), rolling at midnight ET. Still to come: a **`shows.js`-filtered curated pool / per-show rotation** (replacing the finite queue) and persisted stats — see `01 - Design Spec.md`. Deploy with **`wrangler@4.40.0`** (4.97 hangs — see `../05 - Deployment.md`).

## What this is

A daily audio quote-guessing game built on top of the TvTalk catalog. You hear a
clip from a TV show or movie and try to **clock the quote** — name the title it's
from. It's modeled on LinkedIn's **Pinpoint** / **Heardle**: one mystery per day,
escalating clues, a spoiler-free shareable score for group chats.

The TvTalk soundboard already has the hard part done: **64 titles, ~6,400 clips**
with audio + captions in `shows.js` and `audio/`. The game reuses that data as-is.

## How it relates to TvTalk

- The game will be a **separate page** (`clock-the-quote.html`) that loads the
  **same** `shows.js` and the **same** `audio/` clips. Zero data duplication.
- The existing soundboard (`index.html`) is **never modified**. Adding a show via
  the existing playbook automatically feeds the game too.
- Build-pipeline changes are **additive only** (a new optional `game` flag on
  clips) — see `01 - Design Spec.md`.

## When to split into its own folder / GitHub repo

We expect to eventually move this to its own repo. My recommendation on timing:

- **Stay in the TvTalk repo while it shares `shows.js` + `audio/`.** During design
  and early build, sharing the catalog in one repo is the whole convenience — a
  split now would force us to copy or symlink 1MB of data + the audio tree and
  keep them in sync by hand.
- **Make the leap once the game is proven and wants independent deploys/versioning.**
  The clean split point is when (a) the game works end-to-end, and (b) you want it
  on its own domain/release cadence. At that moment we either (i) carve out a repo
  that vendors a *generated* game-data file (a slim pool, not the whole catalog),
  or (ii) publish the catalog as a tiny shared data package both repos consume.
- Until then: this docs folder is the home base. Nothing here affects TvTalk.

## Files in this folder

- `00 - Overview.md` — this note (status, relationship, split timing).
- `01 - Design Spec.md` — the full design we worked through.
- `02 - Decisions & Open Questions.md` — what's locked, what's still open, and the
  rationale, so a future session can resume cold.

## Next steps (when we resume)

The game and the daily-of-1 are **built and live**. What's left:

1. **Refill the daily queue before 2026-07-05** (it loops back to #1 otherwise), OR
   build the ongoing replacement so refills stop being manual.
2. **Ongoing daily source (parked):** a **per-show rotation** — one representative
   clip per title, each title once per cycle, reshuffled each loop, catalog grows
   over time. Build "mechanism now, grow over time." See `02 - …` open question 2.
3. Later: the `shows.js` `GAME:`-filtered pool + the additive pipeline flag, and
   persisted stats. Soundboard stays untouched throughout.
