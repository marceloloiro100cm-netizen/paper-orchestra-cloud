"""M20 (reranking), M22 (verificação iterativa) e revisões humanas (M08/M12/M24). Sem rede."""
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
from fastapi import HTTPException  # noqa: E402
import reranker as rr  # noqa: E402
from retrieval_context import select_passages  # noqa: E402
from fire_audit import run_fire  # noqa: E402
from audit_shield import build_shield  # noqa: E402
from reviews import ReviewIn, add_review, list_reviews  # noqa: E402

# Mesmo módulo simulado do SDK usado nos outros testes (completa, não substitui).
try:
    import google.genai  # noqa: F401
    REAL = not getattr(sys.modules["google.genai"], "__scriptorium_fake__", False)
except ImportError:
    REAL = False
if not REAL:
    try:
        import google  # noqa: F401
    except ImportError:
        g = types.ModuleType("google"); g.__path__ = []; sys.modules["google"] = g
    fake = sys.modules.get("google.genai") or types.ModuleType("google.genai")
    fake.__scriptorium_fake__ = True
    shared = getattr(fake, "types", None) or types.SimpleNamespace()
    shared.GenerateContentConfig = lambda **kw: kw
    shared.ThinkingConfig = lambda **kw: kw
    fake.types = shared
    sys.modules["google.genai"] = fake
    sys.modules["google.genai.types"] = shared


def chunk(source, index, text, pages=(1, 1)):
    digest = hashlib.sha256(text.encode()).hexdigest()
    return {"chunk_id": f"{source * 12}-{index:04d}-{digest[:8]}", "source_id": source, "index": index,
            "heading_path": [], "text": text, "text_sha256": digest, "char_count": len(text),
            "pages": list(pages)}


class FakeFlag:
    def __init__(self, model, use_fp16=True):
        self.model = model

    def compute_score(self, pairs, normalize=False):
        return [0.9 if "gamificação" in p[1] else 0.1 for p in pairs]


class FakeT5:
    def __init__(self, model_name_or_path):
        self.model = model_name_or_path

    def get_scores(self, query, docs):
        return [len(d) / 100 for d in docs]


class RerankerTest(unittest.TestCase):
    def setUp(self):
        sys.modules["FlagEmbedding"] = types.SimpleNamespace(FlagReranker=FakeFlag)
        sys.modules["inranker"] = types.SimpleNamespace(T5Ranker=FakeT5)

    def tearDown(self):
        sys.modules.pop("FlagEmbedding", None)
        sys.modules.pop("inranker", None)

    def test_factory(self):
        self.assertIsNone(rr.make_reranker("none"))
        bge = rr.make_reranker("bge")
        self.assertEqual((bge.name, bge.model), ("bge", "BAAI/bge-reranker-v2-m3"))
        self.assertEqual(rr.make_reranker("inranker").model, "unicamp-dl/InRanker-small")
        self.assertEqual(bge.info()["upstream_id"], "R17")

    def test_missing_library_raises_import_error(self):
        sys.modules["FlagEmbedding"] = None
        with self.assertRaises(ImportError):
            rr.make_reranker("bge")

    def test_rerank_reorders_head_only(self):
        chunks = [chunk("a", 0, "texto sem relação"), chunk("a", 1, "estudo sobre gamificação"),
                  chunk("a", 2, "cauda")]
        hits = [{"chunk_id": c["chunk_id"], "source_id": "a"} for c in chunks]
        by_id = {c["chunk_id"]: c for c in chunks}
        out = rr.rerank_hits(hits, by_id, "gamificação", rr.make_reranker("bge"), top_n=2)
        self.assertEqual([h["chunk_id"] for h in out], [chunks[1]["chunk_id"], chunks[0]["chunk_id"], chunks[2]["chunk_id"]])
        self.assertEqual(out[0]["pre_rerank_rank"], 2)

    def test_select_passages_with_reranker_and_failure(self):
        chunks = [chunk("a", 0, "ensino técnico e avaliação"), chunk("a", 1, "ensino técnico com gamificação")]
        selected, coverage = select_passages(chunks, "ensino técnico", reranker=rr.make_reranker("bge"),
                                             total_budget=40)
        self.assertEqual(selected[0]["index"], 1)
        self.assertEqual(coverage["reranker"]["status"], "completed")
        broken = rr.Reranker("bge", "x", lambda q, d: [1.0])  # quantidade errada de notas
        _, coverage = select_passages(chunks, "ensino técnico", reranker=broken)
        self.assertEqual(coverage["reranker"]["status"], "failed_kept_previous_order")

    def test_eval_compares_with_and_without_reranker(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("eval_retrieval", ROOT / "scripts" / "eval_retrieval.py")
        ev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ev)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "c"
            folder.mkdir()
            (folder / "a.txt").write_text("Ensino técnico e avaliação.\n\nEnsino técnico com gamificação.", encoding="utf-8")
            q = Path(tmp) / "q.jsonl"
            q.write_text(json.dumps({"id": "q1", "query": "ensino técnico",
                                     "relevant": [{"file": "a.txt", "contains": "gamificação"}]}), encoding="utf-8")
            report = ev.run(folder, q, k=1, reranker=rr.make_reranker("bge"))
        self.assertEqual(set(report["strategies"]), {"lexical", "lexical+rerank_bge"})
        self.assertEqual(report["strategies"]["lexical+rerank_bge"]["recall@1"], 1.0)


