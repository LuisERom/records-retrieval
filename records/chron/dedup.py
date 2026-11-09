"""Find duplicate pages in a records PDF without losing any unique content.

Two pages are duplicates when they carry the same record content, even if one
is a fax copy with OCR errors, a rescan with different line breaks, a copy
with a "received" stamp, or cropped at the top or bottom.

Pipeline, per page:
1. Text from the PDF text layer (PyMuPDF).
2. Drop transmission artifacts that differ between copies of the same page:
   fax header lines, "RECEIVED" stamps, Bates numbers, "Page x of y".
3. Canonicalize OCR look-alikes (0/O/o, 1/l/i, 5/S/s, rn/m, ...) so a misread
   character does not change the comparison.
4. Five-word phrases (shingles), hashed. The shingling follows GnoRA's
   documents/text_similarity.py (same phrase length and hash), applied per
   page instead of per file.
5. Candidate pairs from MinHash + LSH banding, so the work grows roughly
   linearly with page count instead of with every pair of pages.
6. A pair is a duplicate only if BOTH hold:
   - phrase containment (shared phrases / phrases of the smaller page) is
     high, which tolerates cropping; and
   - every date and number on the smaller page appears on the larger one.
   The second rule is what keeps templated records apart: two physical
   therapy notes or two claim forms share most of their wording, but not
   their dates, visit numbers or amounts.
7. Union the duplicate pairs into groups; keep the most complete copy of each
   group (the most phrases), mark the rest as duplicates.
"""
import hashlib
import re
from dataclasses import dataclass, field

import numpy as np

PHRASE_WORDS = 5
MIN_WORDS = 12

# OCR look-alikes mapped to one canonical character (applied after lowercasing).
MULTI = [("rn", "m"), ("cl", "d")]
SINGLE = str.maketrans({"0": "o", "1": "l", "i": "l", "5": "s", "8": "b", "h": "b", "e": "c"})


def canon(text: str) -> str:
    t = text.lower()
    for a, b in MULTI:
        t = t.replace(a, b)
    return t.translate(SINGLE)


# Lines that differ between copies of one page and say nothing about the record.
# Matched on the canonical form, so an OCR misread ("RECElVED", "FR0M:") still matches.
ARTIFACT_LINES = [
    re.compile(rf"\b{canon('FROM')}:.*\b{canon('TO')}:.*\b{canon('P')}\.?\s*\S+/\S+"),  # fax header
    re.compile(rf"^\s*{canon('RECEIVED')}\b"),                                   # receiving office stamp
    re.compile(r"^\s*[a-z0-9]{2,12}-[a-z0-9]{4,}\s*$"),                          # Bates number alone on a line
    re.compile(rf"^\s*{canon('Page')}\s+\S+\s+{canon('of')}\s+\S+\s*$"),         # page x of y
]
LOOKALIKE_LETTERS = set("oOlIiSsBb")


def clean_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() and not any(p.search(canon(ln)) for p in ARTIFACT_LINES)]


def words_of(text: str) -> list[str]:
    # As in GnoRA text_similarity.words_of: keep letters/digits, everything else splits.
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text).split()


def shingles(words: list[str]) -> set[int]:
    if len(words) < PHRASE_WORDS:
        return set()
    return {int.from_bytes(hashlib.blake2s(" ".join(words[i:i + PHRASE_WORDS]).encode(), digest_size=4).digest(), "big")
            for i in range(len(words) - PHRASE_WORDS + 1)}


TO_DIGIT = str.maketrans({"o": "0", "O": "0", "l": "1", "I": "1", "i": "1", "S": "5", "s": "5", "B": "8", "b": "8"})


def numeric_tokens(lines: list[str]) -> set[str]:
    """Dates, amounts, scores, codes: tokens with a digit, with OCR look-alike
    letters turned back into digits so a misread does not count as a different
    number. Single characters are ignored: a lone digit is too easily lost to
    OCR, and the dates and amounts around it already tell pages apart."""
    toks = set()
    for ln in lines:
        for w in ln.split():
            w = w.strip(".,;:()[]%$")
            # A number-like word: has a digit, and at most two letters that are not
            # OCR look-alikes ("S83.511A", "NF-1234", "11/27/2024", "1,840.00").
            # "A11ergies" is a word with a misread, not a number.
            if not any(c.isdigit() for c in w):
                continue
            if sum(c.isalpha() and c not in LOOKALIKE_LETTERS for c in w) > 2:
                continue
            w = w.translate(TO_DIGIT)
            if len(w) >= 2:
                toks.add(w)
    return toks


