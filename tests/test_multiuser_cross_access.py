"""Homologação offline de duas contas sem acessar dados reais de pesquisadores.

Cobre pedido -> aprovação -> credencial própria, biblioteca e worker BYOK.
O teste real de Leonardo no Firebase/Cloud Run continua sendo necessário.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "api"))
sys.path.insert(0, str(root / "worker"))

from fastapi import HTTPException
from access import get_access, member_id
from access_requests import request_access, approve_access_request
from library import make_library_router
from model_access import FLASH_MODEL, PRO_MODEL, account_model_access, allowed_models
from byok import personal_agent_environment


class Snap:
    def __init__(self, name, value):
        self.id = name
        self.exists = value is not None
        self.value = value

    def to_dict(self):
        return self.value


class Document:
    def __init__(self, docs, key):
        self.docs, self.key = docs, key

    def get(self):
        return Snap(self.key, self.docs.get(self.key))

    def set(self, value):
        self.docs[self.key] = value

    def update(self, value):
        self.docs[self.key].update(value)


class Query:
    def __init__(self, docs, cond=None):
        self.docs, self.cond = docs, cond
        self.max_items = None

    def where(self, field, operator, value):
        assert operator == "=="
        return Query(self.docs, (field, value))

    def limit(self, count):
        self.max_items = count
        return self

    def stream(self):
        result = [Snap(key, v) for key, v in self.docs.items()
                  if not self.cond or v.get(self.cond[0]) == self.cond[1]]
        return result[:self.max_items] if self.max_items else result


class DB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return QueryWithDocument(self.collections.setdefault(name, {}))


class QueryWithDocument(Query):
    def document(self, key):
        return Document(self.docs, key)


class Bucket:
    def __init__(self):
        self.reads = []
        self.data = {}

    def blob(self, path):
        self.reads.append(path)
        return Blob(self.data.get(path))


class Blob:
    def __init__(self, value):
        self.value = value

    def exists(self):
        return self.value is not None

    def download_as_bytes(self):
        return self.value


class Manager:
    def __init__(self):
        self.requests = []

    def access_secret_version(self, *, request):
        path = request["name"]
        self.requests.append(path)
        uid = path.split("scriptorium-byok-", 1)[1].split("/", 1)[0]
        return SimpleNamespace(payload=SimpleNamespace(data=(uid[0].upper() * 39).encode()))


class TwoUserIsolationTests(unittest.TestCase):
    def setUp(self):
        self.db = DB()
        self.admins = {"admin@example.edu"}
        self.a = {"email": "a@example.edu", "email_verified": True, "uid": "a_uid"}
        self.b = {"email": "b@example.edu", "email_verified": True, "uid": "b_uid"}

    def test_access_request_is_not_approval(self):
        request_access(self.db, self.a)
        self.assertFalse(get_access(self.db, self.a, self.admins)["allowed"])
        approve_access_request(self.db, member_id(self.a["email"]), "admin_uid", self.admins)
        self.assertTrue(get_access(self.db, self.a, self.admins)["allowed"])
        self.assertFalse(get_access(self.db, self.a, self.admins)["byok_ready"])
        self.assertFalse(get_access(self.db, self.b, self.admins)["allowed"])

    def test_second_user_cannot_download_or_archive_first_users_library(self):
        item_id = "a" * 32
        path = "library/a_uid/" + item_id + "/original.pdf"
        self.db.collection("library_items").document(item_id).set({
            "id": item_id, "owner_uid": self.a["uid"], "object_path": path,
            "status": "active", "name": "Fonte.pdf", "format": "pdf",
        })
        bucket = Bucket()
        bucket.data[path] = b"%PDF-synthetic"
        router = make_library_router(self.db, bucket, lambda: None)
        download = next(r.endpoint for r in router.routes
                        if r.path.endswith("/items/{item_id}/download"))
        archive = next(r.endpoint for r in router.routes
                       if r.path.endswith("/items/{item_id}/archive"))
        with self.assertRaises(HTTPException) as ctx:
            download(item_id=item_id, user=self.b)
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            archive(item_id=item_id, user=self.b)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(bucket.reads, [])
        self.assertEqual(download(item_id=item_id, user=self.a).body, b"%PDF-synthetic")

    def test_model_access_and_secrets_are_per_uid_and_no_admin_fallback(self):
        for user in (self.a, self.b):
            self.db.collection("research_credentials").document(user["uid"]).set({
                "status": "active",
                "secret_resource": "projects/test/secrets/scriptorium-byok-" + user["uid"],
                "model_access": {"status": "verified", "models": {
                    FLASH_MODEL: "supported",
                    PRO_MODEL: "supported" if user == self.a else "unavailable",
                }},
            })
        self.assertEqual(allowed_models(account_model_access(self.db, self.a["uid"])),
                         [FLASH_MODEL, PRO_MODEL])
        self.assertEqual(allowed_models(account_model_access(self.db, self.b["uid"])),
                         [FLASH_MODEL])
        manager = Manager()
        admin_environment = {
            "GOOGLE_API_KEY": "OWNER_PRIVATE_KEY",
            "GEMINI_API_KEY": "OWNER_PRIVATE_KEY",
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_CLOUD_PROJECT": "owner-project",
        }
        a_env = personal_agent_environment(admin_environment, self.db, "test", self.a["uid"], manager=manager)
        b_env = personal_agent_environment(admin_environment, self.db, "test", self.b["uid"], manager=manager)
        self.assertEqual(a_env["GOOGLE_API_KEY"], "A" * 39)
        self.assertEqual(b_env["GOOGLE_API_KEY"], "B" * 39)
        self.assertEqual(a_env["GOOGLE_GENAI_USE_VERTEXAI"], "false")
        self.assertEqual(b_env["GOOGLE_GENAI_USE_VERTEXAI"], "false")
        self.assertNotIn("GOOGLE_CLOUD_PROJECT", a_env)
        self.assertNotIn("GOOGLE_CLOUD_PROJECT", b_env)
        self.assertEqual(admin_environment["GEMINI_API_KEY"], "OWNER_PRIVATE_KEY")
        self.assertIn("scriptorium-byok-a_uid", manager.requests[0])
        self.assertIn("scriptorium-byok-b_uid", manager.requests[1])


if __name__ == "__main__":
    unittest.main()
