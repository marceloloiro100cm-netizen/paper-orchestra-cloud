#!/usr/bin/env python3
"""Avaliação de recuperação do Scriptorium (gate G2 do plano V2).

Origem: R01. Mede recall@k e MRR da busca lexical (BM25) e, opcionalmente, da
busca híbrida (BM25 + embeddings Gemini, RRF) num corpus de referência
rotulado por pessoas. Roda localmente; não envia nada ao Scriptorium.

Uso:
  python scripts/eval_retrieval.py --corpus pasta_com_pdfs --queries consultas.jsonl
  GEMINI_API_KEY=... python scripts/eval_retrieval.py --corpus ... --queries ... --hybrid

consultas.jsonl (uma consulta por linha; ver docs/AVALIACAO-RECUPERACAO.md):
  {"id": "q01", "query": "efeitos da sala de aula invertida na autonomia",
   "relevant": [{"file": "bergmann2012.pdf", "pages": [12, 13]},
                {"file": "silva2020.pdf", "contains": "autonomia discente"}]}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

from chunking import chunk_document  # noqa: E402
from latex_text import fold  # noqa: E402
from retrieval_context import rank_chunks  # noqa: E402
from structured_extract import extract_document  # noqa: E402

FORMATS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".bib": "bib", ".ris": "ris"}


def load_corpus(folder: Path) -> tuple[list[dict], dict]:
    chunks, names = [], {}
    for path in sorted(folder.iterdir()):
        fmt = FORMATS.get(path.suffix.lower())
        if not fmt:
            continue
        source_id = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:32]
        names[source_id] = path.name
        chunks += chunk_document(extract_document(path.read_bytes(), fmt), source_id)
    return chunks, names


def is_relevant(chunk: dict, label: dict, names: dict) -> bool:
    if names.get(chunk["source_id"]) != label["file"]:
        return False
    if "pages" in label:
        pages = chunk.get("pages")
        return bool(pages) and any(pages[0] <= p <= pages[1] for p in label["pages"])
    if "contains" in label:
        return fold(label["contains"]) in fold(chunk["text"])
    return True


def evaluate(results: list[list[dict]], queries: list[dict], names: dict, k: int) -> dict:
    """recall@k: fração dos rótulos atendidos no top-k; MRR: 1/posição do 1º relevante."""
    recalls, reciprocal, per_query = [], [], []
    for ranking, query in zip(results, queries):
        labels = query["relevant"]
        top = ranking[:k]
        found = sum(any(is_relevant(c, label, names) for c in top) for label in labels)
        first = next((i for i, c in enumerate(ranking, start=1)
                      if any(is_relevant(c, label, names) for label in labels)), None)
        recall = found / len(labels) if labels else 0.0
        recalls.append(recall)
        reciprocal.append(1 / first if first else 0.0)
        per_query.append({"id": query.get("id"), "recall": round(recall, 4), "first_relevant_rank": first})
    n = len(queries) or 1
    return {f"recall@{k}": round(sum(recalls) / n, 4), "mrr": round(sum(reciprocal) / n, 4),
            "queries": len(queries), "per_query": per_query}


def run(corpus: Path, queries_path: Path, k: int = 10, embedder=None) -> dict:
    chunks, names = load_corpus(corpus)
    by_id = {c["chunk_id"]: c for c in chunks}
    queries = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"corpus_files": len(names), "chunks": len(chunks), "k": k, "strategies": {}}
    vectors = None
    if embedder is not None:
        matrix = embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
        vectors = {c["chunk_id"]: matrix[i] for i, c in enumerate(chunks)}
    for name in ("lexical", "hybrid"):
        if name == "hybrid" and vectors is None:
            continue
        rankings = []
        for query in queries:
            qvec = embedder.embed([query["query"]], "RETRIEVAL_QUERY")[0] if name == "hybrid" else None
            hits, _, strategy = rank_chunks(chunks, query["query"], vectors if name == "hybrid" else None, qvec)
            rankings.append([by_id[h["chunk_id"]] for h in hits])
        report["strategies"][name] = {"strategy": strategy, **evaluate(rankings, queries, names, k)}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--hybrid", action="store_true", help="usa embeddings Gemini (GEMINI_API_KEY)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    embedder = None
    if args.hybrid:
        from embeddings import GeminiEmbedder
        from google import genai
        embedder = GeminiEmbedder(genai.Client(api_key=os.environ["GEMINI_API_KEY"]), "Gemini API (avaliação local)")
    report = run(args.corpus, args.queries, args.k, embedder)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
