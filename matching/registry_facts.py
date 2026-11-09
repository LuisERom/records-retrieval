"""Print the facts about the cached registry data that the README cites, so
no number in the README is typed by hand.

    python registry_facts.py
"""
import json
from collections import Counter

from matcher import CACHE, load_locations


def main():
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    recs = raw["results"]
    loc = lambda r: next(a for a in r["addresses"] if a["address_purpose"] == "LOCATION")
    print(f"fetched {raw['fetched_at']} from {raw['source']}")
    for q in raw["queries"]:
        print(f"  query {q['query']!r}: {q['returned']} records")
    print(f"distinct NPI-2 records cached: {len(recs)}")

    legal = Counter(r["basic"].get("organization_name", "") for r in recs)
    name, n = legal.most_common(1)[0]
    print(f"most common legal name: {name!r} on {n} different NPIs")

    away = [r for r in recs if loc(r).get("state") != "NY"]
    places = Counter(f"{loc(r)['address_1']}, {loc(r)['city']} {loc(r)['state']}" for r in away)
    print(f"records whose primary practice address is outside NY: {len(away)}")
    for p, c in places.most_common(3):
        print(f"  {c:3d} at {p}")
    rescued = sum(1 for r in away if any(p.get("state") == "NY" for p in r.get("practiceLocations") or []))
    print(f"  of those, records that list a NY secondary practice location: {rescued}")

    with_fax = sum(1 for r in recs if loc(r).get("fax_number"))
    print(f"records with a fax number on the primary practice address: {with_fax} of {len(recs)}")

    locs = load_locations()
    print(f"records with no NY practice location at all (dropped): {len(recs) - len({l.npi for l in locs})}")
    print(f"practice locations the matcher can return that list a fax: "
          f"{sum(1 for l in locs if l.fax)} of {len(locs)}")
    by_addr = Counter((l.house, tuple(l.street), l.zip) for l in locs)
    (h, st, z), c = by_addr.most_common(1)[0]
    print(f"busiest street address: {h} {' '.join(st)} {z} with {c} NPIs")
    twins = Counter(l.twin_key for l in locs)
    groups = [k for k, v in twins.items() if v > 1]
    print(f"groups of 2+ NPIs with the same name on the door and same street address: "
          f"{len(groups)} groups, {sum(twins[k] for k in groups)} NPIs")


if __name__ == "__main__":
    main()
