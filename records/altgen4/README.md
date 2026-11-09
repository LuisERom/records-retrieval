# altgen4: independent synthetic records generator

`generate_alt4.py` writes `records/data/alt4/alt4-1` to `alt4-10`. Each folder holds a `records.pdf` (text layer, 250-412 pages) and a `truth.json`. It is held-out test data for a duplicate-page detector and a timeline checker, and it was written without looking at the code under test.

Run: `python generate_alt4.py` (or `--out DIR --cases 1,3`). It needs Python 3.12 and nothing else: `pdfmini.py` is a small PDF writer that uses the standard Type1 fonts and `Tj` text operators. It writes no timestamps or IDs, and seeds are fixed, so a rerun produces the same bytes.

Files: `generate_alt4.py` (case planning, clinical text, layouts, productions, copy transforms, output), `banks.py` (invented names, incidents, region tables, OCR confusion set), `datestyles.py` (date formats), `pdfmini.py` (PDF writer), `_scratch/check_alt4.py` (validator), `_scratch/sample.py` (prints one page per mechanism).

## What one case contains

- **Plaintiff and incident.** Each case has an invented plaintiff and one of 10 incidents: escalator handrail stop, dog knock-down and bite, landlord ladder hinge failure, falling pallet of flooring, trampoline-park platform collapse, chemical spill on a hotel pool deck, restaurant booth bench collapse, stage riser collapse, automatic door closing on the plaintiff, zip-line brake failure. Each incident has its own external-cause code and 2-4 injured body regions.
- **Providers.** Each case has 4-9 invented providers. ER/hospital, orthopedics and PT are always present. EMS, PCP, imaging center, pain management, surgery center, chiropractor, neurology and urgent care are optional.
- **Other parties.** Each case also has an invented plaintiff law office, a liability insurer, and a defense firm.
- **Clinical events.** The kinds are pre-incident PCP visits (`prior_visit`), EMS run, ED visit, and same-day ED imaging and labs (separate events on the same date at the same provider). Then come ortho visits, in-office x-ray, MRI, a PT evaluation with daily notes and re-evaluations every 9-12 visits, an optional discharge summary, chiropractic daily notes, pain injections, EMG/NCS, pre-op labs, surgery and a post-op visit.
- **Codes.** Each event carries ICD-10 and CPT/HCPCS codes. Initial-encounter S-codes change to the subsequent-encounter ("D") form for therapy.
- **Admin pages per provider.** A law-office request letter, a re-request letter, a custodian certification, a fax cover sheet, and itemized statement pages.
- **Admin pages per case.** Two HIPAA authorizations, three claim-line pages, an insurer claim-file cover with index, a hospital certification for the subpoena production, and a defense cover letter.

## Date styles

Each provider has its own style for the date of service. About 55% of providers use a second style for signatures and timestamps. There are 32 patterns in `datestyles.py`:

- **Numeric, month first:**
  - `MM/DD/YYYY`, `M/D/YYYY`, `M/D/YY`, `MM/DD/YY`
  - `MM-DD-YYYY`, `M-D-YY`
  - `M.D.YYYY`, `MM.DD.YY`
- **Numeric, year first:** `YYYY-MM-DD`, `YYYYMMDD`, `YYYY/MM/DD`
- **Month spelled out:**
  - `Month D, YYYY`, `Mon D, YYYY`, `Mon. D, YYYY`
  - AP style (`Sept. 4, 2025`)
  - `MON DD YYYY`, `DD-MON-YYYY`, `D Mon YYYY`, `DDMONYYYY`, `Mon-DD-YYYY`
  - `Weekday, Month D, YYYY`, `Month Dth, YYYY`, `Dy Mon DD, YYYY`
  - the legal form `the Dth day of Month, YYYY`, used on certifications
- **Timestamps:**
  - `MM/DD/YYYY HH:MM`, `M/D/YYYY h:MM AM`
  - `YYYY-MM-DDTHH:MM:SS`, `YYYY-MM-DD HH:MM`, `YYYYMMDD HHMM`
  - `MM/DD/YY@HHMM`, `DD-MON-YYYY HH:MM`, `Mon D YYYY h:MMam`

A day-first date appears only with a spelled month. Pure-digit dates are never day-first. Transmission lines, stamps, insurer and defense pages, and statements use their own fixed styles.

## Page layouts

There are six layouts:

- **letterhead:** centered header, with a short "(continued)" header on later pages.
- **ehr:** Courier printout, with a "Printed by HIM-ROI ... Page n of m" footer.
- **twocol:** header in two columns.
- **running:** later pages print the date with no label.
- **form:** includes the form number and revision.
- **report:** radiology/hospital style.

