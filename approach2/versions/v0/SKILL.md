---
name: dialog-summary
description: Summarize a short speaker-labeled dialogue into a terse 1-2 sentence summary. Use for chat transcripts, messenger conversations, or meeting-like exchanges.
---

# Dialogue Summary Skill (code-assisted)

Produce a very concise summary (1-2 sentences) of a speaker-labeled dialogue,
matching the terse style of reference summaries.

## Bundled scripts

Two helper scripts live in this skill's directory (the same folder as this SKILL.md):
- `extract.py` — reads the dialogue on stdin, prints JSON `{"speakers": [...], "salient_turns": [...]}`.
- `refine.py` — reads a draft summary on stdin, prints a terse (<=2 sentence) version.

## Procedure

1. Run `python extract.py` in this skill's directory, piping the dialogue to stdin,
   to get the speakers and salient turns. Ground your summary in these (correct
   attribution, key decisions/plans only).
2. Write a first-draft summary in natural language, third person.
3. Run `python refine.py` in this skill's directory, piping your draft to stdin, to
   enforce brevity. Use its output as the final summary.
4. Output ONLY the final summary text — no preamble, no explanation, no quotes.

## Rules

- Do not add information not supported by the dialogue; do not misattribute who said/wanted what.
- Preserve important names, dates, times, places, and concrete plans/decisions.
- Keep it terse: aim for 1-2 sentences.
