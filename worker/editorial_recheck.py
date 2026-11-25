"""Reavalia retratações e avisos editoriais de um manuscrito antigo (M07).

Origem: R11 (Retraction Watch via Crossref) e R08 (Crossref REST API), as
mesmas consultas de editorial_status.py. Plano V2, módulo M07: "reavaliar ao
reabrir um manuscrito antigo".

Uma obra pode ser retratada, corrigida ou receber expressão de preocupação
depois que o manuscrito foi gerado. Este modo do worker (RESEARCH_MODE=
editorial_recheck) relê reference_verification.json da pesquisa, consulta de
novo só as referências com DOI e grava editorial_recheck.json com o antes e o
depois. Não chama modelo de linguagem, não usa a chave Gemini e não altera o
manuscrito nem a conferência original.
"""
from __future__ import annotations

from datetime import datetime, timezone

VERSION = "editorial-recheck-1"
MAX_DOIS = 60


def _state(editorial: dict | None) -> str:
    return str((editorial or {}).get("editorial_status") or "sem_consulta")


def _unavailable(editorial: dict) -> bool:
    return editorial.get("query_status") == "unavailable" or editorial.get("status") == "unavailable"


def recheck(report: dict, check, max_dois: int = MAX_DOIS) -> dict:
    """`check(doi) -> dict` no formato de editorial_status.editorial_status."""
    rows, changed, skipped = [], 0, 0
    for item in report.get("items", []):
        ref = item.get("reference") or {}
        doi = (ref.get("doi") or "").strip()
        if not doi:
            continue
        if len(rows) >= max_dois:
            skipped += 1
            continue
        before = item.get("editorial") or {}
        try:
            after = check(doi)
        except Exception as error:
            after = {"status": "unavailable", "error": type(error).__name__}
        different = _state(before) != _state(after) and not _unavailable(after)
        changed += different
        rows.append({"key": ref.get("key"), "doi": doi, "title": str(ref.get("title", ""))[:300],
                     "before": before, "after": after, "changed": different})
    alerts = [r for r in rows if r["changed"] or (r["after"].get("notices") or [])]
    return {
        "schema": "scriptorium.editorial_recheck/1", "version": VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "original_checked_at": report.get("checked_at"),
        "summary": {"dois_checked": len(rows), "changed": changed, "with_notices": len(alerts),
                    "skipped_by_limit": skipped},
        "items": rows,
        "limitations": [
            "Só referências com DOI são reconsultadas (Crossref, inclui Retraction Watch).",
            "Ausência de aviso não prova que a obra nunca foi retratada.",
            "O manuscrito e a conferência original não são alterados.",
        ],
    }
