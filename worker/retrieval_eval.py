"""Avaliação de recuperação no corpus de referência (gate G2 do plano V2).

Origem: R01 (Scriptorium). Mede recall@k e MRR da busca lexical (BM25), da
busca só vetorial (embeddings Gemini, R44) e da híbrida (BM25 + vetores, RRF),
no mesmo corpus e com as mesmas consultas. Plano V2, módulo M04.

Dois usos:
- scripts/eval_retrieval.py e scripts/eval_corpus.py (no computador ou no CI);
- o worker, modo "retrieval_eval" (só administrador): baixa os PDFs de acesso
  aberto listados em corpus_ref/selecao.json, confere o SHA-256 e mede com a
  chave Gemini pessoal de quem pediu. Assim a chave nunca sai do Secret Manager
  e nunca passa pelo GitHub.

Os documentos do corpus são publicados em acesso aberto (não são dados
inéditos; IN IFRS 16/2026, Art. 9º não se aplica). O relatório guarda só
métricas e identificadores das consultas, nunca o texto dos PDFs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from chunking import chunk_document
from latex_text import fold
from reranker import rerank_hits
from retrieval_context import rank_chunks
from structured_extract import extract_document

FORMATS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".bib": "bib", ".ris": "ris"}
EVAL_VERSION = "retrieval-eval-2"
MAX_PDF_BYTES = 40 * 1024 * 1024
USER_AGENT = "Scriptorium-corpus/1 (https://github.com/marceloloiro100cm-netizen/scriptorium)"


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


def run(corpus: Path, queries_path: Path, k: int = 10, embedder=None, reranker=None) -> dict:
    chunks, names = load_corpus(corpus)
    by_id = {c["chunk_id"]: c for c in chunks}
    queries = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"corpus_files": len(names), "chunks": len(chunks), "k": k, "strategies": {}}
    vectors = None
    if embedder is not None:
        matrix = embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
        vectors = {c["chunk_id"]: matrix[i] for i, c in enumerate(chunks)}
    bases = ["lexical"] + (["hybrid"] if vectors is not None else [])
    for base in bases:
        # Com --reranker, cada base é medida com e sem reranking (comparação do M20).
        for rerank in ([False, True] if reranker is not None else [False]):
            name = base + (f"+rerank_{reranker.name}" if rerank else "")
            rankings = []
            for query in queries:
                qvec = embedder.embed([query["query"]], "RETRIEVAL_QUERY")[0] if base == "hybrid" else None
                hits, _, strategy = rank_chunks(chunks, query["query"], vectors if base == "hybrid" else None, qvec)
                if rerank:
                    hits = rerank_hits(hits, by_id, query["query"], reranker)
                rankings.append([by_id[h["chunk_id"]] for h in hits])
            report["strategies"][name] = {"strategy": strategy, "reranker": reranker.info() if rerank else None,
                                          **evaluate(rankings, queries, names, k)}
    return report


# ------------------------------------------------------- corpus de referência
def fetch_reference_corpus(selection: dict, dest: Path, http_get) -> dict:
    """Baixa os PDFs da seleção. http_get(url) -> bytes (até MAX_PDF_BYTES).

    SHA-256 diferente do registrado é anotado (o arquivo mudou na origem) e o
    documento continua, como no workflow do CI; falha de rede só tira o
    documento da conta.
    """
    dest.mkdir(parents=True, exist_ok=True)
    report = {"expected": 0, "downloaded": [], "failed": [], "sha_mismatch": []}
    for item in selection["documentos"]:
        report["expected"] += 1
        name = Path(item["file"]).name
        url = str(item.get("pdf_url", ""))
        if name != item["file"] or not name.endswith(".pdf") or not url.startswith("https://"):
            report["failed"].append({"file": item["file"], "reason": "registro inválido"})
            continue
        try:
            data = http_get(url)
        except Exception as exc:  # noqa: BLE001 - rede de terceiros
            report["failed"].append({"file": name, "reason": type(exc).__name__})
            continue
        if not data.startswith(b"%PDF"):
            report["failed"].append({"file": name, "reason": "não é PDF"})
            continue
        if hashlib.sha256(data).hexdigest() != item.get("sha256"):
            report["sha_mismatch"].append(name)
        (dest / name).write_bytes(data)
        report["downloaded"].append(name)
    return report


def prepare_queries(queries: list[dict], chunks: list[dict], names: dict) -> tuple[list[dict], dict]:
    """Só consultas com resposta; rótulos de arquivos ausentes saem da conta."""
    files = set(names.values())
    fallback, missing = [], set()
    ready = []
    for query in queries:
        if query.get("negative") or not query.get("relevant"):
            continue
        labels = []
        for label in query["relevant"]:
            if label["file"] not in files:
                missing.add(label["file"])
                continue
            label = dict(label)
            if "contains" in label and not any(is_relevant(c, label, names) for c in chunks):
                # Hifenização ou resumo diferente do PDF: o rótulo vale para o arquivo.
                fallback.append({"q": query.get("id"), "file": label["file"]})
                label.pop("contains")
            labels.append(label)
        if labels:
            ready.append({**query, "relevant": labels})
    return ready, {"files_missing_from_corpus": sorted(missing), "contains_fallback_to_file": fallback}


def _vector_rankings(queries, chunks, matrix, query_matrix, limit=50):
    order = np.argsort(-(query_matrix @ matrix.T), axis=1)[:, :limit]
    return [[chunks[i] for i in row] for row in order]


def _groups(per_query: list[dict], queries: list[dict]) -> dict:
    """Específicas (q01-q35) e temáticas (q36 em diante), como em docs/corpus."""
    kinds = {q["id"]: ("tematicas" if int(q["id"][1:]) > 35 else "especificas") for q in queries}
    out = {}
    for name in ("especificas", "tematicas"):
        rows = [p for p in per_query if kinds.get(p["id"]) == name]
        if rows:
            out[name] = {"queries": len(rows),
                         "recall@10": round(sum(p["recall"] for p in rows) / len(rows), 4),
                         "mrr": round(sum(1 / p["first_relevant_rank"] if p["first_relevant_rank"] else 0
                                          for p in rows) / len(rows), 4)}
    return out


def reference_eval(corpus: Path, queries: list[dict], embedder, k: int = 10) -> dict:
    """Lexical, vetorial e híbrida no corpus baixado, com a política de trechos padrão."""
    chunks, names = load_corpus(corpus)
    ready, labels = prepare_queries(queries, chunks, names)
    by_id = {c["chunk_id"]: c for c in chunks}
    matrix = embedder.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
    query_matrix = embedder.embed([q["query"] for q in ready], "RETRIEVAL_QUERY")
    vectors = {c["chunk_id"]: matrix[i] for i, c in enumerate(chunks)}
    rankings = {"lexical": [], "hybrid": []}
    strategy = ""
    for i, query in enumerate(ready):
        hits, _, _ = rank_chunks(chunks, query["query"])
        rankings["lexical"].append([by_id[h["chunk_id"]] for h in hits])
        hits, _, strategy = rank_chunks(chunks, query["query"], vectors, query_matrix[i])
        rankings["hybrid"].append([by_id[h["chunk_id"]] for h in hits])
    rankings["vector"] = _vector_rankings(ready, chunks, matrix, query_matrix)
    strategies = {}
    for name, ranks in rankings.items():
        r10 = evaluate(ranks, ready, names, k)
        r5 = evaluate(ranks, ready, names, 5)
        strategies[name] = {"recall@5": r5["recall@5"], "recall@10": r10["recall@10"], "mrr": r10["mrr"],
                            "groups": _groups(r10["per_query"], ready), "per_query": r10["per_query"]}
    lex = {p["id"]: p for p in strategies["lexical"]["per_query"]}
    changed = []
    for p in strategies["hybrid"]["per_query"]:
        before = lex[p["id"]]
        if (p["recall"], p["first_relevant_rank"]) != (before["recall"], before["first_relevant_rank"]):
            changed.append({"id": p["id"], "lexical": [before["recall"], before["first_relevant_rank"]],
                            "hybrid": [p["recall"], p["first_relevant_rank"]]})
    return {"version": EVAL_VERSION, "corpus_files": len(names), "chunks": len(chunks), "k": k,
            "queries": len(ready), "labels": labels, "hybrid_strategy": strategy,
            "embedder": embedder.info(), "strategies": strategies, "hybrid_vs_lexical": changed}


def summary(report: dict) -> dict:
    """Resumo pequeno para o registro no Firestore e para a tela."""
    out = {"corpus_files": report["corpus_files"], "queries": report["queries"], "chunks": report["chunks"]}
    for name, s in report["strategies"].items():
        out[name] = {"recall@5": s["recall@5"], "recall@10": s["recall@10"], "mrr": s["mrr"],
                     **{f"{g}_recall@10": v["recall@10"] for g, v in s["groups"].items()}}
    out["changed_queries"] = len(report["hybrid_vs_lexical"])
    return out
