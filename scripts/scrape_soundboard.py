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
import html
import json
import re
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import certifi

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
        # Strip comments, but only when `#` is at line start or preceded by
        # whitespace — otherwise `#` inside a hex color value like "#c41e3a"
        # would be mistaken for a comment marker.
        line = re.sub(r"(?:^|\s)#.*$", "", raw).rstrip()
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


# ---------- HTTP ----------

# Homebrew Python on macOS often points at an empty openssl CA bundle, so build
# our own SSL context from certifi's bundle to make this script portable.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as r:
        return r.read().decode("utf-8", errors="replace")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as r, open(dest, "wb") as f:
        f.write(r.read())


# ---------- Clip extraction ----------

_API_URL = "https://www.101soundboards.com/api/v1/boards/{board_id}?limit=2000"
_ASSET_HOST = "https://www.101soundboards.com"
_BOARD_ID_RE = re.compile(r"/boards/(\d+)")
# The API hard-caps a single request at 2000 sounds and ignores offset/page. A
# board with more clips (e.g. 21 Jump Street, 2135) is silently truncated to the
# first 2000 in its default (alpha) sort. Re-querying with sort=id surfaces a
# different 2000-slice; merging the two recovers nearly all clips on such boards.
_API_PAGE_LIMIT = 2000
_API_ALT_SORT_URL = "https://www.101soundboards.com/api/v1/boards/{board_id}?limit=2000&sort=id"

# Legacy community-uploaded boards (board_id < 1M, slug ends in -soundboard) serve a
# notification-ding-poisoned audio file to non-browser User-Agents. Modern official
# boards (7-digit ID, year-suffix slug like -2019) serve clean audio. After downloading
# from a legacy board, we trim TRIM_SECONDS off the front of each MP3 to remove the ding.
_LEGACY_ID_THRESHOLD = 1_000_000
TRIM_SECONDS = 1.0


def is_legacy_board(board_url: str) -> bool:
    m = _BOARD_ID_RE.search(board_url)
    return bool(m) and int(m.group(1)) < _LEGACY_ID_THRESHOLD


def should_trim_board(board_url: str, no_trim: bool = False) -> bool:
    """
    Whether to ding-trim clips from this board.

    A board is ding-poisoned (≈1s notification chime prepended) only when it's a
    legacy community board: board ID < 1M AND the slug ends in `-soundboard`.
    Low-ID boards with a modern `-YYYY` slug (e.g. 21 Jump Street, ID 119606,
    slug -2012) serve clean audio — trimming them would chop 1s of real audio.
    `no_trim` is an explicit escape hatch that suppresses the trim regardless.

    NOTE: do not try to detect poisoning by comparing the downloaded file's
    duration to the API's sound_duration — they match even when poisoned, because
    the API reports the with-ding length.
    """
    # The slug (not the 101soundboards.com domain, which always contains the word)
    # must END in -soundboard. Tolerate a trailing slash / query string.
    slug_is_soundboard = bool(re.search(r"-soundboard/?(\?|$)", board_url.lower()))
    return is_legacy_board(board_url) and slug_is_soundboard and not no_trim


def trim_mp3_inplace(path: Path, seconds: float) -> bool:
    """Trim `seconds` off the front of an MP3 file in place. Returns True on success."""
    # Use ".trimming.mp3" so ffmpeg can detect the output format from the extension.
    tmp = path.with_name(path.stem + ".trimming" + path.suffix)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(seconds), "-i", str(path), "-c", "copy", str(tmp)],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(path)
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    if tmp.exists():
        tmp.unlink()
    return False


def _to_sentence_case(text: str) -> str:
    """Convert an all-uppercase string to sentence case. No-op if not fully uppercase."""
    if not text or text.upper() != text or text == text.lower():
        return text
    result = text.lower()
    result = result[0].upper() + result[1:]
    result = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), result)
    return re.sub(r"\bi\b", "I", result)


_NWORD_RE = re.compile(r"\bnigg[a-z]*\b", re.IGNORECASE)


def _censor_nword(text: str) -> str:
    """Blur the n-word (and its variants/plurals): keep the first letter, star the rest."""
    return _NWORD_RE.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)


