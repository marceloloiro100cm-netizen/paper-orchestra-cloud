"""Testes do cofre: armazenamento, rotação, revogação e isolamento de metadados."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from credentials import credential_state, secret_id, store_credential, delete_credential


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return self.value


class Doc:
    def __init__(self, database, identifier):
        self.db, self.identifier = database, identifier

    def get(self):
        return Snapshot(self.db.get(self.identifier))

    def set(self, data):
        self.db[self.identifier] = data


class Collection:
    def __init__(self, storage):
        self.storage = storage

    def document(self, name):
        return Doc(self.storage, name)


class DB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return Collection(self.collections.setdefault(name, {}))


class Manager:
    def __init__(self):
        self.created = []
        self.versions = []
        self.deleted = []

    def create_secret(self, *, request):
        self.created.append(request["secret_id"])

    def add_secret_version(self, *, request):
        self.versions.append(request)

    def delete_secret(self, *, request):
        self.deleted.append(request["name"])


class CredentialTests(unittest.TestCase):
    def test_store_and_rotate_without_firestore_secret_values(self):
        db, manager = DB(), Manager()
        secret_a = "Z" * 39
        secret_b = "Y" * 39
        a = store_credential(db, "safeproject", "user_a", secret_a, client=manager)
        b = store_credential(db, "safeproject", "user_b", secret_b, client=manager)
        self.assertTrue(a["configured"])
        self.assertTrue(b["configured"])
        self.assertTrue(credential_state(db, "user_a"))
        self.assertTrue(credential_state(db, "user_b"))
        self.assertNotIn(secret_a, str(db.collections))
        self.assertNotIn(secret_b, str(db.collections))
        self.assertEqual(manager.created, [secret_id("user_a"), secret_id("user_b")])
        self.assertIn("/scriptorium-byok-user_a", manager.versions[0]["parent"])
        self.assertIn("/scriptorium-byok-user_b", manager.versions[1]["parent"])

    def test_revocation_disables_credential_and_deletes_secret(self):
        db, manager = DB(), Manager()
        store_credential(db, "safeproject", "guest", "A" * 39, client=manager)
        result = delete_credential(db, "safeproject", "guest", client=manager)
        self.assertFalse(result["configured"])
        self.assertFalse(credential_state(db, "guest"))
        self.assertEqual(manager.deleted, ["projects/safeproject/secrets/scriptorium-byok-guest"])

    def test_bad_uid_rejected(self):
        with self.assertRaises(ValueError):
            secret_id("../unsafe")


if __name__ == "__main__":
    unittest.main()
