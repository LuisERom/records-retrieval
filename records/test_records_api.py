"""Tests for the viewer API.

    python -m unittest test_api      (needs the data from `python generate.py`)
"""
import unittest

from fastapi.testclient import TestClient

import records_api as api
from chron.dedup import deduplicate, pdf_texts

client = TestClient(api.app)


class ApiTest(unittest.TestCase):
    def test_cases_listed(self):
        cs = client.get("/api/cases").json()
        self.assertTrue(any(c["split"] == "test2" for c in cs))

    def test_dedup_matches_the_detector(self):
        d = client.get("/api/cases/dev/dev-1/dedup").json()
        keep = deduplicate(pdf_texts(api.DATA / "dev" / "dev-1" / "records.pdf")).keep
        self.assertEqual([p["kept"] for p in d["pages"]], keep)
        self.assertEqual(d["kept"], sum(keep))
        self.assertTrue(all(g["label"] for g in d["groups"]))

    def test_every_oracle_citation_is_highlighted(self):
        ch = client.get("/api/cases/dev/dev-2/chronology").json()
        cites = [c for e in ch["entries"] for c in e["citations"]]
        self.assertTrue(cites)
        for c in cites:
            boxes = client.get(f"/api/cases/dev/dev-2/pages/{c['page']}/highlight", params={"quote": c["quote"]}).json()
            self.assertTrue(boxes, f"quote not located: page {c['page']} {c['quote']!r}")
            for b in boxes:
                self.assertTrue(0 <= b["x"] <= 1 and 0 <= b["y"] <= 1)

    def test_page_image_and_bad_paths(self):
        r = client.get("/api/cases/dev/dev-1/pages/1.png")
        self.assertEqual(r.headers["content-type"], "image/png")
        self.assertEqual(client.get("/api/cases/dev/dev-1/pages/99999.png").status_code, 404)
        self.assertEqual(client.get("/api/cases/nope/dev-1/dedup").status_code, 404)
        self.assertEqual(client.get("/api/cases/dev/..%2Ftest/dedup").status_code, 404)

    def test_walkthrough_examples_are_what_they_claim(self):
        w = client.get("/api/cases/test2/test2-2001/walkthrough").json()
        self.assertTrue(w["duplicate_pair"]["duplicate"])
        self.assertIsNotNone(w["hard_negative"])
        self.assertFalse(w["hard_negative"]["duplicate"])
        self.assertTrue(w["hard_negative"]["numbers_only_a"] and w["hard_negative"]["numbers_only_b"])
        self.assertTrue(any(line["removed"] for line in w["clean_lines"]))
        self.assertEqual(w["kept"] + w["removed"], w["pages"])

    def test_checker_demo_drops_only_entries_that_fail_a_check(self):
        d = client.get("/api/cases/test2/test2-2001/checker-demo").json()
        self.assertTrue(d["falsified"])
        for e in d["falsified"]:
            self.assertFalse(all(c["ok"] for c in e["checks"]), e)
        self.assertTrue(all(c["ok"] for c in d["passing"]["checks"]))


if __name__ == "__main__":
    unittest.main()
