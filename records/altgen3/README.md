# alt3: synthetic personal-injury case files

`generate_alt3.py` builds 10 fictional personal-injury case files. In each one, the same medical records arrive several times (duplicates), mixed with pages that look alike but are separate originals. The files are a held-out test for a duplicate-page detector and a medical-chronology checker. All patients, clinicians, providers, insurers, law firms and mediators are invented. No real patient data is used.

```
python records/altgen3/generate_alt3.py      # run from the provider-match folder
```

The script writes `records/data/alt3/alt3-<n>/records.pdf` and `truth.json` for n = 1..10, then prints one line per case and a total. Seeds are fixed, so reruns are byte-identical. It needs Python 3.12, PyMuPDF and numpy.

## Cases

| # | Incident | Main injuries |
|---|----------|---------------|
| 1 | Stand-up electric scooter fall | displaced right clavicle fracture (ORIF), forearm abrasions |
| 2 | Slip on ice outside a store | lumbar sprain, L4-L5 disc extrusion, radiculopathy (2 epidural injections) |
| 3 | Trampoline-park landing | ACL tear + medial meniscus tear (arthroscopic reconstruction) |
| 4 | Rideshare rear-end, rear passenger | whiplash, bilateral jaw sprain / TMJ, post-traumatic headache |
| 5 | Falling storefront sign | fractured and luxated incisors, lip laceration, later scar revision |
| 6 | Pressure-cooker lid failure | partial-thickness burns of the right hand and forearm (skin graft) |
| 7 | Golf-cart rollover | right rib fractures 5-8, pneumothorax (chest tube), intercostal blocks |
| 8 | Thrown from a horse | concussion with brief loss of consciousness, neck strain, post-concussion syndrome |
| 9 | Restaurant food poisoning | Salmonella enteritis, dehydration, acute kidney injury (5-day stay, reference labs) |
| 10 | Forklift ran over the foot | 2nd/3rd metatarsal fractures (ORIF), crush injury, later CRPS (sympathetic block) |

Each case has 1-2 pre-incident visits (`prior_visit`), then 5-8 treating providers. Provider types used are EMS, urgent care, emergency department, a hospital stay with one note per day, an imaging center, a reference lab, specialists (orthopaedics, pain, neurosurgery, orofacial pain, neurology, oral surgery, endodontics, plastics, burn clinic, pulmonology, dermatology/laser, neuropsychology, infectious disease, GI, occupational medicine), an ambulatory surgery center, and therapy (PT, chiropractic, OT/hand, vestibular). No pharmacy records are included.

Each case also has non-clinical parties: a plaintiff firm, a liability insurer, a defense firm and a mediator.

Codes are real ICD-10-CM and CPT codes chosen to fit the case. The seventh character switches from A to D once routine follow-up starts (therapy, and visits more than 14 days out). EMS transport bills use HCPCS A0427/A0425 on the bill pages only. Event `procedures` hold CPT codes only.

## Document styles

Each provider gets its own layout. Ten layouts exist, and a case cycles through them so providers in the same case look different:

- `eqbox`: header in a `=`/`||` box, right-aligned date.
- `hashbox`: `#` box with numbered sections (`1. HISTORY ...`).
- `soap`: `S:` / `O:` / `A:` / `P:` lines.
- `narrative`: letterhead with dictated paragraphs and a "Sincerely" signature.
- `colon`: fields aligned on `:` in a monospace font.
- `bilingual`: Spanish / English labels, used for one clinic in cases 2, 9 and 10.
- `stamped`: each section starts with a `[hh:mm]` timestamp and the note ends "signed and locked".
- `dash`: section names underlined with dashes.
- `tilde`: `~` banner with `[bracketed]` labels.
- `grid`: `+---+` / `|` boxed forms.

Tables (vitals, flowsheets, MARs, claim lines, outcome forms) are printed in monospace. Depending on the style, columns are separated by ` : `, ` | ` or spaces.

Every signature carries a date and time. Fonts are Helvetica, Times or Courier, with sizes varying by provider.

