"""Onda 4/5 do plano V2: checkpoint de fontes (M12), diagnóstico (M16),
divergências entre fontes (M17) e importação do Zotero (M26). Sem rede."""
import hashlib
import json
import sys
import types
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
from fastapi import HTTPException  # noqa: E402
from job_state import StateConflict, claim_in_transaction, transition_in_transaction  # noqa: E402
from gap_report import build_gap_report, extract_questions  # noqa: E402
from contradictions import candidate_pairs, classify_pair, detect  # noqa: E402
from audit_shield import build_shield  # noqa: E402
import zotero_import as zi  # noqa: E402


# ------------------------------------------------------------------ fakes
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

    def create(self, value):
        assert self.path not in self.store
        self.store[self.path] = dict(value)


class Query:
    def __init__(self, store, name, cond=None):
        self.store, self.name, self.cond = store, name, cond

    def where(self, field, op, value):
        return Query(self.store, self.name, (field, value))

    def limit(self, n):
        return self

    def stream(self):
        for (name, _), value in list(self.store.items()):
            if name == self.name and (not self.cond or value.get(self.cond[0]) == self.cond[1]):
                yield Snap(value)


class Collection(Query):
    def __init__(self, store, name):
        super().__init__(store, name)

    def document(self, key):
        return Ref(self.store, (self.name, key))


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Collection(self.store, name)


class Tx:
    def set(self, ref, value):
        ref.store[ref.path] = dict(value)

    def update(self, ref, fields):
        ref.update(fields)


class Blob:
    def __init__(self, bucket, path):
        self.bucket, self.path = bucket, path

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        self.bucket.objects[self.path] = data

    def delete(self):
        self.bucket.objects.pop(self.path, None)


class Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, path):
        return Blob(self, path)


# ------------------------------------------------------------- M12
class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.db, self.tx = DB(), Tx()
        self.db.store[("research_jobs", "j1")] = {"id": "j1", "status": "awaiting_source_approval"}

    def approve(self):
        record = {"id": "j1", "status": "queued", "mode": "generate"}
        return claim_in_transaction(self.tx, self.db, "u1", "j1", record,
                                    expected_status="awaiting_source_approval")

    def test_approval_moves_to_queue_and_takes_lock(self):
        self.assertTrue(self.approve())
        self.assertEqual(self.db.store[("research_jobs", "j1")]["status"], "queued")
        self.assertEqual(self.db.store[("research_owner_state", "u1")]["active_job_id"], "j1")

    def test_double_approval_is_rejected(self):
        self.assertTrue(self.approve())
        with self.assertRaises(StateConflict):
            self.approve()

    def test_discard_only_from_awaiting(self):
        transition_in_transaction(self.tx, self.db, "j1", "awaiting_source_approval", {"status": "discarded"})
        self.assertEqual(self.db.store[("research_jobs", "j1")]["status"], "discarded")
        with self.assertRaises(StateConflict):
            transition_in_transaction(self.tx, self.db, "j1", "awaiting_source_approval", {"status": "x"})


# ------------------------------------------------------------- M16
def chunk(source, index, text, pages=(1, 1)):
    digest = hashlib.sha256(text.encode()).hexdigest()
    return {"chunk_id": f"{source * 12}-{index:04d}-{digest[:8]}", "source_id": source, "index": index,
            "heading_path": [], "text": text, "text_sha256": digest, "char_count": len(text),
            "pages": list(pages)}