@dataclass
class Page:
    index: int                      # 0-based page index in the PDF
    words: int
    sh: set = field(repr=False)
    nums: set = field(repr=False)
    ctoks: set = field(repr=False)  # canonical form of every whitespace token


def page_features(texts: list[str]) -> list[Page]:
    out = []
    for i, t in enumerate(texts):
        lines = clean_lines(t)
        w = words_of(canon("\n".join(lines)))
        ctoks = {canon(x.strip(".,;:()[]%$")) for ln in lines for x in ln.split()}
        out.append(Page(i, len(w), shingles(w), numeric_tokens(lines), ctoks))
    return out


def numbers_contained(small: Page, big: Page) -> bool:
    """Every number on `small` is on `big`. A token that is really an OCR-garbled
    word ("0f" for "of", "c0111510n" for "collision") is forgiven when the same
    word, look-alikes canonicalized, is on `big`. A different date or amount is
    never forgiven: its canonical form is not a word on the other page."""
    return all(t in big.nums or canon(t) in big.ctoks for t in small.nums)


def minhash(pages: list[Page], n_perm: int = 64, seed: int = 1):
    rng = np.random.default_rng(seed)
    p = (1 << 61) - 1
    a = rng.integers(1, p, n_perm, dtype=np.uint64)
    b = rng.integers(0, p, n_perm, dtype=np.uint64)
    sig = np.full((len(pages), n_perm), np.iinfo(np.uint64).max, dtype=np.uint64)
    for i, pg in enumerate(pages):
        if pg.sh:
            x = np.fromiter(pg.sh, dtype=np.uint64)
            # (a*x + b) mod p, computed in Python ints to avoid uint64 overflow surprises.
            h = (a[None, :].astype(object) * x[:, None].astype(object) + b[None, :].astype(object)) % p
            sig[i] = np.array(h.min(axis=0), dtype=np.uint64)
    return sig


def candidate_pairs(pages: list[Page], bands: int = 24, rows: int = 3, fast: bool = False) -> set[tuple[int, int]]:
    sig = minhash_fast(pages, bands * rows) if fast else minhash(pages, bands * rows)
    pairs = set()
    for bnd in range(bands):
        buckets = {}
        for i in range(len(pages)):
            if not pages[i].sh:
                continue
            key = sig[i, bnd * rows:(bnd + 1) * rows].tobytes()
            buckets.setdefault(key, []).append(i)
        for ids in buckets.values():
            if 1 < len(ids) < 2000:
                for x in range(len(ids)):
                    for y in range(x + 1, len(ids)):
                        pairs.add((ids[x], ids[y]))
    return pairs


# ---------------------------------------------------------------------------
# v2 (2026-11-09). v1 above was built and tuned on one generator's files; on
# case files from an independently written generator it recognized only 29.5%
# of duplicates. v2 replaces the three parts that depended on known formats
# with rules about how copies behave:
#
# 1. Character fingerprints instead of five-word phrases. The canonical text
#    with every space and punctuation mark removed, cut into overlapping
#    character runs. OCR that merges or splits words ("Date ofService",
#    "Provi der"), re-wrapped lines and line-end hyphens no longer change the
#    fingerprint.
# 2. Page stamps found by behavior, not format. A number pattern (digits in a
#    fixed shape, like MR000544 or OKA_INS_00172) that appears on many pages and
#    counts up page by page through the file is a Bates or exhibit stamp:
#    every copy carries a different one, so it is left out of the comparison.
#    Zero-padded page counters (003/012) are left out too.
# 3. Transmission lines by their vocabulary, not one layout: a fax header
#    (has "FROM:"), a line that starts with a stamp word (received, rec'd,
#    scanned, filed, copy, printed, faxed), with or without a date before it,
#    and a bare page counter ("Page 3 of 12", "Pg 3/12", "P.003/012").
#
# The duplicate rule itself is unchanged: enough shared fingerprint, and the
# dates and numbers that remain must match.

