"""Onda 2 do plano V2: embeddings, busca híbrida, citações literais e matriz de evidências."""
import json
import sys
import types
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from embeddings import GeminiEmbedder, make_embedder, normalize, pack_vectors, unpack_vectors
from evidence_matrix import build_matrix, extract_claims, to_csv
from quote_verification import extract_quotes, verify
from retrieval_context import HYBRID_STRATEGY, rank_chunks, select_passages
from source_materials import compose_library_context_v2
from vector_index import VectorIndex

VOCAB = ["sala", "aula", "invertida", "gamificacao", "engajamento", "avaliacao", "docentes", "ensino"]


def fake_vector(text):
    """Embedding determinístico por palavras (só para teste)."""
    folded = text.lower().replace("ç", "c").replace("ã", "a")
    return [float(folded.count(w)) + 0.01 for w in VOCAB]


class FakeModels:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def embed_content(self, model, contents, config):
        if self.fail:
            raise ConnectionError("indisponível")
        self.calls.append((model, list(contents), config.task_type, config.output_dimensionality))
        return types.SimpleNamespace(embeddings=[types.SimpleNamespace(values=fake_vector(t)) for t in contents])


def fake_embedder(fail=False):
    client = types.SimpleNamespace(models=FakeModels(fail))
    return GeminiEmbedder(client, "teste", model="gemini-embedding-001", dimensions=len(VOCAB))


# Sem o SDK google-genai instalado, um módulo mínimo com EmbedContentConfig basta.
# Não substitui o pacote "google" real (google-api-core é usado por outros testes).
try:
    import google.genai  # noqa: F401  (SDK real, se existir)
    REAL_GENAI = not getattr(sys.modules["google.genai"], "__scriptorium_fake__", False)
except ImportError:
    REAL_GENAI = False
if not REAL_GENAI:
    try:
        import google  # pacote namespace real, se existir
    except ImportError:
        google = types.ModuleType("google")
        google.__path__ = []
        sys.modules["google"] = google
    genai_types = types.SimpleNamespace(EmbedContentConfig=lambda **kw: types.SimpleNamespace(**kw))
    fake_genai = sys.modules.get("google.genai") or types.ModuleType("google.genai")
    fake_genai.__scriptorium_fake__ = True
    shared = getattr(fake_genai, "types", None) or types.SimpleNamespace()
    shared.EmbedContentConfig = genai_types.EmbedContentConfig
    genai_types = shared
    fake_genai.types = genai_types
    sys.modules["google.genai"] = fake_genai
    sys.modules["google.genai.types"] = genai_types


def chunk(source, index, text, pages=(1, 1)):
    import hashlib
    return {"chunk_id": f"{source * 12}-{index:04d}-{hashlib.sha256(text.encode()).hexdigest()[:8]}",
            "source_id": source, "index": index, "heading_path": [], "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "char_count": len(text),
            "pages": list(pages) if pages else None, "parser_version": "p-1", "chunk_policy": "c-1"}


class EmbedderTest(unittest.TestCase):
    def test_batches_task_type_and_usage(self):
        embedder = fake_embedder()
        texts = [f"texto {i} sala" for i in range(120)]
        matrix = embedder.embed(texts, "RETRIEVAL_DOCUMENT")
        self.assertEqual(matrix.shape, (120, len(VOCAB)))
        self.assertEqual(len(embedder.client.models.calls), 3)  # lotes de 50
        self.assertEqual(embedder.client.models.calls[0][2], "RETRIEVAL_DOCUMENT")
        self.assertTrue(np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-5))
        self.assertEqual(embedder.info()["usage"]["texts"], 120)
        self.assertNotIn("texto 1", json.dumps(embedder.info()))

    def test_guest_uses_personal_key_never_admin_project(self):
        created = {}

        class Client:
            def __init__(self, **kwargs):
                created.update(kwargs)
        sys.modules["google.genai"].Client = Client
        try:
            embedder = make_embedder("user_gemini", {"GEMINI_API_KEY": "AQ.chave-pessoal-123456789"}, "projeto-admin")
            self.assertEqual(created, {"api_key": "AQ.chave-pessoal-123456789"})
            self.assertIn("chave pessoal", embedder.provider)
            created.clear()
            make_embedder("admin_vertex", {}, "paperorchestra-mestrado")
            self.assertEqual(created["project"], "paperorchestra-mestrado")
            self.assertIsNone(make_embedder("user_gemini", {}, "x"))
            self.assertIsNone(make_embedder("desconhecido", {}, "x"))
        finally:
            del sys.modules["google.genai"].Client

    def test_cache_roundtrip_and_mismatch(self):
        embedder = fake_embedder()
        chunks = [chunk("a", 0, "sala de aula"), chunk("a", 1, "gamificação")]
        matrix = embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
        raw = pack_vectors(chunks, matrix, embedder)
        restored = unpack_vectors(raw, chunks, embedder)
        self.assertTrue(np.allclose(restored, matrix, atol=1e-2))
        changed = [chunks[0], chunk("a", 1, "outro texto")]
        self.assertIsNone(unpack_vectors(raw, changed, embedder))


