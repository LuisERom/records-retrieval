"""Web API for the records viewer, plus the built page.

    pip install -r requirements.txt
    uvicorn records_api:app --port 8010   # this part's API alone, run from its folder

The repo's web app serves this together with the other part: see ../api.py.

Routes:
    GET /api/cases                                  case files per split
    GET /api/cases/{split}/{case}/dedup             per-page duplicate decisions and groups
    GET /api/cases/{split}/{case}/chronology        the chronology (Claude's saved answer if there is one,
                                                    else the oracle built from the answer key, labeled so)
    GET /api/cases/{split}/{case}/pages/{n}.png     one PDF page as an image
    GET /api/cases/{split}/{case}/pages/{n}/highlight?quote=...
                                                    where a quote sits on the page, as boxes (0-1 fractions)
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chron.chronology import build_chronology, norm
from chron.dedup import content_lines, deduplicate, pdf_texts, stamp_shapes, words_of
from eval_chronology import CACHE, KIND_OF, oracle_extractor, score

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "web" / "dist"
SPLITS = ("dev", "test", "test2", "alt", "alt2", "alt3", "alt4", "alt5")

app = FastAPI(title="records-chronology", description="Duplicate removal and a checked medical chronology.")


def case_dir(split: str, case: str) -> Path:
    if split not in SPLITS:
        raise HTTPException(404, "unknown split")
    d = DATA / split / case
    if not (d / "records.pdf").is_file() or d.parent != DATA / split:
        raise HTTPException(404, "unknown case")
    return d


@lru_cache(maxsize=8)
def load(split: str, case: str):
    d = case_dir(split, case)
    truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))
    texts = pdf_texts(d / "records.pdf")
    return truth, texts, deduplicate(texts)


class CaseInfo(BaseModel):
    split: str
    case: str
    pages: int
    patient: str
    accident_date: str


class PageInfo(BaseModel):
    page: int                 # 1-based PDF page
    kept: bool
    copy_of: int              # page kept for this content (itself if kept)
    mechanism: str            # from the answer key: how this copy was made
    doc_kind: str
    key_says_duplicate: bool  # answer key: another page carries the same content earlier
    correct: bool             # kept/removed agrees with the answer key


class Group(BaseModel):
    kept: int
    copies: list[int]
    label: str               # provider and document title from the kept page


class DedupView(BaseModel):
    pages: list[PageInfo]
    groups: list[Group]
    total: int
    kept: int
    removed: int
    key_duplicates: int
    lost: list[str]           # answer-key originals with no copy kept


class Citation(BaseModel):
    page: int
    quote: str


class EntryView(BaseModel):
    date: str
    provider: str
    kind: str
    summary: str
    diagnosis_codes: list[str]
    procedure_codes: list[str]
    citations: list[Citation]
    matches_key: bool


class Dropped(BaseModel):
    date: str
    provider: str
    kind: str
    reason: str


class ChronologyView(BaseModel):
    source: Literal["claude", "oracle"]
    note: str
    entries: list[EntryView]
    dropped: list[Dropped]
    events_in_key: int
    events_found: int
    usage: dict


@app.get("/api/cases", response_model=list[CaseInfo])
def cases():
    out = []
    for split in SPLITS:
        if not (DATA / split).is_dir():
            continue
        for d in sorted((DATA / split).iterdir()):
            t = json.loads((d / "truth.json").read_text(encoding="utf-8"))
            out.append(CaseInfo(split=split, case=d.name, pages=len(t["pages"]),
                                patient=f"{t['patient']['first']} {t['patient']['last']}", accident_date=t["accident_date"]))
    return out


@app.get("/api/cases/{split}/{case}/dedup", response_model=DedupView)
def dedup(split: str, case: str):
    truth, texts, res = load(split, case)
    cid = [p["content_id"] for p in truth["pages"]]
    first = {}
    for i, c in enumerate(cid):
        first.setdefault(c, i)
    kept_count = {}
    for i, c in enumerate(cid):
        kept_count[c] = kept_count.get(c, 0) + res.keep[i]
    kept_content = {c for c, k in kept_count.items() if k}
    pages = []
    for i, p in enumerate(truth["pages"]):
        # Right if removed while another copy of its content is kept, or kept as the only copy kept.
        correct = kept_count[cid[i]] == 1 if res.keep[i] else cid[i] in kept_content
        pages.append(PageInfo(page=i + 1, kept=res.keep[i], copy_of=res.representative[i] + 1,
                              mechanism=p["mechanism"], doc_kind=p["doc_kind"],
                              key_says_duplicate=first[cid[i]] != i, correct=correct))
    shapes = stamp_shapes(texts)

    def label(i):
        lines = [ln.strip() for ln in content_lines(texts[i], shapes) if ln.strip() and not set(ln.strip()) <= set("-")]
        if not lines:
            return ""
        # Provider line, then the document title: the next all-caps line with no digits (skips the address).
        title = next((ln for ln in lines[1:6] if ln.isupper() and not any(c.isdigit() for c in ln)), "")
        return (lines[0] + (" · " + title if title else ""))[:90]

    groups = []
    for g in res.groups:
        k = next(x for x in g if res.keep[x])
        groups.append(Group(kept=k + 1, copies=[x + 1 for x in g if not res.keep[x]], label=label(k)))
    return DedupView(pages=pages, groups=groups, total=len(texts), kept=sum(res.keep),
                     removed=len(texts) - sum(res.keep), key_duplicates=len(cid) - len(set(cid)),
                     lost=sorted(set(cid) - kept_content))


@lru_cache(maxsize=8)
def chronology_for(split: str, case: str):
    truth, texts, res = load(split, case)
    saved = CACHE / split / f"{case}.json"
    if saved.is_file():
        out = json.loads(saved.read_text(encoding="utf-8"))
        return "claude", out["entries"], out["report"]
    entries, report = build_chronology(texts, res.keep, oracle_extractor(truth, texts), workers=1)
    return "oracle", entries, report


@app.get("/api/cases/{split}/{case}/chronology", response_model=ChronologyView)
def chronology(split: str, case: str):
    truth, _, _ = load(split, case)
    source, entries, report = chronology_for(split, case)
    s = score(truth, entries)
    keyed = {(ev["date"], KIND_OF[ev["kind"]]) for ev in truth["events"]}
    note = ("Claude's answer, checked against the cited pages (saved run)." if source == "claude" else
            "entries built from the answer key, not by a model. It shows how the viewer and the checker "
            "work until a Claude run is saved for this case.")
    return ChronologyView(
        source=source, note=note,
        entries=[EntryView(**{k: e[k] for k in ("date", "provider", "kind", "summary", "diagnosis_codes", "procedure_codes")},
                           citations=[Citation(**c) for c in e["citations"]],
                           matches_key=(e["date"], e["kind"]) in keyed) for e in entries],
        dropped=[Dropped(date=d["entry"].get("date", ""), provider=d["entry"].get("provider", ""),
                         kind=d["entry"].get("kind", ""), reason=d["reason"]) for d in report["dropped"]],
        events_in_key=s["events"], events_found=s["found"], usage=report["usage"])


@lru_cache(maxsize=256)
def page_png(split: str, case: str, n: int) -> bytes:
    import fitz
    with fitz.open(case_dir(split, case) / "records.pdf") as doc:
        if not 1 <= n <= len(doc):
            raise HTTPException(404, "no such page")
        return doc[n - 1].get_pixmap(dpi=110).tobytes("png")


@app.get("/api/cases/{split}/{case}/pages/{n}.png")
def page_image(split: str, case: str, n: int):
    return Response(page_png(split, case, n), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


class Box(BaseModel):
    x: float
    y: float
    w: float
    h: float


@app.get("/api/cases/{split}/{case}/pages/{n}/highlight", response_model=list[Box])
def highlight(split: str, case: str, n: int, quote: str = Query(min_length=1, max_length=500)):
    """Find the quote on the page with the same normalization the checker uses
    (whitespace, case, OCR look-alikes), and return the boxes of its words."""
    import fitz
    with fitz.open(case_dir(split, case) / "records.pdf") as doc:
        if not 1 <= n <= len(doc):
            raise HTTPException(404, "no such page")
        page = doc[n - 1]
        W, H = page.rect.width, page.rect.height
        words = page.get_text("words")
    tokens = []  # (normalized sub-token, index of the PDF word it came from)
    for wi, w in enumerate(words):
        for t in words_of(norm(w[4])):
            tokens.append((t, wi))
    want = words_of(norm(quote))
    if not want:
        return []
    seq = [t for t, _ in tokens]
    for start in range(len(seq) - len(want) + 1):
        if seq[start:start + len(want)] == want:
            hit = sorted({tokens[k][1] for k in range(start, start + len(want))})
            return [Box(x=words[i][0] / W, y=words[i][1] / H, w=(words[i][2] - words[i][0]) / W,
                        h=(words[i][3] - words[i][1]) / H) for i in hit]
    return []


# ---------------------------------------------------------------------------
# Walkthrough: the intermediate results for one case file, step by step, from
# the same functions the pipeline uses.

from chron.chronology import code_on_page, date_on_page, quote_supported  # noqa: E402
from chron.dedup import (TO_DIGIT, Params, canon, document_frequency, is_duplicate, is_stamp_word,  # noqa: E402
                         is_transmission_line, page_features_v2, words_contained)


class Count(BaseModel):
    label: str
    pages: int


class LineView(BaseModel):
    text: str
    removed: bool             # a transmission artifact the comparison ignores


class PairView(BaseModel):
    a: int
    b: int
    a_how: str
    b_how: str
    phrases_a: int
    phrases_b: int
    shared: int
    containment: float        # shared phrases / phrases of the shorter page
    numbers_only_a: list[str]
    numbers_only_b: list[str]
    duplicate: bool
    why: str


class Largest(BaseModel):
    label: str
    copies: int
    kept: int


class Walkthrough(BaseModel):
    pages: int
    originals_in_key: int
    by_source: list[Count]
    by_how: list[Count]
    clean_page: int
    clean_kept_page: int
    clean_lines: list[LineView]
    ocr_pairs: list[list[str]]       # [as read on the copy, as on the kept page]
    duplicate_pair: PairView
    hard_negative: Optional[PairView]
    groups: int
    removed: int
    kept: int
    largest: Largest
    batch_size: int
    batches: int
    min_containment: float


@lru_cache(maxsize=8)
def features(split: str, case: str):
    """The detector's own v2 page features, plus what its word rule needs."""
    _, texts, _ = load(split, case)
    f = page_features_v2(texts)
    return f, document_frequency(f), len(texts), stamp_shapes(texts)