V2_CHARS = 7
STAMP_WORDS = {"received", "recd", "rec'd", "scanned", "filed", "copy", "printed", "print", "faxed",
               "fax", "transmitted", "sent"}
_LEAD_TOKEN = re.compile(r"^(\d[\d/:.\-]*|am|pm|a\.m\.|p\.m\.)$", re.I)
_COUNTER_LINE = re.compile(r"^\s*(page|pg|p\.?)\s*\d{1,3}\s*(of|/)\s*\d{1,3}\s*$", re.I)
_PADDED_COUNTER = re.compile(r"^p?\.?\d{3}/\d{3}$", re.I)
_DIGITISH = re.compile(r"\d")


_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# A year after a month name: four digits, or two digits after an apostrophe ('25, ’25).
_YEAR_AFTER_MON = r"(\d{4}|['’‘`]\s?\d{2})(?!\d)"
_ORD = r"(?:st|nd|rd|th)?"
_DATE_PATTERNS = [
    (re.compile(r"(?<![\d/])(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?![\d/])"), ("y", "m", "d")),
    (re.compile(r"(?<![\d/.])(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})(?![\d/])"), ("m", "d", "y")),
    # spaced separators, four-digit year only, so a pain score ("6 / 10") cannot start one
    (re.compile(r"(?<![\d/.])(\d{1,2})\s?[/\-.]\s?(\d{1,2})\s?[/\-.]\s?(\d{4})(?![\d/])"), ("m", "d", "y")),
    # 14 Mar 2025, 14-MAR-25, 14th March '25, the 14th day of March, 2025
    (re.compile(r"(?<!\d)(\d{1,2})" + _ORD + r"(?:\s+day)?(?:\s+of)?[\s\-]*" + _MON + r"[\s\-,]*(\d{4}|\d{2}|['’‘`]\s?\d{2})(?!\d)", re.I),
     ("d", "mon", "y")),
    # March 14, 2025, Mar. 14th 2025, Mar 14, '25, Mar-14-2025, MAR/14/2025
    (re.compile(_MON + r"[\s\-/]*(\d{1,2})" + _ORD + r"[,\s\-/]*" + _YEAR_AFTER_MON, re.I), ("mon", "d", "y")),
    # 2025 MAR 14, 2025-Mar-14
    (re.compile(r"(?<![\d/])(\d{4})[\s\-/.,]*" + _MON + r"[\s\-/.]*(\d{1,2})(?!\d)", re.I), ("y", "mon", "d")),
    # compact 20250325, also as the start of a timestamp 202503251430 or 20250325143000
    (re.compile(r"(?<![\w.])((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:[01]\d|2[0-3])?(?:[0-5]\d){0,2}(?!\d)"),
     ("y", "m", "d")),
]


def extract_dates(text: str) -> set[str]:
    return {d for _, _, d in dates_with_positions(text)}


def dates_with_positions(text: str) -> list[tuple[int, int, str]]:
    """Every date written on the page, in any common format (03/14/2025, 3/14/25,
    2025-03-14, 14-Mar-2025, March 14, 2025, Mar. 14 2025, Mar 14, '25, the 14th day
    of March, 2025, 2025 MAR 14, 20250314), returned as MM/DD/YYYY.
    OCR look-alike letters inside number-like words are read as digits first.
    US month/day order is assumed for numeric dates."""
    # Only a look-alike letter touching a digit is read as a digit ("2O-Feb" -> "20-Feb"),
    # so month names keep their letters ("Feb" stays "Feb").
    fix = {"O": "0", "o": "0", "l": "1", "I": "1", "i": "1"}
    t = re.sub(r"(?<=\d)[OolIi]|[OolIi](?=\d)", lambda m: fix[m.group(0)], text)
    out = []
    for rx, order in _DATE_PATTERNS:
        for mt in rx.finditer(t):
            parts = dict(zip(order, mt.groups()))
            try:
                m = _MONTHS[parts["mon"][:3].lower()] if "mon" in parts else int(parts["m"])
                d, y = int(parts["d"]), int(parts["y"].lstrip("'’‘` "))
            except (KeyError, ValueError):
                continue
            if y < 100:
                y += 2000 if y < 50 else 1900
            if 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100:
                out.append((mt.start(), mt.end(), f"{m:02d}/{d:02d}/{y:04d}"))
    return sorted(out)


