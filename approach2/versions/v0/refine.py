"""Read a draft summary on stdin; print a terse (<=2 sentence, <=WORD_BUDGET word) version."""
import sys, re

MAX_SENTENCES = 2
WORD_BUDGET = 40

def refine(draft: str) -> str:
    draft = draft.strip()
    sentences = re.split(r"(?<=[.!?])\s+", draft)
    kept = " ".join(sentences[:MAX_SENTENCES]).strip()
    words = kept.split()
    if len(words) > WORD_BUDGET:
        kept = " ".join(words[:WORD_BUDGET]).rstrip(",;:") + "."
    return kept

if __name__ == "__main__":
    print(refine(sys.stdin.read()))
