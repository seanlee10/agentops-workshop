# Approach 2 — Agentic Code-in-Skill Optimization — Design

**Date:** 2026-07-01
**Status:** Approved (design); implementation plan next.
**Relationship:** Phase 2 of the skill-optimization work. Approach 1
(`05_skill_optimization.ipynb`) optimized the *prose* of `dialog-summary/SKILL.md`
via a scripted meta-prompt and found the naive text-only loop did not beat the
baseline (best = v0 @ 0.29, within judge noise). Approach 2 gives the skill
**executable code** and lets **Claude Code autonomously optimize that code**.

## Summary

Turn `dialog-summary` from a prose-only skill into a skill with bundled Python
scripts, run it through a **real Claude Code agent** (not a single LLM call), and
build an **autonomous optimizer loop** where a separate Claude Code agent edits the
skill's scripts + SKILL.md across iterations to improve a reference-based eval score,
keeping only versions that win.

The diagnosis motivating this: samsum gold summaries are extremely terse (~1
sentence); the generator over-produces detail; the reference-based judge penalizes
the excess. Deterministic code (entity extraction + brevity enforcement) can shape
the output in ways prose instructions alone did not.

## Locked decisions

| Decision | Choice |
|---|---|
| Executor | Real Claude Code agent via the `claude` CLI (`claude -p`, headless), on the user's Claude **subscription** (no `ANTHROPIC_API_KEY`). Skill discovered from `approach2/.claude/skills/dialog-summary/`. |
| Bundled skill code | Two scripts: `extract.py` (speakers + key actions/decisions) feeding `refine.py` (brevity/length enforcement toward gold length). |
| Eval signal | Reference-based `gpt-4o-mini` judge vs samsum gold (same `skill_eval` semantics as Approach 1). No ROUGE. |
| Eval mechanism | An Arize experiment (`task=run_skill_agent`, `evaluators=[skill_eval]`) logged as `skill-agent-v{i}` so versions are comparable in the Arize UI. |
| Optimizer | Autonomous `optimize.py` driver that spawns a separate `claude -p` optimizer agent to edit the skill files each round. |
| Convergence control | Keep-best / reject-regression: snapshot the skill dir per accepted iteration; restore from best on regression. |
| Scale (default) | Subset of ~15 samsum rows, ~4 iterations. Tunable; this is the main runtime lever (~30–60 min total). |
| Permissions | Executor and optimizer run headless with `--dangerously-skip-permissions`, scoped to `approach2/`. |
| Generator model | Claude (via the CLI/subscription), replacing Approach 1's gpt-4.1. Judge stays `gpt-4o-mini` (OpenAI). |

## Folder layout

```
approach2/
  .claude/skills/dialog-summary/
      SKILL.md          # instructs the agent: extract -> draft -> refine; terse to match gold
      extract.py        # entity/fact extraction (speakers + key actions/decisions)
      refine.py         # brevity/length enforcement (compress draft toward gold length)
  executor.py           # run_skill_agent(dialogue) -> summary  (claude -p headless)
  evaluate.py           # reference-based gpt-4o-mini judge vs gold; run as an Arize experiment
  optimize.py           # autonomous driver loop (keep-best)
  versions/             # snapshot of the whole skill dir per accepted iteration
  README.md
```

## Components

### Executor — `run_skill_agent(dialogue) -> str`
- Shells out: `claude -p "Use the dialog-summary skill to summarize this dialogue.
  Output only the summary.\n\n<dialogue>"` with `cwd=approach2/` and
  `--dangerously-skip-permissions`.
- The agent reads SKILL.md, runs `extract.py` then `refine.py`, and returns the terse
  summary parsed from stdout.
- Robustness: timeout per call; on non-zero exit / empty output, return an empty
  string (the judge scores it "bad") rather than crashing the eval.

### Bundled skill code
- `extract.py`: parse speaker-labeled turns → `{speakers, key_actions/decisions}`; used
  to ground the summary and avoid misattribution.
- `refine.py`: given a draft summary, enforce a terse target (≤1–2 sentences / a word
  budget derived from samsum gold lengths); compress if over budget.
- SKILL.md tells the agent the pipeline: extract facts → draft a summary → run refine →
  output only the final terse summary.