def _digits_fixed(line: str) -> str:
    """OCR look-alike letters inside number-like words turned back into digits."""
    return " ".join(w.translate(TO_DIGIT) if _DIGITISH.search(w) else w for w in line.split())


def is_transmission_line(line: str) -> bool:
    low = _digits_fixed(line).lower()
    if "from:" in low or "fr0m:" in low:
        return True
    if _COUNTER_LINE.match(low):
        return True
    # A transmission header: a clock time together with a transmission word, on a short line.
    if re.search(r"\b\d{1,2}:\d{2}\b", low) and re.search(r"\b(fax|faxed|tx|rx#|job|from|to:|page|pg|p\.)", low) \
            and len(low.split()) <= 16:
        return True
    tokens = [w for w in low.split() if w.strip("*[]()-_=#.,;:|~")]  # leading decoration ("** FAX **") ignored
    while tokens and _LEAD_TOKEN.match(tokens[0].strip(",;")):
        tokens = tokens[1:]  # a date or time stamped before the word
    if not tokens or len(low.split()) > 14:
        return False
    first = tokens[0].strip("*[(-_.,;:")
    if canon(first) not in {canon(w) for w in STAMP_WORDS}:
        return False
    # A stamp is short or carries a date or number ("SCANNED INTO CHART", "Printed: 03/14/2025 by jdoe");
    # a sentence that merely starts with such a word ("printed instructions given to patient") is not.
    return len(tokens) <= 6 or bool(_DIGITISH.search(low))


def stamp_shapes(texts: list[str]) -> set[str]:
    """Number shapes that behave like page stamps in this file: on a substantial
    share of the pages (at least 8, and 15% of them), counting up with the page
    order. A request or claim number that grows from one letter to the next is on
    a handful of pages, so it is not taken for a stamp. Values may repeat: a copy
    of a copy keeps the stamp of the copy it was made from."""
    seen = {}
    for i, t in enumerate(texts):
        for w in _digits_fixed(t).split():
            w = w.strip(".,;:()[]")
            digits = re.findall(r"\d+", w)
            if not digits or max(len(d) for d in digits) < 4:
                continue
            shape = re.sub(r"\d", "#", w.upper())
            seen.setdefault(shape, []).append((i, int(max(digits, key=len))))
    shapes = set()
    for shape, occ in seen.items():
        pages = {i for i, _ in occ}
        if len(pages) < max(8, 0.15 * len(texts)):
            continue
        occ.sort()
        vals = [v for _, v in occ]
        ups = sum(1 for a, b in zip(vals, vals[1:]) if b > a)
        if ups >= 0.8 * (len(vals) - 1):
            shapes.add(shape)
    return shapes


def char_shingles(text: str, k: int = V2_CHARS) -> set[int]:
    s = "".join(ch for ch in canon(text) if ch.isalnum())
    if len(s) < k:
        return set()
    return {int.from_bytes(hashlib.blake2s(s[i:i + k].encode(), digest_size=4).digest(), "big") & 0x7FFFFFFF
            for i in range(len(s) - k + 1)}


@dataclass
class PageV2(Page):
    dwords: set = field(default_factory=set, repr=False)   # canonical words (4+ letters) on the page
    cstring: str = field(default="", repr=False)           # canonical text, letters and digits only
    dstring: str = field(default="", repr=False)           # the text with look-alikes read as digits, no spaces


def _digit_form(s: str) -> str:
    return "".join(ch for ch in s.translate(TO_DIGIT).upper() if ch.isalnum())


def numbers_contained_v2(small: "PageV2", big: "PageV2") -> bool:
    """v1's rule, plus: a number of 4+ characters that OCR glued to its neighbour
    ("D0802/20/1963", "98.3F", "97110x1") counts if it appears in the other page's
    space-free text. Dates are compared only in normalized form, and short numbers
    (scores, counts) only as whole tokens, so a different date or score still differs."""
    for t in small.nums:
        if t in big.nums or canon(t) in big.ctoks:
            continue
        if not t.startswith("date:") and re.search(r"[~^|]", t):
            continue  # an OCR-mangled number ("0^1F"): not reliable either way
        # (Skipping two-digit numbers too was tried and rejected: look-alike pages that differ
        # only in a score or a count then merged, on both the original and the test2 files.)
        if not t.startswith("date:"):
            f = _digit_form(t)
            if len(f) >= 4 and f in big.dstring:
                continue
        return False
    return True


