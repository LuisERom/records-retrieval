# Part 1: find the provider (matching/)

Part of [records-retrieval](../README.md). Run the commands below from this `matching/` folder.

Match a provider name and address the way someone types it on an intake form ("NYU Langone ortho, 333 E 38th") to the right NYU Langone location in the public NPI Registry. When it can't tell, it says "no confident match" instead of guessing.

## The problem

Codes Health's Software Engineer posting names it: *"Matching patients and facilities across messy provider networks, where a single system like NYU Langone is 340+ care locations with no clean way to match them."* A records request sent to the wrong location costs days, so what matters is getting the right location, and saying so when it can't be pinned down.

## Result

### The headline: 1,000 script-generated held-out queries

`python evaluate.py --queries generated` prints (full output with every miss: `results/evaluate_generated.txt`):

```
queries: generated  split: test  queries: 1000  (of which 66 have no right record)
| method                  | correct      | accuracy | answered | right when it answered | confidently wrong |
|-------------------------|--------------|----------|----------|------------------------|-------------------|
| baseline (closest name) |  603 / 1000  |    60.3% |     1000 |                  60.3% |               397 |
| matcher v1              |  853 / 1000  |    85.3% |      804 |                  97.9% |                17 |
| matcher v2              |  862 / 1000  |    86.2% |      813 |                  97.9% |                17 |
```

How to read it:
- **For a records request, the column that matters is "right when it answered".** A wrong answer sends the request to the wrong office and costs days; "no confident match" goes to a person instead.
  - When the matcher answers, it is right 97.9% of the time.
  - Picking the closest name is right 60.3% of the time, and it always answers. Of 1,000 requests it sends 397 to the wrong place; the matcher sends 17.
- **Where the queries come from:** `gen_queries.py` makes them by seeded rules from registry records, so no one chose which queries are easy:
  - typos;
  - abbreviations;
  - "NYU Langone" dropped or added;
  - names cut short;
  - street words abbreviated or spelled out;
  - suites kept or dropped;
  - missing addresses and ZIPs;
  - 66 queries naming providers outside NYU Langone, where the right answer is to abstain.

  The queries were generated and committed before either matcher was run on them, and no setting was tuned on them.
- **What is left:** the matcher said "can't tell" 121 times on queries that had a right record. In 79 of those its first pick was right, but another record scored too close. That is where the next gain is. It has to be tuned on separate queries, not on these.

### v1 and v2

- **v1** is the matcher as frozen on 2026-11-08.
- **v2** adds one rule: never answer with a pharmacy or a medical-equipment or prosthetics supplier, unless the name typed asks for one ("pharmacy", "supply"). That accounts for 31 of the 445 locations.
  - Why: a patient's treatment records are held by the place that treated them, never by a pharmacy or supplier.
  - All five confident errors of v1 on the hand-written set (below) were answers of that kind.
  - Scores and thresholds are v1's, unchanged.

### The original hand-written test set (163 queries)

`python evaluate.py` prints (`results/evaluate_test.txt`):

```
| method                  | correct      | accuracy | answered | right when it answered | confidently wrong |
|-------------------------|--------------|----------|----------|------------------------|-------------------|
| baseline (closest name) |  121 / 163   |    74.2% |      163 |                  74.2% |                42 |
| matcher v1              |  145 / 163   |    89.0% |      140 |                  97.9% |                 3 |
| matcher v2              |  149 / 163   |    91.4% |      143 |                  98.6% |                 2 |
strict, matcher v1 (a pharmacy or supplier answer never counts as right): 143 / 163 = 87.7%; confidently wrong 5; right when it answered 96.4%
strict, matcher v2 (a pharmacy or supplier answer never counts as right): 149 / 163 = 91.4%; confidently wrong 2; right when it answered 98.6%
```

- **v1's numbers are a held-out result.** v1 was frozen before this set was run; they are unchanged from the first run.
- **v2's numbers are not held out.** v1's misses on this set were inspected, and the pharmacy rule came from them. The held-out result for v2 is the generated set above.
- **The strict line** counts a pharmacy answer as wrong even where a label allowed it (two labels do).

## Try it in the browser

