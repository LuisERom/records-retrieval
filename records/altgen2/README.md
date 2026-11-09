# alt2: independent synthetic personal-injury records generator

`generate_alt2.py` writes ten messy case files for testing a duplicate-page detector and a medical-chronology checker. It was built only from the task brief, without looking at the other generators or the evaluation code in this repository. All patients, clinicians, providers, insurers and law firms are made up. Provider names come from invented town and surname pools, never from real hospitals.

```
python records/altgen2/generate_alt2.py      # from the provider-match folder; deterministic (fixed seeds)
python records/altgen2/validate_alt2.py      # schema, coverage and text-uniqueness checks (--show N prints sample pages)
```

Output goes to `records/data/alt2/alt2-<n>/records.pdf` and `truth.json`. The PDFs are letter size with no images. Text is drawn with PyMuPDF base-14 fonts (Helvetica, Times, Courier, plus their bold and italic forms), so `page.get_text()` returns it.

Files: `specs.py` holds the ten case specifications and the ICD-10-CM and CPT/HCPCS tables. `generate_alt2.py` builds the documents and productions and renders them. `validate_alt2.py` checks the output.

## Cases

| n | case | admitted? | surgery |
|---|------|-----------|---------|
| 1 | Scaffold fall at a construction site, right trimalleolar ankle fracture (workers' comp) | yes | ORIF 27822 |
| 2 | Pedestrian struck in a crosswalk, right femoral neck fracture | yes | hemiarthroplasty 27236 |
| 3 | Assault outside a bar, right zygomaticomaxillary complex (ZMC) and nasal fractures, concussion | yes | ZMC ORIF 21365 |
| 4 | Unwitnessed fall in a nursing home (bed alarm off), Colles fracture and scalp laceration | no | ambulatory surgery center (ASC), 25607 |
| 5 | Cyclist hits a turning car, rotator cuff tear (urgent care, not the ER) | no | ASC, 29827 |
| 6 | Stamping-press crush injury of the hand, 2nd and 3rd metacarpal fractures (workers' comp) | no | ASC, 26615 x2 |
| 7 | Dog attack on a letter carrier, infected forearm bites, rabies post-exposure treatment | yes | debridement 11043 |
| 8 | Supermarket slip, ACL and bucket-handle meniscus tear | no | ASC, 29888 + 29881 |
| 9 | Fall down a dark stairwell, L1 compression fracture; the pre-incident visit documents earlier low back pain | yes | kyphoplasty 22514 |
| 10 | Ladder slid out, bicondylar tibial plateau fracture | yes | ORIF 27536 |

Each case has a pre-incident visit (where the injured region is documented as normal, except case 9), followed by 6 to 9 providers drawn from this list:

- EMS run sheet, or urgent care
- ER: triage, provider note, medical decision making and disposition
- hospital lab report
- radiology group reports (ER studies and outpatient MRI)
- an inpatient stay with an H&P, a daily progress note, day and night nursing flowsheets and a medication administration record (MAR) for each day, and a discharge summary
- operative report and anesthesia record (plus pre-op update and PACU notes at an ASC)
- the surgeon's practice: new, pre-op, post-op and final visits, with in-office x-rays
- second specialists: ophthalmology, occupational medicine work-status notes, a wound clinic that gives the rabies vaccine doses
- PT or OT: evaluation, daily notes, re-evaluation, discharge
- home health PT or chiropractic
- pain management: consult, injection procedure note, follow-up
- nursing facility: incident report and 72-hour post-fall monitoring

Each provider gets its own look, chosen at random:

- font family and size, header alignment, and whether a rule is drawn under the header
- ALL-CAPS or Title Case section headings, and the heading suffix (`:`, ` --` or none)
- key-value separator (`: `, ` - `, ` = `)
- table style (`a | b`, `| a | b |`, or space-padded columns)
- one of three patient-header layouts
- 24-hour, colon or AM/PM times, and the page-number format

Each provider in a case also gets a different date format: `03-14-2025`, `Mar. 14 2025`, `14 March 2025`, `3/14/25`, `2025-03-14` (`2025-03-14T09:30` with a time), `Friday, March 14, 2025`, `2025.03.14`, `14-MAR-2025`, `03/14/2025` or `March 14, 2025`. Day-first numeric dates are never used.

Each case also has:

- **Billing:** itemized statements over several pages with running totals (the hospital's include revenue-code lines), CMS-1500-style claim forms, and a UB-04-style facility summary.
- **Admin:** law-firm request letters, one HIPAA authorization, records-custodian certifications, fax cover sheets, the insurer's cover letter, and the defense exhibit index.

## How the pages are produced (the `production` field)

1. **Plaintiff counsel's records collection.** For each provider, in this order: the request letter, the authorization, the custodian certification, the clinical pages, then billing. Some providers send by fax and some print from an EHR. Outside records sit inside the receiving chart:
   - the ER note and imaging reports in the surgeon's chart
   - the op note in the post-op chart
   - the surgeon's note in the therapy chart
   - the discharge summary in the home health chart
   - the MRI and op note in the pain chart
2. **Re-production after a second request.** Some providers send their records again, in full or in part, with a new request letter, a fax cover sheet and a new certification.
3. **Insurer claim file**, Bates-stamped.
4. **Defense exhibit binder**: an index, exhibit stickers, a running Bates number, and an exhibit/page stamp down the left margin.

The page count is set so the duplicate share falls between 50 and 75 percent.

## Copy mechanisms (the labels in `mechanism`; one page can carry several, joined by `+`)

- `original`: the first time a content appears in a provider's own production. It can already carry that provider's fax header and print footer.
- `authorization_attachment`: the same authorization page is attached to every request.
- `copy_in_other_chart`: another provider's pages filed inside the receiving chart. They carry the sender's fax header (sent to the receiving clinic, with a page counter for that batch), the receiver's stamp (`RECEIVED`, `REC'D`, `OUTSIDE RECORDS` or `SCANNED`, with date and clinic, rotated a few degrees) and the receiver's EHR print footer.
- `rerequest_reprint`: a second printout of the same record. The fax job and time are new, the page counter is new (`P.003/017`, `Page 3 of 17`, `Received Fax : ... p. 3`, or `2025-02-21 10:02:41 3305550129 >> 3305550199 [4471] 3/17`), and so is the "printed by / printed on" footer (four formats, with a new user, time and workstation each time). Possible extras:
  - `reflow`: a different print template. Font, size, margins and line breaks change, and pairs of key: value lines are joined onto one line.
  - `header_missing`: the letterhead and patient block are gone; the body is intact.
  - `stamp`: a `COPY`, `DUPLICATE COPY` or `RE-SENT` stamp.
- `insurer_claim_file`: a Bates number in the bottom-right corner (`ABC-CF 000123`), going up page by page. Possible extras:
  - `copy_of_copy`: the page reproduces an earlier copy and keeps its fax header, print footer, stamps, damage and cropping.
  - `fax`: the insurer's own fax from the provider.
  - `stamp`: the claims unit's `RECEIVED`, `FILED` or `REVIEWED` stamp.
  - `ocr`: damage from scanning and OCR.
- `defense_exhibit`: a Bates number at bottom center (`PVR0004101`), going up page by page, plus a rotated `DEF. EX. 7 - PAGE 3` stamp and a `DEFENDANT EXHIBIT n` sticker on the first page of each exhibit. Possible extras:
  - `copy_of_copy`
  - `ocr`
  - `cropped`: the top, right edge or bottom is cut off, so lines go missing and characters are truncated.
  - `sticky_note`: a yellow note on one copy only ("pre-existing? see PCP note").
  - `handwritten_note`: italic blue ink, rotated ("reviewed - KD", "?? date").

**OCR damage** uses its own confusion set:

- characters: 0/O, 1/l, I/l, 5/S, 8/B, 3/8, 6/b, e/c, a/o, h/b, n/h, u/v, t/f, g/q, i/j, E/F, D/0, 7/1, `,`/`.`, `:`/`;`
- letter pairs: rn->m, m->rn, cl->d, li->h, ri->n, fi->h, vv->w
- words merged (a space dropped) and words split (a space inserted)
- stray characters (`' ` . , ~ ^ | ; _ °`)
- lines broken in the middle of a paragraph

The damage level varies from document to document, and digits in dates and amounts get misread too.

## Look-alike pages that are NOT duplicates (each has its own `content_id`)

- Daily progress notes on consecutive hospital days.
- Nursing flowsheets for the day shift and night shift of the same date, and for different dates.
- MARs for each day of the stay.
- Therapy, chiropractic and home-health daily notes on different dates, built from the same template.
- Claim forms: a replacement claim (resubmission code 7) for the same date of service with a changed code, units or amount; and several claims from the same provider on nearby dates.
- The same intake form filled in on two dates: the pain questionnaire at the consult and at follow-up, and the therapy intake questionnaire at evaluation and at re-evaluation.
- The first and second request letters to a provider. Their wording is identical; only the date and the "Request No." differ.
- Records-custodian certifications from production 1 and production 2, which differ in date, page count and one sentence.
- A corrected imaging report next to the final report. Exactly one finding changes (for example 22 to 31 percent articular involvement, or 14 to 19 mm retraction), and the status changes from FINAL to CORRECTED with a later signature time.
- Statement pages 1, 2 and 3 of the same bill.

## Truth

`truth.json` follows the schema in the brief.

- `pages` lists every PDF page exactly once. Pages with the same `content_id` share the same record content. `provider` is the party that produced that copy: the provider, the insurer or the defense firm.
- `events`: one per encounter, dated as the date of service in MM/DD/YYYY. For labs the date is the collection date, and a corrected report keeps the exam date. An event's `pages` lists every original content id that records the encounter:
  - a hospital day: the progress note (or H&P), both flowsheets, the MAR, and the discharge summary on the last day
  - a therapy evaluation or re-evaluation: the intake questionnaire
  - an imaging event: the final and corrected reports
- Kind mapping:
  - EMS, urgent care, ER -> `er_visit`
  - each hospital day -> `office_visit`
  - facility incident report and monitoring days -> `office_visit`
  - chiropractic, OT and home health -> `pt_eval` / `pt_visit`
  - the pre-incident visit -> `prior_visit`
- Billing and admin pages are not attached to events.
- Codes are real ICD-10-CM codes (7th character A for the ER, inpatient and surgery; D for later care) and real CPT codes. Ambulance and home-health PT use HCPCS codes (A0427, A0425, G0151).

## Checks run

`generate_alt2.py` renders every original with no copy marks and refuses to write a case if two different content ids give the same text.

`validate_alt2.py` checks that:

- every page is listed exactly once and the page numbers match the PDF
- every content id an event points to exists
- every event kind is a valid one
- dates are MM/DD/YYYY
- no two pages with different content ids extract to the same text

## Limits

- Nothing is a real image. "Scans" are text with OCR-style errors, and crops are simulated by dropping or truncating text, so a detector that works on images will not see scan noise.
- Clinical text is template-based. Similar pages in one case share wording, which is intended, but the same templates are reused across cases.
- A partial re-send or exhibit can cut a multi-page document short. Those pages are still exact copies of their content ids.
- Charges are illustrative, not real fee schedules.
