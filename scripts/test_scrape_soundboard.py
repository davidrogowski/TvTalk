#!/usr/bin/env python3
"""
Tests for the durable repeat / manual-clip curation features of
scrape_soundboard.py. Run: python3 scripts/test_scrape_soundboard.py

Covers the pure functions only (no network): REPEAT parsing, quotes.js
repeat-expansion, transcripts.txt REPEAT round-trip, and manual-clip selection.
"""
import json
import tempfile
from pathlib import Path

import scrape_soundboard as s


def test_read_existing_repeats_parses_repeat_lines():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "transcripts.txt"
        p.write_text(
            "001_a.mp3\n"
            '  "A"\n'
            "  CHARACTER: \n"
            "  REPEAT: 3\n"
            "\n"
            "002_b.mp3\n"
            '  "B"\n'
            "  CHARACTER: \n"
            "\n",
            encoding="utf-8",
        )
        repeats = s.read_existing_repeats(p)
        assert repeats.get("001_a.mp3") == 3, repeats
        # No REPEAT line -> not present (callers default to 1).
        assert "002_b.mp3" not in repeats, repeats
    print("ok  read_existing_repeats_parses_repeat_lines")


def test_write_quotes_js_expands_repeat():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "quotes.js"
        entries = [
            {"filename": "001_a.mp3", "transcript": "A", "character": "", "repeat": 3},
            {"filename": "002_b.mp3", "transcript": "B", "character": ""},  # default 1
        ]
        s.write_quotes_js(p, entries, "demo")
        text = p.read_text(encoding="utf-8")
        arr = json.loads(text[text.index("["):text.rindex("]") + 1])
        a = [q for q in arr if q["audioUrl"].endswith("001_a.mp3")]
        b = [q for q in arr if q["audioUrl"].endswith("002_b.mp3")]
        assert len(a) == 3, f"expected 3 copies of a, got {len(a)}"
        assert len(b) == 1, f"expected 1 copy of b, got {len(b)}"
        assert a[0]["audioUrl"] == "audio/demo/001_a.mp3"
    print("ok  write_quotes_js_expands_repeat")


def test_write_transcripts_round_trips_repeat():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "transcripts.txt"
        entries = [
            {"filename": "001_a.mp3", "transcript": "A", "character": "Stephen", "repeat": 2},
            {"filename": "002_b.mp3", "transcript": "B", "character": "", "repeat": 1},
        ]
        s.write_transcripts(p, entries)
        # REPEAT line written only when > 1.
        body = p.read_text(encoding="utf-8")
        assert "REPEAT: 2" in body, body
        assert "REPEAT: 1" not in body, body
        # And it reads back.
        assert s.read_existing_repeats(p).get("001_a.mp3") == 2
    print("ok  write_transcripts_round_trips_repeat")


def test_manual_entries_keeps_present_nonboard_clips():
    existing_transcripts = {
        "001_board.mp3": "On a board",
        "my_local_clip.mp3": "Hand added",
        "missing_clip.mp3": "File was deleted",
    }
    existing_chars = {"my_local_clip.mp3": "Django"}
    existing_repeats = {"my_local_clip.mp3": 2}
    board_filenames = {"001_board.mp3"}
    present_files = {"001_board.mp3", "my_local_clip.mp3"}  # missing_clip absent

    out = s.manual_entries(
        existing_transcripts, existing_chars, existing_repeats,
        board_filenames, present_files,
    )
    fns = [e["filename"] for e in out]
    # Board clip excluded (handled by the board loop); missing file excluded.
    assert fns == ["my_local_clip.mp3"], fns
    assert out[0]["transcript"] == "Hand added"
    assert out[0]["character"] == "Django"
    assert out[0]["repeat"] == 2
    print("ok  manual_entries_keeps_present_nonboard_clips")


if __name__ == "__main__":
    test_read_existing_repeats_parses_repeat_lines()
    test_write_quotes_js_expands_repeat()
    test_write_transcripts_round_trips_repeat()
    test_manual_entries_keeps_present_nonboard_clips()
    print("\nAll tests passed.")
