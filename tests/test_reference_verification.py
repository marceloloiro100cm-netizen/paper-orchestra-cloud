"""Testes sem rede, sem chaves de API, sem chamadas de modelos e sem custo."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from reference_verification import (
    parse_bibtex, canonical_doi, similarity, classify, verify_bibliography,
)


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None, allow_redirects=None):
        self.calls.append((url, params, headers))
        assert url.startswith("https://"), url
        assert allow_redirects is False
        if "api.crossref.org" in url:
            return FakeResponse(200, {"message": {
                "title": ["Complex systems in applied science"], "DOI": "10.1000/example",
                "issued": {"date-parts": [[2024, 1, 1]]}
            }})
        if "api.openalex.org" in url:
            return FakeResponse(200, {
                "title": "Complex systems in applied science",
                "doi": "https://doi.org/10.1000/example",
                "publication_year": 2024,
                "id": "https://openalex.org/W12345"
            })
        if "api.semanticscholar.org" in url:
            return FakeResponse(200, {
                "title": "Complex systems in applied science",
                "year": 2024,
                "externalIds": {"DOI": "10.1000/example"},
                "url": "https://www.semanticscholar.org/paper/demo"
            })
        raise AssertionError("Endpoint inesperado: " + url)


class UnavailableSession:
    def get(self, url, **kwargs):
        return FakeResponse(429, {})


class ReferenceVerifierTests(unittest.TestCase):
    def test_parse_nested_fields_and_doi(self):
        bib = r"""@article{sample2024,
          title = {{Complex} systems in {applied} science},
          author = {Doe, Jane and Roe, John},
          doi = {https://doi.org/10.1000/example},
          year = {2024},
          note = {Some {nested} note}
        }"""
        entries = parse_bibtex(bib)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["key"], "sample2024")
        self.assertEqual(entries[0]["doi"], "10.1000/example")
        self.assertEqual(entries[0]["year"], "2024")
        self.assertGreater(similarity(entries[0]["title"], "Complex systems in applied science"), 0.95)

    def test_metadata_agreement_does_not_claim_scientific_truth(self):
        bib = r"@article{sample, title={Complex systems in applied science}, year={2024}, doi={10.1000/example}}"
        session = FakeSession()
        report = verify_bibliography(bib, session=session, pause=False)
        self.assertEqual(report["checked"], 1)
        item = report["items"][0]
        self.assertEqual(item["classification"], "metadata_match")
        self.assertEqual(len(item["confirmed_by"]), 3)
        self.assertTrue(any("não comprovam" in x.lower() for x in report["limitations"]))
        # Crossref, OpenAlex, Semantic Scholar + consulta de avisos editoriais (M07).
        self.assertEqual(len(session.calls), 4)
        self.assertEqual(session.calls[-1][1], {"filter": "updates:10.1000/example", "rows": 20})
        self.assertEqual(item["editorial"]["editorial_status"], "no_notice_found")
        self.assertNotIn("_editorial_record", item["sources"]["crossref"])
        for url, params, headers in session.calls:
            self.assertNotIn("GEMINI", str(url) + str(params))

    def test_rate_limiting_produces_inconclusive_not_invented(self):
        bib = r"@article{sample, title={Some other paper}, year={2024}, doi={10.1000/example}}"
        report = verify_bibliography(bib, session=UnavailableSession(), pause=False)
        self.assertEqual(report["items"][0]["classification"], "inconclusive")
        self.assertTrue(all(x["status"] == "unavailable"
                            for x in report["items"][0]["sources"].values()))

    def test_metadata_conflict_reported(self):
        mismatch = {"status": "ok", "title": "Unrelated laboratory manual",
                    "doi": "10.1000/example", "year": "2018"}
        report = classify({"title": "Complex systems in applied science",
                           "doi": "10.1000/example", "year": "2024"},
                          {"crossref": mismatch})
        self.assertEqual(report["classification"], "metadata_conflict")

    def test_maximum_references_limits_queries(self):
        bib = "".join(f"@article{{k{i},title={{Title {i}}}, year={{2024}}}}\n" for i in range(23))
        report = verify_bibliography(bib, max_references=0, session=FakeSession(), pause=False)
        self.assertEqual(report["checked"], 0)
        self.assertEqual(report["skipped_by_limit"], 23)

    def test_abnt_templates_present_and_explicitly_experimental(self):
        root = Path(__file__).resolve().parents[1]
        for folder in ("abnt-artigo", "abnt-dissertacao"):
            path = root / "worker" / "templates" / folder
            tex = (path / "template.tex").read_text(encoding="utf-8")
            guide = (path / "guidelines.md").read_text(encoding="utf-8").lower()
            self.assertIn(r"\documentclass", tex)
            self.assertIn("abntex2", tex)
            self.assertIn(r"\bibliography{references}", tex)
            self.assertIn("experimental", guide)
            self.assertNotIn("garantia de conformidade", guide)


if __name__ == "__main__":
    unittest.main()
