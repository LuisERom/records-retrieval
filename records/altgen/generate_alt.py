#!/usr/bin/env python3
"""altgen: an independent synthetic personal-injury case-file generator.

Writes records/data/alt/alt-<n>/records.pdf and truth.json for 12 fictional
cases.  Everything (patients, clinicians, providers, firms, payers) is invented.
Deterministic: every random choice comes from a per-case random.Random seed.
See README.md in this folder for the model.
"""
import datetime as dt
import json
import random
import textwrap
from pathlib import Path

import fitz  # pymupdf

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "alt"
BASE_SEED = 7340
N_CASES = 12
W, H = 612, 792

MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
MONTHS = ("January February March April May June July August September "
          "October November December").split()


def fdate(d, f):
    if f == "us":
        return f"{d.month:02d}/{d.day:02d}/{d.year}"
    if f == "iso":
        return d.isoformat()
    if f == "long":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    if f == "dmy":
        return f"{d.day:02d}-{MON[d.month - 1]}-{d.year}"
    if f == "us2":
        return f"{d.month}/{d.day}/{d.year % 100:02d}"
    raise ValueError(f)


def tdate(d):
    return fdate(d, "us")


def plus(d, n):
    return d + dt.timedelta(days=n)


def wkday(d):
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


# --------------------------------------------------------------------------
# Vocabulary (all invented)
# --------------------------------------------------------------------------
FIRST_F = ["Marisol", "Priya", "Ingrid", "Wren", "Odalys", "Simone", "Yolanda",
           "Beatriz", "Lorna", "Noemi", "Esperanza", "Ilse", "Tamsin", "Corinne"]
FIRST_M = ["Dennis", "Tobias", "Rafael", "Callum", "Desmond", "Anselm", "Kofi",
           "Mateo", "Hollis", "Grady", "Thaddeus", "Jovan", "Emeric", "Lazlo"]
LAST = ["Quintero", "Abernethy", "Okafor", "Lindqvist", "Varga", "Pellerin",
        "Haskett", "Moravec", "Tolliver", "Strand", "Delahunt", "Brennick",
        "Szabo", "Ruelas", "Fairweather", "Ostrowski", "Nwosu", "Castellanos",
        "Kettering", "Duvall", "Iwasaki", "Thorvald", "Galloway", "Penhallow",
        "Rourke", "Valdane", "Ashgrove", "Kalinowski", "Bettencourt", "Lacombe",
        "Esterly", "Merrivale", "Oyelaran", "Brisbois", "Haldane", "Truax"]
CLIN_FIRST = ["Adaeze", "Bernard", "Celia", "Dmitri", "Elspeth", "Farid", "Gwen",
              "Hector", "Imani", "Jules", "Katarina", "Lionel", "Mireille",
              "Nikhil", "Orla", "Pascal", "Rosalind", "Stellan", "Teodora", "Umar",
              "Vivienne", "Warrick", "Xenia", "Yusuf", "Zelda", "Anouk", "Bram"]
PLACES = ["Cedar Hollow", "Brightwater", "Larkspur", "Quarry Ridge", "Tamsin Creek",
          "Wexford Pines", "Alder Point", "Saltmarsh", "Juniper Flats", "Copperleaf",
          "Halvorsen", "Pellham Bay", "Marrow Lake", "Fennimore", "Oriel Valley",
          "Kestrel Hill", "Bramblewood", "Thistledown", "Gilliam Fork", "Rookwood",
          "Corvid Bend", "Sablewater", "Hollin Gate", "Ember Ridge", "Lantern Cove",
          "Ashby Mill", "Dunmore Flats", "Pinecrest Ferry", "Calder Reach", "Vesper Glen"]
CITIES = [("Port Calder", "OR"), ("Lowell Springs", "NM"), ("East Harrow", "OH"),
          ("New Tamsin", "PA"), ("Bricklin", "GA"), ("Sorrel City", "MO")]
STREETS = ["Industry Pkwy", "N. Larch St", "Medical Plaza Dr", "Old Mill Rd",
           "Harbor Blvd", "Orchard Ave", "Station Sq", "Commerce Way", "Willet Ln"]
FIRMS = ["Abernathy Kole & Strand, PLLC", "Delacroix Venn Injury Law Group",
         "Teague Marchetti & Associates", "Oduya Brandt Trial Lawyers"]
DEFENSE = ["Holloway Pryce Defense LLP", "Garamond & Sills, P.C.",
           "Wickham Ostrander LLP"]
HEALTH_PLANS = ["Northvale Health Plan", "Bluefen Mutual Health",
                "Corriedale Care Network"]

ROLE = {
    "er": dict(suffix=["Regional Medical Center", "Community Hospital", "General Hospital"],
               cred=["MD", "DO"], dept="EMERGENCY DEPARTMENT", pos="23"),
    "urgent": dict(suffix=["Urgent Care", "Walk-In Clinic", "Immediate Care"],
                   cred=["PA-C", "MD", "FNP-C"], dept="URGENT CARE", pos="20"),
    "pcp": dict(suffix=["Family Medicine", "Primary Care Associates",
                        "Internal Medicine Group", "Family Health Center"],
                cred=["MD", "DO", "NP"], dept="", pos="11"),
    "imaging": dict(suffix=["Imaging Center", "Diagnostic Imaging", "Open MRI & Radiology"],
                    cred=["MD"], dept="RADIOLOGY", pos="22"),
    "lab": dict(suffix=["Clinical Laboratories", "Reference Laboratory"],
                cred=["MD"], dept="LABORATORY", pos="81"),
    "ortho": dict(suffix=["Orthopaedic Associates", "Bone & Joint Clinic",
                          "Orthopedic & Sports Medicine"], cred=["MD"], dept="", pos="11"),
    "hand": dict(suffix=["Hand & Upper Extremity Center", "Hand Surgery Specialists"],
                 cred=["MD"], dept="", pos="11"),
    "spine": dict(suffix=["Spine & Rehabilitation Medicine", "Physiatry & Spine Center"],
                  cred=["MD", "DO"], dept="", pos="11"),
    "neuro": dict(suffix=["Neurology Consultants", "Neurological Associates"],
                  cred=["MD"], dept="", pos="11"),
    "pain": dict(suffix=["Pain Management", "Interventional Pain & Spine"],
                 cred=["MD"], dept="", pos="11"),
    "pt": dict(suffix=["Physical Therapy", "Rehab & Sports Therapy",
                       "Physical Therapy & Wellness"], cred=["PT, DPT"], dept="", pos="11"),
    "ot": dict(suffix=["Hand Therapy & OT", "Occupational Therapy Services"],
               cred=["OTR/L, CHT"], dept="", pos="11"),
    "chiro": dict(suffix=["Chiropractic", "Chiropractic & Wellness"], cred=["DC"],
                  dept="", pos="11"),
    "asc": dict(suffix=["Surgery Center", "Ambulatory Surgical Center",
                        "Outpatient Surgery Center"], cred=["MD"], dept="", pos="24"),
}
THERAPY_ROLES = ("pt", "ot", "chiro")

FEES = {
    "99203": (190, "Office/outpt visit new, low MDM"),
    "99204": (285, "Office/outpt visit new, moderate MDM"),
    "99213": (135, "Office/outpt visit est, low MDM"),
    "99214": (195, "Office/outpt visit est, moderate MDM"),
    "99024": (0, "Postoperative follow-up visit (global)"),
    "99396": (260, "Periodic preventive visit est, 40-64"),
    "99395": (240, "Periodic preventive visit est, 18-39"),
    "99284": (780, "ED visit, moderate MDM"),
    "99285": (1150, "ED visit, high MDM"),
    "73110": (165, "X-ray wrist, minimum 3 views"),
    "73200": (690, "CT upper extremity w/o contrast"),
    "73130": (150, "X-ray hand, minimum 3 views"),
    "73218": (1390, "MRI upper extremity non-joint w/o contrast"),
    "73030": (140, "X-ray shoulder, minimum 2 views"),
    "73221": (1450, "MRI upper extremity joint w/o contrast"),
    "73562": (155, "X-ray knee, 3 views"),
    "73721": (1480, "MRI lower extremity joint w/o contrast"),
    "72100": (150, "X-ray lumbosacral spine, 2-3 views"),
    "72148": (1620, "MRI lumbar spine w/o contrast"),
    "70450": (980, "CT head/brain w/o contrast"),
    "72125": (1050, "CT cervical spine w/o contrast"),
    "70551": (1700, "MRI brain w/o contrast"),
    "29125": (140, "Application short arm splint, static"),
    "25607": (3900, "ORIF distal radius, extra-articular"),
    "64483": (1350, "Transforaminal epidural, lumbar/sacral, 1 level"),
    "63030": (4800, "Laminotomy w/ discectomy, lumbar, 1 interspace"),
    "20611": (310, "Arthrocentesis/inj major joint w/ US guidance"),
    "29827": (5200, "Arthroscopy shoulder, rotator cuff repair"),
    "29826": (1450, "Arthroscopy shoulder, decompression (add-on)"),
    "29888": (5600, "Arthroscopically aided ACL reconstruction"),
    "29881": (2900, "Arthroscopy knee, meniscectomy medial OR lateral"),
    "26410": (1850, "Repair extensor tendon, hand, w/o graft"),
    "11042": (420, "Debridement subcutaneous tissue, first 20 sq cm"),
    "12032": (390, "Intermediate repair, extremities 2.6-7.5 cm"),
    "90715": (85, "Tdap vaccine, 7 yrs+, IM"),
    "90471": (30, "Immunization administration, 1 vaccine"),
    "90675": (410, "Rabies vaccine, IM"),
    "90375": (1900, "Rabies immune globulin, human"),
    "85025": (38, "CBC w/ automated differential"),
    "80053": (52, "Comprehensive metabolic panel"),
    "80061": (58, "Lipid panel"),
    "80048": (40, "Basic metabolic panel"),
    "86140": (30, "C-reactive protein"),
    "87070": (75, "Culture, bacterial, aerobic, any source"),
    "83036": (45, "Hemoglobin A1c"),
    "36415": (15, "Routine venipuncture"),
    "97161": (195, "PT evaluation, low complexity"),
    "97162": (215, "PT evaluation, moderate complexity"),
    "97164": (130, "PT re-evaluation"),
    "97165": (195, "OT evaluation, low complexity"),
    "97166": (215, "OT evaluation, moderate complexity"),
    "97168": (130, "OT re-evaluation"),
    "97110": (65, "Therapeutic exercise, ea 15 min"),
    "97112": (70, "Neuromuscular reeducation, ea 15 min"),
    "97140": (62, "Manual therapy techniques, ea 15 min"),
    "97530": (72, "Therapeutic activities, ea 15 min"),
    "97014": (28, "Electrical stimulation, unattended"),
    "97012": (40, "Mechanical traction"),
    "98940": (70, "Chiropractic manipulative tx, 1-2 regions"),
    "98941": (85, "Chiropractic manipulative tx, 3-4 regions"),
    "64405": (420, "Injection, anesthetic, greater occipital nerve"),
}

ICD = {
    "S52.531A": "Colles' fracture of right radius, init enc closed fx",
    "S52.531D": "Colles' fracture of right radius, subs enc routine healing",
    "W01.0XXA": "Fall same level from slipping/tripping w/o striking object, init",
    "M25.631": "Stiffness of right wrist, NEC",
    "S39.012A": "Strain of muscle, fascia and tendon of lower back, init",
    "S39.012D": "Strain of muscle, fascia and tendon of lower back, subs",
    "M54.50": "Low back pain, unspecified",
    "M51.26": "Other intervertebral disc displacement, lumbar region",
    "M54.16": "Radiculopathy, lumbar region",
    "X50.0XXA": "Overexertion from strenuous movement or load, init",
    "Y99.0": "Civilian activity done for income or pay",
    "W54.0XXA": "Bitten by dog, initial encounter",
    "S61.451A": "Open bite of right hand, initial encounter",
    "S61.451D": "Open bite of right hand, subsequent encounter",
    "S51.851A": "Open bite of right forearm, initial encounter",
    "L03.113": "Cellulitis of right upper limb",
    "S66.320A": "Laceration of extensor tendon of right index finger at wrist/hand level, init",
    "Z23": "Encounter for immunization",
    "Z20.3": "Contact with and (suspected) exposure to rabies",
    "S06.0X1A": "Concussion w/ LOC of 30 minutes or less, init",
    "S06.0X1D": "Concussion w/ LOC of 30 minutes or less, subs",
    "S13.4XXA": "Sprain of ligaments of cervical spine, init",
    "S13.4XXD": "Sprain of ligaments of cervical spine, subs",
    "V43.52XA": "Car driver injured in collision w/ other type car in traffic accident, init",
    "F07.81": "Postconcussional syndrome",
    "G44.309": "Post-traumatic headache, unspecified, not intractable",
    "S46.011A": "Strain of rotator cuff muscle/tendon, right shoulder, init",
    "S46.011D": "Strain of rotator cuff muscle/tendon, right shoulder, subs",
    "W10.8XXA": "Fall (on) (from) other stairs and steps, init",
    "M75.41": "Impingement syndrome of right shoulder",
    "S83.512A": "Sprain of anterior cruciate ligament of left knee, init",
    "S83.512D": "Sprain of anterior cruciate ligament of left knee, subs",
    "S83.242A": "Other tear of medial meniscus, current injury, left knee, init",
    "S83.242D": "Other tear of medial meniscus, current injury, left knee, subs",
    "W00.0XXA": "Fall on same level due to ice and snow, init",
    "Z00.00": "General adult medical exam w/o abnormal findings",
    "I10": "Essential (primary) hypertension",
    "E78.5": "Hyperlipidemia, unspecified",
    "J06.9": "Acute upper respiratory infection, unspecified",
    "K21.9": "Gastro-esophageal reflux disease w/o esophagitis",
}

QUEST = {
    "QuickDASH": dict(items=["Open a tight or new jar", "Do heavy household chores",
                             "Carry a shopping bag or briefcase", "Wash your back",
                             "Use a knife to cut food", "Recreational activities with force",
                             "Interference with social activities", "Limited in work/daily activities",
                             "Arm, shoulder or hand pain", "Tingling (pins and needles)",
                             "Difficulty sleeping because of pain"], lo=1, hi=5, bad_high=True),
    "Oswestry": dict(items=["Pain intensity", "Personal care", "Lifting", "Walking", "Sitting",
                            "Standing", "Sleeping", "Sex life", "Social life", "Traveling"],
                     lo=0, hi=5, bad_high=True),
    "NDI": dict(items=["Pain intensity", "Personal care", "Lifting", "Reading", "Headaches",
                       "Concentration", "Work", "Driving", "Sleeping", "Recreation"],
                lo=0, hi=5, bad_high=True),
    "SPADI": dict(items=["Pain at its worst", "Pain lying on involved side",
                         "Pain reaching a high shelf", "Pain touching back of neck",
                         "Pain pushing with involved arm", "Washing your hair", "Washing your back",
                         "Putting on undershirt", "Putting on shirt that buttons in front",
                         "Putting on pants", "Placing object on high shelf",
                         "Carrying heavy object (10 lb)", "Removing something from back pocket"],
                  lo=0, hi=10, bad_high=True),
    "LEFS": dict(items=["Usual work/housework", "Usual hobbies", "Getting into/out of bath",
                        "Walking between rooms", "Putting on shoes/socks", "Squatting",
                        "Lifting a bag of groceries", "Light activities around home",
                        "Heavy activities around home", "Getting into/out of a car",
                        "Walking 2 blocks", "Walking a mile", "Up/down 10 stairs",
                        "Standing for 1 hour", "Sitting for 1 hour", "Running on even ground",
                        "Running on uneven ground", "Making sharp turns while running",
                        "Hopping", "Rolling over in bed"], lo=0, hi=4, bad_high=False),
}

