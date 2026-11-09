"""Score duplicate-page detection against the answer key.

    python eval_dedup.py --split test2   # fresh held-out split (the reported number)
    python eval_dedup.py --split test    # first held-out split; its errors were studied, so no longer held out
    python eval_dedup.py --split dev

For each method, over all case files in the split:
- duplicates removed: of the pages that are copies of a page kept elsewhere
  (the ideal removal), how many the method removed;
- duplicates left in: copies the method kept;
- content lost: original pages with NO copy kept. This is the error that
  matters most for a legal file: a removed page that held unique evidence;
- pair precision / recall: over all pairs of pages that are copies of each other.

Methods:
- exact text: pages whose extracted text is identical (whitespace aside).
- GnoRA file check, per page: GnoRA's text_similarity rule as written for whole
  files (raw text, 5-word phrases, Jaccard >= 85%), applied to each page pair.
- this method v1: chron/dedup.py as frozen for the test2 run (Params(version="v1")).
- this method v2: v1 with format-independent rules (character fingerprints, page stamps found by
  behavior, transmission lines by vocabulary); see chron/dedup.py.
"""
import argparse
import hashlib
import json
import time
from itertools import combinations
from pathlib import Path

from chron.dedup import TO_DIGIT, Params, canon, clean_lines, deduplicate, is_transmission_line, pdf_texts, shingles, stamp_shapes, words_of

DATA = Path(__file__).parent / "data"
REPORTED = "this method v3"  # whose lost pages are listed below the table


def groups_to_result(n, groups):
    rep = list(range(n))
    for g in groups:
        for i in g:
            rep[i] = g[0]
    return [rep[i] == i for i in range(n)], rep


def exact_text(texts):
    by = {}
    for i, t in enumerate(texts):
        by.setdefault(hashlib.sha256(" ".join(t.split()).encode()).hexdigest(), []).append(i)
    return groups_to_result(len(texts), [g for g in by.values() if len(g) > 1])


def gnora_file_rule(texts):
    sh = [shingles(words_of(t.lower())) for t in texts]
    parent = list(range(len(texts)))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for i, j in combinations(range(len(texts)), 2):
        a, b = sh[i], sh[j]
        if a and b and round(100 * len(a & b) / len(a | b)) >= 85:
            parent[find(i)] = find(j)
    cl = {}
    for i in range(len(texts)):
        cl.setdefault(find(i), []).append(i)
    return groups_to_result(len(texts), [sorted(g) for g in cl.values() if len(g) > 1])


def ours_v1(texts):
    r = deduplicate(texts, Params(version="v1"))
    return r.keep, r.representative


def ours_v3(texts):
    r = deduplicate(texts, Params(version="v3"))
    return r.keep, r.representative


def ours(texts):
    r = deduplicate(texts, Params(version="v2"))
    return r.keep, r.representative


def pct(x, d):
    """Percent rounded down, so 4334 of 4336 never prints as 100.0%."""
    return f"{int(1000 * x / d) / 10:5.1f}%" if d else "  n/a"


def visible_words(text, shapes=frozenset()):
    """The words of a page's record content: transmission lines (fax headers, stamps,
    page counters) and page-stamp numbers left out, as chron/dedup.py v2 does."""
    import re
    lines = [ln for ln in text.splitlines() if ln.strip() and not is_transmission_line(ln)]
    words = [w for ln in lines for w in ln.split()
             if not (re.search(r"\d{4}", w) and re.sub(r"\d", "#", w.strip(".,;:()[]").translate(TO_DIGIT).upper()) in shapes)]
    return set(words_of(canon(" ".join(words))))


