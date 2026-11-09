# altgen: independent out-of-distribution case-file generator

`python records/altgen/generate_alt.py` (run from `C:\Local_Projects\provider-match`) writes
12 cases to `records/data/alt/alt-<n>/records.pdf` + `truth.json` and prints one line per case
plus a total. Fixed seeds (`BASE_SEED` plus the case number); two runs give byte-identical
truth files. Dependencies: PyMuPDF and the standard library. Every page is text drawn with
`insert_text` in the base-14 fonts (cour, helv, tiro and their bold and italic forms), so
`page.get_text()` returns it. No images.

This was written from a brief only. No other generator, detector or dataset in `records/`
was read.

All people, clinicians, providers, firms and payers are invented. City names are made up and
phone numbers use the 555-01xx range.

## What it models

A personal-injury case file put together by a paralegal from several productions of the same
medical records. Each case is one injury type (six types, two variants each):

| type | care path (roles) | key codes |
|---|---|---|
| wrist | slip in a grocery store -> urgent care/ER, PCP, CT, hand surgeon, ORIF at an ASC, OT/PT | S52.531A/D, W01.0XXA, 73110, 73200, 25607 |
| back | warehouse lift -> urgent care, PCP, MRI, physiatry, TFESI x2, chiro or PT, microdiscectomy in variant 1 | S39.012A, M51.26, M54.16, 72148, 64483, 63030, 98941 |
| dogbite | ER/urgent care with Tdap and rabies prophylaxis, rabies series at the PCP, cellulitis culture, hand MRI, I&D plus extensor tendon repair, OT | S61.451A, S51.851A, L03.113, S66.320A, 90675, 90375, 26410, 11042 |
| mva | rear-end collision -> ER CT head/C-spine, neurology, MRI brain, occipital nerve blocks, vestibular PT or chiro | S06.0X1A, S13.4XXA, V43.52XA, F07.81, G44.309, 70450, 72125, 64405 |
| shoulder | fall on stairs -> rotator cuff MRI, subacromial injection, arthroscopic repair, PT | S46.011A, M75.41, 73221, 20611, 29827, 29826 |
| knee | slip on ice -> ACL and meniscus MRI, ACL reconstruction with partial meniscectomy, PT | S83.512A, S83.242A, 73721, 29888, 29881 |

Each case has 6 to 8 providers, a pre-incident PCP visit plus labs (the back case's prior visit
already records low back pain, so there is a real pre-existing condition), the acute visit with
same-day imaging, PCP follow-ups, specialist consult (with a causation paragraph) and
follow-ups, injections or surgery where they apply, and a therapy course of 18 to 40 daily
notes with re-evaluations. The kinds in truth follow the brief: urgent care is `er_visit`,
chiro and OT are `pt_*`, the pre-incident visit is `prior_visit`, lab dates are collection
dates, and the rabies doses are `office_visit`. An event's `pages` lists only its clinical
original pages, including any addendum. Billing and admin pages belong to no event.

Each case has 107 to 143 originals and 285 to 417 pages after copying. Duplicates make up 57%
to 74% of the pages in each case and 66.0% overall.

## Per-provider layouts (all set per provider, rotated so neighbours differ)
- Header: `left` letterhead, `center` letterhead, ASCII `boxed` (`+----+ | ... |`), or `banner` (`*** ORG ***` / `====`). Continuation pages get a one-line "(continued)" header.
- Date format: `03/14/2025`, `2025-03-14`, `March 14, 2025`, `14-Mar-2025`, `3/14/25`. Truth is always MM/DD/YYYY.
- Date label: `DOS:`, `Visit Date:`, `Service Date:`, `Encounter on`, `Date of Service:`. ID label: MRN / Acct # / Chart No. / Patient ID. Name shown as `LAST, FIRST` or `First Last`.
- Note style: SOAP, narrative with section headings, or a two-column `key | value` table.
- Kind-specific variants (3 per kind): imaging reports (headed sections / ASCII table header / numbered findings), lab reports (aligned columns / pipe table / dotted leaders), therapy daily notes (SOAP / exercise flowsheet grid / true two-column page), claims (1500-style / UB-04-style facility summary / superbill), signature lines (3 formats), page footers (4 formats).
- Font family and size, wrap width and rule length.
- ER triage pages are two-column.

