"""Pull NYU Langone organization (NPI-2) records in New York State from the
public NPI Registry API and cache them to data/npi_raw.json.

Run once (needs internet). Everything else in this repo runs offline from
the cache, so results are repeatable.

    python fetch_npi.py

The registry API returns at most 200 records per call and lets you skip at
most 1000, so one query can return at most 1200 records. Each query below
is paged until it runs dry; if a query hits the 1200 ceiling it is split by
city so nothing is silently cut off.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://npiregistry.cms.hhs.gov/api/"
OUT = Path(__file__).parent / "data" / "npi_raw.json"

# Name searches that cover the NYU Langone system, including the names its
# acquired hospitals used to carry. The registry's wildcard needs 2+ letters
# before the *.
QUERIES = [
    "NYU*",
    "NEW YORK UNIVERSITY*",
    "LANGONE*",
    "WINTHROP*",
    "LUTHERAN MEDICAL*",
    "LUTHERAN AUGUSTANA*",
    "FAMILY HEALTH CENTERS AT NYU*",
    "HOSPITAL FOR JOINT DISEASES*",
    "RUSK*",
]


def call(params):
    q = {"version": "2.1", "enumeration_type": "NPI-2", "state": "NY", "limit": 200}
    q.update(params)
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "provider-match/0.1"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network hiccup: back off and retry
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def page_all(params):
    out = []
    for skip in range(0, 1001, 200):
        d = call({**params, "skip": skip})
        if d.get("Errors"):
            raise RuntimeError(f"{params}: {d['Errors']}")
        batch = d.get("results", [])
        out.extend(batch)
        time.sleep(0.4)
        if len(batch) < 200:
            return out, False
    return out, True  # hit the 1200 ceiling


def main():
    records = {}
    log = []
    for name in QUERIES:
        got, capped = page_all({"organization_name": name})
        if capped:
            cities = sorted({a.get("city", "") for r in got for a in r.get("addresses", [])
                             if a.get("address_purpose") == "LOCATION"})
            got = []
            for city in cities:
                part, capped2 = page_all({"organization_name": name, "city": city})
                if capped2:
                    print(f"WARNING: {name} / {city} still capped at 1200")
                got.extend(part)
        for r in got:
            records[r["number"]] = r
        log.append({"query": name, "returned": len(got), "split_by_city": capped})
        print(f"{name:35s} {len(got):5d} records{'  (split by city)' if capped else ''}")
    OUT.parent.mkdir(exist_ok=True)
    payload = {
        "source": API + "?version=2.1",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "queries": log,
        "results": sorted(records.values(), key=lambda r: r["number"]),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"distinct NPIs cached: {len(records)} -> {OUT}")


if __name__ == "__main__":
    main()
