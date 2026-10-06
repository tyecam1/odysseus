"""Application -10 follow-up: where should a user-approved style sentence sit to actually change the reply?

Direct experiment against the local Ollama endpoint (no Odysseus request path), using the release's REAL prompt
constants so the foundation text is the one production sends. Variants for style 'brief' (response_depth):
  none        no style sentence (baseline)
  system      appended to the persona system prompt (what -10 ships)
  late        a separate system message immediately before the user message
  user        the fixed sentence appended to the user turn
Counts words over N runs per prompt. Indicative only (small model, small N); the measurement decides the placement.
Run on the host with the release venv:  python style-placement-experiment.py <release-dir> [N]
"""
import json
import statistics
import sys
import urllib.request

release = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
sys.path.insert(0, release)
from routes import misumi_routes as mr  # noqa: E402
from src.misumi_persona_state import RENDER, STYLE_HEADER, compose_system, style_block  # noqa: E402
from src.seed_order_enforcement import SEED_OUTPUT_RULES  # noqa: E402
from src.misumi_policy import persona_record  # noqa: E402

PROMPTS = ["Explain how a rainbow forms.", "Why is the sky blue during the day?", "How do vaccines train the immune system?"]
VALUES = {"response_depth": "brief"}
SENTENCE = RENDER[("response_depth", "brief")]


def foundation(persona="misato"):
    record = persona_record(persona)
    system = (
        f"You are {persona}, the Misumi {record.get('role')}. {mr._HONESTY_CONSTRAINTS}\n"
        "Return ONLY one JSON object with keys answer, memory, artifact. answer is the complete user-facing "
        "response. memory is null or {text, category, reason, confidence}; artifact is null or {title, content, reason}."
    )
    return system + f"\n{mr._RATIFICATION_CONSTRAINT}\n{SEED_OUTPUT_RULES}"


def build(variant, prompt):
    base = foundation()
    if variant == "system":
        return [{"role": "system", "content": compose_system(base, VALUES)}, {"role": "user", "content": prompt}]
    if variant == "late":
        return [{"role": "system", "content": base}, {"role": "system", "content": style_block(VALUES)},
                {"role": "user", "content": prompt}]
    if variant == "user":
        return [{"role": "system", "content": base}, {"role": "user", "content": f"{prompt}\n\n({SENTENCE})"}]
    return [{"role": "system", "content": base}, {"role": "user", "content": prompt}]


def ask(messages):
    body = json.dumps({"model": "qwen3:8b", "messages": messages, "stream": False, "think": False,
                       "options": {"num_predict": 500}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = json.loads(resp.read().decode())["message"]["content"]
    try:
        answer = json.loads(text[text.index("{"): text.rindex("}") + 1]).get("answer") or text
    except Exception:
        answer = text
    return len(str(answer).split())


results = {}
for variant in ("none", "system", "late", "user"):
    counts = []
    for prompt in PROMPTS:
        for _ in range(n):
            counts.append(ask(build(variant, prompt)))
    results[variant] = {"mean": round(statistics.mean(counts), 1), "median": statistics.median(counts),
                        "min": min(counts), "max": max(counts), "n": len(counts)}
    print(variant, json.dumps(results[variant]), flush=True)
base = results["none"]["mean"]
print("relative_to_none", json.dumps({k: round(v["mean"] / base, 2) for k, v in results.items()}))
