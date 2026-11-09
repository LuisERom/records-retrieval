"""Generate intake-style test queries by script, from the registry records.

    python gen_queries.py          # writes data/queries_generated.csv

Why a script: the 245 queries in data/queries.csv were written by hand, by the
same session that built the matcher, and their misses were then inspected.
These are made by fixed, seeded rules instead, so nobody chooses which
queries are easy, and there are enough of them (1,000) for steady numbers.
They are the held-out set for matcher v2: no setting was tuned on them.

Each query starts from one care-providing location in the registry cache (the
place a patient was actually treated; pharmacies and suppliers are not
sampled, since an intake form names where care happened). Then, at random:
- the name: the name on the door, or the legal name when it is specific;
  common abbreviations (Center -> Ctr, Associates -> Assoc, Orthopaedic ->
  Ortho, Medical -> Med, Hospital -> Hosp, and -> &); "NYU" / "Langone" /
  "Health" dropped, or "NYU Langone" put in front; cut to its first words;
  zero to two typos (swapped, dropped or doubled letters); any casing;
- the address: street words abbreviated or spelled out (Street/St,
  East/E, First/1st...), suite or floor kept or dropped, the house number
  occasionally dropped, the whole address occasionally missing;
- the ZIP: kept, missing, or written as ZIP+4.
About 8% are providers outside NYU Langone at NYC addresses; for those the
right answer is to abstain.

The label is the NPI the query was made from. As in evaluate.py, a record the
registry cannot tell apart from it (same name on the door, same street
address) also counts as right.
"""
import csv
import random
import re
from pathlib import Path

from matcher import load_locations

OUT = Path(__file__).parent / "data" / "queries_generated.csv"
SEED = 20261109
N = 1000
NEGATIVE_SHARE = 0.08

ABBR = [(r"\bCENTER\b", "Ctr"), (r"\bASSOCIATES\b", "Assoc"), (r"\bORTHOPA?EDICS?\b", "Ortho"),
        (r"\bMEDICAL\b", "Med"), (r"\bHOSPITAL\b", "Hosp"), (r"\bAND\b", "&"), (r"\bDEPARTMENT\b", "Dept"),
        (r"\bPHYSICAL THERAPY\b", "PT"), (r"\bREHABILITATION\b", "Rehab"), (r"\bSURGERY\b", "Surg")]
STREET_FORMS = {"ST": ["St", "Street", "St."], "STREET": ["St", "Street"], "AVE": ["Ave", "Avenue", "Av"],
                "AVENUE": ["Ave", "Avenue"], "E": ["E", "East", "E."], "EAST": ["E", "East"], "W": ["W", "West"],
                "WEST": ["W", "West"], "N": ["N", "North"], "S": ["S", "South"], "BLVD": ["Blvd", "Boulevard"],
                "RD": ["Rd", "Road"], "PL": ["Pl", "Place"], "PKWY": ["Pkwy", "Parkway"], "1ST": ["1st", "First"],
                "2ND": ["2nd", "Second"], "3RD": ["3rd", "Third"], "FIRST": ["1st", "First"]}
UNIT = re.compile(r"\b(SUITE|STE|FLOOR|FL|FLR|ROOM|RM|UNIT|#)\b.*$", re.I)
OTHER_SYSTEMS = ["Mount Sinai Hospital", "Mount Sinai Doctors", "NewYork-Presbyterian Weill Cornell",
                 "Lenox Hill Hospital", "Montefiore Medical Center", "Maimonides Medical Center",
                 "Northwell Health Physician Partners", "Hospital for Special Surgery", "Brooklyn Hospital Center",
                 "Bellevue Hospital", "SUNY Downstate Health", "CityMD Urgent Care", "ColumbiaDoctors",
                 "Kings County Hospital"]
