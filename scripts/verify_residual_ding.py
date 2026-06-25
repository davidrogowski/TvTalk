#!/usr/bin/env python3
"""
Verify there is no residual ding left after strip_residual_ding.py.

Flags clips that START with a loud chime (peak in first 60ms >= LOUD) AND share that loud
leading prefix (>= MIN_MS) with another clip — i.e. real residual ding. Clips that share
only LEADING SILENCE are within-show DUPLICATE clips, not ding, and are NOT flagged here.

  python3 scripts/verify_residual_ding.py --show south-park
  python3 scripts/verify_residual_ding.py --all
"""
from __future__ import annotations
import argparse, struct, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = REPO_ROOT / "audio"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_soundboard import load_shows_yaml, SHOWS_YAML  # type: ignore
from strip_residual_ding import poisoned_show_ids  # type: ignore

SR = 22050; WIN_S = 1.6; T0_MS = 60; LOUD = 2000; MIN_MS = 40.0


def _b2ms(nb): return nb / 2 / SR * 1000.0
def _head(p):
    return subprocess.run(["ffmpeg","-i",str(p),"-t",str(WIN_S),"-ac","1","-ar",str(SR),"-f","s16le","pipe:1"],capture_output=True).stdout
def _lcp(a,b):
    n=min(len(a),len(b)); i=0
    while i<n and a[i]==b[i]: i+=1
    return i
def _peak(pcm):
    if len(pcm)<2: return 0
    v=struct.unpack(f"<{len(pcm)//2}h",pcm[:len(pcm)//2*2]); return max((abs(x) for x in v),default=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show"); g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    ids = [args.show] if args.show else poisoned_show_ids()
    keys=[]; heads=[]
    for sid in ids:
        for f in sorted((AUDIO_ROOT/sid).glob("*.mp3")):
            keys.append((sid,f.name)); heads.append(_head(f))
    order=sorted(range(len(heads)), key=lambda i: heads[i]); shared=[0]*len(heads)
    for pos,i in enumerate(order):
        if pos>0: shared[i]=max(shared[i],_lcp(heads[i],heads[order[pos-1]]))
        if pos<len(order)-1: shared[i]=max(shared[i],_lcp(heads[i],heads[order[pos+1]]))
    t0=int(SR*T0_MS/1000)*2
    flagged=[(keys[i], round(_b2ms(shared[i]))) for i in range(len(keys))
             if _b2ms(shared[i])>=MIN_MS and _peak(heads[i][:min(shared[i],t0)])>=LOUD]
    print(f"residual ding (loud chime onset, shared): {len(flagged)} clip(s)")
    for (sid,fn),ms in flagged[:40]:
        print(f"  {sid}/{fn}  ({ms}ms)")
    if flagged:
        print("\nNon-zero: re-run strip_residual_ding.py, or these may be loud within-show duplicate")
        print("clips (inspect: a real ding is a tonal chime; a dupe starts with the same speech/SFX).")


if __name__ == "__main__":
    main()