## Copy mechanisms (truth `mechanism` holds the tokens joined with `+`)
Productions: **1** first subpoena (every original appears here), **2** second subpoena from about 65% of providers, **3** insurer claim file, **4** defense/prior-counsel copy set.
- `direct`, `ehr_print` (an added "Printed ... by ROI\x Source: EHR" footer line), `fax_A/B/C/D`: four fax formats. A is a top line `P.003/012`. B is a bottom line `RECEIVED Mar-02-2025 02:31PM | From | To | Job | Pg 3 of 12`. C has a `** FAX ** TX#` top line and a bare `003/012` bottom counter. D is an email-style top line `Page 3/12`. Counters run within each transmission.
- `reprint_reflow`: production 2 reprints the same note in a different font family with a different wrap width (+/-18 to 30 characters), and paragraphs re-flow.
- `scan_ocr`, `scan_onecol_crop`, `one_column`: two-column pages come out as one column, left column first.
- `crop_top` / `crop_bottom`: 1 to 4 rendered lines are lost.
- `reverse_order`: the provider produced its chart newest first.
- `chart_copy`: a provider's own production includes another provider's records it holds (the PCP holds ER notes, imaging, op notes and spec consults; the specialist holds therapy re-evaluations; and so on). These carry the sender's fax header plus a receiving stamp: `stamp_recd_bottom` (a boxed `REC'D JUN 03 2025` near the bottom), `stamp_scanned_side` (`SCANNED INTO CHART` rotated in the left margin), `stamp_filed_side` (rotated 270 in the right margin), `stamp_dept_bottom`, or `stamp_copy_top` (`C O P Y` / `COPY - CLAIM FILE` / `DEFENSE COPY`).
- `attached_authorization`: the same signed HIPAA authorization attached to many productions (one content id).
- `insurer_file`: billing plus key clinical pages in shuffled order.
- `counsel_copy_of_pN`: contiguous runs copied from an earlier production copy. A run keeps that copy's fax header, stamps and Bates number, then adds its own Bates number, more OCR, cropping and one-column output.
- Bates: one scheme per production, picked from `LAST 000123`, `PLTF-0042`, `MR001234`, `LAS_INS_00321`, `DEF00315` and `P00042`. Positions are top-right, bottom-left, bottom-right and bottom-centre. Inherited Bates numbers stack.
- OCR noise: rn<->m, cl<->d, w<->vv, h<->li, O<->0, 1/l/I, 5<->S, B<->8, merged spaces, split words, `~` or `^` in place of a letter, and words hyphenated at line ends (applied after wrapping, so the hyphen splits differ from copy to copy).
- Margin note: about 12% of clinical originals carry a handwritten-style italic note in the side or bottom margin. Copies may drop it (`note_absent`), and a few production-2 copies gain a note the original lacks (`note_added`). **These still count as duplicates**: the note is an annotation on the paper, not part of the record, and the content id stays the same.

## Look-alike non-duplicates (different content ids)
- Daily therapy notes from different dates, same template, with progressing pain and measures.
- ER vitals flowsheet sheet 1 and sheet 2, and the anesthesia record: identical layout, different values.
- A claim form and a **corrected claim** for the same DOS (a dropped code or a changed amount, resubmission code 7 / bill type 0137). Claims for the same provider on different dates.
- The same questionnaire (QuickDASH, Oswestry, NDI, SPADI or LEFS) at evaluation and at re-evaluation, with different answers.
- Production-1 and production-2 **cover letters** and **custodian certifications** from the same provider. They differ only in the letter or execution date and the request number and date.
- Rabies-dose visits with the same template, a few days apart.
- An **addendum page**: an exact repeat of a note's last page plus one `ADDENDUM <date>: ...` line. It is listed under the same event.
- A built-in check stops the run if two different content ids render the same text.

## How it differs from a generic generator
- Duplicates come from a model of productions (subpoena 1 and 2, records held in other charts, insurer file, counsel copies of copies) rather than from per-page noise. Copy artefacts therefore stack: a counsel copy of a faxed chart copy carries the original fax line, the receiving stamp, the old Bates number and a new one.
- Layout is set per provider, not per document, and a copy can change the layout itself (reflow, a font swap, one column, cropping), not just add a header line.
- The OCR confusions are glyph-shape errors with whitespace damage and re-hyphenation, not simple character swaps.
- Hard negatives are deliberate and are checked to differ.
- The copy mix varies by case: page order is either by production or by provider, and the sections are shuffled.

## Limits
- No images and no real scan geometry; "scan" is simulated with the text-layer damage above.
- Clinical text comes from templates per case type, so prose within a type repeats across its two variants.
- Production 2 copies the full chart, never a date-limited subset.
