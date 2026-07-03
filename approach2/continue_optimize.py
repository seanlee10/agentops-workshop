"""Continue the keep-best optimizer loop from the current best skill version (v2),
running further rounds until 2 consecutive rounds fail to beat the best score.

Does NOT restart from scratch: the live skill dir is already v2 (the best from the
original optimize.py run). This re-evaluates it fresh under a distinctly-named
experiment ("skill-agent-v2-resume") to get real per-row failures for the next
optimizer round -- the original run's eval_df was never persisted to disk -- then
continues the version numbering forward (v3, v4, ...).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev
from optimize import snapshot, restore, run_optimizer, VERSIONS, FAILURES

MAX_FLAT_ROUNDS = 2    # stop once this many consecutive rounds fail to improve
MAX_TOTAL_ROUNDS = 20  # defensive backstop only (infinite-loop safety net), not a real cap

def main():
    VERSIONS.mkdir(exist_ok=True)
    ev.ensure_eval_dataset()

    # Resume point: re-evaluate the current (v2) skill fresh under a new experiment name
    # so we don't overwrite the historical "skill-agent-v2" record, while getting the
    # failures needed to feed the next round.
    _, df = ev.run_agent_experiment("skill-agent-v2-resume")
    best_score = ev.mean_score(df)
    best_dir = snapshot(2)  # re-confirm versions/v2 matches the live (best) skill
    last_df = df
    history = [("skill-agent-v2-resume", best_score)]
    print(f"skill-agent-v2-resume (fresh baseline) mean score: {best_score:.3f}")

    flat_rounds = 0
    i = 3
    rounds_run = 0
    while flat_rounds < MAX_FLAT_ROUNDS and rounds_run < MAX_TOTAL_ROUNDS:
        FAILURES.write_text(json.dumps(ev.collect_failures(last_df), indent=2))
        run_optimizer()
        _, df = ev.run_agent_experiment(f"skill-agent-v{i}")
        score = ev.mean_score(df)
        last_df = df
        history.append((f"skill-agent-v{i}", score))
        print(f"skill-agent-v{i} mean score: {score:.3f}")
        if score > best_score:
            best_score = score
            best_dir = snapshot(i)
            flat_rounds = 0
        else:
            restore(best_dir)  # reject regression
            flat_rounds += 1
        i += 1
        rounds_run += 1

    print("\n=== continuation history ===")
    for name, s in history:
        print(f"{name}: {s:.3f}")
    best = max(history, key=lambda x: x[1])
    print(f"\nResume baseline: {history[0][1]:.3f} | Best: {best[0]} @ {best[1]:.3f}")
    if flat_rounds >= MAX_FLAT_ROUNDS:
        print(f"Stopped: {flat_rounds} consecutive rounds failed to improve on the best.")
    else:
        print(f"Stopped: hit the {MAX_TOTAL_ROUNDS}-round safety backstop (unexpected).")
    print("Skill dir left at best version. Compare skill-agent-v* in the Arize UI.")

if __name__ == "__main__":
    main()