def missing_numbers(x, y):
    """Numbers (and normalized dates) on x that the v2 rule cannot find on y."""
    from chron.dedup import _digit_form
    out = []
    for t in x.nums:
        if t in y.nums or canon(t) in y.ctoks or any(c in t for c in "~^|"):
            continue
        if not t.startswith("date:") and len(_digit_form(t)) >= 4 and _digit_form(t) in y.dstring:
            continue
        out.append(t.replace("date:", "date "))
    return sorted(out)


def pair_view(split, case, i, j, how) -> PairView:
    f, df, n, _ = features(split, case)
    a, b = f[i], f[j]
    small = a if len(a.sh) <= len(b.sh) else b
    shared = len(a.sh & b.sh)
    cont = shared / len(small.sh) if small.sh else 0.0
    only_a, only_b = missing_numbers(a, b), missing_numbers(b, a)
    dup = is_duplicate(a, b, Params(), df, n)
    words_ok = words_contained(a, b, df, n) or words_contained(b, a, df, n)
    if dup:
        why = (f"{int(cont * 100)}% of the shorter page's text is on the other page, and its dates, numbers and "
               "distinctive words (names, places) are all on the other. Same record: a duplicate.")
    elif cont < Params().min_containment:
        why = f"Only {int(cont * 100)}% of the text is shared. Different records."
    elif only_a and only_b:
        why = (f"{int(cont * 100)}% of the text is shared, so the wording alone says duplicate, but the dates and "
               "numbers differ. Different records: both are kept.")
    elif not words_ok:
        why = (f"{int(cont * 100)}% of the text is shared and the numbers match, but distinctive words (names of "
               "people or places) differ. Different records: both are kept.")
    else:
        why = (f"{int(cont * 100)}% of the text is shared, but each page has numbers or words the other lacks. "
               "Different records: both are kept.")
    return PairView(a=i + 1, b=j + 1, a_how=how[i], b_how=how[j], phrases_a=len(a.sh), phrases_b=len(b.sh),
                    shared=shared, containment=round(cont, 3), numbers_only_a=only_a[:8], numbers_only_b=only_b[:8],
                    duplicate=dup, why=why)


