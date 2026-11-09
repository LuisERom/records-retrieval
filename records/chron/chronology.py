"""Build a medical chronology from the deduplicated pages, with every entry
checked against the page it cites.

    entries, report = build_chronology(pages, extractor)

Pipeline:
1. Map: the kept pages go to the model in batches, each page marked
   "=== PAGE n ===". The model returns structured JSON (a strict Pydantic
   schema): one entry per clinical encounter, each with 1-3 citations
   (page number + a quote copied from that page).
2. Check, in code, every entry against its cited pages (no model involved):
   - each quote must appear in the cited page (whitespace, case and OCR
     look-alikes normalized; GnoRA's report/citations.py quote_supported rule
     plus the OCR canonicalization from dedup.py);
   - the cited page must be in the batch the model was shown;
   - the entry's date must be written on one of its cited pages;
   - every diagnosis or procedure code it lists must be written on one of them.
3. Repair once: if anything fails, the model is shown its own answer and the
   reasons and returns the complete object again (GnoRA's call_with_repair
   pattern). Entries that still fail are dropped and reported, never kept.
4. Reduce in code: entries for the same date, provider and kind found in
   different batches are merged (citations unioned). No model call.
"""
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .dedup import TO_DIGIT, canon

KIND = Literal["er_visit", "office_visit", "imaging", "lab", "therapy_evaluation", "therapy_visit",
               "procedure", "surgery"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(Strict):
    page: int = Field(description="The PAGE number the quote is copied from.")
    quote: str = Field(description="5 to 25 words copied exactly from that page, OCR errors included.")


class Entry(Strict):
    date: str = Field(description="Date of service, MM/DD/YYYY.")
    provider: str = Field(description="The provider organization, as written on the page.")
    kind: KIND
    summary: str = Field(description="One factual sentence: findings, diagnoses, treatment, plan.")
    diagnosis_codes: list[str] = Field(description="ICD-10 codes written on the page for this encounter; empty if none.")
    procedure_codes: list[str] = Field(description="CPT codes written on the page for this encounter; empty if none.")
    citations: list[Citation] = Field(description="1 to 3 citations supporting the entry.")


class Batch(Strict):
    entries: list[Entry]


SYSTEM = """You build a medical chronology for a personal-injury case from pages of a patient's medical records.

The user message holds pages, each starting with a line "=== PAGE n ===". The text comes from scans and faxes, so it can contain OCR errors (0 for O, 1 for l, rn for m, and similar).

List every clinical encounter these pages document: emergency visits, office visits, imaging studies, laboratory tests, therapy evaluations and re-evaluations, therapy visits, procedures such as injections, and surgeries. One entry per encounter; an encounter that spans several pages is one entry citing those pages.

Do not make entries for bills, itemized statements, claim forms, fax cover sheets, certifications of records, authorizations, or questionnaires (a questionnaire is part of the visit it is attached to).

For each entry:
- date: the date of service, MM/DD/YYYY, as written on the page.
- provider: the organization that provided the care, as written in the page header.
- kind: one of the allowed values.
- summary: one factual sentence with what the page says: findings, diagnoses, treatment and plan. Nothing that is not on the page.
- diagnosis_codes and procedure_codes: only codes written on the cited pages for this encounter.
- citations: 1 to 3, each with the page number and a quote of 5 to 25 words copied exactly from that page, including any OCR errors. A quote must support the entry, and at least one cited page must show the date of service.

If the pages document no clinical encounter, return an empty list."""


def page_block(n: int, text: str) -> str:
    return f"=== PAGE {n} ===\n{text.strip()}\n"


_WS = re.compile(r"\s+")
_EDGES = " \t\r\n.,;:!?\"'()[]{}"


def norm(text: str) -> str:
    """GnoRA report/citations.py _normalize (collapse whitespace, trim punctuation
    at the edges, lowercase) plus OCR look-alike canonicalization."""
    return canon(_WS.sub(" ", str(text or "")).strip(_EDGES))


def quote_supported(quote: str, page_text: str) -> bool:
    needle = norm(quote)
    return len(needle.split()) >= 3 and needle in norm(page_text)


def date_on_page(date: str, page_text: str) -> bool:
    """The entry's date (MM/DD/YYYY) is written on the page, in any common format
    (03/14/2025, 3/14/25, 2025-03-14, 14-Mar-2025, March 14, 2025): every date on the
    page is read by dedup.extract_dates and compared in normalized form.
    (Before 2026-11-09 only MM/DD/YYYY was recognized; on the independent generator's
    files most encounters are dated in other formats, so correct entries would have
    been dropped.)"""
    want = date.strip().translate(TO_DIGIT)
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", want):
        return False
    return want in visit_date_candidates(page_text)


# Words that say a date is something other than the visit: when the note was signed or
# dictated, when a result was reported, when the page was printed, sent or received, the
# patient's birth, or an earlier study or visit the note refers to.
_NOT_VISIT = re.compile(
    r"(sign|attest|authenticat|dictat|transcri|report|result|verif|final|amend|correct|addend|print|"
    r"generat|run\s*date|fax|sent|transmit|receiv|rec'?d|\bfiled|scann|reviewed|\bdob\b|birth|\bborn\b|"
    r"download|export|produc|releas|\bcop(y|ied)|access|retriev|request|"
    r"compar|prior|previous|\blast\b|\bnext\b|schedul|injur|accident|"
    r"onset|incident|\bdoi\b|expir|valid|effective)", re.I)


def _ocr_letters(text: str) -> str:
    """A digit OCR put inside a word read back as its letter ("D0B", "5igned"), one for one."""
    letters = {"0": "o", "1": "l", "5": "s", "8": "b"}
    return re.sub(r"(?<=[A-Za-z])[0158]|[0158](?=[A-Za-z])", lambda m: letters[m.group(0)], text)


def visit_date_candidates(page_text: str) -> set[str]:
    """Dates on the page that could be the visit's. A date is ruled out when the text
    between it and the previous date on its line names it as something else (signed,
    reported, printed, received, date of birth, a prior study, the next appointment,
    the injury), or when it sits on a fax header or receipt stamp. If that rules out
    every date, all of them stay: some providers print the visit date only beside the
    signature, and the entry must not be dropped for that."""
    from .dedup import dates_with_positions, extract_dates, is_transmission_line
    allowed, every = set(), set()
    for ln in page_text.splitlines():
        found = dates_with_positions(ln)
        every |= {d for _, _, d in found}
        if is_transmission_line(ln):
            continue
        longest = {}
        for start, end, d in found:   # one reading per spot, the longest ("09/16/2023", not "09/16/20")
            if start not in longest or end > longest[start][0]:
                longest[start] = (end, d)
        prev_end = 0
        for start in sorted(longest):
            end, d = longest[start]
            if start < prev_end:
                continue
            if not _NOT_VISIT.search(_ocr_letters(ln[prev_end:start])):
                allowed.add(d)
            prev_end = end
    if not every:
        every = extract_dates(page_text)
    return allowed or every


_SERVICE_LABEL = re.compile(
    r"(date\s*of\s*service|\bdos\b|service\s*date|visit\s*date|date\s*of\s*visit|encounter\s*(date|on)|exam\s*date|"
    r"date\s*of\s*exam|collected|collection\s*date|date\s*of\s*surgery|surgery\s*date|procedure\s*date|"
    r"date\s*of\s*procedure|admission\s*date|date\s*of\s*admission)\W{0,4}", re.I)


def service_dates(page_text: str) -> set[str]:
    """Dates the page labels as the date of service: the first date written right
    after a label such as "Date of Service", "DOS", "Visit Date", "Exam date",
    "Collected" or "Date of Surgery" (MM/DD/YYYY). A lab line reading
    "Collected: 09/16/2023  Reported: 09/17/2023" gives only 09/16/2023."""
    from .dedup import dates_with_positions
    out = set()
    # Labels are found on a copy where a digit OCR put inside a word is read back as the
    # letter it stands for ("Col1ected", "D0S", "Date 0f 5ervice"). The swap is one
    # character for one, so positions found there are positions in the page text.
    letters = {"0": "o", "1": "l", "5": "s", "8": "b"}
    labels_text = re.sub(r"(?<=[A-Za-z])[0158]|[0158](?=[A-Za-z])", lambda m: letters[m.group(0)], page_text)
    for mt in _SERVICE_LABEL.finditer(labels_text):
        tail = page_text[mt.end():mt.end() + 40].split("\n")[0]
        found = dates_with_positions(tail)
        if found:
            start = found[0][0]
            # the date that starts first, in its longest form ("09/16/2023", not "09/16/20")
            out.add(max((f for f in found if f[0] == start), key=lambda f: f[1])[2])
    return out


def entry_date_supported(date: str, cited_texts: list[str]) -> bool:
    """When a cited page labels its date of service, the entry's date must be that
    date; a page with no such label accepts any date written on it."""
    labeled = set().union(*(service_dates(t) for t in cited_texts)) if cited_texts else set()
    if labeled:
        return date in labeled
    return any(date_on_page(date, t) for t in cited_texts)


def code_on_page(code: str, page_text: str) -> bool:
    return norm(code) in norm(page_text)


def check_entries(entries: list[dict], pages: dict[int, str]) -> list[tuple[int, str]]:
    """Return (entry index, reason) for every failed check; empty means all pass."""
    bad = []
    for i, e in enumerate(entries):
        cites = e.get("citations") or []
        if not cites:
            bad.append((i, "no citations"))
            continue
        cited = []
        for c in cites:
            if c["page"] not in pages:
                bad.append((i, f"cites page {c['page']}, which was not among the pages given"))
            elif not quote_supported(c["quote"], pages[c["page"]]):
                bad.append((i, f"quote not found on page {c['page']}: {c['quote'][:80]!r}"))
            else:
                cited.append(pages[c["page"]])
        if not cited:
            continue
        if not entry_date_supported(e["date"], cited):
            bad.append((i, f"date {e['date']} is not the date of service on the cited pages"
                           if any(service_dates(t) for t in cited) else
                           f"date {e['date']} is not written on any cited page"))
        for code in e.get("diagnosis_codes", []) + e.get("procedure_codes", []):
            if not any(code_on_page(code, t) for t in cited):
                bad.append((i, f"code {code} is not written on any cited page"))
    return bad


def repair_instruction(problems: list[tuple[int, str]]) -> str:
    # GnoRA llm_client.repair_instruction: show the reason, ask for the complete object again.
    lines = "\n".join(f"- entry {i + 1}: {why}" for i, why in problems)
    return ("That answer was rejected by a check against the pages.\n"
            f"Problems:\n{lines}\n\n"
            "Return the complete JSON object for the same schema. Fix only the entries named, by copying "
            "quotes exactly from the cited page or removing what the pages do not support. Leave every "
            "other entry as it was.")


@dataclass
class BatchResult:
    pages: list[int]
    kept: list[dict] = field(default_factory=list)
    dropped: list[tuple[dict, str]] = field(default_factory=list)
    repaired: bool = False
    refused: bool = False
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "calls": 0})


