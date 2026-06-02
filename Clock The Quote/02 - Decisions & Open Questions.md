# Clock The Quote — Decisions & Open Questions

> The "why" behind the design, so a future session can resume without re-litigating.
> Companion notes: `00 - Overview.md`, `01 - Design Spec.md`.

## Locked decisions (from the 2026-06-02 brainstorm)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| 1 | Session format | **Daily puzzle** (Wordle/Pinpoint model) | More reach than a private game; the daily *is* the "play with friends" loop, done async via shared scores. No backend. |
| 2 | Social flavor | **Daily now, party mode later** | Build the async-shareable daily first; architect so a same-screen party mode can bolt on without a rewrite. Live multiplayer rooms rejected (needs a backend). |
| 3 | Answer mechanic | **Pinpoint-style** — guess from an autocomplete list, escalating clues, fewer clues = better | Fits the catalog (many quotes per title); proven, addictive, shareable. |
| 4 | Clue medium | **Audio-first, words revealed gradually** | Hear-and-name on clue 1 is the flex; then ~⅓ → ~⅔ → full quote → title hint. True to "clock the quote." |
| 5 | Daily pick source | **Auto-seeded from a curated "good clips" pool** | High quality with no daily labor after the initial blessing pass. Seeded by date for determinism. |
| 6 | v1 scope | **Daily-only (one and done)** | Max come-back-daily pull; simplest build. Practice mode can come later. |

## Secondary calls made (open to veto)

- **Page name:** `clock-the-quote.html` (vs `game.html`). *Tentative.*
- **Pool marker:** `GAME:` prefix in `transcripts.txt`, reusing the existing
  curation round-trip. *Tentative.*
- **Rollover:** local midnight, keyed to calendar date.
- **Guess count:** 5.
- **Reveal sizing:** by *fraction* of the caption (not fixed word counts), to
  survive very short captions.
- **Stats:** localStorage only (streak, max streak, win %, guess histogram).

## Open questions to resolve before building

1. **Final page name** — `clock-the-quote.html` or something shorter?
2. **`GAME:` marker convention** — confirm prefix spelling and where it sits in the
   `transcripts.txt` line format (alongside `REPEAT:` / character tags).
3. **Clue 5 hint contents** — ship with just `type` + `character`, or invest in the
   optional `genre`/`year` data in `shows.yaml` first?
4. **Initial pool size** — how many clips to bless for launch so the daily doesn't
   repeat for a long while (need enough that #N stays fresh for months).
5. **Repo split timing** — see `00 - Overview.md`; decide at "game proven + wants
   independent deploys."

## Process note (for whoever resumes)

This was produced with the brainstorming skill. The natural next step is the
**writing-plans** skill: turn `01 - Design Spec.md` into a step-by-step
implementation plan. Do that only after the open questions above are settled.
Build must remain **additive** — the live soundboard (`index.html`, `shows.js`,
`audio/`, scripts) stays working throughout.