Fonts, sizes, field styles (`Key:`, `KEY:`, `Key......`), date-of-service labels (`DOS:`, `Arrival:`, `Treatment Date:`, `Service Dt:`, `Seen:`, `Incident Date:` ...) and footers (confidentiality line, NPI/Tax ID, template version) vary by provider. Some providers file their notes newest first.

## Productions and copy mechanisms

Productions are numbered in PDF order. Each `mechanism` lists the copy steps joined with `+`. When a page is a copy of a copy, the parent copy's steps come first, then `>`, then the new steps.

| production | what happens |
|---|---|
| `release` | Provider charts as originals: fax cover, request letter, certification, notes, statements. Outside records are filed inside another provider's chart (`filed_in_chart(<host>)`), with the sender's fax header in some cases and an `OUTSIDE RECORDS ... REVIEWED <date>` stamp on its own line. |
| `re_request` | Providers that answer only the re-request send their originals here. Providers that already released re-send part of their chart by fax: a fax header in that provider's machine style (4 styles) with a page counter that rises (`P.003/017`, `pg 3 of 17`, `Page 03/17`, `PAGE   3/ 17`), and a RECEIVED stamp on its own line. The re-request letters and second certifications arrive here. |
| `insurer` | A claim file: an e-fax or secure-transmit header, a RECEIVED stamp (in the rotated margin or on its own line), and a rising `Claim ... Doc pg 0001` footer. About 40% of documents are "scanned", meaning OCR damage applied to the text from the confusion set in `banks.py` (rn/m, l/1, O/0, S/5, cl/d, n/ri, w/vv, dropped spaces, ...). |
| `portal` | A patient-portal print of one provider's chart plus some outside results. The text is reflowed: lines rewrapped, short lines merged, original header and footer dropped. It carries a portal print line and `Page i of n`. |
| `subpoena` | Hospital HIM release: an `Released by ... HIM Req# ... MM/DD/YY@HHMM` header and a `SUBP i / n` footer, with a new hospital certification. |
| `defense` | Bates-numbered production (`PREFIX 000123`). About 55% of documents are copied from earlier copies, so they keep the fax, OCR and stamp marks of those copies. Other marks: crops (top and bottom lines removed, and sometimes the right edge clipped mid-line), an appended `CONFIDENTIAL-PO` stamp, and double-feed rescans (the same page twice in a row). Records can appear twice from different sources. |

- **Handwritten-style notes:** 2-4 per case at most, in rotated italic. Each is on one copy only and never on an original.
- **Partial documents:** about 15% of documents in some productions are copied without their last page.

## Look-alikes that are not duplicates (different content_ids)

- PT daily notes from one template on consecutive dates.
- Chiropractic daily notes.
- The patient pain questionnaire: the same answers on two visit dates, as its own page.
- Two HIPAA authorizations with the same form, signed about a year apart.
- Three claim-line pages for the same date of service: two differ only in the CPT code (97110 vs 97112), and one differs only in the amount.
- A request letter and a re-request letter to the same provider that differ only in the letter date and reference number.
- An amended MRI report beside the original. It has an AMENDED header, one revised impression line and an addendum, and it belongs to the same event.
- Two or three custodian certifications from the same provider with different custodians, dates and page counts.
- Multi-page statements.

The generator stops with an error if two content_ids produce identical text.

## truth.json

The schema matches `alt3-1/truth.json`.

- **Page `provider`:** the author of the page content. A page filed in another provider's chart keeps its author. Law-office, insurer and defense pages carry the organization's name.
- **Event `pages`:** the clinical content_ids for that encounter, including the amended report and the questionnaire page.
- **Admin and billing pages:** never part of an event.

## Limits

- **Text only.** There are no images, skew, noise or real OCR. "Scanned" pages are clean text with substituted characters. Margin stamps are rotated text, and text extractors may place them anywhere in the reading order.
- **Phrasing repeats.** Clinical phrasing comes from finite banks per region, so it repeats across cases and across providers within a case. Different visits are told apart by dates, numbers and sampled sentences, not free prose.
- **Dates can be lost on copies.** Every original clinical page prints its date of service. Crop and OCR copies sometimes lose or corrupt it (about 97-100% of copies still contain it). That is intended, but a timeline checker should read the original.
- **PT dominates the larger cases.** Case size is controlled mainly through the number of PT visits (up to 90). In the larger cases, PT single-page notes are most of the events.
- **Clinical realism is approximate.** The codes are plausible but not audited. Fee amounts are synthetic. Some events (labs, imaging) share a date and provider with an ED visit.
- **Production 1 contains copies too.** The first occurrence of every content_id is always the clean original, labelled `original`, but production 1 also holds filed-in-chart copies.
