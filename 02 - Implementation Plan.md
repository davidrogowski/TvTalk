# TvTalk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a multi-show personal soundboard web app with config-driven scraper, aggregator, theming UI, and Obsidian documentation.

**Architecture:** Static frontend (`index.html` + generated `shows.js`) loads aggregated quote data from per-show `audio/<id>/quotes.js` files. A Python scraper (stdlib only) downloads MP3s from 101soundboards.com per a YAML registry and round-trips a human-edited `transcripts.txt` for character curation. An aggregator script rebuilds `shows.js` after scraping. Docs are numbered top-level markdown in the project folder, browsable from the parent Obsidian vault.

**Tech Stack:** Python 3.9+ stdlib (urllib, re), PyYAML (optional, with stdlib fallback), vanilla HTML/CSS/JS, Obsidian (Dataview plugin).

---

## File Structure

| Path | Role |
|---|---|
| `00 - Project Overview.md` | Hub note — status, where things live, Dataview index, quick add snippet |
| `01 - Spec.md` | **Already written** (this plan's source of truth) |
| `02 - Implementation Plan.md` | **This file** |
| `03 - Workflow.md` | End-user workflow for adding a show |
| `04 - Troubleshooting.md` | Common scraper / playback issues |
| `README.md` | Plain-text quick-start for non-Obsidian readers |
| `index.html` | Web app: button, picker, theming, audio playback |
| `shows.js` | **Generated** by `build_shows.py` — `const shows = [...]` |
| `scripts/shows.yaml` | Registry: id, name, board_url, status, theme |
| `scripts/scrape_soundboard.py` | Scraper (config-driven + ad-hoc modes) |
| `scripts/build_shows.py` | Aggregator: `audio/*/quotes.js` + `shows.yaml` → `shows.js` |
| `audio/<show-id>/` | Per-show: `*.mp3`, `quotes.js`, `transcripts.txt` |
| `Shows/_Show Template.md` | Frontmatter template for show notes |
| `Shows/The Boys.md` | The Boys show note (seed) |
| `Characters/_Character Template.md` | Frontmatter template for character notes |
| `Characters/Billy Butcher.md` | Seed character note |
| `Characters/Homelander.md` | Seed character note |
| `Maps of Content/All Shows.md` | Dataview table of all shows |
| `Maps of Content/All Characters.md` | Dataview table of all characters |

## Notes on TDD

This is a scaffolding + I/O-heavy project (HTTP scraping, file generation, browser DOM). The spec explicitly puts tests out of scope. Verification per task is therefore: **(a) the file parses / imports**, **(b) `--help` runs**, and **(c) a documented manual-check step**. Where there's pure logic worth verifying (e.g. transcript round-trip parsing), I include a one-shot inline check via `python3 -c '...'` rather than a test framework.

Commits are per-task. Each task is independently revertible.

---

## Task 1: Project skeleton + shows.yaml

**Files:**
- Create: `/Users/dave/Desktop/Obsidian/TvTalk/scripts/shows.yaml`
- Create directories: `audio/`, `scripts/`, `Shows/`, `Characters/`, `Maps of Content/`

- [ ] **Step 1: Create directory tree**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
mkdir -p audio scripts Shows Characters "Maps of Content"
```

- [ ] **Step 2: Write `scripts/shows.yaml`**

```yaml
# Registry of soundboards to scrape.
#
# Fields:
#   id        slug used as folder name in audio/ and as id in shows.js
#   name      human-readable show name shown in the UI
#   board_url 101soundboards.com board URL
#   status    pending | scraped | wip
#   theme     UI colors for this show
#     primary button color, primary text accents
#     accent  secondary accent
#     bg      darkest background color

shows:
  - id: the-boys
    name: "The Boys"
    board_url: "https://www.101soundboards.com/boards/1375005-the-boys-2019"
    status: pending
    theme:
      primary: "#c41e3a"
      accent:  "#d4af37"
      bg:      "#0a0000"
```

- [ ] **Step 3: Verify**

```bash
ls -la /Users/dave/Desktop/Obsidian/TvTalk
```
Expected: `audio`, `scripts`, `Shows`, `Characters`, `Maps of Content` directories present; `01 - Spec.md` and `02 - Implementation Plan.md` already exist.

---

## Task 2: Scraper — module structure and YAML loader

**Files:**
- Create: `scripts/scrape_soundboard.py`

This task creates the file with imports, constants, and the YAML loader (with a tiny stdlib fallback). The CLI and scraping logic come in Task 3; the curation round-trip in Task 4.

- [ ] **Step 1: Write `scripts/scrape_soundboard.py` (initial skeleton)**

```python
#!/usr/bin/env python3
"""
Scrape MP3 clips + transcripts from 101soundboards.com.

Two modes:

  Config-driven (default):
      python3 scripts/scrape_soundboard.py
      python3 scripts/scrape_soundboard.py --show the-boys
      python3 scripts/scrape_soundboard.py --all

  Ad-hoc (legacy, single board):
      python3 scripts/scrape_soundboard.py <board_url> [output_dir]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (personal soundboard project)"
SLEEP_BETWEEN = 1.5
DEFAULT_MIN_WORDS = 1
DEFAULT_MAX_WORDS = 25

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
SHOWS_YAML = REPO_ROOT / "scripts" / "shows.yaml"


# ---------- YAML loading (PyYAML if available, tiny fallback otherwise) ----------

def load_shows_yaml(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data.get("shows", []) if isinstance(data, dict) else []
    except ImportError:
        return _parse_shows_fallback(text)


def _parse_shows_fallback(text: str) -> list[dict]:
    """
    Tiny YAML parser tailored to our shows.yaml shape ONLY.

    Recognizes:
      shows:
        - id: foo
          name: "Foo"
          board_url: "https://..."
          status: pending
          theme:
            primary: "#abc"
            accent:  "#def"
            bg:      "#000"

    Anything else will silently misbehave. Install PyYAML for general use.
    """
    shows: list[dict] = []
    current: dict | None = None
    in_theme = False
    saw_shows = False

    def strip_quotes(v: str) -> str:
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            return v[1:-1]
        return v

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.strip() == "shows:":
            saw_shows = True
            continue
        if not saw_shows:
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped.startswith("- "):
            if current is not None:
                shows.append(current)
            current = {"theme": {}}
            in_theme = False
            stripped = stripped[2:]
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                current[k.strip()] = strip_quotes(v)
            continue

        if current is None:
            continue

        if stripped.rstrip() == "theme:":
            in_theme = True
            continue

        if ":" in stripped:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = strip_quotes(v)
            if in_theme and indent >= 6:
                current["theme"][k] = v
            else:
                in_theme = False
                current[k] = v

    if current is not None:
        shows.append(current)
    return shows


def main() -> None:
    print("scrape_soundboard.py — skeleton (Task 2 of plan)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it parses and YAML loader works**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from scrape_soundboard import load_shows_yaml, SHOWS_YAML
shows = load_shows_yaml(SHOWS_YAML)
print('Loaded', len(shows), 'shows:')
for s in shows:
    print(' -', s.get('id'), '=>', s.get('name'), s.get('theme'))
"
```
Expected output:
```
Loaded 1 shows:
 - the-boys => The Boys {'primary': '#c41e3a', 'accent': '#d4af37', 'bg': '#0a0000'}
```

(Run from `/Users/dave/Desktop/Obsidian/TvTalk`.)

---

## Task 3: Scraper — fetch / parse / download + ad-hoc mode

**Files:**
- Modify: `scripts/scrape_soundboard.py`

Add the network code, the regex extractor, filename sanitizer, length filter, and the `main()` argument parser. Curation round-trip (`transcripts.txt` parsing) lands in Task 4.

- [ ] **Step 1: Append the HTTP + extraction helpers after `_parse_shows_fallback`**

```python
# ---------- HTTP ----------

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


# ---------- Clip extraction ----------

_CLIP_RE = re.compile(
    r'(https://[^"\'<>\s]+?\.mp3\?[^"\'<>\s]+)'
    r'[\s\S]{0,800}?'
    r'<a[^>]*href="https://www\.101soundboards\.com/sounds/[^"]+"[^>]*>'
    r'([^<]+)</a>',
    re.IGNORECASE,
)


def extract_clips(html: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    clips: list[tuple[str, str]] = []
    for mp3_url, transcript in _CLIP_RE.findall(html):
        key = mp3_url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        transcript = re.sub(r"\s+", " ", transcript).strip()
        clips.append((mp3_url, transcript))
    return clips


def safe_filename(transcript: str, mp3_url: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", transcript.lower())[:60].strip("_")
    if not base:
        base = re.sub(r"[^a-z0-9]+", "_", urlparse(mp3_url).path.lower())[-30:].strip("_")
        if not base:
            base = "clip"
    return f"{index:03d}_{base}.mp3"


def passes_length(transcript: str, min_words: int, max_words: int) -> bool:
    n = len(transcript.split())
    return min_words <= n <= max_words
```

- [ ] **Step 2: Add the per-show scrape function and ad-hoc helper**

Append:

```python
# ---------- Curation file I/O (round-trip lands in Task 4) ----------

def read_existing_characters(transcripts_path: Path) -> dict[str, str]:
    """Stub for Task 4 — returns empty so Task 3 still works end-to-end."""
    return {}


def write_transcripts(transcripts_path: Path, entries: list[dict]) -> None:
    """
    Write transcripts.txt in the curation-friendly format. `entries` is a list of
    {filename, transcript, character} dicts in display order.
    """
    lines: list[str] = []
    for e in entries:
        lines.append(e["filename"])
        lines.append(f'  "{e["transcript"]}"')
        lines.append(f'  CHARACTER: {e.get("character", "")}')
        lines.append("")
    transcripts_path.write_text("\n".join(lines), encoding="utf-8")


def write_quotes_js(quotes_path: Path, entries: list[dict], show_id: str) -> None:
    """
    Write audio/<id>/quotes.js. Each entry's audioUrl is project-root-relative:
    `audio/<show-id>/<filename>`.
    """
    out = []
    for e in entries:
        out.append({
            "text": e["transcript"],
            "character": e.get("character", ""),
            "audioUrl": f"audio/{show_id}/{e['filename']}",
        })
    body = json.dumps(out, indent=2, ensure_ascii=False)
    quotes_path.write_text(
        f"// Auto-generated by scrape_soundboard.py. Edit transcripts.txt and re-run.\n"
        f"const quotes = {body};\n",
        encoding="utf-8",
    )


# ---------- Scrape orchestration ----------

def scrape_board(
    board_url: str,
    out_dir: Path,
    show_id: str,
    min_words: int,
    max_words: int,
) -> dict:
    """Scrape one board into out_dir. Returns a stats dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    transcripts_path = out_dir / "transcripts.txt"
    quotes_path = out_dir / "quotes.js"

    existing_chars = read_existing_characters(transcripts_path)

    print(f"Fetching {board_url}")
    html = fetch(board_url)
    clips = extract_clips(html)
    print(f"Found {len(clips)} clips on the page.\n")

    entries: list[dict] = []
    downloaded = skipped_existing = skipped_length = 0

    for i, (mp3_url, transcript) in enumerate(clips, 1):
        if not passes_length(transcript, min_words, max_words):
            skipped_length += 1
            continue

        filename = safe_filename(transcript, mp3_url, i)
        dest = out_dir / filename

        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i}/{len(clips)}] skip (have) {filename}")
            skipped_existing += 1
        else:
            print(f"[{i}/{len(clips)}] download   {filename}")
            try:
                download(mp3_url, dest)
                downloaded += 1
                time.sleep(SLEEP_BETWEEN)
            except Exception as e:
                print(f"   failed: {e}")
                continue

        entries.append({
            "filename": filename,
            "transcript": transcript,
            "character": existing_chars.get(filename, ""),
        })

    write_transcripts(transcripts_path, entries)
    write_quotes_js(quotes_path, entries, show_id)

    stats = {
        "downloaded": downloaded,
        "skipped_existing": skipped_existing,
        "skipped_length": skipped_length,
        "kept": len(entries),
    }
    print(
        f"\nDone [{show_id}]: "
        f"Downloaded {stats['downloaded']}, "
        f"Skipped (already present) {stats['skipped_existing']}, "
        f"Skipped (length filter) {stats['skipped_length']}, "
        f"Total kept {stats['kept']}"
    )
    return stats
