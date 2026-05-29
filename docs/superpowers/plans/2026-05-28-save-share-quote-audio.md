# Save / Share the Current Quote's Audio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subtle control to the quote display that lets a user save or send the mp3 of the quote currently on screen, with a clean `Show - Caption.mp3` filename, optimized for iPhone Safari.

**Architecture:** Everything lives in `index.html`. A muted iOS-style share glyph is added to the `.quote-display`, hidden until a quote plays. Tapping it fetches the (small, same-origin) mp3, wraps it in a `File` with a clean name, and calls the Web Share API (`navigator.share({ files })`) — the native iOS "Save to Files / AirDrop / Messages" flow. On browsers without file-share support (desktop), it falls back to an `<a download>` click. The on-disk audio files are never renamed.

**Tech Stack:** Vanilla JS + CSS in a single static HTML file. Web Share API Level 2, `fetch`/`Blob`/`File`. Node (already installed, v24) is used only to unit-check the one pure helper function.

**Spec:** `docs/superpowers/specs/2026-05-28-save-share-quote-audio-design.md`

---

## File Structure

- **Modify only:** `index.html`
  - CSS: add a `.quote-save` rule block (near the existing `.quote-source` rule, ~line 205).
  - Markup: add one `<a id="quoteSave">` element inside `.quote-display` (~line 261).
  - JS: add `share` to the `els` object; add `sanitizeFilename` + `buildClipFilename` + `triggerDownload` + `saveCurrentQuote` helpers; add a `currentItem` variable; reveal in `showQuote`, hide in `clearQuote`; attach a click handler in the init block.

No other files change. Shareable links (`show id + index`) and the build pipeline are untouched.

---

## Task 1: Pure helpers — `sanitizeFilename` and `buildClipFilename`

**Files:**
- Modify: `index.html` (JS, insert after the `pick()` function, before `showQuote`, ~line 472)
- Test: `/tmp/test_filename.mjs` (throwaway Node check — not committed)

- [ ] **Step 1: Write the failing test**

Create `/tmp/test_filename.mjs` with the expected behavior. The two helpers are pasted in by copy (they have no DOM/browser deps), then asserted:

```js
// --- paste of the helpers under test (kept in sync with index.html) ---
function sanitizeFilename(text) {
  const cleaned = (text || '')
    .replace(/[\/\\:*?"<>|]/g, ' ')   // chars illegal in filenames -> space
    .replace(/\s+/g, ' ')
    .trim();
  return cleaned || 'clip';
}
function buildClipFilename(showName, text) {
  return sanitizeFilename(`${showName} - ${text}`) + '.mp3';
}

// --- assertions ---
import assert from 'node:assert';
assert.strictEqual(
  buildClipFilename('The Boys', "I'll break your legs"),
  "The Boys - I'll break your legs.mp3");
// illegal chars in the caption are stripped
assert.strictEqual(
  buildClipFilename('Show', 'Why? Because: yes'),
  'Show - Why Because yes.mp3');
// runs of whitespace collapse
assert.strictEqual(
  buildClipFilename('A', 'b   c'),
  'A - b c.mp3');
// empty caption still yields a valid name (falls back to "clip")
assert.strictEqual(
  sanitizeFilename('////'),
  'clip');
console.log('OK');
```

- [ ] **Step 2: Run it to confirm the assertions are what we want**

Run: `node /tmp/test_filename.mjs`
Expected: prints `OK` (this validates the helper logic in isolation before it goes into the HTML).

> Note: this is a copy-based check because the helpers live inline in `index.html`. If you change the helper bodies, update this file to match.

- [ ] **Step 3: Add the helpers to `index.html`**

Insert immediately after the `pick(pool)` function (which ends with `}` at ~line 472) and before `function showQuote(item)`:

```js
  function sanitizeFilename(text) {
    const cleaned = (text || '')
      .replace(/[\/\\:*?"<>|]/g, ' ')   // chars illegal in filenames -> space
      .replace(/\s+/g, ' ')
      .trim();
    return cleaned || 'clip';
  }

  function buildClipFilename(showName, text) {
    return sanitizeFilename(`${showName} - ${text}`) + '.mp3';
  }
```

- [ ] **Step 4: Re-run the Node check to confirm parity**

