"""Grid-search the matcher's knobs on the DEV split only and print the best
settings. Copy them into DEFAULTS in matcher.py by hand. The test split is
never read here.

    python tune.py

The two weights change the ranking, so each weight pair is scored once; the
two thresholds only decide whether to answer, so they are swept over the
stored scores without re-matching.
"""
import itertools

from evaluate import correct, gold, load
from matcher import Matcher, load_locations


def main():
    locs = load_locations()
    rows = load("dev")
    golds = [gold(locs, r) for r in rows]
    best = None
    for w, rw in itertools.product([0.2, 0.3, 0.4, 0.5, 0.6, 0.7], [0.0, 0.15, 0.25, 0.4]):
        m = Matcher(locs, name_weight=w, reverse_weight=rw, min_score=0.0, min_margin=-1.0, exclude_supply=False)  # v1 tuning, as run
        scored = []
        for r in rows:
            res = m.match(r["query_name"], r["query_address"], r["query_zip"])
            scored.append((res["top"]["npi"] if res["top"] else None, res["confidence"], res["margin"]))
        for s, mg in itertools.product([0.3, 0.4, 0.5, 0.55, 0.6, 0.7], [0.0, 0.01, 0.02, 0.04, 0.06]):
            right = wrong = abst = 0
            for (npi, conf, margin), ok in zip(scored, golds):
                ans = npi if (conf >= s and margin >= mg) else None
                if correct(ans, ok):
                    right += 1
                elif ans is None:
                    abst += 1
                else:
                    wrong += 1
            # Fewest confident errors first (a wrong answer sends a records
            # request to the wrong office), then most correct, then (on a tie) the strictest thresholds.
            key = (-wrong, right, s, mg)  # ties: the strictest thresholds
            if best is None or key > best[0]:
                best = (key, w, rw, s, mg, abst, wrong, right)
    _, w, rw, s, mg, abst, wrong, right = best
    print(f"dev best: name_weight={w} reverse_weight={rw} min_score={s} min_margin={mg} "
          f"-> {right}/{len(rows)} correct, {abst} abstained, {wrong} wrong")


if __name__ == "__main__":
    main()
