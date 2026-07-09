# Clock The Quote — Design Spec

> Originally captured 2026-06-02 in brainstorming; **updated to as-built once the
> first version shipped live.** Sections marked _(PLANNED)_ are the longer-term
> design, not yet built. Companion notes: `00 - Overview.md`,
> `02 - Decisions & Open Questions.md`.

## One-line concept

A daily, Pinpoint-style audio quote-guessing game on top of the TvTalk catalog:
hear a clip, name the show/movie, fewer clues = better score, share a spoiler-free
result strip.

## Status — LIVE in beta (shipped 2026-06-02; daily-of-1 shipped 2026-06-05)

Shipped as **`clockthequote.html`** at the repo root, live at
**https://tvtalk.fun/clockthequote**, deployed by the same Cloudflare Worker as
the soundboard (which has a cross-link to it; the game links back). The throwaway
prototype that drove the iteration is `Clock The Quote/prototype.html`.

**Built and live:** the 5-clue audio ladder (below), guess-by-autocomplete over
all catalog titles (99 as of 2026-07-01), scoring, the spoiler-free share (native share sheet on mobile /
clipboard on desktop), the "Marquee" visual theme, and — as of **2026-06-05** —
the **real daily-of-1 selection** (below). The original endless shuffle-bag of
hard-coded test clips has been **removed**; there is no practice replay.
**Still not built:** the curated `GAME:` pool drawn from `shows.js` (the daily
draws from a hand-curated in-page queue instead), and persisted stats.

As of **2026-06-30** the game also has a **first-visit How-to-Play overlay**,
**synthesized win/wrong sound effects**, and a **persisted SFX mute button** —
design specs in `docs/superpowers/specs/2026-06-30-ctq-how-to-play-design.md`
and `docs/superpowers/specs/2026-06-30-ctq-sound-effects-design.md`.

As of **2026-07-09** the **clue ladder was retuned** — snippets are now **1s → 3s
→ 5s**, the **written quote arrives at clue 4** (with the full clip), and clue 5's
title hint is the **first letter of the first word + last letter of the last word**
(single-word titles: first letter only). Short snippets now center on a per-clip
**speech anchor** (silero-VAD) instead of the raw midpoint, so they land on
dialogue, not a music bed — see **Clue ladder** and **Speech anchoring** below.

## Daily-of-1 (AS BUILT — 2026-06-05)

One clip per calendar day, the same for every player, rolling over at **midnight ET**.

