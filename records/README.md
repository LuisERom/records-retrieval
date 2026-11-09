# Part 2: process the records (records/)

Part of [records-retrieval](../README.md). Run the commands below from this `records/` folder.

Turn the pile of medical records a law firm receives into something a lawyer can use: remove the duplicate pages without losing anything unique, then build a dated medical chronology where every entry cites the page it came from and is checked against that page.

## The problem

Codes Health's Software Engineer posting names it: *"Processing records that average 300 pages, sometimes hit 30,000, and run roughly 70% duplicate, and still surfacing what matters to a case."*

The duplicates are not byte-identical files:
- The same MRI report comes back from the imaging center, the orthopaedist, the pain clinic and the insurer's claim file.
- Providers answer a second request by sending everything again.
- Copies arrive as faxes and rescans with OCR errors, fax header lines, "received" stamps and different line breaks.
- The firm Bates-stamps every page, so no two pages are ever identical.

Meanwhile, many pages that look alike are **not** duplicates: physical therapy notes from different days, claim forms for different services on the same day, the same questionnaire filled in at each visit. Throwing one of those away throws away evidence.

## What's built

1. **Synthetic case files** (`chron/synth.py`, `chron/bundle.py`, `generate.py`).
   - Fictional motor-vehicle-accident patients with the care such a case usually involves:
     - an earlier physical and labs;
     - the ER visit and X-rays;
     - primary care, orthopaedics and an MRI;
     - 12 to 24 physical therapy visits with re-evaluations;
     - injections or knee surgery;
     - bills and claim forms.
   - Each case becomes the PDF a firm would receive. Each provider sends its own records plus copies it holds from other providers, and some re-send everything. The auto insurer's claim file repeats most of it. Copies get faxed, rescanned, stamped, OCR-garbled and (in the test splits only) cropped.
   - The answer key records, for every page, which original page it is a copy of, and the true list of encounters.
   - **Everything is invented. There is no real patient data.** The ICD-10 and CPT codes are real codes.
2. **Duplicate-page detection** (`chron/dedup.py`).
   - Removes duplicates and keeps the most complete copy of each page.
   - Built so that a unique page is not thrown away.
3. **Chronology with checked citations** (`chron/chronology.py`).
   - The kept pages go to Claude in batches. Claude returns structured JSON: one entry per encounter, each citing 1 to 3 pages with a quote copied from each.
   - Code (no model) then checks every entry: each quote must be on the cited page, the date must be written there, and every code must be written there.
   - Failures get one repair round. Entries that still fail are dropped and listed, never kept.

## How the duplicate detector works (v2)

