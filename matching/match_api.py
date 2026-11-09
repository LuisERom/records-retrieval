"""Web API for the matcher, plus the built demo page.

    pip install -r requirements.txt
    uvicorn match_api:app --port 8010   # this part's API alone, run from its folder

The repo's web app serves this together with the other part: see ../api.py.

Routes:
    GET  /api/health    how many records are loaded, and the thresholds
    GET  /api/queries   the labeled test queries (data/queries.csv)
    POST /api/match     match one name + address; with query_id, also score it
                        against that query's label, the same way evaluate.py does

The matcher itself (matcher.py) is unchanged by this layer: the API calls
Matcher.match and adds display fields around it.
"""
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from evaluate import correct, gold, load
from matcher import Matcher, baseline, describe

DIST = Path(__file__).parent / "web" / "dist"

m = Matcher.from_cache()
QUERIES = {r["id"]: r for r in load("all")}


def is_pharmacy(taxonomy: str) -> bool:
    # Same rule as the strict line in evaluate.py.
    return "PHARMACY" in (taxonomy or "").upper()


class Location(BaseModel):
    npi: str
    name: str
    address: str
    city: str
    zip: str
    phone: str
    fax: str
    taxonomy: str
    is_pharmacy: bool
    score: Optional[float] = None


class MatchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=200)
    zip: str = Field(default="", max_length=10)
    query_id: Optional[str] = Field(default=None, max_length=20)


class Evaluation(BaseModel):
    query_id: str
    split: str
    expected: list[Location]          # the labeled records; empty = none is right
    label_method: str
    note: str
    matcher_correct: bool             # as evaluate.py scores it
    matcher_strict_correct: bool      # a pharmacy answer never counts
    baseline_correct: bool


class MatchResponse(BaseModel):
    answered: bool
    npi: Optional[str]
    reason: Optional[Literal["no_candidates", "low_score", "too_close"]]
    confidence: float
    margin: float
    min_score: float
    min_margin: float
    top: Optional[Location]
    same_in_registry: list[Location]  # records the registry cannot tell apart from top
    runners_up: list[Location]
    baseline: Optional[Location]      # what closest-name matching would pick
    evaluation: Optional[Evaluation] = None


class Query(BaseModel):
    id: str
    split: str
    name: str
    address: str
    zip: str
    expected_npi: str
    label_method: str
    note: str


class Health(BaseModel):
    npis: int
    locations: int
    queries: int
    min_score: float
    min_margin: float


def loc_model(d: dict, score: Optional[float] = None) -> Location:
    return Location(**{k: d[k] for k in ("npi", "name", "address", "city", "zip", "phone", "fax", "taxonomy")},
                    is_pharmacy=is_pharmacy(d["taxonomy"]), score=score)


def first_location(npi: str) -> Optional[Location]:
    loc = next((l for l in m.locs if l.npi == npi), None)
    return loc_model(describe(loc)) if loc else None


def twin_locations(top: dict, npis: list) -> list[Location]:
    """The twin records at the same street address as the top answer."""
    key = next(l.twin_key for l in m.locs
               if l.npi == top["npi"] and f"{l.address_1} {l.address_2}".strip() == top["address"])
    out = []
    for n in npis:
        loc = next((l for l in m.locs if l.npi == n and l.twin_key == key), None)
        if loc:
            out.append(loc_model(describe(loc)))
    return out


app = FastAPI(title="provider-match", description="Match a messy provider name and address to an NPI Registry location.")


@app.get("/api/health", response_model=Health)
def health():
    return Health(npis=len({l.npi for l in m.locs}), locations=len(m.locs), queries=len(QUERIES),
                  min_score=m.p["min_score"], min_margin=m.p["min_margin"])


@app.get("/api/queries", response_model=list[Query])
def queries(split: Literal["dev", "test", "all"] = "test"):
    return [Query(id=r["id"], split=r["split"], name=r["query_name"], address=r["query_address"],
                  zip=r["query_zip"], expected_npi=r["expected_npi"], label_method=r["label_method"],
                  note=r["note"])
            for r in QUERIES.values() if split == "all" or r["split"] == split]