- A hand-curated **`SCHEDULE`** array inline in the page — one entry
  `{show, text, url}` per day, in order. **105 days queued** (#1 = 2026-06-05 …
  #105 = 2026-09-17). #1–30 are the original batch; #31–35 are frozen repeats of
  #1–5 (so the already-played loop days don't shift); #36–70 and #71–105 are two
  fresh batches of previously-unused titles added **2026-07-09**. **All 99 guessable
  titles are now used at least once.** Clips are ≥8s except the 7 in #99–105
  (Beavis and Butt-Head, Caddyshack, ITYSL, King of the Hill, Mean Girls, Role
  Models, Wolf of Wall Street), which have no ≥8s clip so use their best shorter
  one (relaxed floor).
- **Selection is pure client-side date math, no server/cron.** `dailyNumber()` =
  `daysBetween("2026-06-05", todayET) + 1`, where `todayET` is the calendar date in
  `America/New_York` via `Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York'})`
  — **DST-safe**, and correct regardless of the visitor's own timezone. Today's
  clip = `SCHEDULE[(n-1) % len]`; the share `#N` is this real daily number.
- **Loops** past the end (`% len`) so it never dead-ends — a `REFILL BEFORE <date>`
  comment on the last entry marks the cue (currently **2026-09-18**). A **`?day=N`**
  query param force-previews any day for testing. **When you refill/reorder the
  `SCHEDULE`, re-run `scripts/compute_speech_anchors.py --write`** to recompute the
  per-clip speech anchors (see **Speech anchoring** below).
- Clips are all **≥ 8s**, captions cleaned to short labels, every title in the
  full-catalog guess list (99 titles). The result screen shows **"come back tomorrow for #N+1"**
  (no next-clip button; a tab left open across midnight needs a reload).
- **Caveat (intentional):** intra-day consistency is the only hard guarantee
  (same clip for everyone today). Historical day→clip is *not* pinned forever — when
  the queue changes/grows, future picks may shift, which is fine because the share
  strip is spoiler-free.
- **Ongoing plan (parked):** replace the finite hand-curated queue with a
  **per-show rotation** — one representative clip per title, each title once per
  cycle, reshuffled on each loop, catalog grows over time. See
  `02 - Decisions & Open Questions.md`. Design doc:
  `docs/superpowers/specs/2026-06-05-clock-the-quote-daily-clip-design.md`.

## Theme — "Marquee" (chosen from 3 mockups)

Refined dark cinema look (the opposite of the original neon prototype): near-black
background, warm **amber** accent, a marquee-bulb masthead in **Anton** (condensed
display), quotes in **Newsreader** serif, UI in **Hanken Grotesk**. Picked over a
light "Newsprint/NYT" option and a light "Pinpoint card" option.

## Architecture

- Page **`clockthequote.html`** at the repo root, sibling to `index.html`, served
  at **`tvtalk.fun/clockthequote`** (Cloudflare serves `.html` without the extension).
- The daily currently reads a **hand-curated `SCHEDULE`** (one clip/day) inline.
  The intended end state loads the **same** `shows.js` and `audio/` and filters the
  curated pool — zero data duplication, fed automatically by the add-a-show playbook.
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
- `clockthequote.html` builds its pool by filtering all quotes where
  `game === true`.
- **Why this way:** reuses the existing transcript-curation habit (one workflow,
  not a new file) and keeps one-offs isolated, consistent with how curation is
  already kept from leaking into the main scrapes.

## The daily puzzle — BUILT 2026-06-05

The deterministic daily-of-1 is **live** — see the **Daily-of-1 (AS BUILT)** section
above. The one remaining _(PLANNED)_ piece is that it draws from a hand-curated
in-page `SCHEDULE` rather than a `GAME:`-filtered pool of `shows.js`; the per-show
rotation that replaces the finite queue is parked (see `02 - Decisions`).

## Clue ladder (AS BUILT)

5 clues. Guess at any stage from an **autocomplete list of all catalog titles (99, mirrored from shows.js)**; a
wrong guess (or **Skip**) advances to the next clue. **Audio access** escalates
down the ladder — the snippets get longer, then the written quote and a title
hint appear at the end:

1. **1-second snippet — 2 listens.** Plays centered on the clip's **speech anchor**
   (see below), not the start or the raw midpoint — so a clue-1 win means you knew
   it cold. A counter shows `0/2 → 1/2 → 2/2 listens used`.
2. **3-second snippet (same anchor) — 2 listens.**
3. **5-second snippet (same anchor) — 2 listens.** The three snippets are nested
   (1s ⊂ 3s ⊂ 5s) around the anchor, so each is "more of the same moment."
4. **Full clip — 2 listens + the caption** (the quote text) revealed.
5. **Full clip, unlimited + caption + title hint** — the **first letter of the first
   word** plus the **last letter of the last word**, the rest blanked (e.g. The
   Office → `T•• •••••e`). **Single-word titles show only the first letter**
   (Superbad → `S•••••••`).

Then: solve, or use all 5 → **reveal screen**: show/movie name + type, the quote as
a description, the full clip freely replayable, a **Download clip** button (reuses
the soundboard's save/share), and the share strip.

Notes:
- Per-stage listen limits are enforced — when a stage's listens are spent the play
  button greys out until you advance.
- Clips should be **≥ 8s**. The short snippets center on a per-clip **speech anchor**
  computed offline (silero-VAD), so they land on dialogue rather than a music bed —
  this replaced the old "eyeball a good midpoint during curation" chore. See
  **Speech anchoring** below.

### Audio playback — Web Audio (don't regress this)

Snippets play an **exact slice** centered on the clip's **speech anchor** (see
**Speech anchoring** below; falls back to the midpoint), which forced a specific
implementation (the path here was hard-won — see the history below before changing it):

- **Why not a plain `<audio>` element:** Cloudflare static assets serve audio as
  `200` with **no HTTP range support**, so an `<audio>` element can't seek mid-clip
  — it just plays from the start. (A blob URL is seekable but hits the iOS issues
  below anyway.)
- **What we do:** fetch each clip → `decodeAudioData` into an AudioBuffer → play a
  slice with `bufferSource.start(0, offset, windowSeconds)`. No seeking at all;
  frame-accurate snippet windows.
- **iOS gotcha 1 — gesture:** iOS keeps the AudioContext muted until a node starts
  inside a user tap. `unlockAudio()` (called in the play tap) resumes the context
  and starts a 1-sample silent buffer to wake it.
- **iOS gotcha 2 — the mute/ringer switch:** iOS silences *Web Audio* when the ring
  switch is off (most people's default), even though it lets `<audio>` media play.
  Fix: `unlockAudio()` also plays a **looping silent `<audio>` MEDIA element** (an
  inline base64 data URI), which flips iOS into the "playback" audio session so Web
  Audio plays through the switch. Verified on iOS with the ringer off.

### Speech anchoring (AS BUILT — 2026-07-09)

The 1s/3s/5s snippets used to center on the clip's **temporal midpoint**, which for
some clips is a music bed or a beat of silence — so the short snippets captured no
dialogue and were unguessable (the Wedding Crashers case: 0% speech in the 1s
window at the midpoint). Fix ("approach A"):

- **Offline VAD pass** — `scripts/compute_speech_anchors.py` runs **silero-VAD**
  over each `SCHEDULE` clip, finds the **longest run of speech**, and records its
  **center (seconds)** as the clip's anchor.
- **Baked into the page** — the anchors live in a `const ANCHORS = { "<url>": secs }`
  map inline in `clockthequote.html`. `segOffset()` centers the nested 1s/3s/5s
  windows on the anchor and **clamps each window to the clip bounds**; any clip
  missing from `ANCHORS` (or with no detected speech) **falls back to the midpoint**,
  so a stale table degrades gracefully rather than breaking.
- **Why silero, not loudness/webrtcvad** — the failure mode is a **loud** music bed,
  so an energy/loudness heuristic picks the music. webrtcvad also mislabeled the
  Wedding Crashers music as speech (94% "speech", anchor didn't move); silero rejects
  music. Verified: the 1s window went 0% → 90% speech on Wedding Crashers, 0% → 100%
  on This Is The End, while already-good clips stayed good.
- **Regenerate when the SCHEDULE changes** — `python scripts/compute_speech_anchors.py --write`
  (needs a venv with `silero-vad`; see the script header). Run it whenever you
  **refill or reorder the daily `SCHEDULE`** — it reparses the schedule and rewrites
  the `ANCHORS` block in place. New/renamed clips without an anchor just fall back to
  the midpoint until you re-run it.

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
a replay) — **still not built**. The daily-of-1 shipped without stats; there's no
"already played today" lockout yet, so reloading replays the same day's clip fresh.

## Hint data — none needed 🎉

The ladder's late reveals — the **clue-4 quote** and the **clue-5 title hint** — are
derived purely from the entry's own data (the `text` caption and the **answer title
string**), so we need **no extra metadata** — the earlier genre/year idea is dropped.
This removes a whole curation chore.

## Known limitation (carried forward)

- The clip's `audio/<show>/…` path **names the title in devtools**. For
  friends-casual play we **accept this in v1**. If it ever matters, the fix is
  opaque/renamed paths for the daily clip. Logged, not solved.

## Testing & verification

How the beta was verified (useful patterns for next time):

- **Headless screenshots** of each screen (refresh-in-place), plus `node --check` on
  the inlined `<script>` after every change.
- **Audio verified via a beacon-to-server-log trick:** headless browsers have no
  audio clock and can't be screenshotted mid-async, so the test page `fetch()`es a
  result string (e.g. the seeked position) that the local dev server logs — read the
  log to confirm. This is how the midpoint seek was proven (29s clip → 13.26s).
- **Mobile audio can only be verified on a real device** — headless can't reproduce
  iOS (gesture rules, the mute switch). Dave tested on his phone; that's the loop.
- **Playwright verify scripts now exist** (2026-06-30): `scripts/verify-howto.mjs`
  (first-visit How-to-Play overlay), `scripts/verify-sfx.mjs` (UI sound effects +
  mute), `scripts/verify-msgs.mjs` (result messages), plus `scripts/shot.mjs` /
  `scripts/clue-shots.mjs` for screenshots — all using the shared `scripts/_harness.mjs`.

The daily-of-1's deterministic core is small inline helpers — `etDateKey()`,
`daysBetween()`, `dailyNumber()`, `clipForNumber()`. They were verified by running
the extracted logic under `node` (e.g. today → #1, tomorrow → #2, loop at the queue
end) plus headless screenshots of `?day=N` result screens, rather than a unit-test
harness. A future stats build could still extract these into a tested module.

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