def merge_sound_pages(pages: list[list[dict]]) -> list[dict]:
    """
    Merge multiple API 'sounds' pages into one list, deduping by sound id and
    preserving first-seen order. Used to recover clips from boards larger than
    the API's 2000-sound page cap by combining differently-sorted pages.
    """
    seen: set = set()
    merged: list[dict] = []
    for page in pages:
        for sound in page:
            sid = sound.get("id")
            if sid in seen:
                continue
            seen.add(sid)
            merged.append(sound)
    return merged


def fetch_sounds(
    board_url: str,
    *,
    exclude_prefix: str = "",
    case_style: str = "preserve",
    censor_nword: bool = False,
) -> list[tuple[str, str]]:
    """Fetch a board's sounds via the JSON API. Returns [(mp3_url, transcript), ...]."""
    m = _BOARD_ID_RE.search(board_url)
    if not m:
        raise ValueError(f"Could not extract board id from URL: {board_url}")
    board_id = m.group(1)
    payload = json.loads(fetch(_API_URL.format(board_id=board_id)))
    sounds = payload.get("data", {}).get("sounds", [])
    # If the first (alpha-sorted) page is full, the board may exceed the 2000 cap;
    # pull the sort=id page too and merge to recover the truncated tail.
    if len(sounds) >= _API_PAGE_LIMIT:
        alt = json.loads(fetch(_API_ALT_SORT_URL.format(board_id=board_id)))
        sounds = merge_sound_pages([sounds, alt.get("data", {}).get("sounds", [])])

    exclude_prefix_lower = exclude_prefix.strip().lower()

    seen: set[str] = set()
    clips: list[tuple[str, str]] = []
    for s in sounds:
        url = s.get("sound_file_url") or ""
        if not url:
            continue
        if url.startswith("/"):
            url = _ASSET_HOST + url
        url = html.unescape(url)
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        transcript = re.sub(r"\s+", " ", html.unescape(s.get("sound_transcript") or "")).strip()
        # Drop user-uploaded hashtag tag-clouds, e.g. "Quote text #tag1 #tag2" -> "Quote text".
        transcript = re.sub(r"\s*#.*$", "", transcript).strip()
        if exclude_prefix_lower and transcript.lower().startswith(exclude_prefix_lower):
            continue
        if case_style == "fix_all_caps":
            transcript = _to_sentence_case(transcript)
        if censor_nword:
            transcript = _censor_nword(transcript)
        clips.append((url, transcript))
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


# ---------- Curation file I/O ----------

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


