import hashlib, json, re, subprocess, sys
from collections import Counter
import yaml

OD = "/home/agent/projects/odysseus-aoteru"
mapping = json.load(open("/tmp/relabel-private/mapping.json"))
text = open("/tmp/relabel_out.txt", encoding="utf-8").read()
rows = {}
for line in text.splitlines():
    line = line.strip()
    if line.startswith('{"id"') and line.endswith("}"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        rows[d["id"]] = d                      # the transcript echoes the answer; the last copy wins
assert set(rows) == set(mapping), (len(rows), set(mapping) - set(rows))
corpus = subprocess.check_output(["git", "-C", OD, "show", "origin/dev:evals/misumi-allocation/corpus-heldout-v1.yaml"])
cases = {c["id"]: c for c in yaml.safe_load(corpus)["cases"]}
AMEND = {"h-res-4", "h-anom-7"}                # preregistered amendment 1 sensitivity reading

def compare(amended):
    out, dec_agree, lead_ok, sup_ok, auth_ok, all_ok = [], 0, 0, 0, 0, 0
    pairs = []
    for rid, cid in sorted(mapping.items(), key=lambda kv: kv[1]):
        c, r = cases[cid], rows[rid]
        e = dict(c["expect"])
        if amended and cid in AMEND:
            e["decision"] = "solo"; e["supports"] = []
        d_ok = r["decision"] == e["decision"]
        l_ok = r["lead"] in e["lead"]
        s_ok = set(r.get("supports") or []) <= set(e.get("supports") or []) and (e["decision"] != "team" or bool(r.get("supports")) == bool(e.get("supports")))
        a_ok = r["authority"] == e.get("authority", "none")
        dec_agree += d_ok; lead_ok += l_ok; sup_ok += s_ok; auth_ok += a_ok; all_ok += (d_ok and l_ok and a_ok)
        pairs.append((e["decision"], r["decision"]))
        if not (d_ok and l_ok and a_ok):
            out.append((cid, c["prompt"], e, r))
    n = len(mapping)
    # Cohen's kappa on the decision axis
    cats = ["solo", "team", "abstain", "escalate"]
    po = dec_agree / n
    a, b = Counter(p[0] for p in pairs), Counter(p[1] for p in pairs)
    pe = sum(a[k] * b[k] for k in cats) / (n * n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return n, dec_agree, lead_ok, sup_ok, auth_ok, all_ok, kappa, out, Counter(pairs)

corpus_sha = hashlib.sha256(corpus).hexdigest()
lines = ["# Blinded relabel of the spent held-out corpus v1 (2026-11-02)", "",
         "Independent relabel of the 50 held-out prompts, per `PREREGISTRATION.md` (non-subject model family, rubric and registry only).", "",
         f"- labeller: Sol `gpt-6-sol` via `codex exec -s read-only` (codex 0.155.1), model line confirmed in the run output; GPT family, not the family that built the candidate or authored the labels",
         f"- corpus `corpus-heldout-v1.yaml` sha256 `{corpus_sha}` (matches the frozen hash); persona registry `personas.yaml` sha256 `a1a7516f2f9e092f...` (the registry the evaluation used)",
         "- blinding: prompts shuffled and renamed r01..r50, category and author `expect` fields removed, no candidate or production output shown; the labeller's only file read was the packet (one `cat packet.md`)",
         "- the labeller saw the rubric as pre-registered including Amendment 1 (consult-edge rule); it did not see the two label-defect notes", ""]
for amended, title in ((False, "As frozen (pre-registered reading)"), (True, "Amendment 1 sensitivity (h-res-4, h-anom-7 expected `solo`)")):
    n, d, l, s, a, allok, k, out, conf = compare(amended)
    lines += [f"## {title}", "",
              f"- decision agreement {d}/{n} ({100*d/n:.0f}%), Cohen's kappa {k:.2f}",
              f"- lead within the author's acceptable set {l}/{n}; supports consistent {s}/{n}; authority {a}/{n}",
              f"- decision, lead and authority all agree {allok}/{n}", "",
              "Decision confusion (author -> relabeller): " + ", ".join(f"{x}->{y}: {v}" for (x, y), v in sorted(conf.items())), ""]
    if out:
        lines += ["| case | prompt | author | relabeller |", "|---|---|---|---|"]
        for cid, prompt, e, r in out:
            lines.append(f"| {cid} | {prompt[:90].replace('|','/')} | {e['decision']} / {','.join(e['lead'])} / {','.join(e.get('supports') or []) or '-'} / {e.get('authority','none')} | {r['decision']} / {r['lead']} / {','.join(r.get('supports') or []) or '-'} / {r['authority']} ({r['confidence']}) |")
        lines.append("")
lines += ["## Reading", "",
          "Disagreements are listed, not resolved. A disagreement is a defect in the rubric, a defect in the author's label, or a defect in the relabel; none of them changes the verdict, which already holds as not promoted. This relabel measures label quality only. It does not use held-out v1 to tune anything (v1 stays spent) and supplies none of the Phase B quantities.", ""]
open("/tmp/relabel-report.md", "w", encoding="utf-8", newline="\n").write("\n".join(lines))
json.dump({mapping[k]: v for k, v in rows.items()}, open("/tmp/relabel-labels.json", "w"), indent=1, sort_keys=True)
print("\n".join(lines))