This is section 1 of the repo's web app (instructions in the [top-level README](../README.md)): a FastAPI backend (`match_api.py`) around the same matcher, and a React + TypeScript page (`../web/src/match/`). Type a name and address, or pick an example or a random query from the held-out test set. The page shows:
- the match, with its confidence and phone and fax;
- records the registry can't tell apart from it;
- the runners-up;
- what closest-name matching would have picked;
- for a test query, whether the matcher got it right, scored exactly as `evaluate.py` scores it;
- "no confident match" with the reason (score too low, or the next record too close).

API:
- `POST /api/match` takes `{"name", "address", "zip"}`, plus an optional `query_id` to score the answer against that query's label.
- `GET /api/queries` lists the test queries.
- `GET /api/health` reports what is loaded.
- Interactive docs are at http://localhost:8010/docs.

`python -m unittest test_match_api` checks every labeled query: the API's right/wrong verdict must agree with `evaluate.py`, so the page can never show a different result from the reported numbers.

## How to run the evaluation

Python 3.10+, standard library only (only the web app and its tests need packages).

```
python evaluate.py              # held-out test set (the number above)
python evaluate.py --split dev  # the dev set the settings were tuned on
python matcher.py "NYU Langone ortho" "333 E 38th St" "10016"   # one lookup, JSON out
python check_labels.py          # every labeled NPI exists in the cached records
python registry_facts.py        # the registry facts quoted below
python fetch_npi.py             # re-download the registry data (needs internet; changes the cache)
```

The registry data is cached in `data/npi_raw.json`, so everything except `fetch_npi.py` runs offline and gives the same numbers every time.

## What's in it

- **Data:** organization records (the registry calls them NPI-2) from the public NPI Registry API (`https://npiregistry.cms.hhs.gov/api/?version=2.1`), New York State, searched by these names: NYU*, New York University*, Langone*, and the old names of hospitals the system absorbed (Winthrop*, Lutheran Medical*, Lutheran Augustana*, Hospital for Joint Diseases*, Rusk*, Family Health Centers at NYU*). The search returned 448 distinct records. 4 of them have no New York practice location and are dropped, which leaves 444 NPIs at 445 practice locations, on 170 distinct street addresses. Name searches also pull in some unrelated records with similar names (a dietitian named Langone, an equipment company called NYUS), and they stay in as realistic distractors. No patient data of any kind.
- **Matcher** (`matcher.py`):
  1. Cleans up names and addresses: St/Street, E/East, 1st/First, suite and floor dropped, ZIP cut to 5 digits, "New York University" treated as NYU, "ortho" matching "orthopaedic".
  2. Narrows candidates to the same ZIP or the same house number and street.
  3. Scores name similarity and address similarity, keeping each NPI's best location.
  4. Returns the top match with a confidence score, the runners-up, and the phone and fax the registry lists for that location. It answers "no confident match" when the score is low or the next different record is too close, and says which (`reason`).
- **Baseline:** fuzzy string match of the typed name against every record's legal name and DBA names, with the closest one winning. It ignores the address and never abstains, which is roughly what a search box over the registry gives you.

## The test set

- **245 queries, all written for this test on 2026-11-08. None of them is real intake data.**
- Each one was made by picking a record in the cached data and typing it the way an intake form might: abbreviations (GI, ENT, PM&R, UES, Ortho), misspellings ("Fertlity", "NUY"), missing suites and ZIPs, partial names, old names (Winthrop University Hospital, Lutheran Medical Center, Hospital for Joint Diseases), Queens hyphenated house numbers, and name-only queries.
- 10 queries name providers outside NYU Langone (Mount Sinai, Lenox Hill, HSS, Bellevue, which shares a street address with NYU records). For those, the right answer is to abstain.
- How each label was set is in the `label_method` column of `data/queries.csv`, and `make_queries.py` has the full list and definitions:
  - 217 `written_from_record`: the label is the NPI the query was written from.
  - 10 `hospital_any_of`: a whole hospital campus filed under several acute-care NPIs; any of them counts.
  - 5 `registry_near_duplicate`: one practice under 2 or 3 NPIs at the same address whose names are worded slightly differently.
  - 3 `any_of_judgment`: genuinely ambiguous.
  - 10 `not_in_registry`.
