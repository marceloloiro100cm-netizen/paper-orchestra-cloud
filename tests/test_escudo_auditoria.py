"""Onda 3 do plano V2: fatores de contexto (M18), verificação manual (M24) e escudo (M06)."""
import sys
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from audit_shield import build_shield
from source_quality import manual_verification, quality_factors


def ref_item(classification="metadata_match", oa_quality=None, doi="10.1000/x", year="2020",
             editorial="no_notice_found", title="Sala de aula invertida: uma revisão"):
    return {"reference": {"key": "k1", "title": title, "doi": doi, "year": year},
            "classification": classification,
            "sources": {"openalex": {"status": "ok", "quality": oa_quality or {}}},
            "editorial": {"editorial_status": editorial, "label": editorial}}


class QualityFactorsTest(unittest.TestCase):
    def test_journal_article(self):
        factors = quality_factors(ref_item(oa_quality={"document_type": "article", "venue_type": "journal",
                                                       "venue": "Revista X", "cited_by_count": 12}),
                                  today=date(2026, 11, 24))
        self.assertEqual(factors["peer_review_signal"], "periodico_provavelmente_revisado")
        self.assertEqual(factors["age_years"], 6)
        self.assertEqual(factors["citations_openalex"], 12)
        self.assertNotIn("score", factors)
        self.assertIsNone(factors["human_assessment"])

    def test_preprint_is_flagged_not_rejected(self):
        factors = quality_factors(ref_item(oa_quality={"document_type": "preprint", "venue_type": "repository"}))
        self.assertEqual(factors["peer_review_signal"], "preprint_ou_repositorio")

    def test_unknown_and_scielo(self):
        factors = quality_factors(ref_item(doi="10.1590/S0034-89102010005000024", year=""))
        self.assertEqual(factors["peer_review_signal"], "desconhecido")
        self.assertTrue(factors["scielo_doi"])
        self.assertIsNone(factors["age_years"])

    def test_retraction_signals_kept_separate(self):
        factors = quality_factors(ref_item(oa_quality={"is_retracted": True}, editorial="no_notice_found"))
        self.assertEqual(factors["retraction_signals"],
                         {"crossref_retraction_watch": "no_notice_found", "openalex_is_retracted": True})


class ManualVerificationTest(unittest.TestCase):
    def test_links_only_when_not_confirmed(self):
        self.assertIsNone(manual_verification(ref_item("metadata_match")))
        manual = manual_verification(ref_item("not_found", title="Educação & tecnologia {no} Brasil"))
        self.assertEqual(manual["status"], "verificacao_manual_sugerida")
        hosts = [urlparse(link["url"]).hostname for link in manual["links"]]
        self.assertEqual(hosts, ["scholar.google.com", "search.scielo.org", "brapci.inf.br"])
        query = parse_qs(urlparse(manual["links"][0]["url"]).query)["q"][0]
        self.assertEqual(query, "Educação & tecnologia no Brasil")

    def test_no_title(self):
        self.assertEqual(manual_verification(ref_item("not_found", title=""))["links"], [])


class ShieldTest(unittest.TestCase):
    def test_levels_and_stages(self):
        references = {"checked": 4, "skipped_by_limit": 0,
                      "editorial_summary": {"counts": {"retracted": 1}},
                      "items": [ref_item("metadata_conflict"), ref_item(editorial="retracted"),
                                ref_item("not_found"), ref_item(oa_quality={"is_retracted": True})]}
        evidence = {"quotes": {"summary": {"quotes": 2}, "pointers": [{"chunk_id": "x", "status": "unknown"}],
                               "quotes": [{"quote": "q1", "status": "not_found_in_sources"},
                                          {"quote": "q2", "status": "approximate", "overlap": 0.85}]},
                    "matrix": {"summary": {"claims": 2},
                               "claims": [{"claim_id": "c_001", "text": "t", "cites": ["a"], "audit_state": "sem_evidencia_no_corpus"},
                                          {"claim_id": "c_002", "text": "37%", "cites": [], "audit_state": "sem_evidencia_no_corpus"}]}}
        audit = {"summary": {"findings": 1}, "findings": [{"code": "percentages_without_experiments",
                                                           "title": "Percentuais sem experimentos", "detail": "d"}]}
        shield = build_shield(audit, references, evidence)
        titles = {(i["level"], i["title"]) for i in shield["items"]}
        self.assertIn(("alta", "Metadados divergentes"), titles)
        self.assertIn(("alta", "Obra retratada ou retirada"), titles)
        self.assertIn(("alta", "OpenAlex indica retratação"), titles)
        self.assertIn(("alta", "Ponteiro para trecho inexistente"), titles)
        self.assertIn(("alta", "Percentuais sem experimentos"), titles)
        self.assertIn(("media", "Citação literal não encontrada nas fontes anexadas"), titles)
        self.assertIn(("baixa", "Citação com redação diferente da fonte"), titles)
        levels = [i["level"] for i in shield["items"] if i["title"] == "Afirmação sem evidência nas fontes anexadas"]
        self.assertEqual(sorted(levels), ["baixa", "media"])
        self.assertEqual([i["level"] for i in shield["items"]], sorted((i["level"] for i in shield["items"]),
                                                                       key=["alta", "media", "baixa"].index))
        self.assertEqual(shield["stages"]["4_suporte_semantico"]["status"], "parcial")
        self.assertIsNone(shield["verdict"])

    def test_without_reports_nothing_is_claimed(self):
        shield = build_shield(None, None, None)
        self.assertEqual(shield["items"], [])
        self.assertEqual(shield["stages"]["1_ponteiros_citacoes"]["status"], "nao_executado")
        self.assertEqual(shield["stages"]["2_metadados"]["status"], "indisponivel")
        self.assertTrue(any("não comprova" in x for x in shield["limitations"]))


if __name__ == "__main__":
    unittest.main()
