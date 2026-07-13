#!/usr/bin/env python3
"""
Strip poisoned lead-in audio from soundboard clips.

Three artifacts have shown up in 101soundboards rips, and only the first was ever
handled:

  1. loud ding chime          -> trim_mp3_inplace + strip_residual_ding (already fixed)
  2. quiet ding TAIL          -> ~100ms of chime decay left behind by the coarse 1s cut,
                                 followed by dead air. Too quiet for strip_residual_ding's
                                 LOUD threshold, so it survived. Audible on playback.
  3. spoken TTS watermark     -> ~2s of "101soundboards dot com" read aloud at the head.
                                 Not a chime at all, so the ding detectors never saw it.

Detection principle: two DIFFERENT quotes cannot legitimately share their opening audio.
So any lead-in a clip shares with another clip in the same show is an artifact, whatever
it sounds like. We cut exactly that shared region, then continue through any dead air
behind it up to the real speech onset. Audio that is unique to a clip is never touched.

  python3 scripts/strip_lead_artifact.py --show family-guy --dry-run
  python3 scripts/strip_lead_artifact.py --all --apply
"""
from __future__ import annotations

import argparse
import array
import math
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_soundboard import trim_mp3_inplace  # type: ignore

SR = 22050
HEAD_S = 4.0            # analysis window
MIN_SHARED_MS = 40.0    # below this, a shared prefix is just codec noise
SILENCE_RMS = 150       # a 20ms window quieter than this is dead air
WIN_MS = 20
MAX_CUT_S = 2.6         # refuse to cut more than this (safety rail)
MIN_KEEP_S = 0.35       # refuse to leave a clip shorter than this


def head_pcm(path: Path, secs: float = HEAD_S) -> bytes:
    out = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", str(path), "-t", str(secs),
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
        capture_output=True,
    ).stdout
    return out[: len(out) // 2 * 2]


def duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _lcp(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _rms(buf: bytes) -> float:
    if len(buf) < 2:
        return 0.0
    v = array.array("h")
    v.frombytes(buf)
    return math.sqrt(sum(float(x) * x for x in v) / len(v)) if v else 0.0


def shared_prefix_bytes(pcm: dict[str, bytes]) -> dict[str, int]:
    """Longest lead-in each clip shares byte-for-byte with any other clip in the show."""
    names = sorted(pcm, key=lambda n: pcm[n])   # identical prefixes sort adjacent
    best: dict[str, int] = {n: 0 for n in pcm}
    for a, b in zip(names, names[1:]):
        n = _lcp(pcm[a], pcm[b])
        best[a] = max(best[a], n)
        best[b] = max(best[b], n)
    return best


def cut_point_s(buf: bytes, shared_nb: int) -> float:
    """
    Seconds to cut: the shared (artifact) region, extended through any dead air
    behind it, stopping at the first real audio. Returns 0.0 if nothing to cut.
    """
    shared_ms = shared_nb / 2 / SR * 1000.0
    if shared_ms < MIN_SHARED_MS:
        return 0.0
    win_nb = int(WIN_MS / 1000.0 * SR) * 2
    pos = shared_nb
    while pos + win_nb <= len(buf):
        if _rms(buf[pos:pos + win_nb]) >= SILENCE_RMS:
            break                                # real audio starts here
        pos += win_nb
    return pos / 2 / SR


def plan_show(show: str) -> list[tuple[Path, float, float, str]]:
    d = AUDIO_ROOT / show
    pcm: dict[str, bytes] = {}
    for f in sorted(d.glob("*.mp3")):
        b = head_pcm(f)
        if b:
            pcm[f.name] = b
    if len(pcm) < 2:
        return []
    shared = shared_prefix_bytes(pcm)
    plan = []
    for name, nb in shared.items():
        cut = cut_point_s(pcm[name], nb)
        if cut <= 0:
            continue
        f = d / name
        dur = duration(f)
        kind = "watermark" if _rms(pcm[name][:nb]) >= SILENCE_RMS else "ding-tail/deadair"
        if cut > MAX_CUT_S:
            print(f"  SKIP (cut {cut:.2f}s > cap) {name}")
            continue
        if dur - cut < MIN_KEEP_S:
            print(f"  SKIP (would leave {dur - cut:.2f}s) {name}")
            continue
        plan.append((f, cut, dur, kind))
    return plan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true", help="Rewrite the mp3s (default: dry run).")
    args = ap.parse_args()

    shows = ([p.name for p in sorted(AUDIO_ROOT.iterdir()) if p.is_dir()]
             if args.all else [args.show])

    grand = 0
    for show in shows:
        plan = plan_show(show)
        if not plan:
            continue
        wm = sum(1 for _, _, _, k in plan if k == "watermark")
        total_cut = sum(c for _, c, _, _ in plan)
        print(f"{show:<26} {len(plan):4d} clips  (watermark {wm:3d})  "
              f"avg cut {total_cut / len(plan):.2f}s")
        grand += len(plan)
        if args.apply:
            for f, cut, _dur, _k in plan:
                trim_mp3_inplace(f, cut, reencode=True)
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {grand} clip(s) across "
          f"{len(shows)} show(s) scanned.")


if __name__ == "__main__":
    main()
