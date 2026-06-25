#!/usr/bin/env python3
"""
Strip residual 101soundboards "ding" chime left behind by the scraper's fixed 1.0s trim.

As of 2026-06 the scraper (`scrape_soundboard.py`) runs this automatically after the 1s cut,
so a normal `--show <id>` scrape already produces fully de-dinged audio. This standalone tool
remains for: re-cleaning already-downloaded shows, sweeping the whole catalog (`--all`), or
re-running after a partial scrape.

The detection/trim logic lives in `scrape_soundboard.strip_residual_ding` (single source of
truth). A clip's residual = the longest leading decoded-PCM prefix it shares with another clip
(only the ding is byte-identical across distinct dialogue); only LOUD-at-t0 shares (the chime,
not leading silence) are trimmed, capped, and guarded so duplicate clips aren't gutted.

USAGE
-----
  python3 scripts/strip_residual_ding.py --show south-park
  python3 scripts/strip_residual_ding.py --all            # skips no_trim (clean) boards

Then verify:  python3 scripts/verify_residual_ding.py --show <id>
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import scrape_soundboard as s  # type: ignore


def poisoned_show_ids() -> list[str]:
    """Show ids that get ding-trimmed (i.e. NOT flagged no_trim in shows.yaml)."""
    out = []
    for show in s.load_shows_yaml(s.SHOWS_YAML):
        sid = show.get("id")
        if not sid:
            continue
        raw = show.get("no_trim", False)
        clean = raw is True or str(raw).strip().lower() in ("true", "yes", "1")
        if not clean:
            out.append(sid)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", help="strip one show id")
    g.add_argument("--all", action="store_true", help="strip every poisoned show (skips no_trim boards)")
    args = ap.parse_args()
    ids = [args.show] if args.show else poisoned_show_ids()
    grand = 0
    for sid in ids:
        files = sorted((AUDIO_ROOT / sid).glob("*.mp3"))
        if not files:
            print(f"skip {sid}: no clips"); continue
        n = s.strip_residual_ding(files)
        grand += n
        if n or args.show:
            print(f"  {sid}: de-dinged {n} clip(s)")
    print(f"done: {grand} clip(s) de-dinged across {len(ids)} show(s)")


if __name__ == "__main__":
    main()
