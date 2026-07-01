# Skill Optimization (Approach 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `05_skill_optimization.ipynb` — a scripted loop that measures the `dialog-summary` skill against samsum gold summaries via Arize experiments, then auto-rewrites `dialog-summary/SKILL.md` from the eval feedback, iterating until the mean score improves.

**Architecture:** Same shape as `02_prompt_optimization.ipynb`. A task function uses the full text of `dialog-summary/SKILL.md` as a system prompt to summarize each samsum dialogue; a reference-based LLM judge scores the summary against the gold summary; results are logged as an Arize experiment (`skill-v0`, `skill-v1`, …). A meta-prompt LLM rewrites the whole `SKILL.md` from filtered good/bad feedback. Each version is snapshotted to `dialog-summary/versions/` before overwrite.

**Tech Stack:** Python (Jupyter), `arize` SDK, `arize-phoenix` (`phoenix.evals`), `langchain-openai`, `openai`, `pandas`, `python-dotenv`. Data source: Arize dataset `samsum_small` (created by `03_conversations_dataset copy.ipynb`).

## Global Constraints

- Eval is **reference-based only**: judge compares generated summary to the samsum gold `summary`. No ROUGE, no reference-free judging.
- The skill is executed as a **system prompt**: `run_skill` reads `dialog-summary/SKILL.md` fresh on each call. No Claude Code CLI/SDK invocation.
- The meta-optimizer rewrites the **entire `SKILL.md`**, preserving its section structure (Description / Goal / Input / Procedure / Output Format / Rules / Quality Checklist), and derives **general, reusable** instructions — never fixes overfit to specific dialogues.
- Every `SKILL.md` version is snapshotted to `dialog-summary/versions/v{n}.md` **before** the file is overwritten.
- Demo defaults (single source of truth, set once in setup): `N_EXAMPLES = 50`, `N_ITERATIONS = 3`, `GEN_MODEL = "gpt-4.1-2025-04-14"`, `JUDGE_MODEL = "gpt-4o-mini"`, `SKILL_PATH = "dialog-summary/SKILL.md"`, `VERSIONS_DIR = "dialog-summary/versions"`.
- samsum example columns are `dialogue` (input) and `summary` (gold).
- Arize client is constructed with `request_verify=False` (matches existing notebooks).

**Prerequisite (verify before Task 1):** `OPENAI_API_KEY` must be available to the kernel. It is **not** in `.env` (which only has `ARIZE_API_KEY`, `ARIZE_SPACE_ID`). Confirm it is exported in the shell or add it to `.env`. The dataset `samsum_small` must already exist in the Arize space (run `03_conversations_dataset copy.ipynb` if not).

---

### Task 1: Notebook scaffold — setup + load samsum examples

**Files:**
- Create: `05_skill_optimization.ipynb`

**Interfaces:**
- Produces: a live `client` (ArizeClient), `SPACE_ID` (str), config constants (`N_EXAMPLES`, `N_ITERATIONS`, `GEN_MODEL`, `JUDGE_MODEL`, `SKILL_PATH`, `VERSIONS_DIR`), and `examples` (samsum rows from Arize with `dialogue` + `summary`).

- [ ] **Step 1: Create the notebook with a title + deps cell**

Create `05_skill_optimization.ipynb`. First cell (markdown):

```markdown
# 05. Skill Optimization — dialog-summary SKILL.md
Optimize `dialog-summary/SKILL.md` against samsum gold summaries via Arize experiments.
```

Second cell (code):

```python
!pip install -qqq arize arize-phoenix certifi urllib3 langchain-openai python-dotenv
```

- [ ] **Step 2: Add SSL + client + config cell**

```python
import os, certifi
CA = certifi.where()
os.environ["SSL_CERT_FILE"] = CA
os.environ["REQUESTS_CA_BUNDLE"] = CA
os.environ["CURL_CA_BUNDLE"] = CA

from arize import ArizeClient
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("ARIZE_API_KEY")
SPACE_ID = os.getenv("ARIZE_SPACE_ID")
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not set (not in .env) — export it before running"

client = ArizeClient(api_key=API_KEY, request_verify=False)

# ---- demo config (single source of truth) ----
N_EXAMPLES   = 50
N_ITERATIONS = 3
GEN_MODEL    = "gpt-4.1-2025-04-14"
JUDGE_MODEL  = "gpt-4o-mini"
SKILL_PATH   = "dialog-summary/SKILL.md"
VERSIONS_DIR = "dialog-summary/versions"
DATASET_NAME = "samsum_small"
```

