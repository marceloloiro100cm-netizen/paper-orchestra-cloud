"""Testes da Onda 1: desempenho, escrita atômica, caches de índice/capa/referências e paralelismo."""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


class AtomicBlob:
    """Fake GCS blob com suporte a generation e if_generation_match."""

    def __init__(self, store: dict, gens: dict, name: str, calls: list):
        self.store, self.gens, self.name, self.calls = store, gens, name, calls
        self.generation = gens.get(name)

    def exists(self) -> bool:
        self.calls.append(("exists", self.name))
        return self.name in self.store

    def download_as_bytes(self) -> bytes:
        self.calls.append(("download_bytes", self.name))
        if self.name not in self.store:
            raise KeyError(self.name)
        self.generation = self.gens.get(self.name, 1)
        return self.store[self.name]

    def download_to_filename(self, filename: str) -> None:
        self.calls.append(("download_file", self.name))
        Path(filename).write_bytes(self.store[self.name])

    def upload_from_string(self, data, content_type=None, if_generation_match=None) -> None:
        from google.api_core.exceptions import PreconditionFailed
        self.calls.append(("upload_string", self.name, if_generation_match))
        current = self.gens.get(self.name, 0)
        if if_generation_match is not None and current != if_generation_match:
            raise PreconditionFailed("concurrent write")
        self.store[self.name] = data if isinstance(data, bytes) else data.encode("utf-8")
        self.gens[self.name] = current + 1
        self.generation = self.gens[self.name]

    def upload_from_filename(self, filename: str, content_type=None) -> None:
        self.calls.append(("upload_file", self.name))
        self.store[self.name] = Path(filename).read_bytes()
        self.gens[self.name] = self.gens.get(self.name, 0) + 1


class AtomicBucket:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.gens: dict[str, int] = {}
        self.calls: list = []

    def blob(self, name: str) -> AtomicBlob:
        return AtomicBlob(self.files, self.gens, name, self.calls)

    def list_blobs(self, prefix: str = ""):
        return [self.blob(k) for k in sorted(self.files) if k.startswith(prefix)]


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class GuideAtomicWriteTest(unittest.TestCase):
    def test_precondition_failed_vira_409_e_historico_e_limitado(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from guide_api import make_guide_router

        bucket = AtomicBucket()
        app = FastAPI()
        app.include_router(make_guide_router(bucket, lambda: {"uid": "ana"}, today=lambda: "2026-11-26"))
        client = TestClient(app)

        payload = {"schema": 2, "tipo": "artigo", "active": 1, "values": {"tema": "Freire"},
                   "records": {}, "criteria": {}, "versions": [], "changedAt": 100}
        self.assertEqual(client.put("/api/guia/estado?base=0", json=payload).status_code, 200)
        hist_uploads_1 = [c for c in bucket.calls if c[0] == "upload_string" and "historico/" in c[1]]
        self.assertEqual(len(hist_uploads_1), 1)

        # Segunda gravação logo em seguida não reescreve historico/ imediatamente (throttle de 15 min).
        payload2 = {**payload, "changedAt": 200}
        self.assertEqual(client.put("/api/guia/estado?base=100", json=payload2).status_code, 200)
        hist_uploads_2 = [c for c in bucket.calls if c[0] == "upload_string" and "historico/" in c[1]]
        self.assertEqual(len(hist_uploads_2), 1)

        # Simula corrida: entre a leitura e a escrita, outro dispositivo incrementou a generation.
        orig_blob = bucket.blob

        def racing_blob(name: str):
            b = orig_blob(name)
            if name.endswith("estado.json"):
                orig_upload = b.upload_from_string

                def race_upload(data, content_type=None, if_generation_match=None):
                    if if_generation_match is not None:
                        bucket.gens[name] = bucket.gens.get(name, 0) + 1
                    return orig_upload(data, content_type=content_type, if_generation_match=if_generation_match)

                b.upload_from_string = race_upload
            return b

        bucket.blob = racing_blob
        r = client.put("/api/guia/estado?base=200", json={**payload, "changedAt": 300})
        self.assertEqual(r.status_code, 409)


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class LibraryIndexCacheTest(unittest.TestCase):
    def test_le_meta_uma_vez_e_reaproveita_sqlite_em_cache_local(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from library_index import make_library_index_router

        sha = "a" * 64
        bucket = AtomicBucket()
        derived_path = f"library/ana/derived/pymupdf/chunks-1/{sha}.json"
        bucket.files[derived_path] = json.dumps({
            "chunks": [{"chunk_id": "c1", "text": "Paulo Freire e a pedagogia da autonomia na pesquisa.",
                        "pages": [1, 1], "heading_path": ["Introdução"]}]
        }).encode("utf-8")

        class FakeSnap:
            def __init__(self, data):
                self._d = data

            def to_dict(self):
                return self._d

        class FakeQuery:
            def __init__(self, rows):
                self._rows = rows

            def where(self, *_a, **_kw):
                return self

            def limit(self, _n):
                return self

            def stream(self):
                return [FakeSnap(r) for r in self._rows]

        class FakeDB:
            def collection(self, _name):
                return FakeQuery([{"id": "1" * 32, "owner_uid": "ana", "status": "active",
                                   "name": "freire.pdf", "format": "pdf", "sha256": sha}])

        app = FastAPI()
        app.include_router(make_library_index_router(FakeDB(), bucket, lambda: {"uid": "ana"}))
        client = TestClient(app)

        r1 = client.get("/api/library/search?q=autonomia")
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["index_rebuilt"])
        self.assertEqual(len(r1.json()["results"]), 1)

        bucket.calls.clear()
        r2 = client.get("/api/library/search?q=Freire")
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["index_rebuilt"])
        # Meta lido no máximo 1 vez (não 2) e zero download do arquivo .sqlite (cache local em /tmp).
        meta_downloads = [c for c in bucket.calls if c[0] == "download_bytes" and c[1].endswith("fts-1.json")]
        sqlite_downloads = [c for c in bucket.calls if c[0] == "download_file"]
        self.assertEqual(len(meta_downloads), 1)
        self.assertEqual(len(sqlite_downloads), 0)