class HybridTest(unittest.TestCase):
    def test_vector_index_exact_order(self):
        index = VectorIndex(["x", "y", "z"], normalize([[1, 0], [0.7, 0.7], [0, 1]]))
        self.assertEqual([h["chunk_id"] for h in index.search(normalize([1, 0.1])[0], 3)], ["x", "y", "z"])

    def test_semantic_match_without_shared_words(self):
        # O trecho relevante não compartilha palavras com a consulta, mas o vetor sim.
        chunks = [chunk("a", 0, "Agradecimentos aos colegas do laboratório."),
                  chunk("a", 1, "Estudo sobre engajamento discente.")]
        embedder = fake_embedder()
        vectors = {c["chunk_id"]: v for c, v in zip(chunks, embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT"))}
        query = embedder.embed(["engajamento"], "RETRIEVAL_QUERY")[0]
        hits, _, strategy = rank_chunks(chunks, "motivação participação", vectors, query)
        self.assertEqual(strategy, HYBRID_STRATEGY)
        self.assertEqual(hits[0]["chunk_id"], chunks[1]["chunk_id"])
        self.assertIn("vector_rank", hits[0])

    def test_rrf_rewards_agreement(self):
        chunks = [chunk("a", i, t) for i, t in enumerate(
            ["sala de aula invertida ensino", "sala sala sala", "invertida avaliação docentes"])]
        embedder = fake_embedder()
        vectors = {c["chunk_id"]: v for c, v in zip(chunks, embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT"))}
        query = embedder.embed(["sala de aula invertida ensino"], "RETRIEVAL_QUERY")[0]
        selected, coverage = select_passages(chunks, "sala de aula invertida ensino", vectors=vectors, query_vector=query)
        self.assertEqual(selected[0]["index"], 0)
        self.assertEqual(coverage["strategy"], HYBRID_STRATEGY)
        self.assertEqual(coverage["rrf_k"], 60)


class ComposeHybridTest(unittest.TestCase):
    def setUp(self):
        self.sources = [{"id": "a" * 32, "name": "a.txt", "format": "txt", "sha256": "1" * 64,
                         "object_path": "a"}]
        self.data = {"a": "Introdução.\n\nA gamificação aumenta o engajamento no ensino técnico.".encode()}

    def test_hybrid_with_cache_and_collect(self):
        cache, collect = {}, {}

        class Cache:
            def get(self, key):
                return cache.get(key)

            def put(self, key, value):
                cache[key] = value
        embedder = fake_embedder()
        context, manifest, coverage = compose_library_context_v2(
            self.sources, self.data.get, "engajamento", cache=Cache(), embedder=embedder, collect=collect)
        self.assertEqual(coverage["embeddings"]["status"], "completed")
        self.assertEqual(coverage["strategy"], HYBRID_STRATEGY)
        self.assertTrue(any(k.startswith("emb-gemini-embedding-001-") for k in cache))
        self.assertEqual(len(collect["vectors"]), len(collect["chunks"]))
        calls = len(embedder.client.models.calls)
        _, _, coverage2 = compose_library_context_v2(self.sources, self.data.get, "engajamento",
                                                     cache=Cache(), embedder=embedder)
        self.assertEqual(coverage2["embeddings"]["cache_hits"], 1)
        self.assertEqual(len(embedder.client.models.calls), calls + 1)  # só a consulta

    def test_embedding_failure_falls_back_to_lexical(self):
        context, _, coverage = compose_library_context_v2(
            self.sources, self.data.get, "gamificação", embedder=fake_embedder(fail=True))
        self.assertEqual(coverage["embeddings"]["status"], "failed_fallback_lexical")
        self.assertNotEqual(coverage["strategy"], HYBRID_STRATEGY)
        self.assertIn("gamificação", context)


TEX = r"""\documentclass{article}\begin{document}
\section{Introdução}
Segundo a autora, ``a sala de aula invertida desloca a exposição para fora do encontro presencial'' \cite{bergmann2012}.
Outro trecho: \enquote{os estudantes chegam com dúvidas mais qualificadas sobre o conteúdo estudado}.
Uma frase inventada: ``esta citação não aparece em nenhuma das fontes anexadas ao projeto''.
Ver [trecho aaaaaaaaaaaa-0000-12345678 | p. 3].
A gamificação elevou o engajamento em 37\% dos estudantes avaliados \cite{silva2020,costa2021}.
Na Seção 2 apresentamos o método de forma geral para todos.
O clima estava agradável naquele dia de outono em Porto Alegre e arredores.
\end{document}"""


class QuoteVerificationTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            chunk("a", 0, "Na proposta, a sala de aula invertida desloca a exposição para fora do encontro presencial, segundo os autores.", (3, 3)),
            chunk("a", 1, "Os estudantes chegam com dúvidas mais qualificadas sobre o conteúdo que estudaram.", (4, 4)),
        ]
        self.chunks[0]["chunk_id"] = "aaaaaaaaaaaa-0000-12345678"

    def test_extract_quotes(self):
        quotes = extract_quotes(TEX)
        self.assertEqual(len(quotes), 3)

    def test_found_approximate_and_not_found(self):
        report = verify(TEX, self.chunks, {"a": {"name": "Bergmann.pdf"}})
        statuses = [q["status"] for q in report["quotes"]]
        self.assertEqual(statuses, ["found", "not_found_in_sources", "approximate"])
        self.assertEqual(report["quotes"][0]["pages"], [3, 3])
        self.assertEqual(report["quotes"][0]["source_name"], "Bergmann.pdf")
        self.assertEqual(report["pointers"], [{"chunk_id": "aaaaaaaaaaaa-0000-12345678", "status": "valid",
                                               "source_id": "a", "source_name": "Bergmann.pdf",
                                               "chunk_id": "aaaaaaaaaaaa-0000-12345678", "pages": [3, 3],
                                           "locations": []}])

    def test_unknown_pointer_and_no_sources(self):
        report = verify(TEX.replace("aaaaaaaaaaaa-0000-12345678", "bbbbbbbbbbbb-0001-87654321"), [], {})
        self.assertEqual(report["pointers"][0]["status"], "unknown")
        self.assertTrue(all(q["status"] == "no_sources_attached" for q in report["quotes"]))


class EvidenceMatrixTest(unittest.TestCase):
    def test_claims_are_cited_or_numeric_only(self):
        claims = extract_claims(TEX)
        texts = " ".join(c["text"] for c in claims)
        self.assertIn("37", texts)
        self.assertNotIn("Seção 2", texts)
        self.assertNotIn("clima", texts)
        self.assertEqual(claims[0]["cites"], ["bergmann2012"])
        self.assertIn("costa2021", [k for c in claims for k in c["cites"]])

    def test_matrix_candidates_abstention_and_csv(self):
        chunks = [chunk("a", 0, "A gamificação elevou o engajamento dos estudantes avaliados no ensino técnico.", (7, 8)),
                  chunk("a", 1, "Texto sobre outro assunto completamente diferente.", (9, 9))]
        tex = TEX + "\n" + r"\begin{document}Os resultados de 2019 mostram queda de 12\% na evasão escolar regional \cite{x}.\end{document}"
        matrix = build_matrix(TEX, chunks, {"a": {"name": "Silva.pdf"}})
        by_text = {r["text"][:20]: r for r in matrix["claims"]}
        gam = next(r for r in matrix["claims"] if "gamificação" in r["text"])
        self.assertEqual(gam["audit_state"], "candidatos_encontrados")
        self.assertEqual(gam["evidence"][0]["pages"], [7, 8])
        self.assertTrue(all(r["support_state"] == "nao_classificado" and r["requires_human_review"]
                            for r in matrix["claims"]))
        self.assertGreaterEqual(matrix["summary"]["without_evidence_in_corpus"], 1)
        csv_text = to_csv(matrix)
        self.assertTrue(csv_text.startswith("claim_id,afirmacao"))
        self.assertIn("Silva.pdf", csv_text)

    def test_matrix_uses_embeddings_when_available(self):
        chunks = [chunk("a", 0, "Engajamento discente cresceu com gamificação.")]
        embedder = fake_embedder()
        vectors = {chunks[0]["chunk_id"]: embedder.embed([chunks[0]["text"]], "RETRIEVAL_DOCUMENT")[0]}
        matrix = build_matrix(TEX, chunks, {}, vectors=vectors, embedder=embedder)
        self.assertEqual(matrix["embeddings"], "completed")
        self.assertTrue(any(e.get("similarity") for r in matrix["claims"] for e in r["evidence"]))


if __name__ == "__main__":
    unittest.main()