Run: `node /tmp/test_filename.mjs`
Expected: prints `OK` (the version pasted in the test matches what you inserted).

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: add filename helpers for quote audio save"
```

---

## Task 2: The share control — markup + CSS

**Files:**
- Modify: `index.html` (markup ~line 261; CSS ~line 205)

- [ ] **Step 1: Add the CSS**

Insert a new rule block right after the `.quote-source { ... }` rule (the rule that ends `...opacity: 0; transition: opacity 0.35s; }`, ~line 205) and before `.visible { ... }`:

```css
  .quote-save {
    display: inline-flex; align-items: center; justify-content: center;
    margin-top: 1.25rem; padding: 0.4rem;
    color: var(--muted); line-height: 0;
    opacity: 0; pointer-events: none;
    transition: opacity 0.35s, color 0.2s;
    cursor: pointer;
  }
  .quote-save.visible { opacity: 0.6; pointer-events: auto; }
  .quote-save:hover  { color: var(--accent); opacity: 1; }
  .quote-save:focus-visible { outline: 1px solid var(--accent); outline-offset: 4px; }
```

This mirrors the caption fade pattern (`opacity` + `.visible`), and `pointer-events: none` keeps the invisible idle control un-tappable.

- [ ] **Step 2: Add the markup**

Inside `.quote-display`, add the control after the `quote-source` paragraph (after the line `<p class="quote-source" id="quoteSource"></p>`, ~line 261):

```html
    <a class="quote-save" id="quoteSave" href="#" role="button"
       aria-label="Save or share this clip" title="Save or share this clip">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
           stroke="currentColor" stroke-width="1.6"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 15V3"/>
        <path d="M8 7l4-4 4 4"/>
        <path d="M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7"/>
      </svg>
    </a>
```

- [ ] **Step 3: Verify it renders and stays hidden at idle**

Run: `python3 -m http.server 8000` (from the repo root), open `http://localhost:8000`.
Expected: page loads normally; **no** share glyph is visible before pressing PRESS (it's `opacity: 0`). The button area is not clickable yet.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add subtle share-glyph control to quote display (hidden)"
```

---

## Task 3: Reveal on play, hide on switch (`currentItem`, `showQuote`, `clearQuote`)

**Files:**
- Modify: `index.html` (els object ~line 280; `clearQuote` ~line 440; `showQuote` ~line 474; add a `currentItem` var near the other `let`s ~line 290)

- [ ] **Step 1: Add `share` to the `els` object**

In the `els` object (ends with `source: document.getElementById('quoteSource'),` ~line 280), add:

```js
    save:    document.getElementById('quoteSave'),
```

- [ ] **Step 2: Add a module-level `currentItem`**

Next to the other state declarations (after `let currentAudio = null;` ~line 290), add:

```js
  let currentItem = null;   // the quote currently on screen, for save/share
```

- [ ] **Step 3: Track the item and reveal the control in `showQuote`**

`showQuote(item)` currently starts by reading `q`/`show`/`textStyle` then calls `clearQuote()` and a `setTimeout`. Set `currentItem` at the top of the function (right after `const q = item.quote;`):

```js
    currentItem = item;
```

Then inside the existing `setTimeout(() => { ... }, 80)` block, after the line `els.text.classList.add('visible');`, add:

```js
      if (q.audioUrl) els.save.classList.add('visible');
```

(No save control for a quote that has no audio.)

- [ ] **Step 4: Hide the control in `clearQuote`**

`clearQuote()` currently removes `visible` from text/char/source. Add a line so it also hides the save control:

```js
    els.save.classList.remove('visible');
```

- [ ] **Step 5: Verify reveal/hide behavior in the browser**

Run: `python3 -m http.server 8000`, open `http://localhost:8000`.
Expected:
- On load: no glyph.
- Press PRESS: caption appears and the glyph fades in with it.
- Open the picker and switch to a different show: the glyph disappears (via `clearQuote`).
- Press PRESS again: glyph reappears.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: reveal share control with the current quote, hide on switch"
```

---

## Task 4: Save / share behavior + click handler

**Files:**
- Modify: `index.html` (JS: add `triggerDownload` + `saveCurrentQuote` after `buildClipFilename` ~line 484; add click handler in the init `else` block ~line 527)

- [ ] **Step 1: Add `triggerDownload` and `saveCurrentQuote`**

Insert after `buildClipFilename` (and before `showQuote`):

```js
  function triggerDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function saveCurrentQuote() {
    if (!currentItem || !currentItem.quote.audioUrl) return;
    const url = currentItem.quote.audioUrl;
    const filename = buildClipFilename(currentItem.showName, currentItem.quote.text);

    // Primary: native share sheet with the file (works on iOS Safari).
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        const blob = await resp.blob();
        const file = new File([blob], filename, { type: 'audio/mpeg' });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file] });
          return;
        }
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return;  // user dismissed the sheet
      // otherwise fall through to the download fallback
    }

    // Fallback: anchor download (desktop / no file-share support).
    triggerDownload(url, filename);
  }