def run_batch(extract, pages: dict[int, str]) -> BatchResult:
    """`extract(user_text, previous_answer=None, repair=None)` returns
    (entries as dicts or None on refusal, raw answer text, usage dict)."""
    user = "".join(page_block(n, t) for n, t in sorted(pages.items()))
    res = BatchResult(sorted(pages))
    entries, raw, usage = extract(user)
    _add(res.usage, usage)
    if entries is None:
        res.refused = True
        return res
    problems = check_entries(entries, pages)
    if problems:
        res.repaired = True
        fixed, raw2, usage = extract(user, previous_answer=raw, repair=repair_instruction(problems))
        _add(res.usage, usage)
        if fixed is not None:
            entries = fixed
        problems = check_entries(entries, pages)
    failed = {}
    for i, why in problems:
        failed.setdefault(i, why)
    for i, e in enumerate(entries):
        if i in failed:
            res.dropped.append((e, failed[i]))
        else:
            res.kept.append(e)
    return res


def _add(total, usage):
    for k in ("input_tokens", "output_tokens"):
        total[k] += int((usage or {}).get(k) or 0)
    total["calls"] += 1


def provider_key(name: str) -> frozenset:
    stop = {"pc", "pllc", "llc", "inc", "the", "of", "and", "co"}
    return frozenset(w for w in re.findall(r"[a-z0-9]+", canon(name)) if w not in stop)