- [ ] **Step 3: Add load-examples cell**

```python
examples = client.datasets.list_examples(dataset=DATASET_NAME, space=SPACE_ID)
examples
```

- [ ] **Step 4: Run all three cells; verify output**

Run cells top to bottom. Expected: no assertion error, and `examples` renders rows containing `dialogue` and `summary` columns. If `list_examples` returns a wrapper, note the accessor used (mirror `02_prompt_optimization.ipynb` cell 5–6 behavior).
Expected: at least `N_EXAMPLES` rows exist in the dataset.

- [ ] **Step 5: Commit**

```bash
git add 05_skill_optimization.ipynb
git commit -m "feat(skill-opt): notebook scaffold + load samsum examples"
```

---

### Task 2: `run_skill` — SKILL.md as system prompt

**Files:**
- Modify: `05_skill_optimization.ipynb` (add cells)

**Interfaces:**
- Consumes: `GEN_MODEL`, `SKILL_PATH` from Task 1.
- Produces: `read_skill() -> str`, `run_skill(dataset_row) -> str` (reads SKILL.md fresh each call, returns the summary string). `run_skill` is the `task` passed to `client.experiments.run`.

- [ ] **Step 1: Add the task-function cell**

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

gen_llm = ChatOpenAI(model=GEN_MODEL, temperature=0.0)
gen_chain = gen_llm | StrOutputParser()

def read_skill() -> str:
    with open(SKILL_PATH, "r") as f:
        return f.read()

def run_skill(dataset_row) -> str:
    """Use the full SKILL.md text as the system prompt over one dialogue."""
    skill = read_skill()
    dialogue = dataset_row["dialogue"]
    messages = [
        ("system", skill),
        ("human", f"Summarize this dialogue:\n\n{dialogue}"),
    ]
    return gen_chain.invoke(messages)
```

- [ ] **Step 2: Add a smoke-test cell**

```python
# smoke test on one example (does NOT hit Arize)
_sample = examples.to_df().iloc[0] if hasattr(examples, "to_df") else pd.DataFrame(examples).iloc[0]
print("DIALOGUE:\n", _sample["dialogue"][:400])
print("\nGOLD:\n", _sample["summary"])
print("\nSKILL OUTPUT:\n", run_skill(_sample))
```

- [ ] **Step 3: Run both cells; verify output**

Expected: prints a coherent 1–3 sentence summary of the sample dialogue with no exception. If the `_sample` accessor line errors, adjust it to match how `examples` exposes rows (from Task 1 Step 4), then rerun.

- [ ] **Step 4: Commit**

```bash
git add 05_skill_optimization.ipynb
git commit -m "feat(skill-opt): run_skill task uses SKILL.md as system prompt"
```

---

### Task 3: `skill_eval` — reference-based LLM judge vs gold

**Files:**
- Modify: `05_skill_optimization.ipynb` (add cells)

**Interfaces:**
- Consumes: `JUDGE_MODEL` from Task 1.
- Produces: `skill_eval(output, dataset_row) -> EvaluationResult` with `label` in {"good","bad"}, `score` in {1,0}, and an `explanation`. This is the `evaluator` passed to `client.experiments.run`.

- [ ] **Step 1: Add the evaluator cell**

```python
from phoenix.evals import llm_classify, OpenAIModel
from arize.experiments import EvaluationResult

skill_eval_template = """
You are judging whether a generated summary of a dialogue matches the reference (gold) summary.
    [BEGIN DATA]
    ************
    [Generated Summary]: {output}
    ************
    [Reference Summary]: {reference}
    [END DATA]

Compare the Generated Summary to the Reference Summary. Judge whether the Generated Summary is
faithful (no invented facts, correct who-said/wanted-what), covers the same key decisions/requests/
plans as the Reference, and is comparably concise. Your response must be a single word, either
"good" or "bad", with no other text. "good" = faithful, complete on key points, and concise
relative to the Reference. "bad" = misses key points, misattributes, invents facts, or is not concise.
"""

