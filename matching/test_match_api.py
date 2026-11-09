"""Tests for the web API.

    python -m unittest test_api

The key test: for every labeled query, the API's verdict agrees with how
evaluate.py scores it, so the page can never show a different result from
the reported numbers.
"""
import unittest

from fastapi.testclient import TestClient

import match_api as api
from evaluate import correct, gold, load
from matcher import baseline

client = TestClient(api.app)


class ApiTest(unittest.TestCase):
    def test_health(self):
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        h = r.json()
        self.assertEqual(h["locations"], len(api.m.locs))
        self.assertEqual(h["min_score"], api.m.p["min_score"])

    def test_queries_split(self):
        test = client.get("/api/queries").json()
        self.assertEqual(len(test), len(load("test")))
        self.assertTrue(all(q["split"] == "test" for q in test))
        self.assertEqual(len(client.get("/api/queries?split=all").json()), len(load("all")))

    def test_match_returns_matcher_answer(self):
        body = {"name": "NYU Langone ortho", "address": "333 E 38th St", "zip": "10016"}
        r = client.post("/api/match", json=body).json()
        want = api.m.match(body["name"], body["address"], body["zip"])
        self.assertEqual(r["npi"], want["npi"])
        self.assertEqual(r["confidence"], want["confidence"])
        self.assertEqual([x["npi"] for x in r["runners_up"]], [x["npi"] for x in want["runners_up"]])

    def test_abstain_has_reason(self):
        r = client.post("/api/match", json={"name": "Mount Sinai cardiology",
                                            "address": "1 Gustave L Levy Pl", "zip": "10029"}).json()
        self.assertFalse(r["answered"])
        self.assertIn(r["reason"], ("low_score", "too_close", "no_candidates"))

    def test_bad_input(self):
        self.assertEqual(client.post("/api/match", json={"name": ""}).status_code, 422)
        self.assertEqual(client.post("/api/match", json={"name": "x", "query_id": "nope"}).status_code, 404)

    def test_verdicts_agree_with_evaluate(self):
        pharm = {l.npi for l in api.m.locs if "PHARMACY" in l.taxonomy.upper()}
        for row in load("all"):
            with self.subTest(query=row["id"]):
                r = client.post("/api/match", json={"name": row["query_name"], "address": row["query_address"],
                                                    "zip": row["query_zip"], "query_id": row["id"]}).json()
                ok = gold(api.m.locs, row)
                res = api.m.match(row["query_name"], row["query_address"], row["query_zip"])
                ev = r["evaluation"]
                self.assertEqual(ev["matcher_correct"], correct(res["npi"], ok))
                self.assertEqual(ev["matcher_strict_correct"],
                                 correct(res["npi"], ok) and res["npi"] not in pharm)
                self.assertEqual(ev["baseline_correct"], correct(baseline(api.m.locs, row["query_name"]), ok))
                if res["same_in_registry"]:
                    self.assertEqual([x["npi"] for x in r["same_in_registry"]], res["same_in_registry"])

    def test_explain_agrees_with_match_on_every_labeled_query(self):
        for row in load("all"):
            with self.subTest(query=row["id"]):
                body = {"name": row["query_name"], "address": row["query_address"], "zip": row["query_zip"]}
                e = client.post("/api/match/explain", json=body).json()
                res = api.m.match(row["query_name"], row["query_address"], row["query_zip"])
                self.assertEqual(e["top_score"], res["confidence"])
                self.assertEqual(e["answered"], res["npi"] is not None)
                if res["top"]:
                    self.assertEqual(e["candidates"][0]["npi"], res["top"]["npi"])


if __name__ == "__main__":
    unittest.main()
