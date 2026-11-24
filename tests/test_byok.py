"""Isolamento BYOK: testes que não acessam a nuvem."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from byok import personal_agent_environment


class Snapshot:
    def __init__(self, record):
        self.record = record
        self.exists = record is not None

    def to_dict(self):
        return self.record


class Doc:
    def __init__(self, record):
        self.record = record

    def get(self):
        return Snapshot(self.record)


class DB:
    def __init__(self, uid="guest-1", enabled=True):
        self.uid = uid
        self.enabled = enabled

    def collection(self, name):
        assert name == "research_credentials"
        return self

    def document(self, uid):
        record = {"status": "active" if self.enabled else "revoked",
                  "secret_resource": "projects/myproject/secrets/scriptorium-byok-" + uid}
        return Doc(record)


class Manager:
    def __init__(self, key):
        self.key = key
        self.requests = []

    def access_secret_version(self, *, request):
        self.requests.append(request["name"])
        return SimpleNamespace(payload=SimpleNamespace(data=self.key.encode()))


class BYOKTests(unittest.TestCase):
    def test_removes_inherited_owner_credentials(self):
        original = {"GOOGLE_CLOUD_PROJECT": "owner-project",
                    "VERTEX_AI_PROJECT": "owner-project",
                    "GOOGLE_GENAI_USE_VERTEXAI": "true",
                    "GEMINI_API_KEY": "CENTRAL_SECRET",
                    "GOOGLE_API_KEY": "CENTRAL_SECRET",
                    "OTHER": "kept"}
        manager = Manager("A" * 39)
        result = personal_agent_environment(original, DB(), "myproject",
                                            "guest-1", manager=manager)
        self.assertEqual(result["GEMINI_API_KEY"], "A" * 39)
        self.assertEqual(result["GOOGLE_API_KEY"], "A" * 39)
        self.assertEqual(result["GOOGLE_GENAI_USE_VERTEXAI"], "false")
        self.assertNotIn("GOOGLE_CLOUD_PROJECT", result)
        self.assertEqual(result["VERTEX_AI_PROJECT"], "")
        self.assertEqual(result["VERTEX_AI_LOCATION"], "")
        self.assertEqual(original["GEMINI_API_KEY"], "CENTRAL_SECRET")
        self.assertEqual(manager.requests, [
            "projects/myproject/secrets/scriptorium-byok-guest-1/versions/latest"
        ])

    def test_revoked_blocks_before_secret_read(self):
        manager = Manager("A" * 39)
        with self.assertRaises(RuntimeError):
            personal_agent_environment({}, DB(enabled=False), "myproject",
                                       "guest-1", manager=manager)
        self.assertEqual(manager.requests, [])

    def test_invalid_uid_blocks(self):
        with self.assertRaises(RuntimeError):
            personal_agent_environment({}, DB(), "myproject",
                                       "../other", manager=Manager("A" * 39))

    def test_new_aq_key_format_accepted(self):
        key = "AQ." + "a" * 44
        result = personal_agent_environment({}, DB(), "myproject", "guest-1",
                                            manager=Manager(key))
        self.assertEqual(result["GEMINI_API_KEY"], key)

    def test_invalid_key_blocks(self):
        with self.assertRaises(RuntimeError):
            personal_agent_environment({}, DB(), "myproject",
                                       "guest-1", manager=Manager("not valid"))


if __name__ == "__main__":
    unittest.main()
