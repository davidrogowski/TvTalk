#!/usr/bin/env python3
"""
Strip residual 101soundboards "ding" chime left behind by the scraper's fixed 1.0s trim.

WHY THIS EXISTS
---------------
`scrape_soundboard.py` trims a fixed 1.0s off the front of poisoned (-soundboard) clips.
But the ding = variable leading near-silence + a ~repeating-beep chime whose total length
often exceeds 1.0s, and an MP3 `-c copy` cut lands on frame boundaries. So a fixed 1.0s cut
leaves a NON-UNIFORM sliver of the chime on many clips (audible "tail end of a ding").

HOW IT WORKS
------------
The ding is the ONLY audio that is byte-identical across DISTINCT clips (different dialogue
never shares an identical opening). So for each clip, the longest leading decoded-PCM prefix
it shares with another clip == its residual-ding length. We trim exactly that, sample-accurate.

Guards (avoid false trims / gutting clips):
  * only trim when the shared region is LOUD AT t=0 (peak in first 60ms >= LOUD_THRESH) — this
    is the chime; clips that merely share leading SILENCE (true duplicate clips) are skipped.
  * residual must be <= MAX_TRIM_MS and leave >= MIN_REMAIN_S of audio (don't gut dupes).
Loops to convergence so clips don't get "stranded" when their match was trimmed first.

USAGE
-----
  python3 scripts/strip_residual_ding.py --show south-park     # one show (use after scraping it)
  python3 scripts/strip_residual_ding.py --all                 # every poisoned show (skips no_trim boards)

Then verify:  python3 scripts/verify_residual_ding.py --show <id>

NOTE: clips on `no_trim: true` boards are never poisoned, so --all skips them. Re-running is
safe/idempotent (already-clean clips no longer share a loud prefix, so they're left alone).
"""
from __future__ import annotations
import argparse, struct, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_soundboard import load_shows_yaml, SHOWS_YAML  # type: ignore

SR = 22050            # decode rate for matching (mono s16le)
WIN_S = 3.0           # how much of each clip's head to compare
LOUD_THRESH = 2000    # peak (int16) in first 60ms to count as a chime onset
T0_MS = 60
MIN_MS = 40.0         # ignore <40ms shares (coincidence)
MAX_TRIM_MS = 2000.0  # never trim more than this (safety)
MIN_REMAIN_S = 0.6    # must leave at least this much audio (protects true-duplicate clips)
MAX_ITERS = 5


def _b2ms(nbytes: int) -> float:
    return nbytes / 2 / SR * 1000.0


def _head(path: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-i", str(path), "-t", str(WIN_S), "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
        capture_output=True,
    ).stdout


def _dur(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout)
    except ValueError:
        return 0.0


def _lcp(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b)); i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _peak(pcm: bytes) -> int:
    if len(pcm) < 2:
        return 0
    vals = struct.unpack(f"<{len(pcm)//2}h", pcm[:len(pcm)//2*2])
    return max((abs(v) for v in vals), default=0)


def _trim_inplace(path: Path, seconds: float) -> bool:
    tmp = path.with_suffix(".trimming.mp3")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-ss", f"{seconds:.4f}", "-c:a", "libmp3lame", "-q:a", "2", str(tmp)],
        capture_output=True, timeout=60,
    )
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
        tmp.replace(path); return True
    if tmp.exists():
        tmp.unlink()
    return False


def poisoned_show_ids() -> list[str]:
    out = []
    for s in load_shows_yaml(SHOWS_YAML):
        sid = s.get("id")
        if not sid:
            continue
        raw = s.get("no_trim", False)
        clean = raw is True or str(raw).strip().lower() in ("true", "yes", "1")
        if not clean:
            out.append(sid)
    return out


def strip(show_ids: list[str]) -> int:
    files = [p for sid in show_ids for p in sorted((AUDIO_ROOT / sid).glob("*.mp3"))]
    if not files:
        print("no clips found", file=sys.stderr); return 0
    t0_bytes = int(SR * T0_MS / 1000) * 2
    total = 0
    for it in range(1, MAX_ITERS + 1):
        heads = [_head(p) for p in files]
        order = sorted(range(len(files)), key=lambda i: heads[i])
        shared = [0] * len(files)
        for pos, i in enumerate(order):
            if pos > 0:
                shared[i] = max(shared[i], _lcp(heads[i], heads[order[pos - 1]]))
            if pos < len(order) - 1:
                shared[i] = max(shared[i], _lcp(heads[i], heads[order[pos + 1]]))
        trimmed = 0
        for i, p in enumerate(files):
            ms = _b2ms(shared[i])
            if ms < MIN_MS or ms > MAX_TRIM_MS:
                continue
            if _peak(heads[i][:t0_bytes]) < LOUD_THRESH:   # not a chime onset (silence-leading dupe)
                continue
            if _dur(p) - ms / 1000.0 < MIN_REMAIN_S:        # would gut the clip
                continue
            if _trim_inplace(p, ms / 1000.0):
                trimmed += 1
        total += trimmed
        print(f"  iter {it}: trimmed {trimmed}", flush=True)
        if trimmed == 0:
            break
    print(f"done: {total} clip(s) de-dinged across {len(show_ids)} show(s)")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", help="strip one show id")
    g.add_argument("--all", action="store_true", help="strip every poisoned show (skips no_trim boards)")
    args = ap.parse_args()
    ids = [args.show] if args.show else poisoned_show_ids()
    strip(ids)


if __name__ == "__main__":
    main()