# --------------------------------------------------------------------------
# Case types
# --------------------------------------------------------------------------
TYPES = {
    "wrist": dict(
        label="slip-and-fall in a grocery store; right distal radius fracture treated with ORIF",
        roles=[["urgent", "pcp", "lab", "imaging", "hand", "asc", "ot"],
               ["er", "pcp", "hand", "asc", "pt", "imaging"]],
        mech="slipping on spilled liquid in the produce aisle of a grocery store and "
             "falling onto {his} outstretched right hand",
        regions=["right wrist", "right forearm"],
        acute=["S52.531A", "W01.0XXA"], mid=["S52.531D"], late=["S52.531D", "M25.631"],
        complaint="right wrist pain, swelling and deformity",
        exam="Dorsal angulation (dinner-fork) of the right distal forearm with moderate swelling "
             "and ecchymosis. Point tenderness over the distal radius. Radial pulse 2+, capillary "
             "refill under 2 seconds. Sensation intact in median, ulnar and radial distributions. "
             "Unable to make a full fist because of pain.",
        er_tx="Hematoma block with 1% lidocaine, closed reduction, sugar-tong splint applied; "
              "post-reduction films obtained.",
        er_cpt={"er": ["99284", "29125"], "urgent": ["99204", "29125"]},
        er_img=[("XR RIGHT WRIST, 3 VIEWS", "73110",
                 "Extra-articular fracture of the distal radial metaphysis about 2 cm proximal to "
                 "the articular surface with 15 degrees of dorsal angulation and 3 mm of radial "
                 "shortening. Ulnar styloid intact. Carpus aligned.",
                 "Displaced extra-articular distal radius fracture (Colles type).")],
        adv_img=[("CT RIGHT WRIST WITHOUT CONTRAST", "73200",
                  "Comminuted extra-articular distal radius fracture with dorsal cortical "
                  "comminution and 18 degrees of dorsal tilt. No intra-articular step-off. "
                  "Scaphoid and lunate intact.",
                  "Loss of reduction of comminuted extra-articular distal radius fracture; "
                  "no articular involvement.")],
        spec="hand", early_surgery=True,
        surgery=dict(name="Open reduction and internal fixation, right distal radius, volar "
                          "locking plate", cpts=["25607"], dx=["S52.531A"],
                     findings="Dorsally comminuted extra-articular distal radius fracture with "
                              "loss of closed reduction.",
                     technique="A modified Henry approach was made over the FCR sheath. The "
                               "pronator quadratus was elevated. The fracture was reduced under "
                               "fluoroscopy and held with K-wires. A volar locking plate was "
                               "applied with three cortical shaft screws and six distal locking "
                               "screws. Final images showed restored volar tilt and radial "
                               "height. The pronator was repaired and the skin closed.",
                     anes="General anesthesia with supraclavicular block", ebl="15 mL"),
        injection=None,
        ther={"ot": ("97165", "97168", ["97110", "97140", "97530"]),
              "pt": ("97162", "97164", ["97110", "97140", "97530"])},
        quest="QuickDASH",
        measures=[("Wrist extension AROM", 15, 60, "deg"), ("Wrist flexion AROM", 20, 65, "deg"),
                  ("Grip strength R", 12, 55, "lb")],
        exercises=["Tendon glides", "Wrist AROM flex/ext", "Putty squeeze, soft",
                   "Pronation/supination with hammer", "Wrist curls 1 lb", "Retrograde massage",
                   "Scar massage", "Pegboard fine motor"],
        prior=dict(reason="annual preventive examination", codes=["Z00.00"], cpts=["99396"],
                   note="No musculoskeletal complaints. Full painless range of motion of both "
                        "wrists and hands. Grip symmetric."),
    ),
    "back": dict(
        label="workplace lifting injury; lumbar strain progressing to L4-5 disc extrusion with radiculopathy",
        roles=[["urgent", "pcp", "lab", "imaging", "spine", "pain", "chiro"],
               ["urgent", "pcp", "imaging", "spine", "pt", "asc", "pain"]],
        mech="lifting a 60-pound case of brake rotors from a floor-level pallet at {his} "
             "warehouse job and feeling a sudden pop in {his} low back",
        regions=["lumbar spine", "left lower extremity"],
        acute=["S39.012A", "M54.50", "X50.0XXA", "Y99.0"], mid=["M51.26", "M54.16"],
        late=["M51.26", "M54.16"],
        complaint="low back pain radiating into the left buttock",
        exam="Paraspinal spasm L3-S1, worse on the left. Lumbar flexion limited to 30 degrees "
             "with pain. Straight leg raise positive on the left at 40 degrees. Strength 5/5 "
             "except left EHL 4+/5. Reflexes 2+ and symmetric. Gait antalgic.",
        er_tx="Ketorolac 30 mg IM, cyclobenzaprine prescription, light duty note.",
        er_cpt={"er": ["99284"], "urgent": ["99204"]},
        er_img=[("XR LUMBAR SPINE, 2-3 VIEWS", "72100",
                 "Five non-rib-bearing lumbar vertebrae. Mild disc space narrowing at L4-5. "
                 "No fracture or spondylolisthesis. SI joints unremarkable.",
                 "No acute osseous abnormality. Mild L4-5 degenerative disc narrowing.")],
        adv_img=[("MRI LUMBAR SPINE WITHOUT CONTRAST", "72148",
                  "L4-5: broad-based disc bulge with superimposed left paracentral extrusion "
                  "measuring 7 mm, contacting the traversing left L5 nerve root in the lateral "
                  "recess; mild left foraminal narrowing. L5-S1: mild facet arthropathy without "
                  "stenosis. Conus terminates at L1.",
                  "Left paracentral L4-5 disc extrusion contacting the traversing left L5 root.")],
        spec="spine", early_surgery=False,
        surgery=dict(name="Left L4-5 laminotomy and microdiscectomy", cpts=["63030"],
                     dx=["M51.26", "M54.16"],
                     findings="Large sequestered fragment beneath the left L5 root.",
                     technique="Through a 2.5 cm paramedian incision a tubular retractor was "
                               "docked on the left L4-5 interlaminar space. A partial "
                               "hemilaminotomy and medial facetectomy were performed. The L5 "
                               "root was retracted medially and the extruded fragment removed. "
                               "The root was free and pulsatile at the end of the case.",
                     anes="General endotracheal anesthesia", ebl="25 mL"),
        surgery_variants=[1],
        injection=dict(name="Left L4-5 transforaminal epidural steroid injection, fluoroscopic "
                            "guidance", cpts=["64483"], dx=["M51.26", "M54.16"],
                       technique="Prone, sterile prep. 22-gauge spinal needle advanced to the "
                                 "left L4-5 foramen under fluoroscopy. Contrast confirmed "
                                 "epidural spread without vascular uptake. Injected triamcinolone "
                                 "40 mg with 1 mL 0.25% bupivacaine.", count=2),
        ther={"chiro": ("99203", "99213", ["98941", "97140", "97012", "97014"]),
              "pt": ("97162", "97164", ["97110", "97112", "97140"])},
        quest="Oswestry",
        measures=[("Lumbar flexion", 30, 70, "deg"), ("SLR left", 40, 75, "deg"),
                  ("Sitting tolerance", 10, 60, "min")],
        exercises=["Prone press-ups", "Pelvic tilts", "Bird-dog", "Bridges", "Nerve glides L LE",
                   "Walking program", "Cat-camel", "Side plank, modified"],
        prior=dict(reason="intermittent low back stiffness after yard work; blood pressure check",
                   codes=["M54.50", "I10"], cpts=["99213"],
                   note="Mild paraspinal tightness. Straight leg raise negative bilaterally. No "
                        "radicular symptoms. Advised home stretching program."),
    ),
    "dogbite": dict(
        label="dog bite to right hand and forearm; cellulitis and extensor tendon repair",
        roles=[["er", "pcp", "hand", "asc", "ot", "lab"],
               ["urgent", "pcp", "hand", "asc", "ot", "imaging", "lab"]],
        mech="being bitten on the right hand and forearm by a neighbor's unleashed dog while "
             "walking on a public sidewalk",
        regions=["right hand", "right forearm"],
        acute=["S61.451A", "S51.851A", "W54.0XXA", "Z23"], mid=["L03.113", "S61.451D"],
        late=["S66.320A", "S61.451D"],
        complaint="dog bite wounds to the right hand and forearm",
        exam="Four puncture wounds over the dorsal right hand, the largest 1.2 cm over the "
             "second metacarpal, and a 4 cm ragged laceration of the volar forearm. Mild "
             "surrounding erythema. Full flexion; extension of the index finger weak against "
             "resistance. Neurovascularly intact distally.",
        er_tx="Copious irrigation, loose approximation of forearm laceration, Tdap and rabies "
              "post-exposure prophylaxis started, amoxicillin-clavulanate prescribed.",
        er_cpt={"er": ["99284", "12032", "90715", "90471", "90675", "90375"],
                "urgent": ["99204", "12032", "90715", "90471"]},
        er_img=[("XR RIGHT HAND, 3 VIEWS", "73130",
                 "No radiopaque foreign body. No fracture. Soft tissue swelling and small "
                 "locules of gas along the dorsal hand consistent with puncture wounds.",
                 "Soft tissue injury without fracture or retained foreign body.")],
        adv_img=[("MRI RIGHT HAND WITHOUT CONTRAST", "73218",
                  "Partial-thickness tear of the extensor digitorum tendon to the index finger "
                  "at the level of the second metacarpal with surrounding tenosynovitis. No "
                  "drainable abscess. No osteomyelitis.",
                  "Index finger extensor tendon tear with tenosynovitis; no abscess.")],
        spec="hand", early_surgery=True,
        surgery=dict(name="Irrigation and debridement of right dorsal hand wound with repair of "
                          "extensor tendon, right index finger", cpts=["26410", "11042"],
                     dx=["S66.320A", "L03.113"],
                     findings="Necrotic subcutaneous tissue over the second metacarpal; 60 "
                              "percent laceration of the index extensor digitorum tendon.",
                     technique="The puncture wound was excised and extended longitudinally. "
                               "Necrotic subcutaneous tissue was sharply debrided. Cultures "
                               "were sent. The wound was irrigated with 3 L saline. The tendon "
                               "was repaired with a 4-0 running horizontal mattress suture. "
                               "The skin was loosely closed over a drain.",
                     anes="Monitored anesthesia care with wrist block", ebl="minimal"),
        injection=None,
        ther={"ot": ("97165", "97168", ["97110", "97140", "97530"])},
        quest="QuickDASH",
        measures=[("Index MCP flexion", 30, 85, "deg"), ("Grip strength R", 15, 60, "lb"),
                  ("Index extensor lag", 25, 5, "deg")],
        exercises=["Relative motion orthosis check", "Place-and-hold extension", "Scar massage",
                   "Edema glove", "Composite fist", "Desensitization textures",
                   "Putty pinch", "Isolated EDC glides"],
        prior=dict(reason="cough and congestion for five days", codes=["J06.9"], cpts=["99213"],
                   note="Lungs clear. Supportive care. Upper extremities unremarkable."),
        rabies=True,
    ),
    "mva": dict(
        label="rear-end motor vehicle collision; concussion with post-concussive syndrome and cervical sprain",
        roles=[["er", "pcp", "imaging", "neuro", "pt", "pain"],
               ["er", "pcp", "imaging", "neuro", "chiro", "pain", "lab"]],
        mech="a rear-end collision in which {his} stopped sedan was struck from behind at an "
             "estimated 35 mph; {he} was the restrained driver, struck the left side of {his} "
             "head on the window frame and had a brief loss of consciousness",
        regions=["head", "cervical spine"],
        acute=["S06.0X1A", "S13.4XXA", "V43.52XA"], mid=["F07.81", "G44.309", "S13.4XXD"],
        late=["F07.81", "G44.309"],
        complaint="headache, neck pain and dizziness",
        exam="GCS 15. Mild tenderness left parietal scalp without hematoma. Pupils equal and "
             "reactive. No focal deficit. Posterior cervical midline tenderness absent; bilateral "
             "paraspinal and trapezius tenderness. Cervical rotation limited by pain. Tandem gait "
             "mildly unsteady.",
        er_tx="Acetaminophen 1 g PO, ondansetron 4 mg ODT, concussion precautions reviewed.",
        er_cpt={"er": ["99285"], "urgent": ["99204"]},
        er_img=[("CT HEAD WITHOUT CONTRAST", "70450",
                 "No intracranial hemorrhage, mass effect or midline shift. Ventricles normal "
                 "in size. Mild left parietal scalp soft tissue swelling. Calvarium intact.",
                 "No acute intracranial abnormality."),
                ("CT CERVICAL SPINE WITHOUT CONTRAST", "72125",
                 "Normal alignment. No fracture. Prevertebral soft tissues normal. Mild C5-6 "
                 "uncovertebral hypertrophy.", "No acute fracture or malalignment.")],
        adv_img=[("MRI BRAIN WITHOUT CONTRAST", "70551",
                  "No acute infarct or hemorrhage. No microhemorrhage on susceptibility-weighted "
                  "imaging. Two nonspecific punctate T2/FLAIR hyperintensities in the left "
                  "frontal white matter.", "No acute intracranial abnormality.")],
        spec="neuro", early_surgery=False, surgery=None, surgery_variants=[],
        injection=dict(name="Bilateral greater occipital nerve blocks", cpts=["64405"],
                       dx=["G44.309"],
                       technique="Landmarks identified medial to the occipital artery. 27-gauge "
                                 "needle, 2.5 mL of 0.5% bupivacaine with 10 mg triamcinolone "
                                 "injected on each side after negative aspiration.", count=2),
        ther={"pt": ("97162", "97164", ["97112", "97110", "97140", "97530"]),
              "chiro": ("99203", "99213", ["98940", "97140", "97014"])},
        quest="NDI",
        measures=[("Cervical rotation L", 45, 75, "deg"), ("Cervical rotation R", 40, 75, "deg"),
                  ("Dynamic visual acuity lines lost", 4, 1, "")],
        exercises=["Gaze stabilization VOR x1", "Habituation head turns", "Chin tucks",
                   "Scapular retraction", "Upper trap stretch", "Foam balance eyes closed",
                   "Treadmill with head turns", "Cervical isometrics"],
        prior=dict(reason="hypertension and lipid follow-up", codes=["I10", "E78.5"],
                   cpts=["99214"],
                   note="No headaches. Neck supple, full range of motion. Neurologic exam "
                        "nonfocal."),
    ),
    "shoulder": dict(
        label="fall on exterior stairs; right rotator cuff tear repaired arthroscopically",
        roles=[["urgent", "pcp", "imaging", "ortho", "asc", "pt", "lab"],
               ["er", "pcp", "ortho", "imaging", "asc", "pt", "pain"]],
        mech="falling down four exterior concrete steps at {his} apartment complex when a loose "
             "handrail gave way, landing on {his} outstretched right arm",
        regions=["right shoulder"],
        acute=["S46.011A", "W10.8XXA"], mid=["S46.011A", "M75.41"], late=["S46.011D"],
        complaint="right shoulder pain and weakness lifting the arm",
        exam="Tenderness over the greater tuberosity. Active forward flexion 70 degrees, passive "
             "150 degrees. Positive drop-arm sign. Weak external rotation 3/5. Positive Hawkins "
             "and Neer signs. Distal neurovascular exam intact.",
        er_tx="Sling, ice, naproxen; orthopedic follow-up arranged.",
        er_cpt={"er": ["99284"], "urgent": ["99204"]},
        er_img=[("XR RIGHT SHOULDER, MINIMUM 2 VIEWS", "73030",
                 "No fracture or dislocation. Acromiohumeral interval preserved. Type II "
                 "acromion. Mild AC joint arthrosis.", "No acute osseous injury.")],
        adv_img=[("MRI RIGHT SHOULDER WITHOUT CONTRAST", "73221",
                  "Full-thickness tear of the supraspinatus tendon at the footprint measuring "
                  "1.6 cm AP with 1.2 cm of medial retraction; mild muscle edema without fatty "
                  "atrophy. Subacromial-subdeltoid bursitis. Biceps tendon and labrum intact.",
                  "Acute full-thickness supraspinatus tear with mild retraction.")],
        spec="ortho", early_surgery=False,
        surgery=dict(name="Right shoulder arthroscopy, rotator cuff repair and subacromial "
                          "decompression", cpts=["29827", "29826"], dx=["S46.011A", "M75.41"],
                     findings="Crescent-shaped full-thickness supraspinatus tear, 1.5 cm; "
                              "type II acromion with bursitis.",
                     technique="Beach-chair position. Diagnostic arthroscopy through a posterior "
                               "portal. Subacromial bursectomy and acromioplasty with a burr. "
                               "The footprint was prepared and the tear repaired with two "
                               "medial-row and two lateral-row anchors in a transosseous-"
                               "equivalent construct.",
                     anes="General anesthesia with interscalene block", ebl="minimal"),
        surgery_variants=[0, 1],
        injection=dict(name="Right subacromial corticosteroid injection, ultrasound guidance",
                       cpts=["20611"], dx=["S46.011A", "M75.41"],
                       technique="Ultrasound-guided posterior approach to the subacromial "
                                 "space; 40 mg methylprednisolone with 4 mL 1% lidocaine.",
                       count=1),
        ther={"pt": ("97162", "97164", ["97110", "97140", "97112", "97530"])},
        quest="SPADI",
        measures=[("Shoulder flexion AROM", 60, 160, "deg"), ("Shoulder ER at 0 deg", 10, 55, "deg"),
                  ("ER strength MMT", 2, 4, "/5")],
        exercises=["Pendulums", "Table slides", "Supine wand flexion", "Isometric ER/IR",
                   "Scapular sets", "Theraband ER, yellow", "Rows, red band", "Sidelying ER 1 lb"],
        prior=dict(reason="annual preventive examination", codes=["Z00.00", "K21.9"],
                   cpts=["99396"],
                   note="Shoulders with full symmetric range of motion and strength. No "
                        "impingement signs."),
    ),
    "knee": dict(
        label="slip on ice outside a fitness center; left ACL tear and medial meniscus tear, reconstruction",
        roles=[["er", "pcp", "imaging", "ortho", "asc", "pt"],
               ["urgent", "pcp", "lab", "imaging", "ortho", "asc", "pt", "pain"]],
        mech="slipping on an unsalted, ice-covered walkway outside a fitness center and "
             "twisting {his} left knee with an audible pop",
        regions=["left knee"],
        acute=["S83.512A", "W00.0XXA"], mid=["S83.512A", "S83.242A"],
        late=["S83.512D", "S83.242D"],
        complaint="left knee pain, swelling and giving way",
        exam="Moderate effusion of the left knee. Range of motion 10 to 85 degrees limited by "
             "pain. Lachman 2+ with soft endpoint. Medial joint line tenderness. Valgus stress "
             "stable at 0 and 30 degrees. Distal pulses intact.",
        er_tx="Knee immobilizer, crutches, ibuprofen; orthopedic referral.",
        er_cpt={"er": ["99284"], "urgent": ["99204"]},
        er_img=[("XR LEFT KNEE, 3 VIEWS", "73562",
                 "Moderate joint effusion. No fracture. No avulsion fragment. Joint spaces "
                 "maintained.", "Effusion without fracture.")],
        adv_img=[("MRI LEFT KNEE WITHOUT CONTRAST", "73721",
                  "Complete tear of the anterior cruciate ligament at its femoral attachment "
                  "with bone contusions of the lateral femoral condyle and posterolateral tibial "
                  "plateau. Vertical longitudinal tear of the posterior horn of the medial "
                  "meniscus. MCL and LCL intact.",
                  "Complete ACL tear; posterior horn medial meniscus tear.")],
        spec="ortho", early_surgery=False,
        surgery=dict(name="Left knee arthroscopic ACL reconstruction, BTB autograft, with "
                          "partial medial meniscectomy", cpts=["29888", "29881"],
                     dx=["S83.512A", "S83.242A"],
                     findings="Complete ACL tear; unstable posterior horn medial meniscus tear.",
                     technique="Graft harvested from the central third of the patellar tendon. "
                               "Partial medial meniscectomy to a stable rim. Femoral tunnel "
                               "drilled through the anteromedial portal and tibial tunnel with a "
                               "guide. Graft fixed with interference screws at 20 degrees of "
                               "flexion.",
                     anes="General anesthesia with adductor canal block", ebl="30 mL"),
        surgery_variants=[0, 1],
        injection=None,
        ther={"pt": ("97162", "97164", ["97110", "97140", "97112", "97530"])},
        quest="LEFS",
        measures=[("Knee flexion AROM", 75, 130, "deg"), ("Knee extension", -8, 0, "deg"),
                  ("Quad lag", 10, 0, "deg")],
        exercises=["Quad sets", "Straight leg raise", "Heel slides", "Patellar mobilization",
                   "Mini squats", "Step-ups 6 in", "Stationary bike", "Single-leg balance"],
        prior=dict(reason="annual preventive examination", codes=["Z00.00"], cpts=["99395"],
                   note="Knees without effusion, stable ligament exam, full range of motion."),
    ),
}
TYPE_ORDER = ["wrist", "back", "dogbite", "mva", "shoulder", "knee"]
for _k, _v in TYPES.items():
    _v.setdefault("surgery_variants", [0, 1])