def words_contained(small: "PageV2", big: "PageV2", df: dict, n_pages: int) -> bool:
    """Every distinctive word on `small` is somewhere in `big`'s text, with one miss
    allowed for OCR damage. Distinctive: on at least 2 pages of the file (a one-off
    OCR garble is not) and on at most a quarter of them (template words are not).
    Searched in the space-free text, so a word OCR merged with its neighbour counts."""
    missing = 0
    for w in small.dwords:
        if 2 <= df.get(w, 0) <= 0.25 * n_pages and w not in big.cstring:
            missing += 1
            if missing > 1:
                return False
    return True


def is_stamp_word(word: str, shapes: set) -> bool:
    bare = _digits_fixed(word).strip(".,;:()[]")
    return bool((re.search(r"\d{4}", bare) and re.sub(r"\d", "#", bare.upper()) in shapes) or _PADDED_COUNTER.match(bare))


def content_lines(text: str, shapes: set) -> list[str]:
    """A page's record content as v2 compares it: transmission lines dropped, page
    stamps and counters taken out of the lines that remain."""
    kept = []
    for ln in text.splitlines():
        if not ln.strip() or is_transmission_line(ln):
            continue
        words = [w for w in _digits_fixed(ln).split() if not is_stamp_word(w, shapes)]
        if words:
            kept.append(" ".join(words))
    return kept


def page_features_v2(texts: list[str]) -> list[Page]:
    shapes = stamp_shapes(texts)
    out = []
    for i, t in enumerate(texts):
        kept = content_lines(t, shapes)
        text = "\n".join(kept)
        # Dates in any format, normalized, so "Executed on 17-Mar-2026" and "13-Oct-2025" differ.
        nums = numeric_tokens(kept) | {"date:" + d for d in extract_dates(text)}
        ctoks = {canon(x.strip(".,;:()[]%$")) for ln in kept for x in ln.split()}
        ctext = canon(text)
        dwords = set(re.findall(r"[a-z]{4,}", ctext))
        cstring = "".join(ch for ch in ctext if ch.isalnum())
        out.append(PageV2(i, len(words_of(text)), char_shingles(text), nums, ctoks, dwords, cstring, _digit_form(text)))
    return out


def document_frequency(pages: list) -> dict:
    df = {}
    for pg in pages:
        for w in getattr(pg, "dwords", ()):
            df[w] = df.get(w, 0) + 1
    return df


# ---------------------------------------------------------------------------
# v3 (2026-11-09): learn each file's own overlay lines from its near-certain copies.
#
# v2 recognizes stamps and transmission lines by vocabulary and behavior it was
# told about. On a generator it had never seen, most missed duplicates were
# copies carrying overlay lines worded in ways v2 did not know ("IMAGED BY ...",
# exhibit stickers, print footers). v3 learns those wordings from the file:
#
# 1. Near-certain copies: candidate pairs whose character fingerprints overlap
#    by at least 90% and whose distinctive words (names, places) match.
# 2. In each such pair, a line on one page that is absent from the other (most
#    of its character runs missing there, so OCR damage does not count) was
#    added by copying, or lost to a crop.
# 3. A line pattern (its letters only, digits and spaces removed) that is the
#    added line in at least 3 near-certain pairs is an overlay for this file.
#    Crops remove different record lines in different pairs, so they rarely
#    reach 3; an overlay repeats on every copy that carries it.
# 4. Guard: a line labeled as a date of service is never learned as an overlay;
#    that date is record content.
# 5. Those lines are dropped like v2's transmission lines, and matching runs again.

V3_MIN_SUPPORT = 3
V3_MIN_SHARE = 0.6  # share of its near-certain pairs in which the line is on one copy only
_V3_SERVICE_LABEL = re.compile(r"(date\s*of\s*service|\bdos\b|service\s*date|visit\s*date|date\s*of\s*visit|encounter|"
                               r"exam\s*date|date\s*of\s*exam|collected|collection|date\s*of\s*surgery|surgery\s*date|"
                               r"procedure\s*date|admission|admit)", re.I)


