# Skill Optimization — Design

**Date:** 2026-07-01
**Status:** Approved (Approach 1 to implement now; Approach 2 designed for a later session)

## Summary

Demonstrate *skill optimization*: the skill-level analog of the existing prompt
optimization demo (`02_prompt_optimization.ipynb`). Instead of optimizing a bare
prompt string, the artifact under optimization is a **structured skill file**,
`dialog-summary/SKILL.md`. Quality is measured against **samsum's gold summaries**
(reference-based), and results are logged as Arize experiments so improvement across
versions is visible in the UI.

Two phases:

- **Approach 1 (build now):** a self-contained notebook that runs a *scripted*
  meta-prompt loop which auto-rewrites `SKILL.md` from Arize eval feedback.
- **Approach 2 (spec now, build later):** an *agentic* variant where Claude Code
  itself is the optimizer, editing `SKILL.md` and/or the harness scripts across
  iterations.

## Context

- `dialog-summary/SKILL.md` — the skill being optimized (dialogue summarization).
- `03_conversations_dataset copy.ipynb` — uploads the samsum dataset to Arize as
  dataset `samsum_small` (dialogue + gold `summary`). This is the eval data source.
- `02_prompt_optimization.ipynb` — the template loop: task → LLM-judge eval →
  `client.experiments.run(...)` → filter bad rows → meta-prompt rewrites the prompt.
  Approach 1 reuses this shape but targets a full markdown skill and reference-based eval.

## Locked decisions

| Decision | Choice |
|---|---|
| Eval signal | Reference-based: LLM judge scores generated summary vs samsum gold summary. No ROUGE. |
| Skill execution | `SKILL.md` read as the system prompt; single LLM call over each dialogue. No real Claude Code invocation in A1. |
| A1 vs A2 | A1 = scripted meta-prompt auto-rewrites `SKILL.md` (reproducible). A2 = Claude Code drives the loop agentically (exploratory). |
| Version tracking | Snapshot each `SKILL.md` version to `dialog-summary/versions/`. |
| Scope this session | Build A1 fully; design A2 only. |

Tunable defaults (demo params): 50 samsum examples, 3 iterations, generator = `gpt-4.1`,
judge = `gpt-4o-mini`.

## Approach 1 — `05_skill_optimization.ipynb`

### Data flow (one iteration)

```
dialog-summary/SKILL.md ──(read as system prompt)──▶ run_skill(dialogue) ──▶ summary
                                                                              │
samsum gold summary ──────────────────────┐                                  │
                                           ▼                                  ▼
                              reference-based skill_eval ◀────────── Arize experiment
                              (LLM judge: summary vs gold            (score + explanation
                               → score + explanation)                 per row, logged)
                                           │
                          filter low-score rows (+ a few high for contrast)
                                           │
                                           ▼
                    meta-optimizer LLM ──▶ rewrites the WHOLE SKILL.md
                                           │
                     snapshot to versions/, write SKILL.md, re-run, compare mean score
```

### Components (notebook cells)

1. **Setup** — deps install, certifi/SSL env, Arize client (reuse cells 0–5 from the
   existing notebooks).
2. **Load data** — pull examples from the Arize `samsum_small` dataset; keep
   `dialogue` and `summary` (gold).
3. **`run_skill(dialogue) -> str`** — reads `dialog-summary/SKILL.md` *fresh each call*
   and uses its full text as the system prompt over the dialogue (generator = gpt-4.1,
   temperature 0).
4. **`skill_eval(output, row) -> EvaluationResult`** — reference-based LLM judge
   comparing `output` to `row["summary"]` (gold) on faithfulness / coverage /
   conciseness. Returns `score` (0/1 or graded) + `explanation`. No ROUGE.
5. **Baseline experiment** — `client.experiments.run(name="skill-v0", dataset="samsum_small",
   task=run_skill, evaluators=[skill_eval], ...)`.
6. **Collect feedback** — `list_runs(...).to_df()`, filter low-score rows plus a few
   high-score rows for contrast (as in the prompt-opt notebook).
7. **Meta-optimizer** — a meta-prompt that receives the *current full `SKILL.md`* plus
   the failure/success explanations and returns a **rewritten full `SKILL.md`**. It is
   instructed to:
   - preserve the section structure (Description / Goal / Input / Procedure / Output
     Format / Rules / Quality Checklist);
   - derive *general, reusable* instruction improvements from recurring failure
     patterns — **not** fixes overfit to specific dialogues.
8. **Apply + iterate** — snapshot current `SKILL.md` to `dialog-summary/versions/v{n}.md`,
   write the new `SKILL.md`, re-run as `skill-v1`, `skill-v2`, … for N iterations.
9. **Report** — final cell prints/plots mean score per version (v0→vN) so the
   improvement is visible; link to the Arize experiments.

### Key design points

- The optimizer rewrites an **entire structured markdown skill**, not a prompt
  template. The meta-prompt keeps headers and improves instructions generally.
- Each version is snapshotted to `dialog-summary/versions/` before overwrite, so v0→vN
  is diffable.
- Reference-based judge only: the signal is "how well does this summary match the gold
  summary," which is samsum's strongest signal.

## Approach 2 — agentic optimization (designed; build later)

Same objective, but **Claude Code itself is the optimizer** instead of a scripted
meta-prompt. It reads Arize eval results, forms a hypothesis, edits `SKILL.md` and/or
the harness, reruns, and compares — exploring options the way a human would.

### Folder layout

```
approach2/
  task.py       # run_skill(dialogue) -> summary  (SKILL.md as system prompt)
  eval.py       # reference-based LLM judge vs gold
  run.py        # runs the Arize experiment, prints mean score + worst-N rows + explanations
  README.md     # the loop Claude Code follows
```

### Agentic loop (per round)

1. `python run.py` → prints current mean score + worst failing rows with judge
   explanations.
2. Read failures, form a hypothesis (e.g. "summaries drop who-said-what → strengthen
   the attribution rule").
3. Edit `dialog-summary/SKILL.md` — or, when the signal points at the harness (lenient
   judge, task truncating long dialogues), edit `eval.py` / `task.py`.
4. Rerun `run.py`, compare to the previous version; keep if better, revert if worse;
   snapshot to `versions/`.
5. Repeat until the score plateaus or a target is hit.

### Why A2 is distinct

The scripted A1 optimizer can *only* rewrite `SKILL.md` text. A2 can also fix the
**measurement/harness** — tighten a lenient judge, fix a truncation bug in the task,
add a preprocessing step — which a fixed meta-prompt loop structurally cannot do. That
is the "explore through options" capability.

## Out of scope

- Real Claude Code CLI/SDK invocation of the skill (A1 treats `SKILL.md` as a system
  prompt).
- ROUGE / non-LLM metrics.
- Building A2 in this session.
