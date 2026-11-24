"""Situação editorial de referências: retratações, correções e avisos (M07).

Origem: R11 (Retraction Watch, disponível na API da Crossref desde 2025) e
R08 (Crossref REST API). Plano: Scriptorium V2, módulo M07.

Documentação usada (conferida em 24/11/2026):
- https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/
  (filtro "updates": registros que são atualização do DOI informado)

Duas formas de aviso aparecem no campo "update-to":
1. aviso publicado pela editora: registro próprio (outro DOI) que aponta para a obra;
2. registro do Retraction Watch: o "update-to" fica no próprio registro da obra.

Regra do plano V2: falha de consulta vira "inconclusive", e ausência de aviso
vira "no_notice_found", nunca "nunca foi retratado".
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

CROSSREF_WORKS = "https://api.crossref.org/works"
PROVIDER = "Crossref REST API (inclui dados do Retraction Watch)"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s<>\"{}]+", re.I)
GROUPS = {
    "retraction": "retracted",
    "partial_retraction": "retracted",
    "removal": "retracted",
    "withdrawal": "withdrawn",
    "expression_of_concern": "expression_of_concern",
    "correction": "corrected",
    "erratum": "corrected",
    "corrigendum": "corrected",
}
# Mais grave primeiro.
SEVERITY = ("retracted", "withdrawn", "expression_of_concern", "corrected", "other_update")
ALERT_STATES = {"retracted", "withdrawn", "expression_of_concern"}
LABELS_PT = {
    "retracted": "Retratada",
    "withdrawn": "Retirada pela editora",
    "expression_of_concern": "Expressão de preocupação",
    "corrected": "Corrigida (errata ou correção)",
    "other_update": "Outra atualização editorial",
    "no_notice_found": "Nenhum aviso encontrado na Crossref",
    "inconclusive": "Consulta inconclusiva",
    "not_checked": "Não consultada (sem DOI)",
}


def canonical_doi(value) -> str:
    match = DOI_PATTERN.search(str(value or ""))
    return match.group(0).rstrip(".,;)]}").lower() if match else ""


def _normalize_type(value) -> str:
    return re.sub(r"[\s-]+", "_", str(value or "").strip().lower())


def _date(update: dict) -> str:
    updated = update.get("updated") or {}
    if updated.get("date-time"):
        return str(updated["date-time"])[:10]
    parts = (updated.get("date-parts") or [[]])[0]
    return "-".join(f"{int(p):02d}" if i else str(p) for i, p in enumerate(parts)) if parts else ""


def notices_for(doi: str, records: list[dict]) -> list[dict]:
    """Extrai avisos que apontam para `doi` a partir de registros da Crossref."""
    notices, seen = [], set()
    for record in records or []:
        notice_doi = canonical_doi(record.get("DOI", ""))
        for update in record.get("update-to") or []:
            if not isinstance(update, dict) or canonical_doi(update.get("DOI")) != doi:
                continue
            kind = _normalize_type(update.get("type"))
            entry = {
                "type": kind,
                "group": GROUPS.get(kind, "other_update"),
                "label": str(update.get("label") or kind)[:80],
                "source": str(update.get("source") or "publisher")[:40],
                "date": _date(update),
                # Registro do Retraction Watch fica na própria obra: sem DOI de aviso.
                "notice_doi": notice_doi if notice_doi and notice_doi != doi else None,
            }
            key = (entry["group"], entry["notice_doi"], entry["date"], entry["source"])
            if key not in seen:
                seen.add(key)
                notices.append(entry)
    return notices


def classify(notices: list[dict], query_ok: bool) -> str:
    groups = {n["group"] for n in notices}
    for state in SEVERITY:
        if state in groups:
            return state
    return "no_notice_found" if query_ok else "inconclusive"


def editorial_status(doi: str, session, request, own_record: dict | None = None,
                     user_agent: str = "") -> dict:
    """`request(session, url, params, headers) -> (json|None, "ok"|"not_found"|"unavailable")`."""
    doi = canonical_doi(doi)
    checked_at = datetime.now(timezone.utc).isoformat()
    if not doi:
        return {"editorial_status": "not_checked", "label": LABELS_PT["not_checked"],
                "notices": [], "verified_at": checked_at, "source_provider": PROVIDER}
    records = [own_record] if own_record else []
    data, status = request(session, CROSSREF_WORKS,
                           {"filter": f"updates:{doi}", "rows": 20},
                           {"User-Agent": user_agent} if user_agent else {})
    if status == "ok":
        try:
            records += list((data.get("message") or {}).get("items") or [])
        except AttributeError:
            status = "unavailable"
    notices = notices_for(doi, records)
    state = classify(notices, query_ok=status in ("ok", "not_found"))
    return {
        "editorial_status": state,
        "label": LABELS_PT[state],
        "notices": notices[:10],
        "verified_at": checked_at,
        "source_provider": PROVIDER,
        "query_status": status,
        "query_url": f"{CROSSREF_WORKS}?filter=updates:{quote(doi, safe='/.')}",
    }


def summarize(items: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for item in items:
        state = (item.get("editorial") or {}).get("editorial_status")
        if state:
            counts[state] = counts.get(state, 0) + 1
    return {"counts": counts, "alerts": sum(counts.get(s, 0) for s in ALERT_STATES)}
