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
**audio-access escalation**. Final shipped ladder:

1. Short snippet (~2.5s, **from the middle**) — **2 listens** (with a counter)
2. **5-second** snippet (from the middle) — **2 listens**
3. Full clip — **2 listens**
4. Full clip — **unlimited** + the **caption** (quote text) revealed
5. Full clip — unlimited + caption **+ masked title** (first & last letter of each word)

On a correct guess: success message, show name + type, the quote as description,
a freely-replayable full clip, and a **download** button (reuses the TvTalk
soundboard's save/share). `01 - Design Spec.md` has been **re-synced** to this
as-built state (2026-06-02).

**Also shipped:** theme = **"Marquee"** (dark, amber, Anton/Newsreader/Hanken —
picked from 3 mockups); score = clue-solved-on, **lower better** (1/5 best);
spoiler-free share with clickable `https://` link (no streak line); deployed at
**tvtalk.fun/clockthequote** via **`wrangler@4.40.0`** (4.97 hangs). Current beta
pool: 5 hard-coded **movies-only** clips for testing (Anchorman, Office Space, The
Other Guys, Tropic Thunder, Pulp Fiction) — movies-only is a temporary test choice,
not a design decision.

**Audio = Web Audio (decided after a long mobile debug — don't regress).** Snippets
play an exact slice from the midpoint; Cloudflare has no HTTP range support so a
plain `<audio>` can't seek. iOS needs two unlocks, both inside the play tap: resume
the AudioContext + a 1-sample silent buffer, **and** a looping silent `<audio>`
media element to flip iOS into the "playback" session so Web Audio plays through the
**mute/ringer switch** (silenced otherwise — and most people keep the ringer off).
Full detail in `01 - Design Spec.md` → "Audio playback".

## Open questions

_Resolved:_ page name → **`clockthequote.html`** (`/clockthequote`). Masking →
**first & last letter per word**, shown only at clue 5 (no extra letter-reveal step).

_Still open (for the daily build):_

1. **`GAME:` marker convention** — confirm prefix spelling and where it sits in the
   `transcripts.txt` line format (alongside `REPEAT:` / character tags).
2. **Daily rollover timezone** — local midnight (Wordle) vs a fixed zone like
   Pinpoint's midnight PT (everyone on the same #N simultaneously). Leaning fixed-zone.
3. **Initial pool size** — how many clips to bless so the daily stays fresh for months.
   (Also: shows vs movies mix — the beta is movies-only only for testing.)
4. **Repo split timing** — see `00 - Overview.md`; decide at "game proven + wants
   independent deploys."

## Process note (for whoever resumes)

This was produced with the brainstorming skill. The natural next step is the
**writing-plans** skill: turn `01 - Design Spec.md` into a step-by-step
implementation plan. Do that only after the open questions above are settled.
Build must remain **additive** — the live soundboard (`index.html`, `shows.js`,
`audio/`, scripts) stays working throughout.
