"""Unit tests for the duplicate detector's hard cases.

    python -m unittest test_dedup
"""
import random
import unittest

from chron.bundle import ocr_noise, rewrap
from chron.dedup import Params, deduplicate, is_duplicate, learn_overlays, numeric_tokens, page_features, skeleton

PT = """KINGSWAY PHYSICAL THERAPY
PHYSICAL THERAPY DAILY NOTE
Patient: Nguyen, Grace   DOB: 04/02/1981   MRN: 55512345
Date of service: {d}   Therapist: Lena Novak, PT, DPT
SUBJECTIVE:
  Patient reports pain {p}/10 today. Doing home exercises daily.
OBJECTIVE:
  Visit {v} of plan of care. ROM: cervical flexion 40 deg, cervical extension 35 deg.
TREATMENT:
  97110 therapeutic exercise 30 min; 97140 manual therapy 15 min; 97014 electrical stimulation 15 min.
ASSESSMENT:
  Slow progress toward goals; continues to benefit from skilled therapy.
Electronically signed by Lena Novak, PT, DPT on {d}"""

CLAIM = """HEALTH INSURANCE CLAIM FORM (CMS-1500 FORMAT)
1. TYPE OF COVERAGE: No-Fault / Auto      1a. INSURED ID: NF-48213377
2. PATIENT NAME: NGUYEN, GRACE        3. DOB: 04/02/1981
10. IS CONDITION RELATED TO: (b) AUTO ACCIDENT? [X] YES  STATE: NY
21. DIAGNOSIS: A. M54.2   B. S13.4XXA
24.  DATE OF SERVICE   PLACE  CPT/HCPCS   DESCRIPTION                       DX PTR   CHARGES
     03/14/2025       11     {cpt}       {desc}  A        {amt}
28. TOTAL CHARGE: {amt}      29. AMOUNT PAID: 0.00
32. SERVICE FACILITY: Kingsway Physical Therapy, 120 Kings Hwy, Brooklyn, NY 11223
SIGNATURE OF PHYSICIAN OR SUPPLIER: Signature on file"""


def dup(a, b):
    fa, fb = page_features([a, b])
    return is_duplicate(fa, fb, Params())


class HardCases(unittest.TestCase):
    def test_templated_notes_on_different_days_are_not_duplicates(self):
        a = PT.format(d="03/14/2025", p=6, v=7)
        b = PT.format(d="03/17/2025", p=6, v=8)
        self.assertFalse(dup(a, b))

    def test_claim_forms_same_day_different_service_are_not_duplicates(self):
        a = CLAIM.format(cpt="97110", desc="Therapeutic exercise, each 15 m", amt="190.00")
        b = CLAIM.format(cpt="97140", desc="Manual therapy, each 15 min    ", amt="90.00")
        self.assertFalse(dup(a, b))

    def test_noisy_fax_copy_is_a_duplicate(self):
        a = PT.format(d="03/14/2025", p=6, v=7)
        r = random.Random(3)
        b = "03/20/2025 10:12  FROM: Kingsway Physical Thera TO: 7185550142   P.004/031\n" + \
            "\n".join(ocr_noise(ln, 0.04, r) for ln in rewrap(a.splitlines(), 70))
        self.assertTrue(dup(a, b))

    def test_cropped_copy_is_a_duplicate(self):
        a = PT.format(d="03/14/2025", p=6, v=7)
        b = "\n".join(a.splitlines()[3:])
        self.assertTrue(dup(a, b))

    def test_garbled_word_is_not_a_number(self):
        self.assertEqual(numeric_tokens(["A11ergies: NKDA"]), set())
        self.assertIn("03/14/2025", numeric_tokens(["Date of service: O3/l4/2O25"]))

    def test_low_information_page_cannot_merge_two_documents(self):
        # Two different notes, plus a copy of one cropped down to lines both share.
        a = PT.format(d="03/14/2025", p=6, v=7)
        b = PT.format(d="03/17/2025", p=5, v=8)
        shared = "\n".join(ln for ln in a.splitlines() if ln in b.splitlines())
        res = deduplicate([a, b, shared], use_lsh=False)
        self.assertTrue(res.keep[0] and res.keep[1], "both distinct notes must be kept")


