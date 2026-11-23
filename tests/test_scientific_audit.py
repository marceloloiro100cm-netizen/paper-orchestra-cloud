"""Testes offline do relatório: nenhuma chamada ao modelo ou rede."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from scientific_audit import audit_text


class ScientificAuditTests(unittest.TestCase):
    def test_flags_unproven_percentage_and_verification(self):
        report = audit_text(
            "O Verification Oracle alcançou 100% de integridade. A taxa de erro foi 12%.",
            r"Resultados com referência \\citep{a2026} e \\cite{missing}.",
            "@article{a2026, title={Estudo}}",
            "Nenhum experimento científico foi realizado.",
        )
        codes = {f["code"] for f in report["findings"]}
        self.assertIn("percentages_without_experiments", codes)
        self.assertIn("verification_claims", codes)
        self.assertIn("missing_bibliography_keys", codes)
        missing = next(f for f in report["findings"] if f["code"] == "missing_bibliography_keys")
        self.assertEqual(missing["examples"], ["missing"])
        self.assertEqual(report["status"], "human_review_required")
        self.assertEqual(report["summary"]["citation_keys_missing"], 1)
        self.assertTrue(report["input_declares_no_experiments"])

    def test_reference_keys_matching_not_truth_verification(self):
        report = audit_text(
            "Texto teórico sem percentuais.",
            r"Veja \\citet{doe2024}.",
            "@article{doe2024, title={Título}}",
            "Revisão teórica sem dados quantitativos.",
        )
        self.assertEqual(report["summary"]["citation_keys_missing"], 0)
        self.assertEqual(report["summary"]["bibliography_keys_found"], 1)
        self.assertEqual(report["status"], "human_review_required")
        self.assertTrue(any("não comprova" in x.lower() for x in report["limitations"]))

    def test_empty_bibliography_warns_even_without_citations(self):
        report = audit_text("Texto simples", "", "", "Sem dados.")
        self.assertIn("no_bibliography", [f["code"] for f in report["findings"]])


if __name__ == "__main__":
    unittest.main()
