import os, sys, json, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev

APPROACH2 = Path(__file__).resolve().parent
REPO_ROOT = APPROACH2.parent
SKILL_DIR = APPROACH2 / ".claude/skills/dialog-summary"
VERSIONS = APPROACH2 / "versions"
FAILURES = APPROACH2 / "failures.json"
N_ITER = 2
# Harness files the optimizer must never edit; reverted after each optimizer run so a
# stray edit outside the (snapshotted) skill dir cannot corrupt the eval harness.
HARNESS_FILES = ["approach2/executor.py", "approach2/evaluate.py", "approach2/optimize.py"]

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
    # A timeout must not crash the unattended loop: if the optimizer is killed mid-edit,
    # keep-best still judges whatever it left behind (a broken skill scores low -> reverted).
    try:
        subprocess.run(["claude", "-p", OPT_PROMPT, "--dangerously-skip-permissions"],
                       cwd=str(APPROACH2), timeout=600)
    except subprocess.TimeoutExpired:
        print("  optimizer timed out (600s); proceeding — keep-best will judge the partial edit")
    # Scope guard: the optimizer runs with --dangerously-skip-permissions and could edit
    # files outside the snapshotted skill dir. restore() only reverts the skill dir, so undo
    # any edits to the harness files here to keep the eval pipeline intact across iterations.
    subprocess.run(["git", "checkout", "--"] + HARNESS_FILES, cwd=str(REPO_ROOT))

def main():
    VERSIONS.mkdir(exist_ok=True)
    ev.ensure_eval_dataset()
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
