import hashlib, json, os, random, re, subprocess, sys
import yaml

OD = "/home/agent/projects/odysseus-aoteru"
reg_path = "/home/agent/aoteru-worktrees/misumi-ret-20261027/config/personas.yaml"
reg_bytes = open(reg_path, "rb").read()
assert hashlib.sha256(reg_bytes).hexdigest().startswith("a1a7516f2f9e092f"), "registry is not the one the evaluation used"
corpus_text = subprocess.check_output(["git", "-C", OD, "show", "origin/dev:evals/misumi-allocation/corpus-heldout-v1.yaml"])
assert hashlib.sha256(corpus_text).hexdigest() == "1f1b9808cad4ed1938d66b0ff274828af0da9d741f06b4f9bec6570ef74884e2", "corpus hash differs from the frozen one"
cases = yaml.safe_load(corpus_text)["cases"]
prereg = subprocess.check_output(["git", "-C", OD, "show", "origin/dev:evals/misumi-allocation/PREREGISTRATION.md"]).decode()
rubric = prereg.split("## Rubric for the expected decision (fixed before labelling)")[1].split("## Policies compared")[0]
amend = "## Amendment 1" + prereg.split("## Amendment 1")[1].split("## Held-out corpus hash")[0]
# the rubric paragraph's last bullet describes the author's own labelling; the labeller does not need it
rubric = rubric.split("- `expect.lead` lists")[0].rstrip() + "\n"
amend = amend.split("Two held-out labels")[0].rstrip() + "\n"

rng = random.Random(20261102)
order = list(range(len(cases)))
rng.shuffle(order)
mapping, items = {}, []
for n, idx in enumerate(order, 1):
    c = cases[idx]
    rid = f"r{n:02d}"
    mapping[rid] = c["id"]
    item = {"id": rid, "prompt": c["prompt"]}
    if c.get("prior_lead"):
        item["prior_lead"] = c["prior_lead"]
    items.append(item)

os.makedirs("/tmp/relabel", exist_ok=True)
os.makedirs("/tmp/relabel-private", exist_ok=True)
packet = f"""# Blinded relabelling task

You are labelling {len(items)} short household-assistant requests using ONLY the rubric and the persona registry below. You have not been shown anyone else's labels and must not look for them: do not read any file other than this one, do not browse, do not run commands that search the filesystem. Work from this document alone.

For each request decide the allocation the rubric implies and output ONE JSON object per line (JSON Lines), nothing else after the final line except a short "NOTES:" paragraph of at most 6 lines about rubric ambiguities you hit.

Fields: `id`; `decision` (solo|team|abstain|escalate); `lead` (the single persona id you would choose as lead; "aoteru" when no specialist applies); `supports` (persona ids you would recruit; [] unless team); `authority` (none = read-only answer; scoped_write = a write inside the lead's own scope such as adding a list item or archiving; playback_control = controlling music playback; blocked = an action beyond what the lead may do: sending email, moving money, destructive deletion, covert recording); `confidence` (low|medium|high); `reason` (one sentence naming the rubric clause).
`prior_lead`, when present, is the previous turn's lead persona (a follow-up).

## Rubric (fixed before any labelling)
{rubric}
{amend}
## Persona registry (ratified canon; ids, roles, routing intents and aliases, consult edges)
```yaml
{reg_bytes.decode()}
```

## Requests
{chr(10).join(json.dumps(i, ensure_ascii=False) for i in items)}
"""
open("/tmp/relabel/packet.md", "w", encoding="utf-8", newline="\n").write(packet)
json.dump(mapping, open("/tmp/relabel-private/mapping.json", "w"), indent=1)
print("cases", len(items), "packet bytes", len(packet))
