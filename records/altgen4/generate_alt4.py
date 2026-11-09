#!/usr/bin/env python3
"""altgen4: independent synthetic personal-injury medical-records generator.

Writes records/data/alt4/alt4-1 .. alt4-10, each with records.pdf (text layer)
and truth.json. Deterministic: fixed seeds, no clock, no hash-order dependence.

Usage:  python generate_alt4.py [--out DIR] [--cases 1,2,...]
"""
import argparse
import copy
import datetime as dt
import json
import os
import random
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import banks as B  # noqa: E402
from datestyles import fmt, DOS_STYLES, TIMESTAMP_STYLES  # noqa: E402
from pdfmini import write_pdf, text_width, CHAR_W  # noqa: E402

BASE_SEED = 4417_2026
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, "..", "data", "alt4"))

PAGE_TOP = 762
PAGE_BOTTOM = 34
LEFT = 40
RIGHT = 572


# ---------------------------------------------------------------- helpers
def wd(d):
    """Move weekend dates to Monday (clinics)."""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def subseq(code):
    return code[:-1] + "D" if code.endswith("A") and code[0] == "S" else code


class Ctx:
    def __init__(self, rng):
        self.rng = rng

    def pick(self, seq):
        return seq[self.rng.randrange(len(seq))]

    def sample(self, seq, k):
        k = min(k, len(seq))
        return self.rng.sample(list(seq), k)

    def chance(self, p):
        return self.rng.random() < p

    def ri(self, a, b):
        return self.rng.randint(a, b)

    def tm(self, h0=7, h1=19):
        return (self.ri(h0, h1), self.ri(0, 59), self.ri(0, 59))


# ---------------------------------------------------------------- case setup
def make_people(c, used):
    def clin(kind):
        while True:
            n = "%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST))
            if n not in used:
                used.append(n)
                return n
    return clin


def make_providers(c, case):
    kinds = ["er", "ortho", "pt"]
    optional = ["ems", "pcp", "imaging", "pain", "asc", "chiro", "neuro", "urgent"]
    k_extra = c.ri(1, 6)
    kinds += c.sample(optional, k_extra)
    places = c.sample(B.PLACES, len(kinds) + 6)
    used_clin = []
    clin = make_people(c, used_clin)
    styles = c.sample(DOS_STYLES, len(kinds))
    layouts = ["letterhead", "ehr", "twocol", "running", "form", "report"]
    provs = []
    for i, kind in enumerate(kinds):
        p = places[i]
        name = c.pick(B.PROV_NAMES[kind]).format(P=p)
        st = c.pick(B.STATES)
        style = styles[i]
        # some providers mix a second style for signatures/timestamps
        style2 = style
        if c.chance(0.55):
            style2 = c.pick([s for s in DOS_STYLES if s != style])
        if kind == "er":
            layout = c.pick(["ehr", "report"])
        elif kind == "imaging":
            layout = "report"
        elif kind in ("pt", "chiro"):
            layout = c.pick(["form", "twocol"])
        elif kind == "ems":
            layout = c.pick(["ehr", "form"])
        else:
            layout = c.pick(["letterhead", "twocol", "running", "letterhead"])
        family = {"ehr": "C", "report": c.pick(["H", "T"]), "form": "H"}.get(layout, c.pick(["H", "T", "H"]))
        creds = B.CREDS[kind]
        clins = [(clin(kind), creds[j % len(creds)]) for j in range(c.ri(2, 3))]
        provs.append(dict(
            kind=kind, name=name, town="%s, %s" % (p, st),
            addr="%d %s, %s, %s %05d" % (c.ri(100, 9800), c.pick(B.STREETS), p, st, c.ri(10000, 99999)),
            phone="(%03d) 555-%04d" % (c.ri(201, 989), c.ri(1000, 9999)),
            fax="(%03d) 555-%04d" % (c.ri(201, 989), c.ri(1000, 9999)),
            npi="1%09d" % c.ri(100000000, 999999999),
            style=style, style2=style2,
            bill_style=c.pick(["MM/DD/YY", "MM/DD/YYYY", "M/D/YY", "YYYYMMDD", "MM-DD-YYYY"]),
            layout=layout, family=family, size=c.pick([8.6, 9.0, 9.4, 9.8]) if family != "C" else c.pick([8.2, 8.6]),
            maxlines=c.ri(24, 33),
            doslabel=c.pick({"ems": ["Incident Date:", "Date of Call:"],
                             "er": ["Arrival:", "Visit Date:", "Encounter Date:", "ADM:"],
                             "imaging": ["Exam Date:", "Date of Exam:", "Study Date:"],
                             "pt": ["Date of Service:", "Visit Date:", "DOS:", "Treatment Date:"],
                             "chiro": ["DOS:", "Visit Date:"],
                             "asc": ["Date of Surgery:", "Procedure Date:", "DOS:"]}.get(kind, ["DOS:", "Date of Service:", "Visit:", "Seen:", "Service Dt:"])),
            kvstyle=c.pick(["colon", "upper", "dots", "colon"]),
            clins=clins, mrn=c.pick(["%07d", "MR%06d", "%03d-%03d-%02d"]),
            reverse=c.chance(0.3), fax_style=c.pick(["fxA", "fxB", "fxC", "fxD"]),
            footer=c.pick(["conf", "printed", "formrev", "none", "npi"]),
        ))
        mr = provs[-1]["mrn"]
        provs[-1]["mrn"] = mr % ((c.ri(100, 999), c.ri(100, 999), c.ri(10, 99)) if mr.count("%") == 3 else c.ri(100000, 999999))
        provs[-1]["acct"] = "%s%07d" % (c.pick(["A", "V", "", "H"]), c.ri(1000000, 9999999))
    case["providers"] = provs
    case["by_kind"] = {}
    for p in provs:
        case["by_kind"].setdefault(p["kind"], p)
    a, b, c3, f = c.sample(B.CLIN_LAST, 4)
    plc = places[-6:]
    case["law"] = dict(name=c.pick(B.LAW_FMT).format(A=a, B=b, F=c.pick(B.CLIN_FIRST)),
                       addr="%d %s, Suite %d, %s, %s %05d" % (c.ri(10, 990), c.pick(B.STREETS), c.ri(100, 900), plc[0], c.pick(B.STATES), c.ri(10000, 99999)),
                       fax="(%03d) 555-%04d" % (c.ri(201, 989), c.ri(1000, 9999)),
                       atty="%s %s" % (c.pick(B.CLIN_FIRST), a), para="%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST)),
                       fileno="%s-%04d-%02d" % (c.pick(["PI", "GL", "PL"]), c.ri(1000, 9999), c.ri(10, 99)))
    case["insurer"] = dict(name=c.pick(B.INS_FMT).format(P=plc[1]), claim="%02d-%06d-%s" % (c.ri(20, 26), c.ri(100000, 999999), c.pick(["GL", "PL", "LB"])),
                           adjuster="%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST)),
                           fax="(%03d) 555-%04d" % (c.ri(201, 989), c.ri(1000, 9999)))
    case["defense"] = dict(name=c.pick(B.DEF_FMT).format(A=c3, B=f, C=c.pick(B.CLIN_LAST)),
                           prefix=c.pick(["DEF", c3[:3].upper(), "%s%s" % (c3[0], f[0])]),
                           atty="%s %s" % (c.pick(B.CLIN_FIRST), c3), defendant="%s %s Inc." % (plc[2], c.pick(["Holdings", "Operations", "Properties", "Leisure"])))


# ---------------------------------------------------------------- events
def plan_events(c, case, pt_n):
    acc = case["acc"]
    bk = case["by_kind"]
    regs = case["regions"]
    ev = []

    def add(d, kind, prov, **kw):
        e = dict(date=d, kind=kind, prov=prov, **kw)
        ev.append(e)
        return e

    first = regs[0]
    if "pcp" in bk or "chiro" in bk:
        pp = bk.get("pcp") or bk["chiro"]
        for d in sorted(set(acc - dt.timedelta(days=c.ri(45, 900)) for _ in range(c.ri(1, 3)))):
            add(wd(d), "prior_visit", pp, reason=c.pick(B.PRIOR_REASONS))
    if "ems" in bk:
        add(acc, "ems", bk["ems"])
    er = bk["er"]
    add(acc, "er_visit", er)
    for r in regs[:c.ri(1, min(3, len(regs)))]:
        R = B.REGIONS[r]
        st = R["ct"] if (R["ct"] and (r == "head" or c.chance(0.4))) else (R["xr"] or R["ct"])
        if st:
            add(acc, "imaging", er, region=r, study=st, modality="CT" if st == R["ct"] else "XR")
    if c.chance(0.6):
        add(acc, "lab", er, panel="ed")
    day = acc
    if "urgent" in bk:
        add(wd(acc + dt.timedelta(days=c.ri(1, 3))), "office_visit", bk["urgent"], seq=1)
    if "pcp" in bk:
        add(wd(acc + dt.timedelta(days=c.ri(2, 8))), "office_visit", bk["pcp"], seq=1)
    ortho = bk["ortho"]
    o_dates = []
    d = wd(acc + dt.timedelta(days=c.ri(6, 18)))
    n_ortho = c.ri(3, 5)
    for i in range(n_ortho):
        o_dates.append(d)
        d = wd(d + dt.timedelta(days=c.ri(21, 42)))
    for i, od in enumerate(o_dates):
        add(od, "office_visit", ortho, seq=i + 1, form=(i in (0, 1)))
    if c.chance(0.4) and B.REGIONS[first]["xr"]:
        add(o_dates[0], "imaging", ortho, region=first, study=B.REGIONS[first]["xr"], modality="XR")
    img = bk.get("imaging", er)
    mri_regs = [r for r in regs if B.REGIONS[r]["mri"]][:c.ri(1, 2)]
    for j, r in enumerate(mri_regs):
        add(wd(o_dates[0] + dt.timedelta(days=c.ri(4, 14) + j)), "imaging", img, region=r, study=B.REGIONS[r]["mri"],
            modality="MRI", amended=(j == 0))
    pt = bk["pt"]
    pd = wd(o_dates[0] + dt.timedelta(days=c.ri(3, 9)))
    add(pd, "pt_eval", pt, seq=0)
    d = pd
    reeval_every = c.ri(9, 12)
    vn = 1
    for i in range(pt_n):
        d = wd(d + dt.timedelta(days=c.pick([2, 2, 3, 1, 4])))
        if i > 0 and i % reeval_every == 0:
            add(d, "pt_reeval", pt, seq=vn)
        else:
            add(d, "pt_visit", pt, seq=vn)
        vn += 1
    if c.chance(0.5):
        d = wd(d + dt.timedelta(days=c.ri(2, 5)))
        add(d, "pt_reeval", pt, seq=vn, discharge=True)
    if "chiro" in bk:
        cd = wd(acc + dt.timedelta(days=c.ri(3, 10)))
        for i in range(c.ri(4, 8)):
            add(cd, "office_visit", bk["chiro"], seq=i + 1, chiro=True)
            cd = wd(cd + dt.timedelta(days=c.pick([3, 4, 7])))
    if "pain" in bk:
        inj_regs = [r for r in regs if B.REGIONS[r]["inj"]]
        if inj_regs:
            r = inj_regs[0]
            pv = wd(o_dates[1] + dt.timedelta(days=c.ri(5, 15)))
            add(pv, "office_visit", bk["pain"], seq=1)
            for k in range(c.ri(1, 2)):
                pv = wd(pv + dt.timedelta(days=c.ri(10, 35)))
                add(pv, "procedure", bk["pain"], region=r, proc=B.REGIONS[r]["inj"], seq=k + 1)
    if "neuro" in bk:
        nv = wd(o_dates[1] + dt.timedelta(days=c.ri(3, 20)))
        add(nv, "office_visit", bk["neuro"], seq=1)
        add(wd(nv + dt.timedelta(days=c.ri(7, 21))), "procedure", bk["neuro"], region=first, proc=("95886", "EMG/NCS"), emg=True)
    if "asc" in bk:
        s_regs = [r for r in regs if B.REGIONS[r]["surg"]]
        if s_regs:
            r = s_regs[0]
            sd = wd(o_dates[-1] + dt.timedelta(days=c.ri(12, 30)))
            add(wd(sd - dt.timedelta(days=c.ri(3, 7))), "lab", er, panel="preop")
            add(sd, "surgery", bk["asc"], region=r, proc=B.REGIONS[r]["surg"])
            add(wd(sd + dt.timedelta(days=c.ri(10, 16))), "office_visit", ortho, seq=n_ortho + 1, postop=True)
    order = {"prior_visit": 0, "ems": 1, "er_visit": 2, "lab": 3, "imaging": 4}
    ev.sort(key=lambda e: (e["date"], order.get(e["kind"], 9), e["prov"]["name"]))
    for i, e in enumerate(ev):
        e["event_id"] = "e%03d" % (i + 1)
        e["doc_id"] = "d%03d" % (i + 1)
    return ev


# ---------------------------------------------------------------- clinical text
def pron(case):
    if case["sex"] == "F":
        return dict(he="she", him="her", his="her", He="She")
    return dict(he="he", him="him", his="his", He="He")