CERT = """CERTIFICATION OF CUSTODIAN OF RECORDS
I, {who}, am the duly authorized custodian of records for {where} and have authority to certify the
attached records. The attached records pertaining to Marisol Okafor (DOB 02/20/1963) are true and complete
copies of records made at or near the time of the acts recorded, by or from information transmitted by
persons with knowledge, and kept in the course of regularly conducted business activity.
I declare under penalty of perjury that the foregoing is true and correct.
Executed on {when}
{who}, Custodian of Records"""


def dup_v2(pages_text, i, j):
    from chron.dedup import document_frequency, page_features_v2
    f = page_features_v2(pages_text)
    return is_duplicate(f[i], f[j], Params(), document_frequency(f), len(pages_text))


class V2Rules(unittest.TestCase):
    def test_dates_in_every_common_format(self):
        from chron.dedup import extract_dates
        for s in ["03/14/2025", "3/14/25", "2025-03-14", "2025.03.14", "14-Mar-2025", "14 March 2025",
                  "March 14, 2025", "Mar. 14 2025", "Friday, March 14, 2025", "2025-03-14T09:30", "O3/l4/2O25"]:
            self.assertEqual(extract_dates(s), {"03/14/2025"}, s)
        self.assertEqual(extract_dates("BP 151/71 pain 2/10 S52.531A"), set())

    def test_transmission_lines_in_several_formats(self):
        from chron.dedup import is_transmission_line as t
        for ln in ["5/4/25 13:38  FROM: 555-0167  ALDER POINT  P.001/002", "** FAX ** 2025-10-13 17:12:34 TX#56755 Tamsin",
                   "SCANNED INTO CHART", "REC'D 04/02/2025", "Printed: 03/14/2025 10:22 by jdoe", "Pg 3/12", "Page 1 of 2"]:
            self.assertTrue(t(ln), ln)
        for ln in ["Request received: 07/12/2025   Records produced: 07/12/2025", "Patient reports pain 6/10 today.",
                   "printed instructions given to patient and reviewed with family"]:
            self.assertFalse(t(ln), ln)

    def test_page_stamps_found_by_behavior_not_format(self):
        from chron.dedup import stamp_shapes
        pages = [f"Note text line {i}\nZQ_EXH_{1000 + i:05d}" for i in range(20)]
        pages[3] += "\nRequest no. REQ-77001"
        pages[9] += "\nRequest no. REQ-77002"
        shapes = stamp_shapes(pages)
        self.assertIn("ZQ_EXH_#####", shapes)
        self.assertNotIn("REQ-#####", shapes)  # a request number on a few pages is content, not a stamp

    def test_copy_with_merged_and_split_words_is_a_duplicate(self):
        a = PT.format(d="03/14/2025", p=6, v=7)
        b = a.replace("Doing home", "Doinghome").replace("therapeutic exercise", "thera peutic exer cise")
        self.assertTrue(dup_v2([a, b], 0, 1))

    def test_certifications_differing_only_in_names_are_kept_apart(self):
        filler = [PT.format(d=f"03/{k:02d}/2025", p=5, v=k) for k in range(1, 9)]
        a = CERT.format(who="Gwen Szabo", where="Fennimore Immediate Care", when="3/17/26")
        b = CERT.format(who="Umar Brennick", where="Bramblewood Surgery Center", when="3/17/26")
        c = CERT.format(who="Gwen Szabo", where="Fennimore Immediate Care", when="3/17/26")
        d = CERT.format(who="Umar Brennick", where="Bramblewood Surgery Center", when="3/17/26")
        pages = [a, b, c, d] + filler   # each name appears on two pages, as a provider's name does
        self.assertFalse(dup_v2(pages, 0, 1))
        self.assertTrue(dup_v2(pages, 0, 2))

    def test_dates_written_out_still_tell_pages_apart(self):
        a = CERT.format(who="Imani Fairweather", where="Alder Point Hand Surgery", when="17-Mar-2026")
        b = CERT.format(who="Imani Fairweather", where="Alder Point Hand Surgery", when="13-Oct-2025")
        self.assertFalse(dup_v2([a, b], 0, 1))


