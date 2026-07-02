import importlib.util
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "approach2/.claude/skills/dialog-summary/refine.py"
spec = importlib.util.spec_from_file_location("refine", SKILL)
refine = importlib.util.module_from_spec(spec); spec.loader.exec_module(refine)

def test_truncates_to_two_sentences():
    d = "One thing happened. Two thing happened. Three thing happened."
    out = refine.refine(d)
    assert out.count(".") <= 2
    assert "Three" not in out

def test_word_budget_enforced():
    d = " ".join(["word"] * 100) + "."
    out = refine.refine(d)
    assert len(out.split()) <= refine.WORD_BUDGET

def test_short_input_unchanged():
    d = "Mary met Kirk. They meet tonight."
    assert refine.refine(d) == "Mary met Kirk. They meet tonight."