NYC_STREETS = ["Broadway", "Madison Ave", "Lexington Ave", "Atlantic Ave", "Flatbush Ave", "Ocean Pkwy",
               "W 57th St", "E 86th St", "Amsterdam Ave", "Kings Hwy", "Court St", "Queens Blvd"]
NYC_ZIPS = ["10003", "10011", "10019", "10021", "10025", "10029", "10032", "10065", "11201", "11203", "11215",
            "11230", "11375", "10461", "10301"]


def typo(word, r):
    if len(word) < 5:
        return word
    i = r.randrange(1, len(word) - 1)
    kind = r.choice(["swap", "drop", "double"])
    if kind == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if kind == "drop":
        return word[:i] + word[i + 1:]
    return word[:i] + word[i] + word[i:]


def messy_name(loc, r):
    name = loc.other_names[0] if loc.other_names else loc.name
    if loc.other_names and r.random() < 0.15 and "NEW YORK UNIVERSITY" not in loc.name.upper():
        name = loc.name
    s = name.upper()
    for pat, rep in ABBR:
        if r.random() < 0.45:
            s = re.sub(pat, rep.upper(), s)
    words = s.split()
    roll = r.random()
    if roll < 0.25:
        words = [w for w in words if w not in {"NYU", "LANGONE", "HEALTH", "NYULH"}] or words
    elif roll < 0.40 and "NYU" not in words:
        words = ["NYU", "LANGONE"] + words
    if r.random() < 0.20 and len(words) > 3:
        words = words[: r.randint(2, len(words) - 1)]
    for _ in range(r.choice([0, 0, 1, 1, 2])):
        k = r.randrange(len(words))
        words[k] = typo(words[k], r)
    s = " ".join(words)
    case = r.random()
    return s.lower() if case < 0.3 else s.title() if case < 0.8 else s


def messy_address(loc, r):
    if r.random() < 0.10:
        return ""
    a = loc.address_1.upper().replace(",", " ")
    if r.random() < 0.6:
        a = UNIT.sub("", a)
    elif loc.address_2:
        a = f"{a} {loc.address_2.upper()}"
    out = []
    for w in a.split():
        forms = STREET_FORMS.get(w)
        out.append(r.choice(forms) if forms else w.title() if not w[0].isdigit() else w.lower())
    if r.random() < 0.07 and out and out[0][0].isdigit():
        out = out[1:]
    return " ".join(out).strip()


def messy_zip(loc, r):
    roll = r.random()
    if roll < 0.25:
        return ""
    if roll < 0.30:
        return f"{loc.zip}-{r.randint(1000, 9999)}"
    return loc.zip


def main():
    r = random.Random(SEED)
    locs = [l for l in load_locations() if not l.supply_only]
    by_npi = {}
    for l in locs:
        by_npi.setdefault(l.npi, []).append(l)
    npis = sorted(by_npi)
    rows = []
    for i in range(N):
        qid = f"g{i + 1:04d}"
        if r.random() < NEGATIVE_SHARE:
            name = r.choice(OTHER_SYSTEMS)
            name = name if r.random() < 0.7 else typo(name, r)
            addr = f"{r.randint(1, 1999)} {r.choice(NYC_STREETS)}" if r.random() < 0.8 else ""
            rows.append([qid, "test", name, addr, r.choice(NYC_ZIPS) if r.random() < 0.7 else "", "NONE",
                         "generated_not_nyu", "provider outside NYU Langone"])
            continue
        loc = r.choice(by_npi[r.choice(npis)])
        rows.append([qid, "test", messy_name(loc, r), messy_address(loc, r), messy_zip(loc, r), loc.npi,
                     "generated_from_record", f"from {loc.npi} at {loc.address_1}"])
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "query_name", "query_address", "query_zip", "expected_npi", "label_method", "note"])
        w.writerows(rows)
    neg = sum(1 for x in rows if x[5] == "NONE")
    print(f"wrote {len(rows)} queries ({neg} outside NYU Langone) to {OUT}")


if __name__ == "__main__":
    main()