def raw_words(text):
    return [w.strip(".,;:()[]") for w in text.split() if w.strip(".,;:()[]")]


@app.get("/api/cases/{split}/{case}/walkthrough", response_model=Walkthrough)
def walkthrough(split: str, case: str):
    from collections import Counter
    truth, texts, res = load(split, case)
    tp = truth["pages"]
    how = [p["mechanism"] for p in tp]
    by_source = Counter(p["provider"] for p in tp)
    by_how = Counter(("cropped " + m[5:]) if m.startswith("crop+") else m for m in how)

    f, df, n, shapes = features(split, case)

    def line_removed(ln):
        # What the detector ignores: a transmission line, or a line that is only page stamps.
        return is_transmission_line(ln) or all(is_stamp_word(w, shapes) for w in ln.split())

    # A removed copy with the most ignored lines, whose kept page is a clinical record.
    def n_artifacts(i):
        return sum(1 for ln in texts[i].splitlines() if ln.strip() and line_removed(ln))
    removed = [i for i in range(len(texts)) if not res.keep[i] and tp[res.representative[i]]["doc_kind"] == "clinical"]
    ci = max(removed, key=lambda i: (n_artifacts(i), -i)) if removed else 0
    ck = res.representative[ci]
    lines = [LineView(text=ln, removed=line_removed(ln)) for ln in texts[ci].splitlines() if ln.strip()]
    # Words misread on the copy: same canonical form as a word on the kept page, different letters.
    kept_raw = {canon(w): w for w in raw_words("\n".join(content_lines(texts[ck], shapes)))}
    kept_set = {w.lower() for w in kept_raw.values()}
    pairs, seen = [], set()
    for w in raw_words("\n".join(content_lines(texts[ci], shapes))):
        if w.lower() not in kept_set and canon(w) in kept_raw and w not in seen and len(w) > 2:
            seen.add(w)
            pairs.append([w, kept_raw[canon(w)]])
    # The hardest near-miss: the two kept clinical pages sharing the most text that the detector keeps apart.
    kept_clin = [i for i in range(len(texts)) if res.keep[i] and tp[i]["doc_kind"] == "clinical" and f[i].sh][:150]
    best, hard = -1.0, None
    for x in range(len(kept_clin)):
        for y in range(x + 1, len(kept_clin)):
            i, j = kept_clin[x], kept_clin[y]
            small = f[i] if len(f[i].sh) <= len(f[j].sh) else f[j]
            c = len(f[i].sh & f[j].sh) / len(small.sh)
            if c > best and not is_duplicate(f[i], f[j], Params(), df, n):
                best, hard = c, (i, j)
    groups = res.groups
    big = max(groups, key=len) if groups else [0]
    big_kept = next((x for x in big if res.keep[x]), big[0])
    label = " · ".join(ln.strip() for ln in content_lines(texts[big_kept], shapes)[:1])
    kept_n = sum(res.keep)
    return Walkthrough(
        pages=len(texts), originals_in_key=len({p["content_id"] for p in tp}),
        by_source=[Count(label=k, pages=v) for k, v in by_source.most_common()],
        by_how=[Count(label=k, pages=v) for k, v in by_how.most_common()],
        clean_page=ci + 1, clean_kept_page=ck + 1, clean_lines=lines, ocr_pairs=pairs[:8],
        duplicate_pair=pair_view(split, case, ck, ci, how),
        hard_negative=pair_view(split, case, hard[0], hard[1], how) if hard else None,
        groups=len(groups), removed=len(texts) - kept_n, kept=kept_n,
        largest=Largest(label=label, copies=len(big) - 1, kept=big_kept + 1),
        batch_size=30, batches=-(-kept_n // 30), min_containment=Params().min_containment)


class Check(BaseModel):
    check: str
    ok: bool
    detail: str


class CheckedEntry(BaseModel):
    date: str
    kind: str
    provider: str
    summary: str
    checks: list[Check]
    kept: bool
    reason: str


class CheckerDemo(BaseModel):
    passing: Optional[CheckedEntry]
    offered: int
    kept: int
    kept_wrong: int           # kept entries that do not match the answer key (falsified ones that got through)
    falsified: list[CheckedEntry]


def entry_checks(e, texts) -> list[Check]:
    out = []
    pages = [c["page"] for c in e["citations"]]
    for c in e["citations"]:
        t = texts[c["page"] - 1] if 1 <= c["page"] <= len(texts) else ""
        out.append(Check(check=f"Quote is on page {c['page']}", ok=quote_supported(c["quote"], t), detail=c["quote"][:140]))
    out.append(Check(check="Date is written on a cited page", ok=any(date_on_page(e["date"], texts[p - 1]) for p in pages),
                     detail=e["date"]))
    for code in e.get("diagnosis_codes", []) + e.get("procedure_codes", []):
        out.append(Check(check=f"Code {code} is written on a cited page",
                         ok=any(code_on_page(code, texts[p - 1]) for p in pages), detail=code))
    return out


@app.get("/api/cases/{split}/{case}/checker-demo", response_model=CheckerDemo)
def checker_demo(split: str, case: str):
    """Feed the checker answers in which 30% of entries carry a made-up quote or a wrong date
    (no model involved), and show what it keeps and what it drops."""
    truth, texts, res = load(split, case)
    source, entries, _ = chronology_for(split, case)
    passing = None
    if entries:
        e = entries[min(2, len(entries) - 1)]
        passing = CheckedEntry(date=e["date"], kind=e["kind"], provider=e["provider"], summary=e["summary"],
                               checks=entry_checks(e, texts), kept=True, reason="")
    kept_e, report = build_chronology(texts, res.keep, oracle_extractor(truth, texts, corrupt=0.3, seed=7), workers=1)
    falsified = [CheckedEntry(date=d["entry"]["date"], kind=d["entry"]["kind"], provider=d["entry"]["provider"],
                              summary=d["entry"]["summary"], checks=entry_checks(d["entry"], texts), kept=False,
                              reason=d["reason"]) for d in report["dropped"]]
    s = score(truth, kept_e)
    return CheckerDemo(passing=passing, offered=len(kept_e) + len(falsified), kept=len(kept_e),
                       kept_wrong=s["entries"] - s["correct"], falsified=falsified[:12])


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