```

- [ ] **Step 2: Attach the click handler**

In the init `else` block (where `SHOWS.length > 0`), alongside the other listener wiring (e.g. right before `els.btn.addEventListener('click', ...)` ~line 530), add:

```js
    els.save.addEventListener('click', (e) => {
      e.preventDefault();          // it's an <a href="#">; never navigate
      saveCurrentQuote();
    });
```

- [ ] **Step 3: Desktop verification (fallback path)**

Run: `python3 -m http.server 8000`, open `http://localhost:8000` in a desktop browser (Chrome/Firefox — these lack `navigator.canShare` for files, so they exercise the fallback).
Expected: Press PRESS, click the glyph → the mp3 downloads named like `<Show> - <Caption>.mp3` (e.g. `The Boys - I'll break your legs.mp3`) and plays when opened.

- [ ] **Step 4: Verify cancel does nothing harmful**

Still desktop: click the glyph rapidly / repeatedly.
Expected: each click downloads the current clip; no console errors; the page never navigates to `#`.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: save/share current quote audio (share sheet + download fallback)"
```

---

## Task 5: iPhone Safari verification + finalize

**Files:** none (verification only)

- [ ] **Step 1: Serve on the LAN (or deploy) for a real iPhone**

Option A — local: run `python3 -m http.server 8000`, find the Mac's LAN IP (`ipconfig getifaddr en0`), open `http://<ip>:8000` in iPhone Safari.
Note: Web Share with files requires a **secure context**. `http://<LAN-ip>` is *not* secure, so the share path may be unavailable locally and you'll see the fallback. To truly exercise the share sheet, deploy to the HTTPS site instead.
Option B — deploy (authoritative test): `wrangler deploy`, then open `https://tvtalk.davrogowski.workers.dev` in iPhone Safari.

- [ ] **Step 2: Verify the iOS share flow**

On iPhone Safari (HTTPS):
Expected:
- Press PRESS → glyph fades in.
- Tap glyph → the iOS share sheet appears.
- Choose **Save to Files** → the saved file is named `<Show> - <Caption>.mp3` and plays.
- Choose **Messages/AirDrop** → the clip sends with the clean name.
- Dismissing the sheet does nothing (no error, no navigation).

- [ ] **Step 3: Verify subtlety / layout on mobile**

Expected: the glyph is small and muted, sits below the source line, doesn't crowd the caption, and the tap target is comfortable.

- [ ] **Step 4: Final commit (if any tweaks were needed)**

```bash
git add index.html
git commit -m "polish: quote save/share control after device verification"
```

If a deploy was done, mention it in the summary so the live site state is clear.

---

## Self-Review

**Spec coverage:**
- Subtle affordance, appears after play, hidden idle / on switch → Task 2 (CSS/markup), Task 3 (reveal/hide). ✓
- iOS share glyph → Task 2 (SVG). ✓
- `Show - Caption.mp3` name + sanitization + on-disk files untouched → Task 1 (helpers), Task 4 (used in `saveCurrentQuote`); no file rename anywhere. ✓
- Web Share primary, `<a download>` fallback, feature-detect → Task 4. ✓
- `item.showName` available in both modes → used in `buildClipFilename(currentItem.showName, ...)`. ✓
- Error handling: `AbortError` swallowed, fetch failure falls back → Task 4 Step 1. ✓
- Testing: pure helper checked via Node (Task 1); manual browser desktop (Task 4) + iPhone (Task 5). ✓
- Out of scope items (rename files, favorites, server handling) → not present in any task. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step has complete code. ✓

**Type/name consistency:** `sanitizeFilename`, `buildClipFilename`, `triggerDownload`, `saveCurrentQuote`, `currentItem`, `els.save`, `#quoteSave`/`.quote-save` used consistently across tasks. `currentItem` is the full `item` object (`{showId, showName, index, quote}`), and `saveCurrentQuote` reads `currentItem.quote.audioUrl` / `currentItem.quote.text` / `currentItem.showName` — matching the shape `buildPool()` produces. ✓
