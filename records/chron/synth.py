"""Synthetic plaintiff injury cases: the clinical truth and the documents it produces.

Everything here is invented. Patients, clinicians and providers are fictional;
no real patient data is used anywhere. A case is a motor-vehicle accident
followed by the care a plaintiff typically receives (ER, primary care,
orthopaedics, imaging, physical therapy, pain management, sometimes surgery),
plus one unrelated visit before the accident.

    case = make_case(seed)
    case.events     -> the ground-truth chronology (what happened, when, where)
    case.documents  -> the records each provider would produce, as text pages

Each document page gets a stable content id (`<doc_id>-p<n>`). Copies of a page
made later (fax, rescan, re-production) keep that id, which is how the
duplicate answer key is built.
"""
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

LINES_PER_PAGE = 44
WIDTH = 92

FIRST = ["Maria", "James", "Aisha", "Daniel", "Sofia", "Kevin", "Grace", "Luis", "Priya", "Marcus",
         "Elena", "Tyrone", "Mei", "Andre", "Fatima", "Robert", "Yesenia", "Omar", "Hannah", "Victor"]
LAST = ["Alvarez", "Brennan", "Okafor", "Kowalski", "Nguyen", "Delgado", "Feldman", "Haddad", "Morales",
        "Petrov", "Rahman", "Santiago", "Thompson", "Vasquez", "Whitaker", "Yilmaz", "Coleman", "Ibarra"]
CLIN_FIRST = ["Alan", "Beatriz", "Chen", "Deborah", "Emeka", "Farah", "Gregory", "Helen", "Imran", "Julia",
              "Kofi", "Lena", "Mateo", "Nadia", "Oren", "Paula", "Rajiv", "Simone", "Tomas", "Vera"]
CLIN_LAST = ["Abrams", "Bose", "Castellano", "Dunleavy", "Esposito", "Friedman", "Gallo", "Hoffman", "Iqbal",
             "Jensen", "Kaplan", "Lindqvist", "Mancuso", "Novak", "Ortiz", "Pereira", "Quinlan", "Reyes"]

PROVIDERS = {
    "hospital": ["Harbor Point Medical Center", "Eastbridge General Hospital", "Saint Columba Hospital"],
    "pcp": ["Bay Ridge Family Medicine, PC", "Greenway Primary Care Associates", "Linden Avenue Medical Group"],
    "ortho": ["Atlantic Orthopaedic Associates", "Riverside Bone & Joint, PLLC", "Crescent Orthopedics"],
    "imaging": ["Narrows Imaging Center", "Clearview Diagnostic Radiology", "Metro Open MRI"],
    "pt": ["Shorefront Physical Therapy", "Motion First Rehab, PT PC", "Kingsway Physical Therapy"],
    "pain": ["Kings Pain & Spine, PLLC", "Parkside Interventional Pain", "Brightwater Spine Center"],
    "asc": ["Ridgeview Ambulatory Surgery Center", "Northgate Surgical Pavilion"],
}
STREETS = ["Ocean Pkwy", "Fourth Ave", "Kings Hwy", "Atlantic Ave", "Bay Pkwy", "Flatbush Ave", "Court St"]

