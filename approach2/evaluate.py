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
