"""Testes sem rede para permissão de modelos por chave Gemini."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from model_access import SUPPORTED_MODELS, verify_key_models, get_model_capabilities


class Snap:
    def __init__(self, d):
        self.exists = d is not None
        self.value = d

    def to_dict(self):
        return self.value


class Db:
    def __init__(self, values):
        self.values = values

    def collection(self, name):
        assert name == "research_credentials"
        return self

    def document(self, uid):
        self.uid = uid
        return self

    def get(self):
        return Snap(self.values.get(self.uid))


def fake_transport(model_codes=(200, 403), list_code=200):
    calls = []

    def call(method, path, key, payload):
        assert key == "S" * 39
        calls.append((method, path))
        if method == "GET":
            if list_code != 200:
                return list_code, {}
            return 200, {"models": [
                {"name": "models/" + m, "supportedGenerationMethods": ["generateContent"]}
                for m in SUPPORTED_MODELS
            ]}
        index = 0 if SUPPORTED_MODELS[0] in path else 1
        return model_codes[index], {}
    return call, calls


class ModelAccessTests(unittest.TestCase):
    def test_flash_only_never_unlocks_pro(self):
        transport, calls = fake_transport((200, 403))
        checks = verify_key_models("S" * 39, transport=transport)
        self.assertEqual(checks["allowed_models"], ["gemini-3-flash-preview"])
        self.assertEqual(checks["model_status"]["gemini-3.1-pro-preview"], "not_authorized")
        self.assertEqual(sum(c[0] == "POST" for c in calls), 2)

    def test_pro_is_only_enabled_by_successful_generation(self):
        transport, _ = fake_transport((200, 200))
        checks = verify_key_models("S" * 39, transport=transport)
        self.assertEqual(set(checks["allowed_models"]), set(SUPPORTED_MODELS))

    def test_429_does_not_claim_free_or_cancel_existing_entitlement(self):
        transport, _ = fake_transport((200, 429))
        checks = verify_key_models("S" * 39, transport=transport)
        self.assertEqual(checks["allowed_models"], [SUPPORTED_MODELS[0]])
        self.assertEqual(checks["model_status"][SUPPORTED_MODELS[1]], "quota_limited")

    def test_bad_key_fails_without_generation_attempts(self):
        transport, calls = fake_transport(list_code=403)
        checks = verify_key_models("S" * 39, transport=transport)
        self.assertEqual(checks["status"], "invalid_key")
        self.assertEqual(checks["allowed_models"], [])
        self.assertFalse(any(method == "POST" for method, _ in calls))

    def test_old_key_metadata_is_not_granted_models(self):
        db = Db({"one": {"status": "active"}, "two": {"status": "active", "model_access": {
            "allowed_models": [SUPPORTED_MODELS[1]], "status": "verified"
        }}})
        self.assertEqual(get_model_capabilities(db, "one")["allowed_models"], [])
        self.assertEqual(get_model_capabilities(db, "two")["allowed_models"], [SUPPORTED_MODELS[1]])
        self.assertEqual(get_model_capabilities(db, "unknown")["allowed_models"], [])

    def test_revoked_user_does_not_keep_stale_entitlements(self):
        db = Db({"guest": {"status": "revoked", "model_access": {
            "allowed_models": list(SUPPORTED_MODELS), "status": "verified"
        }}})
        self.assertEqual(get_model_capabilities(db, "guest")["allowed_models"], [])


if __name__ == "__main__":
    unittest.main()