def read_existing_transcripts(transcripts_path: Path) -> dict[str, str]:
    """
    Parse an existing transcripts.txt and return {filename: transcript text}.

    Used with the per-show `preserve_transcripts` flag: when a board's
    auto-generated captions are bad (e.g. words run together with no spaces),
    you hand-fix the quoted transcript lines in transcripts.txt and re-run; this
    reads those edits back so they survive even though the API still serves the
    original text. Keyed by filename, which stays stable (it is derived from the
    original API transcript, not the edited one).
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
        if current_file and len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
            result[current_file] = stripped[1:-1]
    return result


def read_existing_repeats(transcripts_path: Path) -> dict[str, int]:
    """
    Parse an existing transcripts.txt and return {filename: repeat_count} for any
    entry carrying a `REPEAT: N` line. Filenames without the line are omitted
    (callers default them to 1). Powers durable per-clip weighting: a clip with
    REPEAT: 3 is emitted three times into quotes.js, so it plays ~3x as often,
    and that survives re-scrapes because it lives in the curated file.
    """
    if not transcripts_path.exists():
        return {}

    result: dict[str, int] = {}
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
        if current_file and stripped.upper().startswith("REPEAT:"):
            try:
                result[current_file] = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
    return result


def manual_entries(
    existing_transcripts: dict[str, str],
    existing_chars: dict[str, str],
    existing_repeats: dict[str, int],
    board_filenames: set[str],
    present_files: set[str],
) -> list[dict]:
    """
    Entries for hand-added clips: listed in the curated transcripts.txt, present
    on disk, but NOT produced by any configured board. The board loop can't
    regenerate these (there's no API source), so without this they'd vanish on
    every re-scrape. Returned in transcripts.txt order. Entries whose mp3 file is
    missing from disk are skipped (stale references).
    """
    out: list[dict] = []
    for fn, text in existing_transcripts.items():
        if fn in board_filenames or fn not in present_files:
            continue
        out.append({
            "filename": fn,
            "transcript": text,
            "character": existing_chars.get(fn, ""),
            "repeat": existing_repeats.get(fn, 1),
        })
    return out


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
        repeat = int(e.get("repeat", 1))
        if repeat > 1:
            lines.append(f"  REPEAT: {repeat}")
        lines.append("")
    transcripts_path.write_text("\n".join(lines), encoding="utf-8")


def write_quotes_js(quotes_path: Path, entries: list[dict], show_id: str) -> None:
    """
    Write audio/<id>/quotes.js. Each entry's audioUrl is project-root-relative:
    `audio/<show-id>/<filename>`.
    """
    out = []
    for e in entries:
        # A clip with REPEAT: N is emitted N times so it lands in the random
        # pool N times and plays ~Nx as often. Defaults to 1.
        for _ in range(max(1, int(e.get("repeat", 1)))):
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
    board_specs: list[tuple[str, int, int]],
    out_dir: Path,
    show_id: str,
    *,
    exclude_prefix: str = "",
    case_style: str = "preserve",
    dedup_transcripts: bool = False,
    preserve_transcripts: bool = False,
    censor_nword: bool = False,
    no_trim: bool = False,
) -> dict:
    """
    Scrape one or more boards into out_dir. Returns a stats dict.

    `board_specs` is a list of (url, min_words, max_words) — each board carries
    its own length filter, so a merge can keep all of one board while trimming
    short clips from another.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    transcripts_path = out_dir / "transcripts.txt"
    quotes_path = out_dir / "quotes.js"

    existing_chars = read_existing_characters(transcripts_path)
    existing_transcripts = read_existing_transcripts(transcripts_path) if preserve_transcripts else {}
    existing_repeats = read_existing_repeats(transcripts_path)

    seen: set[str] = set()
    seen_transcripts: set[str] = set()
    clips: list[tuple[str, str, bool, int, int]] = []
    dropped_dupes = 0
    for url, bmin, bmax in board_specs:
        print(f"Fetching {url}")
        url_is_legacy = should_trim_board(url, no_trim=no_trim)
        for mp3_url, transcript in fetch_sounds(
            url, exclude_prefix=exclude_prefix, case_style=case_style, censor_nword=censor_nword
        ):
            key = mp3_url.split("?")[0]
            if key in seen:
                continue
            # Some boards list the same line twice under different mp3 URLs; when
            # dedup_transcripts is on, keep only the first occurrence of each transcript.
            if dedup_transcripts:
                tkey = transcript.strip().lower()
                if tkey and tkey in seen_transcripts:
                    dropped_dupes += 1
                    continue
                seen_transcripts.add(tkey)
            seen.add(key)
            clips.append((mp3_url, transcript, url_is_legacy, bmin, bmax))
    summary = f"Found {len(clips)} unique clips across {len(board_specs)} board(s)."
    if dropped_dupes:
        summary += f" (deduped {dropped_dupes} repeat transcript(s))"
    print(summary + "\n")

    entries: list[dict] = []
    newly_downloaded: list[tuple[Path, bool]] = []
    downloaded = skipped_existing = skipped_length = 0

    # Once a curated transcripts.txt exists, preserve_transcripts treats it as the
    # authoritative set: include exactly the clips listed there (by filename), with
    # their hand-edited text, and don't apply the length filter (the labels are
    # intentionally short). On the very first scrape (no file yet) it behaves normally.
    curate = preserve_transcripts and bool(existing_transcripts)
    for i, (mp3_url, transcript, from_legacy, cmin, cmax) in enumerate(clips, 1):
        # Filename is derived from the original API transcript so it stays stable
        # across re-runs even when preserve_transcripts swaps in hand-edited text.
        filename = safe_filename(transcript, mp3_url, i)

        if curate:
            if filename not in existing_transcripts:
                skipped_length += 1
                continue
            display_transcript = existing_transcripts[filename]
        else:
            display_transcript = existing_transcripts.get(filename, transcript)
            if not passes_length(display_transcript, cmin, cmax):
                skipped_length += 1
                continue

        dest = out_dir / filename

        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i}/{len(clips)}] skip (have) {filename}")
            skipped_existing += 1
        else:
            print(f"[{i}/{len(clips)}] download   {filename}")
            try:
                download(mp3_url, dest)
                downloaded += 1
                newly_downloaded.append((dest, from_legacy))
                time.sleep(SLEEP_BETWEEN)
            except Exception as e:
                print(f"   failed: {e}")
                continue

        entries.append({
            "filename": filename,
            "transcript": display_transcript,
            "character": existing_chars.get(filename, ""),
            "repeat": existing_repeats.get(filename, 1),
        })

    # In curate mode, also preserve hand-added clips: ones listed in the curated
    # transcripts.txt that exist on disk but aren't produced by any board (so the
    # board loop above never emits them). Without this they'd be dropped here.
    if curate:
        board_filenames = {e["filename"] for e in entries}
        present_files = {p.name for p in out_dir.glob("*.mp3")}
        manual = manual_entries(
            existing_transcripts, existing_chars, existing_repeats,
            board_filenames, present_files,
        )
        if manual:
            print(f"Preserving {len(manual)} hand-added clip(s) not on any board.")
        entries.extend(manual)

    write_transcripts(transcripts_path, entries)
    write_quotes_js(quotes_path, entries, show_id)

    # Auto-trim notification-ding from legacy/poisoned boards. Only newly-downloaded
    # clips that came from a legacy board are trimmed; modern-board clips are already
    # clean (trimming them would chop real audio), and already-existing files were
    # trimmed on a previous run.
    trimmed = 0
    legacy_new = [p for p, from_legacy in newly_downloaded if from_legacy]
    if legacy_new:
        print(f"\nLegacy board detected — trimming {TRIM_SECONDS}s off front of {len(legacy_new)} new MP3s...")
        for p in legacy_new:
            if trim_mp3_inplace(p, TRIM_SECONDS):
                trimmed += 1
        print(f"Trim complete: {trimmed}/{len(legacy_new)} files.")

    stats = {
        "downloaded": downloaded,
        "skipped_existing": skipped_existing,
        "skipped_length": skipped_length,
        "kept": len(entries),
        "trimmed": trimmed,
    }
    print(
        f"\nDone [{show_id}]: "
        f"Downloaded {stats['downloaded']}, "
        f"Skipped (already present) {stats['skipped_existing']}, "
        f"Skipped (length filter) {stats['skipped_length']}, "
        f"Total kept {stats['kept']}"
        + (f", Trimmed {stats['trimmed']}" if trimmed else "")
    )
    return stats


# ---------- CLI ----------

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
        scrape_board([(board_url, args.min_length, args.max_length)], out_dir, show_id)
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

        def _flag(key: str) -> bool:
            raw = s.get(key, False)
            return raw is True or str(raw).strip().lower() in ("true", "yes", "1")

        def _int(key: str, default: int) -> int:
            try:
                return int(s.get(key))
            except (TypeError, ValueError):
                return default

        # Per-board length filters. Board 1 falls back to the CLI args; board 2
        # falls back to board 1's values, so a merge can filter each board differently.
        b1_min, b1_max = _int("min_length", args.min_length), _int("max_length", args.max_length)
        specs = [(url, b1_min, b1_max)]
        if s.get("board_url_2"):
            specs.append((s["board_url_2"], _int("min_length_2", b1_min), _int("max_length_2", b1_max)))

        scrape_board(
            specs, AUDIO_ROOT / sid, sid,
            exclude_prefix=s.get("exclude_prefix", ""),
            case_style=s.get("case_style", "preserve"),
            dedup_transcripts=_flag("dedup"),
            preserve_transcripts=_flag("preserve_transcripts"),
            censor_nword=_flag("censor_nword"),
            no_trim=_flag("no_trim"),
        )


if __name__ == "__main__":
    main()
