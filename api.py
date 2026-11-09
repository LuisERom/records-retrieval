"""One server for both parts, plus the built web page.

    pip install -r requirements.txt
    cd web && npm install && npm run build && cd ..
    uvicorn api:app --port 8010          # http://localhost:8010

The two parts stay independent: matching/match_api.py and
records/records_api.py are complete FastAPI apps of their own (each runs
alone from its folder). This file only puts their routes on one server:

    matching:  GET /api/health, GET /api/queries, POST /api/match
    records:   GET /api/cases, /api/cases/{split}/{case}/dedup | chronology | pages/{n}.png | pages/{n}/highlight
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
# Each part imports its own modules by plain name (matcher, evaluate, chron, ...).
sys.path[:0] = [str(ROOT / "matching"), str(ROOT / "records")]

import match_api  # noqa: E402
import records_api  # noqa: E402

app = FastAPI(title="records-retrieval",
              description="Find the right provider location for a records request, then process what comes back.")
app.include_router(match_api.app.router)
app.include_router(records_api.app.router)

RESULTS = {
    # name: (file, what produced it). Shown on the Overview exactly as the scripts printed them.
    "matching_generated": (ROOT / "matching" / "results" / "evaluate_generated.txt",
                           "cd matching && python evaluate.py --queries generated"),
    "matching_test": (ROOT / "matching" / "results" / "evaluate_test.txt", "cd matching && python evaluate.py"),
    "dedup_test2": (ROOT / "records" / "results" / "dedup_test2.txt", "cd records && python eval_dedup.py --split test2"),
    "dedup_run1": (ROOT / "records" / "results" / "dedup_test_run1.txt", "first held-out run, before the fix (saved record)"),
    "dedup_alt": (ROOT / "records" / "results" / "dedup_alt.txt", "cd records && python eval_dedup.py --split alt"),
    "dedup_alt2": (ROOT / "records" / "results" / "dedup_alt2.txt", "cd records && python eval_dedup.py --split alt2"),
    "dedup_alt5": (ROOT / "records" / "results" / "dedup_alt5.txt", "cd records && python eval_dedup.py --split alt5"),
    "checker_alt5": (ROOT / "records" / "results" / "chronology_corrupted_alt5.txt",
                     "cd records && python eval_chronology.py --extractor corrupted --split alt5"),
    "dedup_alt4": (ROOT / "records" / "results" / "dedup_alt4.txt", "cd records && python eval_dedup.py --split alt4"),
    "checker_alt4": (ROOT / "records" / "results" / "chronology_corrupted_alt4.txt",
                     "cd records && python eval_chronology.py --extractor corrupted --split alt4"),
    "dedup_alt3": (ROOT / "records" / "results" / "dedup_alt3.txt", "cd records && python eval_dedup.py --split alt3"),
    "checker_alt3": (ROOT / "records" / "results" / "chronology_corrupted_alt3.txt",
                     "cd records && python eval_chronology.py --extractor corrupted --split alt3"),
    "checker_alt2": (ROOT / "records" / "results" / "chronology_corrupted_alt2.txt",
                     "cd records && python eval_chronology.py --extractor corrupted --split alt2"),
    "checker_test2": (ROOT / "records" / "results" / "chronology_corrupted_test2.txt",
                      "cd records && python eval_chronology.py --extractor corrupted --split test2"),
    "chronology_claude_test2": (ROOT / "records" / "results" / "chronology_claude_test2_first11.txt",
                                "cd records && python eval_chronology.py --extractor claude --split test2 --cases 11"),
}


@app.get("/api/overview")
def overview():
    """The saved evaluation outputs, verbatim, so the page never shows a number a script did not print."""
    out = {}
    for name, (path, cmd) in RESULTS.items():
        out[name] = {"command": cmd, "text": path.read_text(encoding="utf-8") if path.is_file() else None}
    return out


DIST = ROOT / "web" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