def same_provider(a: str, b: str) -> bool:
    x, y = provider_key(a), provider_key(b)
    return bool(x and y) and len(x & y) / len(x | y) >= 0.5


def merge(entries: list[dict]) -> list[dict]:
    """Same date, kind and provider across batches -> one entry, citations unioned."""
    out = []
    for e in sorted(entries, key=lambda e: (e["date"][6:] + e["date"][:5], e["kind"])):
        for m in out:
            if m["date"] == e["date"] and m["kind"] == e["kind"] and same_provider(m["provider"], e["provider"]):
                seen = {(c["page"], c["quote"]) for c in m["citations"]}
                m["citations"] += [c for c in e["citations"] if (c["page"], c["quote"]) not in seen]
                m["diagnosis_codes"] = sorted(set(m["diagnosis_codes"]) | set(e["diagnosis_codes"]))
                m["procedure_codes"] = sorted(set(m["procedure_codes"]) | set(e["procedure_codes"]))
                break
        else:
            out.append({**e, "citations": list(e["citations"])})
    return out


def batches(page_numbers: list[int], size: int) -> list[list[int]]:
    return [page_numbers[i:i + size] for i in range(0, len(page_numbers), size)]


def build_chronology(texts: list[str], keep: list[bool], extract, batch_size: int = 30, workers: int = 4):
    """texts: every page of the PDF; keep: the deduplicator's decision per page.
    Page numbers given to the model and in citations are 1-based PDF page numbers."""
    from concurrent.futures import ThreadPoolExecutor
    kept = [i + 1 for i in range(len(texts)) if keep[i]]
    jobs = [{n: texts[n - 1] for n in b} for b in batches(kept, batch_size)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda pg: run_batch(extract, pg), jobs))
    entries = merge([e for r in results for e in r.kept])
    report = {
        "batches": len(results),
        "repaired_batches": sum(r.repaired for r in results),
        "refused_batches": sum(r.refused for r in results),
        "dropped": [{"entry": e, "reason": why} for r in results for e, why in r.dropped],
        "usage": {k: sum(r.usage[k] for r in results) for k in ("input_tokens", "output_tokens", "calls")},
    }
    return entries, report