```

- [ ] **Step 3: Replace the placeholder `main()` with the real CLI**

Replace the existing `main()` body with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape 101soundboards.com boards. Config-driven by default.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "positional", nargs="*",
        help="Ad-hoc mode: <board_url> [output_dir]. Omit to use shows.yaml.",
    )
    parser.add_argument("--show", help="Only scrape this show id from shows.yaml.")
    parser.add_argument(
        "--all", action="store_true",
        help="Re-scrape every show in shows.yaml, even ones already scraped.",
    )
    parser.add_argument(
        "--min-length", type=int, default=DEFAULT_MIN_WORDS,
        help=f"Minimum transcript word count (default {DEFAULT_MIN_WORDS}).",
    )
    parser.add_argument(
        "--max-length", type=int, default=DEFAULT_MAX_WORDS,
        help=f"Maximum transcript word count (default {DEFAULT_MAX_WORDS}).",
    )
    args = parser.parse_args()

    # Ad-hoc mode
    if args.positional:
        board_url = args.positional[0]
        out_dir = Path(args.positional[1]) if len(args.positional) > 1 else REPO_ROOT / "soundboard_output"
        show_id = out_dir.name
        scrape_board(board_url, out_dir, show_id, args.min_length, args.max_length)
        return

    # Config-driven mode
    if not SHOWS_YAML.exists():
        print(f"shows.yaml not found at {SHOWS_YAML}", file=sys.stderr)
        sys.exit(1)

    shows = load_shows_yaml(SHOWS_YAML)
    if args.show:
        shows = [s for s in shows if s.get("id") == args.show]
        if not shows:
            print(f"No show with id={args.show!r} in shows.yaml", file=sys.stderr)
            sys.exit(1)

    targets = []
    for s in shows:
        sid = s.get("id")
        if not sid:
            continue
        show_dir = AUDIO_ROOT / sid
        already_has_mp3s = show_dir.exists() and any(show_dir.glob("*.mp3"))
        if args.all or s.get("status") == "pending" or not already_has_mp3s:
            targets.append(s)
        else:
            print(f"skip {sid}: already scraped (use --all to force)")

    for s in targets:
        sid = s["id"]
        url = s.get("board_url")
        if not url:
            print(f"skip {sid}: no board_url", file=sys.stderr)
            continue
        scrape_board(url, AUDIO_ROOT / sid, sid, args.min_length, args.max_length)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify CLI parses**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
python3 scripts/scrape_soundboard.py --help
```
Expected: help text appears with `--show`, `--all`, `--min-length`, `--max-length`, and the epilog showing both usage modes. Exit code 0.