# Body regions an accident can injure, with real ICD-10-CM and CPT codes.
REGIONS = {
    "neck": {
        "label": "cervical spine", "complaint": "neck pain radiating to the right shoulder",
        "acute": [("S13.4XXA", "Sprain of ligaments of cervical spine, initial encounter")],
        "pain": ("M54.2", "Cervicalgia"),
        "disc": ("M50.20", "Other cervical disc displacement, unspecified cervical region"),
        "xray": ("72040", "X-ray cervical spine, 2-3 views"),
        "mri": ("72141", "MRI cervical spine without contrast"),
        "esi": ("62321", "Cervical/thoracic epidural steroid injection with imaging guidance"),
        "rom": ["cervical flexion", "cervical extension", "cervical rotation R", "cervical rotation L"],
        "levels": ["C4-C5", "C5-C6", "C6-C7"],
    },
    "back": {
        "label": "lumbar spine", "complaint": "low back pain radiating to the left buttock",
        "acute": [("S33.5XXA", "Sprain of ligaments of lumbar spine, initial encounter")],
        "pain": ("M54.50", "Low back pain, unspecified"),
        "disc": ("M51.26", "Other intervertebral disc displacement, lumbar region"),
        "xray": ("72100", "X-ray lumbosacral spine, 2-3 views"),
        "mri": ("72148", "MRI lumbar spine without contrast"),
        "esi": ("62323", "Lumbar/sacral epidural steroid injection with imaging guidance"),
        "rom": ["lumbar flexion", "lumbar extension", "lateral bending R", "lateral bending L"],
        "levels": ["L3-L4", "L4-L5", "L5-S1"],
    },
    "knee": {
        "label": "right knee", "complaint": "right knee pain and swelling after striking the dashboard",
        "acute": [("S83.511A", "Sprain of anterior cruciate ligament of right knee, initial encounter")],
        "pain": ("M25.561", "Pain in right knee"),
        "disc": ("S83.241A", "Other tear of medial meniscus, current injury, right knee, initial encounter"),
        "xray": ("73562", "X-ray right knee, 3 views"),
        "mri": ("73721", "MRI right knee without contrast"),
        "surgery": ("29881", "Arthroscopy, knee, with partial medial meniscectomy"),
        "rom": ["knee flexion", "knee extension"],
        "levels": ["posterior horn of the medial meniscus"],
    },
    "shoulder": {
        "label": "right shoulder", "complaint": "right shoulder pain with overhead reaching",
        "acute": [("S43.401A", "Unspecified sprain of right shoulder joint, initial encounter")],
        "pain": ("M25.511", "Pain in right shoulder"),
        "disc": ("S46.011A", "Strain of muscle(s) and tendon(s) of the rotator cuff of right shoulder, initial encounter"),
        "xray": ("73030", "X-ray right shoulder, 2+ views"),
        "mri": ("73221", "MRI right shoulder without contrast"),
        "rom": ["shoulder flexion", "shoulder abduction", "external rotation"],
        "levels": ["supraspinatus tendon"],
    },
}
ACCIDENT_CODE = ("V43.52XA", "Car driver injured in collision with other motor vehicle in traffic accident, initial encounter")


@dataclass
class Event:
    """One entry of the ground-truth chronology."""
    event_id: str
    date: str
    provider: str
    kind: str              # er_visit, office_visit, imaging, pt_eval, pt_visit, injection, surgery, prior_visit
    summary: str
    codes: list            # ICD-10 diagnosis codes recorded at this event
    procedures: list       # CPT codes performed
    doc_id: str = ""       # the document that records it
    pages: list = field(default_factory=list)  # content ids of the pages that record it


@dataclass
class Document:
    doc_id: str
    provider: str
    title: str
    date: str
    kind: str              # clinical, billing, admin
    pages: list            # list of page texts (each a list of lines)


@dataclass
class Case:
    case_id: str
    patient: dict
    accident_date: str
    regions: list
    events: list
    documents: list


