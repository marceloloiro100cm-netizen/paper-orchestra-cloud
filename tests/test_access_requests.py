"""Solicitar convite nunca concede acesso ou usa a chave do administrador."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from access import request_access, pending_access_requests, mark_request_decided, member_id


class Snap:
    def __init__(self, data):
        self.exists = data is not None
        self.data = data

    def to_dict(self):
        return self.data


class Doc:
    def __init__(self, values, key):
        self.values, self.key = values, key

    def get(self):
        return Snap(self.values.get(self.key))

    def set(self, value):
        self.values[self.key] = value

    def update(self, value):
        self.values[self.key].update(value)


class Query:
    def __init__(self, values, target):
        self.values, self.target = values, target

    def limit(self, n):
        self.n = n
        return self

    def stream(self):
        return [Snap(v) for v in self.values.values() if v.get("status") == self.target][:self.n]


class Collection:
    def __init__(self, values):
        self.values = values

    def document(self, key):
        return Doc(self.values, key)

    def where(self, field, op, target):
        assert field == "status" and op == "=="
        return Query(self.values, target)


class Db:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return Collection(self.docs.setdefault(name, {}))


class RequestAccessTests(unittest.TestCase):
    def test_first_login_creates_pending_not_invitation(self):
        db = Db()
        user = {"uid": "leonardo-uid", "email": "Leonardo@Example.ORG", "email_verified": True}
        self.assertEqual(request_access(db, user), {"status": "pending"})
        self.assertEqual(db.docs["research_access_requests"][member_id("leonardo@example.org")]["status"], "pending")
        self.assertNotIn("research_members", db.docs)
        self.assertEqual(pending_access_requests(db)[0]["email"], "leonardo@example.org")

    def test_repeat_request_does_not_reset_request_time(self):
        db = Db()
        user = {"uid": "one", "email": "one@example.org", "email_verified": True}
        request_access(db, user)
        first = db.docs["research_access_requests"][member_id(user["email"])]["requested_at"]
        request_access(db, user)
        self.assertEqual(db.docs["research_access_requests"][member_id(user["email"])]["requested_at"], first)

    def test_approved_request_no_longer_pending(self):
        db = Db()
        user = {"uid": "one", "email": "one@example.org", "email_verified": True}
        request_access(db, user)
        mark_request_decided(db, user["email"], "approved")
        self.assertEqual(pending_access_requests(db), [])
        self.assertEqual(db.docs["research_access_requests"][member_id(user["email"])]["status"], "approved")

    def test_unverified_google_user_cannot_request_access(self):
        db = Db()
        with self.assertRaises(Exception):
            request_access(db, {"email": "x@example.org", "email_verified": False})
        self.assertEqual(db.docs, {})


if __name__ == "__main__":
    unittest.main()
