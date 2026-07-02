# Clock The Quote — "How to Play" first-visit overlay

**Date:** 2026-06-30
**File touched:** `clockthequote.html` (single-file game; all CSS/HTML/JS inline)

## Goal

Show a "How to Play" instructions modal automatically the first time a person
opens the game on a device, cached so it never auto-shows again on that device.
Add a persistent **?** button to re-open it on demand. Emulate the Songless
"How to Play" card (visual diagram), rendered in the existing Marquee/ticket
aesthetic.

## Trigger & caching

- On load, read `localStorage["ctq_howto_seen"]`.
  - Absent → auto-open the modal once (game board renders behind it).
  - Present → never auto-opens.
- Any dismissal sets `ctq_howto_seen = "1"`. Wrapped in try/catch, matching the
  existing `ctq_proto_streak` pattern (graceful degradation if storage blocked).
- The header **?** button opens the modal regardless of the flag, so returning
  players can always pull it back up.

## Layout (visual diagram, ticket aesthetic)

- Full-screen overlay; backdrop `rgba(0,0,0,.72)`. Centered cream card reusing
  the existing `--paper` / radius / shadow language. Scrollable if it exceeds
  viewport height (mobile).
- **Title** "How to Play" in Anton. One-line summary beneath.
- **Mini-mockup block** mirroring the real board:
  - The 5 progress dots (first lit red).
  - The round play button (▶) → label "Hear the quote".
  - A faux guess input "Name the show or movie…" → label "Guess the title".
- **Clue ladder** — 5 labelled rows for what each wrong guess / skip unlocks:
  1. 2.5-second snippet
  2. 5-second snippet
  3. Full clip
  4. + the written quote, title hidden
  5. + the title's initials
- **Footer line:** "Fewer clues = better score. Come back daily to build a streak."
- **Dismiss:** red "Got it" button, an ✕ top-right, click on backdrop, and the
  Esc key. All set the flag and hide the modal.

## Copy

> Hear a quote from a TV show or movie. Name it. Each wrong guess or skip
> unlocks a bigger clue — solve it in as few as you can.

## Header ? button

- Small circular **?** affordance in the marquee header (`.mast`), styled in the
  muted/gold theater palette so it reads as theater chrome, not a game control.
- Click → `openHowTo()` (does not touch the storage flag on open; only dismissal
  writes the flag).

## Implementation footprint

- One CSS block (`.howto-*` / overlay).
- One static HTML overlay node (built once, not re-rendered by `render()`), plus
  the **?** button in `.mast`.
- ~15 lines JS: `openHowTo()`, `closeHowTo()` (writes flag), keydown(Esc),
  backdrop click, and a load-time check that calls `openHowTo()` when the flag is
  absent. Modal lives outside the `#card` innerHTML so the game's `render()` /
  `renderResult()` never clobber it.

## Out of scope

- No change to game logic, scoring, audio, or the daily schedule.
- No server/Worker changes — static file only.

## Verification

- Headless screenshot (fresh storage → modal shows; reload with flag → no modal;
  click **?** → reopens). Check mobile-width rendering and that the backdrop
  doesn't block the game after dismissal.