def skeleton(line: str) -> str:
    """A line's letters only, OCR look-alikes canonicalized: the same overlay on
    different pages, with different dates and page numbers, has one skeleton."""
    no_digits = "".join(ch for ch in line if not ch.isdigit())  # before canon, which maps 0/1/5/8 to letters
    return "".join(ch for ch in canon(no_digits) if "a" <= ch <= "z")


def _grams(s: str, k: int = 5) -> set:
    return {s[i:i + k] for i in range(len(s) - k + 1)} if len(s) >= k else {s} if s else set()


def learn_overlays(texts: list[str], min_support: int = V3_MIN_SUPPORT) -> set[str]:
    shapes = stamp_shapes(texts)
    pages = page_features_v2(texts)
    df = document_frequency(pages)
    n = len(texts)
    lines = [content_lines(t, shapes) for t in texts]
    page_grams = [_grams(pg.cstring) for pg in pages]
    support, seen = {}, {}
    for i, j in candidate_pairs(pages, bands=36, rows=2, fast=True):
        a, b = pages[i], pages[j]
        if not a.sh or not b.sh:
            continue
        small = a if len(a.sh) <= len(b.sh) else b
        if len(a.sh & b.sh) / len(small.sh) < 0.9:
            continue
        if not (words_contained(a, b, df, n) or words_contained(b, a, df, n)):
            continue
        absent = {}
        for x, y in ((i, j), (j, i)):
            absent[x] = set()
            for ln in lines[x]:
                sk = skeleton(ln)
                if len(sk) < 6:
                    continue
                g = _grams("".join(ch for ch in canon(ln) if ch.isalnum()))
                if g and len(g & page_grams[y]) / len(g) < 0.5:
                    absent[x].add((sk, bool(_V3_SERVICE_LABEL.search(ln))))
        # Copying only adds lines: in a copy, one page holds every line of the other plus
        # its overlays. If both pages have lines the other lacks (two certifications with
        # different custodians, a corrected report), they are different records: no evidence.
        if absent[i] and absent[j]:
            continue
        for x in (i, j):
            for ln in lines[x]:
                sk = skeleton(ln)
                if len(sk) >= 6:
                    seen[sk] = seen.get(sk, 0) + 1
        for sk, labeled in absent[i] | absent[j]:
            if not labeled:
                support[sk] = support.get(sk, 0) + 1
    # An overlay is missing from the other copy nearly every time it appears in a near-certain
    # pair. A template line cut off by a crop ("Signature of physician", "Vitals") is missing
    # only in the cropped pairs: measured at 2-25% on this repo's generator, against 86-100%
    # for exhibit stickers, review stamps and handwritten notes on the independent generators.
    return {sk for sk, c in support.items() if c >= min_support and c / max(seen.get(sk, 1), 1) >= V3_MIN_SHARE}


def page_features_v3(texts: list[str], overlays: set[str]) -> list[Page]:
    """v2's features with the file's learned overlay lines also dropped. A line
    matches an overlay by skeleton, exactly or by 70% of its letter runs (OCR)."""
    ov_grams = [(sk, _grams(sk, 4)) for sk in overlays]

    def is_overlay(ln):
        sk = skeleton(ln)
        if len(sk) < 6 or _V3_SERVICE_LABEL.search(ln):
            return False
        if sk in overlays:
            return True
        g = _grams(sk, 4)
        return any(len(g & og) / max(len(g | og), 1) >= 0.7 for _, og in ov_grams)

    stripped = ["\n".join(ln for ln in t.splitlines() if not (ln.strip() and is_overlay(ln))) for t in texts]
    return page_features_v2(stripped)


def minhash_fast(pages: list[Page], n_perm: int = 72, seed: int = 1):
    """MinHash with a 31-bit prime so the arithmetic stays inside uint64."""
    rng = np.random.default_rng(seed)
    p = np.uint64((1 << 31) - 1)
    a = rng.integers(1, int(p), n_perm, dtype=np.uint64)
    b = rng.integers(0, int(p), n_perm, dtype=np.uint64)
    sig = np.full((len(pages), n_perm), np.iinfo(np.uint64).max, dtype=np.uint64)
    for i, pg in enumerate(pages):
        if pg.sh:
            x = np.fromiter(pg.sh, dtype=np.uint64)
            sig[i] = ((x[:, None] * a[None, :] + b[None, :]) % p).min(axis=0)
    return sig