@app.post("/api/match", response_model=MatchResponse)
def match(req: MatchRequest):
    row = None
    if req.query_id is not None:
        row = QUERIES.get(req.query_id)
        if row is None:
            raise HTTPException(404, f"no query with id {req.query_id!r}")
    res = m.match(req.name, req.address, req.zip)
    base_npi = baseline(m.locs, req.name)
    top = res["top"]
    out = MatchResponse(
        answered=res["npi"] is not None,
        npi=res["npi"],
        reason=res["reason"],
        confidence=res["confidence"],
        margin=res["margin"],
        min_score=m.p["min_score"],
        min_margin=m.p["min_margin"],
        top=loc_model(top) if top else None,
        same_in_registry=twin_locations(top, res["same_in_registry"]) if top else [],
        runners_up=[loc_model(r, r["score"]) for r in res["runners_up"]],
        baseline=first_location(base_npi) if base_npi else None,
    )
    if row is not None:
        ok = gold(m.locs, row)
        exp = [] if ok is None else [x for n in row["expected_npi"].split(";") if (x := first_location(n.strip()))]
        pharm = out.top is not None and out.top.is_pharmacy
        out.evaluation = Evaluation(
            query_id=row["id"], split=row["split"], expected=exp, label_method=row["label_method"],
            note=row["note"],
            matcher_correct=correct(res["npi"], ok),
            matcher_strict_correct=correct(res["npi"], ok) and not (res["npi"] and pharm),
            baseline_correct=correct(base_npi, ok),
        )
    return out


class ExplainCandidate(BaseModel):
    npi: str
    name: str
    address: str
    taxonomy: str
    name_forward: float      # share of the typed words found in the record's names and specialty
    name_reverse: float      # share of the record's own name that was typed
    name_score: float
    address_score: Optional[float]
    total: float
    same_as_top: bool        # same name on the door and street address as the top record


class Explain(BaseModel):
    typed_name: str
    typed_address: str
    typed_zip: str
    name_tokens: list[str]
    house: str
    street: list[str]
    zip: str
    blocked_by: Literal["zip and street", "zip", "street", "nothing usable: every location"]
    pharmacies_skipped: int    # pharmacies and suppliers left out (matcher v2 rule)
    candidates_considered: int
    locations_total: int
    weights: dict
    candidates: list[ExplainCandidate]
    min_score: float
    min_margin: float
    top_score: float
    next_different_score: float
    margin: float
    answered: bool
    reason: Optional[str]
    baseline_name: Optional[str]


@app.post("/api/match/explain", response_model=Explain)
def explain(req: MatchRequest):
    """The matcher's intermediate results for one lookup, step by step. Recomputed with
    the matcher's own functions; the decision itself comes from Matcher.match."""
    from matcher import SUPPLY_WORDS, clean, norm_name, norm_street, token_score, zip5
    qn = norm_name(req.name)
    skip_supply = m.p["exclude_supply"] and not (set(clean(req.name).split()) & SUPPLY_WORDS)
    house, street = norm_street(req.address)
    z = zip5(req.zip)
    idx = m.candidates(house, street, z)
    by_zip = bool(z and m.by_zip.get(z))
    by_street = bool(house and m.by_street.get((house, street[0] if street else "")))
    blocked = ("zip and street" if by_zip and by_street else "zip" if by_zip else "street" if by_street
               else "nothing usable: every location")
    w, rw = m.p["name_weight"], m.p["reverse_weight"]
    best = {}
    skipped = set()
    for i in idx:
        loc = m.locs[i]
        if skip_supply and loc.supply_only:
            skipped.add(loc.npi)
            continue
        fwd = token_score(qn, loc.name_tokens)
        rev = token_score(loc.display_tokens, qn)
        ns = (1 - rw) * fwd + rw * rev
        a = m.address_score(house, street, z, loc)
        total = ns if a is None else w * ns + (1 - w) * a
        if loc.npi not in best or total > best[loc.npi][0]:
            best[loc.npi] = (total, loc, fwd, rev, ns, a)
    ranked = sorted(best.values(), key=lambda x: (-x[0], x[1].npi))
    top_key = ranked[0][1].twin_key if ranked else None
    res = m.match(req.name, req.address, req.zip)
    base = baseline(m.locs, req.name)
    base_loc = first_location(base) if base else None
    cands = [ExplainCandidate(npi=loc.npi, name=describe(loc)["name"], address=describe(loc)["address"],
                              taxonomy=loc.taxonomy, name_forward=round(fwd, 3), name_reverse=round(rev, 3),
                              name_score=round(ns, 3), address_score=None if a is None else round(a, 3),
                              total=round(t, 3), same_as_top=k > 0 and loc.twin_key == top_key)
             for k, (t, loc, fwd, rev, ns, a) in enumerate(ranked[:8])]
    return Explain(typed_name=req.name, typed_address=req.address, typed_zip=req.zip, name_tokens=qn, house=house,
                   street=street, zip=z, blocked_by=blocked, candidates_considered=len(best), pharmacies_skipped=len(skipped),
                   locations_total=len({l.npi for l in m.locs}), weights={"name": w, "address": round(1 - w, 2),
                                                                         "reverse_share_of_name": rw},
                   candidates=cands, min_score=m.p["min_score"], min_margin=m.p["min_margin"],
                   top_score=res["confidence"], next_different_score=round(res["confidence"] - res["margin"], 3),
                   margin=res["margin"], answered=res["npi"] is not None, reason=res["reason"],
                   baseline_name=base_loc.name if base_loc else None)


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