def skill_eval(output, dataset_row) -> EvaluationResult:
    eval_df = llm_classify(
        dataframe=pd.DataFrame([{"output": output, "reference": dataset_row["summary"]}]),
        template=skill_eval_template,
        model=OpenAIModel(model=JUDGE_MODEL),
        rails=["good", "bad"],
        provide_explanation=True,
    )
    label = eval_df["label"][0]
    score = 1 if label == "good" else 0
    return EvaluationResult(label=label, score=score, explanation=eval_df["explanation"][0])
```

- [ ] **Step 2: Add a smoke-test cell**

```python
# sanity: a good summary (the gold itself) should score 1; a junk summary should score 0
print("gold-vs-gold:", skill_eval(_sample["summary"], _sample).label, "(expect good)")
print("junk        :", skill_eval("They talked about nothing.", _sample).label, "(expect bad)")
```

- [ ] **Step 3: Run both cells; verify output**

Expected: `gold-vs-gold` → `good`; `junk` → `bad`. If the judge mislabels the gold-vs-gold case, tighten the template wording and rerun before proceeding.

- [ ] **Step 4: Commit**

```bash
git add 05_skill_optimization.ipynb
git commit -m "feat(skill-opt): reference-based skill_eval judge vs gold summary"
```

---

### Task 4: Baseline experiment `skill-v0` + feedback collection

**Files:**
- Modify: `05_skill_optimization.ipynb` (add cells)

**Interfaces:**
- Consumes: `run_skill`, `skill_eval`, `DATASET_NAME`, `SPACE_ID` from earlier tasks.
- Produces: `run_experiment(version_name) -> (experiment, eval_df)` and `collect_feedback(eval_df, eval_name, n_bad=3, n_good=5) -> filtered_df`; a printed baseline mean score.

- [ ] **Step 1: Add the experiment-runner helper cell**

```python
def run_experiment(version_name: str):
    experiment, _ = client.experiments.run(
        name=version_name,
        dataset=DATASET_NAME,
        space=SPACE_ID,
        task=run_skill,
        evaluators=[skill_eval],
    )
    eval_df = client.experiments.list_runs(experiment=experiment.id, all=True).to_df()
    return experiment, eval_df

def mean_score(eval_df) -> float:
    return float(eval_df["eval.skill_eval.score"].astype(float).mean())

def collect_feedback(eval_df, n_bad: int = 3, n_good: int = 5):
    bad  = eval_df[eval_df["eval.skill_eval.label"] == "bad"].head(n_bad)
    good = eval_df[eval_df["eval.skill_eval.label"] == "good"].head(n_good)
    return pd.concat([bad, good])
```

Note: the eval column prefix is derived from the evaluator function name `skill_eval` → `eval.skill_eval.*`, mirroring `02_prompt_optimization.ipynb` where `summary_eval` produced `eval.summary_eval.*`. Confirm the exact column names in Step 2 and adjust if the SDK differs.

- [ ] **Step 2: Add the baseline run cell**

```python
exp_v0, eval_v0 = run_experiment("skill-v0")
print("columns:", list(eval_v0.columns))
print("skill-v0 mean score:", mean_score(eval_v0))
eval_v0.head()
```

- [ ] **Step 3: Run the cells; verify output**

Expected: an experiment named `skill-v0` appears in Arize; `columns` includes `eval.skill_eval.score` and `eval.skill_eval.label` (adjust `mean_score`/`collect_feedback` if the real prefix differs); mean score prints as a float in [0,1]. This is the baseline to beat.

- [ ] **Step 4: Add + verify feedback filtering cell**

```python
filtered_v0 = collect_feedback(eval_v0)
filtered_v0[["output", "eval.skill_eval.label", "eval.skill_eval.explanation"]]
```

Expected: up to 8 rows mixing `bad` and `good`, each with a judge explanation.

- [ ] **Step 5: Commit**

```bash
git add 05_skill_optimization.ipynb
git commit -m "feat(skill-opt): baseline skill-v0 experiment + feedback collection"
```

---

### Task 5: Meta-optimizer — rewrite the whole SKILL.md (with versioning)

**Files:**
- Modify: `05_skill_optimization.ipynb` (add cells)
- Create: `dialog-summary/versions/` (directory, created at runtime)

**Interfaces:**
- Consumes: `read_skill`, `SKILL_PATH`, `VERSIONS_DIR`, `gen_chain`, `filtered_v0` from earlier tasks.
- Produces: `snapshot_skill(version_idx) -> path`, `optimize_skill(current_skill, filtered_df) -> str` (new SKILL.md text), and `apply_skill(new_text)` which snapshots then overwrites `SKILL.md`.

- [ ] **Step 1: Add the snapshot + apply helpers cell**

```python
from pathlib import Path

