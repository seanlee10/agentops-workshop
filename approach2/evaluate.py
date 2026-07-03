import os, time, warnings
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
DATASET_N = 100
JUDGE_MODEL = "gpt-4o-mini"
# Reuse Approach 1's samsum_small (100 rows) so skill-agent-v* is directly comparable to
# Approach 1's skill-v* in the same Arize dataset.
DATASET = "samsum_small"

client = ArizeClient(api_key=os.getenv("ARIZE_API_KEY"), request_verify=False)

def ensure_eval_dataset(n: int = DATASET_N) -> None:
    """Ensure the eval dataset exists; create it (n rows) only if missing. samsum_small
    already exists from Approach 1, so this is normally a no-op."""
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

def _experiment_exists(version_name: str) -> bool:
    existing = client.experiments.list(space=SPACE_ID, dataset=DATASET)
    return any(e.name == version_name for e in existing.experiments)

def _delete_experiment_if_exists(version_name: str):
    existing = client.experiments.list(space=SPACE_ID, dataset=DATASET)
    match = next((e for e in existing.experiments if e.name == version_name), None)
    if match is None:
        return
    client.experiments.delete(experiment=match.id, space=SPACE_ID, dataset=DATASET)
    # Arize's delete is eventually consistent: poll (bounded) until the name no longer
    # appears before returning, so a subsequent create doesn't race the delete and hit
    # "experiment already exists" (observed in practice with a fresh delete-then-create).
    for _ in range(10):
        if not _experiment_exists(version_name):
            return
        time.sleep(2)

def run_agent_experiment(version_name: str, _retries: int = 3, _suffix: int = 0):
    # A name can be permanently blocked server-side even when experiments.list() no
    # longer shows it -- observed in practice: "already exists" persisted across 10
    # real creation attempts for a name whose earlier run was killed mid-execution,
    # despite list() confirming it absent (a ghost/orphaned record). The _retries
    # loop below handles genuine eventual-consistency races; once that budget is
    # exhausted, fall back to a suffixed name so a single poisoned name can't stall
    # an unattended run.
    name = version_name if _suffix == 0 else f"{version_name}-r{_suffix}"
    _delete_experiment_if_exists(name)
    # use run()'s returned df; list_runs().to_df() is broken in arize SDK v8.37.1
    try:
        experiment, eval_df = client.experiments.run(
            name=name, dataset=DATASET, space=SPACE_ID,
            task=_agent_task, evaluators=[skill_eval], concurrency=3,
        )
    except RuntimeError as exc:
        if "already exists" not in str(exc):
            raise
        if _retries > 0:
            time.sleep(5)
            return run_agent_experiment(version_name, _retries=_retries - 1, _suffix=_suffix)
        if _suffix < 3:
            print(f"  '{name}' appears permanently blocked server-side; "
                  f"falling back to '{version_name}-r{_suffix + 1}'")
            return run_agent_experiment(version_name, _retries=3, _suffix=_suffix + 1)
        raise
    return experiment, eval_df

def mean_score(eval_df) -> float:
    return float(eval_df["eval.skill_eval.score"].astype(float).mean())

def collect_failures(eval_df, n: int = 6) -> list:
    bad = eval_df[eval_df["eval.skill_eval.label"] == "bad"].head(n)
    return bad[["output", "eval.skill_eval.explanation"]].to_dict("records")
