---
name: dialog-summary
description: Summarize a short speaker-labeled dialogue into a terse 1-2 sentence summary. Use for chat transcripts, messenger conversations, or meeting-like exchanges.
---

# Dialogue Summary Skill (code-assisted)

Produce a very concise summary (1-2 sentences) of a speaker-labeled dialogue,
matching the terse style of reference summaries.

## Bundled scripts

Two helper scripts live in this skill's directory (the same folder as this SKILL.md):
- `extract.py` — reads the dialogue on stdin, prints JSON
  `{"speakers": [...], "salient_turns": [...], "emotional_turns": [...]}`.
  `salient_turns` catches decisions/plans/suggestions; `emotional_turns` catches
  reactions like upset, confusion, or surprise — these are often the actual
  point of a venting or conflict dialogue, not just color around it.
- `refine.py` — reads a draft summary on stdin, prints a terse (<=2 sentence) version.

## Procedure

1. Run `python extract.py` in this skill's directory, piping the dialogue to stdin,
   to get the speakers, salient turns, and emotional turns. These are candidates,
   not a checklist — the dialogue's actual point can be a turn the heuristic
   missed. Read the full dialogue, not just the candidates, to find the main
   point(s).
2. Identify what the dialogue is *about*:
   - If it covers ONE topic, find the single core point — usually the decision,
     plan, suggestion, or the reaction/feeling driving the exchange (whichever
     one the conversation is *for*), not a peripheral fact mentioned along the
     way. Write a first-draft summary containing only that. Do not add a second
     fact that only elaborates, reacts to, or explains *why* the first fact is
     true — see calibration example below.
   - If it covers TWO genuinely separate topics that don't depend on each other
     (e.g. "X missed today's session" AND "the homework is pages 12-14" — neither
     is context/elaboration for the other), state the key fact from each,
     briefly, rather than dropping one entirely.
3. State facts using the dialogue's own actions/verbs (e.g. "sent" vs "shared",
   "called" vs "texted") — do not substitute a similar-sounding verb.
   Do not invent actions, motivations, interruptions, or resolutions that
   aren't explicitly stated (e.g. don't say someone "decided to let it go" or
   "cut off" another's sentence unless the dialogue says so). If the dialogue
   leaves something unresolved or ambiguous, keep the summary equally
   noncommittal rather than inventing a resolution.
4. Run `python refine.py` in this skill's directory, piping your draft to stdin, to
   enforce brevity. Use its output as the final summary.
5. Output ONLY the final summary text — no preamble, no explanation, no quotes.

## Rules

- Do not add information not supported by the dialogue; do not misattribute who said/wanted what.
- Do not invent interpretive actions or resolutions the dialogue doesn't state
  (interrupting, cutting someone off, deciding to drop it, resolving an
  ambiguity). Match the dialogue's own verbs rather than a paraphrase that
  changes the action (e.g. "sent" vs "shared").
- Preserve important names, dates, times, places, and concrete plans/decisions.
- Keep it terse: aim for 1-2 sentences.
- Find the point the conversation is actually *for*, not just a fact mentioned
  in it. That point is often a plan/suggestion, but it can also be the feeling
  or reaction driving the exchange (e.g. someone being upset, confused, or
  surprised) — don't default to the first concrete fact (like a date) if the
  dialogue is really about the reaction to it.
- Cut anything that only elaborates, reacts to, or explains *why* the core
  point is true — even if true and even if a decision-hint turn mentions it:
  - reactions/agreement to the main point (e.g. "who accepted", "and expressed
    satisfaction that they agree")
  - how the info was obtained or who was asked, when that's not itself the point
  - incidental context about where/when the conversation is happening (e.g.
    "while on vacation") unless that context IS the point
  - a second independent clause tacked on with "and"/"since"/"because"/a
    relative clause ("who...") — if a clause only supports another clause
    rather than standing as its own reference-worthy fact, delete it.
- Exception: if the dialogue covers two genuinely separate topics (neither is
  elaboration/context/reason for the other), keep one brief fact from each
  instead of dropping a whole topic.
- Calibration example 1 (single topic) — the padded version below is WRONG, not just verbose:
  - Dialogue gist: Amanda baked cookies, offered Jerry some, he said sure, she
    said she'd bring them tomorrow.
  - Too padded (extra reaction clause): "Amanda made cookies and offered some
    to Jerry, who accepted; she will bring him some tomorrow."
  - Correct: "Amanda baked cookies and will bring some to Jerry tomorrow."
- Calibration example 2 (two separate topics) — dropping a whole topic is WRONG:
  - Dialogue gist: John explains he missed class because he was sick; Cassandra
    lists the homework (page 15 ex. 2-3, review vocab); they agree to grab a
    beer soon.
  - Too narrow (drops John's absence and the beer plan): "The homework is page
    15 exercises 2 and 3, plus reviewing the vocabulary."
  - Correct: "John missed class because he was sick, so Cassandra told him the
    homework is page 15 exercises 2-3 and vocab review; they plan to meet for a beer."
