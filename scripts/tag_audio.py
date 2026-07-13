#!/usr/bin/env python3
"""Stamp every clip with the TV Talk button as its album art, and clean ID3 tags.

The clips come off soundboard.com carrying a 101soundboards.com banner as their
cover image and "101soundboards.com" in every tag field. That is what shows up
when someone shares a clip, so we replace both.

    python3 scripts/tag_audio.py               # whole catalog
    python3 scripts/tag_audio.py zoolander     # one or more shows
    python3 scripts/tag_audio.py --verify      # check, don't write

Audio is stream-copied, so the sound is bit-identical; only the container's
metadata and attached picture change.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"
COVER = ROOT / "scripts" / "cover_tvtalk.jpg"
ALBUM = "TV Talk"
COMMENT = "tvtalk.fun"
POISON = "101soundboards"


def load_catalog():
    """audioUrl -> (caption, show name), plus show id -> name, from shows.js."""
    src = (ROOT / "shows.js").read_text()
    body = src[src.index("[") : src.rindex("]") + 1]
    shows = json.loads(body)
    captions, names = {}, {}
    for show in shows:
        names[show["id"]] = show["name"]
        for q in show.get("quotes", []):
            captions[q["audioUrl"]] = (q["text"], show["name"])
    return captions, names


def title_from_slug(path: Path) -> str:
    """Fallback title for a clip that shows.js doesn't list: 001_hey_there -> Hey there."""
    stem = re.sub(r"^\d+_", "", path.stem).replace("_", " ").strip()
    return stem[:1].upper() + stem[1:]


def tag(path: Path, title: str, artist: str) -> str | None:
    """Rewrite one mp3 in place. Returns an error string, or None on success."""
    tmp = path.with_suffix(".tagging.mp3")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(path), "-i", str(COVER),
        "-map", "0:a:0", "-map", "1:v:0",
        "-c:a", "copy", "-c:v", "copy",
        "-map_metadata", "-1",            # drop every inherited tag
        "-id3v2_version", "3", "-write_id3v1", "0",
        "-disposition:v:0", "attached_pic",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        "-metadata", f"title={title}",
        "-metadata", f"artist={artist}",
        "-metadata", f"album={ALBUM}",
        "-metadata", f"album_artist={ALBUM}",
        "-metadata", f"comment={COMMENT}",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.replace(tmp, path)
        return None
    except subprocess.CalledProcessError as e:
        tmp.unlink(missing_ok=True)
        return f"{path}: {e.stderr.decode().strip()[:200]}"


def verify(path: Path) -> str | None:
    """Returns a complaint string if the file isn't correctly tagged."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return f"{path}: unreadable"
    data = json.loads(out.stdout)
    tags = {k.lower(): v for k, v in data.get("format", {}).get("tags", {}).items()}
    art = [s for s in data["streams"] if s["codec_type"] == "video"]
    if not art:
        return f"{path}: no cover art"
    if art[0].get("width") != 400:
        return f"{path}: cover is {art[0].get('width')}px, expected 400"
    if not any(s["codec_type"] == "audio" for s in data["streams"]):
        return f"{path}: lost its audio stream"
    if tags.get("album") != ALBUM:
        return f"{path}: album is {tags.get('album')!r}"
    if any(POISON in str(v).lower() for v in tags.values()):
        return f"{path}: still carries {POISON} tags"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shows", nargs="*", help="show ids (default: all)")
    ap.add_argument("--verify", action="store_true", help="check only, write nothing")
    args = ap.parse_args()

    if not COVER.exists():
        sys.exit(f"missing {COVER} — run: node scripts/render_cover.mjs")

    captions, names = load_catalog()
    dirs = [AUDIO / s for s in args.shows] if args.shows else sorted(
        d for d in AUDIO.iterdir() if d.is_dir()
    )
    for d in dirs:
        if not d.is_dir():
            sys.exit(f"no such show dir: {d}")

    files = sorted(f for d in dirs for f in d.glob("*.mp3"))
    if not files:
        sys.exit("no mp3s found")

    workers = min(8, (os.cpu_count() or 4))
    label = "Verifying" if args.verify else "Tagging"
    print(f"{label} {len(files)} clips across {len(dirs)} shows...")

    def work(path: Path):
        if args.verify:
            return verify(path)
        rel = str(path.relative_to(ROOT))
        caption, show = captions.get(rel, (None, None))
        title = caption or title_from_slug(path)
        artist = show or names.get(path.parent.name, ALBUM)
        return tag(path, title, artist)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        problems = [p for p in pool.map(work, files) if p]

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:20]:
            print(f"  {p}")
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
        sys.exit(1)

    print(f"OK — {len(files)} clips {'verified' if args.verify else 'tagged'}.")


if __name__ == "__main__":
    main()
