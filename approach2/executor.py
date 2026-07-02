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