# --------------------------------------------------------------------------
# Row helpers (a page is head rows + blocks + foot row)
# --------------------------------------------------------------------------
def R(t, a="l", b=False, p=False):
    return {"t": t, "a": a, "b": b, "p": p}


def P(t):
    return ("p", t)


def L(t):
    return ("l", t)


def Hd(t):
    return ("h", t)


BL = ("b", "")


def TWO(left, right):
    return ("2", left, right)


def colwrap(lines, width=44):
    out = []
    for x in lines:
        out.extend(textwrap.wrap(x, width) or [""])
    return out


class Prov:
    def __init__(self, role, name, rng, style, city):
        self.role = role
        self.name = name
        self.style = style
        cfg = ROLE[role]
        city_name, st = city
        self.addr = f"{rng.randint(100, 9899)} {rng.choice(STREETS)}, {city_name}, {st} {rng.randint(10000, 99999)}"
        self.phone = f"(555) 01{rng.randint(0, 99):02d}-{rng.randint(1000, 9999)}"[:15]
        self.phone = f"555-01{rng.randint(0, 99):02d}"
        self.fax = f"555-01{rng.randint(0, 99):02d}"
        self.mrn = str(rng.randint(100000, 9999999))
        n = 2 if role in ("er", "imaging", "pcp", "asc", "pt", "chiro", "ot") else 1
        self.clins = []
        for _ in range(n):
            self.clins.append(f"{rng.choice(CLIN_FIRST)} {rng.choice(LAST)}, {rng.choice(cfg['cred'])}")
        self.npi = "9" + "".join(str(rng.randint(0, 9)) for _ in range(9))
        self.tin = f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}"
        self.roi = f"{rng.choice(CLIN_FIRST)} {rng.choice(LAST)}"
        self.nurse = f"{rng.choice(CLIN_FIRST)} {rng.choice(LAST)}, RN"
        self.claim_style = style["v"]


def make_styles(rng, k):
    heads = ["left", "center", "boxed", "banner"]
    fmts = ["us", "iso", "long", "dmy", "us2"]
    labels = ["DOS:", "Visit Date:", "Service Date:", "Encounter on", "Date of Service:"]
    notes = ["soap", "narrative", "table"]
    fonts = ["cour", "helv", "tiro"]
    feet = ["Page {i} of {n}", "Pg {i}/{n}", "- {i} -", "{org} | CONFIDENTIAL | p.{i}"]
    idl = ["MRN", "Acct #", "Chart No.", "Patient ID"]
    for lst in (heads, fmts, labels, notes, fonts, feet, idl):
        rng.shuffle(lst)
    out = []
    for i in range(k):
        font = fonts[i % 3]
        out.append(dict(header=heads[i % 4], date_fmt=fmts[i % 5], dos=labels[i % 5],
                        note=notes[i % 3], font=font,
                        size=rng.choice([9, 9.5, 10]) if font != "cour" else rng.choice([8.5, 9]),
                        wrap=rng.choice([78, 84, 90]) if font == "cour" else rng.choice([92, 100, 108]),
                        foot=feet[i % 4], idl=idl[i % 4], v=i % 3,
                        name_order=rng.choice(["lf", "fl"]), rule=rng.choice([60, 72, 80])))
    return out


class Ctx:
    pass


def pname(C, pv):
    p = C.pat
    return f"{p['last'].upper()}, {p['first'].upper()}" if pv.style["name_order"] == "lf" \
        else f"{p['first']} {p['last']}"


def head_rows(C, pv, title, d, clin, pi, pn):
    st = pv.style
    ds = fdate(d, st["date_fmt"]) if d else ""
    dob = fdate(C.pat["dob_d"], st["date_fmt"])
    nm = pname(C, pv)
    mrn = f"{st['idl']} {pv.mrn}"
    datepart = f"{st['dos']} {ds}"
    if pi > 1:
        return [R(f"{nm}   DOB {dob}   {mrn}   {datepart}   (continued)"), R("")]
    hs = st["header"]
    org = pv.name.upper()
    if ROLE[pv.role]["dept"]:
        org = f"{org} - {ROLE[pv.role]['dept']}"
    if hs in ("left", "center"):
        a = "l" if hs == "left" else "c"
        rows = [R(org, a, True), R(pv.addr, a), R(f"Tel {pv.phone}   Fax {pv.fax}", a), R(""),
                R(title, a, True), R(f"Patient: {nm}    DOB: {dob}    {mrn}"),
                R(f"{datepart}    " + (f"Provider: {clin}" if clin else "")), R("-" * st["rule"])]
        return rows
    if hs == "boxed":
        w = 76
        inner = [f"{org[:44]:<46}{title[:28]:>28}", f"Pt: {nm}   DOB {dob}", f"{mrn}   {datepart}",
                 f"Clinician: {clin}" if clin else f"Tel {pv.phone}  Fax {pv.fax}"]
        rows = [R("+" + "-" * w + "+")]
        rows += [R("| " + x[:w - 2].ljust(w - 2) + " |") for x in inner]
        rows += [R("+" + "-" * w + "+"), R("")]
        return rows
    rows = [R(f"*** {org} ***", "c", True), R(f"{pv.addr} | {pv.phone}", "c"), R(""),
            R(f"{title} -- {datepart}", b=True), R(f"{nm} | DOB {dob} | {mrn}"),
            R(f"Author: {clin}" if clin else f"Fax {pv.fax}"), R("=" * st["rule"])]
    return rows


def foot_row(pv, i, n):
    return R(pv.style["foot"].format(i=i, n=n, org=pv.name), "c")


ORIG_ID = [0]


def new_orig(C, pv, kind, title, d, clin, blocks_pages, event=None, note_p=0.12):
    """blocks_pages: list of block lists, one per page. Returns list of cids."""
    cids = []
    n = len(blocks_pages)
    for i, blocks in enumerate(blocks_pages, 1):
        C.ocount += 1
        cid = f"c{C.ocount:03d}"
        note = None
        if kind == "clinical" and C.rng.random() < note_p:
            note = C.rng.choice(MARGIN_NOTES).format(d=fdate(plus(d, C.rng.randint(1, 9)), "us2"),
                                                      i=C.rng.choice(["LM", "kt", "JR", "dw", "AB"]))
        o = dict(cid=cid, prov=pv.name, pv=pv, kind=kind, title=title, date=d,
                 head=head_rows(C, pv, title, d, clin, i, n) if kind == "clinical" else [],
                 blocks=blocks, foot=foot_row(pv, i, n), note=note,
                 note_pos=C.rng.choice(["side", "bottom"]), event=event)
        C.origs[cid] = o
        C.order.append(cid)
        cids.append(cid)
    return cids


MARGIN_NOTES = ["f/u 2 wk per Dr - called pt {d} {i}", "copy to atty {d} -{i}",
                "pt aware of results {d} {i}", "** NEEDS AUTH ** {i} {d}",
                "reviewed {d} ~{i}", "faxed to ortho {d} {i}", "LVM re: appt {d} {i}"]


# --------------------------------------------------------------------------
# Clinical text builders
# --------------------------------------------------------------------------
def vitals(rng, pain=None):
    return dict(bp=f"{rng.randint(112, 152)}/{rng.randint(68, 96)}", hr=rng.randint(62, 104),
                rr=rng.randint(13, 20), spo2=rng.randint(95, 100),
                t=round(rng.uniform(97.4, 99.3), 1),
                pain=pain if pain is not None else rng.randint(1, 8))


def vit_str(v):
    return (f"BP {v['bp']}  HR {v['hr']}  RR {v['rr']}  SpO2 {v['spo2']}%  T {v['t']} F  "
            f"Pain {v['pain']}/10")


def dx_lines(codes):
    return [L(f"  {i}. {c}  {ICD[c]}") for i, c in enumerate(codes, 1)]


def fill(C, s):
    return s.format(**C.pron)


def sig(C, pv, clin, d):
    t = f"{C.rng.randint(7, 19):02d}:{C.rng.randint(0, 59):02d}"
    st = pv.style["v"]
    if st == 0:
        return L(f"Electronically signed by {clin} on {fdate(d, pv.style['date_fmt'])} {t}")
    if st == 1:
        return L(f"/s/ {clin}    {fdate(d, pv.style['date_fmt'])}")
    return L(f"Signed: {clin} -- Authenticated {fdate(d, 'iso')}T{t}")