class FakeModels:
    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    def generate_content(self, model, contents, config):
        self.prompts.append(contents)
        answer = self.answers.pop(0) if self.answers else {"decisao": "incerta", "confianca": "baixa"}
        return types.SimpleNamespace(text=json.dumps(answer), usage_metadata=types.SimpleNamespace(
            prompt_token_count=50, candidates_token_count=10))


def client(answers):
    return types.SimpleNamespace(models=FakeModels(answers))


class FireTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [chunk("a", 0, "A gamificação aumentou o engajamento discente.", (4, 4)),
                       chunk("b", 0, "Evasão escolar caiu doze por cento no período analisado.", (9, 9))]
        self.meta = {"a": {"name": "A.pdf"}, "b": {"name": "B.pdf"}}
        first = {"chunk_id": self.chunks[0]["chunk_id"], "source_name": "A.pdf", "pages": [4, 4], "excerpt": "x"}
        self.matrix = {"claims": [{"claim_id": "c_001", "text": "A gamificação aumentou o engajamento.",
                                   "cites": [], "evidence": [first]}]}

    def test_confident_decision_with_valid_citation(self):
        report = run_fire(self.matrix, self.chunks, {}, self.meta,
                          client([{"decisao": "apoiada", "confianca": "alta", "evidencias": ["E1"]}]))
        result = report["claims"][0]
        self.assertEqual((result["label"], result["stop_reason"]), ("apoiada_pelas_fontes", "confiante"))
        self.assertTrue(result["evidence"][0]["cited_in_decision"])
        self.assertEqual(report["usage"]["calls"], 1)

    def test_invented_evidence_id_is_not_accepted(self):
        report = run_fire(self.matrix, self.chunks, {}, self.meta,
                          client([{"decisao": "apoiada", "confianca": "alta", "evidencias": ["E9"]}]))
        self.assertEqual(report["claims"][0]["label"], "evidencia_insuficiente")

    def test_uncertain_searches_again_then_decides(self):
        c = client([{"decisao": "incerta", "confianca": "baixa", "nova_busca": "evasão escolar período"},
                    {"decisao": "contrariada", "confianca": "media", "evidencias": ["E2"], "justificativa": "j"}])
        report = run_fire(self.matrix, self.chunks, {}, self.meta, c)
        result = report["claims"][0]
        self.assertEqual(result["label"], "contrariada_pelas_fontes")
        self.assertEqual(len(result["rounds"]), 2)
        self.assertIn("[E2]", c.models.prompts[1])
        shield = build_shield(None, None, None, fire=report)
        self.assertIn(("alta", "Afirmação contrariada pelas fontes anexadas"),
                      {(i["level"], i["title"]) for i in shield["items"]})

    def test_limits_never_become_supported(self):
        report = run_fire(self.matrix, self.chunks, {}, self.meta,
                          client([{"decisao": "incerta", "nova_busca": "x y z"}] * 5))
        self.assertEqual(report["claims"][0]["label"], "evidencia_insuficiente")
        two = {"claims": self.matrix["claims"] * 2}
        report = run_fire(two, self.chunks, {}, self.meta,
                          client([{"decisao": "incerta", "nova_busca": "evasão"}]), max_calls=1)
        self.assertEqual(report["claims"][1]["label"], "nao_verificada")
        self.assertEqual(report["usage"]["calls"], 1)


class Snap:
    def __init__(self, data):
        self.data = data

    def to_dict(self):
        return dict(self.data)


class Coll:
    def __init__(self, store, cond=None):
        self.store, self.cond = store, cond

    def where(self, field, op, value):
        return Coll(self.store, (field, value))

    def limit(self, n):
        return self

    def stream(self):
        return [Snap(v) for v in self.store.values() if not self.cond or v.get(self.cond[0]) == self.cond[1]]

    def document(self, key):
        store = self.store
        return types.SimpleNamespace(create=lambda value: store.__setitem__(key, dict(value)))


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Coll(self.store)


class ReviewsTest(unittest.TestCase):
    def test_append_only_latest_and_owner_filter(self):
        db = DB()
        add_review(db, "j1", "u1", ReviewIn(target_type="claim", target_id="c_001", decision="nao_sustenta"))
        add_review(db, "j1", "u1", ReviewIn(target_type="claim", target_id="c_001", decision="apoia", note="revisto"))
        add_review(db, "j1", "u2", ReviewIn(target_type="claim", target_id="c_001", decision="contradiz"))
        result = list_reviews(db, "j1", "u1")
        self.assertEqual(len(result["history"]), 2)
        self.assertEqual(result["latest"]["claim:c_001"]["decision"], "apoia")

    def test_decision_must_match_type_and_id_is_safe(self):
        with self.assertRaises(HTTPException):
            add_review(DB(), "j1", "u1", ReviewIn(target_type="reference", target_id="k1", decision="apoia"))
        with self.assertRaises(ValueError):
            ReviewIn(target_type="claim", target_id="<script>", decision="apoia")


if __name__ == "__main__":
    unittest.main()