def fmt(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def paginate(lines, header):
    """Split body lines into pages, each starting with the document header."""
    body = LINES_PER_PAGE - len(header) - 2
    chunks = [lines[i:i + body] for i in range(0, len(lines), body)] or [[]]
    n = len(chunks)
    return [header + [""] + c + ["", f"Page {i + 1} of {n}".rjust(WIDTH)] for i, c in enumerate(chunks)]


class Builder:
    def __init__(self, seed: int):
        self.r = random.Random(seed)
        self.seed = seed
        self.events, self.documents = [], []
        self._doc_n = 0

    def pick(self, xs):
        return self.r.choice(xs)

    def clinician(self, cred):
        return f"{self.pick(CLIN_FIRST)} {self.pick(CLIN_LAST)}, {cred}"

    def doc(self, provider, title, d, kind, lines, header_extra=()):
        self._doc_n += 1
        doc_id = f"d{self._doc_n:03d}"
        p = self.patient
        header = [provider["name"].upper(), f"{provider['address']}   Tel {provider['phone']}   Fax {provider['fax']}",
                  title.upper(), f"Patient: {p['last']}, {p['first']}   DOB: {fmt(p['dob'])}   MRN: {provider['mrn']}",
                  *header_extra, "-" * WIDTH]
        document = Document(doc_id, provider["name"], title, fmt(d), kind, paginate(lines, header))
        self.documents.append(document)
        return document

    def event(self, d, provider, kind, summary, codes, procedures, document, pages=None):
        e = Event(f"e{len(self.events) + 1:03d}", fmt(d), provider["name"], kind, summary,
                  [c for c, _ in codes], [c for c, _ in procedures], document.doc_id,
                  [f"{document.doc_id}-p{i + 1}" for i in (pages if pages is not None else range(len(document.pages)))])
        self.events.append(e)
        return e

    def provider(self, kind):
        return {"name": self.pick(PROVIDERS[kind]),
                "address": f"{self.r.randint(10, 9800)} {self.pick(STREETS)}, Brooklyn, NY {self.r.choice(['11204', '11209', '11214', '11220', '11223', '11229'])}",
                "phone": f"718-{self.r.randint(200, 999)}-{self.r.randint(1000, 9999)}",
                "fax": f"718-{self.r.randint(200, 999)}-{self.r.randint(1000, 9999)}",
                "mrn": f"{self.r.randint(10_000_000, 99_999_999)}"}


def wrap(text, width=WIDTH, indent=""):
    words, lines, cur = text.split(), [], indent
    for w in words:
        if len(cur) + len(w) + 1 > width and cur.strip():
            lines.append(cur.rstrip())
            cur = indent
        cur += w + " "
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def section(title, text):
    return [title.upper() + ":"] + wrap(text, indent="  ") + [""]


def charges_lines(rows):
    lines = [f"{'DATE':<12}{'CPT':<8}{'DESCRIPTION':<56}{'CHARGE':>12}"]
    total = 0
    for d, code, desc, amt in rows:
        lines.append(f"{d:<12}{code:<8}{desc[:54]:<56}{amt:>12,.2f}")
        total += amt
    lines += ["", f"{'TOTAL CHARGES':<76}{total:>12,.2f}", f"{'PAYMENTS / ADJUSTMENTS':<76}{0:>12,.2f}",
              f"{'BALANCE DUE':<76}{total:>12,.2f}"]
    return lines


DISCHARGE_TEXT = (
    "You were seen in the Emergency Department for injuries from a motor vehicle collision. Muscle strain "
    "and ligament sprain are common after a collision and may feel worse during the first 2 to 3 days. "
    "Apply ice for 20 minutes at a time, several times a day, for the first 48 hours, then switch to warm "
    "compresses. Take medications only as directed. Do not drive or operate machinery while taking "
    "cyclobenzaprine, as it may cause drowsiness. Gentle movement is better than bed rest. Return to the "
    "Emergency Department immediately for new numbness or weakness in the arms or legs, loss of bladder or "
    "bowel control, severe headache, vomiting, confusion, chest pain or shortness of breath, or pain that "
    "is getting rapidly worse. Follow up with your primary care provider in 2 to 3 days. If you were "
    "referred to a specialist, call to schedule an appointment. Bring this paper and a list of your "
    "medications to your follow-up visit. These instructions do not replace the advice of your doctor.")

QUESTIONNAIRE = {
    "neck": ("NECK DISABILITY INDEX", ["Pain intensity", "Personal care", "Lifting", "Reading", "Headaches",
                                       "Concentration", "Work", "Driving", "Sleeping", "Recreation"]),
    "back": ("OSWESTRY LOW BACK DISABILITY QUESTIONNAIRE", ["Pain intensity", "Personal care", "Lifting", "Walking",
                                                            "Sitting", "Standing", "Sleeping", "Social life", "Traveling", "Employment"]),
    "knee": ("LOWER EXTREMITY FUNCTIONAL SCALE", ["Usual work", "Hobbies", "Getting into bath", "Walking between rooms",
                                                  "Putting on shoes", "Squatting", "Lifting a bag", "Light activities",
                                                  "Stairs", "Running"]),
    "shoulder": ("QUICKDASH SHOULDER QUESTIONNAIRE", ["Open a jar", "Heavy chores", "Carry a bag", "Wash your back",
                                                      "Use a knife", "Recreation", "Social activities", "Work limitation",
                                                      "Arm pain", "Tingling", "Sleeping"]),
}


def questionnaire(r, regions, severity):
    """A patient-completed form: same layout every visit, different scores."""
    out = []
    for reg in regions:
        title, items = QUESTIONNAIRE[reg]
        out += [title, "Patient-completed form. Circle the one statement that best describes you today.", ""]
        total = 0
        for it in items:
            s = max(0, min(5, round(severity * 5 + r.uniform(-1.2, 1.2))))
            total += s
            out.append(f"  {it:<28} 0  1  2  3  4  5      Selected: {s}")
        out += ["", f"  TOTAL SCORE: {total} / {5 * len(items)}  ({round(100 * total / (5 * len(items)))}%)",
                "  Patient signature: ______________________", ""]
    return out


def claim_form(prov, patient, d, code, desc, amount, dx, insured_id):
    """One CMS-1500-style claim page: identical layout, different service line."""
    return [
        "HEALTH INSURANCE CLAIM FORM (CMS-1500 FORMAT)", "",
        f"1. TYPE OF COVERAGE: No-Fault / Auto      1a. INSURED ID: {insured_id}",
        f"2. PATIENT NAME: {patient['last'].upper()}, {patient['first'].upper()}        3. DOB: {fmt(patient['dob'])}",
        "10. IS CONDITION RELATED TO: (b) AUTO ACCIDENT? [X] YES  STATE: NY",
        "21. DIAGNOSIS: " + "   ".join(f"{chr(65 + i)}. {c}" for i, c in enumerate(dx)), "",
        "24.  DATE OF SERVICE   PLACE  CPT/HCPCS   DESCRIPTION                       DX PTR   CHARGES",
        f"     {fmt(d)}       11     {code:<10}  {desc[:32]:<32}  A        {amount:>9,.2f}", "",
        f"28. TOTAL CHARGE: {amount:,.2f}      29. AMOUNT PAID: 0.00",
        f"32. SERVICE FACILITY: {prov['name']}, {prov['address']}",
        f"33. BILLING PROVIDER: {prov['name']}   PH {prov['phone']}",
        "", "SIGNATURE OF PHYSICIAN OR SUPPLIER: Signature on file",
    ]


def make_case(seed: int, case_id: str = "") -> Case:
    b = Builder(seed)
    r = b.r
    acc = date(2024, 1, 1) + timedelta(days=r.randint(0, 540))
    b.patient = {"first": b.pick(FIRST), "last": b.pick(LAST),
                 "dob": date(1958, 1, 1) + timedelta(days=r.randint(0, 365 * 40))}
    regions = r.sample(list(REGIONS), r.choice([1, 2, 2, 3]))
    R = [REGIONS[x] for x in regions]
    prov = {k: b.provider(k) for k in PROVIDERS}
    age = (acc - b.patient["dob"]).days // 365
    billing = {k: [] for k in PROVIDERS}  # per provider: (date, cpt, desc, amount)

    # --- Prior unrelated visit (pre-existing history matters to a case) ---
    d0 = acc - timedelta(days=r.randint(120, 400))
    doc_clin = b.clinician("MD")
    lines = (section("Reason for visit", "Annual physical examination. No complaints today.")
             + section("History", f"{age - 1}-year-old here for routine physical. Denies neck, back or joint pain. "
                       f"No prior injuries to the {', '.join(x['label'] for x in R)}. Exercises 2-3 times weekly.")
             + section("Vitals", f"BP {r.randint(112, 134)}/{r.randint(70, 86)}, HR {r.randint(60, 82)}, BMI {r.uniform(22, 31):.1f}")
             + section("Exam", "Full range of motion of the spine and all extremities without pain. Neurologic exam normal.")
             + section("Assessment", "Z00.00 Encounter for general adult medical examination without abnormal findings.")
             + section("Plan", "Routine labs ordered. Return in one year.") + [f"Electronically signed by {doc_clin} on {fmt(d0)}"])
    dd = b.doc(prov["pcp"], "Office Visit Note", d0, "clinical", lines, (f"Date of service: {fmt(d0)}   Provider: {doc_clin}",))
    b.event(d0, prov["pcp"], "prior_visit", "Annual physical before the accident; no complaints and full range of motion.",
            [("Z00.00", "")], [("99396", "")], dd)
    billing["pcp"].append((fmt(d0), "99396", "Preventive visit, established patient, 40-64", 285.00))
    labs = [("WBC", f"{r.uniform(4.5, 9.5):.1f}", "4.0-11.0 K/uL"), ("Hemoglobin", f"{r.uniform(12.5, 15.5):.1f}", "12.0-16.0 g/dL"),
            ("Platelets", f"{r.randint(170, 380)}", "150-400 K/uL"), ("Glucose", f"{r.randint(78, 104)}", "70-99 mg/dL"),
            ("Creatinine", f"{r.uniform(.6, 1.1):.2f}", "0.6-1.2 mg/dL"), ("Sodium", f"{r.randint(136, 144)}", "135-145 mmol/L"),
            ("Potassium", f"{r.uniform(3.6, 4.9):.1f}", "3.5-5.1 mmol/L"), ("ALT", f"{r.randint(12, 38)}", "7-56 U/L"),
            ("LDL cholesterol", f"{r.randint(85, 150)}", "<100 mg/dL")]
    ld0 = d0 + timedelta(days=1)
    lines = ([f"Collected: {fmt(d0)}   Reported: {fmt(ld0)}   Ordering: {doc_clin}", "",
              f"{'TEST':<24}{'RESULT':>10}   {'REFERENCE RANGE':<20}"]
             + [f"{t:<24}{v:>10}   {ref:<20}" for t, v, ref in labs] + ["", "Results reviewed. No critical values."])
    lb = b.doc(prov["pcp"], "Laboratory Report", ld0, "clinical", lines, (f"Accession: L{r.randint(100000, 999999)}",))
    b.event(d0, prov["pcp"], "lab", "Routine blood work after the annual physical; no critical values.", [], [("80053", ""), ("85025", "")], lb)

    # --- ER visit on the day of the accident ---
    er = b.clinician("MD")
    mech = b.pick(["rear-ended while stopped at a red light", "struck on the driver side at an intersection",
                   "rear-ended at about 30 mph on the expressway"])
    xr = [x["xray"] for x in R]
    acute = [c for x in R for c in x["acute"]] + [ACCIDENT_CODE]
    lines = (section("Chief complaint", "; ".join(x["complaint"] for x in R) + " after motor vehicle collision.")
             + section("History of present illness", f"{age}-year-old restrained driver {mech} approximately "
                       f"{r.randint(1, 5)} hours prior to arrival. Airbags {'deployed' if r.random() < .5 else 'did not deploy'}. "
                       f"No loss of consciousness. Pain rated {r.randint(6, 9)}/10.")
             + section("Vitals", f"BP {r.randint(128, 152)}/{r.randint(78, 94)}, HR {r.randint(78, 104)}, RR 16, SpO2 99% on room air")
             + section("Physical exam", " ".join(f"Tenderness to palpation over the {x['label']} with reduced range of motion." for x in R)
                       + " Neurovascularly intact distally.")
             + section("Imaging", " ".join(f"{d} ordered." for _, d in xr))
             + section("ED course", "Ketorolac 30 mg IM given with partial relief.")
             + section("Diagnoses", "; ".join(f"{c} {t}" for c, t in acute))
             + section("Disposition", "Discharged home in stable condition. Ibuprofen 600 mg every 8 hours as needed, "
                       "cyclobenzaprine 5 mg at bedtime. Follow up with primary care in 2-3 days.")
             + [f"Electronically signed by {er} on {fmt(acc)}", ""]
             + section("Triage nursing note", f"Arrived by {b.pick(['ambulance', 'private car', 'taxi'])}. Ambulatory with "
                       f"assistance. Cervical collar {'applied by EMS' if r.random() < .4 else 'not applied'}. Pain {r.randint(6, 9)}/10. "
                       f"Allergies: {b.pick(['NKDA', 'penicillin (rash)', 'sulfa drugs'])}. Triage level ESI 3.")
             + section("Discharge instructions", DISCHARGE_TEXT)
             + ["Patient verbalized understanding of discharge instructions.", "Patient signature: ______________________"])
    ed = b.doc(prov["hospital"], "Emergency Department Record", acc, "clinical", lines,
               (f"Date of service: {fmt(acc)}   Attending: {er}",))
    b.event(acc, prov["hospital"], "er_visit", f"ER visit after motor vehicle collision ({mech}); "
            + "; ".join(x["complaint"] for x in R) + ". Discharged with ibuprofen and cyclobenzaprine.",
            acute, [("99284", "")], ed)
    rad = b.clinician("MD")
    lines = []
    for code, desc in xr:
        lines += section(desc, "No acute fracture or dislocation. Mild straightening of the normal curvature, "
                         "which may reflect muscle spasm." if "spine" in desc else "No acute fracture or dislocation. "
                         "Small joint effusion.") + section("Impression", "No acute osseous abnormality.")
    lines.append(f"Dictated and signed by {rad} on {fmt(acc)}")
    xd = b.doc(prov["hospital"], "Radiology Report", acc, "clinical", lines, (f"Exam date: {fmt(acc)}   Ordering: {er}",))
    b.event(acc, prov["hospital"], "imaging", "X-rays in the ER: " + ", ".join(d for _, d in xr) + "; no fracture.",
            [], xr, xd)
    billing["hospital"] += [(fmt(acc), "99284", "Emergency dept visit, moderate-high severity", 1840.00),
                            (fmt(acc), "J1885", "Ketorolac tromethamine injection, per 15 mg", 64.00)]
    billing["hospital"] += [(fmt(acc), c, d, float(r.randint(380, 720))) for c, d in xr]

    # --- Primary care follow-up ---
    d1 = acc + timedelta(days=r.randint(2, 6))
    lines = (section("Reason for visit", "Follow-up after motor vehicle collision on " + fmt(acc) + ".")
             + section("Interval history", "Seen in the emergency department on the day of the accident. "
                       + " ".join(f"Persistent {x['complaint']}." for x in R) + f" Pain {r.randint(5, 8)}/10. Difficulty sleeping.")
             + section("Exam", " ".join(f"Paraspinal/periarticular tenderness of the {x['label']}; range of motion reduced by about "
                                        f"{r.randint(20, 45)}%." for x in R))
             + section("Assessment", "; ".join(f"{x['pain'][0]} {x['pain'][1]}" for x in R))
             + section("Plan", "Referred to orthopaedics and physical therapy. Continue ibuprofen. Out of work for two weeks.")
             + [f"Electronically signed by {doc_clin} on {fmt(d1)}", ""] + questionnaire(r, regions, .75))
    dd = b.doc(prov["pcp"], "Office Visit Note", d1, "clinical", lines, (f"Date of service: {fmt(d1)}   Provider: {doc_clin}",))
    b.event(d1, prov["pcp"], "office_visit", "Primary care follow-up; referred to orthopaedics and physical therapy; "
            "out of work for two weeks.", [x["pain"] for x in R], [("99214", "")], dd)
    billing["pcp"].append((fmt(d1), "99214", "Office visit, established patient, moderate", 260.00))

    # --- Orthopaedic consult -> MRI ---
    ortho = b.clinician("MD")
    d2 = d1 + timedelta(days=r.randint(5, 12))
    lines = (section("History", f"Referred by {doc_clin} for injuries from a motor vehicle collision on {fmt(acc)}. "
                     + " ".join(f"Reports {x['complaint']}." for x in R) + " Prior to the accident the patient had no "
                     "symptoms in these areas.")
             + section("Exam", " ".join(f"{x['label'].capitalize()}: " + ", ".join(f"{m} {r.randint(20, 60)} degrees" for m in x["rom"])
                                        + "." for x in R))
             + section("Assessment", "; ".join(f"{c} {t}" for x in R for c, t in x["acute"]))
             + section("Plan", "MRI of the " + " and ".join(x["label"] for x in R) + ". Continue physical therapy 3 times weekly. "
                       "Naproxen 500 mg twice daily. Re-evaluate after MRI.")
             + [f"Electronically signed by {ortho} on {fmt(d2)}", ""] + questionnaire(r, regions, .7))
    od = b.doc(prov["ortho"], "Orthopaedic Consultation", d2, "clinical", lines, (f"Date of service: {fmt(d2)}   Physician: {ortho}",))
    b.event(d2, prov["ortho"], "office_visit", "Orthopaedic consultation; MRI ordered; started naproxen.",
            [c for x in R for c in x["acute"]], [("99204", "")], od)
    billing["ortho"].append((fmt(d2), "99204", "Office visit, new patient, moderate", 420.00))

    d3 = d2 + timedelta(days=r.randint(6, 16))
    rad2 = b.clinician("MD")
    findings = {}
    lines = []
    for x in R:
        lvl = b.pick(x["levels"])
        size = r.choice([2, 3, 3, 4, 5])
        if x["label"].endswith("spine"):
            f = f"{size} mm posterior disc herniation at {lvl} indenting the thecal sac"
        elif "knee" in x["label"]:
            f = f"Oblique tear of the {lvl} extending to the inferior articular surface"
        else:
            f = f"Partial-thickness articular-sided tear of the {lvl}"
        findings[x["label"]] = f
        lines += section(x["mri"][1], "Technique: multiplanar multisequence imaging without contrast. Findings: " + f + ".")
        lines += section("Impression", f + ".")
    lines.append(f"Electronically signed by {rad2}, Board Certified Radiologist, on {fmt(d3)}")
    md = b.doc(prov["imaging"], "MRI Report", d3, "clinical", lines, (f"Exam date: {fmt(d3)}   Referring: {ortho}",))
    b.event(d3, prov["imaging"], "imaging", "MRI: " + "; ".join(findings.values()) + ".", [x["disc"] for x in R],
            [x["mri"] for x in R], md)
    billing["imaging"] += [(fmt(d3), c, d, float(r.randint(1400, 2600))) for c, d in (x["mri"] for x in R)]

    # --- Physical therapy: evaluation + templated daily notes ---
    pt = b.clinician("PT, DPT")
    pt_start = d1 + timedelta(days=r.randint(3, 8))
    lines = (section("Diagnosis", "; ".join(f"{x['pain'][0]} {x['pain'][1]}" for x in R))
             + section("Subjective", f"Injured in a motor vehicle collision on {fmt(acc)}. Pain {r.randint(6, 8)}/10, worse with sitting and lifting.")
             + section("Objective", " ".join(", ".join(f"{m} {r.randint(15, 50)} deg" for m in x["rom"]) + "." for x in R))
             + section("Plan", "Therapeutic exercise, manual therapy and electrical stimulation, 3 times weekly for 8 weeks.")
             + [f"Electronically signed by {pt} on {fmt(pt_start)}", ""] + questionnaire(r, regions, .7))
    pd = b.doc(prov["pt"], "Physical Therapy Initial Evaluation", pt_start, "clinical", lines,
               (f"Date of service: {fmt(pt_start)}   Therapist: {pt}",))
    b.event(pt_start, prov["pt"], "pt_eval", "Physical therapy evaluation; plan 3 times weekly for 8 weeks.",
            [x["pain"] for x in R], [("97162", "")], pd)
    billing["pt"].append((fmt(pt_start), "97162", "PT evaluation, moderate complexity", 210.00))
    n_visits = r.randint(12, 24)
    d = pt_start
    pain = r.randint(6, 8)
    for v in range(1, n_visits + 1):
        d += timedelta(days=r.choice([2, 2, 3, 3, 4]))
        pain = max(2, pain - (1 if r.random() < .3 else 0))
        rom = ", ".join(f"{m} {r.randint(25, 70)} deg" for x in R for m in x["rom"][:2])
        lines = (section("Subjective", f"Patient reports pain {pain}/10 today. "
                         + b.pick(["Slept better this week.", "Pain worse after work.", "Doing home exercises daily.",
                                   "Tolerated last session well.", "Stiffness in the morning."]))
                 + section("Objective", f"Visit {v} of plan of care. ROM: {rom}.")
                 + section("Treatment", "97110 therapeutic exercise 30 min; 97140 manual therapy 15 min; 97014 electrical stimulation 15 min.")
                 + section("Assessment", "Slow progress toward goals; continues to benefit from skilled therapy.")
                 + [f"Electronically signed by {pt} on {fmt(d)}"])
        vd = b.doc(prov["pt"], "Physical Therapy Daily Note", d, "clinical", lines, (f"Date of service: {fmt(d)}   Therapist: {pt}",))
        b.event(d, prov["pt"], "pt_visit", f"Physical therapy visit {v}; pain {pain}/10.", [], [("97110", ""), ("97140", ""), ("97014", "")], vd)
        if v % 8 == 0 and v < n_visits:
            lines = (section("Progress summary", f"Re-evaluation after {v} visits. Pain decreased to {pain}/10. "
                             + b.pick(["Partial improvement in function.", "Plateau in range of motion.", "Improving tolerance to sitting."]))
                     + section("Objective", f"ROM: {rom}.")
                     + section("Plan", "Continue skilled physical therapy 2-3 times weekly for 4 more weeks.")
                     + [f"Electronically signed by {pt} on {fmt(d)}", ""] + questionnaire(r, regions, pain / 10))
            rd = b.doc(prov["pt"], "Physical Therapy Re-evaluation", d, "clinical", lines, (f"Date of service: {fmt(d)}   Therapist: {pt}",))
            b.event(d, prov["pt"], "pt_reeval", f"Physical therapy re-evaluation after {v} visits; pain {pain}/10; plan to continue.",
                    [], [("97164", "")], rd)
            billing["pt"].append((fmt(d), "97164", "PT re-evaluation", 150.00))
        billing["pt"] += [(fmt(d), "97110", "Therapeutic exercise, each 15 min", 95.00 * 2),
                          (fmt(d), "97140", "Manual therapy, each 15 min", 90.00), (fmt(d), "97014", "Electrical stimulation, unattended", 45.00)]

    # --- Ortho follow-up after MRI, then injection or surgery ---
    d4 = d3 + timedelta(days=r.randint(5, 14))
    plan = []
    if any("esi" in x for x in R):
        plan.append("Referred to pain management for epidural steroid injection.")
    if "knee" in regions:
        plan.append("Recommended right knee arthroscopy with partial medial meniscectomy; risks and benefits discussed.")
    lines = (section("Interval history", f"Returns to review MRI. Attending physical therapy. Pain {r.randint(5, 7)}/10.")
             + section("MRI review", " ".join(f"{k}: {v}." for k, v in findings.items()))
             + section("Assessment", "; ".join(f"{x['disc'][0]} {x['disc'][1]}" for x in R)
                       + ". Injuries are causally related to the motor vehicle collision of " + fmt(acc) + ".")
             + section("Plan", " ".join(plan) or "Continue physical therapy.")
             + [f"Electronically signed by {ortho} on {fmt(d4)}", ""] + questionnaire(r, regions, .55))
    od2 = b.doc(prov["ortho"], "Orthopaedic Follow-up Note", d4, "clinical", lines, (f"Date of service: {fmt(d4)}   Physician: {ortho}",))
    b.event(d4, prov["ortho"], "office_visit", "Orthopaedic follow-up reviewing MRI; injuries stated as causally related to the "
            "collision. " + " ".join(plan), [x["disc"] for x in R], [("99214", "")], od2)
    billing["ortho"].append((fmt(d4), "99214", "Office visit, established patient, moderate", 260.00))

    spine = [x for x in R if "esi" in x]
    if spine:
        x = spine[0]
        pm = b.clinician("MD")
        d5 = d4 + timedelta(days=r.randint(10, 30))
        lvl = findings[x["label"]].split(" at ")[-1].split(" ")[0]
        lines = (section("Procedure", x["esi"][1] + f" at {lvl}."))
        lines += (section("Indication", f"{x['disc'][0]} {x['disc'][1]} with radicular pain refractory to physical therapy.")
                  + section("Medications", "Dexamethasone 10 mg and 2 mL preservative-free normal saline; lidocaine 1% for skin.")
                  + section("Complications", "None. Patient tolerated the procedure well. Pre-procedure pain 7/10, post-procedure 3/10.")
                  + [f"Electronically signed by {pm} on {fmt(d5)}"])
        ij = b.doc(prov["pain"], "Procedure Note", d5, "clinical", lines, (f"Date of service: {fmt(d5)}   Physician: {pm}",))
        b.event(d5, prov["pain"], "injection", f"{x['esi'][1]} at {lvl}; pain 7/10 before, 3/10 after.",
                [x["disc"]], [x["esi"]], ij)
        billing["pain"].append((fmt(d5), x["esi"][0], x["esi"][1], float(r.randint(2200, 3800))))
    if "knee" in regions:
        x = REGIONS["knee"]
        surg = b.clinician("MD")
        d6 = d4 + timedelta(days=r.randint(20, 45))
        lines = (section("Preoperative diagnosis", f"{x['disc'][0]} {x['disc'][1]}")
                 + section("Procedure", x["surgery"][1] + ", right knee.")
                 + section("Anesthesia", "General.")
                 + section("Findings", "Complex tear of the posterior horn of the medial meniscus; ACL intact with mild laxity.")
                 + section("Disposition", "Discharged home the same day. Weight bearing as tolerated with crutches.")
                 + [f"Electronically signed by {surg} on {fmt(d6)}"])
        sd = b.doc(prov["asc"], "Operative Report", d6, "clinical", lines, (f"Date of surgery: {fmt(d6)}   Surgeon: {surg}",))
        b.event(d6, prov["asc"], "surgery", "Right knee arthroscopy with partial medial meniscectomy.",
                [x["disc"]], [x["surgery"]], sd)
        billing["asc"].append((fmt(d6), x["surgery"][0], x["surgery"][1], float(r.randint(9000, 16000))))

    # --- Itemized bills, one per provider (billing pages are their own documents) ---
    for k, rows in billing.items():
        if rows:
            stmt = acc + timedelta(days=200)
            b.doc(prov[k], "Itemized Statement of Charges", stmt, "billing", charges_lines(rows),
                  (f"Statement date: {fmt(stmt)}",))

    # One claim form page per billed service (identical layout, different line).
    for k, rows in billing.items():
        if not rows:
            continue
        insured = f"NF-{r.randint(10**7, 10**8 - 1)}"
        dx = sorted({c for e in b.events if e.provider == prov[k]["name"] for c in e.codes})[:4] or ["M54.2"]
        pages = []
        for d_s, code, desc, amt in rows:
            dt = date(int(d_s[6:]), int(d_s[:2]), int(d_s[3:5]))
            pages.append([prov[k]["name"].upper(), "CLAIM FORM", "-" * WIDTH, ""]
                         + claim_form(prov[k], b.patient, dt, code, desc, amt, dx, insured))
        b._doc_n += 1
        b.documents.append(Document(f"d{b._doc_n:03d}", prov[k]["name"], "Claim Forms", rows[0][0], "billing", pages))
    # The law firm's HIPAA authorization: one document, which every provider returns a copy of.
    firm = "Marlowe & Castell, LLP"
    lines = ["AUTHORIZATION FOR RELEASE OF PROTECTED HEALTH INFORMATION", "(HIPAA compliant, 45 CFR 164.508)", "",
             f"Patient name: {b.patient['first']} {b.patient['last']}      Date of birth: {fmt(b.patient['dob'])}", "",
             "I authorize any hospital, physician, therapist, imaging center or other health care provider to release",
             f"to {firm}, 200 Court Street, Brooklyn, NY 11201, my complete medical records, including office notes,",
             "imaging reports and films, therapy records, and itemized billing, for the period from "
             f"{fmt(acc - timedelta(days=730))} to the present.", "",
             "Purpose: at the request of the individual, in connection with a personal injury claim.",
             f"This authorization expires on {fmt(acc + timedelta(days=1095))}. I may revoke it in writing at any time.",
             "A photocopy or fax of this authorization is as valid as the original.", "",
             f"Signature of patient: ______________________      Date: {fmt(acc + timedelta(days=r.randint(20, 40)))}"]
    b._doc_n += 1
    b.documents.append(Document(f"d{b._doc_n:03d}", firm, "HIPAA Authorization", fmt(acc), "admin", [lines]))

    b.events.sort(key=lambda e: (e.date[6:] + e.date[:5], e.event_id))
    return Case(case_id or f"case{seed}", {"first": b.patient["first"], "last": b.patient["last"], "dob": fmt(b.patient["dob"])},
                fmt(acc), regions, b.events, b.documents)
