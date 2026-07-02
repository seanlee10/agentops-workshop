# Approach 2 — Agentic Code-in-Skill Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `approach2/` — a self-improving skill-optimization system where a real Claude Code agent runs the `dialog-summary` skill (now carrying `extract.py` + `refine.py`) to summarize dialogues, a reference-based judge scores it against samsum gold, and an autonomous optimizer agent edits the skill's code across iterations, keeping only versions that beat the best.

**Architecture:** The executor shells out to `claude -p` (headless, on the Claude subscription) with the skill discoverable from `approach2/.claude/skills/dialog-summary/`. Evaluation runs as an Arize experiment (`task=run_skill_agent`, reference-based `gpt-4o-mini` judge vs gold) over a small `samsum_tiny` dataset, reusing Approach 1's idempotency + `run()`-df SDK workarounds. The optimizer (`optimize.py`) loops: eval → write failures → spawn a `claude -p` optimizer that edits `extract.py`/`refine.py`/`SKILL.md` → re-eval → keep-best/revert.

**Tech Stack:** Python 3.13 (`.venv`), the `claude` CLI (v2.1.197, subscription auth), `arize` SDK, `arize-phoenix` (`phoenix.evals`), `openai` (judge), `datasets` (samsum), `pandas`, `pytest`.

## Global Constraints

- Executor = real Claude Code agent via `claude -p` headless, `cwd=approach2/`, `--dangerously-skip-permissions`, on the Claude subscription (NO `ANTHROPIC_API_KEY`). Generation is Claude, not OpenAI.
- The skill `SKILL.md` MUST have valid YAML frontmatter (`name: dialog-summary`, `description: ...`) or Claude Code will not discover it.
- Bundled skill code: `extract.py` (speakers + salient turns) feeds `refine.py` (brevity/length enforcement toward gold length). Initial versions are intentionally simple — the optimizer improves them.
- Eval is REFERENCE-BASED ONLY: `gpt-4o-mini` judge compares the agent summary to samsum gold (`skill_eval`, good=1/bad=0 + explanation). No ROUGE.
- Eval runs as an Arize experiment named `skill-agent-v{i}` over the `samsum_tiny` dataset (~15 rows), reusing `_delete_experiment_if_exists` and the `run()`-returned DataFrame (NOT `list_runs().to_df()`, which is broken in arize SDK v8.37.1).
- Optimizer = autonomous `optimize.py` that spawns a separate `claude -p` agent to edit the skill files; keep-best / reject-regression via full skill-dir snapshots in `approach2/versions/`.
- Scale defaults: `TINY_N = 15`, `N_ITER = 4`. Tunable; main runtime lever.
- `OPENAI_API_KEY`, `ARIZE_API_KEY`, `ARIZE_SPACE_ID` are read from the repo-root `.env` (already present). Do not print secrets.
- Long runs (full eval loop) exceed the 600s subagent watchdog → execute those at controller level (background), never inside a subagent, exactly as Approach 1 Tasks 4/6 were run.

## File Structure

```
approach2/
  .claude/skills/dialog-summary/
      SKILL.md          # frontmatter + pipeline: extract -> draft -> refine -> output only summary
      extract.py        # stdin dialogue -> JSON {speakers, salient_turns}
      refine.py         # stdin draft summary -> terse summary (<=2 sentences / word budget)
  executor.py           # run_skill_agent(dialogue) -> summary  (claude -p headless)
  evaluate.py           # samsum_tiny dataset + skill_eval + run_agent_experiment(version)
  optimize.py           # autonomous keep-best loop + report
  versions/             # per-accepted-iteration snapshot of the skill dir
  README.md
tests/approach2/
  test_extract.py
  test_refine.py
```

---

### Task 1: Scaffold + skill + executor (Milestone 0 de-risk)

**Files:**
- Create: `approach2/.claude/skills/dialog-summary/SKILL.md`
- Create: `approach2/.claude/skills/dialog-summary/extract.py`
- Create: `approach2/.claude/skills/dialog-summary/refine.py`
- Create: `approach2/executor.py`

**Interfaces:**
- Produces: `run_skill_agent(dialogue: str, timeout: int = 240) -> str` in `approach2/executor.py`. Returns the agent's summary text, or `""` on failure/timeout.

