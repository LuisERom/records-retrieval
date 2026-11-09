"""Explain the duplicates the method misses on a split (dev by default).

    python diagnose_dedup.py --split dev

For each missed copy: the copy mechanism, and why the pair to its kept copy
failed (phrase containment, or a number on the smaller page not found on the
larger one).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from chron.dedup import MIN_WORDS, Params, canon, deduplicate, is_duplicate, page_features, page_features_v2, pdf_texts

DATA = Path(__file__).parent / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test", "test2", "alt", "alt2", "alt3", "alt4", "alt5"])
    ap.add_argument("--show", type=int, default=8)
    ap.add_argument("--version", default="v2", choices=["v1", "v2"])
    a = ap.parse_args()
    reasons, shown = Counter(), 0
    for c in sorted((DATA / a.split).iterdir()):
        truth = json.loads((c / "truth.json").read_text(encoding="utf-8"))["pages"]
        texts = pdf_texts(c / "records.pdf")
        res = deduplicate(texts, Params(version=a.version))
        feats = page_features_v2(texts) if a.version == "v2" else page_features(texts)
        cid = [p["content_id"] for p in truth]
        for i in range(len(cid)):
            r = res.representative[i]
            if not res.keep[i] or cid[r] == cid[i] and r == i:
                pass
            # A missed copy: kept, but another kept page has the same content.
            if res.keep[i]:
                others = [j for j in range(len(cid)) if j != i and res.keep[j] and cid[j] == cid[i] and j < i]
                if not others:
                    continue
                j = others[0]
                x, y = feats[i], feats[j]
                small, big = (x, y) if len(x.sh) <= len(y.sh) else (y, x)
                cont = len(small.sh & big.sh) / len(small.sh) if small.sh else 0
                missing = sorted(t for t in small.nums if t not in big.nums and canon(t) not in big.ctoks)
                why = ("too few words" if min(x.words, y.words) < MIN_WORDS else
                       f"containment {cont:.2f}" if cont < Params().min_containment else
                       "numbers differ" if not is_duplicate(x, y, Params(version=a.version)) else
                       "pair passes but not joined (LSH miss)")
                key = (truth[i]["mechanism"], why.split(" ")[0] + (" " + why.split(" ")[1] if why.startswith("numbers") else ""))
                reasons[key] += 1
                if shown < a.show:
                    shown += 1
                    print(f"{c.name} p{i + 1} ({truth[i]['mechanism']}) vs p{j + 1} ({truth[j]['mechanism']}) "
                          f"[{cid[i]}]: {why}; missing numbers: {missing[:8]}")
    print()
    for (mech, why), n in reasons.most_common():
        print(f"{n:5d}  {mech:<16} {why}")


if __name__ == "__main__":
    main()
