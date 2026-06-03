# Clock The Quote — Decisions & Open Questions

> The "why" behind the design, so a future session can resume without re-litigating.
> Companion notes: `00 - Overview.md`, `01 - Design Spec.md`.

## Locked decisions (from the 2026-06-02 brainstorm)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| 1 | Session format | **Daily puzzle** (Wordle/Pinpoint model) | More reach than a private game; the daily *is* the "play with friends" loop, done async via shared scores. No backend. |
| 2 | Social flavor | **Daily now, party mode later** | Build the async-shareable daily first; architect so a same-screen party mode can bolt on without a rewrite. Live multiplayer rooms rejected (needs a backend). |
| 3 | Answer mechanic | **Pinpoint-style** — guess from an autocomplete list, escalating clues, fewer clues = better | Fits the catalog (many quotes per title); proven, addictive, shareable. |
| 4 | Clue ladder | **5-rung ladder: snippet → full clip → caption text → masked title → more letters** | Audio-first flex, then escalating reveals. One clip (no quote-ranking); late hints come from the title string, so **no extra metadata needed**. Refined after studying real Pinpoint (clues run hardest→easiest, score 5-best). |
| 5 | Daily pick source | **Auto-seeded from a curated "good clips" pool** | High quality with no daily labor after the initial blessing pass. Seeded by date for determinism. |
| 6 | v1 scope | **Daily-only (one and done)** | Max come-back-daily pull; simplest build. Practice mode can come later. |

## Secondary calls made (open to veto)

- **Page name:** `clock-the-quote.html` (vs `game.html`). *Tentative.*
- **Pool marker:** `GAME:` prefix in `transcripts.txt`, reusing the existing
  curation round-trip. *Tentative.*
- **Rollover:** local midnight, keyed to calendar date.
- **Guess count:** 5.
- **Score direction:** the number = the clue you solved on, **lower is better**
  (clue 1 = `1/5` best … clue 5 = `5/5`, miss = `X/5`). Wordle/golf-style, not
  Pinpoint's inverted 5-best. (Reversed 2026-06-02 per Dave.)
- **Sharing:** spoiler-free strip (⬛ used · 🟩 solved-on · ⬜ unused) + `🎬` brand
  line + `#N` + score + `🔥 N day win streak!` + clickable `https://` play link.
  Share button = native share sheet on mobile, clipboard copy on desktop. Streak
  persisted in localStorage (prototype counts consecutive wins; real game keys to
  calendar days). `PLAY_URL` is a placeholder until the real domain is set.
- **Stats:** localStorage only (streak, max streak, win %, guess histogram).
- **Snippet plays from the MIDDLE** of the clip (window centered on `duration/2`),
  not the opening — makes clue 1 a real "do you know it cold" test. Pool clips
  should be **≥ 8s** so there's audio either side of the midpoint. We'll eyeball
  bad midpoints (landing on a pause) manually during early curation — accepted.

### ⚠️ Ladder evolved in the prototype (Design Spec is now behind)

Hands-on iteration replaced the old "reveal more words" ladder with an
**audio-access escalation**. Current, agreed ladder:

1. Snippet (~2.5s, from middle) — **one listen**
2. Snippet — **replay freely**
3. Full clip — **one listen**
4. Full clip — **replay freely**
5. Full clip — replay freely **+ masked title** (first & last letter of each word)

On a correct guess: success message, show name + type, the quote as description,
a freely-replayable full clip, and a **download** button (reuses the TvTalk
soundboard's save/share). The quote text is now **only** a post-win reveal, never
an in-game clue. `01 - Design Spec.md` still describes the older ladder and should
be re-synced once the prototype feel is locked.

## Open questions to resolve before building

1. **Final page name** — `clock-the-quote.html` or something shorter?
2. **`GAME:` marker convention** — confirm prefix spelling and where it sits in the
   `transcripts.txt` line format (alongside `REPEAT:` / character tags).
3. **Masking rule for clues 4–5** — exact letters revealed at each step (first+last
   per word, then ~half remaining? vowels?). Decide by feel during build.
4. **Daily rollover timezone** — local midnight (Wordle) vs a fixed zone like
   Pinpoint's midnight PT (everyone on the same #N simultaneously, better for
   shared bragging). Leaning fixed-zone.
5. **Initial pool size** — how many clips to bless for launch so the daily doesn't
   repeat for a long while (need enough that #N stays fresh for months).
6. **Repo split timing** — see `00 - Overview.md`; decide at "game proven + wants
   independent deploys."

## Process note (for whoever resumes)

This was produced with the brainstorming skill. The natural next step is the
**writing-plans** skill: turn `01 - Design Spec.md` into a step-by-step
implementation plan. Do that only after the open questions above are settled.
Build must remain **additive** — the live soundboard (`index.html`, `shows.js`,
`audio/`, scripts) stays working throughout.
