# Approach 2 — Agentic code-in-skill optimization

A real Claude Code agent runs the `dialog-summary` skill (SKILL.md + extract.py + refine.py)
to summarize samsum dialogues; a reference-based gpt-4o-mini judge scores each summary vs the
gold; an autonomous optimizer (`optimize.py`) edits the skill's code across iterations,
keeping only versions that beat the best. Experiments log to Arize as `skill-agent-v{i}`.

## Run
```
.venv/bin/python approach2/optimize.py
```
Requires: the `claude` CLI (subscription auth), and `OPENAI_API_KEY` / `ARIZE_API_KEY` /
`ARIZE_SPACE_ID` in the repo-root `.env`. Runs ~30-60 min (real agents; `TINY_N=15`,
`N_ITER=4`). The best skill version is left live in `.claude/skills/dialog-summary/`;
snapshots are in `versions/`.