class GapReportTest(unittest.TestCase):
    def test_questions_or_subtopics(self):
        qs = extract_questions("Gamificação no ensino técnico",
                               "Quero estudar isso. Como a gamificação afeta o engajamento discente? "
                               "Quais críticas existem sobre o efeito novidade?")
        self.assertEqual([q["kind"] for q in qs], ["tema_geral", "pergunta", "pergunta"])
        qs = extract_questions("", "A sala de aula invertida melhora a autonomia dos estudantes no ensino médio.")
        self.assertEqual(qs[0]["kind"], "subtopico")

    def test_levels_suggestions_and_problems(self):
        chunks = [chunk("a", 0, "Gamificação aumenta engajamento discente no ensino técnico segundo o estudo."),
                  chunk("a", 1, "Engajamento discente com gamificação cresceu em turmas do ensino técnico."),
                  chunk("b", 0, "A gamificação elevou o engajamento discente em escolas de ensino técnico."),
                  chunk("c", 0, "Receitas de culinária regional gaúcha.")]
        meta = {"a": {"name": "A.pdf"}, "b": {"name": "B.pdf"}, "c": {"name": "C.pdf"}}
        report = build_gap_report(
            "Gamificação", "Como a gamificação afeta o engajamento discente no ensino técnico? "
            "Qual o impacto da avaliação formativa remota sincronizada?", chunks, meta,
            [{"name": "C.pdf", "status": "included", "ocr_pages_flagged": [3]}])
        levels = [q["coverage"] for q in report["questions"] if q["kind"] == "pergunta"]
        self.assertEqual(levels, ["boa", "lacuna"])
        self.assertIn("C.pdf", " ".join(report["suggestions"]))
        self.assertTrue(any("Sem trechos" in s for s in report["suggestions"]))
        self.assertEqual(report["source_problems"][0]["ocr_pages_flagged"], [3])
        self.assertTrue(any("não ausência" in x for x in report["limitations"]))


# ------------------------------------------------------------- M17
class FakeModels:
    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        return types.SimpleNamespace(text=json.dumps(self.payloads.pop(0)), usage_metadata=types.SimpleNamespace(
            prompt_token_count=100, candidates_token_count=20))


# Sem o SDK real: completa (sem substituir) o módulo simulado de outros testes.
try:
    import google.genai  # noqa: F401
    REAL_GENAI = not getattr(sys.modules["google.genai"], "__scriptorium_fake__", False)
except ImportError:
    REAL_GENAI = False
if not REAL_GENAI:
    try:
        import google  # noqa: F401
    except ImportError:
        google = types.ModuleType("google")
        google.__path__ = []
        sys.modules["google"] = google
    fake = sys.modules.get("google.genai") or types.ModuleType("google.genai")
    fake.__scriptorium_fake__ = True
    shared = getattr(fake, "types", None) or types.SimpleNamespace()
    shared.GenerateContentConfig = lambda **kw: kw
    shared.ThinkingConfig = lambda **kw: kw
    fake.types = shared
    sys.modules["google.genai"] = fake
    sys.modules["google.genai.types"] = shared


class ContradictionsTest(unittest.TestCase):
    def setUp(self):
        self.a = chunk("a", 0, "A gamificação aumentou o engajamento em 30% dos alunos.")
        self.b = chunk("b", 0, "Não houve efeito da gamificação sobre o engajamento após seis meses.")
        self.c = chunk("a", 1, "Outro trecho da mesma fonte A sobre gamificação.")
        self.vectors = {self.a["chunk_id"]: np.array([1.0, 0.0]), self.b["chunk_id"]: np.array([0.95, 0.31]),
                        self.c["chunk_id"]: np.array([1.0, 0.01])}

    def test_pairs_only_across_sources(self):
        pairs = candidate_pairs([self.a, self.b, self.c], self.vectors)
        self.assertEqual(len(pairs), 1)
        self.assertNotEqual(pairs[0][1]["source_id"], pairs[0][2]["source_id"])

    def test_quotes_are_checked_and_relation_validated(self):
        client = types.SimpleNamespace(models=FakeModels([
            {"relacao": "divergente", "justificativa": "Uma diz que aumentou, outra que não houve efeito.",
             "evidencia_a": "aumentou o engajamento em 30%", "evidencia_b": "frase inventada pelo modelo"}]))
        result, tokens = classify_pair(client, self.a, self.b)
        self.assertEqual(result["relacao"], "divergente")
        self.assertEqual(result["evidencia_a"], "aumentou o engajamento em 30%")
        self.assertIsNone(result["evidencia_b"])
        self.assertFalse(result["citacoes_conferidas"])
        client = types.SimpleNamespace(models=FakeModels([{"relacao": "talvez"}]))
        self.assertEqual(classify_pair(client, self.a, self.b)[0]["relacao"], "nao_classificado")

    def test_detect_and_shield(self):
        client = types.SimpleNamespace(models=FakeModels([{"relacao": "divergente", "justificativa": "j"}]))
        result = detect([self.a, self.b, self.c], self.vectors, {"a": {"name": "A"}, "b": {"name": "B"}}, client)
        self.assertEqual(result["summary"]["divergente"], 1)
        self.assertEqual(result["usage"]["calls"], 1)
        shield = build_shield(None, None, None, result)
        self.assertIn("Possível divergência entre fontes", [i["title"] for i in shield["items"]])
        self.assertEqual(build_shield(None, None, None)["stages"]["5_divergencias_entre_fontes"]["status"], "nao_executado")