Per page, from the PDF text layer:
1. **Drop what copying adds,** recognized by behavior and vocabulary rather than one layout:
   - a fax header (has "FROM:", or a clock time beside a transmission word);
   - a line that starts with a stamp word (received, rec'd, scanned, filed, copy, printed, faxed), with or without a date before it;
   - a bare page counter ("Page 3 of 12", "Pg 3/12", "P.003/012");
   - **page stamps found by behavior:** a number shape (digits in a fixed pattern, like `MR000544` or `OKA_INS_00172`) that appears on a large share of the file's pages and counts up in page order is a Bates or exhibit stamp, whatever its format. A request number that grows from one letter to the next is on only a few pages, so it is not taken for a stamp.
2. **Canonicalize OCR look-alikes** (0/O, 1/l/i, 5/S, rn/m, ...).
3. **Character fingerprints:**
   - the text with every space and punctuation mark removed, cut into overlapping 7-character runs, so OCR that merges or splits words ("Date ofService", "Provi der") does not change them;
   - candidate pairs come from MinHash + LSH, so the work grows roughly with page count.
4. **Two pages are duplicates only if, in one direction:**
   - most of one page's fingerprint is on the other (this tolerates cropping);
   - every number and every date on it is on the other. Dates are read in any common format (03/14/2025, 3/14/25, 2025-03-14, 14-Mar-2025, March 14, 2025) and compared as the same date. A number OCR glued to its neighbor ("D0802/20/1963", "98.3F") is found in the other page's space-free text.
   - its distinctive words, meaning names of people, places and organizations, are on the other. A distinctive word appears on 2 or more pages of the file (so a one-off OCR garble is not one) but on no more than a quarter of them (so template words are not either).

   The last two rules keep look-alike records apart: two therapy notes or claim forms share most of their wording but not their dates, numbers or amounts; two certifications share everything but the custodian's and the provider's names.
5. **Group by anchors:** a page joins a group only by matching that group's most complete page directly (why: the first test run, below).

v1, the version built only on this repo's own generator, is still in `chron/dedup.py` (`Params(version="v1")`), and every evaluation prints both.

## v3: learn each file's own stamps (`Params(version="v3")`)

v2 only drops overlay lines it has a rule for. v3 learns the rest from the file itself, before comparing pages:
1. **Find copies it is already sure of:** pairs whose character fingerprints overlap by 90% or more and whose distinctive words match.
2. **Look at what one copy has that the other lacks.** Copying only adds lines (a stamp, a sticker, a handwritten note), so a pair where *both* pages have lines the other lacks is two different records and teaches nothing.
3. **Turn each added line into a skeleton:** digits removed, scan look-alikes folded, letters only. `LITIGATION BINDER TAB 12 PRODUCED 03/02/2026` and `TAB 7 PRODUCED 11/19/2025` have the same skeleton.
4. **A skeleton is an overlay** when it was the added line in at least 3 sure pairs, and was missing from the other copy in at least 60% of the sure pairs it appears in. A template line cut off by a crop ("Signature of physician") is missing only in the cropped pairs: measured at 2 to 25% on this repo's generator, against 86 to 100% for real overlays on the independent generators. A line with a date-of-service label is never treated as an overlay.
5. Those lines are removed from every page, and v2 runs on the result. The copy that is kept is still the most complete page as received.

It costs about 3 to 6 times v2's time.

## Results

### Summary

`python eval_dedup.py --split <split>`, one row per test set. The full output is in `results/dedup_<split>.txt`.

| test set | what it is | v1: removed | v2: removed | v2: unique pages lost | v3: removed | v3: unique pages lost |
|---|---|---|---|---|---|---|
| `dev` | this repo's generator; used to build v1 | 100.0% | 99.0% | 5 | 99.1% | 5 |
| `test2` | this repo's generator, held out for v1 | 99.9% | 99.3% | 16 | 99.3% | 16 |
| `alt` | **independent generator #1**; used to develop v2 and v3 | 29.5% | 76.5% | 8 | 83.0% | 9 |
| `alt2` | **independent generator #2**; held out for v2 (run once), then used to develop v3 | 35.1% | **57.1%** | **0** | 62.8% | 0 |
| `alt3` | **independent generator #3**; held out for v3, run once | 17.1% | 22.9% | 2 | **67.0%** | **4** |
| `alt4` | **independent generator #4**; held out for v3 and the new date reader, run once | 67.5% | 81.7% | 1 | **86.7%** | **8** |
| `alt5` | **independent generator #5**; held out, run once | 64.5% | 80.6% | **12** | 84.4% | 15 |

**`alt5`** (`results/dedup_alt5.txt`, run once): v2 removes 80.6% but loses 12 of 1,223 unique pages, its worst result on a never-seen set. Almost all are billing pages: generator #5 includes a corrected statement that differs from the original in one line's code or amount, and v2 merges the two. Not diagnosed further and not fixed.

**v3 on `alt4`** (`results/dedup_alt4.txt`, run once): it removes the most duplicates (86.7% against v2's 81.7%) but loses 8 of 1,361 unique pages, against 1 for v2. Pair precision is 96.5% against 99.0%. On both never-seen sets, v3 removes more duplicates and loses more unique pages. For a legal file, where a lost page is the costly error, **v2 stays the default**, and the viewer uses it.

Exact counts are in `results/dedup_<split>.txt` (v1 and v2, as first run) and `results/dedup_<split>_with_v3.txt`.

**The held-out numbers are v2 on `alt2` and v3 on `alt3`.** Every other cell is on data the method was developed on.

**v3 on `alt3`** (`results/dedup_alt3.txt`, run once, nothing changed after):
- **It removes 67.0% of the duplicates, against 22.9% for v2 and 17.1% for v1.** Generator #3 puts overlay stamps on most copies, in wordings nothing in this repo had seen. v2 has no rule for them; v3 learned them from the file.
- **It lost 4 of 1,032 unique pages (v2 lost 2, v1 lost 1); pair precision 99.1%.** Looked at only after the run, all four are look-alike records merged into each other:
  - two custodian certifications from the same provider, with different custodians, dates and request numbers;
  - a corrected MRI report merged into the report it corrects;
  - two chiropractic visits.
- **One cause found in that look:** generator #3 writes some dates as `Mar 14, '25` and `20250325`, which the date reader does not read. Those pages lose their "every date must match" check, so look-alikes can merge. v3 also folds digits out of a learned line, so a line like `Request reference OBL-9947-P11` could be learned as an overlay if it is often added to copies; whether that happened here was not measured.
- **Not fixed,** because a fix found on `alt3` could only be measured honestly on a fourth independent set.

**v2 on `alt2`** (the earlier held-out number):
- **What it does well:** on a third generator's files, with formats nothing in this repo was shaped around, v2 removes 57.1% of duplicates against v1's 35.1%. It **loses no unique page** and **never merges two different pages** (pair precision 100.0%). For a legal file, losing evidence is the error that matters most, and it did not happen.
- **What it does not do:** 43% of the duplicates in that unfamiliar format are left in. On the generator it was built with, v1 reached 99.9%, so the gap between "built on this data" and "never seen it" is large. That gap is the honest state of the method.
- **Where v2 still misses** (`python diagnose_dedup.py --split alt2`, looked at only after the run): mostly copies carrying extra overlay lines in wordings v2 does not know, such as a defense exhibit binder's stamps and copies of copies, where a date and a time sit next to unfamiliar words.
- **The next step** was to learn each file's own stamp formats; that is v3, above.
- **The cost on this repo's own files is small:** test2 drops from 99.9% to 99.3%. Of its 16 lost originals, 3 hold any word missing from the page they were merged into: "Page", "Signature", and the page count "6" on a fax cover.

### How the independent test sets were made

- **Five generators written separately:** `altgen/` through `altgen5/` were each written by a separate agent from a written brief. No agent saw the detector, the chronology code, this repo's generator, or another agent's generator.
- **Each has its own:**
  - case types and providers;
  - layouts;
  - date formats;
  - fax, Bates, stamp and print-footer formats;
  - OCR damage;
  - look-alike pages that are not copies;

  see each folder's README.
- **Order of work:**
  1. `alt` was committed before v1 ran on it. v1 removed 29.5% of its duplicates, and that result was committed before any fix.
  2. v2 was then developed on `dev` and `alt`, including the diagnosis of every miss. Two attempted changes made things worse and were reverted; the code says which.
  3. v2 was frozen before `alt2` was generated.
  4. `alt2` was committed and run once. Nothing was changed in v2 after that.
  5. v3 was developed on `dev`, `test2`, `alt` and `alt2`. A first version without the 60% rule reached more on `alt` and `alt2` but lost hundreds of pages on `test2`; the rule came from measuring how often template lines and real overlays go missing. v3 was frozen before `alt3` was run.
  6. `alt3` was committed and run once.
  7. The date reader and the checker were fixed on all the earlier sets, `alt3` included, and frozen before `alt4` was run. The fourth generator was briefed only to use a wide range of realistic date styles; it was not told which ones the reader handles.
  8. `alt4` was committed and run once. The scoring script then needed two answer-key kinds it had never seen (`procedure`, and `ems`, scored as an ER visit because the timeline has no ambulance kind); that change touches only scoring.
  9. Both `alt4` checker gaps were fixed on all the earlier sets and frozen before `alt5` was run. Generator #5 was briefed that pages carry other dates (signature, report, print, birth, prior studies) and varied visit labels, but not told how the checker decides.
  10. `alt5` was committed and run once.

### The timeline checker on the independent files

- **The problem:** v1 of the checker only recognized dates written MM/DD/YYYY. On `alt`, 438 of the 525 encounters never show their date that way, so correct entries would have been dropped.
- **The fix:**
  - the checker reads dates in any common format;
  - when a cited page labels its date of service ("Date of Service", "DOS", "Visit Date", "Exam date", "Collected", "Date of Surgery"...), the entry's date must be that date, not just any date on the page. A shifted date that lands on a report date or signature date is then rejected.
- **Checked against Claude's 410 saved entries** before it was kept: all of them still pass.

Measured with answers built from the answer key, so no model and no cost (`python eval_chronology.py --extractor oracle|corrupted --split alt2`, held out, run once):

```
split: alt2  extractor: oracle  case files: 10  encounters in the answer key: 347
events found:              321 / 347 = 92.5%
entries correct:           321 / 321 = 100.0%
dropped by the checker:    8 entries; batches repaired 8 / 78; refused 0
split: alt2  extractor: corrupted  case files: 10  encounters in the answer key: 347
entries correct:           285 / 285 = 100.0%
dropped by the checker:    224 entries; batches repaired 70 / 78; refused 0
```

- **Every falsified quote or date was dropped.**
- **8 correct entries were dropped too:** the checker is stricter than it needs to be on some of these pages.
- **Claude has not been run on the independent files,** because the account's API spending limit was reached.

On `alt3` (held out, run once; `results/chronology_oracle_alt3.txt`, `results/chronology_corrupted_alt3.txt`):

```
split: alt3  extractor: oracle  case files: 10  encounters in the answer key: 316
events found:              241 / 316 = 76.2%
entries correct:           241 / 241 = 100.0%
dropped by the checker:    1 entries; batches repaired 1 / 75; refused 0
split: alt3  extractor: corrupted  case files: 10  encounters in the answer key: 316
entries correct:           225 / 225 = 100.0%
dropped by the checker:    184 entries; batches repaired 68 / 75; refused 0
```

- **Every entry that reached the timeline is correct,** and every falsified one was dropped.
- **Only 76.2% of encounters were found, and the checker is not why:** the oracle builds an entry only when it can find the encounter's date written on the page, and for 75 encounters no page shows the date in a form the date reader reads. The ones looked at write it `Mar 14, '25` or `20250325`. A model's correct entry citing such a page would be dropped as "date not on the cited page".

### The date reader fix, and the fourth generator

- **What changed** (`chron/dedup.py` `dates_with_positions`, `chron/chronology.py`):
  - the date reader now also reads apostrophe years (`Mar 14, '25`), compact dates and timestamps (`20250314`, `202503141430`), "the 14th day of March, 2025", year-first month names (`2025 MAR 14`) and spaced separators (`03 / 14 / 2025`);
  - date-of-service labels are found even when OCR garbled them (`Col1ected`, `D0S`);
  - a date on a fax header or a "received" stamp no longer supports an entry's date, because it records when the copy was sent, not when the patient was seen. The fix exposed one shifted date on `alt3` that matched a fax-received date.
- **Checks before freezing:**
  - the reader still finds no date in pain scores, blood pressures, MRNs, visit counts or request numbers (unit tests);
  - all 351 of Claude's saved `test2` entries still pass;
  - duplicate removal is unchanged on every earlier set except `alt3`, where v3 loses 3 pages instead of 4 and v2 loses 1 instead of 2 (`results/*_dates.txt`).
- **On the sets it was developed on:** `alt3` oracle went from 76.2% to 100% of encounters found. With 30% falsified answers, every entry the checker kept was correct on `test2`, `alt`, `alt2` and `alt3`.

**On `alt4`, held out, run once** (`results/chronology_oracle_alt4.txt`, `results/chronology_corrupted_alt4.txt`):

```
split: alt4  extractor: oracle  case files: 10  encounters in the answer key: 856
events found:              833 / 856 = 97.3%
entries correct:           833 / 833 = 100.0%
dropped by the checker:    0 entries; batches repaired 0 / 62; refused 0
split: alt4  extractor: corrupted  case files: 10  encounters in the answer key: 856
entries correct:           633 / 637 = 99.3%
dropped by the checker:    311 entries; batches repaired 58 / 62; refused 0
```

- **The reader held up:** the fourth generator uses about 30 date styles. No correct entry was dropped, and 97.3% of encounters were found.
- **What it still misses** (looked at after the run, not fixed):
  - `Mar-26-2025`, a month name joined to the day by a hyphen, is not read (7 encounters);
  - **4 falsified entries got through.** Each shifted date sits on the next day's signature line ("Signed Saturday, March 15, 2025"), on pages that label the visit "Arrival:" or "Seen:". Those labels are not in the checker's list, so the page accepts any date written on it. Adding labels one at a time is the same patch-the-format approach v2 moved away from; a page-level rule that says which date is the visit's would be the general fix.

### The page-level visit-date rule, and the fifth generator

- **What changed** (`chron/chronology.py` `visit_date_candidates`, `chron/dedup.py`):
  - on a page with no date-of-service label the checker can read, a date no longer supports an entry when the words just before it name it as something else: signed, dictated, reported, printed, faxed, received, downloaded, released, date of birth, a prior or comparison study, the next visit, the injury;
  - if that rules out every date on the page, all of them count again, because a cropped copy may keep only the signature date;
  - `Mar-26-2025` is read.
- **On the sets it was developed on** (`results/*_fix2.txt`): falsified entries kept fell to 0 on all five (`alt4`: 4 of 637 before). Correct entries dropped rose slightly: `alt2` 13 (was 8), `alt3` 2 (was 1), `test2` 1 (was 0). All 351 of Claude's saved entries still pass.

**On `alt5`, held out, run once** (`results/chronology_oracle_alt5.txt`, `results/chronology_corrupted_alt5.txt`):

```
split: alt5  extractor: oracle  case files: 10  encounters in the answer key: 646
events found:              613 / 646 = 94.8%
entries correct:           613 / 613 = 100.0%
dropped by the checker:    13 entries; batches repaired 10 / 57; refused 0
split: alt5  extractor: corrupted  case files: 10  encounters in the answer key: 646
entries correct:           470 / 472 = 99.5%
dropped by the checker:    250 entries; batches repaired 52 / 57; refused 0
```

- **2 falsified entries got through** (4 on `alt4`). Both moved the date onto a dictation line, `D: 13 February 2023   T: 14 February 2023`, where `T:` means transcribed; the rule does not know that shorthand.
- **13 correct entries were dropped** (2.1%). The cause is a flaw in the rule itself, not one format: a date after a document title such as `PROGRESS REPORT 04/21/23` or `RADIOLOGY REPORT 12JAN2023` is ruled out because "report" precedes it, and a date of birth in parentheses with no label keeps the fallback from rescuing the page.
- **What this says:** judging a date by the words just before it trades one kind of error for another. Each fix closed the gap it was aimed at and the next independent set found the next one. A sturdier design would look at the page's layout (the date in the header block, the first date after the patient line) rather than at nearby words; not built.

### v1's order of work, and the first test run

- The dev split was used to build and tune the method.
- The method was then frozen and run once on the held-out `test` split. That run removed 99.7% of duplicates but **lost 33 unique pages**, all certifications and fax covers. The output is saved verbatim in `results/dedup_test_run1.txt`.
- Looking at those failures showed a design flaw. Grouping by transitive closure let a copy cropped so badly that its dates were gone match several different certifications at once and chain them into one group. The fix is anchor grouping.
- Because the flaw was found by looking at the `test` split, that split no longer counts as held out. The fixed method was scored once on a freshly generated split, `test2` (the table above).
- Two changes to the report were made after that run, and neither changes the method:
  - percentages now round down;
  - the evaluation now checks whether each lost page held any word not on its kept page.
- On dev the method removes 2058 / 2058 duplicates with nothing lost (`results/dedup_dev.txt`).
- The `test2` split was also generated after the method was designed, so the method was not tuned against those cases.

### Chronology

**Claude (Opus 5.5), held-out split `test2`, first 11 of 16 case files** (`results/chronology_claude_test2_first11.txt`):
```
split: test2  extractor: claude  case files: 11  encounters in the answer key: 352
events found:              351 / 352 = 99.7%
entries correct:           351 / 351 = 100.0%
citations on the right record: 829 / 830 = 99.8%
diagnosis codes listed:    118 / 135 = 87.4%
dropped by the checker:    0 entries; batches repaired 0 / 58; refused 0
model calls: 58  input tokens: 771388  output tokens: 109481  cost: $5.28 ($0.48 per case file)
```
- **Why 11 and not 16:** the run stopped when the account's monthly API spending limit was reached, and the API refused further calls until the limit resets. The other 5 case files have not been run. These numbers cover the 11 that were, and they are the only Claude numbers here.
- **What came before the run:**
  - The method was frozen before this run.
  - Before that, a 2-case trial on the dev split found an error in the **answer key**, not in Claude's output. Claude dated each lab test by when the blood was collected, which is the date of service; the generator's key used the report date, one day later.
  - The key was fixed to use the collection date. Only the lab event dates changed, and the page text and duplicate key are identical.
- Every entry passed the checker, so none were dropped. Every one of them matches an encounter in the answer key.

The pipeline was also checked with no model at all:

- **Oracle:** answers built from the answer key, citing the date line of each page. This confirms that the batching, the checker, the merge step and the scorer work end to end (`results/chronology_oracle_test2.txt`):
  ```
  events found:              511 / 511 = 100.0%
  entries correct:           511 / 511 = 100.0%
  citations on the right record: 588 / 588 = 100.0%
  ```
- **Corrupted oracle:** the same answers with 30% of entries given a fabricated quote or a wrong date, to see whether the checker drops them (`results/chronology_corrupted_test2.txt`):
  ```
  entries correct:           368 / 369 = 99.7%
  dropped by the checker:    166 entries; batches repaired 64 / 84; refused 0
  ```
  - **One falsified entry gets through.** Its date was moved one day later, onto the report date of a lab printed on the same line ("Col1ected: 10/26/2024   Rep0rted: 10/27/2024").
  - **Why:** OCR garbled the label "Collected" into "Col1ected", so the checker did not recognize the date-of-service label and fell back to accepting any date on the page.
  - **The known fix:** match the labels after OCR normalization. It is not applied, because no unused held-out set is left to measure it on.

## What came from GnoRA

These pieces of GnoRA were reused or adapted. All of them were written by Luis Roman.
- **Five-word phrase hashing** (`api/documents/text_similarity.py`): same phrase length and hash, applied per page instead of per file.
- **The quote check** (`api/report/citations.py`, `quote_supported`): a normalized substring match, here with OCR canonicalization added.
- **The repair round** (`api/chat/reasoning/calls.py`, `call_with_repair`, and `llm_client.repair_instruction`): show the model its rejected answer and the reasons, and take the complete object back once.
- **Strict output models** (`api/llm_schemas.py`): `extra="forbid"`, with the response validated against the same schema.
- **Map in batches, reduce in code** (`api/documents/index_card.py`): batches go to the model, and results are merged in code with no reducing model call.

## Viewer

This is section 2 of the repo's web app (instructions in the [top-level README](../README.md)): a FastAPI backend (`records_api.py`) and a React + TypeScript page (`../web/src/records/`) for looking at one case file at a time:
- **Chronology tab:**
  - each entry with its date, kind, provider, summary, codes and the pages it cites;
  - clicking a citation opens that page with the quoted words highlighted in place, located with the same normalization the checker uses;
  - entries the checker dropped are listed with the reason.
- **Duplicates tab:**
  - every group of copies, labelled with the provider and document title;
  - the kept page shown beside any removed copy, with how that copy was made (fax, rescan, received stamp, cropped);
  - the count of pages whose decision disagrees with the answer key.
- **Where the chronology comes from:** until a Claude run is saved for a case, it is built by the oracle from the answer key, and the page says so in a banner. After `eval_chronology.py --extractor claude`, the page shows Claude's checked answer instead.

`python -m unittest test_records_api` checks the routes against the detector and that every oracle citation is located on its page.

## How to run

Run these from this `records/` folder. Python 3.10+ with `pymupdf`, `numpy` and `pydantic` (all in the repo's `requirements.txt`); the real chronology run also needs `anthropic`.

```
python generate.py                          # build dev, test and test2 case files and answer keys into data/
python eval_dedup.py --split test2          # duplicate detection on the held-out split
python eval_dedup.py --split dev
python diagnose_dedup.py --split dev        # why each missed duplicate was missed
python -m unittest test_dedup               # the hard cases, pinned
python eval_chronology.py --extractor oracle --split test2
python eval_chronology.py --extractor corrupted --split test2
python eval_chronology.py --extractor claude --split test2   # needs ANTHROPIC_API_KEY; answers cached in results/chronology/
```

`data/` is not in the repository. `generate.py` rebuilds it exactly from fixed seeds.

## Limits

- **The data is synthetic, and I wrote the generator,** so the method could be shaped to the generator's habits. The defenses:
  - held-out splits with more noise and a copy mechanism (cropping) that the dev split never has;
  - a second held-out split after the first was used for diagnosis;
  - stating plainly what was looked at and when.

  Real records will have problems this generator does not make, such as rotated scans, handwriting, two-up pages and pages with no text layer. Those would need OCR first.
- The detector reads the PDF text layer. Pages with no text layer need OCR before this step.
- The real chronology numbers (recall, precision, citation accuracy, cost per case) do not exist until the model run is done. Nothing here should be read as a claim about them.