def phase_text(C, ev):
    days = (ev["date"] - C.acc).days
    rng = C.rng
    if days < 0:
        return ""
    if days <= 14:
        return rng.choice(["Pain remains significant, rated {p}/10, and limits sleep.",
                           "Symptoms unchanged since the injury; pain {p}/10.",
                           "Reports constant aching pain {p}/10 worse with activity."]).format(p=rng.randint(6, 8))
    if days <= 60:
        return rng.choice(["Gradual improvement; pain now {p}/10 with activity.",
                           "Partial improvement with therapy, pain {p}/10, still limited at work.",
                           "Better overall but flares with use; pain {p}/10."]).format(p=rng.randint(3, 6))
    return rng.choice(["Residual stiffness and intermittent pain {p}/10.",
                       "Improving steadily; pain {p}/10, occasional flare after exertion.",
                       "Near baseline for daily tasks, pain {p}/10 with heavy use."]).format(p=rng.randint(1, 4))


def office_pages(C, pv, ev, clin, consult=False):
    rng, sp, pat = C.rng, C.sp, C.pat
    st = pv.style["note"]
    d = ev["date"]
    prior = ev["kind"] == "prior_visit"
    v = vitals(rng, pain=0 if prior else None)
    if prior:
        cc = C.sp["prior"]["reason"]
        hpi = (f"{pat['first']} is a {pat['age']}-year-old {pat['sexw']} seen for "
               f"{C.sp['prior']['reason']}. " + C.sp["prior"]["note"])
        exam = C.sp["prior"]["note"] + " Heart regular rate and rhythm. Lungs clear."
        plan = rng.choice(["Routine labs ordered. Return in 12 months.",
                           "Continue current medications. Fasting labs. Recheck in 6 months."])
    else:
        days = (d - C.acc).days
        cc = sp["complaint"] if days < 40 else f"follow-up of {sp['regions'][0]} injury"
        hpi = (f"{pat['age']}-year-old {pat['sexw']} injured on {fdate(C.acc, pv.style['date_fmt'])} "
               f"after {fill(C, sp['mech'])}. " + phase_text(C, ev) + " " +
               ev.get("hpi_extra", ""))
        exam = sp["exam"] if days < 40 else rng.choice([
            "Healing incisions/wounds without erythema. Range of motion improved but not full. "
            "Strength 4/5 in the affected region.",
            "Mild residual tenderness. Range of motion approximately 75 percent of the "
            "contralateral side. Neurovascularly intact.",
            "No effusion or swelling. Motion improving. Mild guarding at end range."])
        plan = ev.get("plan") or rng.choice([
            "Continue therapy as prescribed. Activity modification. Return in 4 weeks.",
            "Continue home program; work restrictions as noted. Follow up after therapy re-evaluation.",
            "Reviewed imaging with patient. Proceed as discussed. Return in 2-3 weeks."])
    codes = ev["codes"]
    meds = C.pat["meds"]
    ros = rng.choice(["ROS: negative except as noted in HPI.",
                      "Review of systems: 10-point ROS negative other than HPI.",
                      "ROS otherwise negative; denies fever, chest pain, bowel/bladder change."])
    pmh = f"PMH: {C.pat['pmh']}. Meds: {meds}. Allergies: {C.pat['allergy']}."
    soc = f"Social: {C.pat['social']}."
    if st == "soap":
        p1 = [P(f"S: Chief complaint: {cc}."), P(hpi), P(ros), P(pmh), P(soc)]
        p2 = [P(f"O: {vit_str(v)}"), P(exam), BL, L("A:")] + dx_lines(codes) + \
             [BL, P(f"P: {plan}")]
    elif st == "narrative":
        p1 = [Hd("CHIEF COMPLAINT"), P(cc.capitalize() + "."), Hd("HISTORY OF PRESENT ILLNESS"),
              P(hpi), Hd("PAST HISTORY"), P(pmh + " " + soc), P(ros)]
        p2 = [Hd("VITAL SIGNS"), L(vit_str(v)), Hd("PHYSICAL EXAMINATION"), P(exam),
              Hd("IMPRESSION")] + dx_lines(codes) + [Hd("PLAN"), P(plan)]
    else:
        def kv(k, val):
            ls = textwrap.wrap(val, 64) or [""]
            return [L(f"{k:<18}| {ls[0]}")] + [L(f"{'':<18}| {x}") for x in ls[1:]]
        p1 = kv("Chief Complaint", cc) + kv("HPI", hpi) + kv("ROS", ros) + kv("History", pmh) + kv("Social", soc)
        p2 = kv("Vitals", vit_str(v)) + kv("Exam", exam) + [L(f"{'Assessment':<18}|")] + \
            dx_lines(codes) + kv("Plan", plan)
    if ev.get("procs"):
        p2.append(L("Procedures/services: " + ", ".join(ev["procs"])))
    p2 += [BL, sig(C, pv, clin, d)]
    pages = [p1, p2]
    if consult:
        work = rng.choice(["Off work until next visit.", "Light duty: no lifting over 10 lb.",
                           "Modified duty, no use of the affected extremity."])
        caus = (f"Within a reasonable degree of medical probability, the injuries described "
                f"above are causally related to the incident of "
                f"{fdate(C.acc, pv.style['date_fmt'])}. The pre-incident records reviewed do not "
                f"document comparable symptoms." if C.tname != "back" else
                f"The patient has a documented history of intermittent low back stiffness. "
                f"Within a reasonable degree of medical probability, the incident of "
                f"{fdate(C.acc, pv.style['date_fmt'])} caused a new disc extrusion and "
                f"radiculopathy and aggravated the pre-existing condition.")
        pages.append([Hd("RECORDS AND IMAGING REVIEWED"),
                      P("Outside emergency records and imaging reviewed: " +
                        "; ".join(x[3] for x in C.sp["er_img"])),
                      Hd("WORK STATUS"), P(work), Hd("CAUSATION"), P(caus), BL,
                      sig(C, pv, clin, d)])
    return pages


def er_pages(C, pv, ev, clin):
    rng, sp, pat = C.rng, C.sp, C.pat
    d = ev["date"]
    h0 = rng.randint(8, 20)
    arrival = f"{h0:02d}:{rng.randint(0, 59):02d}"
    v0 = vitals(rng, pain=rng.randint(6, 9))
    pages = []
    if pv.role == "er":
        left = colwrap([f"Arrival: {arrival}", f"Mode: {rng.choice(['private vehicle', 'EMS', 'ambulatory'])}",
                        f"Chief complaint: {sp['complaint']}", f"ESI level: {rng.choice([2, 3, 3])}",
                        f"Allergies: {pat['allergy']}", f"Home meds: {pat['meds']}"])
        right = colwrap([f"BP {v0['bp']}", f"HR {v0['hr']}", f"RR {v0['rr']}", f"SpO2 {v0['spo2']}%",
                         f"Temp {v0['t']} F", f"Pain {v0['pain']}/10", f"Triage RN: {pv.nurse}"])
        pages.append([P(f"Patient arrives reporting injury after {fill(C, sp['mech'])}."),
                      BL, TWO(left, right), BL,
                      P(rng.choice(["Patient alert and oriented x4, in moderate distress.",
                                    "Ambulatory to room with assistance, guarding the injured area.",
                                    "Calm, cooperative, tearful when describing the event."])),
                      L("Fall risk screen: negative    Abuse screen: negative")])
    hpi = (f"{pat['age']}-year-old {pat['sexw']} presenting {rng.choice(['about an hour', 'shortly', 'several hours'])} "
           f"after {fill(C, sp['mech'])}. Pain rated {v0['pain']}/10. {rng.choice(['No other injuries reported.', 'Denies other complaints.', 'No prior injury to this area.'])}")
    p1 = [Hd("HISTORY OF PRESENT ILLNESS"), P(hpi), Hd("PAST MEDICAL HISTORY"),
          P(f"{pat['pmh']}. Medications: {pat['meds']}. Allergies: {pat['allergy']}."),
          Hd("PHYSICAL EXAM"), P(f"Vitals: {vit_str(v0)}"), P(sp["exam"])]
    p2 = [Hd("ED COURSE / MEDICAL DECISION MAKING"), P(sp["er_tx"]),
          P("Imaging obtained: " + "; ".join(f"{x[0]} - {x[3]}" for x in sp["er_img"])),
          Hd("DIAGNOSES")] + dx_lines(ev["codes"]) + \
         [Hd("DISPOSITION"), P(rng.choice(["Discharged home in stable condition with follow-up instructions.",
                                           "Discharged to home with family; return precautions given."])),
          L("Services: " + ", ".join(ev["procs"])), BL, sig(C, pv, clin, d)]
    pages += [p1, p2]
    # vitals flowsheet: two (or one) pages that look identical but carry different values
    nfs = 2 if pv.role == "er" else 1
    t = h0 * 60 + rng.randint(0, 50)
    for k in range(nfs):
        rows = [L(f"{'Time':<7}{'BP':<10}{'HR':<6}{'RR':<5}{'SpO2':<7}{'Temp':<7}{'Pain':<6}Init")]
        for _ in range(8):
            v = vitals(rng)
            rows.append(L(f"{t // 60 % 24:02d}:{t % 60:02d}  {v['bp']:<10}{v['hr']:<6}{v['rr']:<5}"
                          f"{str(v['spo2']) + '%':<7}{v['t']:<7}{v['pain']:<6}{rng.choice(['MK', 'TS', 'RN2'])}"))
            t += rng.choice([15, 20, 30, 45])
        pages.append([Hd(f"VITAL SIGNS FLOWSHEET  (sheet {k + 1} of {nfs})"), BL] + rows +
                     [BL, L("Pain scale: 0-10 NRS. Abnormal values reported to provider.")])
    pages.append([Hd("DISCHARGE INSTRUCTIONS"),
                  P(f"You were seen today for {sp['complaint']}. " +
                    rng.choice(["Keep the splint/dressing clean and dry.", "Rest and apply ice 20 minutes at a time.",
                                "Avoid strenuous activity until cleared."])),
                  P("Return to the emergency department for worsening pain, numbness, fever, or any "
                    "new concern."),
                  P(f"Follow up with your primary care provider or specialist within "
                    f"{rng.choice(['2-3', '5-7', '3-5'])} days."),
                  L("Patient verbalized understanding.   Signature on file.")])
    return pages


def imaging_pages(C, pv, ev, clin):
    rng = C.rng
    out = []
    for name, cpt, find, imp in ev["studies"]:
        acc = f"{rng.choice(['A', 'RX', 'IMG'])}{rng.randint(1000000, 9999999)}"
        hist = f"{C.sp['complaint']} after injury on {fdate(C.acc, pv.style['date_fmt'])}."
        v = pv.style["v"]
        if v == 0:
            b = [Hd(f"EXAM: {name}"), L(f"ACCESSION: {acc}    CPT: {cpt}"),
                 Hd("CLINICAL HISTORY"), P(hist), Hd("COMPARISON"),
                 P(rng.choice(["None.", "Outside radiographs from the date of injury."])),
                 Hd("TECHNIQUE"), P("Standard departmental protocol."),
                 Hd("FINDINGS"), P(find), Hd("IMPRESSION"), P(imp)]
        elif v == 1:
            b = [L("+-------------------+------------------------------------------+"),
                 L(f"| Exam              | {name[:40]:<40} |"),
                 L(f"| Accession         | {acc:<40} |"),
                 L(f"| Ordering          | {ev.get('ordering', 'Referring provider')[:40]:<40} |"),
                 L("+-------------------+------------------------------------------+"),
                 BL, P("Indication: " + hist), P("FINDINGS: " + find), BL, P("IMPRESSION: " + imp)]
        else:
            items = [x.strip() for x in find.split(". ") if x.strip()]
            b = [Hd(name), L(f"Acc# {acc}"), P("History: " + hist), L("Findings:")]
            b += [P(f"{i}. {x.rstrip('.')}.") for i, x in enumerate(items, 1)]
            b += [L("Conclusion:"), P(imp)]
        b += [BL, sig(C, pv, clin, ev["date"])]
        out.append(b)
    return out


LAB_PANELS = {
    "85025": [("WBC", 4.0, 11.0, "K/uL"), ("Hemoglobin", 12.0, 16.5, "g/dL"),
              ("Hematocrit", 36.0, 48.0, "%"), ("Platelets", 150, 400, "K/uL")],
    "80053": [("Sodium", 135, 145, "mmol/L"), ("Potassium", 3.5, 5.1, "mmol/L"),
              ("Glucose", 70, 99, "mg/dL"), ("Creatinine", 0.6, 1.2, "mg/dL"),
              ("ALT", 7, 40, "U/L"), ("Albumin", 3.5, 5.0, "g/dL")],
    "80048": [("Sodium", 135, 145, "mmol/L"), ("Potassium", 3.5, 5.1, "mmol/L"),
              ("Glucose", 70, 99, "mg/dL"), ("Creatinine", 0.6, 1.2, "mg/dL")],
    "80061": [("Total cholesterol", 100, 199, "mg/dL"), ("LDL", 0, 129, "mg/dL"),
              ("HDL", 40, 90, "mg/dL"), ("Triglycerides", 0, 149, "mg/dL")],
    "86140": [("CRP", 0.0, 0.9, "mg/dL")],
    "83036": [("Hemoglobin A1c", 4.0, 5.6, "%")],
    "87070": [],
}


def lab_pages(C, pv, ev, clin):
    rng = C.rng
    v = pv.style["v"]
    rows = []
    for cpt in ev["procs"]:
        if cpt == "36415":
            continue
        for name, lo, hi, unit in LAB_PANELS[cpt]:
            val = rng.uniform(lo - (hi - lo) * 0.15, hi + (hi - lo) * 0.25)
            val = round(val, 1) if hi < 20 else int(val)
            flag = "H" if val > hi else ("L" if val < lo else "")
            rows.append((name, str(val), f"{lo}-{hi}", unit, flag))
        if cpt == "87070":
            rows.append(("Wound culture", rng.choice(["Pasteurella multocida, moderate growth",
                                                      "Mixed skin flora, light growth"]), "", "", "A"))
    coll = f"{rng.randint(6, 11):02d}:{rng.randint(0, 59):02d}"
    acc = f"L{rng.randint(10000000, 99999999)}"
    if v == 0:
        b = [L(f"Accession {acc}    Collected {fdate(ev['date'], pv.style['date_fmt'])} {coll}"),
             L(f"Ordering: {ev.get('ordering', 'Primary care')}"), BL,
             L(f"{'TEST':<22}{'RESULT':<14}{'REF RANGE':<14}{'UNITS':<9}FLAG"),
             L("-" * 66)]
        b += [L(f"{a[:21]:<22}{r[:40]:<14}{rr:<14}{u:<9}{f}") for a, r, rr, u, f in rows]
    elif v == 1:
        b = [L(f"| Specimen {acc} | Collection date {fdate(ev['date'], pv.style['date_fmt'])} |"), BL]
        b += [L(f"| {a:<20} | {r:<12} | {rr:<12} | {u:<7} | {f:<2}|") for a, r, rr, u, f in rows]
    else:
        b = [P(f"Specimen collected {fdate(ev['date'], pv.style['date_fmt'])} at {coll}; received "
               f"same day. Accession {acc}.")]
        b += [L(f"{a + ' ':.<30} {r} {u}  [{rr}] {f}") for a, r, rr, u, f in rows]
    b += [BL, L(f"Reviewed by laboratory director {clin}"),
          L("Results flagged H/L/A are outside the reference interval.")]
    return [b]


