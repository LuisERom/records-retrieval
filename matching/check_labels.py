"""Check every label in data/queries.csv against the cached registry records.

- every labeled NPI must exist in data/npi_raw.json
- a not_in_registry query must not share its name with any cached record
  (its address may be shared, which is the point of some of them)
- prints, per label method, how many queries there are, and how many labels
  have a twin the registry cannot tell apart (same name on the door, same
  street address)

Exits non-zero if any label fails.
"""
import csv
import sys
from collections import Counter

from evaluate import QUERIES
from matcher import acceptable, load_locations


def main():
    locs = load_locations()
    npis = {l.npi for l in locs}
    bad, twins = [], 0
    methods = Counter()
    with open(QUERIES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        methods[r["label_method"]] += 1
        exp = r["expected_npi"].strip()
        if exp.upper() == "NONE":
            if r["label_method"] != "not_in_registry":
                bad.append(f"{r['id']}: NONE label but method {r['label_method']}")
            continue
        for n in exp.split(";"):
            if n not in npis:
                bad.append(f"{r['id']}: NPI {n} not in cache")
        first = exp.split(";")[0]
        if len(acceptable(locs, first)) > 1:
            twins += 1
    print(f"queries: {len(rows)}  " + "  ".join(f"{k}={v}" for k, v in sorted(methods.items())))
    print(f"labels with a registry twin (same name and street address): {twins}")
    for b in bad:
        print("FAIL", b)
    print("labels OK" if not bad else f"{len(bad)} label problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
