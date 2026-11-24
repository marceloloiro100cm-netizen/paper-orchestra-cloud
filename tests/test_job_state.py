"""Trava de uma pesquisa ativa por conta e reconciliação de Jobs interrompidos."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from job_state import (STALE_AFTER, claim_in_transaction, is_stale, reconcile)

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)


class Snap:
    def __init__(self, data):
        self.data, self.exists = data, data is not None

    def to_dict(self):
        return None if self.data is None else dict(self.data)


class Ref:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def get(self, transaction=None):
        return Snap(self.store.get(self.path))

    def update(self, fields):
        self.store[self.path] = {**self.store[self.path], **fields}


class Collection:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def document(self, key):
        return Ref(self.store, (self.name, key))


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Collection(self.store, name)


class Transaction:
    def set(self, ref, value):
        ref.store[ref.path] = dict(value)

    def update(self, ref, fields):
        ref.update(fields)


def job(status, minutes_ago, field="created_at"):
    return {"status": status, field: (NOW - timedelta(minutes=minutes_ago)).isoformat()}


class StaleTest(unittest.TestCase):
    def test_recent_running_is_not_stale(self):
        self.assertFalse(is_stale(job("running", 30), NOW))

    def test_old_running_is_stale(self):
        minutes = STALE_AFTER.total_seconds() / 60 + 1
        self.assertTrue(is_stale(job("running", minutes), NOW))
        self.assertTrue(is_stale(job("queued", minutes), NOW))

    def test_started_at_has_priority(self):
        record = {**job("running", 500), **job("running", 10, "started_at")}
        self.assertFalse(is_stale(record, NOW))

    def test_finished_or_undated_is_never_stale(self):
        self.assertFalse(is_stale(job("completed", 10_000), NOW))
        self.assertFalse(is_stale({"status": "running", "created_at": ""}, NOW))
        self.assertFalse(is_stale({"status": "running", "created_at": "lixo"}, NOW))

    def test_reconcile_marks_failed_in_store(self):
        db = DB()
        ref = db.collection("research_jobs").document("a")
        db.store[ref.path] = job("running", 1_000)
        result = reconcile(ref, db.store[ref.path], NOW)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(db.store[ref.path]["status"], "failed")
        self.assertTrue(result["error"])


class ClaimTest(unittest.TestCase):
    def setUp(self):
        self.db, self.tx = DB(), Transaction()

    def claim(self, job_id):
        return claim_in_transaction(self.tx, self.db, "uid1", job_id,
                                    {**job("queued", 0), "id": job_id}, NOW)

    def test_first_claim_creates_job_and_lock(self):
        self.assertTrue(self.claim("j1"))
        self.assertEqual(self.db.store[("research_owner_state", "uid1")]["active_job_id"], "j1")
        self.assertIn(("research_jobs", "j1"), self.db.store)

    def test_second_claim_blocked_while_active(self):
        self.assertTrue(self.claim("j1"))
        self.assertFalse(self.claim("j2"))
        self.assertNotIn(("research_jobs", "j2"), self.db.store)

    def test_claim_allowed_after_finish(self):
        self.claim("j1")
        self.db.store[("research_jobs", "j1")]["status"] = "completed"
        self.assertTrue(self.claim("j2"))

    def test_stale_active_job_is_failed_and_released(self):
        self.claim("j1")
        self.db.store[("research_jobs", "j1")].update(job("running", 1_000))
        self.assertTrue(self.claim("j2"))
        self.assertEqual(self.db.store[("research_jobs", "j1")]["status"], "failed")

    def test_lock_pointing_to_missing_job_is_released(self):
        self.db.store[("research_owner_state", "uid1")] = {"active_job_id": "sumiu"}
        self.assertTrue(self.claim("j2"))


if __name__ == "__main__":
    unittest.main()
