"""Gate G2: métricas de recuperação (recall@k e MRR) num corpus mínimo, sem rede."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_retrieval", ROOT / "scripts" / "eval_retrieval.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


class EvalTest(unittest.TestCase):
    def test_metrics(self):
        names = {"s": "a.txt"}
        relevant = {"source_id": "s", "pages": None, "text": "resposta certa aqui"}
        other = {"source_id": "s", "pages": None, "text": "nada a ver"}
        queries = [{"id": "q1", "relevant": [{"file": "a.txt", "contains": "resposta certa"}]},
                   {"id": "q2", "relevant": [{"file": "a.txt", "contains": "inexistente"}]}]
        report = ev.evaluate([[other, relevant], [other]], queries, names, k=10)
        self.assertEqual(report["recall@10"], 0.5)
        self.assertEqual(report["mrr"], 0.25)
        self.assertEqual(report["per_query"][0]["first_relevant_rank"], 2)

    def test_page_labels(self):
        chunk = {"source_id": "s", "pages": [3, 4], "text": "x"}
        self.assertTrue(ev.is_relevant(chunk, {"file": "a.pdf", "pages": [4]}, {"s": "a.pdf"}))
        self.assertFalse(ev.is_relevant(chunk, {"file": "a.pdf", "pages": [5]}, {"s": "a.pdf"}))
        self.assertFalse(ev.is_relevant(chunk, {"file": "b.pdf", "pages": [4]}, {"s": "a.pdf"}))

    def test_end_to_end_lexical(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "corpus"
            folder.mkdir()
            (folder / "a.txt").write_text("Agradecimentos.\n\nA gamificação aumenta o engajamento discente.", encoding="utf-8")
            (folder / "b.txt").write_text("Sala de aula invertida e autonomia dos estudantes.", encoding="utf-8")
            queries = Path(tmp) / "q.jsonl"
            queries.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in [
                {"id": "q1", "query": "gamificação engajamento", "relevant": [{"file": "a.txt", "contains": "engajamento"}]},
                {"id": "q2", "query": "autonomia na sala invertida", "relevant": [{"file": "b.txt"}]},
            ]), encoding="utf-8")
            report = ev.run(folder, queries, k=1)
        lexical = report["strategies"]["lexical"]
        self.assertEqual(report["corpus_files"], 2)
        self.assertEqual(lexical["recall@1"], 1.0)
        self.assertEqual(lexical["mrr"], 1.0)
        self.assertNotIn("hybrid", report["strategies"])


if __name__ == "__main__":
    unittest.main()
