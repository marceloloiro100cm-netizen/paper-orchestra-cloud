"""Fatores de contexto das referências (M18) e verificação manual (M24).

Origens: R15 (RA-RAG, POSTECH: confiabilidade como sinal contextual, não
como verdade) como referência de desenho, sem código copiado; R09 (OpenAlex),
R08/R11 (Crossref e Retraction Watch) e R19/R20 (SciELO e BRAPCI).
Plano: Scriptorium V2, módulos M18 "Confiabilidade contextual das fontes" e
M24 "Metadados brasileiros: SciELO e BRAPCI".

Regras do plano respeitadas:
- nenhum escore único: cada sinal fica separado e explicado;
- prestígio da revista ou número de citações não é veracidade;
- preprint válido não é rejeitado; fonte brasileira sem DOI não vira
  "inexistente": recebe links para conferência manual (sem raspagem).

SciELO: DOIs com prefixo 10.1590 são registrados na Crossref e já passam pela
conferência normal (orientação oficial da SciELO sobre DOI).
"""
from __future__ import annotations

from datetime import date
from urllib.parse import quote_plus

VERSION = "source-quality-1"
SCIELO_PREFIX = "10.1590/"
PEER_REVIEWED_TYPES = {"article", "review", "journal-article"}
MANUAL_STATES = {"not_found", "inconclusive", "possible_match", "insufficient_metadata", "metadata_conflict"}


def _openalex_quality(item: dict) -> dict:
    data = (item.get("sources") or {}).get("openalex") or {}
    return data.get("quality") or {} if data.get("status") == "ok" else {}


def quality_factors(item: dict, today: date | None = None) -> dict:
    ref = item.get("reference") or {}
    oa = _openalex_quality(item)
    doc_type, venue_type = oa.get("document_type"), oa.get("venue_type")
    if doc_type == "preprint" or venue_type == "repository":
        review_signal = "preprint_ou_repositorio"
    elif doc_type in PEER_REVIEWED_TYPES and venue_type == "journal":
        review_signal = "periodico_provavelmente_revisado"
    elif doc_type or venue_type:
        review_signal = "outro_tipo"
    else:
        review_signal = "desconhecido"
    year = str(ref.get("year") or "").strip()
    age = (today or date.today()).year - int(year) if year.isdigit() else None
    editorial = (item.get("editorial") or {}).get("editorial_status")
    return {
        "version": VERSION,
        "document_type": doc_type,
        "venue": oa.get("venue") or None,
        "venue_type": venue_type,
        "peer_review_signal": review_signal,
        "retraction_signals": {"crossref_retraction_watch": editorial,
                               "openalex_is_retracted": oa.get("is_retracted")},
        "age_years": age,
        "citations_openalex": oa.get("cited_by_count"),
        "open_access": oa.get("is_oa"),
        "scielo_doi": str(ref.get("doi") or "").lower().startswith(SCIELO_PREFIX),
        "human_assessment": None,
        "note": "Sinais separados, sem nota única. Revista, citações e idade não comprovam veracidade.",
    }


def manual_verification(item: dict) -> dict | None:
    """Links de busca para conferência humana quando as bases globais não bastam."""
    if item.get("classification") not in MANUAL_STATES:
        return None
    ref = item.get("reference") or {}
    title = (ref.get("title") or "").replace("{", "").replace("}", "").strip()
    if not title:
        return {"status": "verificacao_manual_sugerida", "reason": "sem título para buscar", "links": []}
    query = quote_plus(title[:250])
    return {
        "status": "verificacao_manual_sugerida",
        "reason": "Não confirmada nas bases globais; pode ser obra nacional sem DOI ou referência incorreta.",
        "links": [
            {"name": "Google Acadêmico", "url": f"https://scholar.google.com/scholar?q={query}"},
            {"name": "SciELO", "url": f"https://search.scielo.org/?q={query}&lang=pt"},
            {"name": "BRAPCI (buscar pelo título)", "url": "https://brapci.inf.br/"},
        ],
    }