class DateReader(unittest.TestCase):
    def test_formats_read(self):
        from chron.dedup import extract_dates
        for text in ["03/14/2025", "3/14/25", "2025-03-14", "14-Mar-2025", "March 14, 2025", "Mar. 14th 2025",
                     "Mar 14, '25", "14th Mar ’25", "the 14th day of March, 2025", "2025 MAR 14", "20250314",
                     "202503141430", "03 / 14 / 2025"]:
            self.assertEqual(extract_dates(f"seen {text} today"), {"03/14/2025"}, text)

    def test_numbers_that_are_not_dates(self):
        from chron.dedup import extract_dates
        for text in ["Pain 6 / 10 today", "Acct A0067897", "MRN 818756", "BP 129/75 HR 94", "Visit 3 of 12",
                     "OBL-9947-P11", "March 2025 note 14"]:
            self.assertEqual(extract_dates(text), set(), text)

    def test_service_label_garbled_by_ocr(self):
        from chron.chronology import service_dates
        self.assertEqual(service_dates("Col1ected: 09/16/2023  Reported: 09/17/2023"), {"09/16/2023"})
        self.assertEqual(service_dates("D0S Mar 14, '25"), {"03/14/2025"})

    def test_fax_date_does_not_support_an_entry(self):
        from chron.chronology import date_on_page
        page = "Received by fax Mar 18 2025 13:29 -- page 2 of 9\nORTHO NOTE  Mar 17, '25\nPain 6/10."
        self.assertTrue(date_on_page("03/17/2025", page))
        self.assertFalse(date_on_page("03/18/2025", page))

    def test_signature_and_other_dates_do_not_support_an_entry(self):
        from chron.chronology import date_on_page
        page = ("Arrival: March 14, 2025   DOB: Aug. 23, 1972\nComparison: radiographs from Friday, March 7, 2025.\n"
                "Interpreted by B. Paredes, MD. Signed Saturday, March 15, 2025\nNext visit 04/01/2025")
        self.assertTrue(date_on_page("03/14/2025", page))
        for wrong in ("03/15/2025", "08/23/1972", "03/07/2025", "04/01/2025"):
            self.assertFalse(date_on_page(wrong, page), wrong)
        # a provider that prints the visit date only beside the signature still passes
        self.assertTrue(date_on_page("03/14/2025", "Progress note. Pain 5/10.\nSigned 03/14/2025 J. Doe, MD"))

    def test_month_joined_to_day_by_hyphen(self):
        from chron.dedup import extract_dates
        self.assertEqual(extract_dates("Service Dt: Mar-26-2025"), {"03/26/2025"})


class V3Rules(unittest.TestCase):
    """v3 learns a file's own overlay lines from copies it is already sure of."""

    def _file(self):
        notes = ["Ice twice daily helped.", "Slept poorly after driving to work.", "Neck stiff in the morning only.",
                 "Missed two days of exercises.", "Turning head to check mirrors still hurts.", "Lifting grocery bags hurts.",
                 "Able to sit through a two hour meeting.", "Headache returned after computer work."]
        # Different visits are different notes: each gets its own paragraph, as real notes do.
        originals = [PT.format(d=f"03/{k:02d}/2025", p=k % 9, v=k) + "\nASSESSMENT:\n  " + (notes[k - 1] + " ") * 6
                     for k in range(1, 9)]
        copies = [o + f"\nLITIGATION BINDER TAB {k + 3} PRODUCED 0{k % 9 + 1}/2{k}/2026 BY HALVERSON" for k, o in enumerate(originals)]
        return originals, copies

    def test_skeleton_ignores_digits_and_scan_lookalikes(self):
        self.assertEqual(skeleton("BINDER TAB 12 PRODUCED 03/02/2026"), skeleton("BlNDER TAB 7 PRODUCED 11/19/2025"))

    def test_overlay_line_learned_and_copies_removed(self):
        originals, copies = self._file()
        self.assertIn(skeleton("LITIGATION BINDER TAB 4 PRODUCED 01/20/2026 BY HALVERSON"), learn_overlays(originals + copies))
        res = deduplicate(originals + copies, Params(version="v3"), use_lsh=False)
        self.assertEqual(sum(res.keep), len(originals))
        n = len(originals)
        for k in range(n):   # each visit survives, as itself or as its own copy
            self.assertIn(res.representative[k], (k, k + n))

    def test_template_lines_are_not_learned(self):
        originals, copies = self._file()
        learned = learn_overlays(originals + copies)
        for line in PT.splitlines():
            if len(skeleton(line)) >= 6:
                self.assertNotIn(skeleton(line), learned, line)


if __name__ == "__main__":
    unittest.main()
