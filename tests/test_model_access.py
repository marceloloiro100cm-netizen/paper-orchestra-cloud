"""Testes isolados das permissões Gemini, sem chamadas a APIs pagas."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from model_access import (FLASH_MODEL, PRO_MODEL, allowed_models, account_model_access,
                          classify_probe_status, validate_key_and_models)


class Snapshot:
    def __init__(self, record):
        self.record = record
        self.exists = record is not None

    def to_dict(self):
        return self.record


class Doc:
    def __init__(self, storage, uid):
        self.storage, self.uid = storage, uid

    def get(self):
        return Snapshot(self.storage.get(self.uid))


class Collection:
    def __init__(self, storage):
        self.storage = storage

    def document(self, uid):
        return Doc(self.storage, uid)


class DB:
    def __init__(self, records):
        self.records = records

    def collection(self, name):
        self_name = name
        assert self_name == "research_credentials"
        return Collection(self.records)


class ModelAccessTests(unittest.TestCase):
    def test_short_probe_enables_flash_but_never_pro_for_free_key(self):
        calls = []
        def fake(url, key, payload=None):
            calls.append((url, key, payload))
            if url.endswith("models?pageSize=1000"):
                return 200, {"models": []}
            if FLASH_MODEL in url:
                return 200, {"candidates": []}
            return 403, {}
        key = "AQ." + "z" * 44
        result = validate_key_and_models(key, transport=fake)
        self.assertEqual(result["models"][FLASH_MODEL], "supported")
        self.assertEqual(result["models"][PRO_MODEL], "unavailable")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call[1] == key for call in calls))
        self.assertNotIn(key, str(result))
        db = DB({"u": {"status": "active", "model_access": result}})
        self.assertEqual(allowed_models(account_model_access(db, "u")), [FLASH_MODEL])

    def test_pro_only_after_actual_generation_success(self):
        def fake(url, key, payload=None):
            return 200, {}
        result = validate_key_and_models("A" * 39, transport=fake)
        self.assertEqual(allowed_models(account_model_access(
            DB({"u": {"status": "active", "model_access": result}}), "u")),
            [FLASH_MODEL, PRO_MODEL])

    def test_rate_limit_does_not_mean_free_or_premium(self):
        self.assertEqual(classify_probe_status(429), "limited")
        result = validate_key_and_models("A" * 39,
            transport=lambda url, key, payload=None:
                (200, {}) if payload is None else (429, {}))
        self.assertEqual(result["status"], "needs_attention")
        self.assertEqual(allowed_models(account_model_access(
            DB({"u": {"status": "active", "model_access": result}}), "u")), [])

    def test_invalid_key_is_rejected_before_storage(self):
        with self.assertRaises(ValueError):
            validate_key_and_models("A" * 39,
                transport=lambda url, key, payload=None: (403, {}))

    def test_legacy_key_requires_verification_before_any_model(self):
        legacy = account_model_access(DB({"u": {"status": "active"}}), "u")
        self.assertEqual(legacy["status"], "legacy_unverified")
        self.assertEqual(allowed_models(legacy), [])
        self.assertNotIn(PRO_MODEL, allowed_models(legacy))

    def test_revoked_key_cannot_unlock_any_model(self):
        revoked = account_model_access(DB({"u": {"status": "revoked",
            "model_access": {"status": "verified", "models": {
                FLASH_MODEL: "supported", PRO_MODEL: "supported"}}}}), "u")
        self.assertEqual(allowed_models(revoked), [])

    def test_network_unavailable_never_grants_pro(self):
        with self.assertRaises(ConnectionError):
            validate_key_and_models("A" * 39,
                transport=lambda url, key, payload=None: (0, {}))


if __name__ == "__main__":
    unittest.main()