def codes_for(case, e):
    regs = case["regions"]
    k = e["kind"]
    if k == "prior_visit":
        return list(e["reason"][1]), list(e["reason"][2])
    if k in ("ems", "er_visit"):
        cs = []
        for r in regs:
            cs.append(B.REGIONS[r]["acute"][0])
        cs.append(case["incident"]["ecode"])
        cpt = ["A0427", "A0425"] if k == "ems" else [("99285" if len(regs) > 2 else "99284")]
        return cs, cpt
    if k == "imaging":
        R = B.REGIONS[e["region"]]
        return [R["acute"][0] if e["modality"] != "MRI" else R["later"][0]], [e["study"][0]]
    if k == "lab":
        return (["Z01.812"] if e["panel"] == "preop" else [B.REGIONS[regs[0]]["acute"][0]]), (["85025", "80048"] if e["panel"] == "preop" else ["85025", "80048", "81001"])
    if k == "office_visit":
        if e.get("chiro"):
            return [subseq(B.REGIONS[r]["acute"][0]) for r in regs if r in ("cervical spine", "lumbar spine", "thoracic spine")] or [subseq(B.REGIONS[regs[0]]["acute"][0])], ["98941", "97140"] if e["seq"] > 1 else ["99203", "98941"]
        cs = [B.REGIONS[r]["later"][0] if e["seq"] > 1 else B.REGIONS[r]["acute"][0] for r in regs[:3]]
        if e.get("postop"):
            return cs[:1] + ["Z98.890"], ["99024"]
        cpt = "99204" if e["seq"] == 1 else c_pick_static(["99213", "99214"], e["date"].toordinal())
        return cs, [cpt]
    if k in ("pt_eval", "pt_visit", "pt_reeval"):
        cs = [subseq(B.REGIONS[r]["acute"][0]) for r in regs[:2]] + ["M62.81"]
        if k == "pt_eval":
            return cs, ["97162", "97110", "97140"]
        if k == "pt_reeval":
            return cs, ["97164", "97110"]
        opts = [["97110", "97140"], ["97110", "97112", "97140"], ["97110", "97530"], ["97110", "97140", "97530"]]
        return cs, opts[e["seq"] % 4]
    if k == "procedure":
        R = B.REGIONS[e["region"]]
        if e.get("emg"):
            return [R["later"][1]], ["95886", "95910"]
        return [R["later"][0]], [e["proc"][0]] + (["77002"] if e["proc"][0] in ("20610", "20605") else [])
    if k == "surgery":
        R = B.REGIONS[e["region"]]
        return [R["later"][0]], [e["proc"][0]]
    return [], []


SPINE_LEVELS = {"cervical spine": ["C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1"],
                "lumbar spine": ["L1-L2", "L2-L3", "L3-L4", "L4-L5", "L5-S1"],
                "thoracic spine": ["T4-T5", "T5-T6", "T6-T7", "T7-T8", "T8-T9"]}


def dstyle(prov):
    """A date-only style for incidental dates on a provider's pages."""
    for st in (prov["style2"], prov["style"]):
        if st not in TIMESTAMP_STYLES:
            return st
    return "MM/DD/YYYY"


def c_pick_static(seq, n):
    return seq[n % len(seq)]


def vitals(c):
    return "BP %d/%d  HR %d  RR %d  SpO2 %d%%  Temp %.1f F" % (c.ri(112, 152), c.ri(68, 96), c.ri(62, 108), c.ri(14, 22), c.ri(95, 100), 97.6 + c.ri(0, 14) / 10.0)


