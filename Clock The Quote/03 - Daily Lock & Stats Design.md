# Clock The Quote — Daily Lock & Stats Design

> **Status:** 🟡 Design approved 2026-07-12, not yet built. Tier-1 (local-only) scope.
> Companion notes: `00 - Overview.md`, `01 - Design Spec.md`, `02 - Decisions & Open Questions.md`.
> Target file: the shipped `../clockthequote.html` (single static file, no backend).

## Goal

Turn the daily into a proper once-a-day game with persisted personal stats — the
classic Wordle model, entirely client-side:

1. **Once-a-day lock** — after you finish today's puzzle you can't replay it; you
   see your result + stats + a countdown to the next quote.
2. **Real streak** — consecutive days *won*, keyed to calendar days (the current
   `ctq_proto_streak` just counts consecutive wins and is retired).
3. **Average score** — mean score across all completed days.
4. **Guess distribution** — a histogram of which clue you solved on.

Friends / leaderboards are **out of scope** (Tier 3 — needs a backend + identity).
This design does nothing that would block adding them later.

## How this compares to Wordle (and its honesty)

The lock is a **soft, per-browser honor system**, exactly like classic Wordle:
state lives in `localStorage`. Clearing site data, incognito, or a different
browser/device resets it. That is accepted and intended — *hard* one-play-per-human
enforcement and cross-device sync require accounts + a server (a future Tier-3
project), not this one. The daily puzzle itself is already global and deterministic
(same clip for everyone, rolling at midnight ET); this design only adds the local
lock + stats layer on top.

## Data model

One JSON blob under a **new** key `ctq_v1` (versioned so a future migration is
clean). Accessed only through the existing throw-safe `lsGet`/`lsSet` helpers.

```js
ctq_v1 = {
  v: 1,
  lastNum: <int|null>,          // puzzle # of the last COMPLETED real day
  progress: {                   // today's round (in-progress OR finished); null if none
    num,                        // puzzle number this progress belongs to
    stage, guesses, solvedStage, finished
  } | null,
  stats: {
    played,                     // # of completed days (win or loss)
    wins, fails,
    curStreak, maxStreak,
    dist: [0,0,0,0,0],          // wins solved on clue index 0..4 (clue 1..5)
    scoreSum                    // Σ effective score over all completed days
  }
}
```

**Effective score per completed day** (lower is better):
- Win solved on clue *n* (0-based `solvedStage`) → `solvedStage + 1` (i.e. `1`…`5`).
- Loss (`X/5`) → **`6`** (a fail is worse than the worst win, so it drags the average).

**Average** = `stats.scoreSum / stats.played`, shown to one decimal (e.g. `3.4`).
Displayed only when `played > 0`.

## Round lifecycle

`isPreview` = a `?day=N` override is present in the URL (the queue-preview dev tool).

**On load / `startRound()`:**
- `todayNum = dailyNumber()`.
- **Preview rounds are always fresh and never persist** — if `isPreview`, skip the
  lock and skip all saves below. (Prevents dev previews from corrupting real stats
  or locking a real day.)
- Else consult `progress`:
  - `progress.num === todayNum && progress.finished` → **LOCKED**: render the result
    screen (share strip + stats + countdown). Board not playable.
  - `progress.num === todayNum && !finished` → **resume**: restore
    `stage/guesses/solvedStage` so a mid-round refresh doesn't hand out a fresh board
    with plays reset (closes the obvious refresh-cheese).
  - otherwise → **fresh** playable round for today.

**On every guess/skip (non-preview):** write `progress = {num: todayNum, stage,
guesses, solvedStage, finished}` so in-progress state survives a refresh.

**On finish (`finished` becomes true, non-preview) → `recordResult()`:**
- `win = solvedStage != null`; `eff = win ? solvedStage + 1 : 6`.
- `stats.played++`, `stats.scoreSum += eff`.
- If **win**: `wins++`, `dist[solvedStage]++`; streak — if `lastNum === todayNum - 1`
  then `curStreak++` else `curStreak = 1`; `maxStreak = max(maxStreak, curStreak)`.
- If **loss**: `fails++`, `curStreak = 0`.
- `lastNum = todayNum`; persist.

Streak uses the **puzzle-number gap** (`todayNum - lastNum`), not date arithmetic —
it's inherently DST-proof and matches the existing daily numbering.

## The lock choke-point (monetization hook)

The lock decision goes through a **single** function:

```js
function isLockedToday(todayNum){
  if (hasUnlimitedPass()) return false;         // future paid unlock — stub returns false for now
  return !!(progress && progress.num === todayNum && progress.finished);
}
```

`hasUnlimitedPass()` is a stub returning `false` for now. The future **"unlimited
plays for $"** tier flips it (e.g. an entitlement flag / receipt check) so paying
users can replay — with **zero** change to the stats or round logic, since replays
would just not call `recordResult()` again for an already-completed day.

## Stats screen

Rendered both after finishing today and via a **stats button** (a small "📊" in the
header, available any time). Contents:

- **Played · Win % · Current streak · Max streak · Average** (five stat tiles).
- **Guess distribution** — 5 rows (Clue 1…5) as horizontal bars sized to `dist[i]`,
  today's solved row highlighted; a separate **Fails** count shown alongside.
- When today is finished: the spoiler-free **share strip** + existing **Share** button
  + a live **"Next quote in HH:MM:SS"** countdown to the next ET midnight
  (`setInterval`, computed from `America/New_York` midnight, DST-safe).
- If `localStorage` is unreadable (blocked cookies / lockdown): show a friendly
  "Stats unavailable — storage is blocked" note; the game itself stays playable each
  visit (current graceful degradation is unchanged).

## Migration

- The old `ctq_proto_streak` key is **retired**. Real per-day history can't be
  reconstructed, so stats start fresh under `ctq_v1`. Optionally delete the old key
  on first `ctq_v1` write. No user-facing migration prompt.

## Testing (test-first)

Pull the pure logic out of the DOM so it's unit-testable under Node before any UI
wiring:

- `nextStats(stats, lastNum, {num, solvedStage})` → new stats + new lastNum. The
  reducer for a completed day.
- `average(stats)`, `isLockedToday(...)`, and the existing `dailyNumber` /
  `daysBetween`.

Unit tests to cover:
- Streak **continues** when `todayNum === lastNum + 1`, **resets to 1** on a skipped
  day, **resets to 0** on a loss; `maxStreak` tracks the peak.
- Average counts a **fail as 6** and averages over `played` (win-then-fail sequence
  gives the expected mean).
- `dist` increments the solved clue; a loss touches neither `dist` nor `wins`.
- Preview (`?day=N`) writes **nothing** and never locks.

Then verify live: play a day (lock + countdown appear), refresh mid-round (resume),
open `?day=N` (always fresh, stats untouched), and simulate rollover with a mocked
clock.

## Out of scope (explicitly)

- Any backend, account, or cross-device sync.
- Friend leaderboards / head-to-head (Tier 3).
- A playable archive of past days (a missed day is simply gone; you always get today).
- Practice mode — deferred to the paid "unlimited plays" unlock above.
