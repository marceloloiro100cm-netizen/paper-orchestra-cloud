"""Teste de busca no corpus de referência (gate G2, M04). Sem rede e sem modelo."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "tests"))
from fastapi import HTTPException  # noqa: E402

import retrieval_eval as re_eval  # noqa: E402
import retrieval_eval_api  # noqa: E402
from test_biblioteca_exportacao import DB, Bucket, endpoint  # noqa: E402


class FakeEmbedder:
    """Vetores determinísticos por palavras (sacola de palavras com hash)."""
    def __init__(self):
        self.calls = []

    def embed(self, texts, task_type):
        self.calls.append((task_type, len(texts)))
        out = np.zeros((len(texts), 32), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % 32] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return out / norms

    def info(self):
        return {"model": "fake", "usage": {}}


class CorpusCopyTest(unittest.TestCase):
    def test_worker_copy_matches_docs(self):
        for name in ("selecao.json", "consultas.jsonl"):
            self.assertEqual((ROOT / "worker" / "corpus_ref" / name).read_bytes(),
                             (ROOT / "docs" / "corpus" / name).read_bytes(),
                             f"Copie docs/corpus/{name} para worker/corpus_ref/")

    def test_dockerfile_copies_corpus(self):
        self.assertIn("COPY corpus_ref/ /app/corpus_ref/", (ROOT / "worker" / "Dockerfile").read_text())


class FetchTest(unittest.TestCase):
    def test_sha_failures_and_invalid_records(self):
        good = b"%PDF-1.7 bom"
        selection = {"documentos": [
            {"file": "a.pdf", "pdf_url": "https://x/a.pdf", "sha256": hashlib.sha256(good).hexdigest()},
            {"file": "b.pdf", "pdf_url": "https://x/b.pdf", "sha256": "0" * 64},
            {"file": "c.pdf", "pdf_url": "https://x/c.pdf", "sha256": "0" * 64},
            {"file": "d.pdf", "pdf_url": "https://x/d.pdf", "sha256": "0" * 64},
            {"file": "../e.pdf", "pdf_url": "https://x/e.pdf", "sha256": "0" * 64},
            {"file": "f.pdf", "pdf_url": "http://x/f.pdf", "sha256": "0" * 64},
        ]}

        def http_get(url):
            if url.endswith("c.pdf"):
                raise TimeoutError()
            if url.endswith("d.pdf"):
                return b"<html>"
            return good

        with tempfile.TemporaryDirectory() as tmp:
            report = re_eval.fetch_reference_corpus(selection, Path(tmp), http_get)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["a.pdf", "b.pdf"])
        self.assertEqual(report["downloaded"], ["a.pdf", "b.pdf"])
        self.assertEqual(report["sha_mismatch"], ["b.pdf"])
        self.assertEqual({f["file"] for f in report["failed"]}, {"c.pdf", "d.pdf", "../e.pdf", "f.pdf"})


class ReferenceEvalTest(unittest.TestCase):
    def test_lexical_vector_hybrid_and_summary(self):
        docs = {
            "T1_a.txt": "A pesquisa como princípio pedagógico orienta a iniciação científica no ensino médio integrado.",
            "T6_b.txt": "Artificial intelligence literacy helps students question generative tools critically.",
            "T3_c.txt": "Letramento científico envolve argumentação a partir de evidências em sala de aula.",
        }
        queries = [
            {"id": "q01", "query": "pesquisa como princípio pedagógico", "relevant": [{"file": "T1_a.txt"}]},
            {"id": "q02", "query": "argumentação com evidências", "relevant": [
                {"file": "T3_c.txt", "contains": "frase que não existe"}, {"file": "faltando.pdf"}]},
            {"id": "q36", "query": "artificial intelligence literacy", "relevant": [{"file": "T6_b.txt"}]},
            {"id": "n01", "query": "turbinas eólicas", "relevant": [], "negative": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in docs.items():
                (Path(tmp) / name).write_text(text, encoding="utf-8")
            embedder = FakeEmbedder()
            report = re_eval.reference_eval(Path(tmp), queries, embedder)
        self.assertEqual(report["queries"], 3)  # a negativa sai da conta
        self.assertEqual(report["labels"]["files_missing_from_corpus"], ["faltando.pdf"])
        self.assertEqual(report["labels"]["contains_fallback_to_file"], [{"q": "q02", "file": "T3_c.txt"}])
        self.assertEqual(set(report["strategies"]), {"lexical", "vector", "hybrid"})
        self.assertEqual(report["strategies"]["lexical"]["recall@10"], 1.0)
        self.assertIn("tematicas", report["strategies"]["hybrid"]["groups"])
        self.assertEqual([c[0] for c in embedder.calls], ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"])
        small = re_eval.summary(report)
        self.assertEqual(small["queries"], 3)
        self.assertIn("especificas_recall@10", small["hybrid"])
        self.assertNotIn("per_query", json.dumps(small))
        # O relatório guarda métricas e identificadores, nunca o texto dos documentos.
        self.assertNotIn("princípio pedagógico orienta", json.dumps(report, ensure_ascii=False))


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket, self.started = DB(), Bucket(), []
        self.admin, self.ready = True, True
        self.router = retrieval_eval_api.make_retrieval_eval_router(
            self.db, self.bucket, lambda: None, lambda user: self.admin, lambda user: self.ready,
            lambda *a: self.started.append(a))
        self.post = endpoint(self.router, "/retrieval-eval", "POST")
        self.get = endpoint(self.router, "/retrieval-eval", "GET")
        self.download = endpoint(self.router, "/download")

    def test_admin_with_key_starts_once(self):
        self.assertIsNone(self.get(user={"uid": "u1"})["last"])
        result = self.post(user={"uid": "u1"})
        job = self.db.store[("research_jobs", result["job_id"])]
        self.assertEqual((job["mode"], job["ai_auth_mode"]), ("retrieval_eval", "user_gemini"))
        self.assertEqual(self.started, [(result["job_id"], "u1", "retrieval_eval")])
        self.assertEqual(self.get(user={"uid": "u1"})["last"]["status"], "queued")
        with self.assertRaises(HTTPException) as ctx:
            self.post(user={"uid": "u1"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_requires_admin_and_key(self):
        self.ready = False
        with self.assertRaises(HTTPException) as ctx:
            self.post(user={"uid": "u1"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.admin = False
        for call in (lambda: self.post(user={"uid": "u1"}), lambda: self.get(user={"uid": "u1"})):
            with self.assertRaises(HTTPException) as ctx:
                call()
            self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.started, [])

    def test_download_only_owner_and_completed(self):
        job_id = self.post(user={"uid": "u1"})["job_id"]
        with self.assertRaises(HTTPException) as ctx:
            self.download(job_id=job_id, user={"uid": "u1"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.db.store[("research_jobs", job_id)]["status"] = "completed"
        self.bucket.objects[f"research/u1/{job_id}/output/retrieval_eval.json"] = b'{"queries": 42}'
        response = self.download(job_id=job_id, user={"uid": "u1"})
        self.assertEqual(json.loads(response.body)["queries"], 42)
        with self.assertRaises(HTTPException):
            self.download(job_id=job_id, user={"uid": "outra"})
        with self.assertRaises(HTTPException):
            self.download(job_id="../x", user={"uid": "u1"})


if __name__ == "__main__":
    unittest.main()
