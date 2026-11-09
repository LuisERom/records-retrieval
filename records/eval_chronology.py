"""Score the medical chronology against the answer key.

    python eval_chronology.py --extractor oracle      # answers built from the key: checks the pipeline and scorer
    python eval_chronology.py --extractor corrupted   # oracle with falsified quotes/dates: checks the checker
    python eval_chronology.py --extractor claude --split test2   # the real run (needs an Anthropic API key)

The chronology runs on the pages the deduplicator kept. Claude results are
cached in results/chronology/<split>/<case>.json, so a re-run scores the saved
answers instead of paying again (use --refresh to call the model again).

Measures, over all case files in the split:
- events found: answer-key encounters matched by an entry with the same date,
  a compatible kind and the same provider (recall);
- entries correct: entries that match an answer-key encounter (precision);
- citations on the right record: cited pages that belong to the matched encounter;
- diagnosis codes: answer-key ICD-10 codes of matched encounters that the entry lists;
- dropped by the checker: entries removed because a quote, date or code was
  not on the cited page, even after one repair;
- model calls, tokens and cost.
"""
import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from chron.chronology import build_chronology, claude_extractor, cost_usd, same_provider
from chron.dedup import deduplicate, extract_dates, pdf_texts

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = ROOT / "results" / "chronology"

KIND_OF = {"er_visit": "er_visit", "office_visit": "office_visit", "prior_visit": "office_visit",
           "imaging": "imaging", "lab": "lab", "pt_eval": "therapy_evaluation", "pt_reeval": "therapy_evaluation",
           "pt_visit": "therapy_visit", "injection": "procedure", "surgery": "surgery",
           "procedure": "procedure", "ems": "er_visit"}  # alt4 answer keys use these two; the model schema has no EMS kind
COMPATIBLE = {("procedure", "surgery"), ("surgery", "procedure")}
PAGE_RE = re.compile(r"^=== PAGE (\d+) ===$", re.M)


def oracle_extractor(truth, texts, corrupt=0.0, seed=0):
    """Entries built from the answer key, citing the date line of each page the
    model was shown. With `corrupt`, that share of entries gets a falsified
    quote or date, to show the checker drops them."""
    cid = {p["page"]: p["content_id"] for p in truth["pages"]}
    r = random.Random(seed)

    def extract(user_text, previous_answer=None, repair=None):
        if repair:  # the oracle cannot fix anything: return the same answer
            return json.loads(previous_answer)["entries"], previous_answer, {"input_tokens": 0, "output_tokens": 0}
        shown = [int(n) for n in PAGE_RE.findall(user_text)]
        entries = []
        for ev in truth["events"]:
            pages = [n for n in shown if cid[n] in ev["pages"]]
            if not pages:
                continue
            cites = []
            for n in pages[:3]:
                line = next((ln.strip() for ln in texts[n - 1].splitlines()
                             if ev["date"] in extract_dates(ln) and len(ln.split()) >= 3), None)
                if line:
                    cites.append({"page": n, "quote": line})
            if not cites:
                continue
            e = {"date": ev["date"], "provider": ev["provider"], "kind": KIND_OF[ev["kind"]], "summary": ev["summary"],
                 "diagnosis_codes": [c for c in ev["codes"] if any(c in texts[x["page"] - 1] for x in cites)],
                 "procedure_codes": [], "citations": cites}
            if r.random() < corrupt:
                if r.random() < .5:
                    e["citations"] = [{"page": c["page"], "quote": "Patient denies any pain and was never injured"} for c in cites]
                else:
                    m, d, y = e["date"].split("/")
                    e["date"] = f"{m}/{int(d) % 28 + 1:02d}/{y}"
            entries.append(e)
        raw = json.dumps({"entries": entries})
        return entries, raw, {"input_tokens": 0, "output_tokens": 0}

    return extract


def score(truth, entries):
    cid = {p["page"]: p["content_id"] for p in truth["pages"]}
    events = truth["events"]
    used = set()
    matched = []
    for ev in events:
        want = KIND_OF[ev["kind"]]
        for j, e in enumerate(entries):
            if j in used or e["date"] != ev["date"]:
                continue
            if (e["kind"] == want or (e["kind"], want) in COMPATIBLE) and same_provider(e["provider"], ev["provider"]):
                used.add(j)
                matched.append((ev, e))
                break
    cites = [(ev, c) for ev, e in matched for c in e["citations"]]
    codes_true = [c for ev, _ in matched for c in ev["codes"]]
    codes_found = [c for ev, e in matched for c in ev["codes"] if c in e["diagnosis_codes"]]
    by_kind = Counter(KIND_OF[ev["kind"]] for ev in events)
    found_kind = Counter(KIND_OF[ev["kind"]] for ev, _ in matched)
    return {"events": len(events), "found": len(matched), "entries": len(entries), "correct": len(used),
            "cites": len(cites), "cites_ok": sum(1 for ev, c in cites if cid.get(c["page"]) in ev["pages"]),
            "codes": len(codes_true), "codes_found": len(codes_found), "by_kind": by_kind, "found_kind": found_kind}