def quest_page(C, pv, ev, severity):
    q = QUEST[C.sp["quest"]]
    rng = C.rng
    ans = []
    for _ in q["items"]:
        x = severity if q["bad_high"] else 1 - severity
        val = round(q["lo"] + x * (q["hi"] - q["lo"]) + rng.uniform(-0.8, 0.8))
        ans.append(min(q["hi"], max(q["lo"], val)))
    tot = sum(ans)
    b = [Hd(f"{C.sp['quest']} QUESTIONNAIRE"),
         L(f"Completed by patient on {fdate(ev['date'], pv.style['date_fmt'])}"),
         L(f"Scale {q['lo']}-{q['hi']}"), BL]
    for i, (item, a) in enumerate(zip(q["items"], ans), 1):
        b.append(L(f"{i:>2}. {item:<45} [ {a} ]"))
    b += [BL, L(f"Raw total: {tot}"), L("Scored by: " + pv.clins[-1])]
    return b


def measure_vals(C, frac):
    out = []
    for lab, a, g, u in C.sp["measures"]:
        val = a + (g - a) * frac + C.rng.uniform(-2, 2) * (1 if abs(g - a) > 5 else 0.2)
        out.append((lab, round(val) if abs(g - a) > 5 else round(val, 1), g, u))
    return out


def ther_eval_pages(C, pv, ev, clin, re=False):
    rng, sp = C.rng, C.sp
    frac = ev.get("frac", 0.0)
    ms = measure_vals(C, frac)
    title_goal = [f"{lab}: {g} {u}" for lab, _, g, u in ms]
    body = [Hd("PROGRESS RE-EVALUATION" if re else "INITIAL EVALUATION"),
            P(f"Referred for {', '.join(sp['regions'])} after {fill(C, sp['mech'])}. " +
              phase_text(C, ev)),
            Hd("OBJECTIVE MEASURES")]
    body += [L(f"  {lab:<32} {val} {u}") for lab, val, _, u in ms]
    body += [Hd("ASSESSMENT"),
             P(rng.choice(["Impairments in motion, strength and function consistent with the "
                           "referring diagnosis. Good rehabilitation potential.",
                           "Patient demonstrates deficits limiting work and household tasks. "
                           "Skilled therapy indicated.",
                           "Progressing toward goals; continued skilled intervention needed."]))]
    p2 = [Hd("GOALS (6-8 weeks)")] + [L("  - " + g) for g in title_goal] + \
         [Hd("PLAN OF CARE"),
          P(f"Frequency {rng.choice(['2x/week', '2-3x/week', '3x/week'])} for "
            f"{rng.choice([4, 6, 8])} weeks. Interventions: " + ", ".join(sp["exercises"][:5]) + "."),
          L("Billing: " + ", ".join(ev["procs"])), BL, sig(C, pv, clin, ev["date"])]
    pages = [body, p2] if not re else [body + p2[:3] + p2[-3:]]
    pages.append(quest_page(C, pv, ev, max(0.1, 0.85 - frac * 0.7)))
    return pages


def ther_visit_page(C, pv, ev, clin):
    rng, sp = C.rng, C.sp
    frac = ev.get("frac", 0.3)
    v = pv.style["v"]
    pain = max(0, round(7 - 6 * frac + rng.uniform(-1, 1)))
    ex = rng.sample(sp["exercises"], 5)
    units = ", ".join(f"{c} x{rng.choice([1, 1, 2])}" for c in ev["procs"])
    tin = f"{rng.randint(7, 17):02d}:{rng.choice(['00', '15', '30', '45'])}"
    vis = f"Visit {ev['visit_no']} of {ev['auth']} authorized"
    ms = measure_vals(C, frac)
    if pv.role == "chiro":
        ex = ["Diversified CMT, segments " + rng.choice(["L3-S1", "C2-C6", "T4-T8 and L4-S1"]),
              "Myofascial release paraspinals 8 min", "Interferential e-stim 15 min",
              "Intersegmental traction 10 min", rng.choice(sp["exercises"])]
    if v == 0:
        b = [L(vis + f"    Time in {tin}"),
             P(f"S: Patient reports pain {pain}/10. " + rng.choice(
                 ["Sleeping better.", "Sore after last session.", "Able to do more at home.",
                  "Flare after a long shift.", "No new complaints."])),
             L("O:")]
        b += [L(f"   {e:<34} {rng.choice([2, 3])} x {rng.choice([10, 12, 15])}") for e in ex]
        b += [L(f"   {ms[0][0]}: {ms[0][1]} {ms[0][3]}"),
              P("A: " + rng.choice(["Tolerated treatment well.", "Mild fatigue with progression.",
                                    "Improved quality of movement.", "Required cueing for form."])),
              P("P: " + rng.choice(["Continue plan of care.", "Progress resistance next visit.",
                                    "Add functional tasks.", "Re-assess at next visit."]))]
        b += [L("Units: " + units), sig(C, pv, clin, ev["date"])]
    elif v == 1:
        b = [L(vis), L(f"{'Exercise / Modality':<34}|{'Sets x Reps':^13}|{'Load':^8}| Notes"),
             L("-" * 72)]
        for e in ex:
            b.append(L(f"{e[:33]:<34}|{str(rng.choice([2, 3])) + ' x ' + str(rng.choice([8, 10, 15])):^13}|"
                       f"{rng.choice(['--', '1 lb', '2 lb', 'red', 'green']):^8}| {rng.choice(['ok', 'cues', 'pain-free', 'mod fatigue'])}"))
        b += [BL, L(f"Pain pre {pain}/10, post {max(0, pain - rng.randint(0, 2))}/10"),
              L(f"{ms[0][0]} {ms[0][1]} {ms[0][3]};  {ms[1][0]} {ms[1][1]} {ms[1][3]}"),
              L("CPT: " + units), sig(C, pv, clin, ev["date"])]
    else:
        left = colwrap(["TREATMENT"] + ex + [f"Time in {tin}"], 40)
        right = colwrap(["RESPONSE", f"Pain {pain}/10",
                         rng.choice(["Tolerated well", "Mild soreness", "Improved motion"]),
                         f"{ms[0][0]} {ms[0][1]} {ms[0][3]}",
                         rng.choice(["Continue POC", "Progress next visit", "Re-eval due soon"]),
                         "Units: " + units], 40)
        b = [L(vis), BL, TWO(left, right), BL, sig(C, pv, clin, ev["date"])]
    return [b]


def inj_pages(C, pv, ev, clin):
    rng, inj = C.rng, C.sp["injection"]
    v = vitals(rng)
    p1 = [Hd("PRE-PROCEDURE NOTE"), P(f"Indication: {phase_text(C, ev)} Failed conservative care."),
          P(f"Vitals: {vit_str(v)}"),
          P("Risks including infection, bleeding, nerve injury, and elevated blood glucose were "
            "discussed. Written consent obtained. Time-out performed."),
          Hd("DIAGNOSES")] + dx_lines(ev["codes"])
    p2 = [Hd("PROCEDURE NOTE"), L(f"Procedure: {inj['name']}"), L("CPT: " + ", ".join(ev["procs"])),
          P(inj["technique"]),
          P(f"Pre-procedure pain {rng.randint(6, 8)}/10; post-procedure pain {rng.randint(1, 4)}/10."),
          P("No complications. Discharged ambulatory after 20 minutes of observation."),
          BL, sig(C, pv, clin, ev["date"])]
    return [p1, p2]


def surg_pages(C, pv, ev, surgeon):
    rng, sg = C.rng, C.sp["surgery"]
    anes = pv.clins[1] if len(pv.clins) > 1 else pv.clins[0]
    v = vitals(rng, pain=rng.randint(3, 7))
    hp = [Hd("PRE-OPERATIVE HISTORY AND PHYSICAL"),
          P(f"{C.pat['age']}-year-old {C.pat['sexw']} injured after {fill(C, C.sp['mech'])}. "
            f"Failed nonoperative management / indicated for operative care."),
          P(f"PMH: {C.pat['pmh']}. Allergies: {C.pat['allergy']}. NPO since midnight."),
          P(f"Vitals {vit_str(v)}. Heart and lungs normal."),
          P(f"Plan: {sg['name']}. Consent signed. Site marked.")]
    op1 = [Hd("OPERATIVE REPORT"), L(f"Surgeon: {surgeon}"), L(f"Anesthesia: {sg['anes']} ({anes})"),
           L("Preoperative diagnosis:")] + dx_lines(ev["codes"]) + \
          [L("Postoperative diagnosis: same"), L(f"Procedure: {sg['name']}"),
           L("CPT: " + ", ".join(ev["procs"])), Hd("FINDINGS"), P(sg["findings"])]
    op2 = [Hd("DESCRIPTION OF PROCEDURE"),
           P("The patient was identified in the holding area and brought to the operating room. "
             "After induction of anesthesia the extremity was prepped and draped in the usual "
             "sterile fashion. A time-out was performed. Preoperative antibiotics were given."),
           P(sg["technique"]),
           P(f"Estimated blood loss {sg['ebl']}. No complications. Counts correct. The patient "
             f"was taken to recovery in stable condition."), BL, sig(C, pv, surgeon, ev["date"])]
    rows = [L(f"{'Time':<7}{'BP':<10}{'HR':<6}{'SpO2':<7}{'EtCO2':<7}Agent")]
    t = rng.randint(7, 11) * 60
    for _ in range(12):
        vv = vitals(rng)
        rows.append(L(f"{t // 60:02d}:{t % 60:02d}  {vv['bp']:<10}{vv['hr']:<6}{str(vv['spo2']) + '%':<7}"
                      f"{rng.randint(32, 42):<7}{rng.choice(['sevo 2.0', 'sevo 1.8', 'propofol gtt', '--'])}"))
        t += 5
    anesrec = [Hd("ANESTHESIA RECORD"), L(f"Anesthesia provider: {anes}"), L(f"Technique: {sg['anes']}"),
               L(f"ASA class {rng.choice(['I', 'II'])}"), BL] + rows
    dc = [Hd("PACU / DISCHARGE SUMMARY"),
          P(f"Aldrete score {rng.choice([9, 10])} at discharge. Pain {rng.randint(2, 4)}/10 controlled "
            "with oral analgesics. Tolerating fluids."),
          P("Discharge instructions: keep dressing dry, elevate, sling/brace as directed, follow up "
            f"in {rng.choice(['10-14', '7-10'])} days."),
          L(f"Discharged to home with {rng.choice(['spouse', 'adult child', 'friend'])}.")]
    return [hp, op1, op2, anesrec, dc]


# --------------------------------------------------------------------------
# Billing and admin builders
# --------------------------------------------------------------------------
def statement_pages(C, pv, evs):
    rng = C.rng
    lines = []
    for ev in evs:
        for c in ev["procs"]:
            amt = FEES[c][0]
            lines.append((ev["date"], c, FEES[c][1], amt))
    if not lines:
        return []
    per = 18
    chunks = [lines[i:i + per] for i in range(0, len(lines), per)]
    acct = f"{rng.randint(100000, 999999)}"
    sdate = plus(max(e["date"] for e in evs), rng.randint(20, 60))
    pages = []
    total = sum(x[3] for x in lines)
    paid = round(total * rng.uniform(0.2, 0.55), 2)
    for k, ch in enumerate(chunks):
        b = [Hd(f"{pv.name.upper()}"), L(pv.addr), L(f"Billing inquiries {pv.phone}   Tax ID {pv.tin}"),
             BL, Hd("ITEMIZED STATEMENT OF CHARGES"),
             L(f"Patient: {pname(C, pv)}   Account: {acct}"),
             L(f"Statement date: {fdate(sdate, pv.style['date_fmt'])}"), BL,
             L(f"{'Service Date':<14}{'Code':<8}{'Description':<46}{'Charge':>10}"), L("-" * 78)]
        b += [L(f"{fdate(d, pv.style['date_fmt']):<14}{c:<8}{ds[:45]:<46}{a:>10,.2f}") for d, c, ds, a in ch]
        if k == len(chunks) - 1:
            b += [L("-" * 78), L(f"{'Total charges':<68}{total:>10,.2f}"),
                  L(f"{'Payments/adjustments':<68}{-paid:>10,.2f}"),
                  L(f"{'Balance due':<68}{total - paid:>10,.2f}")]
        pages.append(b)
    return pages


def claim_page(C, pv, ev, corrected=False):
    rng = C.rng
    procs = list(ev["procs"])
    amts = [FEES[c][0] for c in procs]
    if corrected:
        # corrected claim: same DOS, different code or amount
        if len(procs) > 1 and rng.random() < 0.5:
            procs = procs[:-1]
            amts = amts[:-1]
        else:
            amts = [round(a * rng.choice([0.85, 1.1, 1.25]), 2) for a in amts]
    payer = C.payer
    d = ev["date"]
    v = pv.claim_style
    dxs = ev["codes"][:4]
    if v == 0:
        b = [Hd("HEALTH INSURANCE CLAIM FORM  (1500 facsimile)"),
             L(f"1. Payer: {payer}    1a. Insured ID: {C.pat['member']}"),
             L(f"2. Patient: {pname(C, pv)}   3. DOB {fdate(C.pat['dob_d'], 'us')}  Sex {C.pat['sex']}"),
             L(f"10b. Related to auto accident? {'YES' if C.tname == 'mva' else 'NO'}   "
               f"10a. Employment? {'YES' if C.tname == 'back' else 'NO'}"),
             L(f"14. Date of current illness/injury: {fdate(C.acc, 'us')}"),
             L(f"22. Resubmission code: {'7  Orig ref ' + ev['claim_ref'] if corrected else '1'}"),
             L("21. Diagnosis: " + "  ".join(f"{'ABCD'[i]}. {c}" for i, c in enumerate(dxs))), BL,
             L(f"{'24A DOS':<12}{'B POS':<7}{'D CPT':<8}{'E Ptr':<7}{'F Charges':>11}{'G Units':>9}  J NPI")]
        for c, a in zip(procs, amts):
            b.append(L(f"{fdate(d, 'us'):<12}{ROLE[pv.role]['pos']:<7}{c:<8}{'A':<7}{a:>11,.2f}{1:>9}  {pv.npi}"))
        b += [BL, L(f"28. Total charge {sum(amts):,.2f}    25. Fed Tax ID {pv.tin}"),
              L(f"33. Billing provider: {pv.name}, {pv.addr}")]
    elif v == 1:
        b = [Hd("UB-04 SUMMARY / FACILITY CLAIM"), L(f"Provider: {pv.name}   NPI {pv.npi}"),
             L(f"Pt control #: {ev['claim_ref']}   Type of bill: {'0137' if corrected else '0131'}"),
             L(f"Statement covers period {fdate(d, 'us')} thru {fdate(d, 'us')}"),
             L(f"Patient: {pname(C, pv)}   Payer: {payer}"), BL,
             L(f"{'Rev':<6}{'Description':<40}{'HCPCS':<8}{'Date':<12}{'Charges':>11}")]
        for c, a in zip(procs, amts):
            rev = "0450" if pv.role == "er" else ("0360" if pv.role == "asc" else "0510")
            b.append(L(f"{rev:<6}{FEES[c][1][:39]:<40}{c:<8}{fdate(d, 'us'):<12}{a:>11,.2f}"))
        b += [L(f"{'0001':<6}{'TOTAL':<60}{sum(amts):>11,.2f}"), BL,
              L("Principal dx: " + dxs[0] + "   Other dx: " + " ".join(dxs[1:]))]
    else:
        b = [Hd("SUPERBILL / ENCOUNTER FORM"), L(f"{pv.name}  |  Tax ID {pv.tin}"),
             L(f"Patient {pname(C, pv)}  |  Visit {fdate(d, pv.style['date_fmt'])}"),
             L(f"Insurance: {payer}  ID {C.pat['member']}"),
             L("Claim: " + ("CORRECTED, replaces " + ev["claim_ref"] if corrected else ev["claim_ref"])), BL]
        for c, a in zip(procs, amts):
            b.append(L(f"[x] {c}  {FEES[c][1][:44]:<44} ${a:,.2f}"))
        b += [BL, L("ICD-10: " + ", ".join(dxs)), L(f"Total ${sum(amts):,.2f}")]
    return b


