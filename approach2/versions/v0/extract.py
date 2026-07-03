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