def pct(x, d):
    return f"{int(1000 * x / d) / 10:.1f}%" if d else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test", "test2", "alt", "alt2", "alt3", "alt4", "alt5"])
    ap.add_argument("--extractor", default="oracle", choices=["oracle", "corrupted", "claude"])
    ap.add_argument("--cases", type=int, default=0, help="score only the first N case files")
    ap.add_argument("--refresh", action="store_true", help="call the model even if a saved answer exists")
    a = ap.parse_args()
    lines = []

    def say(*parts):
        text = " ".join(str(x) for x in parts)
        print(text)
        lines.append(text)

    cases = sorted((DATA / a.split).iterdir())
    if a.cases:
        cases = cases[:a.cases]
    tot = Counter()
    by_kind, found_kind = Counter(), Counter()
    usage = Counter()
    rep = Counter()
    dropped_examples = []
    for c in cases:
        truth = json.loads((c / "truth.json").read_text(encoding="utf-8"))
        texts = pdf_texts(c / "records.pdf")
        keep = deduplicate(texts).keep
        saved = CACHE / a.split / f"{c.name}.json"
        if a.extractor == "claude" and saved.exists() and not a.refresh:
            out = json.loads(saved.read_text(encoding="utf-8"))
            entries, report = out["entries"], out["report"]
        else:
            if a.extractor == "claude":
                ex = claude_extractor()
            else:
                ex = oracle_extractor(truth, texts, corrupt=0.3 if a.extractor == "corrupted" else 0.0, seed=len(c.name))
            entries, report = build_chronology(texts, keep, ex)
            if a.extractor == "claude":
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_text(json.dumps({"entries": entries, "report": report}, indent=1), encoding="utf-8")
        s = score(truth, entries)
        for k in ("events", "found", "entries", "correct", "cites", "cites_ok", "codes", "codes_found"):
            tot[k] += s[k]
        by_kind.update(s["by_kind"])
        found_kind.update(s["found_kind"])
        usage.update(report["usage"])
        rep["batches"] += report["batches"]
        rep["repaired"] += report["repaired_batches"]
        rep["refused"] += report["refused_batches"]
        rep["dropped"] += len(report["dropped"])
        dropped_examples += [f"{c.name}: {d['reason']}" for d in report["dropped"][:2]]
    say(f"split: {a.split}  extractor: {a.extractor}  case files: {len(cases)}  "
          f"encounters in the answer key: {tot['events']}")
    say(f"events found:              {tot['found']} / {tot['events']} = {pct(tot['found'], tot['events'])}")
    say(f"entries correct:           {tot['correct']} / {tot['entries']} = {pct(tot['correct'], tot['entries'])}")
    say(f"citations on the right record: {tot['cites_ok']} / {tot['cites']} = {pct(tot['cites_ok'], tot['cites'])}")
    say(f"diagnosis codes listed:    {tot['codes_found']} / {tot['codes']} = {pct(tot['codes_found'], tot['codes'])}")
    say(f"dropped by the checker:    {rep['dropped']} entries; batches repaired {rep['repaired']} / {rep['batches']}; "
          f"refused {rep['refused']}")
    say("events found by kind:     " + ", ".join(f"{k} {found_kind[k]}/{n}" for k, n in sorted(by_kind.items())))
    if a.extractor == "claude":
        say(f"model calls: {usage['calls']}  input tokens: {usage['input_tokens']}  output tokens: {usage['output_tokens']}  "
              f"cost: ${cost_usd(usage):.2f} (${cost_usd(usage) / len(cases):.2f} per case file)")
    for x in dropped_examples[:6]:
        say("  dropped:", x)

    if not a.cases:  # a whole split: save exactly what was printed
        out = ROOT / "results" / f"chronology_{a.extractor}_{a.split}.txt"
        out.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


if __name__ == "__main__":
    main()
