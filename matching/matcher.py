"""Match a messy provider name + address (as typed on an intake form) to an
NPI Registry organization record.

    from matcher import Matcher
    m = Matcher.from_cache()
    m.match("NYU Langone ortho", "333 E 38th St", "10016")

Pipeline: normalize -> block candidates on ZIP and street -> score name and
address similarity per location -> keep each NPI's best location -> return
the top NPI, a confidence, and runners-up, or "no confident match" when the
top score is low or the top two are too close to call.
"""
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

CACHE = Path(__file__).parent / "data" / "npi_raw.json"

# Tuned on the dev split only (see tune.py); the held-out test split is never
# used to pick these.
DEFAULTS = {"name_weight": 0.7, "reverse_weight": 0.25, "min_score": 0.6, "min_margin": 0.04,
            "exclude_supply": True}
# v1 (2026-11-08) had no supply rule. The scores and thresholds above are unchanged from v1.
V1 = {**DEFAULTS, "exclude_supply": False}

# Entities that never hold a patient's treatment records: a records request does not go there.
# A record counts as supply-only when every type it lists is one of these.
SUPPLY_TYPES = ("PHARMACY", "DURABLE MEDICAL EQUIPMENT", "PROSTHETIC/ORTHOTIC SUPPLIER")
# ...unless the person typed one of these words, which means they did ask for such a place.
SUPPLY_WORDS = {"PHARMACY", "PHARM", "RX", "SUPPLY", "SUPPLIES", "EQUIPMENT", "DME", "PROSTHETIC",
                "PROSTHETICS", "ORTHOTIC", "ORTHOTICS"}

STREET_ABBR = {
    "STREET": "ST", "STR": "ST", "AVENUE": "AVE", "AV": "AVE", "AVEN": "AVE",
    "BOULEVARD": "BLVD", "ROAD": "RD", "PLACE": "PL", "DRIVE": "DR",
    "PARKWAY": "PKWY", "HIGHWAY": "HWY", "TURNPIKE": "TPKE", "LANE": "LN",
    "COURT": "CT", "SQUARE": "SQ", "PLAZA": "PLZ", "TERRACE": "TER",
    "EXPRESSWAY": "EXPY", "CENTER": "CTR", "CENTRE": "CTR",
    "EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S",
    "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5",
    "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8", "NINTH": "9", "TENTH": "10",
}
STREET_TYPES = {"ST", "AVE", "BLVD", "RD", "PL", "DR", "PKWY", "HWY", "TPKE",
                "LN", "CT", "SQ", "PLZ", "TER", "EXPY"}
DIRECTIONS = {"E", "W", "N", "S"}
UNIT_WORDS = {"SUITE", "STE", "FLOOR", "FL", "FLR", "ROOM", "RM", "UNIT",
              "APT", "BLDG", "BUILDING", "DEPT", "LEVEL", "LBBY", "LOBBY", "#"}
NAME_EXPAND = [
    (r"\bNEW YORK UNIVERSITY\b", "NYU"),
    (r"\bN Y U\b", "NYU"),
    (r"\bNYULH\b", "NYU LANGONE HOSPITALS"),
    (r"\bNYULMC\b", "NYU LANGONE MEDICAL CENTER"),
    (r"\bLONG ISLAND\b", "LI"),
    (r"\bMEDICAL\b", "MED"),
    (r"\bMED CTR\b", "MED CENTER"),
    (r"\bCTR\b", "CENTER"),
    (r"\bHOSP\b", "HOSPITAL"),
    (r"\bASSOC\b", "ASSOCIATES"),
    (r"\b(ORTHOPAEDIC|ORTHOPEDIC|ORTHOPAEDICS|ORTHOPEDICS)\b", "ORTHO"),
    (r"\bPEDIATRICS?\b", "PEDS"),
    (r"\bCARDIOLOGY\b", "CARDIO"),
    # Added after dev-set misses (q015, q032, q114, q130); test set not used.
    (r"\b(GASTROENTEROLOGY|GASTROINTESTINAL|GI)\b", "GASTRO"),
    (r"\bCT\b", "CARDIOTHORACIC"),
]
NAME_STOP = {"THE", "OF", "AT", "AND", "INC", "LLC", "PC", "PLLC", "P", "C",
             "CORP", "CORPORATION", "DBA", "A", "FOR", "CO"}


def clean(s):
    s = (s or "").upper().replace("&", " AND ")
    return re.sub(r"[^A-Z0-9# ]+", " ", s)


def norm_name(s):
    s = clean(s)
    for pat, rep in NAME_EXPAND:
        s = re.sub(pat, rep, s)
    return [t for t in s.split() if t not in NAME_STOP]


