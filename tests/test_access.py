"""Testes sem credenciais reais para a primeira fase de acesso multiusuário."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from access import get_access, is_admin, member_id, normalize_email, set_invitation


class FakeDoc:
    def __init__(self, documents, key):
        self.documents, self.key = documents, key

    def get(self):
        return FakeSnap(self.documents.get(self.key))

    def set(self, value):
        self.documents[self.key] = value


class FakeSnap:
    def __init__(self, data):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def document(self, key):
        return FakeDoc(self.documents, key)


class FakeDb:
    def __init__(self):
        self.documents = {}

    def collection(self, name):
        return FakeCollection(self.documents.setdefault(name, {}))


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.admins = {"admin@example.org"}

    def test_admin_also_needs_personal_key_for_ai_tokens(self):
        # Separação de custos (24/11/2026): o projeto paga só a infraestrutura.
        user = {"uid": "admin-uid", "email": "admin@example.org", "email_verified": True}
        self.assertTrue(is_admin(user, self.admins))
        self.assertEqual(get_access(self.db, user, self.admins),
                         {"allowed": True, "admin": True, "byok_ready": False})
        self.db.collection("research_credentials").document("admin-uid").set({"status": "active"})
        self.assertEqual(get_access(self.db, user, self.admins),
                         {"allowed": True, "admin": True, "byok_ready": True})

    def test_uninvited_and_unverified_denied(self):
        user = {"email": "guest@example.org", "email_verified": True}
        self.assertFalse(get_access(self.db, user, self.admins)["allowed"])
        set_invitation(self.db, "guest@example.org", True, "admin-uid", self.admins)
        user["email_verified"] = False
        self.assertFalse(get_access(self.db, user, self.admins)["allowed"])

    def test_invite_normalizes_email_but_never_enables_shared_ai(self):
        invitation = set_invitation(self.db, " Guest@Example.Org ", True, "admin-uid", self.admins)
        self.assertEqual(invitation["email"], "guest@example.org")
        access = get_access(self.db, {"email": "guest@example.org",
                                     "email_verified": True}, self.admins)
        self.assertTrue(access["allowed"])
        self.assertFalse(access["admin"])
        self.assertFalse(access["byok_ready"])

    def test_revocation(self):
        set_invitation(self.db, "guest@example.org", True, "admin-uid", self.admins)
        set_invitation(self.db, "guest@example.org", False, "admin-uid", self.admins)
        self.assertFalse(get_access(self.db, {"email": "guest@example.org",
                          "email_verified": True}, self.admins)["allowed"])

    def test_invitation_id_is_not_raw_email(self):
        self.assertEqual(member_id("  GUEST@example.org"), member_id("guest@example.org"))
        self.assertNotIn("@", member_id("guest@example.org"))

    def test_cannot_override_admin(self):
        with self.assertRaises(Exception):
            set_invitation(self.db, "admin@example.org", False, "admin-uid", self.admins)

    def test_individual_credential_status(self):
        from credentials import credential_state
        guest = {"uid": "researcher-123", "email": "guest@example.org",
                 "email_verified": True}
        set_invitation(self.db, guest["email"], True, "admin-uid", self.admins)
        self.assertFalse(get_access(self.db, guest, self.admins)["byok_ready"])
        self.db.collection("research_credentials").document(guest["uid"]).set({
            "status": "active", "secret_resource": "projects/p/secrets/scriptorium-byok-researcher-123"
        })
        self.assertTrue(credential_state(self.db, guest["uid"]))
        self.assertTrue(get_access(self.db, guest, self.admins)["byok_ready"])
        self.db.collection("research_credentials").document(guest["uid"]).set({"status": "revoked"})
        self.assertFalse(get_access(self.db, guest, self.admins)["byok_ready"])

    def test_invalid_email(self):
        with self.assertRaises(ValueError):
            normalize_email("invalid")


if __name__ == "__main__":
    unittest.main()
