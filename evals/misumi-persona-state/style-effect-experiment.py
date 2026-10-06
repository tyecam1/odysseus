"""Does each fixed persona-state style sentence actually move the behaviour it names? (application -10/-12 follow-up)

For every non-default (dimension, value) in ``RENDER`` this appends the shipped sentence to the persona system prompt (the
shipped placement) and measures a deterministic metric against a no-style baseline, on the local Ollama model, using the release's
real prompt constants. Metrics are proxies chosen to be mechanical, not quality judgements:

  response_depth     words in the answer (thorough up, brief down)
  technical_depth    share of long words (>= 9 letters)            (technical up, plain down)
  structure          share of replies with bullet lines / numbered lines (bullets, stepwise up; prose down)
  intervention_style share of replies that offer or suggest a next step (proactive up, reactive down)

Usage (on the host, release venv):  python style-effect-experiment.py <release-dir> [N]   (N repeats per prompt, default 3)
A sentence "works" when its metric moves in the intended direction by a clear margin; a weak one is a rewording candidate.
Rewording must never ask a persona to drop caveats or safety information.
"""
import json
import re
import statistics
import sys
import urllib.request

release = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
sys.path.insert(0, release)
from routes import misumi_routes as mr  # noqa: E402
from src.misumi_persona_state import DEFAULTS, DIMENSIONS, RENDER, STYLE_HEADER  # noqa: E402
from src.misumi_policy import persona_record  # noqa: E402
from src.seed_order_enforcement import SEED_OUTPUT_RULES  # noqa: E402

PROMPTS = [
    "Explain how a rainbow forms.",
    "How do vaccines train the immune system?",
    "What are some ways to save energy at home?",
    "How should I plan a weekly meal prep?",
]
BULLET = re.compile(r"^\s*(?:[-*•])\s+", re.M)
NUMBERED = re.compile(r"^\s*\d+[.)]\s+", re.M)
OFFER = re.compile(r"(would you like|shall i|do you want me|next step|i can also|let me know if|want me to|if you want)", re.I)


def foundation(persona="misato"):
    record = persona_record(persona)
    system = (
        f"You are {persona}, the Misumi {record.get('role')}. {mr._HONESTY_CONSTRAINTS}\n"
        "Return ONLY one JSON object with keys answer, memory, artifact. answer is the complete user-facing "
        "response. memory is null or {text, category, reason, confidence}; artifact is null or {title, content, reason}."
    )
    return system + f"\n{mr._RATIFICATION_CONSTRAINT}\n{SEED_OUTPUT_RULES}"


def ask(system_text, prompt):
    body = json.dumps({"model": "qwen3:8b", "stream": False, "think": False, "options": {"num_predict": 600},
                       "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        text = json.loads(resp.read().decode())["message"]["content"]
    try:
        return str(json.loads(text[text.index("{"): text.rindex("}") + 1]).get("answer") or text)
    except Exception:
        return text


def metrics(answer):
    words = answer.split()
    long_share = (sum(1 for w in words if len(re.sub(r"\W", "", w)) >= 9) / len(words)) if words else 0.0
    return {"words": len(words), "long": long_share, "bullets": 1.0 if BULLET.search(answer) else 0.0,
            "numbered": 1.0 if NUMBERED.search(answer) else 0.0, "offer": 1.0 if OFFER.search(answer) else 0.0}


TARGET = {  # (dimension, value) -> (metric, intended direction)
    ("response_depth", "brief"): ("words", "down"), ("response_depth", "thorough"): ("words", "up"),
    ("technical_depth", "plain"): ("long", "down"), ("technical_depth", "technical"): ("long", "up"),
    ("structure", "bullets"): ("bullets", "up"), ("structure", "stepwise"): ("numbered", "up"),
    ("structure", "prose"): ("bullets", "down"),
    ("intervention_style", "proactive"): ("offer", "up"), ("intervention_style", "reactive"): ("offer", "down"),
}


def run(sentence):
    base = foundation()
    system = base if sentence is None else f"{base}\n\n{STYLE_HEADER}\n- {sentence}"
    rows = [metrics(ask(system, p)) for p in PROMPTS for _ in range(n)]
    return {k: round(statistics.mean(r[k] for r in rows), 3) for k in rows[0]}


# Candidate rewordings for sentences that moved weakly or not at all in the first round. Only run with `--alts`.
# A candidate must never ask a persona to drop caveats or safety information.
ALTS = {
    ("intervention_style", "proactive"): [
        "End every answer with one concrete next step you could take, phrased as an offer.",
        "After answering, add one short suggestion for what to do next.",
    ],
    ("structure", "bullets"): [
        "Format every answer as a bulleted list, one short point per line, each line starting with '- '.",
        "Answer only in short bullet points (lines starting with '- ').",
    ],
    ("technical_depth", "technical"): [
        "Assume expert knowledge: use precise technical terminology and do not explain basic terms.",
        "Write for a specialist: use the correct technical terms without simplifying them.",
    ],
}
baseline = run(None)
print("baseline", json.dumps(baseline), flush=True)
if "--alts" in sys.argv:
    for (dimension, value), sentences in sorted(ALTS.items()):
        metric, direction = TARGET[(dimension, value)]
        for index, sentence in enumerate(sentences):
            got = run(sentence)
            print(json.dumps({"dimension": dimension, "value": value, "candidate": index, "sentence": sentence, "metric": metric,
                              "baseline": baseline[metric], "with_sentence": got[metric], "all": got}), flush=True)
    sys.exit(0)
for (dimension, value), sentence in sorted(RENDER.items()):
    metric, direction = TARGET[(dimension, value)]
    got = run(sentence)
    delta = got[metric] - baseline[metric]
    moved = (delta < 0) if direction == "down" else (delta > 0)
    rel = (got[metric] / baseline[metric]) if baseline[metric] else None
    print(json.dumps({"dimension": dimension, "value": value, "metric": metric, "intended": direction,
                      "baseline": baseline[metric], "with_sentence": got[metric], "moved_as_intended": moved,
                      "relative": None if rel is None else round(rel, 2), "all": got}), flush=True)
