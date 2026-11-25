#!/usr/bin/env python3
"""Rodada de avaliação do corpus de referência (gate G2 do plano V2).

Origem: R01. Usa scripts/eval_retrieval.py (M04) e mede, no mesmo corpus:
- M04: busca lexical BM25 (recall@5, recall@10, MRR);
- M19: política de trechos com alvos de 800, 1200 (padrão) e 1800 caracteres,
  e uma janela móvel simples que ignora a estrutura (linha de base);
- M20: reranker bge (R17), se a biblioteca estiver instalada;
- M10/M16: limiar de "termos em comum" (MIN_SHARED_TERMS) que separa trechos
  relevantes de irrelevantes, incluindo perguntas SEM resposta no corpus
  (negative=true), que medem o falso "há evidência".
Resultado: um JSON com todas as estratégias e a recomendação de limiar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "scripts"))

import chunking  # noqa: E402
import eval_retrieval as ev  # noqa: E402
from lexical_index import LexicalIndex, query_terms  # noqa: E402
from retrieval_context import rank_chunks  # noqa: E402


def sliding_chunks(corpus: Path, size: int = 1200, overlap: int = 200) -> tuple[list[dict], dict]:
    """Linha de base do M19: janelas fixas sobre o texto de cada página."""
    from structured_extract import extract_document
    import hashlib
    chunks, names = [], {}
    for path in sorted(corpus.glob("*.pdf")):
        sid = hashlib.sha256(path.name.encode()).hexdigest()[:32]
        names[sid] = path.name
        doc = extract_document(path.read_bytes(), "pdf")
        by_page = {}
        for block in doc["blocks"]:
            by_page.setdefault(block.get("page"), []).append(block["text"])
        for page, texts in sorted(by_page.items(), key=lambda kv: kv[0] or 0):
            text = " ".join(texts)
            for start in range(0, max(len(text), 1), size - overlap):
                piece = text[start:start + size]
                if len(piece) < 80:
                    continue
                chunks.append({"chunk_id": f"{sid[:12]}-{len(chunks):04d}-00000000", "source_id": sid,
                               "index": len(chunks), "text": piece, "pages": [page, page],
                               "heading_path": [], "char_count": len(piece)})
    return chunks, names


def measure(chunks, names, queries, k=10, reranker=None):
    by_id = {c["chunk_id"]: c for c in chunks}
    out = {}
    for rerank in ([False, True] if reranker else [False]):
        rankings = []
        for q in queries:
            hits, _, _ = rank_chunks(chunks, q["query"], limit=50)
            if rerank:
                hits = ev.rerank_hits(hits, by_id, q["query"], reranker)
            rankings.append([by_id[h["chunk_id"]] for h in hits])
        name = "rerank_" + reranker.name if rerank else "lexical"
        r10 = ev.evaluate(rankings, queries, names, 10)
        r5 = ev.evaluate(rankings, queries, names, 5)
        out[name] = {"recall@5": r5["recall@5"], "recall@10": r10["recall@10"], "mrr": r10["mrr"],
                     "per_query": r10["per_query"]}
    return out


def calibrate(chunks, names, queries, negatives):
    """Para cada limiar t: o trecho com >= t termos em comum é 'evidência forte'?"""
    index = LexicalIndex()
    index.add(chunks)
    by_id = {c["chunk_id"]: c for c in chunks}
    rows = []
    try:
        for q in queries + negatives:
            terms = query_terms(q["query"])
            for hit in index.search(terms, 10):
                chunk = by_id[hit["chunk_id"]]
                shared = len(set(terms) & set(query_terms(chunk["text"], 200)))
                relevant = any(ev.is_relevant(chunk, lab, names) for lab in q.get("relevant", []))
                rows.append({"q": q["id"], "negative": bool(q.get("negative")), "shared": shared, "relevant": relevant})
    finally:
        index.close()
    table = []
    for t in range(1, 8):
        strong = [r for r in rows if r["shared"] >= t]
        tp = sum(r["relevant"] for r in strong)
        precision = tp / len(strong) if strong else 0.0
        recall = tp / max(1, sum(r["relevant"] for r in rows))
        # Pergunta sem resposta acusada como "há evidência" (falso positivo do M10/M16).
        neg_flagged = len({r["q"] for r in strong if r["negative"]})
        pos_ok = len({r["q"] for r in strong if not r["negative"] and r["relevant"]})
        table.append({"min_shared_terms": t, "precision": round(precision, 3), "recall": round(recall, 3),
                      "negative_queries_flagged": neg_flagged, "negatives": len(negatives),
                      "positive_queries_with_strong_relevant": pos_ok, "positives": len(queries)})
    f1 = lambda r: 2 * r["precision"] * r["recall"] / (r["precision"] + r["recall"] or 1)  # noqa: E731
    best = max(table, key=f1)
    return {"table": table, "recommended_min_shared_terms": best["min_shared_terms"], "current": 3}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--reranker", choices=["bge"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    all_q = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line.strip()]
    queries = [q for q in all_q if not q.get("negative")]
    negatives = [q for q in all_q if q.get("negative")]
    report = {"queries": len(queries), "negative_queries": len(negatives), "variants": {}}
    default_target, default_max = chunking.TARGET_CHARS, chunking.MAX_CHARS
    # Rótulos "contains" vêm dos resumos do OpenAlex; se a frase não aparece em
    # nenhum trecho do arquivo (hifenização, resumo diferente do PDF), o rótulo
    # passa a valer para o documento inteiro, e isso fica registrado.
    base_chunks, base_names = ev.load_corpus(args.corpus)
    files = set(base_names.values())
    fallback, missing_files = [], set()
    for q in queries:
        for label in q["relevant"]:
            if label["file"] not in files:
                missing_files.add(label["file"])
            elif "contains" in label and not any(ev.is_relevant(c, label, base_names) for c in base_chunks):
                fallback.append({"q": q["id"], "file": label["file"], "contains": label.pop("contains")})
        q["relevant"] = [lab for lab in q["relevant"] if lab["file"] in files]
    queries = [q for q in queries if q["relevant"]]
    report["queries"] = len(queries)
    report["labels"] = {"contains_fallback_to_file": fallback, "files_missing_from_corpus": sorted(missing_files)}
    reranker = None
    if args.reranker:
        from reranker import make_reranker
        reranker = make_reranker(args.reranker)
    for target in (800, 1200, 1800):
        chunking.TARGET_CHARS, chunking.MAX_CHARS = target, max(default_max, int(target * 1.6))
        started = time.time()
        chunks, names = ev.load_corpus(args.corpus)
        variant = f"section-paragraph-{target}"
        report["variants"][variant] = {"chunks": len(chunks), "files": len(names),
                                      **measure(chunks, names, queries,
                                                reranker=reranker if target == default_target else None),
                                      "seconds": round(time.time() - started, 1)}
        if target == default_target:
            report["calibration"] = calibrate(chunks, names, queries, negatives)
    chunking.TARGET_CHARS, chunking.MAX_CHARS = default_target, default_max
    chunks, names = sliding_chunks(args.corpus)
    report["variants"]["sliding-1200-overlap-200"] = {"chunks": len(chunks), "files": len(names),
                                                      **measure(chunks, names, queries)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, v in report["variants"].items():
        line = ", ".join(f"{s}: R@10={m['recall@10']} MRR={m['mrr']}" for s, m in v.items()
                         if isinstance(m, dict) and "mrr" in m)
        print(f"{name} ({v['chunks']} trechos): {line}")
    print("Limiar recomendado:", report["calibration"]["recommended_min_shared_terms"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