**This task is the critical de-risk: prove headless `claude -p` discovers the skill, runs the bundled scripts, and returns a clean summary for ONE dialogue.** If skill discovery, permissions, script invocation, or stdout parsing misbehave, resolve it here (adjust the prompt, the SKILL.md script-invocation instructions, or use `--output-format json` and parse `.result`) before any later task.

- [ ] **Step 1: Create the skill SKILL.md (with frontmatter + pipeline)**

`approach2/.claude/skills/dialog-summary/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Create minimal working `extract.py`**

`approach2/.claude/skills/dialog-summary/extract.py`:

```python
"""Read a speaker-labeled dialogue on stdin; print JSON {speakers, salient_turns}."""
import sys, json, re

DECISION_HINTS = ("will", "let's", "lets", "plan", "meet", "tomorrow", "tonight",
                  "agree", "should", "need to", "going to", "gonna")

def parse(dialogue: str):
    speakers, salient = [], []
    for line in dialogue.splitlines():
        m = re.match(r"\s*([A-Za-z][\w .'-]{0,30}?):\s*(.*)", line)
        if not m:
            continue
        who, text = m.group(1).strip(), m.group(2).strip()
        if who not in speakers:
            speakers.append(who)
        if any(h in text.lower() for h in DECISION_HINTS):
            salient.append(f"{who}: {text}")
    return {"speakers": speakers, "salient_turns": salient}

if __name__ == "__main__":
    print(json.dumps(parse(sys.stdin.read())))
```

- [ ] **Step 3: Create minimal working `refine.py`**

`approach2/.claude/skills/dialog-summary/refine.py`:

```python
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
```

- [ ] **Step 4: Create `executor.py`**

`approach2/executor.py`:

```python
"""run_skill_agent: summarize a dialogue via a headless Claude Code agent using the
dialog-summary skill (which runs extract.py + refine.py)."""
import subprocess
from pathlib import Path

APPROACH2_DIR = Path(__file__).resolve().parent

PROMPT = (
    "Use the dialog-summary skill to summarize the following dialogue. "
    "Follow the skill's procedure (run its extract.py and refine.py helpers). "
    "Output ONLY the final summary text, nothing else.\n\nDialogue:\n{dialogue}"
)