def snapshot_skill(version_idx: int) -> str:
    Path(VERSIONS_DIR).mkdir(parents=True, exist_ok=True)
    dest = f"{VERSIONS_DIR}/v{version_idx}.md"
    with open(dest, "w") as f:
        f.write(read_skill())
    return dest

def apply_skill(new_text: str):
    with open(SKILL_PATH, "w") as f:
        f.write(new_text)
```

- [ ] **Step 2: Add the meta-optimizer cell**

```python
meta_prompt = """You are an expert at optimizing Claude "skills" — structured Markdown instruction
files (SKILL.md). You are given the CURRENT SKILL.md and PERFORMANCE DATA from running that skill as
a summarization system prompt over a dialogue dataset. Each record has the model's `output` summary,
an LLM-judge `label` (good/bad) comparing it to a gold reference summary, and an `explanation` of why.

Rewrite the SKILL.md so future summaries earn "good".

CURRENT SKILL.md
================
{current_skill}
================

PERFORMANCE DATA (bad records show failures, good records show what the judge rewards)
================
{feedback_samples}
================

REQUIREMENTS
1. Read every explanation. Find the recurring failure pattern across the `bad` records and contrast
   with the `good` ones.
2. Translate those patterns into GENERAL, REUSABLE instructions — never fixes overfit to specific
   dialogues in the data.
3. Preserve the section structure exactly: Description, Goal, Input, Procedure, Output Format, Rules,
   Quality Checklist. Keep the same Markdown headers.
4. Output ONLY the complete rewritten SKILL.md Markdown. No preamble, no code fences, no commentary.
"""

def optimize_skill(current_skill: str, filtered_df) -> str:
    feedback = filtered_df[["output", "eval.skill_eval.label", "eval.skill_eval.explanation"]].to_string(index=False)
    return gen_chain.invoke(meta_prompt.format(current_skill=current_skill, feedback_samples=feedback))
```

- [ ] **Step 3: Add a dry-run cell (snapshot v0, generate, inspect — do NOT apply yet)**

```python
snap = snapshot_skill(0)
new_skill_text = optimize_skill(read_skill(), filtered_v0)
print("snapshotted:", snap)
print("---- proposed SKILL.md ----")
print(new_skill_text)
# structural check
for header in ["## Description", "## Goal", "## Procedure", "## Rules", "## Quality Checklist"]:
    assert header in new_skill_text, f"missing section: {header}"
print("\nOK: all required sections present")
```

- [ ] **Step 4: Run the cells; verify output**

Expected: `dialog-summary/versions/v0.md` is created (identical to current `SKILL.md`); the proposed text is a full SKILL.md with all required section headers (assertions pass); no code fences or preamble. If a fence/preamble sneaks in, strip it in `optimize_skill` (e.g. remove leading/trailing ```` ``` ````) and rerun.

- [ ] **Step 5: Commit**

```bash
git add 05_skill_optimization.ipynb dialog-summary/versions/v0.md
git commit -m "feat(skill-opt): meta-optimizer rewrites full SKILL.md + version snapshots"
```

---

### Task 6: Iteration loop + improvement report

**Files:**
- Modify: `05_skill_optimization.ipynb` (add cells)