def cover_letter(C, pv, prod_date, req_no, req_date):
    rng = C.rng
    rng_dates = f"{fdate(plus(C.acc, -365), 'us')} to present"
    return [L(fdate(prod_date, pv.style["date_fmt"])), BL, L(C.firm), L(C.firm_addr), BL,
            L(f"RE: Records Request No. {req_no}"),
            L(f"    Patient: {C.pat['first']} {C.pat['last']}    DOB: {C.pat['dob']}"),
            L(f"    Dates requested: {rng_dates}"), BL, L("Dear Records Coordinator:"), BL,
            P(f"In response to your request dated {fdate(req_date, pv.style['date_fmt'])}, enclosed "
              f"are copies of the medical and billing records maintained by {pv.name} for the "
              f"patient named above. Records are released pursuant to the enclosed authorization."),
            P("Please note that records received from outside facilities may be included where "
              "they form part of our chart. Contact our office with any questions."), BL,
            L("Sincerely,"), BL, L(pv.roi), L("Release of Information Specialist"), L(pv.name),
            L(f"Phone {pv.phone}   Fax {pv.fax}")]


def certification(C, pv, d):
    return [Hd("CERTIFICATION OF CUSTODIAN OF RECORDS"), BL,
            P(f"I, {pv.roi}, am the duly authorized custodian of records for {pv.name} and have "
              f"authority to certify the attached records."),
            P(f"The attached records pertaining to {C.pat['first']} {C.pat['last']} (DOB "
              f"{C.pat['dob']}) are true and complete copies of records made at or near the time "
              f"of the acts recorded, by or from information transmitted by persons with "
              f"knowledge, and kept in the course of regularly conducted business activity."),
            P("I declare under penalty of perjury that the foregoing is true and correct."), BL,
            L(f"Executed on {fdate(d, pv.style['date_fmt'])}"), BL,
            L("______________________________"), L(f"{pv.roi}, Custodian of Records")]


def hipaa_page(C, d):
    return [Hd("AUTHORIZATION FOR RELEASE OF PROTECTED HEALTH INFORMATION"),
            L("(HIPAA-compliant, 45 CFR 164.508)"), BL,
            L(f"Patient name: {C.pat['first']} {C.pat['last']}     Date of birth: {C.pat['dob']}"),
            P(f"I authorize any physician, hospital, clinic, laboratory, therapist, pharmacy or "
              f"other provider to release my complete medical and billing records, including "
              f"imaging, to {C.firm} and its staff, for the purpose of evaluating and pursuing a "
              f"personal injury claim arising from the incident of {tdate(C.acc)}."),
            P("This authorization expires two years from the date signed. I may revoke it in "
              "writing at any time except to the extent action has been taken in reliance on it. "
              "Information disclosed may be redisclosed by the recipient and no longer protected."),
            P("A photocopy or electronic copy of this authorization is as valid as the original."),
            BL, L(f"Signature: /{C.pat['first']} {C.pat['last']}/       Date signed: {tdate(d)}"),
            L("Witness: ____________________")]


