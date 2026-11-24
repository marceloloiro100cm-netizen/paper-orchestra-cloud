"""Diagnóstico das fontes antes da pesquisa (M16, inspirado no GapView).

Origem: R13 (GapView, UC Irvine) como referência de desenho, sem código
copiado; usa a busca de M03/M04 (R06, R43, R44). Plano: Scriptorium V2,
módulo M16 "GapView: diagnóstico pré-pesquisa".

Roda ANTES da geração (modo preflight do worker): mede, para cada pergunta ou
subtópico da ideia, quantos trechos das fontes anexadas parecem tratar dele e
de quantas fontes diferentes. O pesquisador vê as lacunas e decide, no
checkpoint de aprovação (M12), se gera, troca fontes ou descarta, antes de
pagar pela redação.

Regra do plano: baixa cobertura pode ser limitação da busca, não ausência de
literatura. O relatório nunca afirma que algo "não existe".
"""
from __future__ import annotations

import re

from evidence_matrix import find_candidates, is_strong
from lexical_index import LexicalIndex, query_terms

VERSION = "gap-report-1"
MAX_QUESTIONS = 8
TOP_PER_QUESTION = 5


def extract_questions(title: str, idea: str) -> list[dict]:
    """Perguntas explícitas (terminadas em ?) ou, sem elas, frases-chave da ideia."""
    text = re.sub(r"\s+", " ", idea or "")
    questions = [q.strip() for q in re.findall(r"[^.?!]*\?", text) if len(q.split()) >= 4]
    kind = "pergunta"
    if not questions:
        kind = "subtopico"
        questions = [s.strip() for s in re.split(r"(?<=[.!;])\s+", text) if len(s.split()) >= 6][:MAX_QUESTIONS - 1]
    items = [{"kind": "tema_geral", "text": title.strip()}] if title.strip() else []
    items += [{"kind": kind, "text": q[:400]} for q in dict.fromkeys(questions)]
    return items[:MAX_QUESTIONS]


def build_gap_report(title: str, idea: str, chunks: list[dict], sources_meta: dict,
                     source_records: list[dict], vectors: dict | None = None, embedder=None) -> dict:
    questions = extract_questions(title, idea)
    by_id = {c["chunk_id"]: c for c in chunks}
    index = LexicalIndex()
    vector_index, qvectors, embedding_status = None, None, "disabled"
    contribution = {sid: 0 for sid in sources_meta}
    rows = []
    try:
        index.add(chunks)
        if embedder is not None and vectors and questions:
            try:
                from vector_index import VectorIndex
                ids = [cid for cid in by_id if cid in vectors]
                vector_index = VectorIndex(ids, [vectors[i] for i in ids])
                qvectors = embedder.embed([q["text"] for q in questions], "RETRIEVAL_QUERY")
                embedding_status = "completed"
            except Exception as error:
                vector_index, qvectors = None, None
                embedding_status = f"failed_fallback_lexical:{type(error).__name__}"
        for position, question in enumerate(questions):
            qvec = qvectors[position] if qvectors is not None else None
            evidence = find_candidates(question["text"], qvec, index, vector_index, by_id,
                                       sources_meta, top=TOP_PER_QUESTION)
            strong = [e for e in evidence if is_strong(e)]
            covering = sorted({e["source_id"] for e in strong})
            for sid in covering:
                contribution[sid] = contribution.get(sid, 0) + 1
            if len(strong) >= 3 and len(covering) >= 2:
                level = "boa"
            elif strong:
                level = "parcial"
            else:
                level = "lacuna"
            found_terms = set()
            for e in strong:
                found_terms |= set(query_terms(by_id[e["chunk_id"]]["text"], 400))
            missing = [t for t in query_terms(question["text"]) if t not in found_terms][:10]
            rows.append({**question, "coverage": level, "evidence_count": len(strong),
                         "sources_covering": covering, "missing_terms": missing,
                         "evidence": strong[:3]})
    finally:
        index.close()
    counts = {level: sum(r["coverage"] == level for r in rows) for level in ("boa", "parcial", "lacuna")}
    unrelated = [sources_meta[sid]["name"] for sid, n in contribution.items() if n == 0 and sid in sources_meta]
    problems = [{"name": r.get("name"), "status": r.get("status"),
                 "ocr_pages_flagged": r.get("ocr_pages_flagged") or []}
                for r in source_records
                if r.get("status") in ("unreadable", "no_extractable_text") or r.get("ocr_pages_flagged")]
    suggestions = []
    for row in rows:
        if row["coverage"] == "lacuna":
            suggestions.append(f"Sem trechos correspondentes para: \"{row['text'][:120]}\". "
                               f"Considere anexar fontes sobre {', '.join(row['missing_terms'][:5]) or 'este ponto'}.")
        elif row["coverage"] == "parcial" and len(row["sources_covering"]) == 1:
            suggestions.append(f"Apenas uma fonte cobre: \"{row['text'][:120]}\". Considere uma segunda fonte para comparar.")
    if unrelated:
        suggestions.append("Fontes sem relação aparente com as perguntas: " + "; ".join(unrelated) + ".")
    return {
        "version": VERSION, "embeddings": embedding_status,
        "questions": rows, "summary": {"questions": len(rows), **counts,
                                       "sources": len(sources_meta), "chunks": len(chunks)},
        "source_contribution": {sources_meta[s]["name"]: n for s, n in contribution.items() if s in sources_meta},
        "source_problems": problems, "suggestions": suggestions[:12],
        "limitations": [
            "Cobertura medida por busca automática: 'lacuna' pode ser limitação da busca, não ausência de literatura.",
            "O diagnóstico olha só as fontes anexadas; não pesquisa bases externas.",
            "Limiares provisórios, os mesmos da matriz de evidências; serão calibrados com o corpus de referência.",
        ],
    }
