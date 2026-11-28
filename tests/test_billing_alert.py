"""Aviso de saldo pré-pago esgotado (BYOK). Sem rede."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "tests"))
import billing_alert  # noqa: E402
import model_access  # noqa: E402
from test_biblioteca_exportacao import DB  # noqa: E402

GOOGLE = ("402 RESOURCE_EXHAUSTED. {'error': {'code': 402, 'message': 'Your prepayment credits are "
          "depleted. Please go to AI Studio at https://ai.studio/projects to manage your project'}}")
DELETE = object()


class BillingAlertTest(unittest.TestCase):
    def test_detects_google_message_only(self):
        self.assertTrue(billing_alert.prepay_depleted(GOOGLE))
        self.assertTrue(billing_alert.prepay_depleted("Your prepay credits are depleted. A payment is due"))
        self.assertFalse(billing_alert.prepay_depleted("429 RESOURCE_EXHAUSTED quota exceeded"))
        self.assertFalse(billing_alert.prepay_depleted(None))
        self.assertNotIn("—", billing_alert.MESSAGE)

    def test_log_tail(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as log:
            log.write("x" * 300_000 + "\n" + GOOGLE)
        self.assertTrue(billing_alert.log_mentions_depleted(log.name))
        self.assertFalse(billing_alert.log_mentions_depleted(log.name + ".inexistente"))

    def test_mark_shows_in_account_and_clear(self):
        db = DB()
        db.store[("research_credentials", "u1")] = {"status": "active", "model_access": {
            "status": "verified", "models": {model_access.FLASH_MODEL: "supported"}}}
        billing_alert.mark(db, "u1", "2026-11-25T13:00:00+00:00")
        info = model_access.account_model_access(db, "u1")
        self.assertEqual(info["billing_alert"]["state"], "prepay_depleted")
        self.assertEqual(info["verified_models"], [model_access.FLASH_MODEL])  # não bloqueia
        billing_alert.clear(db, "u1", None)
        self.assertIsNone(model_access.account_model_access(db, "u1")["billing_alert"])
        billing_alert.mark(db, "sem-chave", "agora")  # sem credencial: nada a marcar
        self.assertNotIn(("research_credentials", "sem-chave"), db.store)

    def test_probe_classifies_402(self):
        self.assertEqual(model_access.classify_probe_status(402), "no_credit")


if __name__ == "__main__":
    unittest.main()
