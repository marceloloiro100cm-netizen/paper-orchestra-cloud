#!/usr/bin/env python3
"""Avaliação de recuperação do Scriptorium (gate G2 do plano V2).

Origem: R01. Mede recall@k e MRR da busca lexical (BM25) e, opcionalmente, da
busca híbrida (BM25 + embeddings Gemini, RRF) num corpus de referência
rotulado por pessoas. Roda localmente; não envia nada ao Scriptorium.

Uso:
  python scripts/eval_retrieval.py --corpus pasta_com_pdfs --queries consultas.jsonl
  GEMINI_API_KEY=... python scripts/eval_retrieval.py --corpus ... --queries ... --hybrid
  python scripts/eval_retrieval.py --corpus ... --queries ... --reranker bge   # M20

consultas.jsonl (uma consulta por linha; ver docs/AVALIACAO-RECUPERACAO.md):
  {"id": "q01", "query": "efeitos da sala de aula invertida na autonomia",
   "relevant": [{"file": "bergmann2012.pdf", "pages": [12, 13]},
                {"file": "silva2020.pdf", "contains": "autonomia discente"}]}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

# A lógica fica no worker (worker/retrieval_eval.py), que também roda a
# avaliação na nuvem com a chave pessoal do administrador.
from retrieval_eval import evaluate, is_relevant, load_corpus, run  # noqa: E402,F401
from reranker import rerank_hits  # noqa: E402,F401


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--hybrid", action="store_true", help="usa embeddings Gemini (GEMINI_API_KEY)")
    parser.add_argument("--reranker", choices=["bge", "inranker"],
                        help="M20: requer pip install FlagEmbedding (bge) ou inranker")
    parser.add_argument("--reranker-model")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    embedder = None
    if args.hybrid:
        from embeddings import GeminiEmbedder
        from google import genai
        embedder = GeminiEmbedder(genai.Client(api_key=os.environ["GEMINI_API_KEY"]), "Gemini API (avaliação local)")
    reranker = None
    if args.reranker:
        from reranker import make_reranker
        reranker = make_reranker(args.reranker, args.reranker_model)
    report = run(args.corpus, args.queries, args.k, embedder, reranker)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
