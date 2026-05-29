# Save / share the current quote's audio

**Date:** 2026-05-28
**Status:** Approved, ready for implementation plan
**Scope:** `index.html` only. No build-pipeline, scraper, or data changes.

## Goal

Let a user save (or send) the mp3 of a quote they just heard and liked. The
primary audience is **iPhone Safari**, so the design is built around the iOS
native flow first and desktop second.

## Behavior

- A small, muted affordance appears in the quote display **after a quote plays**,
  fading in alongside the caption via the existing `.visible` class.
- It is **hidden in the idle state** (before any quote) and hidden again on
  show-switch (`clearQuote()`), then re-revealed and re-pointed at the new quote
  each time PRESS is pressed.
- It always acts on **the quote currently on screen**.
- The affordance is the familiar **iOS share glyph** (box-with-up-arrow outline),
  subtle enough not to compete with the caption.

## Save name

`<Show> - <Caption>.mp3` — e.g. `The Boys - I'll break your legs.mp3`.

- Show name comes from `item.showName`, which `buildPool()` already sets in both
  random and single-show modes.
- Caption is the quote's `text`.
- A `sanitizeFilename(text)` helper strips/replaces characters illegal in
  filenames (`/ \ : * ? " < > |`), collapses whitespace, and trims. Falls back to
  a sensible default (e.g. `clip`) if the result is empty.
- **The served mp3 file on disk is never renamed** (decision C from brainstorming):
  the clean name is applied only to the saved/shared copy.

## Mechanism

Feature-detect and branch on a single tap:

1. **Primary — Web Share API with a file** (covers iOS Safari well):
   - `fetch(q.audioUrl)` → `blob()` → `new File([blob], cleanName, { type: 'audio/mpeg' })`.
   - If `navigator.canShare?.({ files: [file] })`, call `navigator.share({ files: [file] })`.
   - User gets the iOS share sheet (Save to Files, AirDrop, Messages, …) with the
     clean filename preserved.
2. **Fallback — `<a download="cleanName" href="q.audioUrl">`** (desktop / browsers
   without file-share): the audio is same-origin (static asset), so the browser
   honors the rename.

Clips are small (a few hundred KB), so the fetch-then-share is effectively instant.
The site is already HTTPS and the action is behind a user tap, satisfying Web Share's
requirements.

### Why not the simpler options

- **Plain `<a download>` everywhere:** iOS Safari ignores the `download` filename
  and saves under the ugly URL-derived name — it fails the exact platform that
  matters most.
- **Worker `Content-Disposition` header:** server-forced and an infra change; the
  filename would be baked per-file, losing the dynamic `Show - Caption` name, and
  it's still unreliable on iOS.

## Implementation sketch (all in `index.html`)

- Add a muted share control to `.quote-display` markup, hidden by default.
- Add `sanitizeFilename(text)` helper.
- Add a `saveCurrentQuote()` handler implementing the share-primary /
  download-fallback branch above, using the currently-displayed item.
- Track the current item (the existing code already has `item` in the PRESS
  handler; store what the control needs — `audioUrl`, `showName`, `text`).
- In `showQuote(item)`: set the control's target + clean name and reveal it.
- In `clearQuote()`: hide the control.
- CSS: small, muted color, fades in with the caption; nothing that competes
  visually.

## Error handling

- If the user dismisses the iOS share sheet, `navigator.share` rejects with an
  `AbortError` — swallow it silently (it's a normal cancel, not an error).
- If `fetch` fails (offline, etc.), fall back to the download-anchor path so the
  user still has a way to get the file; if that also can't run, fail quietly
  without breaking the page.

## Testing

Manual (primary verification on a real iPhone Safari):

- Press a quote → share glyph fades in → tap → iOS share sheet shows, "Save to
  Files" produces `Show - Caption.mp3` that plays.
- Glyph is hidden on initial load and after switching shows; re-appears and points
  at the new quote after each PRESS.
- Desktop browser: tap → file downloads with the clean name (anchor fallback).
- Caption with illegal filename characters (e.g. a quote containing `?` or `:`)
  produces a valid, clean filename.

## Out of scope

- Renaming on-disk audio files or changing the scraper/build pipeline.
- Batch save / favorites list / history of saved quotes.
- Any server-side download handling.
