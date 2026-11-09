"""Generate the synthetic case files and their answer keys.

    python generate.py

Writes data/<split>/<case_id>/records.pdf and truth.json. The dev split is
for building and tuning; the test split uses different seeds, more OCR noise,
more faxed and re-sent copies, and one copy mechanism the dev split never
has (pages cropped at the top or bottom), so a method tuned on dev is checked
on files it was not shaped around.
"""
import json
import shutil
from collections import Counter
from pathlib import Path

from chron.bundle import DEV, TEST, make_bundle, render_pdf, truth_dict
from chron.synth import make_case

DATA = Path(__file__).parent / "data"
SPLITS = {"dev": (DEV, range(1, 9)), "test": (TEST, range(1001, 1017)), "test2": (TEST, range(2001, 2017))}


def main():
    for split, (settings, seeds) in SPLITS.items():
        out = DATA / split
        if out.exists():
            shutil.rmtree(out)
        tot_pages = tot_unique = 0
        for seed in seeds:
            case = make_case(seed, f"{split}-{seed}")
            pages, truth = make_bundle(case, seed, settings)
            d = out / case.case_id
            d.mkdir(parents=True)
            render_pdf(pages, d / "records.pdf", f"MC{seed:04d}")
            (d / "truth.json").write_text(json.dumps(truth_dict(case, truth), indent=1), encoding="utf-8")
            uniq = len({t.content_id for t in truth})
            tot_pages += len(pages)
            tot_unique += uniq
            mech = Counter(t.mechanism for t in truth)
            print(f"{split} {case.case_id}: {len(pages)} pages, {uniq} unique, "
                  f"{100 * (1 - uniq / len(pages)):.0f}% duplicate, {len(case.events)} events | {dict(mech)}")
        print(f"{split}: {len(list(seeds))} cases, {tot_pages} pages, {100 * (1 - tot_unique / tot_pages):.1f}% duplicate\n")


if __name__ == "__main__":
    main()