# --------------------------------------------------------------------------
# Case construction
# --------------------------------------------------------------------------
def build_case(n):
    rng = random.Random(BASE_SEED + 7919 * n)
    C = Ctx()
    C.rng, C.n = rng, n
    C.tname = TYPE_ORDER[(n - 1) % 6]
    C.var = (n - 1) // 6
    sp = TYPES[C.tname]
    C.sp = sp
    C.ocount = 0
    C.origs, C.order = {}, []
    sex = rng.choice(["F", "M"])
    first = rng.choice(FIRST_F if sex == "F" else FIRST_M)
    last = rng.choice(LAST)
    acc = dt.date(rng.choice([2024, 2025]), rng.randint(1, 10), rng.randint(1, 28))
    if C.tname == "knee":
        acc = dt.date(rng.choice([2024, 2025]), rng.choice([1, 2, 12]) if True else 1, rng.randint(1, 26))
        if acc.month == 12:
            acc = acc.replace(year=2024)
    age = rng.randint(24, 63)
    dob = dt.date(acc.year - age, rng.randint(1, 12), rng.randint(1, 28))
    if (acc.month, acc.day) < (dob.month, dob.day):
        age -= 1
    C.acc = acc
    C.pat = dict(first=first, last=last, sex=sex, dob=tdate(dob), dob_d=dob, age=age,
                 sexw="female" if sex == "F" else "male",
                 member=f"{rng.choice(['NVH', 'BFM', 'CCN'])}{rng.randint(10000000, 99999999)}",
                 pmh=rng.choice(["Hypertension, hyperlipidemia", "Seasonal allergies",
                                 "GERD; remote appendectomy", "No significant past history",
                                 "Mild intermittent asthma"]),
                 meds=rng.choice(["lisinopril 10 mg daily", "none", "omeprazole 20 mg daily",
                                  "cetirizine PRN", "albuterol inhaler PRN"]),
                 allergy=rng.choice(["NKDA", "penicillin (rash)", "sulfa", "NKDA"]),
                 social=rng.choice(["Works as a warehouse associate, nonsmoker",
                                    "Office manager, rare alcohol", "School bus driver, nonsmoker",
                                    "Line cook, former smoker", "Retail supervisor, no tobacco"]))
    C.pron = dict(he="she" if sex == "F" else "he", his="her" if sex == "F" else "his",
                  him="her" if sex == "F" else "him")
    C.firm = FIRMS[n % len(FIRMS)]
    C.firm_addr = f"{rng.randint(10, 990)} {rng.choice(STREETS)}, Suite {rng.randint(100, 900)}, {CITIES[n % 6][0]}"
    C.defense = DEFENSE[n % len(DEFENSE)]
    C.payer = HEALTH_PLANS[n % 3]
    C.insurer = {"mva": "Harrowgate Auto Insurance Exchange",
                 "back": "Ridgeline Workers Compensation Mutual"}.get(
        C.tname, "Bellwether Premises Liability Underwriters")

    roles = list(sp["roles"][C.var])
    places = PLACES[:]
    rng.shuffle(places)
    city = CITIES[(n * 5) % 6]
    styles = make_styles(rng, len(roles))
    provs = {}
    for i, r in enumerate(roles):
        nm = f"{places[i]} {rng.choice(ROLE[r]['suffix'])}"
        provs[r] = Prov(r, nm, rng, styles[i], city)
    C.provs = provs
    first_role = roles[0]
    therapy = next(r for r in roles if r in THERAPY_ROLES)
    spec = provs[sp["spec"]]
    pcp = provs["pcp"]
    has_surg = sp["surgery"] is not None and C.var in sp["surgery_variants"] and "asc" in provs
    inj_prov = provs.get("pain") or (spec if sp["injection"] else None)

    evs = []

    def E(kind, date, pv, codes, procs, summary, **kw):
        e = dict(kind=kind, date=wkday(date) if kind not in ("er_visit",) else date, pv=pv,
                 codes=list(codes), procs=list(procs), summary=summary, **kw)
        evs.append(e)
        return e

    # pre-incident
    pd = plus(acc, -rng.randint(60, 420))
    pr = sp["prior"]
    E("prior_visit", pd, pcp, pr["codes"], pr["cpts"], f"Pre-incident visit: {pr['reason']}")
    labp = provs.get("lab", pcp)
    E("lab", plus(pd, rng.randint(0, 3)), labp, pr["codes"][:1], ["80053", "85025", "80061", "36415"],
      "Pre-incident routine labs (CMP, CBC, lipid panel)", ordering=pcp.clins[0])
    # acute
    fp = provs[first_role]
    d0 = acc if first_role == "er" or rng.random() < 0.6 else plus(acc, 1)
    er_codes = sp["acute"]
    E("er_visit", d0, fp, er_codes, sp["er_cpt"][first_role],
      f"{'Emergency department' if first_role == 'er' else 'Urgent care'} visit after the incident; "
      f"{sp['complaint']}")
    E("imaging", d0, fp, sp["acute"][:2], [x[1] for x in sp["er_img"]],
      "Initial imaging: " + "; ".join(x[0].title() + " - " + x[3] for x in sp["er_img"]),
      studies=sp["er_img"], ordering=fp.clins[0])
    if sp.get("rabies") and first_role == "er":
        E("lab", d0, fp, ["S61.451A"], ["85025", "86140", "36415"], "ED labs: CBC and CRP",
          ordering=fp.clins[0])
    d = plus(d0, rng.randint(2, 6))
    E("office_visit", d, pcp, sp["acute"][:2], ["99214"], "Primary care follow-up after the incident",
      plan="Referral to specialist and therapy. Work note provided. Return in 2-3 weeks.")
    if sp.get("rabies"):
        for k, off in enumerate([3, 7, 14]):
            dd = plus(d0, off)
            E("office_visit", dd, pcp, ["Z23", "Z20.3"] + (["L03.113"] if k == 0 else []),
              ["90675", "90471"] + (["99213"] if k == 0 else []),
              f"Rabies vaccine series dose {k + 2}" + (" and wound check; cellulitis" if k == 0 else ""),
              plan="Continue rabies post-exposure series. Wound check." if k else
              "Cellulitis of right hand: culture sent, continue amoxicillin-clavulanate. Rabies dose given.")
            if k == 0:
                E("lab", dd, provs.get("lab", pcp), ["L03.113"], ["87070", "85025", "86140", "36415"],
                  "Wound culture, CBC and CRP for cellulitis", ordering=pcp.clins[0])
    s1 = wkday(plus(d0, rng.randint(5, 12) if sp["early_surgery"] else rng.randint(8, 21)))
    E("office_visit", s1, spec, sp["mid"] if not sp["early_surgery"] else sp["acute"][:2],
      [rng.choice(["99204", "99204", "99203"])], f"Specialist consultation ({spec.name})", consult=True)
    cur = s1
    if "imaging" in provs and sp["adv_img"]:
        di = plus(s1, rng.randint(2, 9))
        E("imaging", di, provs["imaging"], sp["mid"], [x[1] for x in sp["adv_img"]],
          "Advanced imaging: " + "; ".join(x[0].title() + " - " + x[3] for x in sp["adv_img"]),
          studies=sp["adv_img"], ordering=spec.clins[0])
        cur = plus(di, rng.randint(3, 9))
        E("office_visit", cur, spec, sp["mid"], ["99214"], "Specialist follow-up; imaging reviewed")
    if sp["injection"] and inj_prov is not None:
        for k in range(sp["injection"]["count"]):
            cur = plus(cur, rng.randint(7, 24))
            E("injection", cur, inj_prov, sp["injection"]["dx"], sp["injection"]["cpts"],
              f"{sp['injection']['name']} (#{k + 1})")
    surg_date = None
    if has_surg:
        if "lab" in provs:
            E("lab", plus(cur, rng.randint(4, 10)), provs["lab"], sp["surgery"]["dx"][:1],
              ["85025", "80048", "36415"], "Pre-operative labs (CBC, BMP)", ordering=spec.clins[0])
        surg_date = wkday(plus(cur, rng.randint(9, 18)))
        E("surgery", surg_date, provs["asc"], sp["surgery"]["dx"], sp["surgery"]["cpts"],
          sp["surgery"]["name"], surgeon=spec.clins[0])
        E("office_visit", plus(surg_date, rng.randint(10, 14)), spec, sp["late"][:2], ["99024"],
          "Post-operative visit: wound check, sutures removed")
    # therapy course
    t0 = wkday(plus(surg_date or s1, rng.randint(4, 12)))
    tp = provs[therapy]
    ev_cpt, re_cpt, vis_cpts = sp["ther"][therapy]
    nvis = rng.randint(18, 40)
    auth = nvis + rng.randint(0, 6)
    weeks_gap = [2, 2, 3, 2, 3]
    E("pt_eval", t0, tp, sp["late"] if has_surg else sp["mid"], [ev_cpt],
      f"{'Chiropractic' if therapy == 'chiro' else ('Occupational' if therapy == 'ot' else 'Physical')} "
      f"therapy initial evaluation", frac=0.0)
    cur = t0
    re_at = sorted({nvis // 2, nvis - 1} if nvis > 20 else {nvis - 1})
    vno = 0
    for i in range(nvis):
        cur = plus(cur, rng.choice(weeks_gap))
        cur = wkday(cur)
        frac = (i + 1) / nvis
        vno += 1
        E("pt_visit", cur, tp, (sp["late"] if has_surg else sp["mid"])[:2],
          rng.sample(vis_cpts, min(len(vis_cpts), rng.choice([2, 3]))),
          f"Therapy visit #{vno}", frac=frac, visit_no=vno, auth=auth)
        if i in re_at:
            cur = wkday(plus(cur, rng.choice([1, 2, 3])))
            E("pt_reeval", cur, tp, (sp["late"] if has_surg else sp["mid"])[:2], [re_cpt],
              "Therapy re-evaluation" + (" and discharge" if i == nvis - 1 else ""), frac=frac)
    mid_pcp = plus(t0, rng.randint(20, 40))
    E("office_visit", mid_pcp, pcp, sp["mid"][:2], ["99213"], "Primary care interval visit")
    E("office_visit", plus(cur, rng.randint(5, 20)), spec, sp["late"][:2], ["99214"],
      "Specialist final visit; maximum medical improvement discussed",
      plan="Maximum medical improvement anticipated. Home program. Return as needed. "
           "Future care may include periodic evaluation and therapy for flares.")
    evs.sort(key=lambda e: (e["date"], ["prior_visit", "lab", "er_visit", "imaging", "office_visit",
                                        "injection", "surgery", "pt_eval", "pt_visit",
                                        "pt_reeval"].index(e["kind"])))
    for i, e in enumerate(evs, 1):
        e["eid"] = f"e{i:03d}"
        e["claim_ref"] = f"{rng.randint(10 ** 9, 10 ** 10 - 1)}"
    C.events = evs

    # ---- clinical originals
    for e in evs:
        pv = e["pv"]
        clin = pv.clins[rng.randrange(len(pv.clins))]
        k = e["kind"]
        if k in ("prior_visit", "office_visit"):
            pages = office_pages(C, pv, e, clin, consult=e.get("consult", False))
            title = "CONSULTATION" if e.get("consult") else rng.choice(["OFFICE VISIT", "PROGRESS NOTE", "CLINIC NOTE"])
        elif k == "er_visit":
            pages = er_pages(C, pv, e, clin)
            title = "EMERGENCY PHYSICIAN RECORD" if pv.role == "er" else "URGENT CARE VISIT"
        elif k == "imaging":
            pages = imaging_pages(C, pv, e, pv.clins[0])
            title = "RADIOLOGY REPORT"
        elif k == "lab":
            pages = lab_pages(C, pv, e, pv.clins[0])
            title = "LABORATORY REPORT"
        elif k in ("pt_eval", "pt_reeval"):
            pages = ther_eval_pages(C, pv, e, pv.clins[0], re=(k == "pt_reeval"))
            title = "THERAPY EVALUATION" if k == "pt_eval" else "THERAPY RE-EVALUATION"
        elif k == "pt_visit":
            pages = ther_visit_page(C, pv, e, pv.clins[rng.randrange(len(pv.clins))])
            title = rng.choice(["DAILY TREATMENT NOTE"]) if pv.role != "chiro" else "CHIROPRACTIC VISIT NOTE"
        elif k == "injection":
            pages = inj_pages(C, pv, e, pv.clins[0])
            title = "PROCEDURE NOTE"
        else:
            pages = surg_pages(C, pv, e, e["surgeon"])
            title = "OPERATIVE RECORD"
        e["cids"] = new_orig(C, pv, "clinical", title, e["date"], clin, pages, event=e["eid"])
    # addenda: repeat the last page of a note and add a single line
    office = [e for e in evs if e["kind"] in ("office_visit", "injection") and e["date"] > acc]
    for e in rng.sample(office, min(len(office), rng.choice([1, 2]))):
        src = C.origs[e["cids"][-1]]
        ad_d = plus(e["date"], rng.randint(1, 4))
        line = L(f"ADDENDUM {fdate(ad_d, src['pv'].style['date_fmt'])}: " + rng.choice([
            "Patient called; symptoms unchanged, plan reviewed by phone.",
            "Imaging report received and reviewed; no change to plan.",
            "Work status form completed and faxed to employer.",
            "Corrected laterality in exam section: findings refer to the injured side."]))
        C.ocount += 1
        cid = f"c{C.ocount:03d}"
        o = dict(src)
        o.update(cid=cid, blocks=list(src["blocks"]) + [line], note=None)
        C.origs[cid] = o
        C.order.append(cid)
        e["cids"].append(cid)
    # ---- billing originals
    C.bill_by_prov = {}
    for r, pv in provs.items():
        pevs = [e for e in evs if e["pv"] is pv]
        if not pevs:
            continue
        cids = new_orig(C, pv, "billing", "STATEMENT", None, None, statement_pages(C, pv, pevs))
        claim_evs = [e for e in pevs if e["kind"] != "pt_visit"] + \
            [e for e in pevs if e["kind"] == "pt_visit"][:rng.randint(0, 4)]
        for e in claim_evs:
            cids += new_orig(C, pv, "billing", "CLAIM", e["date"], None, [claim_page(C, pv, e)])
        if claim_evs and rng.random() < 0.6:
            e = rng.choice(claim_evs)
            cids += new_orig(C, pv, "billing", "CLAIM", e["date"], None, [claim_page(C, pv, e, corrected=True)])
        C.bill_by_prov[r] = cids
    return C


# --------------------------------------------------------------------------
# Copy model
# --------------------------------------------------------------------------
OCR_CONF = [("rn", "m"), ("m", "rn"), ("cl", "d"), ("d", "cl"), ("w", "vv"), ("vv", "w"),
            ("h", "li"), ("li", "h"), ("O", "0"), ("0", "O"), ("l", "1"), ("1", "l"),
            ("I", "l"), ("l", "I"), ("S", "5"), ("5", "S"), ("B", "8"), ("8", "B")]


def ocr_text(s, rate, rng):
    out = []
    i = 0
    while i < len(s):
        cands = [(a, b) for a, b in OCR_CONF if s.startswith(a, i)]
        r = rng.random()
        if cands and r < rate:
            a, b = rng.choice(cands)
            out.append(b)
            i += len(a)
            continue
        ch = s[i]
        if ch == " " and r < rate * 0.7:
            i += 1  # merged words
            continue
        if ch.isalpha() and r < rate * 0.05:
            out.append(rng.choice("~^"))
            i += 1
            continue
        out.append(ch)
        if ch.isalpha() and rng.random() < rate * 0.12:
            out.append(" ")  # split word
        i += 1
    return "".join(out)


def ocr_rows(rows, rate, rng):
    rows = [dict(r) if "two" not in r else {"two": ([ocr_text(x, rate, rng) for x in r["two"][0]],
                                                    [ocr_text(x, rate, rng) for x in r["two"][1]])}
            for r in rows]
    for r in rows:
        if "t" in r:
            r["t"] = ocr_text(r["t"], rate, rng)
    # random hyphenation at line ends of paragraph text
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if a.get("p") and b.get("p") and rng.random() < 0.25:
            words = a["t"].split(" ")
            w = words[-1]
            if len(w) >= 7 and w.isalpha():
                k = rng.randint(3, len(w) - 3)
                a["t"] = " ".join(words[:-1] + [w[:k] + "-"])
                b["t"] = w[k:] + " " + b["t"]
    return rows


def compose(o, wrap, one_col):
    rows = list(o["head"])
    for blk in o["blocks"]:
        t = blk[0]
        if t == "p":
            for ln in textwrap.wrap(blk[1], wrap) or [""]:
                rows.append(R(ln, p=True))
        elif t == "l":
            rows.append(R(blk[1]))
        elif t == "h":
            rows.append(R(blk[1], b=True))
        elif t == "b":
            rows.append(R(""))
        elif t == "2":
            if one_col:
                rows += [R(x) for x in blk[1]] + [R("")] + [R(x) for x in blk[2]]
            else:
                rows.append({"two": (blk[1], blk[2])})
    rows.append(R(""))
    rows.append(dict(o["foot"]))
    return rows


BOLD = {"cour": "cobo", "helv": "hebo", "tiro": "tibo"}


def tlen(t, font):
    return fitz.get_text_length(t, fontname=font, fontsize=1)


def eff(cp):
    """Merge a copy's artefacts with those of the copy it was made from."""
    if cp.get("src") is None:
        e = dict(cp["p"])
        e.setdefault("stamps", [])
        e.setdefault("bates", [])
        e["bates"] = list(e["bates"]) + list(cp.get("bates_own", []))
        return e
    base = eff(cp["src"])
    own = cp["p"]
    e = dict(base)
    for k, v in own.items():
        if k in ("stamps",):
            e[k] = list(base.get(k, [])) + list(v)
        elif k == "ocr":
            e[k] = max(base.get("ocr", 0), v)
        elif k in ("fax",) and base.get("fax"):
            continue
        else:
            e[k] = v
    e["bates"] = list(base.get("bates", [])) + list(cp.get("bates_own", []))
    return e


def render(doc, C, cp, seed):
    rng = random.Random(seed)
    o = C.origs[cp["cid"]]
    st = o["pv"].style
    p = eff(cp)
    font = p.get("font", st["font"] if o["kind"] != "admin" else "tiro")
    size = p.get("size", st["size"] if o["kind"] != "admin" else 10.5)
    wrap = p.get("wrap", st["wrap"])
    rows = compose(o, wrap, p.get("one_col", False))
    ct, cb = p.get("crop_top", 0), p.get("crop_bot", 0)
    if ct:
        rows = rows[ct:]
    if cb:
        rows = rows[:-cb]
    if p.get("ocr"):
        rows = ocr_rows(rows, p["ocr"], rng)
    page = doc.new_page(width=W, height=H)
    fax = p.get("fax")
    top = 46 + (14 if fax and fax["style"] in ("A", "C", "D") else 0) + (16 if any(s["kind"] == "copy_top" for s in p["stamps"]) else 0)
    bot = H - 44 - (14 if fax and fax["style"] in ("B", "C") else 0) - (12 * len(p["bates"]) if p["bates"] else 0) \
        - (14 if p.get("printed") else 0) - (22 if any(s["kind"] == "recd_bottom" for s in p["stamps"]) else 0)
    nlines = sum(max(len(r["two"][0]), len(r["two"][1])) if "two" in r else 1 for r in rows)
    sz = min(size, (bot - top) / (max(nlines, 1) * 1.22))
    maxw = 1e-6
    for r in rows:
        if "two" in r:
            for x in r["two"][0] + r["two"][1]:
                maxw = max(maxw, tlen(x, font) * 2.08)
        else:
            maxw = max(maxw, tlen(r["t"], BOLD[font] if r["b"] else font))
    sz = max(5.0, min(sz, 512 / maxw))
    lh = sz * 1.22
    y = top + sz
    for r in rows:
        if "two" in r:
            lft, rgt = r["two"]
            for i, x in enumerate(lft):
                page.insert_text((50, y + i * lh), x, fontname=font, fontsize=sz)
            for i, x in enumerate(rgt):
                page.insert_text((316, y + i * lh), x, fontname=font, fontsize=sz)
            y += max(len(lft), len(rgt)) * lh
            continue
        fn = BOLD[font] if r["b"] else font
        x = 50
        if r["a"] == "c":
            x = max(20, (W - tlen(r["t"], fn) * sz) / 2)
        if r["t"]:
            page.insert_text((x, y), r["t"], fontname=fn, fontsize=sz)
        y += lh
    # handwritten-style margin note (present on original, may be absent on a copy, or added)
    note = None
    if o["note"] and not p.get("drop_note"):
        note = o["note"]
    elif p.get("add_note"):
        note = p["add_note"]
    if note:
        if o["note_pos"] == "side":
            page.insert_text((588, 560), note, fontname="tiit", fontsize=9, rotate=90)
        else:
            page.insert_text((300, H - 58), note, fontname="tiit", fontsize=9)
    draw_artifacts(page, p)


def draw_artifacts(page, p):
    fax = p.get("fax")
    if fax:
        s, i, n = fax["style"], fax["i"], fax["n"]
        if s == "A":
            t = f"{fax['date_us2']} {fax['time']}  FROM: {fax['from']}  {fax['sender'][:26].upper()}  P.{i:03d}/{n:03d}"
            page.insert_text((28, 22), t, fontname="cour", fontsize=7)
        elif s == "B":
            t = (f"RECEIVED {fax['date_dmy']} {fax['time12']} | From:{fax['from'].replace('-', '')} | "
                 f"To:{fax['to'].replace('-', '')} | Job {fax['job']} | Pg {i} of {n}")
            page.insert_text((28, H - 20), t, fontname="helv", fontsize=7)
        elif s == "C":
            page.insert_text((28, 22), f"** FAX ** {fax['date_iso']} {fax['time']}:{fax['sec']:02d}  TX#{fax['job']}  "
                                       f"{fax['sender'][:30]}", fontname="cour", fontsize=7)
            page.insert_text((W - 80, H - 20), f"{i:03d}/{n:03d}", fontname="cour", fontsize=8)
        else:  # D
            page.insert_text((28, 22), f"From: {fax['sender'][:30]}  Sent: {fax['date_long']} {fax['time12']}  "
                                       f"Page {i}/{n}  Subject: Medical Records", fontname="helv", fontsize=7)
    for s in p["stamps"]:
        k = s["kind"]
        if k == "recd_bottom":
            page.insert_text((400, H - 70), "+--------------------------+", fontname="cour", fontsize=8)
            page.insert_text((400, H - 60), f"|  {s['text']:<23} |", fontname="cobo", fontsize=8)
            page.insert_text((400, H - 50), "+--------------------------+", fontname="cour", fontsize=8)
        elif k == "scanned_side":
            page.insert_text((22, 600), s["text"], fontname="hebo", fontsize=8, rotate=90)
        elif k == "copy_top":
            t = s["text"]
            page.insert_text(((W - tlen(t, "hebo") * 14) / 2, 40), t, fontname="hebo", fontsize=14)
        elif k == "filed_side":
            page.insert_text((596, 200), s["text"], fontname="cour", fontsize=7, rotate=270)
        elif k == "dept_bottom":
            page.insert_text((50, H - 52), s["text"], fontname="hebo", fontsize=8)
    if p.get("printed"):
        page.insert_text((50, H - 34), p["printed"], fontname="helv", fontsize=6)
    used = {}
    for text, pos in p["bates"]:
        k = used.get(pos, 0)
        used[pos] = k + 1
        if pos == "tr":
            y = 36 + 11 * k
            page.insert_text((W - 36 - tlen(text, "hebo") * 9, y), text, fontname="hebo", fontsize=9)
        else:
            y = H - 26 - 11 * k
            x = {"bl": 36, "br": W - 36 - tlen(text, "hebo") * 9,
                 "bc": (W - tlen(text, "hebo") * 9) / 2}[pos]
            page.insert_text((x, y), text, fontname="hebo", fontsize=9)


def fax_meta(rng, sender, from_fax, to_fax, d):
    h = rng.randint(8, 17)
    m = rng.randint(0, 59)
    return dict(style=rng.choice("ABCD"), sender=sender, **{"from": from_fax}, to=to_fax,
                job=rng.randint(1000, 99999), date_us2=fdate(d, "us2"), date_dmy=f"{MON[d.month - 1]}-{d.day:02d}-{d.year}",
                date_iso=d.isoformat(), date_long=fdate(d, "long"), time=f"{h:02d}:{m:02d}",
                time12=f"{(h - 1) % 12 + 1:02d}:{m:02d}{'AM' if h < 12 else 'PM'}", sec=rng.randint(0, 59))


def mk(cid, prod, producer, mech, p=None, src=None, fax=None):
    p = dict(p or {})
    p.setdefault("stamps", [])
    return dict(cid=cid, prod=prod, producer=producer, mech=list(mech), p=p, src=src, fax=fax)


def plan_copies(C):
    rng = C.rng
    provs = C.provs
    evs = C.events
    last = max(e["date"] for e in evs)
    p1d = wkday(plus(last, rng.randint(25, 70)))
    p2d = wkday(plus(p1d, rng.randint(90, 200)))
    insd = wkday(plus(p1d, rng.randint(30, 120)))
    defd = wkday(plus(p2d, rng.randint(20, 90)))
    C.hipaa = new_orig(C, provs["pcp"], "admin", "HIPAA", None, None,
                       [hipaa_page(C, plus(last, rng.randint(5, 20)))])[0]
    ev_by_cid = {}
    for e in evs:
        for c in e["cids"]:
            ev_by_cid[c] = e

    def own_items(pv):
        """(date, cid) of a provider's own clinical pages, chronological."""
        out = []
        for e in evs:
            if e["pv"] is pv:
                out += [(e["date"], c) for c in e["cids"]]
        return out

    # what other providers keep in their charts
    holds = {"pcp": ["er_visit", "imaging", "surgery", "office_visit_spec", "lab"],
             C.sp["spec"]: ["er_visit", "imaging", "pt_reeval", "lab", "injection"],
             "pain": ["imaging", "office_visit_spec"], "asc": ["imaging", "office_visit_spec", "lab"]}
    for t in THERAPY_ROLES:
        holds[t] = ["office_visit_spec", "surgery"]

    def chart_copies(holder, prod):
        want = holds.get(holder.role, [])
        out = []
        for e in evs:
            if e["pv"] is holder:
                continue
            key = e["kind"]
            if key == "office_visit" and e["pv"].role == C.sp["spec"]:
                key = "office_visit_spec"
            if key not in want or rng.random() < 0.3:
                continue
            if e["kind"] == "er_visit":
                cids = [c for c in e["cids"] if "FLOWSHEET" not in str(C.origs[c]["blocks"][0])]
            elif e["kind"] == "surgery":
                cids = e["cids"][1:3]
            else:
                cids = e["cids"]
            sender = e["pv"]
            rd = plus(e["date"], rng.randint(1, 6))
            fx = fax_meta(rng, sender.name, sender.fax, holder.fax, rd)
            stk = rng.choice(["recd_bottom", "scanned_side", "copy_top", "filed_side", "dept_bottom"])
            text = {"recd_bottom": f"REC'D {MON[rd.month - 1].upper()} {rd.day:02d} {rd.year}",
                    "scanned_side": f"SCANNED INTO CHART {fdate(rd, 'us')} by {rng.choice(['kt', 'mjb', 'AR', 'lp'])}",
                    "copy_top": "C O P Y",
                    "filed_side": f"FILED {fdate(rd, 'iso')} / OUTSIDE RECORDS",
                    "dept_bottom": f"RECEIVED  MEDICAL RECORDS DEPT  {fdate(rd, 'dmy')}"}[stk]
            for c in cids:
                p = dict(stamps=[dict(kind=stk, text=text)], ocr=round(rng.uniform(0.01, 0.04), 3))
                mech = ["chart_copy", "stamp_" + stk, "fax_" + fx["style"], "ocr"]
                if C.origs[c]["note"] and rng.random() < 0.6:
                    p["drop_note"] = True
                    mech.append("note_absent")
                if rng.random() < 0.15:
                    p["crop_bot"] = rng.randint(1, 3)
                    mech.append("crop_bottom")
                out.append((e["date"], mk(c, prod, holder.name, mech, p, fax=fx)))
        return out

    def p1_block(pv):
        mode = rng.choice(["direct", "ehr_print", "fax"])
        fx = fax_meta(rng, pv.name, pv.fax, "555-0100", p1d) if mode == "fax" else None
        base = {}
        if mode == "ehr_print":
            base["printed"] = (f"Printed {fdate(p1d, 'us')} {rng.randint(8, 16):02d}:{rng.randint(0, 59):02d} "
                               f"by ROI\\{pv.roi.split()[0].lower()}  Source: EHR  Release #{rng.randint(1000, 9999)}")
        cover = new_orig(C, pv, "admin", "COVER", p1d, None,
                         [cover_letter(C, pv, p1d, C.req1[pv.role], plus(p1d, -rng.randint(14, 40)))])[0]
        cert = new_orig(C, pv, "admin", "CERT", p1d, None, [certification(C, pv, p1d)])[0]
        C.p1_admin[pv.role] = (cover, cert)
        items = [(None, mk(cover, 1, pv.name, ["direct"], base, fax=fx)),
                 (None, mk(cert, 1, pv.name, ["direct"], base, fax=fx))]
        if rng.random() < 0.55:
            items.append((None, mk(C.hipaa, 1, pv.name, ["attached_authorization"], base, fax=fx)))
        body = [(d, mk(c, 1, pv.name, [mode], base, fax=fx)) for d, c in own_items(pv)]
        body += chart_copies(pv, 1)
        body.sort(key=lambda x: x[0])
        bill = [(None, mk(c, 1, pv.name, [mode], base, fax=fx)) for c in C.bill_by_prov.get(pv.role, [])]
        return [x[1] for x in items + body + bill]

    def p2_block(pv):
        mode = rng.choice(["reprint_reflow", "fax", "scan_ocr", "scan_onecol_crop"])
        fx = fax_meta(rng, pv.name, pv.fax, "555-0177", p2d) if mode == "fax" else None
        base = {}
        mech = [mode]
        if mode == "reprint_reflow":
            st = pv.style
            base.update(font=rng.choice([f for f in ("cour", "helv", "tiro") if f != st["font"]]),
                        wrap=st["wrap"] + rng.choice([-30, -22, 18, 26]),
                        printed=f"Reprinted {fdate(p2d, 'iso')} -- second request -- {pv.name}")
        elif mode == "scan_ocr":
            base["ocr"] = round(rng.uniform(0.015, 0.05), 3)
        elif mode == "scan_onecol_crop":
            base.update(one_col=True, ocr=round(rng.uniform(0.01, 0.03), 3))
        cover = new_orig(C, pv, "admin", "COVER", p2d, None,
                         [cover_letter(C, pv, p2d, C.req2[pv.role], plus(p2d, -rng.randint(14, 40)))])[0]
        cert = new_orig(C, pv, "admin", "CERT", p2d, None, [certification(C, pv, p2d)])[0]
        out = [mk(cover, 2, pv.name, ["direct"], {}), mk(cert, 2, pv.name, ["direct"], {})]
        if rng.random() < 0.7:
            out.append(mk(C.hipaa, 2, pv.name, ["attached_authorization"], {"ocr": 0.01}))
        own = [c for _, c in own_items(pv)] + C.bill_by_prov.get(pv.role, [])
        if rng.random() < 0.4:
            own = own[::-1]
            mech = mech + ["reverse_order"]
        own += [cp["cid"] for _, cp in chart_copies(pv, 2)][: rng.randint(0, 6)]
        for c in own:
            p = dict(base)
            m = list(mech)
            if mode == "scan_onecol_crop" and rng.random() < 0.5:
                if rng.random() < 0.5:
                    p["crop_top"] = rng.randint(2, 4)
                    m.append("crop_top")
                else:
                    p["crop_bot"] = rng.randint(2, 4)
                    m.append("crop_bottom")
            if C.origs[c]["note"] and rng.random() < 0.4:
                p["drop_note"] = True
                m.append("note_absent")
            elif not C.origs[c]["note"] and C.origs[c]["kind"] == "clinical" and rng.random() < 0.05:
                p["add_note"] = f"2nd req - {rng.choice(['pg flagged', 'see prior prod', 'dup?'])} {fdate(p2d, 'us2')}"
                m.append("note_added")
            out.append(mk(c, 2, pv.name, m, p, fax=fx))
        return out

    C.p1_admin = {}
    C.req1 = {r: f"RR-{rng.randint(1000, 8999)}" for r in provs}
    C.req2 = {r: f"RR-{int(C.req1[r][3:]) + rng.randint(30, 900)}" for r in provs}
    blocks1 = [(pv, p1_block(pv)) for pv in provs.values()]
    p2_provs = [pv for pv in provs.values() if rng.random() < 0.65]
    if len(p2_provs) < 2:
        p2_provs = list(provs.values())[:3]
    blocks2 = [(pv, p2_block(pv)) for pv in p2_provs]
    # insurer claim file
    ins = []
    for pv in provs.values():
        for c in C.bill_by_prov.get(pv.role, []):
            if rng.random() < 0.85:
                ins.append(c)
    for e in evs:
        if e["kind"] in ("er_visit", "imaging", "surgery", "pt_eval", "injection") or \
                (e["kind"] == "office_visit" and rng.random() < 0.3):
            ins += [c for c in e["cids"] if rng.random() < 0.8]
    rng.shuffle(ins)
    ins_block = []
    for c in ins:
        p = {"ocr": round(rng.uniform(0.005, 0.03), 3)}
        m = ["insurer_file", "ocr"]
        if rng.random() < 0.3:
            p["stamps"] = [dict(kind="copy_top", text="COPY - CLAIM FILE")]
            m.append("stamp_copy_top")
        if rng.random() < 0.2:
            p["crop_top"] = rng.randint(1, 3)
            m.append("crop_top")
        if C.origs[c]["note"] and rng.random() < 0.5:
            p["drop_note"] = True
            m.append("note_absent")
        ins_block.append(mk(c, 3, C.insurer, m, p))
    sections = {"p1": blocks1, "p2": blocks2, "ins": ins_block}
    return sections, (p1d, p2d, insd, defd)


def assemble(C):
    rng = C.rng
    sections, dates = plan_copies(C)
    defd = dates[3]
    uniq = len(C.origs)
    lo, hi = max(250, int(uniq / 0.45) + 1), min(450, int(uniq / 0.25))
    target = rng.randint(lo, max(lo, hi - 20)) if lo <= hi else lo
    order_mode = rng.choice(["by_production", "by_provider"])
    p1 = [cp for _, blk in sections["p1"] for cp in blk]
    p2 = [cp for _, blk in sections["p2"] for cp in blk]
    ins = sections["ins"]
    mandatory = len(p1) + len(p2) + len(ins)
    # trim if over target (never touch production 1, which carries every original)
    while mandatory > target - 10 and (p2 or ins):
        pool = ins if len(ins) >= len(p2) // 2 and ins else p2
        k = rng.randrange(len(pool))
        if pool is p2 and pool[k]["mech"] == ["direct"]:
            if all(c["mech"] == ["direct"] for c in pool):
                break
            continue
        pool.pop(k)
        mandatory -= 1
    p2_set = {id(c) for c in p2}
    sections["p2"] = [(pv, [c for c in blk if id(c) in p2_set]) for pv, blk in sections["p2"]]
    # prior/defense counsel copy set: contiguous runs copied from earlier productions
    need = max(0, target - mandatory)
    src_pool = p1 + p2
    dfn = []
    while len(dfn) < need:
        start = rng.randrange(len(src_pool))
        run = src_pool[start:start + rng.randint(4, 22)][: need - len(dfn)]
        crop = rng.random() < 0.35
        for s in run:
            p = {"ocr": round(rng.uniform(0.02, 0.06), 3)}
            m = ["counsel_copy_of_p%d" % s["prod"], "ocr"]
            if rng.random() < 0.5:
                p["one_col"] = True
                m.append("one_column")
            if crop:
                key = rng.choice(["crop_top", "crop_bot"])
                p[key] = rng.randint(1, 4)
                m.append("crop_top" if key == "crop_top" else "crop_bottom")
            if rng.random() < 0.2:
                p["stamps"] = [dict(kind="copy_top", text="DEFENSE COPY")]
                m.append("stamp_copy_top")
            dfn.append(mk(s["cid"], 4, C.defense, m, p, src=s))
    # order
    out = []
    if order_mode == "by_production":
        groups = [p1, [c for _, b in sections["p2"] for c in b], ins, dfn]
        rest = groups[1:]
        rng.shuffle(rest)
        groups = [groups[0]] + rest
        for g in groups:
            out += g
    else:
        p2map = {pv.name: b for pv, b in sections["p2"]}
        for pv, b in sections["p1"]:
            out += b
            out += p2map.get(pv.name, [])
        tail = [ins, dfn]
        rng.shuffle(tail)
        for g in tail:
            out += g
    # fax page counters per transmission
    groups = {}
    for cp in out:
        if cp["fax"] is not None:
            groups.setdefault(id(cp["fax"]), []).append(cp)
    for g in groups.values():
        for i, cp in enumerate(g, 1):
            f = dict(cp["fax"])
            f.update(i=i, n=len(g))
            cp["p"]["fax"] = f
            if not any(x.startswith("fax") for x in cp["mech"]):
                cp["mech"].append("fax_" + f["style"])
            elif "fax" in cp["mech"]:
                cp["mech"][cp["mech"].index("fax")] = "fax_" + f["style"]
    # Bates schemes (one per production)
    L_ = C.pat["last"].upper()
    schemes = [lambda k: f"{L_} {k:06d}", lambda k: f"PLTF-{k:04d}", lambda k: f"MR{k:06d}",
               lambda k: f"{L_[:3]}_INS_{k:05d}", lambda k: f"DEF{k:05d}", lambda k: f"P{k:05d}"]
    poss = ["tr", "bl", "br", "bc"]
    rng.shuffle(poss)
    idx = list(range(len(schemes)))
    rng.shuffle(idx)
    counters = {}
    for prod in (1, 2, 3, 4):
        counters[prod] = [schemes[idx[prod - 1]], poss[(prod - 1) % 4], rng.randint(1, 900)]
    for cp in out:
        f, pos, k = counters[cp["prod"]]
        if cp["prod"] == 2 and rng.random() < 0.0:
            continue
        cp["bates_own"] = [(f(k), pos)]
        counters[cp["prod"]][2] += 1
    return out, order_mode


def check_distinct(C):
    """Different content ids must carry different text (look-alikes differ by at least a value)."""
    seen = {}
    for cid, o in C.origs.items():
        key = chr(10).join(r.get("t", "") if "t" in r else repr(r["two"]) for r in compose(o, 90, False)) + str(o["note"])
        if key in seen:
            raise SystemExit(f"alt-{C.n}: {cid} identical to {seen[key]}")
        seen[key] = cid


def write_case(n):
    C = build_case(n)
    copies, order_mode = assemble(C)
    check_distinct(C)
    case_dir = OUT / f"alt-{n}"
    case_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    pages = []
    for i, cp in enumerate(copies, 1):
        render(doc, C, cp, BASE_SEED * 1000 + n * 100003 + i)
        o = C.origs[cp["cid"]]
        pages.append(dict(page=i, content_id=cp["cid"], provider=cp["producer"], production=cp["prod"],
                          mechanism="+".join(cp["mech"]), doc_kind=o["kind"]))
    doc.save(case_dir / "records.pdf", garbage=3, deflate=True)
    doc.close()
    events = []
    for i, e in enumerate(C.events, 1):
        events.append(dict(event_id=e["eid"], date=tdate(e["date"]), provider=e["pv"].name, kind=e["kind"],
                           summary=e["summary"], codes=e["codes"], procedures=e["procs"],
                           doc_id=f"d{i:03d}", pages=e["cids"]))
    truth = dict(case_id=f"alt-{n}",
                 patient=dict(first=C.pat["first"], last=C.pat["last"], dob=C.pat["dob"]),
                 accident_date=tdate(C.acc), regions=C.sp["regions"], events=events, pages=pages)
    (case_dir / "truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
    uniq = len({p["content_id"] for p in pages})
    dup = 1 - uniq / len(pages)
    print(f"alt-{n}: {C.tname:<8} var{C.var} providers={len(C.provs)} pages={len(pages)} "
          f"unique_originals={uniq} duplicate%={dup * 100:.1f} order={order_mode}")
    return len(pages), uniq


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tp = tu = 0
    for n in range(1, N_CASES + 1):
        p, u = write_case(n)
        tp += p
        tu += u
    print(f"TOTAL pages={tp} unique={tu} duplicate%={(1 - tu / tp) * 100:.1f}")


if __name__ == "__main__":
    main()
