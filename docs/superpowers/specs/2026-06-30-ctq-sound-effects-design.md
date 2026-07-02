# Clock The Quote — UI sound effects

**Date:** 2026-06-30
**File touched:** `clockthequote.html` (single-file game; all CSS/HTML/JS inline)
**Inspo:** Songless (lessgames.com) — satisfying button sounds. We synthesize our
own equivalents rather than copy their assets.

## Goal

Add satisfying, synthesized UI sounds to the game: a subtle click on general
buttons, a tonal "pop" on a wrong guess, and a rising "octave jump" on a correct
guess. Include a mute toggle (on by default, cached per device).

## The two sounds

All generated live through the game's existing Web Audio context (`getCtx()` /
`audioCtx`). No asset files, no libraries (Songless uses Howler + .wav files; we
don't need either).

| Sound | When | Synthesis | Effective vol (master 0.4) |
|-------|------|-----------|------|
| **pop** | wrong guess **and** skip clue | 680 Hz sine blip, 50 ms, exp decay | 0.32 |
| **win** (bright bell ding) | correct guess | 3 stacked blips — 1046/1568 Hz triangle + 2093 Hz sine sparkle | ~0.20 |

A `SFX_MASTER` constant (0.4) scales both for easy tuning. (An earlier "soft
tick" click on general buttons was cut — sounds are now reserved for the three
meaningful moments: skip, wrong, win.)

## Interaction map

- **Guess submitted** → correct → **win**, wrong → **pop**.
- **Skip clue** → **pop** (skipping burns a clue just like a wrong guess).
- **No sound** on Play / Replay, the **?** button, modal open/close, Download,
  or Share.

## Guess confirmation (behavior change, bundled in)

Previously, picking a title from the autocomplete dropdown auto-submitted the
guess. Now selecting (click, or Enter while the list is open) only **fills the
input**; the player must press **Guess** (or Enter once the list is closed) to
lock it in. `submit()` only fires when the box holds an exact title, so a partial
string can't be submitted by accident.

## Mute toggle

- A small **🔊 / 🔇** button fixed top-right, just left of the **?** button.
- Sounds **on** by default (first-timers hear them). Tap toggles; choice cached
  in `localStorage["ctq_muted"]` ("1" = muted), same try/catch pattern as
  `ctq_howto_seen` / `ctq_proto_streak`.
- When muted, `sfx()` early-returns — nothing plays. Unmuting plays one click as
  confirmation.

## Technical notes

- `sfx(name)` is the single dispatcher: early-return if muted, else call
  `unlockAudio()` (existing — resumes the context and flips the iOS audio session
  inside the user gesture) then play. Every sound fires inside a tap/click, so
  mobile/iOS playback works with the existing unlock path.
- Reuses the shared `audioCtx`; does not create a second AudioContext.
- ~30 lines JS (3 sound fns + dispatcher + mute state/toggle) + one button node +
  a little CSS. All inline in `clockthequote.html`.

## Out of scope

- No change to game logic, scoring, the daily schedule, or clip audio.
- No server/Worker change — static file only.

## Verification

- Headless smoke test: no JS errors; `sfx()` callable for each name; mute flag
  round-trips through localStorage (muted → `sfx` is a no-op); toggle button
  updates icon. Manual ear check on desktop + phone before/after deploy.
