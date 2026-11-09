# altgen5: independent synthetic records generator (held-out set alt5)

`generate_alt5.py` writes `records/data/alt5/alt5-1` .. `alt5-10`. Each folder holds `records.pdf` (a text-layer PDF) and `truth.json`.
It uses the standard library only. The PDF writer is its own: Type1 base-14 fonts, WinAnsi encoding, Flate content streams, and no dates or IDs in the file.
All randomness comes from string-seeded `random.Random` instances, so a rerun is byte-identical. This was checked on repeated runs, including one with a different `PYTHONHASHSEED`.

```
python generate_alt5.py                 # writes ../data/alt5
python generate_alt5.py --out DIR --cases N
python _scratch/check_alt5.py ../data/alt5 [--samples]
```

## What a case models

- **The incident and patient.** Each case has an invented plaintiff and one of ten incidents, a different one per case: rear-end crash, T-bone, rideshare passenger, delivery-truck sideswipe, motorcycle, pedestrian in a crosswalk, grocery slip, sidewalk trip, stair-rail collapse, icy loading dock. Each case has 2-3 injured regions with laterality, an invented insurer and its insured, a plaintiff firm and a defense firm.
- **Providers (4-9 per case).** The pool is EMS, ER hospital or urgent care, primary care (which also holds the pre-accident visits), orthopedics, imaging center, PT, chiropractic, pain management, surgery center and neurology. Each provider gets its own style profile:
  - letterhead variant (5) and patient-block variant (4)
  - patient-name format (5)
  - its own date style for the visit date, the continuation-page header, in-text mentions, signatures, the print footer, DOB and billing
  - one of 8 signature templates and one of 7 footer templates
  - an MRN format
  - a visit-date label per encounter kind. About 1 provider in 5 prints the visit date unlabeled in the title line.
- **Timeline.** The timeline runs through these stages:
  1. 1-3 prior visits with no complaints in the injured regions.
  2. EMS, then the ER (with X-ray/CT events and sometimes labs) or urgent care.
  3. A PCP follow-up, then orthopedics: a consult with a work-status form, an MRI review, follow-ups and a pre-op visit.
  4. MRIs, one of which may have a corrected or amended report.
  5. A PT evaluation, daily notes, and re-evaluations every 12 visits plus a post-op one.
  6. Chiropractic visits; pain consult, 1-2 epidural injections and follow-up; neurology for head injuries.
  7. Surgery (op report plus anesthesia record) with post-op visits.

  The number of PT/chiro notes is tuned so that each case lands on a target page count and duplicate rate.
- **Event pages.** Every clinical page belongs to exactly one event and prints that event's date in the provider's style. The date is in the labeled header on page 1, and in the running header on continuation pages, often in a second style. Pages also carry other dates:
  - DOB and date of injury
  - signature or e-signature dates, often 1-5 days after the visit
  - dictated and transcribed dates
  - report and addendum dates; lab received and resulted times
  - prior visit and prior study (comparison) dates
  - next appointment, goal and certification-period dates
  - "effective through" dates on work forms
  - print and release dates in footers
  - transmission and received dates in the overlays

## Productions and copy mechanisms (`pages[].mechanism`)

`production` is the chronological number of the production. Production 1 is always the provider releases; the others are shuffled per case.

| Production token | What it is | Marks added to copies |
|---|---|---|
| `provider_release` | Each provider's release, with a request letter, HIPAA authorization, ROI cover letter, custodian certification, chart and itemized statement | `enclosure_copy` (the same authorization re-enclosed) |
| `filed_in_other_chart` | Another provider's document filed in a provider's chart (ER/MRI/EMS/op report/ortho consult) | outside-record stamp |
| `insurer_file` | Carrier claim file | `fax_header` in the sending provider's format (7 formats); `fax_header_x2` when forwarded again through the plaintiff firm; received stamp; `page_counter` (claim page numbers) |
| `portal_download` | Patient-portal export | `reflow` (re-wrapped, new font), portal header/footer, sometimes cropped |
| `rerequest` | Second request to 1-2 providers | COPY/DUPLICATE stamp, provider-to-firm fax header. Visits after the first release appear here first. |
| `opposing_production` | Defense production | `bates` (rising), `ocr` (text-level confusion set), `crop_top`/`crop_bottom`/`crop_right`; `copy_of_copy` when it reproduces the carrier's faxed copy with its headers and stamps |
| `exhibit` | Plaintiff exhibits behind slip sheets | `exhibit_label` (Ex. n - p), `handnote` (a margin note in Times-Italic on one copy of a content only), `copy_of_copy` when made from the defense copy (keeps its Bates) |

Stamp placement is recorded as `stamp_line` (own line), `stamp_margin` (rotated left margin, top or bottom) or `stamp_append` (appended to an existing line). `double_scan` marks a second pass over the pool (an extra OCR-damaged copy).

The first occurrence of each content in PDF page order is `original`. It is rendered clean, with no production marks, wherever it falls. Cases are arranged either by production or by provider tab (provider, then production), so in some cases the first occurrence is the filed-in-other-chart copy or the carrier copy. In those cases the provider's own release copy is a `provider_release` duplicate.

## Look-alikes that are not duplicates (each has its own content_id)

- Consecutive PT and chiro daily notes from one template, differing by date, visit number, pain score and interventions.
- The same work/activity status form on two ortho dates.
- A corrected billing statement page that differs from the original page only in one line's CPT code or amount, with the same statement date.
- A first and second records-request letter that differ only in date and reference number.
- An original MRI report and a corrected report with an addendum, both in the same event.
- Two custodian certifications from the same provider, with different custodian, date, page count and notary.
- Two statements from the same provider at different statement dates.
- Exhibit slip sheets that differ only in number and title.

No two content_ids extract to identical text.

## truth.json

The schema matches the alt3 example. `pages[].provider` is the authoring entity: the medical provider for its records, covers and certifications, and the law firm or insurer for letters, the authorization, the bill review, the defense index and the slip sheets. It is the same on every copy of a content.

## Limits

- **Dates are never damaged.** On every copy, the header line that carries the visit date is protected from OCR damage and cropping, so the date always survives in extracted text. Other lines, including other dates, can be damaged.
- **Damage is simulated in the text layer.** There are no images, skew or real scans. OCR damage is character substitution and dropped spaces, and cropping removes lines or truncates them. The handwritten note is italic typed text.
- **Table extraction differs by mode.** Billing, lab and index tables are positioned cells. `pdftotext -layout` keeps the rows, while raw `pdftotext` and pypdf may read them column by column.
- **The clinical text is templated.** Phrases repeat within and across cases, and pages are about half full. Each event has a single date of service: there are no multi-day admissions and no undated clinical pages.
- **Day-first dates are spelled only.** Spelled day-first forms ("7 March 2024", "7-Mar-2024", "07-MAR-2024") do occur. No day-first numeric dates are produced, and the checker confirms this.
- **Productions are limited.** There are 4-5 productions per case, and none has 6.
- **Some realism quirks remain.** For example, an ER X-ray may be read by a clinician with a PA or DO credential, and the label "Triage Time:" can be followed by a date with no time.