def norm_street(s):
    """Return (house_number, street_tokens) with the suite/floor part dropped."""
    toks = clean(s).replace("#", " # ").split()
    out = []
    for i, t in enumerate(toks):
        if t in UNIT_WORDS:
            break  # everything after a unit word is the suite/floor
        t = re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", t)
        t = STREET_ABBR.get(t, t)
        out.append(t)
        if t in STREET_TYPES and len(out) > 2:
            # "530 1ST AVE HCC 3B": stop at the street type, keeping one
            # trailing direction ("222 STATION PLZ N").
            nxt = STREET_ABBR.get(toks[i + 1], toks[i + 1]) if i + 1 < len(toks) else ""
            if nxt in DIRECTIONS:
                out.append(nxt)
            break
    house = out[0] if out and re.fullmatch(r"\d+[A-Z]?", out[0]) else ""
    rest = out[1:] if house else out
    return house, rest


def zip5(z):
    m = re.match(r"\d{5}", (z or "").strip())
    return m.group(0) if m else ""


def ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def token_score(q, c):
    """How well query tokens are covered by candidate tokens (0..1).
    Each query token takes its best match in the candidate; a token that is a
    prefix of a candidate token ("ORTHO" / "ORTHOPEDIC", "PEDS") counts fully.
    Order-free, so "Langone NYU" == "NYU Langone"."""
    if not q or not c:
        return 0.0
    tot = 0.0
    for t in q:
        best = 0.0
        for u in c:
            if t == u or (len(t) >= 3 and u.startswith(t)):
                best = 1.0
                break
            best = max(best, ratio(t, u))
        tot += best if best >= 0.75 else 0.0  # weak fuzzy hits count as misses
    return tot / len(q)


@dataclass
class Location:
    npi: str
    name: str             # registry organization name
    other_names: list
    taxonomy: str
    address_1: str
    address_2: str
    city: str
    zip: str
    phone: str
    fax: str
    name_tokens: list = field(default_factory=list)
    house: str = ""
    street: list = field(default_factory=list)
    display_tokens: list = field(default_factory=list)
    twin_key: tuple = ()  # same display name + same street address + ZIP
    supply_only: bool = False  # every listed type is a pharmacy or supplier (SUPPLY_TYPES)


def display_name(name, others):
    """The name a person would see on the door: the first DBA if the record
    has one, else the legal name (many records are legally just "NEW YORK
    UNIVERSITY", so the DBA is what tells them apart)."""
    return others[0] if others else name


