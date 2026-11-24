"""Pedidos de acesso nunca liberam o uso até um admin aprovar."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from access import get_access, member_id
from access_requests import request_access, pending_access_requests, approve_access_request


class Snap:
    def __init__(self, doc_id, data):
        self.id, self.data = doc_id, data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class Doc:
    def __init__(self, collection, doc_id):
        self.collection, self.doc_id = collection, doc_id

    def get(self):
        return Snap(self.doc_id, self.collection.get(self.doc_id))

    def set(self, data):
        self.collection[self.doc_id] = data

    def update(self, data):
        self.collection[self.doc_id].update(data)


class Collection:
    def __init__(self, docs):
        self.docs = docs
        self.condition = None

    def document(self, doc_id):
        return Doc(self.docs, doc_id)

    def where(self, field, op, value):
        self.condition = (field, op, value)
        return self

    def limit(self, _n):
        return self

    def stream(self):
        result = []
        for key, val in self.docs.items():
            if not self.condition or val.get(self.condition[0]) == self.condition[2]:
                result.append(Snap(key, val))
        return result


class DB:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return Collection(self.data.setdefault(name, {}))


class AccessRequestTests(unittest.TestCase):
    def setUp(self):
        self.db = DB()
        self.guest = {"email": "leonardo@example.edu", "email_verified": True,
                      "uid": "leonardo-uid"}
        self.admins = {"admin@example.edu"}

    def test_request_does_not_grant_account_access(self):
        request_access(self.db, self.guest)
        self.assertFalse(get_access(self.db, self.guest, self.admins)["allowed"])
        pending = pending_access_requests(self.db)["items"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["email"], "leonardo@example.edu")

    def test_approval_only_enables_invitation_not_shared_ai(self):
        request_access(self.db, self.guest)
        response = approve_access_request(
            self.db, member_id(self.guest["email"]), "admin-uid", self.admins)
        self.assertEqual(response["status"], "active")
        self.assertTrue(get_access(self.db, self.guest, self.admins)["allowed"])
        self.assertFalse(get_access(self.db, self.guest, self.admins)["byok_ready"])
        self.assertEqual(pending_access_requests(self.db)["items"], [])

    def test_idempotent_pending_request(self):
        request_access(self.db, self.guest)
        request_access(self.db, self.guest)
        self.assertEqual(len(pending_access_requests(self.db)["items"]), 1)

    def test_unverified_google_email_cannot_request(self):
        self.guest["email_verified"] = False
        with self.assertRaises(Exception):
            request_access(self.db, self.guest)
        self.assertEqual(pending_access_requests(self.db)["items"], [])

    def test_bad_request_id_is_rejected(self):
        with self.assertRaises(Exception):
            approve_access_request(self.db, "../guest", "admin-uid", self.admins)

    def test_nonmatching_request_id_is_rejected(self):
        request_access(self.db, self.guest)
        fake = member_id("other@example.edu")
        self.db.collection("research_access_requests").document(fake).set({
            "email": self.guest["email"], "status": "pending",
        })
        with self.assertRaises(Exception):
            approve_access_request(self.db, fake, "admin-uid", self.admins)


if __name__ == "__main__":
    unittest.main()
