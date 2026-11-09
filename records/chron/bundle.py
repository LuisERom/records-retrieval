"""Turn a synthetic case into the messy PDF a law firm actually receives.

Each provider answers the records request with a "production": a fax cover,
a certification of records, a copy of the firm's HIPAA authorization, its own
records, and copies of records it received from other providers (the MRI
report sits in the orthopaedist's chart too). Some providers answer a second
request and send everything again. Copies arrive by fax or as rescans, with
OCR errors, fax header lines, "received" stamps and re-wrapped lines, and the
firm Bates-stamps every page.

That is where the duplication in real case files comes from. The answer key
records, for every page of the final PDF, which original page it is a copy of
(its content id), so duplicates are known exactly.

Hard negatives are kept on purpose: physical therapy daily notes, claim forms,
questionnaires, fax covers and certifications share most of their text across
pages but are NOT duplicates, because the dates and numbers differ.
"""
import random
from dataclasses import asdict, dataclass

from .synth import PROVIDERS, WIDTH, Case

# Which providers end up holding a copy of which document type.
COPIED_TO = {
    "Emergency Department Record": ["pcp", "ortho"],
    "Radiology Report": ["pcp", "ortho"],
    "Orthopaedic Consultation": ["pcp", "pt"],
    "MRI Report": ["ortho", "pcp", "pain", "asc", "pt"],
    "Orthopaedic Follow-up Note": ["pcp", "pain", "asc"],
    "Physical Therapy Initial Evaluation": ["ortho"],
    "Physical Therapy Re-evaluation": ["ortho"],
    "Procedure Note": ["ortho"],
    "Operative Report": ["ortho", "pt"],
}

OCR_SWAPS = [("rn", "m"), ("l", "1"), ("O", "0"), ("o", "0"), ("S", "5"), ("e", "c"), ("i", "l"), ("B", "8"),
             ("m", "rn"), ("1", "l"), ("0", "O"), ("5", "S"), ("cl", "d"), ("h", "b")]


@dataclass
class Settings:
    noise: tuple = (0.005, 0.02)      # per-character OCR error rate range for a copy
    p_fax: float = 0.5                # a production arrives by fax (header line + OCR noise)
    p_second: float = 0.55            # a provider answers a second request
    p_copy: float = 0.85              # a provider's chart includes a given received document
    p_crop: float = 0.0               # a copy loses its top or bottom lines (held-out mechanism)
    p_third: float = 0.25             # ...and a third one
    insurer_files: tuple = (1, 2)     # copies of the auto insurer's claim file the firm obtains
    p_insurer_copy: float = 0.9       # the claim file holds a given clinical or billing document


DEV = Settings()
TEST = Settings(noise=(0.01, 0.04), p_fax=0.6, p_second=0.6, p_crop=0.15)


@dataclass
class PageTruth:
    page: int            # 1-based page number in the final PDF
    content_id: str      # the original page this is a copy of; equal ids = duplicates
    provider: str        # whose production this page came in
    production: int
    mechanism: str       # original, fax, rescan, received, crop+...
    doc_kind: str        # clinical, billing, admin


def ocr_noise(text, rate, r):
    if rate <= 0:
        return text
    out, i = [], 0
    while i < len(text):
        if r.random() < rate:
            for a, b in r.sample(OCR_SWAPS, len(OCR_SWAPS)):
                if text.startswith(a, i):
                    out.append(b)
                    i += len(a)
                    break
            else:
                out.append(text[i])
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def rewrap(lines, width):
    out = []
    for ln in lines:
        while len(ln) > width:
            cut = ln.rfind(" ", 0, width)
            cut = cut if cut > 0 else width
            out.append(ln[:cut])
            ln = "  " + ln[cut:].lstrip()
        out.append(ln)
    return out


def fax_line(r, sender, when, page, total):
    return (f"{when} {r.randint(7, 18):02d}:{r.randint(0, 59):02d}  FROM: {sender[:28]:<28} "
            f"TO: 7185550142   P.{page:03d}/{total:03d}")


