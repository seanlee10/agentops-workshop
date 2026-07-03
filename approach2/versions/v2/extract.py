"""Read a speaker-labeled dialogue on stdin; print JSON {speakers, salient_turns, emotional_turns}."""
import sys, json, re

DECISION_HINTS = ("will", "let's", "lets", "plan", "meet", "tomorrow", "tonight",
                  "agree", "should", "need to", "going to", "gonna",
                  "recommend", "suggest", "advice", "technique", "idea",
                  "how about", "why don't", "instead of", "decide")

# Emotional/relational-stakes turns are often the actual point of a dialogue
# (e.g. venting, conflict, surprise) even when no plan/decision word appears.
EMOTION_HINTS = ("upset", "angry", "mad", "sad", "worried", "confused",
                 "frustrated", "annoyed", "disappointed", "hurt", "forgot",
                 "forget", "remind", "sorry", "afraid", "nervous", "sick",
                 "unhappy", "happy", "excited", "scared", "surprised")

def parse(dialogue: str):
    speakers, salient, emotional = [], [], []
    for line in dialogue.splitlines():
        m = re.match(r"\s*([A-Za-z][\w .'-]{0,30}?):\s*(.*)", line)
        if not m:
            continue
        who, text = m.group(1).strip(), m.group(2).strip()
        if who not in speakers:
            speakers.append(who)
        low = text.lower()
        if any(h in low for h in DECISION_HINTS):
            salient.append(f"{who}: {text}")
        if any(h in low for h in EMOTION_HINTS):
            emotional.append(f"{who}: {text}")
    return {"speakers": speakers, "salient_turns": salient, "emotional_turns": emotional}

if __name__ == "__main__":
    print(json.dumps(parse(sys.stdin.read())))