Each provider uses one date format: `03/14/2025`, `3-14-2025`, `14 Mar 2025`, `March 14th, 2025`, `2025/03/14`, `Mar 14, '25` or `20250314`. Day-first numeric dates are never used.

## Copy mechanisms (the `mechanism` field joins the labels with `+`)

The case file is a set of productions. Production 1 always comes first; the order of productions 2-6 is shuffled per case.

1. **`provider_release`** (production 1). Each provider answers the plaintiff firm's request. The packet is a fax cover, the firm's request letter, the patient's HIPAA authorization (one original reused in every packet), a custodian certification, then the whole chart. Clinical pages come first and billing pages last.
2. **Transmission lines**, one style per packet, at the top or bottom with date, time, job/document id and page counter:
   - `fax`: `07/02/2025 15:15  FROM:(209) 555-0136  HPT HIM   JOB 84443   P.002/022`
   - `efax`: `eFax relay | rcvd 2025-07-09T16:13 | doc 19730 | pg 5/10`
   - `secure`: `<<SENT VIA SECUREXCH JUL 9 2025 16:13:35 ID=... [5/10]>>`
   - `relay`: `Received by fax Aug 24 2025 09:12 -- page 2 of 22 -- <provider>`
   - Some packets arrive by mail and have no line.
3. **`embedded_in_chart`**: copies of other providers' pages filed inside a chart. The hospital holds the EMS run sheet and ER note. Specialists hold outside imaging reports. Therapy holds the referring consult. The surgery center holds the surgeon's consult. These copies often carry the sender's fax line and an "OUTSIDE RECORD - FILED TO CHART" or "SCANNED -- HIM" stamp. `provider` is the chart holder.
4. **`second_request_reprint`** (production 2). About a third of providers re-produce after a second request. Each re-production has a new cover, a new request letter, and a certification signed by a different custodian. The records are re-printed from "the current system", which adds the **`reflow`** label: different wrap width, font size and sometimes font family. Some re-productions leave out billing or the embedded outside records.
5. **`portal_download`** (production 3). The patient downloads clinical notes from 1-2 provider portals. The footer reads `Downloaded from patient portal (... HealthLink account) on Apr 24, 2026 7:52 AM by R. ... -- 1/10`. Many of these pages also have **`header_missing`**: the whole letterhead and patient block is dropped, as a portal print view would.
6. **`insurer_claim_file`** (production 4). The firm's demand letter, every bill, and a subset of clinical pages. Each page has a "RECEIVED ... CLAIMS DIV." stamp and **`claim_bates`** numbering (`NGI-2025-77471 / 0003`, rising page by page).
7. **`handwritten_annotation`** (inside production 4): adjuster notes in italic ("gap in tx -- ask -- adj.", "causation?"), sometimes with a rotated margin mark. Only one copy of any original is annotated.
8. **`defense_production`** (production 5). A cover letter, then the certification and a subset of each subpoenaed provider's chart. Every page is scanned (**`ocr_scan`**) and carries **`bates`** numbering (`AQDG-DEF 000291`, rising page by page).
9. **`ocr_scan` damage**, with its own confusion set: `rn->m`, `m->rn`, `cl->d`, `0<->O`, `1<->l`, `I->|`, `5<->S`, `8<->B`, `e->c`, `h->b`, `ii->u`, `6->G`, `.->,`, `g->q`, `Z->2`, `t->f`, `a->o`, `3->8`, `/->l` and `u->v`. On top of that it merges words (drops a space), splits words, inserts stray symbols (``~ ` ^ ' _ ° ¦ ;``) and breaks long lines in two. Bates, claim and exhibit numbers are applied after scanning and are never damaged. Overlay stamps and fax lines are damaged with the page.
10. **`cropped`** (productions 5 and 6): the first two body lines and the last body line are lost, and long lines are cut off at 64-80 characters.
11. **`two_up`** (production 5): two consecutive original pages from the same provider are printed side by side on one sheet. That sheet's `content_id` is the **first** of the two originals, because it shows all of that page's content. The second original's content also appears on the sheet, but its own `content_id` is recorded only on its stand-alone copies, which always exist elsewhere in the file. A detector that matches the second half to its original is not wrong; truth simply records the first.
12. **`mediator_binder`** (production 6). New exhibit-index pages, then key records (ER notes, H&Ps, operative reports, imaging, consults, procedure notes, re-evaluations, discharge summaries, ledgers). Each page carries an **`exhibit_stamp`** (`EX. 07  |  p. 2 of 3`), and some pages are reflowed or cropped.
13. **`stamp`**: overlay stamps placed as their own line at the top or bottom, rotated in the left or right margin, or appended to an existing line. The texts are:
    - `IMAGED <date>`
    - `INDEXED BY: <initials> <yyyymmdd>`
    - `ATTORNEY WORK COPY`
    - `DUPLICATE - DO NOT FILE`
    - `Released per authorization #<no>`
    - `RECEIVED <date> - CLAIMS DIV.`
    - `SCANNED -- HIM`
    - `COPY FOR MEDIATION -- CONFIDENTIAL`
    - `OUTSIDE RECORD - FILED TO CHART <date>`
    - `REVIEWED -- NOT FOR RE-RELEASE`

## Look-alike originals (separate `content_id`s, never identical text)

- Hospital daily progress notes on consecutive days, each with its own 24-hour nursing flowsheet and its own medication administration record.
- Therapy, chiropractic, OT and vestibular daily notes on different dates. They share a template but differ in visit number, pain score, measurements, exercises and billed units.
- Specialist follow-ups on different dates.
- The same outcome form (QuickDASH, Oswestry, NDI, LEFS, DHI or PSFS) filled at the evaluation and again at the re-evaluation, plus a work-status / restriction form filled at the first two specialist visits.
- Claim-form lines on the same date of service with different codes and amounts (for example ED facility vs. imaging, or 97110 vs. 97140 on one therapy day). The EMS ledger lists both the ALS1 transport charge and the mileage charge for one date.
- First and second request letters. Their body text is identical; they differ only in date, file reference and document reference (shown in the PDF next to the transmission line).
- A corrected imaging report (one per imaging center) that supersedes the original report for the same study and changes one numbered finding.
- Two custodian certifications from the same provider: the first and second production, signed by different custodians.
- Fax cover sheets for the first and second production.

## truth.json

The file follows the requested schema exactly. Conventions:

- `pages[].provider` is whoever produced that copy. For production 1 that is the releasing provider, or the chart holder for embedded copies. For production 3 it is the portal's provider. For productions 4, 5 and 6 it is the insurer, defense firm or mediator.
- `production` is 1-6 as numbered above.
- `content_id` values are `c0001`, `c0002`, and so on. Pages with equal ids hold the same record content.
- `events[].pages` lists the original **clinical** pages that record the encounter. Bills and admin pages are not linked to events.
  - A hospital day's event includes its progress note (or the H&P on day 1), flowsheet, MAR and, on the last day, the discharge summary.
  - The operative report and anesthesia record form a separate `surgery` event on the same date.
  - An imaging event includes the corrected report.
- Lab events use the collection date.
- Event kinds:
  - EMS, urgent care and ER: `er_visit`. Imaging done in the ER or urgent care is its own `imaging` event.
  - Hospital days, dental, burn-clinic and other specialist visits, and a post-incident visit to the primary-care doctor (case 9): `office_visit`.
  - Chiropractic, OT and vestibular care: `pt_eval`, `pt_visit` and `pt_reeval`.
  - Epidural, nerve and sympathetic blocks and trigger points: `injection`.
- Each event has its own `doc_id` (`d001`...).

## Size control

`run_case` tries a fixed list of scale factors in order. Each scale changes how many providers re-produce and what share of pages go to the insurer, defense and mediator sets. It keeps the first result with a duplicate share of 50-75% and 220-420 pages, or the closest result if none qualifies. Case 5 has the fewest originals (79) and comes out at 219 pages.

## Limits

- Text is templated, so wording repeats across cases. Narrative depth is modest.
- No images, handwriting or real scan noise are rendered; "scanned" and "handwritten" exist only as text effects.
- The two-up sheet and the embedded copies make some "duplicate" judgments partial by design.
- Stamps and transmission lines are rendered as extractable text, never as images.