def make_bundle(case: Case, seed: int, s: Settings):
    r = random.Random(seed * 7919 + 13)
    kind_of = {name: k for k, names in PROVIDERS.items() for name in names}
    originals = {}   # content id -> lines
    docs_by_kind = {}
    auth = None
    for d in case.documents:
        for i, pg in enumerate(d.pages):
            originals[f"{d.doc_id}-p{i + 1}"] = (pg, d.kind)
        if d.title == "HIPAA Authorization":
            auth = d
        else:
            docs_by_kind.setdefault(kind_of[d.provider], []).append(d)

    def pages_of(doc):
        return [f"{doc.doc_id}-p{i + 1}" for i in range(len(doc.pages))]

    productions = []
    admin_n = 0
    for k, docs in docs_by_kind.items():
        provider = docs[0].provider
        received = [d for kk, dd in docs_by_kind.items() if kk != k for d in dd
                    if k in COPIED_TO.get(d.title, []) and r.random() < s.p_copy]
        rounds = 1 + (r.random() < s.p_second) + (r.random() < s.p_third)
        for rnd in range(rounds):
            items = []  # (content_id, mechanism)
            sent = f"{r.randint(1, 12):02d}/{r.randint(1, 28):02d}/2025"
            own = [(c, "original") for d in docs for c in pages_of(d)]
            recv = [(c, "received") for d in received for c in pages_of(d)]
            if rnd == 1:  # second request: everything again, maybe a few new pages missing
                own = [x for x in own if r.random() < 0.95]
            body = own + recv
            if auth:
                body.insert(0, (pages_of(auth)[0], "original"))
            # Admin pages unique to this production (fax cover, certification): near-identical templates.
            admin_n += 1
            cover_id, cert_id = f"admin{admin_n:03d}-cover", f"admin{admin_n:03d}-cert"
            total = len(body) + 2
            originals[cover_id] = ([f"{provider.upper()}", "FACSIMILE COVER SHEET", "-" * WIDTH, "",
                                    f"Date: {sent}", "To: Marlowe & Castell, LLP   Fax: 718-555-0142",
                                    f"From: Health Information Management, {provider}",
                                    f"Re: Records request for {case.patient['last']}, {case.patient['first']} (DOB {case.patient['dob']})",
                                    f"Number of pages including cover: {total}", "",
                                    "CONFIDENTIALITY NOTICE: This facsimile contains protected health information. If you",
                                    "received it in error, notify the sender and destroy all copies."], "admin")
            originals[cert_id] = ([f"{provider.upper()}", "CERTIFICATION OF RECORDS", "-" * WIDTH, "",
                                   "I certify that I am the custodian of records for the above facility and that the",
                                   f"attached {total - 2} pages are a true and complete copy of the records of",
                                   f"{case.patient['first']} {case.patient['last']}, DOB {case.patient['dob']}, "
                                   "kept in the regular course of business.", "",
                                   f"Request received: {sent}   Records produced: {sent}",
                                   f"Custodian: ______________________   Request no. RR-{r.randint(10000, 99999)}"], "admin")
            body = [(cover_id, "original"), (cert_id, "original")] + body
            delivery = "fax" if r.random() < s.p_fax else ("rescan" if rnd == 1 else "clean")
            productions.append((provider, delivery, sent, body))
    # The no-fault insurer's claim file: copies of most reports and bills, usually rescanned.
    insurer = "Statewide Mutual Insurance Co. (No-Fault Claim File)"
    every = [d for dd in docs_by_kind.values() for d in dd]
    for _ in range(r.randint(*s.insurer_files)):
        body = [(c, "received") for d in every if r.random() < s.p_insurer_copy for c in pages_of(d)]
        admin_n += 1
        cover_id = f"admin{admin_n:03d}-cover"
        sent = f"{r.randint(1, 12):02d}/{r.randint(1, 28):02d}/2025"
        originals[cover_id] = ([insurer.upper(), "CLAIM FILE PRODUCTION", "-" * WIDTH, "",
                                f"Date: {sent}   Claim no. NF{r.randint(10**6, 10**7 - 1)}",
                                f"Claimant: {case.patient['last']}, {case.patient['first']} (DOB {case.patient['dob']})",
                                f"Documents enclosed: {len(body)} pages of medical reports and bills.", "",
                                "Produced pursuant to subpoena duces tecum."], "admin")
        productions.append((insurer, r.choice(["rescan", "fax"]), sent, [(cover_id, "original")] + body))
    r.shuffle(productions)

    pages, truth = [], []
    for pi, (provider, delivery, sent, body) in enumerate(productions):
        rate = r.uniform(*s.noise)
        for j, (cid, mech) in enumerate(body):
            lines, dkind = originals[cid]
            lines = list(lines)
            m = mech if delivery == "clean" else (delivery if mech == "original" else mech)
            if mech == "received":
                lines = [f"RECEIVED {sent}  {provider[:40]}"] + lines
            if m in ("rescan", "received") or delivery == "rescan":
                lines = rewrap(lines, r.randint(70, WIDTH))
            if s.p_crop and m != "original" and r.random() < s.p_crop:
                k = r.randint(2, 5)
                lines = lines[k:] if r.random() < .5 else lines[:-k]
                m = "crop+" + m
            if m != "original" and m != "clean":
                lines = [ocr_noise(ln, rate, r) for ln in lines]
            if delivery == "fax":
                lines = [fax_line(r, provider, sent, j + 1, len(body))] + lines
            pages.append(lines)
            truth.append(PageTruth(len(pages), cid, provider, pi, m if m != "clean" else "original", dkind))
    return pages, truth


def render_pdf(pages, path, bates_prefix):
    import fitz
    doc = fitz.open()
    for n, lines in enumerate(pages, 1):
        pg = doc.new_page(width=612, height=792)
        y = 40
        for ln in lines[:56]:
            pg.insert_text((36, y), ln[:100], fontname="cour", fontsize=8)
            y += 12.2
        pg.insert_text((470, 772), f"{bates_prefix}-{n:06d}", fontname="cour", fontsize=8)
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def truth_dict(case: Case, truth):
    return {"case_id": case.case_id, "patient": case.patient, "accident_date": case.accident_date,
            "regions": case.regions, "events": [asdict(e) for e in case.events],
            "pages": [asdict(t) for t in truth]}