@dataclass
class Params:
    min_containment: float = 0.8    # shared phrases (v1) or character runs (v2) / those of the smaller page
    numbers_must_match: bool = True  # the smaller page's dates and numbers all appear on the larger
    version: str = "v2"


def is_duplicate(a: Page, b: Page, p: Params, df: dict | None = None, n_pages: int = 0) -> bool:
    if a.words < MIN_WORDS or b.words < MIN_WORDS:
        return False
    small, big = (a, b) if len(a.sh) <= len(b.sh) else (b, a)
    if not small.sh:
        return False
    if len(small.sh & big.sh) / len(small.sh) < p.min_containment:
        return False
    if not p.numbers_must_match:
        return True
    # Either direction: which page is "smaller" must not decide the answer.
    if df is None:  # v1: numbers only
        return numbers_contained(a, b) or numbers_contained(b, a)
    # v2: in one direction, both the numbers and the distinctive words of one page are on the other.
    return any(numbers_contained_v2(x, y) and words_contained(x, y, df, n_pages) for x, y in ((a, b), (b, a)))


@dataclass
class Result:
    groups: list            # lists of 0-based page indices, each a set of duplicates (size >= 2)
    keep: list              # for each page: True if kept
    representative: list    # for each page: index of the kept copy of its content


def deduplicate(texts: list[str], p: Params = Params(), use_lsh: bool = True) -> Result:
    """Anchor clustering, not transitive closure.

    Pages are visited from most to least informative. A page joins an existing
    group only if it is a duplicate of that group's anchor (its most complete
    page); otherwise it starts a new group. Joining through any member
    (union-find) lets a low-information page, such as a copy cropped so badly
    that its dates are gone, bridge two different documents into one group,
    and one of them is then thrown away. With anchors, such a page can only be
    absorbed as a copy; it can never merge two anchors.
    """
    v2 = p.version in ("v2", "v3")  # v3 is v2's matching on pages with the file's learned overlays removed
    if p.version == "v3":
        pages = page_features_v3(texts, learn_overlays(texts))
    else:
        pages = page_features_v2(texts) if v2 else page_features(texts)
    n = len(pages)
    if not use_lsh:
        pairs = {(i, j) for i in range(n) for j in range(i + 1, n)}
    elif v2:  # more bands of fewer rows: heavily OCR-damaged copies still become candidates
        pairs = candidate_pairs(pages, bands=36, rows=2, fast=True)
    else:
        pairs = candidate_pairs(pages)
    neighbors = {i: [] for i in range(n)}
    df = document_frequency(pages) if v2 else None
    for i, j in pairs:
        if is_duplicate(pages[i], pages[j], p, df, n):
            neighbors[i].append(j)
            neighbors[j].append(i)
    # Which copy is kept: the most complete page. For v3 that is judged on the page as
    # received (learned overlays included), so a page holding one line more than its
    # match, such as an addendum, is the one kept and nothing written on it is lost.
    full = page_features_v2(texts) if p.version == "v3" else pages
    info = lambda i: (len(full[i].sh) + len(full[i].nums), -i)
    rep = list(range(n))
    is_anchor = [False] * n
    for i in sorted(range(n), key=info, reverse=True):
        anchors = [j for j in neighbors[i] if is_anchor[j]]
        if anchors:
            # The anchor it overlaps most (shared phrases, then shared numbers).
            rep[i] = max(anchors, key=lambda j: (len(pages[i].sh & pages[j].sh), len(pages[i].nums & pages[j].nums), -j))
        else:
            is_anchor[i] = True
    groups = {}
    for i in range(n):
        groups.setdefault(rep[i], []).append(i)
    return Result(sorted(sorted(g) for g in groups.values() if len(g) > 1), is_anchor, rep)


def pdf_texts(path) -> list[str]:
    import fitz
    with fitz.open(path) as doc:
        return [pg.get_text() for pg in doc]