# ------------------------------------------------------------- M26
KEY = "AbCdEfGhIjKlMnOpQrStUvWx"


def bib(n, start=0):
    return "\n".join(f"@article{{k{i},\n title={{T{i}}}\n}}" for i in range(start, start + n)).encode()


class ZoteroTransport:
    def __init__(self, total=150, status=200):
        self.total, self.status, self.calls = total, status, []

    def __call__(self, path, key):
        self.calls.append(path)
        if self.status != 200:
            return self.status, {}, b""
        if path.startswith("/keys/"):
            return 200, {}, json.dumps({"userID": 4321, "key": key}).encode()
        if "/collections?" in path:
            return 200, {"Total-Results": "1"}, json.dumps(
                [{"key": "ABCD2345", "data": {"name": "Mestrado"}, "meta": {"numItems": 12}}]).encode()
        start = int(path.split("start=")[1])
        limit = int(path.split("limit=")[1].split("&")[0])
        count = max(0, min(limit, self.total - start))
        return 200, {"Total-Results": str(self.total)}, bib(count, start)


class ZoteroTest(unittest.TestCase):
    def test_collections(self):
        items = zi.list_collections(KEY, transport=ZoteroTransport())
        self.assertEqual(items, [{"key": "ABCD2345", "name": "Mestrado", "parent": None, "items": 12}])

    def test_export_paginates_top_items_in_bibtex(self):
        transport = ZoteroTransport(total=150)
        text, user_id, count, _version = zi.export_bibtex(KEY, "ABCD2345", 500, transport=transport)
        self.assertEqual((user_id, count), ("4321", 150))
        pages = [c for c in transport.calls if "/items/top" in c]
        self.assertEqual(len(pages), 2)
        self.assertTrue(all("format=bibtex" in c and "/collections/ABCD2345/" in c for c in pages))

    def test_errors_never_echo_key(self):
        with self.assertRaises(HTTPException) as ctx:
            zi.export_bibtex(KEY, None, 10, transport=ZoteroTransport(status=403))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertNotIn(KEY, str(ctx.exception.detail))
        with self.assertRaises(HTTPException):
            zi.export_bibtex(KEY, "../x", 10, transport=ZoteroTransport())
        with self.assertRaises(HTTPException):
            zi.ZoteroKey(api_key="curta").value()

    def test_import_saves_bib_with_origin_and_no_key(self):
        db, bucket = DB(), Bucket()
        router = zi.make_zotero_router(db, bucket, lambda: None, transport=ZoteroTransport(total=3))
        endpoint = next(r.endpoint for r in router.routes if r.path.endswith("/import"))
        result = endpoint(payload=zi.ZoteroImport(api_key=KEY, collection_key="ABCD2345"), user={"uid": "u1"})
        self.assertEqual(result["items_imported"], 3)
        stored = next(v for (name, _), v in db.store.items() if name == "library_items")
        self.assertEqual(stored["format"], "bib")
        self.assertEqual(stored["origin"]["provider"], "zotero")
        self.assertEqual(stored["origin"]["attachments"], "not_imported")
        self.assertNotIn(KEY, json.dumps(stored))
        self.assertTrue(next(iter(bucket.objects)).startswith("library/u1/"))


if __name__ == "__main__":
    unittest.main()