def load_locations(path=CACHE):
    """One row per (NPI, practice location). Primary LOCATION address plus any
    secondary practiceLocations the record lists. Mailing addresses skipped."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["results"]
    locs = []
    for r in raw:
        b = r.get("basic", {})
        name = b.get("organization_name", "")
        others = [o.get("organization_name", "") for o in r.get("other_names", [])
                  if o.get("organization_name")]
        tax = "; ".join(t.get("desc") or "" for t in r.get("taxonomies") or [])
        addrs = [a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"]
        addrs += r.get("practiceLocations", []) or []
        seen = set()
        for a in addrs:
            if a.get("state") != "NY":
                continue
            key = (a.get("address_1", "").upper(), zip5(a.get("postal_code")))
            if key in seen:
                continue
            seen.add(key)
            loc = Location(r["number"] if isinstance(r["number"], str) else str(r["number"]),
                           name, others, tax, a.get("address_1", ""),
                           a.get("address_2", ""), a.get("city", ""),
                           zip5(a.get("postal_code")), a.get("telephone_number", ""),
                           a.get("fax_number", ""))
            loc.name_tokens = norm_name(" ".join([name] + others + [tax]))
            loc.house, loc.street = norm_street(loc.address_1)
            loc.display_tokens = norm_name(display_name(name, others))
            types = [t.strip().upper() for t in tax.split(";") if t.strip()]
            loc.supply_only = bool(types) and all(t.startswith(SUPPLY_TYPES) for t in types)
            loc.twin_key = (" ".join(loc.display_tokens),
                            loc.house, tuple(loc.street), loc.zip)
            locs.append(loc)
    return locs


class Matcher:
    def __init__(self, locations, **params):
        self.locs = locations
        self.p = {**DEFAULTS, **params}
        self.by_zip, self.by_street = {}, {}
        for i, l in enumerate(locations):
            self.by_zip.setdefault(l.zip, []).append(i)
            if l.house:
                self.by_street.setdefault((l.house, l.street[0] if l.street else ""), []).append(i)

    @classmethod
    def from_cache(cls, path=CACHE, **params):
        return cls(load_locations(path), **params)

    def candidates(self, house, street, z):
        """Blocking: same ZIP, or same house number + first street token.
        Falls back to everything when the query gives no usable address."""
        idx = set(self.by_zip.get(z, [])) if z else set()
        if house:
            idx |= set(self.by_street.get((house, street[0] if street else ""), []))
        return idx if idx else set(range(len(self.locs)))

    def address_score(self, house, street, z, loc):
        if not (house or street or z):
            return None  # no address given: name decides alone
        s = 0.0
        s += 0.4 if house and house == loc.house else 0.0
        s += 0.4 * token_score(street, loc.street) if street else 0.0
        s += 0.2 if z and z == loc.zip else 0.0
        if not house:
            s = s / 0.6 if (street and z) else s / 0.4 if (street or z) else s
        return min(s, 1.0)

    def match(self, name, address="", zipcode="", k=3):
        qn = norm_name(name)
        house, street = norm_street(address)
        z = zip5(zipcode)
        w = self.p["name_weight"]
        best = {}  # npi -> (score, loc)
        skip_supply = self.p["exclude_supply"] and not (set(clean(name).split()) & SUPPLY_WORDS)
        for i in self.candidates(house, street, z):
            loc = self.locs[i]
            if skip_supply and loc.supply_only:
                continue
            # Forward: are the typed words in the record (any of its names or
            # its specialty)? Reverse: how much of the name on the door did
            # the person type? Reverse breaks ties like "NYU Cardiology
            # Associates" vs "NYU Cardiothoracic Surgery Associates" (added
            # after dev-set ties).
            rw = self.p["reverse_weight"]
            ns = (1 - rw) * token_score(qn, loc.name_tokens) + rw * token_score(loc.display_tokens, qn)
            a = self.address_score(house, street, z, loc)
            score = ns if a is None else w * ns + (1 - w) * a
            if loc.npi not in best or score > best[loc.npi][0]:
                best[loc.npi] = (score, loc)
        ranked = sorted(best.values(), key=lambda x: (-x[0], x[1].npi))
        top = ranked[0] if ranked else (0.0, None)
        # Records the registry cannot tell apart (same name on the door, same
        # street address) are reported together instead of forcing a coin
        # flip; the margin is measured against the best *different* record.
        twins = [l.npi for _, l in ranked[1:] if top[1] and l.twin_key == top[1].twin_key]
        others = [(s, l) for s, l in ranked[1:] if l.npi not in twins]
        second = others[0][0] if others else 0.0
        margin = top[0] - second
        confident = top[0] >= self.p["min_score"] and margin >= self.p["min_margin"]
        # Why it held back, for display only; decided on the unrounded scores.
        reason = (None if (confident and top[1]) else "no_candidates" if not top[1]
                  else "low_score" if top[0] < self.p["min_score"] else "too_close")
        return {
            "npi": top[1].npi if (confident and top[1]) else None,
            "reason": reason,
            "same_in_registry": twins if confident else [],
            "confidence": round(top[0], 3),
            "margin": round(margin, 3),
            "top": describe(top[1]) if top[1] else None,
            "runners_up": [dict(describe(l), score=round(s, 3)) for s, l in others[:k - 1]],
        }


def describe(l):
    return {"npi": l.npi, "name": display_name(l.name, l.other_names), "address": f"{l.address_1} {l.address_2}".strip(),
            "city": l.city, "zip": l.zip, "phone": l.phone, "fax": l.fax, "taxonomy": l.taxonomy}


def baseline(locations, name):
    """Closest name only: fuzzy string ratio of the typed name against each
    record's legal name and DBA names, best one wins. Ignores the address and
    never abstains. This is roughly what a search box over the registry gives."""
    q = " ".join(norm_name(name))
    best, best_s = None, -1.0
    for l in locations:
        for n in [l.name] + l.other_names:
            s = ratio(q, " ".join(norm_name(n)))
            if s > best_s:
                best, best_s = l.npi, s
    return best


def acceptable(locations, npi):
    """The labeled NPI plus any record the registry cannot tell apart from it
    (same name on the door and same street address). Computed from the
    records alone, never from what the matcher returned."""
    keys = {l.twin_key for l in locations if l.npi == npi}
    return {npi} | {l.npi for l in locations if l.twin_key in keys}


if __name__ == "__main__":
    import sys
    m = Matcher.from_cache()
    args = sys.argv[1:] + ["", "", ""]
    print(json.dumps(m.match(args[0], args[1], args[2]), indent=1))
