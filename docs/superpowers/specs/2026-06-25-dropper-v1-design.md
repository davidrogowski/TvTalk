# Dropper V1 — Design

**Date:** 2026-06-25
**Status:** Approved (design); pending implementation plan
**URL:** `tvtalk.fun/dropper`

## One-liner

Paste a YouTube link, mark the beat drop, pick a quote from the TvTalk
library, and the quote lands right as the beat drops — the "Two Friends"
move. Shareable by link, fully in-browser, no backend.

## Goals

- Let anyone recreate the build-up → spoken-quote → DROP effect in a few taps.
- Reuse the existing TvTalk quote library (9,672 labeled clips across 99
  shows/movies, already hosted under `/audio/...` and indexed in `shows.js`).
- Ship V1 as pure static-on-Cloudflare with zero new infrastructure.

## Non-goals (deferred to V2)

- Downloadable / rendered clip files.
- `yt-dlp` + `ffmpeg` backend.
- Text search across quotes.
- Automatic beat-drop detection.
- User-uploaded songs (instead of YouTube links).

## Architecture

A single static page (`dropper.html`) deployed with the rest of the site on
Cloudflare. **No backend, no new infra.** Three audio actors, all
client-side, coordinated by a small JS scheduler:

1. **YouTube IFrame Player API** — plays the song. We drive `seekTo()`,
   `playVideo()`, `pauseVideo()`, and `setVolume()`.
2. **HTML5 `Audio`** — plays the chosen quote mp3 directly from `/audio/...`.
3. **Timing scheduler** — aligns the quote against the marked drop on a
   shared timeline.

### Why no backend

We never extract YouTube audio. The IFrame API plays the video in-page and
exposes volume control, which is all the duck→boom effect needs. The
tradeoff: because the YouTube audio is cross-origin and uncapturable, we
cannot (a) auto-detect the drop or (b) render a downloadable file. Both are
intentionally V2, where a real `yt-dlp` + `ffmpeg` backend earns its keep.

## Components

- **Loader** — paste a YouTube URL → parse out the `videoId` → mount the
  IFrame player.
- **Drop marker** — play the video; a prominent **"Mark the drop"** button
  stamps the current playback time as `dropTime`. ◀ ▶ nudge buttons (±0.1s)
  and a numeric readout fine-tune it.
- **Quote picker** — a show/movie dropdown (grouped like the main app),
  feeding a scrollable clip list with a ▶ to audition each clip; plus a
  **🎲 Surprise me** button that loads a random clip (optionally scoped to
  the currently selected show). Data comes from `shows.js`. (No text search
  in V1.)
- **The moment (player)** — a **Play** button that runs the aligned preview;
  a **Share** button that copies the reconstruct URL; and a **Download**
  button rendered as a disabled "coming soon" stub (V2).

## Timing engine (the core)

Inputs: the marked `dropTime` (seconds into the video) and `quoteDuration`
(read from the quote mp3's metadata when the clip loads).

Defaults:

- `gap = 0` — quote ends exactly **on** the drop (nudgeable ±0.5s).
- `leadIn ≈ 1.8s` — build-up runway played before the quote starts.
- `duck ≈ 20%` — YouTube volume during the quote.
- `tail ≈ 4s` — how long the drop rides after the boom before stopping.

Schedule:

1. `quoteStart = dropTime − quoteDuration − gap`
2. Preview begins by seeking the song to `quoteStart − leadIn` and playing.
3. At `quoteStart`: ramp YouTube volume down to `duck` and start the quote
   `Audio`.
4. At `dropTime`: snap YouTube volume back to 100% (the boom).
5. After `tail` seconds, stop playback. The resulting ~8–10s window is the
   shareable "moment."

The schedule math (`quoteStart`, clamping, tail cutoff) is implemented as
pure functions so it can be unit-tested without the DOM or network.

## Share model (zero storage)

Everything needed to reconstruct a moment fits in the URL — no KV/R2 in V1:

```
tvtalk.fun/dropper?v=<videoId>&d=<dropTime>&q=<show>:<clipIndex>&g=<gap>&dk=<duck>
```

Opening such a link rebuilds the exact moment and arms **Play**. Pretty short
links via KV are a trivial later addition and are deferred.

## Error handling

- **Non-embeddable / region-locked / age-restricted video** — the IFrame
  fires an error event; show "this video can't be embedded, try another link."
- **Drop marked too early** — if `quoteStart` would be < 0, clamp `leadIn`
  (and if still impossible, warn that the drop is too close to the start).
- **Mobile autoplay policy** — the single **Play** tap is the user gesture
  that unlocks both the IFrame player and the quote `Audio`.
- **Invalid/garbled share URL params** — fall back to the empty builder
  state rather than erroring out.

## Visual identity

Default: reuse the TvTalk page shell/navigation so it feels part of the
family, with a distinct DJ-flavored accent (the drop UI, waveform-ish
timeline treatment). Final styling polish is an implementation detail to
settle while building; it does not change the architecture.

## Testing

- **Unit:** the timing functions — `quoteStart`, start-clamping, tail cutoff
  — as pure functions, no DOM.
- **Manual:**
  - A clean EDM-drop video: verify the duck→boom feel lands.
  - A region-locked / non-embeddable video: verify the error path.
  - A couple of quotes of different lengths: verify end-on-drop alignment.
  - Copy a Share URL, open it fresh: verify it reconstructs identically.

## Open / deferred decisions

- Exact default values (`leadIn`, `duck`, `tail`) may be tuned by ear during
  manual testing.
- Pretty short-links (KV) — deferred.
- Whether **Surprise me** defaults to all-shows or the selected show —
  settle during implementation (lean: selected show if one is chosen, else
  all).
