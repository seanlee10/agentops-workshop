import sys, importlib.util
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "approach2/.claude/skills/dialog-summary/extract.py"
spec = importlib.util.spec_from_file_location("extract", SKILL)
extract = importlib.util.module_from_spec(spec); spec.loader.exec_module(extract)

def test_speakers_deduped_in_order():
    d = "Alice: hi\nBob: yo\nAlice: bye"
    assert extract.parse(d)["speakers"] == ["Alice", "Bob"]

def test_salient_turn_detected():
    d = "Alice: how are you\nBob: let's meet tonight"
    salient = extract.parse(d)["salient_turns"]
    assert any("meet tonight" in s for s in salient)
    assert all(":" in s for s in salient)

def test_non_dialogue_lines_ignored():
    d = "<file_gif>\nAlice: hello there\n\n   \nBob: ok"
    assert extract.parse(d)["speakers"] == ["Alice", "Bob"]