### Eval — `evaluate.py`
- Reuses Approach 1's reference-based `skill_eval` (gpt-4o-mini judge, summary vs gold,
  score good=1/bad=0 + explanation).
- Runs as an Arize experiment named `skill-agent-v{i}` with `task=run_skill_agent`,
  reusing the `_delete_experiment_if_exists` idempotency guard and the `run()`-returned
  DataFrame (the list_runs SDK workaround) from Approach 1.
- Subset handling: because `experiments.run` executes over the whole dataset, Approach 2
  creates a dedicated small Arize dataset **`samsum_tiny`** (~15 rows, sampled from the
  same samsum data) and runs all `skill-agent-v{i}` experiments against it. This keeps
  each eval fast while preserving the Arize UI comparison. Created once (idempotently) in
  a setup step.

### Optimizer — `optimize.py`
```
snapshot skill -> versions/v0
baseline = eval("skill-agent-v0"); best_score = baseline; best_dir = versions/v0
for i in 1..N_ITER:
    write failures.json   # bad rows (dialogue, output, gold, explanation) from last eval
    claude -p "You are optimizing the dialog-summary skill. Eval failures: {failures}.
               Edit .claude/skills/dialog-summary/{SKILL.md,extract.py,refine.py} to raise
               the score. Keep summaries terse to match the gold style."
              --dangerously-skip-permissions   (cwd=approach2/)
    score = eval(f"skill-agent-v{i}")
    if score > best_score: best_score = score; snapshot -> versions/v{i}; best_dir = versions/v{i}
    else: restore skill dir from best_dir        # reject regression
report per-version scores; leave skill dir = best_dir
```

## Data flow (one iteration)

```
samsum subset ──▶ run_skill_agent (claude -p + skill scripts) ──▶ summary
      │                                                              │
   gold summary ──────────────────┐                                 ▼
                                   ▼                    Arize experiment skill-agent-v{i}
                     reference-based skill_eval ◀──────  (score + explanation per row)
                                   │
                    failures.json (bad rows + explanations)
                                   │
                                   ▼
              claude -p optimizer edits extract.py / refine.py / SKILL.md
                                   │
                    re-eval ──▶ keep-best or revert ──▶ next iteration
```

## Milestone 0 (critical de-risk)

Before building the loop, get `run_skill_agent` working for **one** dialogue: confirm
`claude -p` discovers the `dialog-summary` skill from `approach2/.claude/skills/`, runs
`extract.py`/`refine.py`, and returns a clean summary parsed from stdout. Everything
downstream depends on reliable headless skill execution; if it is flaky (permissions,
skill discovery, stdout parsing), resolve it here before investing in eval + loop.

## Error handling

- Executor: per-call timeout; empty/failed output → empty summary (scored "bad"), eval
  continues.
- Optimizer agent: if it produces syntactically broken scripts, the next eval's executor
  runs fail → that iteration scores low → keep-best reverts it. Optionally, a quick
  `python -c "import ast"` syntax check on edited scripts before eval.
- Idempotency: reuse `_delete_experiment_if_exists` so re-runs don't collide on
  experiment names.

## Testing / verification

- Milestone 0 manual check (one dialogue end-to-end).
- `extract.py` / `refine.py` unit-tested in isolation (deterministic functions:
  speaker parsing, length compression) — no agent needed.
- Eval smoke: run `skill-agent-v0` over the subset, confirm a baseline score and clean
  Arize experiment.
- Loop: confirm keep-best reverts on a deliberately-worse edit (or just that reported
  best is monotonic and the final skill dir equals the best snapshot).

## Scale, cost, runtime

- Executor + optimizer run on the Claude **subscription** (no per-token API cost).
- Judge runs on OpenAI `gpt-4o-mini` (small cost).
- Default ~15 rows × (1 + ~4) evals + ~4 optimizer runs ≈ 30–60 min. Subset size and
  iteration count are the tunable levers.

## Out of scope

- Claude Agent SDK (Python) executor — using the CLI instead (already installed,
  subscription auth, no extra dependency).
- Changing the eval objective (reference-based vs gold is retained from Approach 1).
- Full 100-row eval per iteration (too slow for real agents; subset instead).
- Modifying Approach 1's notebook.