Also verify the module imports clean:
```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import scrape_soundboard; print('OK', scrape_soundboard.DEFAULT_MAX_WORDS)"
```
Expected: `OK 25`

---

## Task 4: Scraper — transcripts.txt round-trip

**Files:**
- Modify: `scripts/scrape_soundboard.py` (`read_existing_characters` only)

Replace the stub with a real parser so re-runs preserve user-edited character names.

- [ ] **Step 1: Replace `read_existing_characters`**

Replace the stub body with:

```python
def read_existing_characters(transcripts_path: Path) -> dict[str, str]:
    """
    Parse an existing transcripts.txt and return {filename: character}.

    Expected format per entry (blank line separated):
        001_oi_cunt.mp3
          "Oi, cunt."
          CHARACTER: Billy Butcher
    """
    if not transcripts_path.exists():
        return {}

    result: dict[str, str] = {}
    current_file: str | None = None
    for raw in transcripts_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip():
            current_file = None
            continue
        stripped = line.lstrip()
        if line == stripped and stripped.lower().endswith(".mp3"):
            current_file = stripped
            continue
        if current_file and stripped.upper().startswith("CHARACTER:"):
            value = stripped.split(":", 1)[1].strip()
            result[current_file] = value
    return result
```

- [ ] **Step 2: Inline verification of the round-trip**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
python3 - <<'PY'
import sys, tempfile, os
sys.path.insert(0, "scripts")
from pathlib import Path
from scrape_soundboard import read_existing_characters, write_transcripts

with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "transcripts.txt"
    write_transcripts(p, [
        {"filename": "001_oi.mp3",         "transcript": "Oi, cunt.",     "character": "Billy Butcher"},
        {"filename": "002_diabolical.mp3", "transcript": "Diabolical.",   "character": ""},
        {"filename": "003_world.mp3",      "transcript": "World is mine", "character": "Homelander"},
    ])
    got = read_existing_characters(p)
    assert got == {
        "001_oi.mp3": "Billy Butcher",
        "002_diabolical.mp3": "",
        "003_world.mp3": "Homelander",
    }, got
    print("Round-trip OK:", got)
