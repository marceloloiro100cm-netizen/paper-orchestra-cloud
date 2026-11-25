"""Reaproveita a conferência manual de referências em execuções seguintes (M24).

Origem: R19 (SciELO) e R20 (BRAPCI), que pedem conferência manual quando a
obra não tem DOI ou não aparece nas bases; R01 (Scriptorium). Plano V2,
módulo M24 "Metadados brasileiros": "usar o resultado humano na próxima execução".

Quando o pesquisador registra "referência confirmada" ou "referência incorreta"
(coleção research_reviews, somente acréscimo), a API guarda junto o DOI e o
título normalizado da referência. Numa execução seguinte do MESMO pesquisador,
a mesma obra (mesmo DOI ou mesmo título normalizado) recebe essa decisão como
histórico. A decisão não apaga nem substitui a conferência automática: as duas
aparecem lado a lado, com data e pesquisa de origem.
"""
from __future__ import annotations

import re
import unicodedata

DECISIONS = {"referencia_confirmada", "referencia_incorreta"}
MAX_REVIEWS = 2000


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[{}\\]", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def canonical_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value)
    return value


def fingerprint(reference: dict) -> dict:
    """O que a API guarda junto da decisão para reconhecer a obra depois."""
    return {"doi": canonical_doi(reference.get("doi", "")),
            "title_norm": normalize_title(reference.get("title", ""))[:300]}


def load_history(db, owner_uid: str, current_job: str) -> list[dict]:
    """Decisões de referência do pesquisador em OUTRAS pesquisas, da mais antiga à mais nova."""
    docs = (db.collection("research_reviews").where("owner_uid", "==", owner_uid)
            .limit(MAX_REVIEWS).stream())
    rows = []
    for snap in docs:
        review = snap.to_dict() or {}
        if (review.get("target_type") == "reference" and review.get("decision") in DECISIONS
                and review.get("job_id") != current_job and review.get("reference_fingerprint")):
            rows.append(review)
    return sorted(rows, key=lambda r: r.get("at", ""))


def apply_history(report: dict, history: list[dict]) -> dict:
    """Anexa a decisão humana mais recente a cada referência reconhecida."""
    by_doi, by_title = {}, {}
    for review in history:  # em ordem cronológica: a mais recente sobrescreve
        fp = review.get("reference_fingerprint") or {}
        entry = {"decision": review["decision"], "at": review.get("at", ""),
                 "job_id": review.get("job_id", ""), "note": str(review.get("note", ""))[:300]}
        if fp.get("doi"):
            by_doi[fp["doi"]] = entry
        if len(fp.get("title_norm", "")) >= 12:
            by_title[fp["title_norm"]] = entry
    counts = {"confirmadas": 0, "incorretas": 0}
    for item in report.get("items", []):
        ref = item.get("reference") or {}
        fp = fingerprint(ref)
        match = by_doi.get(fp["doi"]) if fp["doi"] else None
        how = "doi"
        if match is None and len(fp["title_norm"]) >= 12:
            match, how = by_title.get(fp["title_norm"]), "titulo"
        if match is None:
            continue
        item["manual_history"] = {**match, "matched_by": how}
        counts["confirmadas" if match["decision"] == "referencia_confirmada" else "incorretas"] += 1
    report["manual_history_summary"] = {
        **counts, "source": "decisões do próprio pesquisador em pesquisas anteriores",
        "note": "Histórico humano mostrado ao lado da conferência automática; não a substitui.",
    }
    return report