# ---------------------------------------------------------------------------
# Extractors. Each returns (entries or None, raw text, usage).

MODEL = "claude-opus-5-5"
PRICE_PER_MTOK = {"input": 4.00, "output": 20.00}   # Claude Opus 5.5, Anthropic API, as of 2026-10


def load_env_local() -> None:
    """Read ANTHROPIC_API_KEY from a .env.local file (the repo root or records/) when it is
    not already set. The file is git-ignored; its contents are never printed or logged."""
    import os
    from pathlib import Path
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    here = Path(__file__).resolve().parent
    for path in (here.parent / ".env.local", here.parent.parent / ".env.local"):
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and key.strip() == "ANTHROPIC_API_KEY" and value.strip():
                    os.environ["ANTHROPIC_API_KEY"] = value.strip().strip("\"'")
                    return


def claude_extractor(model: str = MODEL, effort: str = "medium", max_tokens: int = 16000):
    import anthropic
    load_env_local()
    client = anthropic.Anthropic()

    def extract(user_text: str, previous_answer: Optional[str] = None, repair: Optional[str] = None):
        messages = [{"role": "user", "content": user_text}]
        if repair:
            messages += [{"role": "assistant", "content": previous_answer or "{}"},
                         {"role": "user", "content": repair}]
        resp = client.messages.parse(
            model=model, max_tokens=max_tokens,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages, output_format=Batch,
            output_config={"effort": effort},
        )
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return None, raw, usage
        return [e.model_dump() for e in resp.parsed_output.entries], raw, usage

    return extract


def cost_usd(usage: dict) -> float:
    return (usage["input_tokens"] * PRICE_PER_MTOK["input"] + usage["output_tokens"] * PRICE_PER_MTOK["output"]) / 1e6