PY
```
Expected: `Round-trip OK: {'001_oi.mp3': 'Billy Butcher', '002_diabolical.mp3': '', '003_world.mp3': 'Homelander'}`

---

## Task 5: Aggregator — build_shows.py

**Files:**
- Create: `scripts/build_shows.py`

- [ ] **Step 1: Write `scripts/build_shows.py`**

```python
#!/usr/bin/env python3
"""
Aggregate every per-show audio/<id>/quotes.js into shows.js at the project root.

Reads metadata (name, theme) from scripts/shows.yaml. Each show's quotes are
extracted from its quotes.js by stripping the wrapper and parsing the array.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
SHOWS_YAML = REPO_ROOT / "scripts" / "shows.yaml"
OUT_PATH = REPO_ROOT / "shows.js"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_soundboard import load_shows_yaml  # type: ignore


_ARRAY_RE = re.compile(r"const\s+quotes\s*=\s*(\[[\s\S]*?\])\s*;?\s*$", re.MULTILINE)


def parse_quotes_js(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    m = _ARRAY_RE.search(text)
    if not m:
        raise ValueError(f"Could not find `const quotes = [...]` in {path}")
    return json.loads(m.group(1))


def main() -> None:
    if not SHOWS_YAML.exists():
        print(f"shows.yaml not found at {SHOWS_YAML}", file=sys.stderr)
        sys.exit(1)

    registry = load_shows_yaml(SHOWS_YAML)
    out_shows: list[dict] = []

    for s in registry:
        sid = s.get("id")
        if not sid:
            continue
        quotes_path = AUDIO_ROOT / sid / "quotes.js"
        if not quotes_path.exists():
            print(f"skip {sid}: no audio/{sid}/quotes.js yet")
            continue
        try:
            quotes = parse_quotes_js(quotes_path)
        except Exception as e:
            print(f"skip {sid}: failed to parse quotes.js ({e})", file=sys.stderr)
            continue

        out_shows.append({
            "id": sid,
            "name": s.get("name", sid),
            "theme": s.get("theme", {}),
            "quotes": quotes,
        })
        print(f"included {sid}: {len(quotes)} quotes")

    body = json.dumps(out_shows, indent=2, ensure_ascii=False)
    OUT_PATH.write_text(
        f"// Auto-generated by build_shows.py. Do not edit by hand.\n"
        f"const shows = {body};\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT_PATH} ({len(out_shows)} shows)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify with a synthetic fixture**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
mkdir -p audio/the-boys
cat > audio/the-boys/quotes.js <<'JS'
// fixture
const quotes = [
  { "text": "Oi, cunt.",  "character": "Billy Butcher", "audioUrl": "audio/the-boys/001_oi.mp3" },
  { "text": "Diabolical.","character": "Billy Butcher", "audioUrl": "audio/the-boys/002_d.mp3" }
];
JS
python3 scripts/build_shows.py
```
Expected:
```
included the-boys: 2 quotes
Wrote /Users/dave/Desktop/Obsidian/TvTalk/shows.js (1 shows)
```

Then sanity-check the output:
```bash
head -20 shows.js
```
Expected: a `const shows = [...]` declaration containing one entry with `id`, `name: "The Boys"`, `theme: {primary, accent, bg}`, and a `quotes` array of length 2.

- [ ] **Step 3: Clean up the fixture so we don't ship fake data**

```bash
rm audio/the-boys/quotes.js shows.js
rmdir audio/the-boys
```

---

## Task 6: index.html — multi-show frontend

**Files:**
- Create: `index.html`

- [ ] **Step 1: Write `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TvTalk</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Special+Elite&display=swap');

  :root {
    --primary: #c41e3a;
    --accent:  #d4af37;
    --bg:      #0a0000;
    --bg-glow: #2a0a0a;
    --text:    #f0e6d2;
    --muted:   #888;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    min-height: 100vh;
    background: radial-gradient(ellipse at center, var(--bg-glow) 0%, var(--bg) 70%);
    color: var(--text);
    font-family: 'Special Elite', monospace;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 2rem; overflow-x: hidden; position: relative;
    transition: background 0.4s ease;
  }
  body::before {
    content: ''; position: fixed; inset: 0; pointer-events: none; opacity: 0.08;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    mix-blend-mode: overlay; z-index: 1;
  }

  .picker-row {
    position: fixed; top: 1.25rem; right: 1.25rem; z-index: 3;
  }
  .picker-row select {
    background: rgba(0,0,0,0.6);
    color: var(--text);
    border: 1px solid var(--accent);
    font-family: 'Special Elite', monospace;
    font-size: 0.9rem;
    padding: 0.4rem 0.7rem;
    letter-spacing: 0.05em;
    cursor: pointer;
  }
  .picker-row select:focus { outline: 2px solid var(--primary); }

  h1 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(2.5rem, 9vw, 5.5rem); letter-spacing: 0.15em;
    color: var(--accent);
    text-shadow: 3px 3px 0 var(--primary), 6px 6px 0 #000;
    margin-bottom: 0.2em; transform: skewX(-3deg);
    text-align: center;
    transition: color 0.3s, text-shadow 0.3s;
  }
  .subtitle {
    font-size: 0.85rem; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 3rem;
  }

  .button {
    width: 220px; height: 220px; border-radius: 50%; border: none;
    background: radial-gradient(circle at 30% 30%, var(--primary), color-mix(in srgb, var(--primary) 55%, black) 60%, #1a0000);
    color: #fff; font-family: 'Bebas Neue', sans-serif; font-size: 2.5rem;
    letter-spacing: 0.15em; cursor: pointer;
    box-shadow:
      0 0 0 6px var(--bg),
      0 0 0 10px var(--accent),
      0 20px 60px color-mix(in srgb, var(--primary) 50%, transparent),
      inset 0 -10px 30px rgba(0,0,0,0.5),
      inset 0 10px 20px rgba(255,255,255,0.1);
    transition: transform 0.1s ease-out, box-shadow 0.3s, background 0.3s;
    z-index: 2;
  }
  .button:hover {
    transform: scale(1.04);
    box-shadow:
      0 0 0 6px var(--bg),
      0 0 0 10px var(--accent),
      0 20px 80px color-mix(in srgb, var(--primary) 85%, transparent),
      inset 0 -10px 30px rgba(0,0,0,0.5);
  }
  .button:active { transform: scale(0.95); }
  .button.playing { animation: pulse 0.7s infinite; }
  @keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.04); } }

  .quote-display { margin-top: 3rem; max-width: 620px; min-height: 120px; text-align: center; z-index: 2; }
  .quote-text {
    font-size: 1.4rem; line-height: 1.5; color: var(--text); font-style: italic;
    opacity: 0; transition: opacity 0.35s;
  }
  .quote-character {
    margin-top: 1rem; font-family: 'Bebas Neue', sans-serif; font-size: 1.2rem;
    letter-spacing: 0.25em; color: var(--accent); opacity: 0; transition: opacity 0.35s, color 0.3s;
  }
  .quote-source {
    margin-top: 0.5rem; font-size: 0.75rem; letter-spacing: 0.2em; color: var(--muted);
    opacity: 0; transition: opacity 0.35s;
  }
  .visible { opacity: 1 !important; }

  .empty-hint {
    color: var(--muted); font-size: 0.9rem; max-width: 500px; text-align: center;
    line-height: 1.6;
  }
  .empty-hint code {
    background: rgba(255,255,255,0.06); padding: 0.1rem 0.4rem;
    border-radius: 3px; color: var(--accent);
  }

  footer {
    position: fixed; bottom: 1rem; font-size: 0.7rem; color: #555;
    letter-spacing: 0.2em; z-index: 2;
  }
</style>
</head>
<body>
  <div class="picker-row">
    <select id="showPicker" aria-label="Select a show"></select>
  </div>

  <h1 id="title">TV TALK</h1>
  <p class="subtitle" id="subtitle">Press for chaos</p>

  <button class="button" id="quoteBtn">PRESS</button>

  <div class="quote-display">
    <p class="quote-text"      id="quoteText"></p>
    <p class="quote-character" id="quoteChar"></p>
    <p class="quote-source"    id="quoteSource"></p>
  </div>

  <footer>Diabolical · for personal use</footer>

<script src="shows.js"></script>
<script>
  // ----- safety: shows.js missing or empty -----
  const SHOWS = (typeof shows !== 'undefined' && Array.isArray(shows)) ? shows : [];

  const els = {
    picker:  document.getElementById('showPicker'),
    title:   document.getElementById('title'),
    sub:     document.getElementById('subtitle'),
    btn:     document.getElementById('quoteBtn'),
    text:    document.getElementById('quoteText'),
    char:    document.getElementById('quoteChar'),
    source:  document.getElementById('quoteSource'),
  };

  const RANDOM = '__random__';
  let currentSelection = RANDOM;
  let lastKey = null;        // `${showId}::${index}` to avoid immediate repeats
  let currentAudio = null;

  // ----- populate picker -----
  function buildPicker() {
    els.picker.innerHTML = '';
    const randOpt = document.createElement('option');
    randOpt.value = RANDOM;
    randOpt.textContent = '🎲 Random (all shows)';
    els.picker.appendChild(randOpt);
    for (const s of SHOWS) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.name;
      els.picker.appendChild(opt);
    }
    els.picker.value = RANDOM;
  }

  // ----- theme -----
  const DEFAULT_THEME = { primary: '#c41e3a', accent: '#d4af37', bg: '#0a0000' };
  function applyTheme(theme) {
    const t = { ...DEFAULT_THEME, ...(theme || {}) };
    document.documentElement.style.setProperty('--primary', t.primary);
    document.documentElement.style.setProperty('--accent',  t.accent);
    document.documentElement.style.setProperty('--bg',      t.bg);
    document.documentElement.style.setProperty(
      '--bg-glow',
      `color-mix(in srgb, ${t.primary} 18%, ${t.bg})`
    );
  }

  // ----- selection change -----
  function onSelectionChange() {
    currentSelection = els.picker.value;
    lastKey = null;
    if (currentSelection === RANDOM) {
      applyTheme(DEFAULT_THEME);
      els.title.textContent = 'TV TALK';
      els.sub.textContent   = 'Press for chaos';
    } else {
      const show = SHOWS.find(s => s.id === currentSelection);
      if (show) {
        applyTheme(show.theme);
        els.title.textContent = show.name.toUpperCase();
        els.sub.textContent   = 'Press for chaos';
      }
    }
    clearQuote();
  }

  function clearQuote() {
    els.text.classList.remove('visible');
    els.char.classList.remove('visible');
    els.source.classList.remove('visible');
  }

  // ----- quote pool & pick -----
  function buildPool() {
    if (currentSelection === RANDOM) {
      const pool = [];
      for (const s of SHOWS) {
        for (let i = 0; i < s.quotes.length; i++) {
          pool.push({ showId: s.id, showName: s.name, index: i, quote: s.quotes[i] });
        }
      }
      return pool;
    }
    const s = SHOWS.find(x => x.id === currentSelection);
    if (!s) return [];
    return s.quotes.map((q, i) => ({ showId: s.id, showName: s.name, index: i, quote: q }));
  }

  function pick(pool) {
    if (pool.length === 0) return null;
    if (pool.length === 1) return pool[0];
    let chosen;
    do {
      chosen = pool[Math.floor(Math.random() * pool.length)];
    } while (`${chosen.showId}::${chosen.index}` === lastKey);
    lastKey = `${chosen.showId}::${chosen.index}`;
    return chosen;
  }

  function showQuote(item) {
    const q = item.quote;
    clearQuote();
    setTimeout(() => {
      els.text.textContent   = `"${q.text}"`;
      els.char.textContent   = q.character ? `— ${q.character}` : '';
      els.source.textContent = (currentSelection === RANDOM) ? item.showName : '';
      els.text.classList.add('visible');
      if (q.character)                 els.char.classList.add('visible');
      if (currentSelection === RANDOM) els.source.classList.add('visible');
    }, 80);
  }

  function playAudio(q) {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    if (!q.audioUrl) { els.btn.classList.remove('playing'); return; }
    currentAudio = new Audio(q.audioUrl);
    currentAudio.onended = () => els.btn.classList.remove('playing');
    currentAudio.onerror = () => els.btn.classList.remove('playing');
    currentAudio.play().catch(() => els.btn.classList.remove('playing'));
  }

  // ----- empty state -----
  function showEmptyState() {
    els.btn.style.display = 'none';
    const hint = document.createElement('div');
    hint.className = 'empty-hint';
    hint.innerHTML = `
      <p>No shows loaded yet.</p><br>
      <p>Run <code>python3 scripts/scrape_soundboard.py --show the-boys</code>,
      then <code>python3 scripts/build_shows.py</code>,
      then refresh.</p>
    `;
    document.querySelector('.quote-display').appendChild(hint);
  }

  // ----- wire up -----
  buildPicker();
  if (SHOWS.length === 0) {
    showEmptyState();
  } else {
    onSelectionChange();
    els.picker.addEventListener('change', onSelectionChange);
    els.btn.addEventListener('click', () => {
      const pool = buildPool();
      const item = pick(pool);
      if (!item) return;
      showQuote(item);
      els.btn.classList.add('playing');
      playAudio(item.quote);
    });
  }
</script>
</body>
</html>
```

- [ ] **Step 2: Manual smoke test (no audio yet)**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
# Create a tiny placeholder shows.js so the page has something to render.
cat > shows.js <<'JS'
const shows = [
  {
    id: "demo",
    name: "Demo",
    theme: { primary: "#4a7c59", accent: "#f6f4d2", bg: "#0a1410" },
    quotes: [
      { text: "Hello from a placeholder.", character: "Test",  audioUrl: null },
      { text: "If you can read this, the wiring works.", character: "Test", audioUrl: null }
    ]
  }
];
JS
open index.html
```
Expected (manual check): page opens, picker shows "Random (all shows)" and "Demo", clicking PRESS alternates the two quotes. Selecting "Demo" changes the theme (green button + tan accent).

- [ ] **Step 3: Clean up placeholder**

```bash
rm shows.js
```

---

## Task 7: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# TvTalk

A personal soundboard web app. Click a button, hear a random quote from a TV show, see the text. Supports multiple shows with a picker and a "Random (all shows)" mode.

Full docs are in the Obsidian notes alongside this file — see `00 - Project Overview.md`.

## Add a show in 5 commands

```sh
# 1. Edit scripts/shows.yaml — add an entry with id, name, board_url, theme.
$EDITOR scripts/shows.yaml

# 2. Scrape the board.
python3 scripts/scrape_soundboard.py --show <id>

# 3. Curate: open the generated transcripts file and fill in CHARACTER: lines.
$EDITOR audio/<id>/transcripts.txt

# 4. Re-run the scraper to bake character names into quotes.js (no re-downloads).
python3 scripts/scrape_soundboard.py --show <id>

# 5. Rebuild shows.js and open the app.
python3 scripts/build_shows.py && open index.html
```

## Running

Double-click `index.html`. Works in Safari and Firefox over `file://`.

Chrome blocks loading `shows.js` from `file://`. Use a local server:

```sh
python3 -m http.server 8000
# then open http://localhost:8000
```

## Dependencies

- Python 3.9+. Stdlib only is required.
- PyYAML is optional and gives you a real YAML parser if you ever extend `shows.yaml` beyond the simple shape it ships with: `pip install pyyaml`.

## Project layout

See `01 - Spec.md` for the full project layout and design decisions.
```

- [ ] **Step 2: Verify**

```bash
ls /Users/dave/Desktop/Obsidian/TvTalk/README.md
```
Expected: file exists.

---

## Task 8: Obsidian docs — hub + workflow + troubleshooting

**Files:**
- Create: `00 - Project Overview.md`
- Create: `03 - Workflow.md`
- Create: `04 - Troubleshooting.md`

- [ ] **Step 1: Write `00 - Project Overview.md`**

```markdown
# TvTalk

A personal soundboard web app. Press a button → random quote from a TV show plays + appears on screen. Multiple shows with a picker; "Random (all shows)" is the default.

## Status (2026-05-27)

- ✅ Scaffolded
- ⏳ Pending: scrape The Boys — see [[03 - Workflow|the workflow]]

## Where things live

| Thing | Location |
|---|---|
| Spec (source of truth) | [[01 - Spec]] |
| Implementation plan | [[02 - Implementation Plan]] |
| Adding a new show | [[03 - Workflow]] |
| Common issues | [[04 - Troubleshooting]] |
| Web app | `index.html` |
| Scraper | `scripts/scrape_soundboard.py` |
| Aggregator | `scripts/build_shows.py` |
| Show registry | `scripts/shows.yaml` |
| Audio + per-show data | `audio/<show-id>/` |
| Aggregated data (generated) | `shows.js` |

## Active shows

```dataview
TABLE status, board_url AS "Board", clip_count, curated_count
FROM "Shows"
WHERE type = "show"
SORT file.name
```

## Quick add

```sh
python3 scripts/scrape_soundboard.py --show <id>
$EDITOR audio/<id>/transcripts.txt
python3 scripts/scrape_soundboard.py --show <id>
python3 scripts/build_shows.py
open index.html
```

See [[03 - Workflow]] for the full version.
```

- [ ] **Step 2: Write `03 - Workflow.md`**

```markdown
# Workflow — Adding a new show

## 1. Find a 101soundboards board

Browse https://www.101soundboards.com/ and copy the URL. It looks like:

```
https://www.101soundboards.com/boards/1234567-show-name-year
```

The slug after the number isn't load-bearing; the number is what matters.

## 2. Add the show to `scripts/shows.yaml`

```yaml
shows:
  - id: short-slug                   # used as folder name + show id in JS
    name: "Show Name"
    board_url: "https://www.101soundboards.com/boards/..."
    status: pending
    theme:
      primary: "#hex"                # button color
      accent:  "#hex"                # gold-equivalent
      bg:      "#hex"                # darkest background
```

Theme colors: pick anything that fits the show's vibe. The page interpolates a glow color from `primary` + `bg`, so you don't need to set that separately.

## 3. Scrape

```sh
python3 scripts/scrape_soundboard.py --show <id>
```

Goes through the board, downloads every MP3 to `audio/<id>/`, writes `transcripts.txt` and `quotes.js`. Politely paced (1.5s between downloads).

Optional flags:
- `--min-length 1 --max-length 25` — word-count filter on the transcript. Default keeps clips that are 1-25 words. Set `--max-length 100` if you want longer scene transcripts.
- `--all` — re-scrape everything, even shows already done.

## 4. Curate

Open `audio/<id>/transcripts.txt`. It looks like:

```
001_oi_cunt.mp3
  "Oi, cunt."
  CHARACTER:

002_diabolical.mp3
  "Diabolical."
  CHARACTER:
```

Fill in the `CHARACTER:` lines for the ones you want. Delete entire blocks for clips you want to drop. Save.

## 5. Re-run the scraper

```sh
python3 scripts/scrape_soundboard.py --show <id>
```

It reads your edited `transcripts.txt`, preserves the `CHARACTER:` values, and rewrites `quotes.js` with character names baked in. Already-downloaded MP3s are not re-downloaded.

## 6. Rebuild the aggregated data

```sh
python3 scripts/build_shows.py
```

Writes `shows.js` at the project root with every show's data combined.

## 7. Add an Obsidian show note

Copy `Shows/_Show Template.md` to `Shows/<Show Name>.md`. Fill in the frontmatter. The Dataview table on [[00 - Project Overview]] picks it up automatically.

## 8. Open the app

Safari/Firefox:
```sh
open index.html
```

Chrome (blocks `file://` script loads):
```sh
python3 -m http.server 8000
# open http://localhost:8000
```

Pick your new show from the dropdown to verify it loads and themes correctly.
```

- [ ] **Step 3: Write `04 - Troubleshooting.md`**

```markdown
# Troubleshooting

## "Page loads but no shows in the picker"

`shows.js` is missing, empty, or didn't get rebuilt after a scrape.
Run `python3 scripts/build_shows.py`.

If you're in Chrome and the file *exists*, Chrome blocks the `<script src>` load over `file://`. Use a local server:

```sh
python3 -m http.server 8000
```

## "Button does nothing when I click"

Browsers gate autoplay behind a user gesture; the button click satisfies that, so this is rarely the audio. More likely: `audioUrl` is `null` (transcript was kept but the MP3 download failed), or the path is wrong. Check the browser console.

## "Scraper finds 0 clips"

101soundboards' markup changed. The regex in `scripts/scrape_soundboard.py` (look for `_CLIP_RE`) needs to be adjusted. Open the board page in a browser, View Source, and find one MP3 URL and its accompanying transcript link — adjust the regex to match.

## "My CHARACTER: edits disappeared"

You ran the scraper from a different working directory and it wrote to a different `transcripts.txt`. The scraper computes paths relative to its own location (`<repo>/audio/<id>/`), so running it from anywhere with `python3 /path/to/scripts/scrape_soundboard.py --show ...` is safe, but the ad-hoc mode (passing a board URL directly) writes to whatever output dir you pass — don't mix the two for the same show.

## "PyYAML not installed"

You don't need it. The scraper falls back to a small parser tailored to the shape of `shows.yaml`. Install it (`pip install pyyaml`) only if you want to add nested or non-standard YAML structures.

## "Audio plays but feels muffled / inconsistent"

Source-board clips vary in encoding. Not fixable from this app — re-rip from the show if you care.
```

- [ ] **Step 4: Verify**

```bash
ls "/Users/dave/Desktop/Obsidian/TvTalk/" | grep -E '^(00|03|04|README)'
```
Expected: `00 - Project Overview.md`, `03 - Workflow.md`, `04 - Troubleshooting.md`, `README.md`.

---

## Task 9: Obsidian docs — Show/Character templates + seed notes

**Files:**
- Create: `Shows/_Show Template.md`
- Create: `Shows/The Boys.md`
- Create: `Characters/_Character Template.md`
- Create: `Characters/Billy Butcher.md`
- Create: `Characters/Homelander.md`
- Create: `Maps of Content/All Shows.md`
- Create: `Maps of Content/All Characters.md`

- [ ] **Step 1: Write `Shows/_Show Template.md`**

```markdown
---
type: show
status: wip
board_url: ""
show_id: ""
clip_count: 0
curated_count: 0
theme_primary: ""
theme_accent: ""
tags: [show]
---

# {{title}}

Notes, favorite quotes, character list, etc.

## Characters

- [[ ]]

## Favorite lines

> ""
```

- [ ] **Step 2: Write `Shows/The Boys.md`**

```markdown
---
type: show
status: wip
board_url: "https://www.101soundboards.com/boards/1375005-the-boys-2019"
show_id: the-boys
clip_count: 0
curated_count: 0
theme_primary: "#c41e3a"
theme_accent: "#d4af37"
tags: [show]
---

# The Boys

Amazon's adaptation of the Garth Ennis comic. Superheroes are corporate-sponsored monsters; the only people willing to keep them in check are the eponymous Boys.

## Characters

- [[Billy Butcher]]
- [[Homelander]]

## Notes

Scrape pending. Once `audio/the-boys/transcripts.txt` is curated, update `clip_count` and `curated_count` here.
```

- [ ] **Step 3: Write `Characters/_Character Template.md`**

```markdown
---
type: character
show: "[[ ]]"
actor: ""
tags: [character]
---

# {{title}}

## Favorite lines

> ""

## Notes
```

- [ ] **Step 4: Write `Characters/Billy Butcher.md`**

```markdown
---
type: character
show: "[[The Boys]]"
actor: Karl Urban
tags: [character]
---

# Billy Butcher

Leader of the Boys. East London, ex-SAS, deeply ill-adjusted.

## Favorite lines

> "Oi, cunt."
> "Diabolical."
```

- [ ] **Step 5: Write `Characters/Homelander.md`**

```markdown
---
type: character
show: "[[The Boys]]"
actor: Antony Starr
tags: [character]
---

# Homelander

Vought's flagship supe. All-American smile over a void.

## Favorite lines

> ""
```

- [ ] **Step 6: Write `Maps of Content/All Shows.md`**

```markdown
# All Shows

```dataview
TABLE status, show_id, clip_count, curated_count, board_url AS "Board"
FROM "Shows"
WHERE type = "show"
SORT file.name
```
```

- [ ] **Step 7: Write `Maps of Content/All Characters.md`**

```markdown
# All Characters

```dataview
TABLE show, actor
FROM "Characters"
WHERE type = "character"
SORT file.name
```
```

- [ ] **Step 8: Verify**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
ls Shows Characters "Maps of Content"
```
Expected:
```
Characters:
_Character Template.md
Billy Butcher.md
Homelander.md

Maps of Content:
All Characters.md
All Shows.md

Shows:
_Show Template.md
The Boys.md
```

---

## Task 10: Final verification

**Files:** none modified.

- [ ] **Step 1: Re-confirm both scripts parse and `--help` works**

```bash
cd /Users/dave/Desktop/Obsidian/TvTalk
python3 -c "import sys; sys.path.insert(0,'scripts'); import scrape_soundboard, build_shows; print('imports OK')"
python3 scripts/scrape_soundboard.py --help
python3 scripts/build_shows.py
```
Expected:
- `imports OK`
- scraper help text including `--show`, `--all`, `--min-length`, `--max-length`
- `build_shows.py` runs, prints `Wrote .../shows.js (0 shows)` (no per-show quotes.js yet, so empty array — fine).

- [ ] **Step 2: Confirm full file inventory**

```bash
find /Users/dave/Desktop/Obsidian/TvTalk -type f \
  ! -path '*/.DS_Store' \
  ! -path '*/.obsidian/*' \
  | sort
```
Expected: everything from the File Structure table at the top, minus any `audio/<id>/` content (we never actually scrape during setup).

- [ ] **Step 3: Open the app in browser, verify empty state**

```bash
open /Users/dave/Desktop/Obsidian/TvTalk/index.html
```
Expected: page loads, picker has only "🎲 Random (all shows)" (since `shows.js` is `const shows = []`), and the empty-state hint appears with the scrape command. After step 1's `build_shows.py` run, `shows.js` exists but `shows = []`, which is the correct empty state — the page won't crash.

---

## Self-Review Pass

**Spec coverage check** against `01 - Spec.md`:

| Spec requirement | Task |
|---|---|
| Project at `/Users/dave/Desktop/Obsidian/TvTalk/` w/ numbered docs | Task 1 + Task 8 |
| `scripts/shows.yaml` seeded with The Boys | Task 1 |
| Scraper: config-driven + ad-hoc modes | Task 3 |
| Scraper: `--show`, `--all`, `--min-length`, `--max-length` | Task 3 |
| Scraper: per-show folders | Task 3 |
| Scraper: polite 1.5s sleep, resumable | Task 3 |
| Scraper: transcripts.txt round-trip | Task 4 |
| Scraper: kept / skipped counts | Task 3 |
| `build_shows.py` aggregator | Task 5 |
| `index.html` with picker, theming, never-repeat | Task 6 |
| `index.html` loads `shows.js` via script tag | Task 6 |
| `audioUrl` is project-root-relative | Task 3 (`write_quotes_js`) |
| README with 5-command quick-start | Task 7 |
| Obsidian hub (`00 - Project Overview.md`) with Dataview | Task 8 |
| Workflow doc | Task 8 |
| Troubleshooting doc | Task 8 |
| Show + Character templates + seed notes | Task 9 |
| Maps of Content with Dataview tables | Task 9 |
| Final verification: scraper parses + `--help` works | Task 10 |

All spec items mapped. ✅

**Placeholder scan:** no TBDs / "fill in details" / "similar to Task N" — every step has the actual content.

**Type/name consistency:**
- `load_shows_yaml` → used in scraper (Task 3) and aggregator (Task 5). ✅
- `read_existing_characters` / `write_transcripts` / `write_quotes_js` / `scrape_board` — defined Task 3, refined Task 4. ✅
- `audioUrl` format `audio/<id>/<filename>` — set in `write_quotes_js` (Task 3), parsed by `parse_quotes_js` (Task 5), consumed in `index.html` (Task 6). ✅
- CSS variables `--primary` / `--accent` / `--bg` / `--bg-glow` — defined in `:root`, mutated in `applyTheme()`. ✅
- The `__random__` sentinel matches between picker option value and `currentSelection` check. ✅