**Interfaces:**
- Consumes: everything from Tasks 4–5 (`run_experiment`, `mean_score`, `collect_feedback`, `snapshot_skill`, `optimize_skill`, `apply_skill`, `N_ITERATIONS`, `eval_v0`).
- Produces: `history` (list of `{"version": str, "score": float}`) and a printed per-version comparison.

- [ ] **Step 1: Add the iteration-loop cell**

```python
history = [{"version": "skill-v0", "score": mean_score(eval_v0)}]
last_eval = eval_v0

for i in range(1, N_ITERATIONS + 1):
    filtered = collect_feedback(last_eval)
    new_text = optimize_skill(read_skill(), filtered)
    snapshot_skill(i - 1)          # save the version we are about to replace
    apply_skill(new_text)          # SKILL.md now = optimized version i
    exp, last_eval = run_experiment(f"skill-v{i}")
    score = mean_score(last_eval)
    history.append({"version": f"skill-v{i}", "score": score})
    print(f"skill-v{i} mean score: {score:.3f}")

pd.DataFrame(history)
```

Note: `snapshot_skill(i-1)` re-saves each pre-edit version; v0 (Task 5) is the original baseline, so re-running is idempotent for v0 and captures v1, v2 … before each overwrite.

- [ ] **Step 2: Add the report cell**

```python
hist_df = pd.DataFrame(history)
best = hist_df.loc[hist_df["score"].idxmax()]
print(hist_df.to_string(index=False))
print(f"\nBaseline (skill-v0): {history[0]['score']:.3f}")
print(f"Best: {best['version']} @ {best['score']:.3f}")
print("Compare experiments skill-v0..skill-v{} in the Arize UI.".format(N_ITERATIONS))
```

- [ ] **Step 3: Run the cells; verify output**

Expected: `N_ITERATIONS` new experiments (`skill-v1`…) appear in Arize; `history` shows mean score per version; the report prints baseline vs best. Each version exists under `dialog-summary/versions/`. A monotonic improvement is ideal but not guaranteed — the report simply surfaces which version won.

- [ ] **Step 4: Commit (notebook + all version snapshots + final SKILL.md)**

```bash
git add 05_skill_optimization.ipynb dialog-summary/versions/ dialog-summary/SKILL.md
git commit -m "feat(skill-opt): iteration loop + per-version improvement report"
```

---

## Self-Review

**Spec coverage:**
- Reference-based judge vs gold, no ROUGE → Task 3 ✓ (Global Constraints ✓)
- SKILL.md as system prompt, read fresh each call → Task 2 (`run_skill`/`read_skill`) ✓
- Scripted meta-prompt rewrites the whole structured SKILL.md → Task 5 (`optimize_skill`, structural assertions) ✓
- Snapshot each version to `dialog-summary/versions/` before overwrite → Tasks 5–6 (`snapshot_skill`) ✓
- Arize experiments per version (skill-v0…vN) + mean-score comparison → Tasks 4, 6 ✓
- Filter low-score + a few high-score rows for contrast → Task 4 (`collect_feedback`) ✓
- Demo defaults (50 examples, 3 iterations, model ids) → Task 1 config cell ✓
- Data source `samsum_small`, columns `dialogue`/`summary` → Tasks 1–3 ✓

Note: `N_EXAMPLES` is defined as config for clarity and reporting, but the experiment runs over the full `samsum_small` dataset as loaded by `client.experiments.run`. If the dataset is larger than 50 and you need to cap cost, subset it at dataset-creation time in `03_conversations_dataset copy.ipynb` (it already slices `[:100]`); this plan does not re-slice inside the experiment. Flagged so it is not a silent gap.

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code and expected output.

**Type consistency:** `run_skill`/`skill_eval` signatures match the `client.experiments.run` task/evaluator usage in Task 4; `mean_score`/`collect_feedback`/`optimize_skill` all consume the `eval.skill_eval.*` columns consistently; `snapshot_skill(version_idx)` / `apply_skill(new_text)` / `optimize_skill(current_skill, filtered_df)` signatures are used consistently in Task 6.

**Out of scope (per spec):** real Claude Code invocation, ROUGE, Approach 2 folder — none appear in tasks. ✓
