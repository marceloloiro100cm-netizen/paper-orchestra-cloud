"""Matriz de evidências e sinal de abstenção por afirmação (M08 e M10).

Origem: R01 (código próprio), usando os índices de M03/M04 (R06, R43, R44).
Plano: Scriptorium V2, módulos M08 "Matriz de Evidências e proveniência" e M10
"Abstenção quando há evidência insuficiente".

Para cada afirmação verificável do manuscrito final (frase com citação \\cite,
número ou percentual), busca até 3 trechos candidatos nas fontes anexadas
(BM25, e embeddings quando disponíveis, fundidos por RRF).

O que a matriz NÃO faz: decidir se o trecho sustenta ou contradiz a afirmação.
support_state fica sempre "nao_classificado" e toda linha pede revisão humana.
O sinal M10 ("sem_evidencia_no_corpus") significa apenas que nada parecido foi
localizado nas fontes ANEXADAS; a afirmação pode estar apoiada em obras da
bibliografia que não foram anexadas.
"""
from __future__ import annotations

import csv
import io
import re

from latex_text import CITE, body_of, strip_commands
from lexical_index import LexicalIndex, query_terms

VERSION = "evidence-matrix-1"
MAX_CLAIMS = 60
TOP_EVIDENCE = 3
# Limiares provisórios, a calibrar com o corpus de referência (gate G2).
MIN_SHARED_TERMS = 3
MIN_SIMILARITY = 0.70
THRESHOLD_VERSION = "provisorio-1"
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý\\])")
# Percentuais, decimais e números com 2+ dígitos (ignora "Seção 2", "Tabela 1").
NUMERIC = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|\\%|por cento|percent)|\b\d+[.,]\d+\b|\b\d{2,}\b")


def extract_claims(tex: str) -> list[dict]:
    body = body_of(tex)
    claims, seen = [], set()
    for raw in SENTENCE.split(re.sub(r"\s+", " ", body)):
        cites = [k.strip() for m in CITE.finditer(raw) for k in m.group(1).split(",") if k.strip()]
        text = strip_commands(raw)
        if len(text.split()) < 6 or text in seen:
            continue
        has_number = bool(NUMERIC.search(text))
        if not cites and not has_number:
            continue
        seen.add(text)
        claims.append({"text": text[:600], "cites": cites, "has_number": has_number})
    # Prioridade: afirmações com citação, depois as numéricas.
    claims.sort(key=lambda c: (not c["cites"],))
    claims = claims[:MAX_CLAIMS]
    for index, claim in enumerate(claims, start=1):
        claim["claim_id"] = f"c_{index:03d}"
    return claims


def find_candidates(text: str, query_vector, index: LexicalIndex, vector_index, by_id: dict,
                    sources_meta: dict, top: int = TOP_EVIDENCE) -> list[dict]:
    """Trechos candidatos para um texto (BM25 + vetores por RRF), com página."""
    terms = query_terms(text)
    scores: dict[str, dict] = {}
    for rank, hit in enumerate(index.search(terms, 10), start=1):
        scores.setdefault(hit["chunk_id"], {"rrf": 0.0})
        scores[hit["chunk_id"]].update(bm25_rank=rank)
        scores[hit["chunk_id"]]["rrf"] += 1 / (60 + rank)
    if query_vector is not None and vector_index is not None:
        for rank, hit in enumerate(vector_index.search(query_vector, 10), start=1):
            scores.setdefault(hit["chunk_id"], {"rrf": 0.0})
            scores[hit["chunk_id"]].update(vector_rank=rank, similarity=hit["similarity"])
            scores[hit["chunk_id"]]["rrf"] += 1 / (60 + rank)
    evidence = []
    for chunk_id, info in sorted(scores.items(), key=lambda kv: -kv[1]["rrf"])[:top]:
        chunk = by_id[chunk_id]
        evidence.append({
            "chunk_id": chunk_id, "source_id": chunk["source_id"],
            "source_name": sources_meta.get(chunk["source_id"], {}).get("name", ""),
            "pages": chunk.get("pages"), "excerpt": chunk["text"][:280],
            "shared_terms": len(set(terms) & set(query_terms(chunk["text"], 200))),
            "bm25_rank": info.get("bm25_rank"), "similarity": info.get("similarity"),
            "relation": "nao_classificado",
        })
    return evidence


def is_strong(evidence: dict) -> bool:
    return evidence["shared_terms"] >= MIN_SHARED_TERMS or (evidence["similarity"] or 0) >= MIN_SIMILARITY


def build_matrix(tex: str, chunks: list[dict], sources_meta: dict,
                 vectors: dict | None = None, embedder=None) -> dict:
    claims = extract_claims(tex)
    by_id = {c["chunk_id"]: c for c in chunks}
    index = LexicalIndex()
    claim_vectors, vector_index, embedding_status = None, None, "disabled"
    try:
        index.add(chunks)
        if embedder is not None and vectors and claims:
            try:
                from vector_index import VectorIndex
                ids = [cid for cid in by_id if cid in vectors]
                vector_index = VectorIndex(ids, [vectors[i] for i in ids])
                claim_vectors = embedder.embed([c["text"] for c in claims], "RETRIEVAL_QUERY")
                embedding_status = "completed"
            except Exception as error:
                claim_vectors, embedding_status = None, f"failed_fallback_lexical:{type(error).__name__}"
        rows = []
        for position, claim in enumerate(claims):
            qvec = claim_vectors[position] if claim_vectors is not None else None
            evidence = find_candidates(claim["text"], qvec, index, vector_index, by_id, sources_meta)
            strong = [e for e in evidence if is_strong(e)]
            rows.append({
                **claim,
                "evidence": evidence,
                "support_state": "nao_classificado",
                "audit_state": "candidatos_encontrados" if strong else "sem_evidencia_no_corpus",
                "requires_human_review": True,
            })
    finally:
        index.close()
    found = sum(r["audit_state"] == "candidatos_encontrados" for r in rows)
    return {
        "version": VERSION, "threshold_version": THRESHOLD_VERSION,
        "thresholds": {"min_shared_terms": MIN_SHARED_TERMS, "min_similarity": MIN_SIMILARITY},
        "embeddings": embedding_status,
        "claims": rows,
        "summary": {"claims": len(rows), "with_candidates": found,
                    "without_evidence_in_corpus": len(rows) - found,
                    "with_citation": sum(bool(r["cites"]) for r in rows)},
        "limitations": [
            "A relação entre afirmação e trecho NÃO foi classificada (apoia, contradiz ou só menciona): leia os trechos.",
            "'Sem evidência no corpus' vale só para as fontes anexadas; a afirmação pode se apoiar na bibliografia.",
            "Limiares provisórios; serão calibrados com o corpus de referência.",
            f"No máximo {MAX_CLAIMS} afirmações por manuscrito, priorizando as que têm citação.",
        ],
    }


def to_csv(matrix: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["claim_id", "afirmacao", "citacoes", "situacao", "fonte", "paginas",
                     "trecho_id", "termos_em_comum", "similaridade", "relacao"])
    for row in matrix["claims"]:
        evidence = row["evidence"] or [{}]
        for item in evidence:
            pages = item.get("pages")
            writer.writerow([
                row["claim_id"], row["text"], ";".join(row["cites"]), row["audit_state"],
                item.get("source_name", ""), f"{pages[0]}-{pages[1]}" if pages else "",
                item.get("chunk_id", ""), item.get("shared_terms", ""),
                item.get("similarity") if item.get("similarity") is not None else "",
                item.get("relation", ""),
            ])
    return buffer.getvalue()