def score(truth_pages, keep, rep):
    cid = [p["content_id"] for p in truth_pages]
    n = len(cid)
    kept_content = {cid[i] for i in range(n) if keep[i]}
    ideal_removable = n - len(set(cid))
    removed_ok = sum(1 for i in range(n) if not keep[i] and cid[i] in kept_content)
    # Copies left in: kept pages beyond the first kept page of each content.
    seen, left_in = set(), 0
    for i in range(n):
        if keep[i]:
            left_in += cid[i] in seen
            seen.add(cid[i])
    lost = len(set(cid) - kept_content)
    # Pairwise: predicted pairs = pages sharing a representative.
    pred, true = {}, {}
    for i in range(n):
        pred.setdefault(rep[i], []).append(i)
        true.setdefault(cid[i], []).append(i)
    pp = {pr for g in pred.values() for pr in combinations(sorted(g), 2)}
    tp = {pr for g in true.values() for pr in combinations(sorted(g), 2)}
    return {"pages": n, "removable": ideal_removable, "removed_ok": removed_ok, "left_in": left_in, "lost": lost,
            "pairs_tp": len(pp & tp), "pairs_pred": len(pp), "pairs_true": len(tp)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test2", choices=["dev", "test", "test2", "alt", "alt2", "alt3", "alt4", "alt5"])
    a = ap.parse_args()
    cases = sorted((DATA / a.split).iterdir())
    methods = {"exact text": exact_text, "GnoRA file check, per page": gnora_file_rule, "this method v1": ours_v1,
               "this method v2": ours, "this method v3": ours_v3}
    tot = {m: {} for m in methods}
    secs = {m: 0.0 for m in methods}
    lost_detail = []
    for c in cases:
        truth = json.loads((c / "truth.json").read_text(encoding="utf-8"))
        texts = pdf_texts(c / "records.pdf")
        for m, fn in methods.items():
            t0 = time.perf_counter()
            keep, rep = fn(texts)
            secs[m] += time.perf_counter() - t0
            s = score(truth["pages"], keep, rep)
            for k, v in s.items():
                tot[m][k] = tot[m].get(k, 0) + v
            if m == REPORTED and s["lost"]:
                # For each lost original: does any copy of it hold a word (look-alikes
                # canonicalized, transmission artifacts removed) that the page it was
                # merged into does not? If not, nothing visible was lost.
                cid = [p["content_id"] for p in truth["pages"]]
                kept = {cid[i] for i in range(len(cid)) if keep[i]}
                for x in sorted(set(cid) - kept):
                    copies = [i for i in range(len(cid)) if cid[i] == x]
                    shapes = stamp_shapes(texts)
                    extra = set().union(*(visible_words(texts[i], shapes) - visible_words(texts[rep[i]], shapes) for i in copies))
                    kind = next(p["doc_kind"] for p in truth["pages"] if p["content_id"] == x)
                    lost_detail.append((f"{c.name}: {x} ({kind})", sorted(extra)))
    t = tot[REPORTED]
    print(f"split: {a.split}  case files: {len(cases)}  pages: {t['pages']}  "
          f"duplicate pages in the answer key: {t['removable']} ({100 * t['removable'] / t['pages']:.1f}%)")
    print("| method                      | duplicates removed | duplicates left in | content lost | pair precision | pair recall | seconds |")
    print("|-----------------------------|--------------------|--------------------|--------------|----------------|-------------|---------|")
    for m in methods:
        s = tot[m]
        print(f"| {m:<27} | {s['removed_ok']:>5} / {s['removable']:<5} {pct(s['removed_ok'], s['removable'])} "
              f"| {s['left_in']:>18} | {s['lost']:>12} | {pct(s['pairs_tp'], s['pairs_pred']):>14} "
              f"| {pct(s['pairs_tp'], s['pairs_true']):>11} | {secs[m]:>7.1f} |")
    print(f"content lost by {REPORTED} (original pages with no copy kept):", len(lost_detail))
    print("  of those, with words not on the page they were merged into:",
          sum(1 for _, extra in lost_detail if extra))
    for name, extra in lost_detail[:40]:
        print("  ", name, "| words not on the kept page:", " ".join(extra[:12]) if extra else "none")


if __name__ == "__main__":
    main()
