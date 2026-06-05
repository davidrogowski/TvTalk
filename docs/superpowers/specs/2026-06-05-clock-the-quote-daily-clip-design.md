# Clock The Quote — Daily clip design

> Captured 2026-06-05 in brainstorming. Scope: turn the live beta's endless random
> shuffle into a real **one-clip-per-day** daily, queued 10 days out, auto-rolling
> at midnight ET. Edits `clockthequote.html` only.

## Goal

Today the live page (`clockthequote.html`, served at `/clockthequote`) runs an
**endless random shuffle** of 5 hard-coded test clips. We want a **true daily**:
exactly one specific clip per calendar day in US Eastern time, the same clip for
every player that day, automatically becoming the next queued clip at midnight ET.
No server, no cron — pure client-side date math.

## Decisions (locked)

- **One specific clip per day**, from a fixed ordered queue — NOT a pool that cycles
  `mod length`. Each day maps to one explicit schedule entry.
- **Queue depth: 10 clips** (10 days). Refill before it runs out.
- **Puzzle #1 = 2026-06-05 ET** (today). #2 = 2026-06-06, etc.
- **Timezone: America/New_York**, resolved with `Intl.DateTimeFormat` (DST-safe —
  no manual offset), so the rollover is correct for every visitor regardless of
  their device timezone.
- **"1 clip only":** remove the random shuffle and all replay-to-a-different-clip
  paths. You get today's clip; tomorrow you get the next one.

## Mechanic

```
const DAILY_START = "2026-06-05";   // ET date of puzzle #1
const SCHEDULE = [ {show, text, url, ...}, ... ];   // 10 entries, in day order
```

- `etDateKey()` → `"YYYY-MM-DD"` for *now* in `America/New_York`
  (`Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date())`).
- `dayIndex = floor((Date.UTC(todayET) - Date.UTC(DAILY_START)) / 86400000)`.
- `puzzleNo = dayIndex + 1` → used as `#N` in the share text.
- **Today's clip = `SCHEDULE[dayIndex]`.**

### Edge cases
- **`?day=N` URL override** (1-based): force any puzzle for previewing the queue
  before it goes live. `?day=2` shows puzzle #2.
- **Queue exhausted (dayIndex ≥ 10) or before start (< 0):** safely **loop** —
  `SCHEDULE[((dayIndex % len) + len) % len]` — so the game never dead-ends. The
  puzzle number still climbs (e.g. #11 shows clip #1 but reads "#11"). The last
  schedule entry carries a `// REFILL BEFORE <date>` comment as the cue to top up.

## Replay behavior changes

- Delete `clipBag` / `pickClip()` random-shuffle machinery.
- Remove the bottom **"↻ New clip"** practice link.
- Result screen: replace **"Next clip ↻"** with a **"Come back tomorrow for #N+1"**
  line. Keep **Share** and **Replay full clip**. (Replay plays *today's* clip only.)

## The 10-day queue

All ≥8s so the centered snippet has audio on both sides (per the as-built ladder).
Captions are cleaned to short labels per the add-show SOP.

| # | Title | Caption | Type | File (under `audio/`) | Len |
|---|---|---|---|---|---|
| 1 | Superbad | McLovin | movie | `superbad/030_mclovin.mp3` | 16s |
| 2 | The Office | Bears. Beets. Battlestar Galactica | show | `the-office/019_bears_beets_battlestar_galactica.mp3` | 21s |
| 3 | Anchorman | I love lamp | movie | `anchorman/055_i_love_lamp.mp3` | 9s |
| 4 | The Hangover | One man wolf pack | movie | `the-hangover/028_one_man_wolf_pack.mp3` | 8s |
| 5 | Forrest Gump | Life is like a box of chocolates | movie | `forrest-gump/074_my_mom_always_said_life_was_like_a_box_of_chocolates_you_nev.mp3` | 11s |
| 6 | The Big Lebowski | That rug really tied the room together | movie | `big-lebowski/057_that_rug_really_tied_the_room_together_did_it_not_fucking_a.mp3` | 8s |
| 7 | Dodgeball | If you can dodge a wrench, you can dodge a ball | movie | `dodgeball/017_if_you_can_dodge_a_wrench_you_can_dodge_a_ball.mp3` | 15s |
| 8 | Talladega Nights | Thank you sweet baby Jesus | movie | `talladega-nights/037_thank_you_sweet_baby_jesus.mp3` | 16s |
| 9 | Step Brothers | I didn't touch the drum set | movie | `step-brothers/043_look_i_didn_t_touch_a_drum_set_ok_i_witnessed_with_my_eyes_y.mp3` | 9s |
| 10 | The Office | Prison Mike | show | `the-office/261_prison_mike.mp3` | 14s |

All 10 titles already exist in the 64-title autocomplete list, so each is guessable.

## Playback start (no change)

Confirmed 2026-06-05: the snippet clues (1 & 2) must start from the **middle** of
the clip — which the as-built `segOffset()` already does (centered window on the
midpoint). The full-clip stages (clues 3–5) and result replay keep playing from
the start so players hear the whole clip. **No audio-playback change is required.**

## Out of scope (beta)

- Per-day "you already played today" lockout / persistence.
- Calendar-day streak logic (current `ctq_proto_streak` consecutive-win behavior
  is left unchanged).
- Drawing from the full curated `shows.js` pool (still the spec's planned end state).

## Verification

- Local render: open `clockthequote.html`, confirm `?day=1`…`?day=10` each load the
  expected clip + caption + masked title, and `#N` matches.
- Default load (no `?day`) shows puzzle #1 today.
- Confirm the random shuffle and "New clip" link are gone; result screen shows the
  "come back tomorrow" line.
- Deploy via the pinned wrangler flow and verify the live URL.
