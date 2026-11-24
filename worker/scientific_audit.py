"""Triagem científica determinística: NÃO é revisão por pares nem verificação online.

Sinaliza riscos no manuscrito sem modificar o texto e sem chamar modelos de IA.
Especialmente útil quando o usuário informa que não realizou experimentos.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s{}]+)\s*,", re.IGNORECASE)
LATEX_CITATION = re.compile(
    r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|citealt)\*?"
    r"(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}", re.IGNORECASE
)
PERCENTAGE = re.compile(r"(?<!\w)\d{1,3}(?:[.,]\d+)?\s*%(?!\w)")
NO_EMPIRICAL = re.compile(
    r"(?:nenhum(?:a)?\s+(?:experimento|pesquisa\s+emp[ií]rica))"
    r"|(?:n[aã]o\s+(?:foram\s+realizados?\s+experimentos?|existem\s+resultados\s+emp[ií]ricos))"
    r"|(?:no\s+experiments?\s+(?:were\s+)?(?:performed|conducted))"
    r"|(?:no\s+empirical\s+(?:results|data))",
    re.IGNORECASE,
)
STRONG_VERIFICATION = re.compile(
    r"\b(?:verification\s+oracle|assertion[- ]log\s+mapping|"
    r"latex\s+sanitizer|verifica[cç][aã]o\s+automatizada|"
    r"100\s*%\s+(?:adherence|accuracy|integrity))\b",
    re.IGNORECASE,
)


def _context(text: str, match: re.Match, width: int = 95) -> str:
    start = max(0, match.start() - width)
    end = min(len(text), match.end() + width)
    return " ".join(text[start:end].split())[:220]


def audit_text(pdf_text: str, latex_text: str, bib_text: str, experimental_log: str) -> dict:
    """Returns warning-only findings. Never labels references or claims 'verified'."""
    findings = []
    no_experiments = bool(NO_EMPIRICAL.search(experimental_log))
    percent_matches = list(PERCENTAGE.finditer(pdf_text))
    if no_experiments and percent_matches:
        findings.append({
            "code": "percentages_without_experiments",
            "priority": "high",
            "title": "Percentuais em texto que declara não ter experimentos",
            "detail": "Confira se cada percentual tem uma fonte independente ou pertence a resultado real. A presença não prova invenção.",
            "examples": [_context(pdf_text, x) for x in percent_matches[:6]],
            "count": len(percent_matches),
        })
    elif percent_matches:
        findings.append({
            "code": "percentages_require_sources",
            "priority": "review",
            "title": "Percentuais encontrados",
            "detail": "Verifique origem, método e pertinência de cada percentual antes de divulgar.",
            "examples": [_context(pdf_text, x) for x in percent_matches[:4]],
            "count": len(percent_matches),
        })
    strong_matches = list(STRONG_VERIFICATION.finditer(pdf_text))
    if strong_matches:
        findings.append({
            "code": "verification_claims",
            "priority": "high" if no_experiments else "review",
            "title": "Alegações de mecanismos ou métricas de verificação",
            "detail": "Verifique se o mecanismo citado realmente foi implementado e avaliado. O PaperOrchestra não garante verificação factual.",
            "examples": [_context(pdf_text, x) for x in strong_matches[:5]],
            "count": len(strong_matches),
        })

    bib_keys = set(BIB_ENTRY.findall(bib_text))
    cited_keys = set()
    for cite in LATEX_CITATION.finditer(latex_text):
        cited_keys.update(k.strip() for k in cite.group(1).split(",") if k.strip())
    missing = sorted(cited_keys - bib_keys)
    if missing:
        findings.append({
            "code": "missing_bibliography_keys",
            "priority": "high",
            "title": "Citações sem entrada correspondente no arquivo BibTeX",
            "detail": "O arquivo LaTeX usa chaves que não aparecem em references.bib.",
            "examples": missing[:30],
            "count": len(missing),
        })
    if not bib_keys:
        findings.append({
            "code": "no_bibliography",
            "priority": "review",
            "title": "Nenhuma entrada BibTeX encontrada",
            "detail": "Confira se o artigo deve conter referências e se o arquivo de bibliografia foi produzido.",
            "examples": [], "count": 0,
        })

    return {
        "status": "human_review_required",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scope": "triagem local de texto, citações LaTeX e presença de entradas BibTeX",
        "limitations": [
            "Não consulta bases externas, DOI ou texto integral das referências.",
            "Correspondência de chaves BibTeX não comprova que uma publicação existe.",
            "Não comprova experimentos, originalidade, metodologia ou rigor científico.",
            "Alertas são heurísticos e podem incluir falsos positivos ou omissões.",
        ],
        "input_declares_no_experiments": no_experiments,
        "summary": {
            "percentages_found": len(percent_matches),
            "citation_keys_used": len(cited_keys),
            "bibliography_keys_found": len(bib_keys),
            "citation_keys_missing": len(missing),
            "findings": len(findings),
        },
        "findings": findings,
    }


def audit_pdf(pdf_path: Path, latex_path: Path, bib_path: Path, experimental_log_path: Path) -> dict:
    from pdf_backend import fitz  # PyMuPDF (R37)

    with fitz.open(str(pdf_path)) as doc:
        # Leitura limitada: relatórios extensos também são auditados com custo previsível.
        text = "\n".join(page.get_text("text") for page in list(doc)[:200])
        pages = len(doc)
    report = audit_text(
        text,
        latex_path.read_text(encoding="utf-8", errors="replace") if latex_path.is_file() else "",
        bib_path.read_text(encoding="utf-8", errors="replace") if bib_path.is_file() else "",
        experimental_log_path.read_text(encoding="utf-8", errors="replace"),
    )
    report["pages"] = pages
    if pages > 200:
        report["limitations"].append("A extração de texto foi limitada às primeiras 200 páginas.")
    return report
