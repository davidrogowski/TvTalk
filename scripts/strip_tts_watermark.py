#!/usr/bin/env python3
"""
Strip the spoken "101soundboards dot com" TTS watermark.

Companion to strip_lead_artifact.py, which cuts lead-in audio a clip shares
BYTE-FOR-BYTE with another clip. That misses watermarks the site re-renders per
clip: they sound the same but are not byte-identical (r~0.91, not 1.0), so no two
clips share an exact prefix and the shared-prefix detector never fires.

This pass matches the watermark by SOUND instead: correlate each clip's head
against known watermark templates, find where the clip stops tracking the
template (that's where the watermark ends and the real line begins), and cut
there plus any dead air behind it.

  python3 scripts/strip_tts_watermark.py --all                 # dry run
  python3 scripts/strip_tts_watermark.py --all --apply
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
DS = 5                    # analyse at 4410 Hz
HEAD_S = 3.0
WIN_MS = 100              # correlation window
TRACK_R = 0.60            # window still "tracking" the template above this
MATCH_R = 0.75            # clip is watermarked if its first ~600ms matches this well
SILENCE_RMS = 150
MIN_CUT_S = 0.8           # a watermark is ~2s; never call a tiny match a watermark
MAX_CUT_S = 2.6
MIN_KEEP_S = 0.35

# Clips confirmed by ear/analysis to open with the watermark. Templates are read
# from git HEAD when the working copy has already been cleaned.
TEMPLATE_SPECS = [
    # (path, read_from_git). The working copy of 603 was never cleaned (its watermark
    # was re-rendered, so no byte-identical twin existed to expose it) — it still
    # carries the watermark verbatim, which makes it a live template.
    ("audio/happy-gilmore/603_okay_as_long_as_you_re_willing_to_admit_that_now.mp3", False),
    ("audio/happy-gilmore/359_i_tried_to_stab_someone_with_my_skate_nobody_else_ever_did_t.mp3", True),
    ("audio/role-models/151_schedule_wise_you_can_elect_to_spend.mp3", True),
    ("audio/role-models/078_i_i_lost_my_temper_when_i_saw_you_last_and_that_was_regretta.mp3", True),
    ("audio/ted-lasso-s1/016_and_i_am_trying_to_be_more_honest.mp3", True),
    ("audio/old-school/025_always_smiling_hi_honey_judging_watching_look_at_the_baby.mp3", True),
    # The site re-renders the watermark, so renditions only correlate ~0.91 with each
    # OTHER rendition — below the match gate. Cover each rendition family with its own
    # template, or clips in that family go undetected (this is what hid 603).
    ("audio/happy-gilmore/195_handsome_fellow_huh_he_said_when_i_grew_up_i_could_be_anythi.mp3", True),
    ("audio/happy-gilmore/304_i_did_this_to_get_grandma_s_house_back_now_i_can_no_regrets.mp3", True),
    ("audio/happy-gilmore/426_if_not_for_you_none_of_this_would_have_happened.mp3", True),
    ("audio/happy-gilmore/569_norman_spends_more_time_in_the_sand_than_david_hasselhoff.mp3", True),
]


def _decode(raw: bytes) -> array.array:
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    return a[::DS]


def head(path: Path, secs: float = HEAD_S) -> array.array:
    out = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", str(path), "-t", str(secs),
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
        capture_output=True,
    ).stdout
    return _decode(out)


def head_from_git(rel: str, secs: float = HEAD_S) -> array.array:
    blob = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True,
                          cwd=REPO_ROOT).stdout
    out = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", "pipe:0", "-t", str(secs),
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
        input=blob, capture_output=True,
    ).stdout
    return _decode(out)


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def pearson(x, y) -> float:
    n = min(len(x), len(y))
    if n < 20:
        return 0.0
    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n
    sxy = sxx = syy = 0.0
    for i in range(n):
        a = x[i] - mx
        b = y[i] - my
        sxy += a * b
        sxx += a * a
        syy += b * b
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


def rms(seg) -> float:
    return math.sqrt(sum(float(v) * v for v in seg) / len(seg)) if len(seg) else 0.0


def watermark_end_s(clip, tpl) -> float:
    """Seconds at which the clip stops tracking the watermark template (0 if no match)."""
    w = int(WIN_MS / 1000.0 * SR / DS)
    if len(clip) < w * 2 or len(tpl) < w * 2:
        return 0.0
    # gate: does the opening match the template at all?
    if pearson(tpl[: w * 6], clip[: w * 6]) < MATCH_R:
        return 0.0
    last = 0
    for i in range(0, min(len(tpl), len(clip)) // w):
        a = tpl[i * w:(i + 1) * w]
        b = clip[i * w:(i + 1) * w]
        if pearson(a, b) >= TRACK_R:
            last = i + 1
        else:
            break
    return last * WIN_MS / 1000.0


def cut_for(path: Path, templates) -> float:
    clip = head(path)
    # A template sourced from THIS clip matches it end-to-end (same audio), which would
    # read as a full-window "watermark". Score against the other templates only.
    usable = [t for src, t in templates if src != path]
    end = max((watermark_end_s(clip, t) for t in usable), default=0.0)
    if end < MIN_CUT_S:
        return 0.0
    # walk through any dead air behind the watermark
    w = int(20 / 1000.0 * SR / DS)
    pos = int(end * SR / DS)
    while pos + w <= len(clip):
        if rms(clip[pos:pos + w]) >= SILENCE_RMS:
            break
        pos += w
    return pos / (SR / DS)


def load_templates(quiet: bool = False):
    """Load the watermark reference clips. Also used by scrape_soundboard at scrape time."""
    templates = []
    for rel, from_git in TEMPLATE_SPECS:
        try:
            t = head_from_git(rel) if from_git else head(REPO_ROOT / rel)
            if len(t):
                templates.append((REPO_ROOT / rel, t))
        except Exception as e:
            if not quiet:
                print(f"  (template unavailable: {rel}: {e})")
    return templates


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    templates = load_templates()
    if not templates:
        sys.exit("No watermark templates could be loaded.")
    print(f"loaded {len(templates)} watermark template(s)\n")

    shows = ([p.name for p in sorted(AUDIO_ROOT.iterdir()) if p.is_dir()]
             if args.all else [args.show])
    total = 0
    for show in shows:
        hits = []
        for f in sorted((AUDIO_ROOT / show).glob("*.mp3")):
            cut = cut_for(f, templates)
            if cut <= 0:
                continue
            dur = duration(f)
            if cut > MAX_CUT_S or dur - cut < MIN_KEEP_S:
                print(f"  SKIP (cut {cut:.2f}s of {dur:.2f}s) {show}/{f.name}")
                continue
            hits.append((f, cut))
        if hits:
            print(f"{show:<26} {len(hits):3d} watermarked  "
                  f"avg cut {sum(c for _, c in hits) / len(hits):.2f}s")
            total += len(hits)
            if args.apply:
                for f, cut in hits:
                    trim_mp3_inplace(f, cut, reencode=True)
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {total} watermarked clip(s).")


if __name__ == "__main__":
    main()