def clin_items(c, case, e):
    """Return (title, items) for an event's clinical document."""
    P = pron(case)
    pt = case["patient"]
    inc = case["incident"]
    regs = case["regions"]
    k = e["kind"]
    prov = e["prov"]
    doc, cred = prov["clins"][0]
    doc2 = prov["clins"][1][0]
    codes, cpts = e["codes"], e["cpts"]
    story = inc["story"].format(**P)
    it = []
    ds = lambda d: fmt(d, prov["style"], e["time"])  # noqa: E731
    ds2 = lambda d, t=None: fmt(d, prov["style2"], t or e["time"])  # noqa: E731
    days = (e["date"] - case["acc"]).days

    def kv(a, b):
        it.append(("kv", a, b))

    def p(t):
        it.append(("p", t))

    def h(t):
        it.append(("h", t))

    if k == "prior_visit":
        title = "Office Visit Note"
        reason = e["reason"][0]
        kv("Reason for visit", reason)
        h("Subjective")
        p("%s %d-year-old %s presents for %s. %s denies neck, back or joint complaints today and reports working full duty without restriction."
          % ("A", case["age_at"](e["date"]), "woman" if case["sex"] == "F" else "man", reason.lower(), P["He"]))
        if "low back" in reason or "elbow" in reason:
            p("Symptoms began after %s and have mostly settled with ibuprofen and stretching. No radiating pain, numbness or weakness." % c.pick(["raking leaves", "moving furniture", "a weekend tournament"]))
        kv("Vitals", vitals(c))
        h("Exam")
        p("General: well appearing, no distress. Neck supple with full range of motion. Back: no tenderness. Extremities: full strength, normal gait.")
        h("Assessment / Plan")
        for cd in codes:
            it.append(("row", "  %s  %s" % (cd, reason)))
        p(c.pick(["Continue current medications. Return in one year or as needed.", "Recheck in three months. Labs ordered.",
                  "Supportive care discussed. Return if not improved in two weeks."]))
        it.append(("sig", "%s, %s" % (doc, cred)))
        return title, it

    if k == "ems":
        title = "Patient Care Report"
        t0 = e["time"]
        tt = lambda add: "%02d:%02d" % ((t0[0] + (t0[1] + add) // 60) % 24, (t0[1] + add) % 60)  # noqa: E731
        kv("Run #", "%d-%05d" % (e["date"].year % 100, c.ri(10000, 99999)))
        kv("Unit", "Medic %d" % c.ri(2, 19))
        kv("Times", "Disp %s  Enr %s  OnSc %s  PtCt %s  Trans %s  Dest %s" % (tt(0), tt(1), tt(7), tt(9), tt(24), tt(41)))
        kv("Location type", inc["place"])
        kv("Chief complaint", "; ".join(c.sample(B.REGIONS[regs[0]]["complaint"], 1) + ["pain after %s" % inc["short"]]))
        h("Narrative")
        p("Dispatched for injured person at %s. On arrival found pt %s, alert and oriented x4, GCS 15. Pt states %s %s. %s"
          % (inc["place"], c.pick(["seated on the ground", "standing with bystanders", "supine on the floor"]), P["he"], story,
             c.pick(["Denies loss of consciousness.", "Unsure whether there was loss of consciousness.", "Bystander reports pt did not lose consciousness."])))
        p("Pt complains of %s. Pain rated %d/10. %s" % (", ".join(B.REGIONS[r]["complaint"][0] for r in regs[:2]), c.ri(6, 9),
                                                        c.pick(["Spinal motion restriction applied per protocol.", "Pt ambulated to stretcher with assistance; no SMR indicated by criteria."])))
        h("Vitals")
        for j in range(3):
            it.append(("row", "%s   %s   GCS 15   Pain %d" % (tt(9 + j * 11), vitals(c), c.ri(5, 9))))
        h("Interventions")
        p(c.pick(["Ice pack, position of comfort, cardiac monitor: sinus rhythm.", "Fentanyl 50 mcg IN for pain with improvement to 5/10. Cold pack applied."]))
        kv("Transported to", case["by_kind"]["er"]["name"])
        it.append(("sig", "%s, %s / %s, %s" % (doc, cred, doc2, prov["clins"][1][1])))
        return title, it

    if k == "er_visit":
        title = "Emergency Department Record"
        kv("Triage", "ESI %d   %s" % (c.ri(3, 4), vitals(c)))
        kv("Mode of arrival", "Ambulance" if "ems" in case["by_kind"] else c.pick(["Private vehicle", "Walk-in"]))
        kv("Chief complaint", "%s after %s" % (B.REGIONS[regs[0]]["complaint"][0], inc["short"]))
        h("History of Present Illness")
        p("%s %s %s, about %d hours prior to arrival. %s reports %s. %s"
          % (pt["first"], pt["last"], story, c.ri(1, 3), P["He"], "; ".join(c.sample(sum((B.REGIONS[r]["complaint"] for r in regs), []), 3)),
             c.pick(["No anticoagulant use.", "Took acetaminophen before arrival without relief.", "No prior injury to these areas reported."])))
        kv("Social history", c.pick(["Nonsmoker, no illicit drugs.", "Occasional alcohol, no tobacco.", "Smokes half a pack per day."]))
        kv("Last tetanus", c.pick(["Unknown", "Within 5 years", "Over 10 years, Tdap given"]))
        h("Review of Systems")
        p("Negative for fever, chest pain, shortness of breath, abdominal pain, bowel or bladder incontinence. All other systems reviewed and negative except as in HPI.")
        kv("PMH", c.pick(["Hypertension", "None", "Seasonal allergies", "Migraine (remote)"]))
        kv("Medications", c.pick(["lisinopril 10 mg daily", "none", "cetirizine as needed", "oral contraceptive"]))
        kv("Allergies", c.pick(["NKDA", "Penicillin (rash)", "Sulfa"]))
        h("Physical Examination")
        for r in regs:
            p("%s: %s" % (r.capitalize(), " ".join(c.sample(B.REGIONS[r]["exam"], 2))))
        p("Neuro: strength 5/5 except as noted, sensation intact to light touch.")
        h("ED Course")
        p("Imaging ordered as below. %s Re-examined at %02d:%02d with improvement." % (
            c.pick(["Ketorolac 30 mg IM given.", "Ibuprofen 600 mg PO and ice given.", "Morphine 4 mg IV and ondansetron 4 mg IV given."]),
            (e["time"][0] + 3) % 24, c.ri(0, 59)))
        h("Medical Decision Making")
        p("Mechanism significant for %s. Imaging without acute fracture except as reported. Differential included fracture, ligamentous injury and intracranial injury; low suspicion after evaluation." % inc["short"])
        h("Diagnoses")
        for cd in codes:
            it.append(("row", "  %s" % cd))
        kv("Disposition", "Discharged home in stable condition at %02d:%02d" % ((e["time"][0] + 4) % 24, c.ri(0, 59)))
        p("Discharge instructions: rest, ice 20 minutes several times daily, %s, follow up with orthopedics within one week, return for worsening pain, numbness, weakness or new symptoms."
          % c.pick(["naproxen 500 mg twice daily with food", "cyclobenzaprine 5 mg at bedtime as needed", "acetaminophen 1000 mg every 8 hours"]))
        it.append(("sig", "Electronically signed: %s, %s  %s" % (doc, cred, ds2(e["date"]))))
        return title, it

    if k == "imaging":
        R = B.REGIONS[e["region"]]
        title = e["study"][1]
        kv("Exam", e["study"][1])
        kv("CPT", e["study"][0])
        kv("Ordering", case["order_doc"](e))
        kv("Accession", "%s%07d" % (c.pick(["RA", "IM", "CT", "MR"]), c.ri(1000000, 9999999)))
        kv("Clinical history", "%s, %s." % (R["complaint"][0].capitalize(), inc["short"]))
        kv("Technique", {"XR": "Standard radiographic views.", "CT": "Axial images without contrast with sagittal and coronal reformats.",
                         "MRI": "Multiplanar multisequence MR imaging without contrast on a 1.5T magnet."}[e["modality"]])
        kv("Comparison", "None." if e["modality"] != "MRI" else "Radiographs from %s." % fmt(case["acc"], dstyle(prov)))
        h("FINDINGS")
        finds = R["mri_find"] if e["modality"] == "MRI" else R["xr_find"]
        for f in finds:
            p(f)
        if e["modality"] == "MRI" and e["region"] in SPINE_LEVELS:
            for lev in SPINE_LEVELS[e["region"]]:
                if not any(f.startswith(lev) for f in finds):
                    p("%s: %s" % (lev, c.pick(["No disc herniation, canal or foraminal stenosis.", "Mild facet hypertrophy without stenosis.",
                                               "Minimal disc bulge without neural impingement.", "Unremarkable."])))
            p("Paraspinal soft tissues: %s" % c.pick(["unremarkable.", "mild edema in the paraspinal musculature, likely strain."]))
        elif e["modality"] == "MRI":
            p("Bone marrow signal: %s" % c.pick(["no fracture or contusion.", "small bone contusion, otherwise normal marrow signal."]))
            p("Surrounding musculature: %s" % c.pick(["normal bulk and signal.", "mild intramuscular edema consistent with strain."]))
        h("IMPRESSION")
        imp = finds[0]
        p("1. " + imp)
        if len(finds) > 1:
            p("2. " + finds[1])
        it.append(("sig", "Interpreted by %s, %s. Signed %s" % (doc, cred, ds2(e["date"] + dt.timedelta(days=c.ri(0, 1)), c.tm()))))
        return title, it

    if k == "lab":
        title = "Laboratory Report"
        kv("Collected", ds(e["date"]))
        kv("Ordering", case["by_kind"]["er"]["clins"][0][0] if e["panel"] == "ed" else case["by_kind"]["ortho"]["clins"][0][0])
        kv("Specimen", "Blood, venous" + ("; urine, clean catch" if e["panel"] == "ed" else ""))
        it.append(("row", "%-24s %-10s %-8s %-14s" % ("TEST", "RESULT", "FLAG", "REF RANGE")))
        rows = [("WBC", "%.1f" % (5 + c.ri(0, 70) / 10), "", "4.0-11.0 K/uL"), ("Hemoglobin", "%.1f" % (12 + c.ri(0, 30) / 10), "", "12.0-16.0 g/dL"),
                ("Platelets", "%d" % c.ri(160, 390), "", "150-400 K/uL"), ("Sodium", "%d" % c.ri(135, 144), "", "135-145 mmol/L"),
                ("Potassium", "%.1f" % (3.5 + c.ri(0, 14) / 10), "", "3.5-5.1 mmol/L"), ("Glucose", "%d" % c.ri(78, 142), "", "70-99 mg/dL"),
                ("Creatinine", "%.2f" % (0.6 + c.ri(0, 50) / 100), "", "0.60-1.20 mg/dL"), ("BUN", "%d" % c.ri(8, 22), "", "7-20 mg/dL")]
        if e["panel"] == "ed":
            rows += [("UA Blood", c.pick(["Negative", "Trace"]), "", "Negative"), ("UA Protein", "Negative", "", "Negative")]
        for r in rows:
            fl = "H" if (r[0] == "Glucose" and int(r[1]) > 99) or (r[0] == "BUN" and int(r[1]) > 20) else ""
            it.append(("row", "%-24s %-10s %-8s %-14s" % (r[0], r[1], fl, r[3])))
        p("Results verified by %s, MLS(ASCP). Reported %s." % (doc2, ds2(e["date"], c.tm())))
        return title, it

    if k == "office_visit":
        if e.get("chiro"):
            title = "Chiropractic Daily Note"
            kv("Visit", "#%d" % e["seq"])
            h("S:")
            p("Pt reports %s, %d/10 today, %s since last visit." % (B.REGIONS[regs[0]]["complaint"][e["seq"] % len(B.REGIONS[regs[0]]["complaint"])],
                                                                  max(2, 8 - e["seq"] // 2 - c.ri(0, 1)), c.pick(["slightly better", "about the same", "better after last adjustment", "sore after work"])))
            h("O:")
            p("Subluxation/segmental dysfunction noted at %s with hypertonicity of the adjacent paraspinals. Palpation tenderness grade %d." %
              (", ".join(c.sample(["C2", "C5", "C6", "T3", "T5", "L3", "L4", "L5", "SI-R"], 3)), c.ri(1, 3)))
            h("A:")
            p("Condition %s. Codes: %s." % (c.pick(["improving", "unchanged", "improving slowly"]), ", ".join(codes)))
            h("P:")
            p("Diversified adjustment 3-4 regions (98941). Manual therapy %d min (97140). Return %s." % (c.pick([8, 10, 12, 15]), c.pick(["in 3 days", "next week", "Thursday"])))
            it.append(("sig", "%s, %s" % (doc, cred)))
            return title, it
        if e.get("postop"):
            title = "Postoperative Visit"
        elif e["seq"] == 1:
            title = c.pick(["New Patient Consultation", "Initial Evaluation", "New Patient Visit"])
        else:
            title = c.pick(["Follow-up Visit", "Progress Note", "Established Patient Visit"])
        kv("Provider", "%s, %s" % (doc, cred))
        kv("Referred by", c.pick(["Emergency department", "Self", "Primary care", "Attorney referral"]) if e["seq"] == 1 else "n/a")
        h("History")
        if e["seq"] == 1:
            p("%s %s is seen %s after %s. %s %s. %s" % (pt["first"], pt["last"], "%d day%s" % (days, "" if days == 1 else "s"), inc["short"], P["He"], story,
                                                         c.pick(["Seen in the emergency department the same day.", "Was evaluated in the ED and discharged."])))
        elif e.get("postop"):
            p("Seen %d days after surgery. Incision healing, pain controlled with %s. Started physical therapy." % (c.ri(10, 16), c.pick(["acetaminophen", "tramadol at night", "ice and ibuprofen"])))
        else:
            p("Interval history: %s. Attending physical therapy %s. Pain %d/10, %s." % (
                c.pick(["persistent symptoms", "partial improvement", "flare after returning to work", "no new injury"]),
                c.pick(["twice weekly", "three times weekly", "irregularly due to work"]), c.ri(3, 8),
                c.pick(["worse at night", "worse with activity", "better in the morning"])))
        p("Current complaints: %s." % "; ".join(B.REGIONS[r]["complaint"][(e["seq"] + j) % len(B.REGIONS[r]["complaint"])] for j, r in enumerate(regs[:3])))
        h("Past History")
        kv("PMH", c.pick(["Hypertension, controlled", "No chronic illness", "Seasonal allergies", "Remote appendectomy", "Migraine without aura"]))
        kv("Medications", c.pick(["naproxen 500 mg BID", "cyclobenzaprine 5 mg qhs, acetaminophen prn", "ibuprofen 600 mg TID, lisinopril 10 mg", "gabapentin 300 mg qhs"]))
        kv("Allergies", c.pick(["NKDA", "Penicillin", "Codeine (nausea)"]))
        kv("Social", c.pick(["Nonsmoker. Works as a %s." , "Former smoker, quit 2015. Employed as a %s.", "No tobacco. Occasional alcohol. Occupation: %s."]) % c.pick(["warehouse lead", "dental hygienist", "bus driver", "accountant", "line cook", "teacher", "electrician"]))
        h("Review of Systems")
        p(c.pick(["Positive for musculoskeletal pain and sleep disturbance. Negative for fever, weight loss, bowel or bladder change.",
                  "Positive for pain, stiffness and fatigue. Denies chest pain, dyspnea, saddle anesthesia or incontinence.",
                  "Musculoskeletal and neurologic positives as in HPI; remaining systems negative."]))
        kv("Vitals", vitals(c))
        h("Examination")
        for r in regs[:3]:
            p("%s: %s" % (r.capitalize(), " ".join(c.sample(B.REGIONS[r]["exam"], 2))))
        h("Assessment")
        for cd in codes:
            it.append(("row", "  %s" % cd))
        h("Plan")
        plan = [c.pick(["Continue physical therapy 2-3x/week.", "Begin physical therapy, referral given.", "Home exercise program reviewed."])]
        if prov["kind"] == "ortho" and e["seq"] == 1:
            plan.append("MRI ordered to evaluate for structural injury.")
        if prov["kind"] == "ortho" and e["seq"] >= 3 and "asc" in case["by_kind"]:
            plan.append("Discussed surgical options; patient wishes to proceed.")
        if prov["kind"] == "pain":
            plan.append("Will schedule %s." % (B.REGIONS[regs[0]]["inj"] or ("injection",))[1].lower() if B.REGIONS[regs[0]]["inj"] else "Medication management.")
        plan.append(c.pick(["Off work until next visit.", "Light duty, no lifting over 15 lb.", "Return to regular duty as tolerated."]))
        plan.append(c.pick(["Discussed natural history of soft-tissue injury and the importance of staying active within limits.",
                            "Reviewed imaging with the patient using the viewer; questions answered.",
                            "Medication risks reviewed including GI upset with NSAIDs; take with food.",
                            "Patient advised to avoid prolonged static postures and use heat before exercise."]))
        plan.append("Return in %d weeks." % c.ri(3, 6))
        for x in plan:
            p(x)
        it.append(("sig", "%s, %s   Signed %s" % (doc, cred, ds2(e["date"] + dt.timedelta(days=c.ri(0, 2)), c.tm()))))
        if e.get("form"):
            it.append(("form", e))
        return title, it

    if k in ("pt_eval", "pt_reeval"):
        title = "Physical Therapy Initial Evaluation" if k == "pt_eval" else ("Physical Therapy Discharge Summary" if e.get("discharge") else "Physical Therapy Re-Evaluation")
        meas = B.REGIONS[regs[0]]["measure"]
        kv("Referring physician", case["by_kind"]["ortho"]["clins"][0][0])
        kv("Treatment diagnosis", ", ".join(codes))
        kv("Visit", "%d" % (e["seq"] + 1))
        h("Subjective")
        if k == "pt_eval":
            p("Pt reports %s. Injury: %s on %s. Prior level of function: independent, working full time, %s." % (
                "; ".join(B.REGIONS[r]["complaint"][0] for r in regs[:2]), inc["short"], fmt(case["acc"], dstyle(prov)),
                c.pick(["walking 3 miles daily", "recreational volleyball", "gardening", "caring for two children"])))
        else:
            p("Pt has attended %d visits. Reports %d%% overall improvement. %s" % (e["seq"], c.ri(20, 70), c.pick(["Still limited with lifting.", "Sleeping better.", "Pain flares with prolonged sitting."])))
        if k == "pt_eval":
            h("Functional Limitations")
            for x in c.sample(["Unable to lift more than 10 lb from floor", "Sleep interrupted 2-3 times nightly", "Difficulty with dressing (upper body)",
                               "Sitting tolerance under 30 minutes", "Driving limited by pain when turning head", "Unable to jog or run",
                               "Stairs require handrail", "Unable to perform overhead work"], 4):
                it.append(("row", "  - " + x))
            h("Systems Review")
            p("Cardiopulmonary: unimpaired. Integumentary: intact. Neuromuscular: %s. Communication and cognition: intact." % c.pick(["unimpaired", "paresthesia reported as above"]))
            kv("Palpation", c.pick(["Hypertonicity and tenderness of the paraspinal and upper trapezius musculature.", "Tender over the involved joint line and adjacent musculature.", "Trigger points noted with referral pattern consistent with complaint."]))
        h("Objective")
        sc = c.ri(28, 56) if k == "pt_eval" else c.ri(12, 34)
        kv(B.MEASURE_NAMES[meas], "%d%s" % (sc, "" if meas == "LEFS" else "%"))
        rom = B.REGIONS[regs[0]]["rom"] or [("Balance (SLS)", 30, 8)]
        it.append(("row", "%-16s %-8s %-8s %-8s" % ("ROM", "Normal", "Right", "Left")))
        for nm, nrm, val in rom:
            v = val if k == "pt_eval" else min(nrm, val + c.ri(5, 25))
            other = nrm - c.ri(0, 5)
            r_, l_ = (other, v) if regs[0].startswith("left") else (v, other)
            it.append(("row", "%-16s %-8s %-8s %-8s" % (nm, nrm, r_, l_)))
        p("MMT: %s 4-/5, %s 4/5, remainder 5/5." % tuple(c.sample(["shoulder flexion", "hip abduction", "knee extension", "grip", "trunk extension", "ankle eversion"], 2)))
        h("Assessment")
        p("Pt presents with impairments of pain, decreased ROM and strength limiting %s. Rehab potential %s." % (
            c.pick(["work tasks", "lifting and carrying", "sleep and self-care", "stairs and community ambulation"]), c.pick(["good", "fair to good"])))
        h("Goals")
        p("STG (4 wk): pain <= 4/10, independent HEP. LTG (8 wk): %s score improved by MCID, return to prior level of function." % meas)
        h("Plan")
        p("Frequency %s for %d weeks: therapeutic exercise, manual therapy, neuromuscular re-education, modalities as indicated." % (c.pick(["2x/week", "3x/week"]), c.ri(4, 8)))
        it.append(("row", "Billed: %s" % ", ".join(cpts)))
        it.append(("sig", "%s, %s   %s" % (doc, cred, ds2(e["date"]))))
        return title, it

    if k == "pt_visit":
        title = "Daily Treatment Note"
        kv("Visit #", "%d" % (e["seq"] + 1))
        kv("Time in/out", "%02d:%02d / %02d:%02d" % (e["time"][0], e["time"][1], (e["time"][0] + 1) % 24, e["time"][1]))
        h("S")
        p("Pain %d/10 at rest, %d/10 with activity. %s" % (c.ri(2, 6), c.ri(4, 8), c.pick(["Reports doing HEP daily.", "Missed HEP over weekend.", "Sore after last session.", "Felt looser after last visit.", "Worse after a long shift."])))
        h("O")
        exs = c.sample(sum((B.REGIONS[r]["ex"] for r in regs[:2]), []), 4)
        for x in exs:
            it.append(("row", "  %-34s %dx%d" % (x, c.ri(2, 3), c.pick([10, 12, 15, 20]))))
        if "97140" in cpts:
            it.append(("row", "  Manual: %s %d min" % (c.pick(["STM paraspinals", "joint mobs grade II-III", "IASTM", "trigger point release"]), c.pick([8, 10, 12]))))
        h("A")
        p(c.pick(["Tolerated session well.", "Required cues for form.", "Progressed resistance.", "Limited by pain at end range."]))
        h("P")
        p("Continue POC. Units: %s." % ", ".join("%s x%d" % (cp, c.ri(1, 2)) for cp in cpts))
        it.append(("sig", "%s, %s" % (prov["clins"][e["seq"] % len(prov["clins"])][0], prov["clins"][e["seq"] % len(prov["clins"])][1])))
        return title, it

    if k == "procedure":
        R = B.REGIONS[e["region"]]
        if e.get("emg"):
            title = "Electrodiagnostic Study Report"
            kv("Indication", R["complaint"][-1])
            h("Nerve Conduction Studies")
            it.append(("row", "%-22s %-10s %-10s %-8s" % ("Nerve", "Lat (ms)", "Amp", "CV m/s")))
            for nv in ["R Median motor", "R Ulnar motor", "R Median sensory", "L Peroneal motor", "L Sural sensory"]:
                it.append(("row", "%-22s %-10.1f %-10.1f %-8d" % (nv, 2.5 + c.ri(0, 20) / 10, 4 + c.ri(0, 80) / 10, c.ri(45, 62))))
            h("Needle EMG")
            p(c.pick(["Mild chronic reinnervation in the C6 myotome on the right without active denervation.",
                      "Fibrillations in the left L5 myotome including tibialis anterior and paraspinals.",
                      "No electrodiagnostic evidence of radiculopathy or entrapment neuropathy."]))
            h("Impression")
            p(c.pick(["Findings consistent with a subacute radiculopathy.", "Normal study."]))
        else:
            title = "Procedure Note"
            kv("Procedure", e["proc"][1])
            kv("Pre/Post diagnosis", ", ".join(codes))
            kv("Anesthesia", "Local, 1% lidocaine")
            h("Description")
            p("Informed consent obtained after discussing risks including infection, bleeding, nerve injury and headache. Time-out performed. Patient positioned %s. Skin prepped with chlorhexidine and draped sterilely." % c.pick(["prone", "seated", "supine"]))
            p("Under %s guidance the needle was advanced to the target. %s Injectate: %s with 2 mL 1%% lidocaine." % (
                c.pick(["fluoroscopic", "ultrasound"]), c.pick(["Loss of resistance obtained.", "Contrast confirmed appropriate spread without vascular uptake."]),
                c.pick(["triamcinolone 80 mg", "dexamethasone 10 mg", "methylprednisolone 40 mg"])))
            p("Pre-procedure pain %d/10, post-procedure %d/10. No complications. Discharged ambulatory." % (c.ri(6, 9), c.ri(1, 4)))
            kv("Injection #", str(e.get("seq", 1)))
        it.append(("sig", "%s, %s   %s" % (doc, cred, ds2(e["date"]))))
        return title, it

    if k == "surgery":
        title = "Operative Report"
        kv("Surgeon", "%s, MD" % case["by_kind"]["ortho"]["clins"][0][0])
        kv("Assistant", "%s, PA-C" % case["by_kind"]["ortho"]["clins"][-1][0])
        kv("Anesthesia", "General endotracheal by %s, %s" % (prov["clins"][1][0], prov["clins"][1][1]))
        kv("Preoperative diagnosis", ", ".join(codes))
        kv("Postoperative diagnosis", "Same")
        kv("Procedure", "%s (CPT %s)" % (e["proc"][1], e["proc"][0]))
        kv("EBL", "%d mL" % c.ri(10, 150))
        h("Indications")
        p("The patient sustained %s on %s and failed more than %d weeks of conservative care including physical therapy and %s. Imaging showed %s Risks, benefits and alternatives were reviewed and consent signed." % (
            inc["short"], fmt(case["acc"], dstyle(prov)), max(6, days // 7 - 2), c.pick(["injection", "anti-inflammatories", "activity modification"]),
            B.REGIONS[e["region"]]["mri_find"][0][0].lower() + B.REGIONS[e["region"]]["mri_find"][0][1:]))
        h("Description of Procedure")
        p("The patient was brought to the operating room and placed under general anesthesia. Preoperative antibiotics were given. The operative site was prepped and draped in the usual sterile fashion and a time-out was performed confirming patient, site and procedure.")
        p(c.pick(["Standard portals were established and diagnostic inspection performed.", "A standard incision was made and dissection carried down in layers."]) +
          " The pathology was identified as described in the findings and addressed with %s." % e["proc"][1].lower())
        p(c.pick(["Hemostasis was obtained with bipolar electrocautery. Fluoroscopy confirmed position of the implants in two planes.",
                  "The repair was tested through a full range of motion and found to be secure. The joint was thoroughly irrigated.",
                  "Neural elements were inspected and found to be free of compression at the end of the procedure."]))
        p("The wound was irrigated and closed in layers. Sterile dressing applied. Sponge and needle counts correct x2. The patient was extubated and taken to PACU in stable condition.")
        h("Findings")
        for f in B.REGIONS[e["region"]]["mri_find"][:2]:
            p(f)
        kv("Implants", c.pick(["None", "Two 4.75 mm knotless anchors", "Volar locking plate with 7 screws", "PEEK cage 6 mm with anterior plate"]))
        kv("Specimens", "None")
        h("Postoperative Plan")
        p("Discharge home today when criteria are met. %s Follow up in clinic in 10 to 14 days. Begin physical therapy per protocol." % c.pick(
            ["Sling at all times except hygiene and exercises.", "Weight bearing as tolerated with crutches.", "Soft collar for comfort only.", "Splint to remain clean and dry."]))
        it.append(("sig", "%s, MD   Dictated %s  Transcribed %s" % (case["by_kind"]["ortho"]["clins"][0][0], ds2(e["date"]), ds2(e["date"] + dt.timedelta(days=1), c.tm()))))
        return title, it
    raise ValueError(k)


# ---------------------------------------------------------------- page building
def kvfmt(style, k, v):
    if style == "upper":
        return "%s: %s" % (k.upper(), v)
    if style == "dots":
        return "%s%s %s" % (k, "." * max(2, 22 - len(k)), v)
    return "%s: %s" % (k, v)


def L(t, f, s, x=LEFT, align=None, gap=0):
    return dict(t=t, f=f, s=s, x=x, align=align, gap=gap)


def RULE():
    return dict(rule=True)


def items_to_lines(prov, items, case=None):
    fam = prov["family"]
    bold = {"H": "HB", "C": "CB", "T": "TB"}[fam]
    s = prov["size"]
    width = int((RIGHT - LEFT) / (CHAR_W[fam] * s))
    out = []
    for itm in items:
        tag = itm[0]
        if tag == "h":
            out.append(L(itm[1].upper() if fam == "C" else itm[1], bold, s + 0.6, gap=3))
        elif tag == "kv":
            for j, w in enumerate(textwrap.wrap(kvfmt(prov["kvstyle"], itm[1], itm[2]), width) or [""]):
                out.append(L(w, fam, s, x=LEFT + (12 if j else 0)))
        elif tag == "p":
            for w in textwrap.wrap(itm[1], width):
                out.append(L(w, fam, s))
        elif tag == "row":
            out.append(L(itm[1], "C" if fam != "T" else "C", s - 0.4))
        elif tag == "sig":
            out.append(L("_" * 34, fam, s, gap=8))
            for w in textwrap.wrap(itm[1], width):
                out.append(L(w, fam, s))
        elif tag == "form":
            out.append(dict(pagebreak=True))
            out.extend(form_block(prov, itm[1], case))
        elif tag == "blank":
            out.append(L("", fam, s))
    return out


def form_block(prov, e, case):
    """Patient-completed pain questionnaire: identical answers on two dates."""
    fam = prov["family"]
    s = prov["size"]
    ans = case["form_answers"]
    out = [L("PATIENT PAIN QUESTIONNAIRE (completed by patient)", {"H": "HB", "C": "CB", "T": "TB"}[fam], s, gap=6),
           L("Date completed: %s" % fmt(e["date"], prov["style"], e["time"]), fam, s)]
    for q, a in ans:
        out.append(L("[%s] %s" % (a, q), fam, s - 0.3))
    return out


def ptname(case, mode):
    pt = case["patient"]
    if mode == "lf":
        return "%s, %s" % (pt["last"].upper(), pt["first"].upper())
    if mode == "lfm":
        return "%s, %s" % (pt["last"], pt["first"])
    return "%s %s" % (pt["first"], pt["last"])


def header_lines(prov, case, title, dos_txt, pg, npg, label=None):
    """Return (top lines, bottom lines) for a provider page."""
    fam = prov["family"]
    bold = {"H": "HB", "C": "CB", "T": "TB"}[fam]
    s = prov["size"]
    dob = fmt(case["dob"], prov["style"] if prov["style"] not in TIMESTAMP_STYLES else prov["style2"] if prov["style2"] not in TIMESTAMP_STYLES else "MM/DD/YYYY")
    lab = label if label is not None else prov["doslabel"]
    lay = prov["layout"]
    out = []
    bottom = []
    if lay == "letterhead":
        if pg == 1:
            out += [L(prov["name"], bold, s + 4, align="c"), L(prov["addr"], fam, s - 1, align="c"),
                    L("Tel %s   Fax %s" % (prov["phone"], prov["fax"]), fam, s - 1, align="c"), RULE(),
                    L(title, bold, s + 2, align="c", gap=2),
                    L("Patient: %s     DOB: %s     Acct: %s" % (ptname(case, "fl"), dob, prov["acct"]), fam, s, gap=2)]
            if dos_txt:
                out.append(L("%s %s" % (lab, dos_txt), fam, s))
            out.append(RULE())
        else:
            out += [L("%s   DOB %s   %s %s   (continued)" % (ptname(case, "fl"), dob, lab, dos_txt or ""), fam, s - 0.5), RULE()]
        bottom.append(L("Page %d of %d" % (pg, npg), fam, s - 1.5, align="r"))
    elif lay == "ehr":
        out += [L("%-40s %s" % (prov["name"].upper()[:40], title.upper()[:36]), "CB", s),
                L("PATIENT: %-26s MRN: %-12s DOB: %s" % (ptname(case, "lf"), prov["mrn"], dob), "C", s),
                L("%s %s   ACCT#: %s" % (lab.upper(), dos_txt or "", prov["acct"]), "C", s),
                L("=" * 86, "C", s - 1)]
        bottom.append(L("Printed by HIM-ROI  %s  Page %d of %d" % (prov["name"][:30], pg, npg), "C", s - 1.2))
    elif lay == "twocol":
        out += [L("%-44s Patient: %s" % (prov["name"][:44], ptname(case, "lfm")), bold if pg == 1 else fam, s),
                L("%-48s DOB: %s" % (prov["addr"][:48] if pg == 1 else "", dob), fam, s - 0.4),
                L("%-48s %s %s" % (("Ph %s  Fx %s" % (prov["phone"], prov["fax"])) if pg == 1 else "", lab, dos_txt or ""), fam, s - 0.4),
                RULE()]
        if pg == 1:
            out.append(L(title, bold, s + 1.5, gap=2))
        bottom.append(L("%s - Confidential  |  pg %d/%d" % (prov["name"], pg, npg), fam, s - 1.5))
    elif lay == "running":
        if pg == 1:
            out += [L(prov["name"], bold, s + 3), L(prov["addr"] + "  " + prov["phone"], fam, s - 1), RULE(),
                    L(title, bold, s + 1.5, gap=2),
                    L(kvfmt(prov["kvstyle"], "Patient", ptname(case, "fl")) + "    " + kvfmt(prov["kvstyle"], "DOB", dob), fam, s)]
            if dos_txt:
                out.append(L("%s %s" % (lab, dos_txt), fam, s))
        else:
            # continuation pages print the date without a label
            out += [L("%s | %s | %s | Page %d" % (ptname(case, "lf"), dob, dos_txt or "", pg), fam, s - 0.5), RULE()]
    elif lay == "form":
        out += [L("%s  -  %s" % (prov["name"], title), bold, s + 1.5),
                L("Patient Name: %s     DOB: %s" % (ptname(case, "fl"), dob), fam, s),
                L("%s %s     Acct: %s" % (lab, dos_txt or "", prov["acct"]), fam, s), RULE()]
        bottom.append(L("Form %s rev. %s   Page %d of %d" % (prov["formno"], prov["formrev"], pg, npg), fam, s - 1.6))
    elif lay == "report":
        out += [L(prov["name"].upper(), bold, s + 2.5, align="c"),
                L("%s  |  %s" % (prov["addr"], prov["phone"]), fam, s - 1.5, align="c"),
                L("Name: %s   MR#: %s   DOB: %s" % (ptname(case, "lf"), prov["mrn"], dob), fam, s, gap=3),
                L("%s %s   Location: %s" % (lab, dos_txt or "", prov["loc"]), fam, s), RULE()]
        if pg == 1:
            out.append(L(title, bold, s + 1, gap=2))
        bottom.append(L("Page %d" % pg, fam, s - 1.5, align="c"))
    ft = prov["footer"]
    if ft == "conf":
        bottom.insert(0, L("CONFIDENTIAL: protected health information. Redisclosure prohibited.", fam, s - 2))
    elif ft == "npi":
        bottom.insert(0, L("%s  NPI %s  Tax ID %s" % (prov["name"], prov["npi"], prov["taxid"]), fam, s - 2))
    elif ft == "formrev" and lay != "form":
        bottom.insert(0, L("%s template v%s" % (prov["name"].split()[0], prov["formrev"]), fam, s - 2))
    return out, bottom


def paginate(prov, case, title, body, dos_txt, label=None):
    n = prov["maxlines"]
    tail = []
    if any(ln.get("pagebreak") for ln in body):
        k = [i for i, ln in enumerate(body) if ln.get("pagebreak")][0]
        body, tail = body[:k], body[k + 1:]
    chunks = [body[i:i + n] for i in range(0, len(body), n)] or [[]]
    # avoid a lonely last chunk of a few lines: rebalance
    if len(chunks) > 1 and len(chunks[-1]) < 5:
        moved = chunks[-2][-6:]
        chunks[-2] = chunks[-2][:-6]
        chunks[-1] = moved + chunks[-1]
    if tail:
        chunks.append(tail)
    models = []
    for i, ch in enumerate(chunks):
        top, bottom = header_lines(prov, case, title, dos_txt, i + 1, len(chunks), label)
        models.append(dict(lines=top + ch, top=[], bottom=bottom, over=[]))
    return models


# ---------------------------------------------------------------- admin and billing
def law_letter_models(case, prov, date, ref, followup):
    law = case["law"]
    s = 10
    lines = [L(law["name"], "TB", 15, align="c"), L(law["addr"], "T", 9, align="c"),
             L("Facsimile %s" % law["fax"], "T", 9, align="c"), RULE(),
             L(fmt(date, case["law_style"]), "T", s, gap=10),
             L("VIA FACSIMILE %s AND U.S. MAIL" % prov["fax"], "TB", s, gap=8),
             L("Custodian of Records", "T", s, gap=6), L(prov["name"], "T", s), L(prov["addr"], "T", s),
             L("Re:      Our client: %s" % ptname(case, "fl"), "TB", s, gap=10),
             L("         Date of birth: %s" % fmt(case["dob"], case["law_style"]), "T", s),
             L("         Date of incident: %s" % fmt(case["acc"], case["law_style"]), "T", s),
             L("         Our reference: %s" % ref, "T", s),
             L("Dear Custodian:", "T", s, gap=10)]
    body = ("This office represents the above-named individual for injuries sustained on the date shown. Enclosed is a HIPAA-compliant "
            "authorization signed by our client. Please provide a complete and legible copy of all medical records, including office notes, "
            "diagnostic reports, therapy notes, correspondence and an itemized billing statement, for all dates of service from %s to the present, "
            "together with a signed certification of the custodian of records.") % fmt(case["acc"] - dt.timedelta(days=730), case["law_style"])
    for w in textwrap.wrap(body, 98):
        lines.append(L(w, "T", s))
    body2 = ("Please forward the records to the undersigned by facsimile or to the address above. If a fee is required, kindly send an invoice "
             "and we will remit promptly. Thank you for your courtesy and cooperation.")
    lines.append(L("", "T", s))
    for w in textwrap.wrap(body2, 98):
        lines.append(L(w, "T", s))
    lines += [L("Very truly yours,", "T", s, gap=12), L(law["para"], "T", s, gap=22), L("Paralegal to %s, Esq." % law["atty"], "T", s),
              L("Enclosure: Authorization", "T", s - 1, gap=12)]
    return [dict(lines=lines, top=[], bottom=[], over=[])]


def hipaa_models(case, date):
    law = case["law"]
    s = 9.4
    st = case["law_style"]
    lines = [L("AUTHORIZATION FOR RELEASE OF PROTECTED HEALTH INFORMATION", "HB", 11.5, align="c"),
             L("(45 CFR 164.508)", "H", 8.5, align="c"), RULE(),
             L("Patient name: %s          Date of birth: %s" % (ptname(case, "fl"), fmt(case["dob"], "MM/DD/YYYY")), "H", s, gap=6),
             L("Address: %s" % case["pt_addr"], "H", s),
             L("I authorize: ANY PHYSICIAN, HOSPITAL, CLINIC, THERAPIST, PHARMACY OR OTHER HEALTH CARE PROVIDER", "H", s, gap=6),
             L("to release to: %s, %s" % (law["name"], law["addr"]), "H", s),
             L("Information to be released:", "HB", s, gap=6)]
    for x in ["[X] Complete medical record including office and progress notes", "[X] Diagnostic imaging reports and films",
              "[X] Physical therapy and rehabilitation records", "[X] Itemized billing and payment ledgers",
              "[ ] Psychotherapy notes (separate authorization required)"]:
        lines.append(L(x, "H", s))
    txt = ("Purpose: legal representation. This authorization expires two years from the date signed. I understand that I may revoke this "
           "authorization in writing at any time except to the extent action has already been taken. Information disclosed may be subject "
           "to redisclosure by the recipient and no longer protected by federal privacy rules. Treatment, payment, enrollment or eligibility "
           "for benefits will not be conditioned on signing this form. A photocopy or facsimile of this authorization is as valid as the original.")
    lines.append(L("", "H", s))
    for w in textwrap.wrap(txt, 104):
        lines.append(L(w, "H", s - 0.4))
    lines += [L("Signature of patient: %s" % ("/s/ " + ptname(case, "fl")), "H", s, gap=16),
              L("Date signed: %s" % fmt(date, "MM/DD/YYYY"), "H", s), L("Witness: %s" % law["para"], "H", s)]
    return [dict(lines=lines, top=[], bottom=[L("Form AUTH-PI-2 (%s)" % law["name"], "H", 7)], over=[])]


def cert_models(case, prov, custodian, date, npages, first, last):
    s = 10.5
    fam = "T"
    lines = [L(prov["name"], "TB", 13, align="c"), L(prov["addr"], "T", 9, align="c"), RULE(),
             L("CERTIFICATION OF CUSTODIAN OF RECORDS", "TB", 12, align="c", gap=10),
             L("STATE OF %s     )" % prov["town"].split(", ")[1], fam, s, gap=8), L("                         ) ss.", fam, s),
             L("COUNTY OF %s )" % prov["town"].split(", ")[0].upper(), fam, s)]
    txt = ("I, %s, being duly sworn, state that I am the duly authorized custodian of records or other qualified witness for %s, "
           "and that I have authority to certify the records attached hereto. The attached %d pages are true and complete copies of all "
           "records in our possession relating to %s, date of birth %s, for the period %s through %s. The records were made at or near the "
           "time of the acts, events or conditions recorded, by or from information transmitted by a person with knowledge, and were kept in "
           "the course of regularly conducted activity as a regular practice.") % (
        custodian, prov["name"], npages, ptname(case, "fl"), fmt(case["dob"], "Month D, YYYY"),
        fmt(first, "Month D, YYYY"), fmt(last, "Month D, YYYY"))
    lines.append(L("", fam, s))
    for w in textwrap.wrap(txt, 96):
        lines.append(L(w, fam, s))
    lines += [L("Executed on %s." % fmt(date, "Dth day of Month, YYYY"), fam, s, gap=10),
              L("______________________________", fam, s, gap=18), L("%s, Custodian of Records" % custodian, fam, s),
              L("Subscribed and sworn before me on %s." % fmt(date, "Month D, YYYY"), fam, s, gap=10),
              L("Notary Public  Commission No. %d" % (abs(hash_str(custodian)) % 900000 + 100000), fam, s - 1, gap=14)]
    return [dict(lines=lines, top=[], bottom=[], over=[])]


def hash_str(s):
    h = 2166136261
    for ch in s.encode():
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


def faxcover_models(case, prov, date, to, pages, note):
    s = 11
    lines = [L("F A X", "HB", 28, gap=0), L(prov["name"], "HB", 12, gap=6), L(prov["addr"], "H", 9),
             L("Phone %s     Fax %s" % (prov["phone"], prov["fax"]), "H", 9), RULE(),
             L("Date:     %s" % fmt(date, prov["style2"], (9 + hash_str(prov["name"]) % 8, hash_str(to) % 60, 7)), "H", s, gap=10),
             L("To:       %s" % to, "H", s), L("From:     Release of Information Dept.", "H", s),
             L("Pages:    %d (including cover)" % pages, "H", s),
             L("Re:       %s, DOB %s" % (ptname(case, "fl"), fmt(case["dob"], "MM/DD/YYYY")), "H", s),
             L("Message:", "HB", s, gap=10)]
    for w in textwrap.wrap(note, 90):
        lines.append(L(w, "H", s))
    conf = ("CONFIDENTIALITY NOTICE: The documents accompanying this transmission contain confidential health information that is legally "
            "privileged. If you are not the intended recipient, you are hereby notified that any disclosure, copying or distribution is "
            "strictly prohibited. If you received this fax in error, please notify the sender immediately and destroy the documents.")
    lines.append(L("", "H", 8))
    for w in textwrap.wrap(conf, 120):
        lines.append(L(w, "H", 7.5, gap=0))
    return [dict(lines=lines, top=[], bottom=[], over=[])]


def billing_models(c, case, prov, evs, stmt_date):
    """Itemized statement pages for one provider. Returns list of models."""
    fam = prov["family"]
    s = prov["size"]
    rows = []
    for e in evs:
        for j, cp in enumerate(e["cpts"]):
            amt = case["fee"](cp)
            rows.append((e["date"], cp, B_DESC.get(cp, "Professional service"), 1 if not cp.startswith("971") else c.ri(1, 3), amt))
    per = 26
    models = []
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)]
    total = sum(r[3] * r[4] for r in rows)
    for i, ch in enumerate(chunks):
        lines = [L("%s" % prov["name"], {"H": "HB", "C": "CB", "T": "TB"}[fam], s + 3),
                 L("PATIENT ACCOUNT STATEMENT - ITEMIZED", {"H": "HB", "C": "CB", "T": "TB"}[fam], s + 1),
                 L("Statement date: %s     Account: %s     Guarantor: %s" % (fmt(stmt_date, prov["bill_style"]), prov["acct"], ptname(case, "lfm")), fam, s, gap=4),
                 L("Billing NPI %s   Tax ID %s" % (prov["npi"], prov["taxid"]), fam, s), RULE(),
                 L("%-11s %-7s %-34s %-5s %10s" % ("DOS", "CODE", "DESCRIPTION", "UNIT", "CHARGE"), "C", s - 0.4)]
        for r in ch:
            lines.append(L("%-11s %-7s %-34s %-5d %10s" % (fmt(r[0], prov["bill_style"]), r[1], r[2][:34], r[3], "%.2f" % (r[3] * r[4])), "C", s - 0.4))
        lines.append(RULE())
        if i == len(chunks) - 1:
            lines += [L("Total charges: $%s     Payments: $0.00     Adjustments: $0.00" % ("{:,.2f}".format(total)), fam, s, gap=3),
                      L("Balance due: $%s   (letter of protection on file)" % "{:,.2f}".format(total), fam, s)]
        else:
            lines.append(L("Continued on next page", fam, s))
        models.append(dict(lines=lines, top=[], bottom=[L("Statement page %d of %d" % (i + 1, len(chunks)), fam, s - 1.5, align="r")], over=[]))
    return models


def claimline_models(case, prov, e, code, amount, tag):
    """A single claim-line detail page (CMS-1500 box 24 style)."""
    s = 9.5
    lines = [L("HEALTH INSURANCE CLAIM - SERVICE LINE DETAIL", "HB", 11),
             L("Billing provider: %s   NPI %s" % (prov["name"], prov["npi"]), "H", s, gap=4),
             L("Patient: %s   DOB %s   Patient acct: %s" % (ptname(case, "lf"), fmt(case["dob"], "MM/DD/YYYY"), prov["acct"]), "H", s),
             L("Payer: %s   Claim #: %s" % (case["insurer"]["name"], case["insurer"]["claim"]), "H", s), RULE(),
             L("24A FROM      TO        B POS  D CPT/HCPCS  MOD  E DX PTR  F CHARGES  G UNITS  J RENDERING NPI", "C", 8),
             L("   %s  %s  11      %-9s  GP   A,B       %9s  1        %s" % (fmt(e["date"], "MM/DD/YY"), fmt(e["date"], "MM/DD/YY"), code, "%.2f" % amount, prov["npi"]), "C", 8),
             RULE(),
             L("21 DIAGNOSIS: A. %s   B. %s" % (e["codes"][0], e["codes"][1] if len(e["codes"]) > 1 else ""), "H", s, gap=4),
             L("Line control #: %s" % tag, "H", s),
             L("31 Signature of physician or supplier: on file", "H", s, gap=6)]
    return [dict(lines=lines, top=[], bottom=[], over=[])]


B_DESC = {"99203": "Office visit new pt, low", "99204": "Office visit new pt, moderate", "99213": "Office visit est, low",
          "99214": "Office visit est, moderate", "99284": "ED visit, moderate", "99285": "ED visit, high", "99024": "Postop visit, global",
          "99396": "Preventive visit 40-64", "A0427": "ALS1 emergency transport", "A0425": "Ground mileage",
          "85025": "CBC w/ auto diff", "80048": "Basic metabolic panel", "81001": "Urinalysis w/ micro",
          "97161": "PT eval low", "97162": "PT eval moderate", "97164": "PT re-eval", "97110": "Therapeutic exercise",
          "97140": "Manual therapy", "97112": "Neuromuscular reeducation", "97530": "Therapeutic activities",
          "98941": "CMT spinal 3-4 regions", "97012": "Mechanical traction", "95886": "Needle EMG w/ NCS",
          "95910": "Nerve conduction 7-8 studies", "77002": "Fluoroscopic guidance", "62321": "Inj epidural cerv/thor",
          "62323": "Inj epidural lumb/sacral", "20610": "Arthrocentesis/inj major joint", "20605": "Arthrocentesis/inj interm joint",
          "64405": "Nerve block greater occipital", "22551": "ACDF single interspace", "63030": "Laminotomy w/ discectomy lumbar",
          "29827": "Arthroscopic rotator cuff repair", "29881": "Knee arthroscopy meniscectomy", "25607": "ORIF distal radius",
          "27695": "Repair ankle collateral ligament"}


def insurer_cover_models(case, date, index_docs):
    ins = case["insurer"]
    lines = [L(ins["name"], "HB", 14), L("CLAIM FILE - MEDICAL DOCUMENTATION", "HB", 11, gap=4), RULE(),
             L("Claim number: %s" % ins["claim"], "H", 10, gap=4), L("Claimant: %s" % ptname(case, "fl"), "H", 10),
             L("Insured: %s" % case["defense"]["defendant"], "H", 10), L("Date of loss: %s" % fmt(case["acc"], case["ins_style"]), "H", 10),
             L("Adjuster: %s" % ins["adjuster"], "H", 10), L("Compiled: %s" % fmt(date, case["ins_style"]), "H", 10),
             L("Contents:", "HB", 10, gap=8)]
    for i, (nm, n) in enumerate(index_docs):
        lines.append(L("  %2d. %-58s %3d pp." % (i + 1, nm[:58], n), "C", 8.6))
    return [dict(lines=lines, top=[], bottom=[], over=[])]


def defense_cover_models(case, date, first_bates, last_bates):
    d = case["defense"]
    s = 10.5
    lines = [L(d["name"], "TB", 14, align="c"), L("Attorneys at Law", "TI", 10, align="c"), RULE(),
             L(fmt(date, case["def_style"]), "T", s, gap=10),
             L("%s, Esq." % case["law"]["atty"], "T", s, gap=8), L(case["law"]["name"], "T", s), L(case["law"]["addr"], "T", s),
             L("Re:  %s v. %s" % (ptname(case, "fl"), d["defendant"]), "TB", s, gap=10),
             L("     Defendant's Supplemental Production of Medical Records", "T", s),
             L("Dear Counsel:", "T", s, gap=10)]
    txt = ("Enclosed please find documents bates-labeled %s through %s, consisting of medical records and billing obtained by "
           "authorization and subpoena from the providers identified in your client's interrogatory answers. Certain pages were produced "
           "to us more than once by different sources; we have produced them as received. These documents are designated confidential "
           "under the stipulated protective order.") % (first_bates, last_bates)
    for w in textwrap.wrap(txt, 96):
        lines.append(L(w, "T", s))
    lines += [L("Sincerely,", "T", s, gap=12), L("%s" % d["atty"], "T", s, gap=20)]
    return [dict(lines=lines, top=[], bottom=[], over=[])]


# ---------------------------------------------------------------- copy transforms
def tx_line(kind, case, d, t, i, n, sender, sender_fax, to_fax):
    if kind == "fxA":
        return "%s %02d:%02d   FROM: %-26s %s   TO: %s   P.%03d/%03d" % (fmt(d, "MON DD YYYY"), t[0], t[1], sender[:26].upper(), sender_fax, to_fax, i, n)
    if kind == "fxB":
        return "%s %s   %s -> %s   pg %d of %d" % (fmt(d, "M/D/YY"), "%d:%02d%s" % ((t[0] % 12) or 12, t[1], "a" if t[0] < 12 else "p"), sender, to_fax, i, n)
    if kind == "fxC":
        return "Received via eFax %s UTC | Job %d | From %s | Page %02d/%02d" % (fmt(d, "YYYY-MM-DD HH:MM", t), 400000 + hash_str(sender) % 99999, sender_fax, i, n)
    if kind == "fxD":
        return "%s  PAGE %3d/%3d  FaxGate Server  %s" % (fmt(d, "M/D/YYYY h:MM AM", t), i, n, sender[:30])
    if kind == "secure":
        return "[SecureDocs Transmit] Sent %s | Sender ID %05d | %d of %d" % (fmt(d, "DD-MON-YYYY HH:MM", t), hash_str(sender) % 99999, i, n)
    if kind == "him":
        return "Released by %s HIM  Req# R-%05d  %s" % (sender[:34], hash_str(sender + str(d)) % 99999, fmt(d, "MM/DD/YY@HHMM", t))
    raise ValueError(kind)


def apply_tf(model, tf, c):
    k = tf[0]
    if k == "top":
        model["top"].insert(0, L(tf[1], tf[2] if len(tf) > 2 else "C", tf[3] if len(tf) > 3 else 7.4))
    elif k == "bottom":
        model["bottom"].append(L(tf[1], tf[2] if len(tf) > 2 else "HB", tf[3] if len(tf) > 3 else 8.5, align=tf[4] if len(tf) > 4 else "r"))
    elif k == "stamp_line":
        pos = min(len(model["lines"]), tf[2])
        model["lines"].insert(pos, L(tf[1], "CB", 10.5, x=LEFT + 150, gap=2))
    elif k == "stamp_margin":
        model["over"].append(("HB", 9, 22, tf[2], 90, tf[1]))
    elif k == "stamp_append":
        idxs = [i for i, ln in enumerate(model["lines"]) if not ln.get("rule") and ln["t"]]
        if idxs:
            i = idxs[tf[2] % len(idxs)]
            model["lines"][i] = dict(model["lines"][i], t=model["lines"][i]["t"] + "   " + tf[1])
    elif k == "annot":
        model["over"].append(("TI", tf[4], tf[2], tf[3], tf[5], tf[1]))
    elif k == "ocr":
        r = random.Random(tf[2])
        for coll in ("top", "lines", "bottom"):
            for i, ln in enumerate(model[coll]):
                if ln.get("rule"):
                    continue
                model[coll][i] = dict(ln, t=ocr_text(ln["t"], tf[1], r))
    elif k == "crop":
        top_k, bot_k, clip = tf[1], tf[2], tf[3]
        allines = model["top"] + model["lines"]
        allines = allines[top_k:]
        model["top"] = []
        model["lines"] = allines[:len(allines) - bot_k] if bot_k else allines
        model["bottom"] = model["bottom"][:-1] if bot_k and model["bottom"] else model["bottom"]
        if clip:
            for i, ln in enumerate(model["lines"]):
                if not ln.get("rule") and text_width(ln["t"], ln["f"], ln["s"]) + ln["x"] > 600 - clip:
                    keep = int((600 - clip - ln["x"]) / (CHAR_W[ln["f"]] * ln["s"]))
                    model["lines"][i] = dict(ln, t=ln["t"][:max(0, keep)])
        model["over"] = [o for o in model["over"] if o[2] < 600 - clip]
    elif k == "reflow":
        width = tf[1]
        src = [ln for ln in model["top"] + model["lines"] if not ln.get("rule") and ln["t"].strip()]
        texts = [ln["t"].strip() for ln in src]
        merged = []
        i = 0
        while i < len(texts):
            t = texts[i]
            if i + 1 < len(texts) and len(t) < 34 and len(texts[i + 1]) < 34:
                t = t + "    " + texts[i + 1]
                i += 1
            merged.append(t)
            i += 1
        out = []
        for t in merged:
            t = " ".join(t.split()) if not t.startswith("[") else t
            for w in textwrap.wrap(t, width) or [""]:
                out.append(L(w, "H", tf[2]))
        model["top"] = []
        model["lines"] = out
        model["bottom"] = []
        model["over"] = []
    return model


def ocr_text(t, rate, r):
    out = []
    i = 0
    while i < len(t):
        done = False
        if r.random() < rate:
            for a, b in B.OCR_CONFUSION:
                if t.startswith(a, i) and r.random() < 0.5:
                    out.append(b)
                    i += len(a)
                    done = True
                    break
            if not done and t[i] == " " and r.random() < 0.3:
                i += 1
                done = True
        if not done:
            out.append(t[i])
            i += 1
    return "".join(out)


def render(model):
    ops = []
    tops = model["top"]
    body = model["lines"]
    bottom = model["bottom"]
    need = sum(ln["s"] * 1.25 for ln in tops) + sum((6 if ln.get("rule") else ln["s"] * 1.28 + ln.get("gap", 0)) for ln in body)
    avail = (PAGE_TOP - PAGE_BOTTOM) - sum(ln["s"] * 1.3 for ln in bottom) - 6
    scale = 1.0 if need <= avail else avail / need
    y = PAGE_TOP + 8
    for ln in tops:
        y -= ln["s"] * 1.25 * scale
        ops.append(("T", ln["f"], ln["s"], 30, y, 0, ln["t"]))
    y -= 4 * scale
    for ln in body:
        if ln.get("rule"):
            ops.append(("L", LEFT, y - 2 * scale, RIGHT, y - 2 * scale, 0.6))
            y -= 6 * scale
            continue
        y -= (ln["s"] * 1.28 + ln.get("gap", 0)) * scale
        x = ln["x"]
        if ln.get("align") == "c":
            x = max(20, (612 - text_width(ln["t"], ln["f"], ln["s"])) / 2)
        elif ln.get("align") == "r":
            x = max(20, RIGHT - text_width(ln["t"], ln["f"], ln["s"]))
        if ln["t"]:
            ops.append(("T", ln["f"], ln["s"], x, y, 0, ln["t"]))
    by = 20
    for ln in reversed(bottom):
        x = ln["x"]
        if ln.get("align") == "r":
            x = max(20, RIGHT - text_width(ln["t"], ln["f"], ln["s"]))
        elif ln.get("align") == "c":
            x = max(20, (612 - text_width(ln["t"], ln["f"], ln["s"])) / 2)
        ops.append(("T", ln["f"], ln["s"], x, by, 0, ln["t"]))
        by += ln["s"] * 1.3
    for (f, s, x, yy, ang, t) in model["over"]:
        ops.append(("G", 0.35))
        ops.append(("T", f, s, x, yy, ang, t))
        ops.append(("G", 0.0))
    return ops


def model_text(model):
    parts = [ln["t"] for coll in ("top", "lines", "bottom") for ln in model[coll] if not ln.get("rule")]
    parts += [o[5] for o in model["over"]]
    return "\n".join(parts)


# ---------------------------------------------------------------- case build
def build_case(idx):
    seed = BASE_SEED + 7919 * idx
    for attempt in range(40):
        c = Ctx(random.Random(seed + attempt * 104729))
        case = try_case(c, idx, attempt)
        if case is not None:
            return case
    raise RuntimeError("could not build case %d" % idx)


def try_case(c, idx, attempt):
    case = {"case_id": "alt4-%d" % idx}
    sex = c.pick(["F", "M"])
    first = c.pick(B.FIRST_F if sex == "F" else B.FIRST_M)
    last = c.pick(B.LAST)
    acc = dt.date(2024, 1, 1) + dt.timedelta(days=c.ri(0, 600))
    dob = dt.date(acc.year - c.ri(24, 66), c.ri(1, 12), c.ri(1, 28))
    inc = B.INCIDENTS[(idx - 1) % len(B.INCIDENTS)]
    regs = list(inc["regions"])
    keep = c.ri(2, len(regs))
    regs = regs[:1] + c.sample(regs[1:], keep - 1)
    case.update(sex=sex, patient=dict(first=first, last=last), dob=dob, acc=acc, incident=inc, regions=regs)
    case["age_at"] = lambda d: d.year - dob.year - ((d.month, d.day) < (dob.month, dob.day))
    case["pt_addr"] = "%d %s, %s, %s %05d" % (c.ri(10, 9999), c.pick(B.STREETS), c.pick(B.PLACES), c.pick(B.STATES), c.ri(10000, 99999))
    make_providers(c, case)
    for p in case["providers"]:
        p["taxid"] = "%02d-%07d" % (c.ri(10, 99), c.ri(1000000, 9999999))
        p["formno"] = "%s-%02d" % (c.pick(["PT", "CL", "EV", "DN"]), c.ri(1, 40))
        p["formrev"] = "%02d/%d" % (c.ri(1, 12), c.ri(2016, 2022))
        p["loc"] = c.pick(["ED", "Main Campus", "Imaging Ctr 2", "OP Radiology", "Suite 110"])
    case["law_style"] = c.pick(["Month D, YYYY", "Weekday, Month D, YYYY", "AP Mon. D, YYYY"])
    case["ins_style"] = c.pick(["MM/DD/YYYY", "YYYY-MM-DD", "Mon D, YYYY"])
    case["def_style"] = c.pick(["Month D, YYYY", "Month Dth, YYYY"])
    fees = {}

    def fee(cp):
        if cp not in fees:
            base = {"9": 180, "A": 900, "8": 60, "7": 420, "2": 3800, "6": 1500}.get(cp[0], 250)
            fees[cp] = round(base * (0.6 + (hash_str(cp + case["case_id"]) % 1000) / 1000.0), 2)
        return fees[cp]
    case["fee"] = fee
    case["form_answers"] = [(q, c.pick(a)) for q, a in [
        ("Pain right now (0-10)", ["6", "7", "5"]), ("Worst pain in last week (0-10)", ["8", "9"]),
        ("Pain wakes me at night", ["Yes", "Sometimes"]), ("I can sit for", ["< 30 min", "30-60 min"]),
        ("Medications helping", ["Some", "No"]), ("Able to work", ["Light duty", "No", "Full duty with pain"])]]

    pt_n = c.ri(8, 20)
    # spread case sizes deliberately: roughly 230 to 410 pages
    n_center = [150, 100, 172, 115, 160, 125, 178, 106, 140, 166][(idx - 1) % 10] + c.ri(-4, 4)
    case["order_doc"] = lambda e: (case["by_kind"]["ortho"]["clins"][0][0] if e["prov"]["kind"] != "er" else case["by_kind"]["er"]["clins"][0][0])
    for tweak in range(16):
        evs = plan_events(c, case, pt_n)
        n_est = estimate_pages(case, evs) * 0.93
        if n_est < n_center - 12:
            pt_n = min(90, pt_n + max(3, int((n_center - n_est) * 0.8)))
        elif n_est > n_center + 12:
            pt_n = max(6, pt_n - max(3, int((n_est - n_center) * 0.8)))
        else:
            break
    case["events"] = evs
    for e in evs:
        e["time"] = c.tm(7, 20)
        e["codes"], e["cpts"] = codes_for(case, e)
    built = build_originals(c, case)
    if built is None:
        return None
    n_orig = len(case["content"])
    n_orig += 3  # insurer/subpoena/defense cover pages are added during assembly
    if not (85 <= n_orig <= 178):
        return None
    case["dup_target"] = 0.565 + c.ri(0, 70) / 1000.0
    total = int(round(n_orig / (1 - case["dup_target"])))
    if not (226 <= total <= 414):
        return None
    case["n_copies_target"] = total - n_orig + 3
    assemble(c, case)
    return case


def estimate_pages(case, evs):
    per = {"prior_visit": 1.2, "ems": 2, "er_visit": 3, "imaging": 1.2, "lab": 1, "office_visit": 1.8, "pt_eval": 2.4,
           "pt_visit": 1, "pt_reeval": 2, "procedure": 1.5, "surgery": 2.5}
    return sum(per[e["kind"]] for e in evs) + 5 * len(case["providers"]) + 8


def build_originals(c, case):
    """Create every original page. Fills case['content'] and case['docs']."""
    content = {}
    docs = []
    seq = [0]

    def new_cid():
        seq[0] += 1
        return "c%04d" % seq[0]

    def add_doc(models, prov_name, kind, date, dtype, event=None, extra=None):
        cids = []
        for m in models:
            cid = new_cid()
            content[cid] = dict(model=m, provider=prov_name, doc_kind=kind, event=event)
            cids.append(cid)
        d = dict(cids=cids, provider=prov_name, kind=kind, date=date, dtype=dtype, event=event)
        if extra:
            d.update(extra)
        docs.append(d)
        return d

    for e in case["events"]:
        prov = e["prov"]
        title, items = clin_items(c, case, e)
        body = items_to_lines(prov, items, case)
        dos = fmt(e["date"], prov["style"], e["time"])
        models = paginate(prov, case, title, body, dos)
        d = add_doc(models, prov["name"], "clinical", e["date"], e["kind"], event=e)
        e["cids"] = list(d["cids"])
        if e.get("amended"):
            # amended radiology report: same study, one finding sentence revised, addendum line
            models2 = copy.deepcopy(models)
            m0 = models2[0]
            for ln in m0["lines"]:
                if not ln.get("rule") and ln["t"] == title and ln["f"] in ("HB", "TB", "CB"):
                    ln["t"] = "AMENDED REPORT - " + title
                    break
            else:
                m0["lines"].insert(0, L("*** AMENDED REPORT ***", "HB", 11))
            last = models2[-1]
            # revise first impression sentence
            for ln in last["lines"] + m0["lines"]:
                if not ln.get("rule") and ln["t"].startswith("1. "):
                    ln["t"] = ln["t"].replace("1. ", "1. (Revised) ", 1)
                    break
            last["lines"].append(L("ADDENDUM: Measurement corrected after comparison with outside images.", prov["family"], prov["size"], gap=4))
            last["lines"].append(L("Findings otherwise unchanged. Addendum signed %s"
                                   % fmt(e["date"] + dt.timedelta(days=c.ri(2, 9)), prov["style2"], c.tm()), prov["family"], prov["size"]))
            d2 = add_doc(models2, prov["name"], "clinical", e["date"], "amended", event=e)
            e["cids"] += d2["cids"]
    # admin + billing per provider
    case["treat_end"] = max(e["date"] for e in case["events"])
    rel = case["treat_end"] + dt.timedelta(days=c.ri(30, 120))
    case["release_date"] = rel
    law_refs = {}
    for p in case["providers"]:
        evs = [e for e in case["events"] if e["prov"] is p]
        if not evs:
            continue
        ref1 = "%s/%s-%d" % (case["law"]["fileno"], p["name"][:3].upper(), c.ri(1, 9))
        req_date = wd(rel - dt.timedelta(days=c.ri(20, 45)))
        add_doc(law_letter_models(case, p, req_date, ref1, False), case["law"]["name"], "admin", req_date, "request", extra=dict(for_prov=p["name"]))
        rr_date = wd(req_date + dt.timedelta(days=c.ri(40, 75)))
        ref2 = "%s/%s-%d" % (case["law"]["fileno"], p["name"][:3].upper(), c.ri(10, 19))
        add_doc(law_letter_models(case, p, rr_date, ref2, True), case["law"]["name"], "admin", rr_date, "rerequest", extra=dict(for_prov=p["name"]))
        law_refs[p["name"]] = (req_date, rr_date)
        cust = "%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST))
        npg = sum(len(dd["cids"]) for dd in docs if dd["provider"] == p["name"])
        add_doc(cert_models(case, p, cust, rel, npg + 2, evs[0]["date"], evs[-1]["date"]), p["name"], "admin", rel, "cert", extra=dict(for_prov=p["name"]))
        add_doc(faxcover_models(case, p, rel, case["law"]["name"], npg + 3, "Records per your request %s. Please see certification." % ref1),
                p["name"], "admin", rel, "faxcover", extra=dict(for_prov=p["name"]))
        add_doc(billing_models(c, case, p, evs, rel - dt.timedelta(days=c.ri(1, 10))), p["name"], "billing", rel, "statement", extra=dict(for_prov=p["name"]))
    # second custodian certification (look-alike) for 1-2 providers, with re-request
    case["second_certs"] = []
    for p in c.sample([p for p in case["providers"] if p["name"] in law_refs], c.ri(1, 2)):
        evs = [e for e in case["events"] if e["prov"] is p]
        d2 = law_refs[p["name"]][1] + dt.timedelta(days=c.ri(8, 25))
        cust = "%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST))
        npg = sum(len(dd["cids"]) for dd in docs if dd["provider"] == p["name"] and dd["kind"] == "clinical")
        dd = add_doc(cert_models(case, p, cust, d2, npg, evs[0]["date"], evs[-1]["date"]), p["name"], "admin", d2, "cert2", extra=dict(for_prov=p["name"]))
        case["second_certs"].append(dd)
    # HIPAA authorization signed on two dates (same form)
    a1 = case["acc"] + dt.timedelta(days=c.ri(5, 20))
    add_doc(hipaa_models(case, a1), case["law"]["name"], "admin", a1, "hipaa")
    a2 = a1 + dt.timedelta(days=c.ri(380, 420))
    add_doc(hipaa_models(case, a2), case["law"]["name"], "admin", a2, "hipaa2")
    # claim-line look-alikes: same DOS, differing only in code (and one only in amount)
    ptp = case["by_kind"]["pt"]
    pv = [e for e in case["events"] if e["prov"] is ptp and e["kind"] == "pt_visit"]
    e = pv[len(pv) // 2]
    amt = case["fee"]("97110")
    tag = "LC%07d" % c.ri(1000000, 9999999)
    add_doc(claimline_models(case, ptp, e, "97110", amt, tag), ptp["name"], "billing", e["date"], "claimline", extra=dict(for_prov=ptp["name"]))
    add_doc(claimline_models(case, ptp, e, "97112", amt, tag), ptp["name"], "billing", e["date"], "claimline", extra=dict(for_prov=ptp["name"]))
    add_doc(claimline_models(case, ptp, e, "97110", round(amt * 1.5, 2), tag), ptp["name"], "billing", e["date"], "claimline", extra=dict(for_prov=ptp["name"]))
    case["content"] = content
    case["docs"] = docs
    # all originals must have distinct text
    seen = {}
    for cid, v in content.items():
        t = model_text(v["model"])
        if t in seen:
            raise RuntimeError("duplicate text %s %s in %s" % (seen[t], cid, case["case_id"]))
        seen[t] = cid
        if not t.strip():
            raise RuntimeError("empty page")
    return True


# ---------------------------------------------------------------- productions
def assemble(c, case):
    content = case["content"]
    docs = case["docs"]
    provs = case["providers"]
    seq = []           # final page instances
    emitted = {}       # cid -> list of seq indexes
    prods = []

    def doc_of(dtype=None, prov=None, kind=None):
        return [d for d in docs if (dtype is None or d["dtype"] in dtype) and (prov is None or d.get("for_prov", d["provider"]) == prov)
                and (kind is None or d["kind"] == kind)]

    clinical_docs = [d for d in docs if d["kind"] == "clinical"]
    # which providers release in production 1 vs arrive on re-request
    order_kinds = ["ems", "er", "urgent", "pcp", "imaging", "ortho", "neuro", "pain", "chiro", "asc", "pt"]
    ordered = sorted(provs, key=lambda p: order_kinds.index(p["kind"]))
    late = c.sample([p for p in ordered if p["kind"] not in ("er",)], c.ri(1, max(1, len(ordered) // 3)))
    late_names = [p["name"] for p in late]
    early = [p for p in ordered if p["name"] not in late_names]

    middle = ["insurer", "portal", "subpoena"]
    c.rng.shuffle(middle)
    middle = middle[:c.ri(2, 3)]
    plan = ["release", "re_request"] + middle + ["defense"]
    target = case["n_copies_target"]
    weights = {"release": 0.06, "re_request": 0.24, "insurer": 0.24, "portal": 0.12, "subpoena": 0.1, "defense": 0.32}
    wsum = sum(weights[k] for k in plan)
    quota = {k: int(target * weights[k] / wsum) for k in plan}
    quota["defense"] += target - sum(quota.values())
    copies_made = [0]

    def emit(cid, prod, mech, model, entry_tfs=None):
        seq.append(dict(cid=cid, prod=prod, mech=mech, model=model))
        emitted.setdefault(cid, []).append(len(seq) - 1)

    def emit_original(cid, prod):
        emit(cid, prod, "original", copy.deepcopy(content[cid]["model"]))

    pending = []  # entries for current production: dict(cid, src, mech, tfs)

    def queue(cid, mech_tokens, tfs, src=None):
        pending.append(dict(cid=cid, src=src, mech=mech_tokens, tfs=list(tfs)))

    def flush(prod, numbering):
        """numbering: list of (kind, args) applied with page index across the production or per group."""
        n = len(pending)
        groups = {}
        for ent in pending:
            g = ent.get("group")
            if g is not None:
                groups.setdefault(g, []).append(ent)
        for i, ent in enumerate(pending):
            if ent["src"] == "orig":
                emit_original(ent["cid"], prod)
                continue
            base = copy.deepcopy(seq[ent["src"]]["model"]) if ent["src"] is not None else copy.deepcopy(content[ent["cid"]]["model"])
            for tf in ent["tfs"]:
                apply_tf(base, tf, c)
            g = ent.get("group")
            if g is not None:
                gi = groups[g].index(ent) + 1
                gn = len(groups[g])
                for fn in ent.get("gfun", []):
                    fn(base, gi, gn)
            for fn in numbering:
                fn(base, i + 1, n)
            parent_mech = seq[ent["src"]]["mech"] if ent["src"] is not None else None
            mech = "+".join(ent["mech"])
            if parent_mech and parent_mech != "original":
                mech = parent_mech + ">" + mech
            emit(ent["cid"], prod, mech, base)
            copies_made[0] += 1
        pending.clear()

    prod_no = [0]

    def next_prod(kind):
        prod_no[0] += 1
        prods.append(dict(no=prod_no[0], kind=kind))
        return prod_no[0]

    law_fax = case["law"]["fax"]

    # ---- production: provider release (originals, charts with outside records filed inside)
    pr = next_prod("release")
    hosts = [p for p in early if p["kind"] in ("ortho", "pt", "pain", "asc", "pcp", "neuro")]
    filed_budget = quota["release"]
    for p in early:
        chart = []
        for dt_ in ("faxcover", "request", "cert"):
            for d in doc_of([dt_], p["name"]):
                chart.append(("orig", d))
        cd = [d for d in clinical_docs if d["provider"] == p["name"]]
        cd.sort(key=lambda d: d["date"], reverse=p["reverse"])
        for d in cd:
            chart.append(("orig", d))
        for d in doc_of(["statement", "claimline"], p["name"]):
            chart.append(("orig", d))
        for d in chart:
            for cid in d[1]["cids"]:
                queue(cid, [], [], src="orig")
        # outside records filed in this chart
        if p in hosts and filed_budget > 0:
            outside = [d for d in clinical_docs if d["provider"] != p["name"] and all(cid in emitted or any(pe["cid"] == cid for pe in pending) for cid in d["cids"])
                       and d["dtype"] in ("er_visit", "imaging", "amended", "office_visit", "surgery", "ems")]
            for d in c.sample(outside, c.ri(1, 3)):
                if filed_budget <= 0:
                    break
                sender = next(pp for pp in provs if pp["name"] == d["provider"])
                fd = d["date"] + dt.timedelta(days=c.ri(1, 21))
                t = c.tm()
                tok = ["filed_in_chart(%s)" % p["name"]]
                tfs = []
                if c.chance(0.6):
                    tok.append("fax_header_%s" % sender["fax_style"])
                stamp = "OUTSIDE RECORDS - %s - REVIEWED %s" % (p["name"].split()[0].upper(), fmt(fd, p["style2"] if p["style2"] not in TIMESTAMP_STYLES else "MM/DD/YY"))
                tok.append("stamp_line")
                for j, cid in enumerate(d["cids"]):
                    ent_tfs = []
                    if "fax_header_%s" % sender["fax_style"] in tok:
                        ent_tfs.append(("top", tx_line(sender["fax_style"], case, fd, t, j + 1, len(d["cids"]), sender["name"], sender["fax"], p["fax"])))
                    if j == 0:
                        ent_tfs.append(("stamp_line", stamp, 3))
                    queue(cid, tok if j == 0 else [t_ for t_ in tok if t_ != "stamp_line"], ent_tfs)
                    filed_budget -= 1
        # first pass resolves originals in order so later filed copies can follow
    flush(pr, [])
    quota["re_request"] += max(0, filed_budget)

    # ---- production: re-request response (late providers' originals + re-sent copies by fax)
    pr = next_prod("re_request")
    budget = quota["re_request"]
    rr_provs = late + c.sample([p for p in early], len(early))
    for p in rr_provs:
        d_rr = doc_of(["rerequest"], p["name"])
        fdate = wd(d_rr[0]["date"] + dt.timedelta(days=c.ri(5, 20))) if d_rr else case["release_date"]
        t = c.tm()
        grp = "rr-" + p["name"]
        is_late = p["name"] in late_names
        items = []
        for dd in d_rr:
            items.append(("orig", dd))
        if is_late:
            for dt_ in ("faxcover", "request", "cert"):
                for d in doc_of([dt_], p["name"]):
                    items.append(("orig", d))
        for dd in [x for x in case["second_certs"] if x["for_prov"] == p["name"]]:
            items.append(("orig", dd))
        cd = sorted([d for d in clinical_docs if d["provider"] == p["name"]], key=lambda d: d["date"], reverse=p["reverse"])
        if is_late:
            for d in cd:
                items.append(("orig", d))
            for d in doc_of(["statement", "claimline"], p["name"]):
                items.append(("orig", d))
        elif budget > 0:
            k = max(1, int(len(cd) * (0.4 + c.rng.random() * 0.5)))
            for d in sorted(c.sample(cd, k), key=lambda d: d["date"]):
                if budget <= 0:
                    break
                items.append(("copy", d))
                budget -= len(d["cids"])
            if c.chance(0.6) and budget > 0:
                for d in doc_of(["statement"], p["name"]):
                    items.append(("copy", d))
                    budget -= len(d["cids"])
        stamp_d = fdate + dt.timedelta(days=c.ri(1, 4))
        first_copy = True
        for kind_, d in items:
            for j, cid in enumerate(d["cids"]):
                if kind_ == "orig":
                    queue(cid, [], [], src="orig")
                    continue
                tfs = []
                tok = ["re_request", "fax_header_%s" % p["fax_style"], "fax_page_count"]
                if first_copy:
                    tfs.append(("stamp_line", "RECEIVED  %s  %s" % (fmt(stamp_d, "MON DD YYYY"), case["law"]["name"].split()[0].upper()), 0))
                    tok.append("received_stamp_line")
                    first_copy = False
                queue(cid, tok, tfs)
                ent = pending[-1]
                ent["group"] = grp
                ent["gfun"] = [lambda m, gi, gn, p=p, fdate=fdate, t=t: apply_tf(m, ("top", tx_line(p["fax_style"], case, fdate, t, gi, gn, p["name"], p["fax"], law_fax)), None)]
    flush(pr, [])

    # remaining originals not yet emitted (safety): put them into re_request? (should be none)
    missing = [cid for cid in content if cid not in emitted]
    if missing:
        pr2 = prod_no[0]
        for cid in missing:
            queue(cid, [], [], src="orig")
        flush(pr2, [])

    def pick_docs(pool, budget, allow_partial=True):
        out = []
        pool = list(pool)
        c.rng.shuffle(pool)
        for d in pool:
            if budget <= 0:
                break
            cids = list(d["cids"])
            if allow_partial and len(cids) > 2 and c.chance(0.15):
                cids = cids[:len(cids) - 1]
            out.append((d, cids))
            budget -= len(cids)
        return out

    def parent_for(cid, prefer_copy):
        insts = emitted.get(cid, [])
        copies = [i for i in insts if seq[i]["mech"] != "original"]
        if prefer_copy and copies:
            return c.pick(copies)
        return None

    annotations_left = [c.ri(2, 4)]

    def maybe_annot(tfs, tok):
        if annotations_left[0] > 0 and c.chance(0.04):
            annotations_left[0] -= 1
            tfs.append(("annot", c.pick(B.ANNOTATIONS), c.ri(300, 470), c.ri(120, 640), 11.5, c.pick([0, 4, -3, 7])))
            tok.append("handwritten_note")

    for kind in middle:
        pr = next_prod(kind)
        budget = quota[kind]
        if kind == "insurer":
            cdate = case["release_date"] + dt.timedelta(days=c.ri(60, 140))
            pool = [d for d in docs if d["dtype"] in ("er_visit", "imaging", "amended", "surgery", "ems", "statement", "office_visit", "procedure", "pt_eval", "request", "claimline", "hipaa")]
            chosen = pick_docs(pool, budget)
            chosen.sort(key=lambda x: (x[0]["kind"] != "admin", x[0]["provider"], x[0]["date"]))
            cov_idx = [("%s - %s" % (d["provider"], d["dtype"].replace("_", " ")), len(cids)) for d, cids in chosen][:40]
            cov = insurer_cover_models(case, cdate, cov_idx)
            # cover is a new original admin page
            cid_new = "c%04d" % (len(content) + 1)
            content[cid_new] = dict(model=cov[0], provider=case["insurer"]["name"], doc_kind="admin", event=None)
            queue(cid_new, [], [], src="orig")
            t = c.tm()
            ins_tx = c.pick(["fxC", "secure"])
            for d, cids in chosen:
                scanned = c.chance(0.4)
                rate = c.pick([0.012, 0.02, 0.03])
                margin = c.chance(0.5)
                rd = cdate - dt.timedelta(days=c.ri(3, 50))
                for j, cid in enumerate(cids):
                    tok = ["insurer_claim_file", "transmit_header_%s" % ins_tx, "claim_page_number"]
                    tfs = [("top", tx_line(ins_tx, case, rd, t, j + 1, len(cids), case["law"]["name"], law_fax, case["insurer"]["fax"]))]
                    if j == 0:
                        if margin:
                            tfs.append(("stamp_margin", "RECEIVED %s CLAIMS INTAKE" % fmt(rd + dt.timedelta(days=1), "MM.DD.YY"), c.ri(250, 520)))
                            tok.append("received_stamp_margin")
                        else:
                            tfs.append(("stamp_line", "REC'D %s  CLAIM %s" % (fmt(rd + dt.timedelta(days=1), "M/D/YY"), case["insurer"]["claim"]), c.ri(1, 6)))
                            tok.append("received_stamp_line")
                    if scanned:
                        tfs.append(("ocr", rate, hash_str(cid + "ins")))
                        tok.append("scan_ocr_errors")
                    maybe_annot(tfs, tok)
                    queue(cid, tok, tfs)
            claim = case["insurer"]["claim"]
            flush(pr, [lambda m, i, n, claim=claim: apply_tf(m, ("bottom", "Claim %s   Doc pg %04d" % (claim, i), "H", 7.5, "l"), None)])
        elif kind == "portal":
            cands = [p for p in provs if p["kind"] in ("ortho", "pcp", "pt", "pain", "neuro", "er", "chiro")]
            size = lambda p: sum(len(d["cids"]) for d in clinical_docs if d["provider"] == p["name"])  # noqa: E731
            big = [p for p in cands if size(p) >= budget]
            host = c.pick(big) if big else max(cands, key=size)
            pool = [d for d in clinical_docs if d["provider"] == host["name"]]
            # portals often also show results received from other providers
            pool += c.sample([d for d in clinical_docs if d["dtype"] in ("imaging", "lab") and d["provider"] != host["name"]], 2)
            chosen = pick_docs(pool, budget, allow_partial=False)
            chosen.sort(key=lambda x: x[0]["date"])
            portal = "%s MyChart-style portal".replace("MyChart-style", c.pick(["HealthLink", "PatientConnect", "CareView"])) % host["name"].split()[0]
            pd = case["release_date"] + dt.timedelta(days=c.ri(5, 60))
            t = c.tm()
            for d, cids in chosen:
                for cid in cids:
                    queue(cid, ["portal_download", "reflow", "portal_page_count"], [("reflow", c.pick([88, 96, 104]), c.pick([8.2, 8.8]))])
            flush(pr, [lambda m, i, n, portal=portal, pd=pd, t=t: apply_tf(m, ("top", "%s - printed by patient %s" % (portal, fmt(pd, "Mon D YYYY h:MMam", t)), "H", 7.6), None),
                       lambda m, i, n: apply_tf(m, ("bottom", "Page %d of %d" % (i, n), "H", 7.6, "c"), None)])
        elif kind == "subpoena":
            er = case["by_kind"]["er"]
            pool = [d for d in clinical_docs if d["provider"] == er["name"]]
            chosen = pick_docs(pool, budget, allow_partial=False)
            chosen.sort(key=lambda x: x[0]["date"])
            sd = case["release_date"] + dt.timedelta(days=c.ri(90, 200))
            t = c.tm()
            # a fresh cert from the hospital for this production (another look-alike cert)
            cust = "%s %s" % (c.pick(B.CLIN_FIRST), c.pick(B.CLIN_LAST))
            evs = [e for e in case["events"] if e["prov"] is er]
            cm = cert_models(case, er, cust, sd, sum(len(x[1]) for x in chosen), evs[0]["date"], evs[-1]["date"])[0]
            cid_new = "c%04d" % (len(content) + 1)
            content[cid_new] = dict(model=cm, provider=er["name"], doc_kind="admin", event=None)
            queue(cid_new, [], [], src="orig")
            for d, cids in chosen:
                for cid in cids:
                    tok = ["subpoena_response", "him_release_header", "page_x_of_y"]
                    tfs = [("top", tx_line("him", case, sd, t, 0, 0, er["name"], er["fax"], ""), "C", 7.2)]
                    maybe_annot(tfs, tok)
                    queue(cid, tok, tfs)
            flush(pr, [lambda m, i, n: apply_tf(m, ("bottom", "SUBP %d / %d" % (i, n), "CB", 8, "r"), None)])
        quota["defense"] += max(0, budget - copies_this(seq, pr))

    # ---- defense production (Bates; many copies of copies)
    pr = next_prod("defense")
    budget = case["n_copies_target"] - copies_made[0]
    ddate = case["release_date"] + dt.timedelta(days=c.ri(200, 320))
    pool = [d for d in docs if d["dtype"] not in ("hipaa2",)]
    chosen = []
    left = max(0, budget - 1)
    while left > 0:
        # the same records can reach defense counsel from more than one source
        got = pick_docs(pool, left)
        chosen += got
        left -= sum(len(x[1]) for x in got)
    order = c.pick(["provider", "date", "mixed"])
    if order == "provider":
        chosen.sort(key=lambda x: (x[0]["provider"], x[0]["date"]))
    elif order == "date":
        chosen.sort(key=lambda x: x[0]["date"])
    prefix = case["defense"]["prefix"]
    start = c.ri(1, 900)
    total_n = sum(len(x[1]) for x in chosen) + 1
    dc = defense_cover_models(case, ddate, "%s %06d" % (prefix, start), "%s %06d" % (prefix, start + total_n - 1))[0]
    cid_new = "c%04d" % (len(content) + 1)
    content[cid_new] = dict(model=dc, provider=case["defense"]["name"], doc_kind="admin", event=None)
    queue(cid_new, [], [], src="orig")
    for d, cids in chosen:
        crop = c.chance(0.22)
        crop_args = (c.ri(1, 3), c.ri(0, 2), c.pick([0, 0, 40, 70]))
        prefer_copy = c.chance(0.55)
        append_stamp = c.chance(0.3)
        for j, cid in enumerate(cids):
            src = parent_for(cid, prefer_copy)
            tok = ["defense_production", "bates"]
            tfs = []
            if crop:
                tfs.append(("crop",) + crop_args)
                tok.append("crop" if not crop_args[2] else "crop_right_clip")
            if append_stamp:
                tfs.append(("stamp_append", "CONFIDENTIAL-PO", c.ri(0, 30)))
                tok.append("appended_stamp")
            maybe_annot(tfs, tok)
            queue(cid, tok, tfs, src=src)
            if c.chance(0.025):
                queue(cid, tok + ["rescan_double_feed"], tfs, src=src)
    flush(pr, [lambda m, i, n: apply_tf(m, ("bottom", "%s %06d" % (prefix, start + i - 1), "HB", 9, "r"), None)])

    case["seq"] = seq
    case["prods"] = prods


def copies_this(seq, prod):
    return sum(1 for s in seq if s["prod"] == prod and s["mech"] != "original")


# ---------------------------------------------------------------- output
def write_case(case, outdir):
    os.makedirs(outdir, exist_ok=True)
    seq = case["seq"]
    content = case["content"]
    # mechanism of first occurrence must be original
    first = {}
    for i, s in enumerate(seq):
        if s["cid"] not in first:
            first[s["cid"]] = i
            assert s["mech"] == "original", (case["case_id"], s["cid"], s["mech"])
    pages = []
    for i, s in enumerate(seq):
        cv = content[s["cid"]]
        pages.append(dict(page=i + 1, content_id=s["cid"], provider=cv["provider"], production=s["prod"],
                          mechanism=s["mech"], doc_kind=cv["doc_kind"]))
    events = []
    for e in case["events"]:
        events.append(dict(event_id=e["event_id"], date=fmt(e["date"], "MM/DD/YYYY"), provider=e["prov"]["name"], kind=e["kind"],
                           summary=summary_for(case, e), codes=e["codes"], procedures=e["cpts"], doc_id=e["doc_id"], pages=e["cids"]))
    truth = dict(case_id=case["case_id"],
                 patient=dict(first=case["patient"]["first"], last=case["patient"]["last"], dob=fmt(case["dob"], "MM/DD/YYYY")),
                 accident_date=fmt(case["acc"], "MM/DD/YYYY"), regions=case["regions"], events=events, pages=pages)
    with open(os.path.join(outdir, "truth.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(truth, f, indent=1)
        f.write("\n")
    write_pdf(os.path.join(outdir, "records.pdf"), [render(s["model"]) for s in seq], title="Records %s" % case["case_id"])
    return truth


def summary_for(case, e):
    k = e["kind"]
    inc = case["incident"]
    if k == "prior_visit":
        return "Pre-incident visit: %s." % e["reason"][0].lower()
    if k == "ems":
        return "EMS response and transport to %s after %s." % (case["by_kind"]["er"]["name"], inc["short"])
    if k == "er_visit":
        return "Emergency department evaluation after %s involving the %s." % (inc["short"], ", ".join(case["regions"]))
    if k == "imaging":
        return "%s of the %s%s." % (e["study"][1], e["region"], " (original and amended report)" if e.get("amended") else "")
    if k == "lab":
        return "Laboratory panel (%s)." % ("pre-operative" if e["panel"] == "preop" else "emergency department")
    if k == "office_visit":
        if e.get("chiro"):
            return "Chiropractic treatment visit #%d." % e["seq"]
        if e.get("postop"):
            return "Postoperative follow-up visit."
        return "%s visit #%d at %s for injuries from the incident." % ("New patient" if e["seq"] == 1 else "Follow-up", e["seq"], e["prov"]["name"])
    if k == "pt_eval":
        return "Physical therapy initial evaluation."
    if k == "pt_visit":
        return "Physical therapy treatment session, visit %d." % (e["seq"] + 1)
    if k == "pt_reeval":
        return "Physical therapy %s." % ("discharge summary" if e.get("discharge") else "re-evaluation")
    if k == "procedure":
        return ("Electrodiagnostic study (EMG/NCS)." if e.get("emg") else "%s." % e["proc"][1])
    if k == "surgery":
        return "%s." % e["proc"][1]
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--cases", default="1,2,3,4,5,6,7,8,9,10")
    a = ap.parse_args()
    for i in [int(x) for x in a.cases.split(",")]:
        case = build_case(i)
        truth = write_case(case, os.path.join(a.out, "alt4-%d" % i))
        n = len(truth["pages"])
        u = len(set(p["content_id"] for p in truth["pages"]))
        print("alt4-%d pages=%d unique=%d dup=%.1f%% events=%d providers=%d" % (i, n, u, 100.0 * (n - u) / n, len(truth["events"]), len(case["providers"])))


if __name__ == "__main__":
    main()