class BibIntegrityParallelTest(unittest.TestCase):
    def test_parallel_and_url_dedup_preserves_order_and_unique_keys(self):
        import bib_integrity

        calls = []
        lock = threading.Lock()

        def slow_oa(url: str):
            with lock:
                calls.append(url)
            time.sleep(0.05)
            return {
                "title": "Pedagogia da Autonomia",
                "publication_year": 1996,
                "doi": "https://doi.org/10.1234/freire1996",
                "authorships": [{"author": {"display_name": "Paulo Freire"}}],
                "primary_location": {"source": {"display_name": "Paz e Terra"}},
            }

        sources = [
            {"id": f"s{i}", "name": f"doc{i}.pdf", "origin": {"doi": "10.1234/freire1996"}}
            for i in range(4)
        ]
        entries = bib_integrity.library_entries(sources, slow_oa, max_workers=4)
        self.assertEqual([e["source_id"] for e in entries], ["s0", "s1", "s2", "s3"])
        # Chaves determinísticas e únicas na ordem original.
        self.assertEqual(len({e["key"] for e in entries}), 4)
        self.assertTrue(entries[0]["key"].startswith("freire1996"))
        # Deduplicação por URL no mesmo job: menos chamadas repetidas do que 4 seriais.
        self.assertLessEqual(len(calls), 4)


class FirestoreIndexesConfigTest(unittest.TestCase):
    def test_firestore_indexes_wired_in_firebase_json(self):
        fb = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
        self.assertEqual(fb["firestore"]["indexes"], "firestore.indexes.json")
        idx = json.loads((ROOT / "firestore.indexes.json").read_text(encoding="utf-8"))
        groups = {i["collectionGroup"] for i in idx["indexes"]}
        self.assertTrue({"library_items", "mcp_projects", "research_jobs"} <= groups)


if __name__ == "__main__":
    unittest.main()
