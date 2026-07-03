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
   to get the speakers and salient turns. These are candidates, not a checklist —
   the dialogue's actual point can be a turn the heuristic missed (e.g. a
   suggestion buried in venting). Read the full dialogue, not just the
   candidates, to find the single main point.
2. Identify the ONE core point: the decision, plan, or key fact the dialogue is
   *about*. Write a first-draft summary containing only that. Do not add a
   second fact unless it is genuinely independent and reference-worthy (not an
   elaboration, reaction, or reason for the first fact).
3. Run `python refine.py` in this skill's directory, piping your draft to stdin, to
   enforce brevity. Use its output as the final summary.
4. Output ONLY the final summary text — no preamble, no explanation, no quotes.

## Rules

- Do not add information not supported by the dialogue; do not misattribute who said/wanted what.
- Preserve important names, dates, times, places, and concrete plans/decisions.
- Keep it terse: aim for 1-2 sentences.
- State only the single most important point. Cut anything that only elaborates,
  reacts to, or explains *why* — even if true and even if a decision-hint turn
  mentions it:
  - reactions/agreement to the main point (e.g. "who accepted", "and expressed
    satisfaction that they agree")
  - how the info was obtained or who was asked, when that's not itself the point
  - incidental context about where/when the conversation is happening (e.g.
    "while on vacation") unless that context IS the point
  - a second independent clause tacked on with "and"/"since"/"because"/a
    relative clause ("who...") — if a clause only supports another clause
    rather than standing as its own reference-worthy fact, delete it.
- Calibration example — the padded version below is WRONG, not just verbose:
  - Dialogue gist: Amanda baked cookies, offered Jerry some, he said sure, she
    said she'd bring them tomorrow.
  - Too padded (extra reaction clause): "Amanda made cookies and offered some
    to Jerry, who accepted; she will bring him some tomorrow."
  - Correct: "Amanda baked cookies and will bring some to Jerry tomorrow."
