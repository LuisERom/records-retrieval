"""Evaluate the matcher against labeled queries.

    python evaluate.py                          # hand-written test split (data/queries.csv)
    python evaluate.py --split dev
    python evaluate.py --queries generated      # 1,000 script-generated queries (data/queries_generated.csv)

Three methods are scored on the same queries:
- baseline: closest name, never abstains;
- matcher v1: as frozen on 2026-11-08;
- matcher v2: v1 plus one rule, a records request never goes to a pharmacy or a
  medical-equipment / prosthetics supplier unless the person typed such a word
  (matcher.SUPPLY_TYPES). Scores and thresholds are v1's, unchanged.

An answer counts as correct when it is one of the labeled NPIs, or a record
the registry cannot tell apart from a labeled one (same name on the door and
same street address; matcher.acceptable, computed from the records alone).
A query labeled NONE has no right record in the registry, so the correct
behaviour there is to abstain.

"strict" counts a pharmacy or supplier answer as wrong even where a label
allowed it (two hand-written test labels do); on the generated queries labels
never point at one, so strict and plain agree there.
"""
import argparse
import csv
from pathlib import Path

from matcher import V1, Matcher, acceptable, baseline, load_locations

DATA = Path(__file__).parent / "data"
FILES = {"handwritten": DATA / "queries.csv", "generated": DATA / "queries_generated.csv"}
QUERIES = FILES["handwritten"]


def load(split, which="handwritten"):
    with open(FILES[which], newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if split == "all" or r["split"] == split]


def gold(locs, r):
    exp = r["expected_npi"].strip()
    if exp.upper() == "NONE":
        return None
    ok = set()
    for n in exp.split(";"):
        ok |= acceptable(locs, n)
    return ok


def correct(answer, ok):
    return answer is None if ok is None else answer in ok


def summarize(results, supply):
    """results: list of (row, res, ok). Returns counts for one method."""
    n = len(results)
    right = sum(1 for _, res, ok in results if correct(res["npi"], ok))
    answered = sum(1 for _, res, _ in results if res["npi"] is not None)
    wrong = sum(1 for _, res, ok in results if res["npi"] is not None and not correct(res["npi"], ok))
    abst = sum(1 for _, res, ok in results if res["npi"] is None and ok is not None)
    s_right = sum(1 for _, res, ok in results if correct(res["npi"], ok) and res["npi"] not in supply)
    s_wrong = sum(1 for _, res, ok in results if res["npi"] is not None and (not correct(res["npi"], ok) or res["npi"] in supply))
    first = sum(1 for _, res, ok in results if res["npi"] is None and ok is not None and res["top"] and res["top"]["npi"] in ok)
    return dict(n=n, right=right, answered=answered, wrong=wrong, abst=abst, s_right=s_right, s_wrong=s_wrong, first=first)


def pct(x, d):
    return f"{100 * x / d:.1f}%" if d else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--queries", default="handwritten", choices=list(FILES))
    a = ap.parse_args()
    locs = load_locations()
    versions = {"matcher v1": Matcher(locs, **V1), "matcher v2": Matcher(locs)}
    supply = {l.npi for l in locs if l.supply_only}
    rows = load(a.split, a.queries)
    oks = [gold(locs, r) for r in rows]
    base = sum(1 for r, ok in zip(rows, oks) if correct(baseline(locs, r["query_name"]), ok))
    runs = {name: [(r, m.match(r["query_name"], r["query_address"], r["query_zip"]), ok) for r, ok in zip(rows, oks)]
            for name, m in versions.items()}
    n = len(rows)
    print(f"registry cache: {len({l.npi for l in locs})} NPIs with a NY practice location, {len(locs)} practice locations, "
          f"{len({(l.house, tuple(l.street), l.zip) for l in locs})} distinct street addresses")
    print(f"queries: {a.queries}  split: {a.split}  queries: {n}  (of which {sum(ok is None for ok in oks)} have no right record)")
    print("| method                  | correct      | accuracy | answered | right when it answered | confidently wrong |")
    print("|-------------------------|--------------|----------|----------|------------------------|-------------------|")
    print(f"| baseline (closest name) | {base:>4d} / {n:<5d} | {pct(base, n):>8s} | {n:>8d} | {pct(base, n):>22s} | {n - base:>17d} |")
    stats = {}
    for name, res in runs.items():
        s = stats[name] = summarize(res, supply)
        print(f"| {name:<23} | {s['right']:>4d} / {n:<5d} | {pct(s['right'], n):>8s} | {s['answered']:>8d} | "
              f"{pct(s['answered'] - s['wrong'], s['answered']):>22s} | {s['wrong']:>17d} |")
    for name, s in stats.items():
        print(f"strict, {name} (a pharmacy or supplier answer never counts as right): {s['s_right']} / {n} = {pct(s['s_right'], n)}; "
              f"confidently wrong {s['s_wrong']}; right when it answered {pct(s['answered'] - s['s_wrong'], s['answered'])}")
    s = stats["matcher v2"]
    print(f"matcher v2: of the {s['abst']} abstentions, the right record was ranked first in {s['first']} "
          f"(it held back because the next record scored too close)")
    print("misses of matcher v2:")
    for r, res, ok in runs["matcher v2"]:
        if correct(res["npi"], ok):
            continue
        kind = "ABSTAIN" if res["npi"] is None else "WRONG"
        t = res["top"] or {}
        print(f"  [{kind}] {r['id']} {r['query_name']!r} | {r['query_address']!r} | {r['query_zip']!r}"
              f" -> want {r['expected_npi']}; top {t.get('npi')} {t.get('name', '')!r}"
              f" @ {t.get('address', '')!r} (score {res['confidence']}, margin {res['margin']})")


if __name__ == "__main__":
    main()