def run_skill_agent(dialogue: str, timeout: int = 240) -> str:
    try:
        proc = subprocess.run(
            ["claude", "-p", PROMPT.format(dialogue=dialogue),
             "--dangerously-skip-permissions"],
            cwd=str(APPROACH2_DIR),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()

if __name__ == "__main__":
    demo = ("Mary: Sorry, I didn't make it to your bday party :(\n"
            "Nick: It's OK...\n"
            "Mary: I met this guy Kirk, an architect, we spent the week together.\n"
            "Nick: Let's meet tonight, I want details!\n"
            "Mary: Sure, tonight then.")
    print("SUMMARY:", run_skill_agent(demo))
```

- [ ] **Step 5: Milestone 0 — run the executor on one dialogue and verify**

Run: `.venv/bin/python approach2/executor.py`
Expected: prints `SUMMARY:` followed by a terse 1-2 sentence summary of the demo dialogue (mentions Mary/Nick/Kirk and meeting tonight), with no agent chatter/preamble.
If the output contains agent commentary or is empty: adjust the invocation (try `--output-format json` and parse the `result` field; or tighten the PROMPT / SKILL.md "output only" instruction; or verify the skill is discovered by checking the agent actually ran the scripts). Iterate until the output is a clean summary. Record the working invocation in the report.

- [ ] **Step 6: Commit**

```bash
git add approach2/.claude/skills/dialog-summary/ approach2/executor.py
git commit -m "feat(approach2): skill scaffold + headless executor (Milestone 0)"
```

---

### Task 2: `extract.py` real logic + unit tests

**Files:**
- Modify: `approach2/.claude/skills/dialog-summary/extract.py`
- Create: `tests/approach2/test_extract.py`

**Interfaces:**
- Produces: `parse(dialogue: str) -> dict` with keys `"speakers"` (list[str], de-duplicated, in first-seen order) and `"salient_turns"` (list[str] of `"Speaker: text"`).

- [ ] **Step 1: Write failing tests**

`tests/approach2/test_extract.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail (if logic absent) or pass (Task 1 minimal already satisfies)**

Run: `.venv/bin/python -m pytest tests/approach2/test_extract.py -v`
Expected: If Task 1's minimal `parse` already satisfies these, they PASS — that is acceptable; extend `parse` only if a test fails. If you strengthen extraction (e.g., better salient detection), first add a failing test for the new behavior.

- [ ] **Step 3: Ensure `extract.py` satisfies the tests**

Keep the Task 1 `parse` (it already handles speakers/salient/noise). If any test fails, adjust `parse` minimally to pass. Do not over-engineer.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/approach2/test_extract.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add approach2/.claude/skills/dialog-summary/extract.py tests/approach2/test_extract.py
git commit -m "feat(approach2): extract.py entity/salient-turn logic + tests"
```

---

### Task 3: `refine.py` real logic + unit tests

**Files:**
- Modify: `approach2/.claude/skills/dialog-summary/refine.py`
- Create: `tests/approach2/test_refine.py`

**Interfaces:**
- Produces: `refine(draft: str) -> str` enforcing ≤2 sentences and ≤`WORD_BUDGET` words.

- [ ] **Step 1: Write failing tests**

`tests/approach2/test_refine.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify**

Run: `.venv/bin/python -m pytest tests/approach2/test_refine.py -v`
Expected: Task 1's minimal `refine` should satisfy these — 3 passed. If a test fails, adjust `refine` minimally.

- [ ] **Step 3: (If needed) adjust `refine.py`**

Only if a test fails. Keep it deterministic and simple.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest tests/approach2/ -v`
Expected: all extract + refine tests pass, output pristine.

- [ ] **Step 5: Commit**

```bash
git add approach2/.claude/skills/dialog-summary/refine.py tests/approach2/test_refine.py
git commit -m "feat(approach2): refine.py brevity enforcement + tests"
```

---

### Task 4: `evaluate.py` — samsum_tiny dataset + agent experiment

**Files:**
- Create: `approach2/evaluate.py`

**Interfaces:**
- Consumes: `run_skill_agent` from `executor.py`.
- Produces: `ensure_tiny_dataset(n=TINY_N) -> None`; `skill_eval(output, dataset_row) -> EvaluationResult`; `run_agent_experiment(version_name) -> (experiment, eval_df)`; `mean_score(eval_df) -> float`; `collect_failures(eval_df, n=6) -> list[dict]`.

- [ ] **Step 1: Write `evaluate.py`**

`approach2/evaluate.py`:

```python
import os, warnings
warnings.filterwarnings("ignore")
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import pandas as pd
from arize import ArizeClient
from arize.experiments import EvaluationResult
from phoenix.evals import llm_classify, OpenAIModel
from executor import run_skill_agent

SPACE_ID = os.getenv("ARIZE_SPACE_ID")
TINY_N = 15
JUDGE_MODEL = "gpt-4o-mini"
DATASET = "samsum_tiny"

client = ArizeClient(api_key=os.getenv("ARIZE_API_KEY"), request_verify=False)

def ensure_tiny_dataset(n: int = TINY_N) -> None:
    """Create the samsum_tiny dataset (n rows) once; skip if it already exists."""
    existing = client.datasets.list(space=SPACE_ID)
    if any(getattr(d, "name", None) == DATASET for d in getattr(existing, "datasets", existing)):
        return
    from datasets import load_dataset
    df = load_dataset("knkarthick/samsum")["train"].to_pandas()[:n][["dialogue", "summary"]]
    client.datasets.create(name=DATASET, space=SPACE_ID, examples=df)

skill_eval_template = """
You are judging whether a generated summary of a dialogue matches the reference (gold) summary.
    [BEGIN DATA]
    ************
    [Generated Summary]: {output}
    ************
    [Reference Summary]: {reference}
    [END DATA]
Judge whether the Generated Summary is faithful (no invented facts, correct who-said/wanted-what),
covers the same key decisions/requests/plans as the Reference, and is comparably concise. Reply with
a single word, "good" or "bad", nothing else. "good" = faithful, complete on key points, concise.
"""

def skill_eval(output, dataset_row) -> EvaluationResult:
    df = llm_classify(
        dataframe=pd.DataFrame([{"output": output, "reference": dataset_row["summary"]}]),
        template=skill_eval_template, model=OpenAIModel(model=JUDGE_MODEL),
        rails=["good", "bad"], provide_explanation=True,
    )
    label = df["label"][0]
    return EvaluationResult(label=label, score=1 if label == "good" else 0,
                            explanation=df["explanation"][0])

def _agent_task(dataset_row) -> str:
    return run_skill_agent(dataset_row["dialogue"])

def _delete_experiment_if_exists(version_name: str):
    existing = client.experiments.list(space=SPACE_ID, dataset=DATASET)
    for e in existing.experiments:
        if e.name == version_name:
            client.experiments.delete(experiment=e.id, space=SPACE_ID, dataset=DATASET)

def run_agent_experiment(version_name: str):
    _delete_experiment_if_exists(version_name)
    # use run()'s returned df; list_runs().to_df() is broken in arize SDK v8.37.1
    experiment, eval_df = client.experiments.run(
        name=version_name, dataset=DATASET, space=SPACE_ID,
        task=_agent_task, evaluators=[skill_eval], concurrency=3,
    )
    return experiment, eval_df

def mean_score(eval_df) -> float:
    return float(eval_df["eval.skill_eval.score"].astype(float).mean())

def collect_failures(eval_df, n: int = 6) -> list:
    bad = eval_df[eval_df["eval.skill_eval.label"] == "bad"].head(n)
    return bad[["output", "eval.skill_eval.explanation"]].to_dict("records")
```

- [ ] **Step 2: Create the dataset + run the baseline experiment (controller-level; long)**

Run (this spawns ~15 headless agents; several minutes — run in background at controller level, NOT in a watchdog-limited subagent):
```bash
.venv/bin/python -c "import sys; sys.path.insert(0,'approach2'); import evaluate as e; e.ensure_tiny_dataset(); exp,df=e.run_agent_experiment('skill-agent-v0'); print('cols:', list(df.columns)); print('baseline mean:', e.mean_score(df))"
```
Expected: `samsum_tiny` dataset created in Arize; an experiment `skill-agent-v0` appears; `cols` includes `eval.skill_eval.score`; a baseline mean score in [0,1] prints. Note the baseline value in the report.

- [ ] **Step 3: Commit**

```bash
git add approach2/evaluate.py
git commit -m "feat(approach2): evaluate.py samsum_tiny + agent experiment + baseline"
```

---

### Task 5: `optimize.py` — autonomous keep-best loop + report

**Files:**
- Create: `approach2/optimize.py`
- Create: `approach2/README.md`

**Interfaces:**
- Consumes: everything in `evaluate.py`.
- Produces: a runnable `optimize.py` that snapshots the skill dir, runs the baseline, iterates (optimizer agent edits → re-eval → keep-best), and prints per-version scores; `approach2/versions/` snapshots.

- [ ] **Step 1: Write `optimize.py`**

`approach2/optimize.py`:

```python
import os, sys, json, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev

APPROACH2 = Path(__file__).resolve().parent
SKILL_DIR = APPROACH2 / ".claude/skills/dialog-summary"
VERSIONS = APPROACH2 / "versions"
FAILURES = APPROACH2 / "failures.json"
N_ITER = 4

OPT_PROMPT = (
    "You are optimizing the dialog-summary skill so its summaries better match terse "
    "reference summaries (a judge scored these below). The skill lives in "
    ".claude/skills/dialog-summary/ (SKILL.md, extract.py, refine.py). Read the failures "
    "in failures.json, then EDIT any of SKILL.md / extract.py / refine.py to raise the "
    "score. Keep summaries terse (1-2 sentences), faithful, correctly attributed. Make the "
    "edits directly; do not ask questions."
)

def snapshot(idx: int) -> Path:
    dest = VERSIONS / f"v{idx}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_DIR, dest)
    return dest

def restore(src: Path):
    shutil.rmtree(SKILL_DIR)
    shutil.copytree(src, SKILL_DIR)

def run_optimizer():
    subprocess.run(["claude", "-p", OPT_PROMPT, "--dangerously-skip-permissions"],
                   cwd=str(APPROACH2), timeout=600)

def main():
    VERSIONS.mkdir(exist_ok=True)
    ev.ensure_tiny_dataset()
    _, df = ev.run_agent_experiment("skill-agent-v0")
    best_score = ev.mean_score(df); best_dir = snapshot(0); last_df = df
    history = [("skill-agent-v0", best_score)]
    print(f"skill-agent-v0 mean score: {best_score:.3f}")

    for i in range(1, N_ITER + 1):
        FAILURES.write_text(json.dumps(ev.collect_failures(last_df), indent=2))
        run_optimizer()
        _, df = ev.run_agent_experiment(f"skill-agent-v{i}")
        score = ev.mean_score(df); last_df = df
        history.append((f"skill-agent-v{i}", score))
        print(f"skill-agent-v{i} mean score: {score:.3f}")
        if score > best_score:
            best_score = score; best_dir = snapshot(i)
        else:
            restore(best_dir)   # reject regression

    print("\n=== history ===")
    for name, s in history:
        print(f"{name}: {s:.3f}")
    best = max(history, key=lambda x: x[1])
    print(f"\nBaseline: {history[0][1]:.3f} | Best: {best[0]} @ {best[1]:.3f}")
    print("Skill dir left at best version. Compare skill-agent-v* in the Arize UI.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `approach2/README.md`**

`approach2/README.md`:

```markdown
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
```

- [ ] **Step 3: Smoke-run the loop with N_ITER=1 (controller-level; long)**

Run (background, controller level — spawns agents, several minutes):
```bash
cd approach2 && sed 's/^N_ITER = 4/N_ITER = 1/' optimize.py > /tmp/opt1.py && .venv/bin/python /tmp/opt1.py
```
Expected: prints `skill-agent-v0` then `skill-agent-v1` scores; `versions/v0` exists; if v1 lost, the skill dir was restored to v0 (verify `.claude/skills/dialog-summary/` matches `versions/v0`); if v1 won, `versions/v1` exists. No unhandled exception. (This validates the loop mechanics + keep-best without the full 4 iterations.)

- [ ] **Step 4: Commit**

```bash
git add approach2/optimize.py approach2/README.md
git commit -m "feat(approach2): autonomous optimizer loop (keep-best) + README"
```

- [ ] **Step 5: (Execution, not a code change) full run at controller level**

The full `N_ITER=4` run is a controller-level background execution (~30-60 min), reported separately with the per-version scores. Add `approach2/versions/` and any resulting best skill to git after the run:
```bash
.venv/bin/python approach2/optimize.py    # controller-level, background
git add approach2/versions/ approach2/.claude/skills/dialog-summary/
git commit -m "chore(approach2): full optimization run results + best skill"
```

---

## Self-Review

**Spec coverage:**
- Real Claude Code agent executor (`claude -p`, subscription, skill discovered) → Task 1 ✓
- Skill frontmatter requirement → Task 1 Step 1 ✓
- `extract.py` (entities/salient) + `refine.py` (brevity) → Tasks 2, 3 ✓ (minimal in Task 1 for Milestone 0)
- Reference-based `gpt-4o-mini` judge vs gold, no ROUGE → Task 4 `skill_eval` ✓
- Arize experiment `skill-agent-v{i}` over `samsum_tiny` (~15), idempotency + run()-df workaround → Task 4 ✓
- Autonomous optimizer editing skill files, keep-best/revert, `versions/` snapshots → Task 5 ✓
- Scale defaults TINY_N=15, N_ITER=4; controller-level long runs → Tasks 4/5 ✓
- Milestone 0 de-risk before the loop → Task 1 ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code and expected output.

**Type consistency:** `run_skill_agent(dialogue)->str` (Task 1) consumed by `_agent_task` (Task 4); `run_agent_experiment`/`mean_score`/`collect_failures` (Task 4) consumed by `optimize.py` (Task 5); `eval.skill_eval.*` columns consistent with the evaluator name `skill_eval`; `snapshot`/`restore` operate on the same `SKILL_DIR`/`VERSIONS` paths.

**Known risks flagged:** headless skill discovery/stdout parsing (de-risked in Task 1); optimizer may produce broken scripts (keep-best reverts a low-scoring iteration; an optional `ast` syntax-check could be added if it proves flaky); `datasets.list`/`experiments.list` pagination assumed within first page (few datasets/experiments here).
