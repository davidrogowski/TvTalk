#!/usr/bin/env python3
"""
Compute a per-clip *speech anchor* for Clock The Quote and write it into the game.

Why this exists
---------------
The daily game reveals the clip in escalating snippets — a 1s snippet, then 3s, then 5s,
then the full clip. Those short windows used to be centered on the clip's temporal
MIDPOINT, which for some clips is a music bed or a beat of silence — so the 1s/3s
snippets captured no dialogue and were unguessable (the Wedding Crashers case).

This tool runs Voice Activity Detection (silero-VAD) over each clip, finds the LONGEST
run of speech, and records its CENTER (seconds) as the clip's anchor. The player centers
the nested 1s/3s/5s windows on that anchor (clamping each window to the clip bounds), so
the short snippets are guaranteed to land on a character actually talking.

We use silero, not a loudness/energy heuristic or webrtcvad, on purpose: the failure mode
is a LOUD music bed, and only a real speech model reliably tells music from dialogue.
(webrtcvad flagged the Wedding Crashers music as speech; silero does not.)

Setup (one-time)
----------------
  python3.13 -m venv .venv-vad
  .venv-vad/bin/pip install silero-vad          # pulls torch (~offline, run-once tooling)
  # ffmpeg must be on PATH (already required by the scraper)

Usage
-----
  .venv-vad/bin/python scripts/compute_speech_anchors.py            # dry-run: print table + block
  .venv-vad/bin/python scripts/compute_speech_anchors.py --write    # inject ANCHORS into the game

Run --write whenever the daily SCHEDULE changes (new clips added / queue refilled). Clips
with no detected speech fall back to the midpoint; the player also falls back to the midpoint
for any clip missing from ANCHORS, so a stale table degrades gracefully rather than breaking.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

REPO_ROOT = Path(__file__).resolve().parent.parent
GAME = REPO_ROOT / "clockthequote.html"
SR = 16000

ANCHORS_RE = re.compile(r"const ANCHORS = \{.*?\};")
SCHEDULE_RE = re.compile(
    r'\{show:"((?:[^"\\]|\\.)*)",\s*text:"((?:[^"\\]|\\.)*)",\s*url:"((?:[^"\\]|\\.)*)"\}'
)


def parse_schedule(html: str) -> list[dict]:
    block = html[html.index("const SCHEDULE"):html.index("const TITLES")]
    return [{"show": s, "text": t, "url": u} for s, t, u in SCHEDULE_RE.findall(block)]


def load_audio(path: Path) -> np.ndarray:
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    )
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def anchor_for(audio: np.ndarray, model) -> tuple[float, str, float]:
    """Return (anchor_seconds, source_label, speech_coverage)."""
    dur = len(audio) / SR
    segs = get_speech_timestamps(torch.from_numpy(audio), model, sampling_rate=SR, return_seconds=True)
    cover = sum(s["end"] - s["start"] for s in segs) / dur if dur else 0.0
    if segs:
        longest = max(segs, key=lambda s: s["end"] - s["start"])
        return round((longest["start"] + longest["end"]) / 2, 3), \
            f'{longest["start"]:.2f}-{longest["end"]:.2f}', cover
    return round(dur / 2, 3), "NONE->mid", cover


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute speech anchors and (optionally) write them into the game.")
    ap.add_argument("--write", action="store_true", help="inject the ANCHORS block into clockthequote.html in place")
    args = ap.parse_args()

    html = GAME.read_text(encoding="utf-8")
    clips = parse_schedule(html)
    model = load_silero_vad()

    anchors: dict[str, float] = {}
    rows = []
    for c in clips:
        audio = load_audio(REPO_ROOT / c["url"])
        dur = len(audio) / SR
        anchor, src, cover = anchor_for(audio, model)
        anchors[c["url"]] = anchor
        rows.append((c["show"], dur, round(dur / 2, 2), anchor, src, round(cover, 2), round(abs(anchor - dur / 2), 2)))

    rows.sort(key=lambda r: -r[6])
    print(f"{'show':<28}{'dur':>6}{'mid':>7}{'anchor':>8}{'longestSeg':>13}{'cover':>7}{'moved':>7}")
    for show, dur, mid, anchor, src, cover, moved in rows:
        print(f"{show[:27]:<28}{dur:6.1f}{mid:7.2f}{anchor:8.2f}{src:>13}{cover:7.2f}{moved:7.2f}")

    block = "const ANCHORS = " + json.dumps(anchors) + ";"
    if args.write:
        if not ANCHORS_RE.search(html):
            print("\nERROR: could not find the `const ANCHORS = {...};` line to replace.", file=sys.stderr)
            return 1
        GAME.write_text(ANCHORS_RE.sub(lambda _: block, html, count=1), encoding="utf-8")
        print(f"\nwrote {len(anchors)} anchors into {GAME.relative_to(REPO_ROOT)}")
    else:
        print(f"\n(dry run) {len(anchors)} anchors computed — re-run with --write to inject:\n\n{block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