- An answer also counts as right when it is a record the registry cannot tell apart from the labeled one: same name on the door, same street address. That set is computed from the records alone, never from what the matcher returned.
- **Dev/test split:** a seeded shuffle (seed 20261108) in `make_queries.py` puts 82 queries in a dev set and 163 in a test set. Anyone can re-run it and get the same split.
  - The work was done in this order: split first, then the matcher was run and adjusted on dev only, then test was run.
  - The dev-driven changes were: also scoring how much of the record's own name the query covers, and the GI and CT abbreviations.
  - The settings were tuned by `tune.py` on dev only. It prefers zero confident errors, then the most correct answers, then the strictest thresholds on a tie.
  - After the first test run, no matcher setting or label changed. The only later change was to the report: `evaluate.py` gained the strict and abstention lines.
  - The order is stated here; the published git history does not record it.
  - On dev, the same settings score 75 / 82.
- Abbreviations that appear only in test queries (ENT, PM&R, ER) were deliberately not added, which is why those queries miss.

## What it gets wrong, and why

`python registry_facts.py` prints the facts below. Most of the trouble is in the registry, not the matcher.

1. **The registry files billing entities, not places.**
   - 138 different NPIs have the legal name "NEW YORK UNIVERSITY"; only the "doing business as" name tells them apart.
   - 58 records give a billing office at 3301 Quantum Blvd, Boynton Beach, FL as their primary practice address. The real New York clinic appears only as a secondary practice location, which the matcher uses.
   - 41 NPIs sit at one street address, 530 1st Ave.
2. **Some locations cannot be separated with registry data.** 122 NPIs fall into 47 groups where every member has the same name on the door and the same street address as another NPI. Examples: two "NYU Hematology Associates" at 160 E 34th St, two "NYU Ophthalmology Associates" in the same suite. The matcher returns these together, in a `same_in_registry` list, instead of flipping a coin. Telling them apart takes data the registry doesn't have, such as which one actually answered a records request last time.
3. **The 5 strict confident errors of v1 all have one cause: the name the person typed belongs, in the registry, to a different entity than the one that holds the records.** v2's rule (never answer with a pharmacy or supplier) fixes three of them. v2 has 2 confident errors on this set, neither a pharmacy answer: "NYU Langone Brooklyn hospital" lands on the system-wide "NYU Langone Hospitals" record instead of the Brooklyn campus, and for "Perlmuter cancer center Mineola" the only record with that name is a pharmacy, so v2 answers with a different clinic at the same address.
   - "NYU Langone Brooklyn hospital" (2 queries): the only record carrying the hospital's current name, "NYU Langone Hospital - Brooklyn", is the hospital's institutional pharmacy. The hospital itself is still filed as Lutheran Medical Center and NYU Lutheran.
   - "Rusk Institute" (name only): the record with that exact name belongs to Hanger Prosthetics & Orthotics, an outside supplier.
   - "NYU Langone ortho, 333 E 38th" and "Perlmutter cancer center Mineola": the only record carrying the "Orthopedic Center" or "Perlmutter Cancer Center" name at that address is a clinic pharmacy. The test labels allowed it; the strict line does not.
   - Each of these would send a request to the wrong office.
4. **Abstentions (15 on test) come in two kinds.**
   - Real ties the registry can't settle: a practice filed twice under slightly different names (Women's Health Center, Winthrop Hyperbaric, Winthrop Orthopaedic Associates), or a hospital spread over several NPIs.
   - Near-misses: in 10 of the 15, the top pick was right, but another record scored too close to call, usually a similar name at the same address ("NYU Ambulatory Care Center" vs "NYU Langone Rusk Ambulatory Care Center", a clinic pharmacy in the same building).
   - The other 5: abbreviations it doesn't know (ENT, PM&R, ER), a misspelled name typed with no ZIP, and an old hospital name typed with no address.
5. **Only 154 of the 445 practice locations the matcher can return list a fax**, so the registry alone is a weak source for where to send a request.

## What would come next with real intake data

- Replace these written test queries with real (de-identified) intake strings and the location each request actually went to. Accuracy on that is the number that matters, and the misses would show which abbreviations and old names people really use.
- Learn the name-to-location mapping from outcomes. Every request that reaches the right office confirms one pairing of a messy name and an NPI. Every request that comes back "wrong department" is a labeled negative. That fixes the pharmacy and vendor-name errors above, which no string matching can.
- Add routing: for the matched location, return where the request should go (phone and fax, already in the output) and flag stale or conflicting data, such as an out-of-state billing address, a missing fax, or two locations sharing one fax.
- Add the remaining locations. The registry search found 170 distinct NY street addresses against the "340+ care locations" in the posting, so some locations are filed under names these searches don't reach, or under individual-provider (NPI-1) records, which this does not pull.
