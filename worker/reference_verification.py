"""Conferência bibliográfica não conclusiva, com fontes acadêmicas públicas.

Consulta Crossref, OpenAlex e Semantic Scholar (sem LLM). Não afirma
que uma referência é verdadeira ou que a obra sustenta o argumento citado.
Todos os endpoints são fixos; nunca executa URLs fornecidas pelo manuscrito.
"""
from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import quote

import requests

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s<>\"{}]+", re.I)
ENTRY_START = re.compile(r"@([A-Za-z]+)\s*[{(]\s*([^,\s{}()]+)\s*,", re.I)
PROVIDERS = ("crossref", "openalex", "semantic_scholar")
MAX_REFERENCES = 20
USER_AGENT = "PaperOrchestraAcademic/0.2 (https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud)"


def _balanced(text: str, pos: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    """Lê campo aninhado de BibTeX até chave correspondente."""
    if pos >= len(text) or text[pos] != opening:
        return "", pos
    depth = 1
    i = pos + 1
    start = i
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], len(text)


def _fields(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    i = 0
    while i < len(body):
        while i < len(body) and body[i] in ", \n\t\r":
            i += 1
        match = re.match(r"[A-Za-z][A-Za-z0-9_-]*\s*=", body[i:])
        if not match:
            # Recuperação segura para texto de referência não canônico.
            comma = body.find(",", i)
            i = len(body) if comma == -1 else comma + 1
            continue
        key = match.group().split("=")[0].strip().lower()
        i += match.end()
        while i < len(body) and body[i].isspace():
            i += 1
        if i < len(body) and body[i] == "{":
            value, i = _balanced(body, i)
        elif i < len(body) and body[i] == '"':
            i += 1
            start = i
            while i < len(body):
                if body[i] == "\\" and i + 1 < len(body):
                    i += 2
                elif body[i] == '"':
                    break
                else:
                    i += 1
            value = body[start:i]
            i += 1
        else:
            start = i
            while i < len(body) and body[i] not in ",\r\n":
                i += 1
            value = body[start:i].strip()
        out[key] = value.strip()
    return out


def parse_bibtex(text: str) -> list[dict]:
    results = []
    for match in ENTRY_START.finditer(text):
        kind, key = match.group(1).lower(), match.group(2)
        if kind in {"comment", "string", "preamble"}:
            continue
        opener = "{" if text[match.start():match.end()].count("{") else "("
        content, _ = _balanced(text, match.end() - 1, opener, "}" if opener == "{" else ")")
        # match ends immediately after comma; find a balanced body by scanning from
        # the original entry's opening brace, not from the citation key.
        open_pos = text.find(opener, match.start(), match.end())
        if open_pos >= 0:
            full, _ = _balanced(text, open_pos, opener, "}" if opener == "{" else ")")
            body = full[len(key):].lstrip(" \t\r\n,")
        else:
            body = content
        fields = _fields(body)
        if not fields:
            continue
        doi = canonical_doi(fields.get("doi") or fields.get("url") or fields.get("note") or "")
        results.append({
            "key": key, "entry_type": kind,
            "title": fields.get("title", ""),
            "year": fields.get("year", ""),
            "authors": fields.get("author", ""),
            "doi": doi,
        })
    return results


def canonical_doi(value: str) -> str:
    m = DOI_PATTERN.search(str(value or ""))
    return m.group(0).rstrip(".,;)]}").lower() if m else ""


def clean_title(value: str) -> str:
    value = re.sub(r"[{}\\]", "", value or "")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def similarity(a: str, b: str) -> float:
    aa, bb = clean_title(a), clean_title(b)
    return SequenceMatcher(None, aa, bb).ratio() if aa and bb else 0.0


def _request(session, url: str, params: dict | None = None, headers: dict | None = None):
    try:
        response = session.get(
            url, params=params, headers=headers or {}, timeout=(3, 7),
            allow_redirects=False,
        )
        if response.status_code in (404, 410):
            return None, "not_found"
        if response.status_code != 200:
            return None, "unavailable"
        return response.json(), "ok"
    except (requests.RequestException, ValueError):
        return None, "unavailable"


def _crossref(entry, session):
    doi = entry["doi"]
    url = "https://api.crossref.org/works"
    params = {"query.bibliographic": entry["title"], "rows": 1}
    if doi:
        url += "/" + quote(doi, safe="")
        params = None
    data, status = _request(session, url, params=params, headers={"User-Agent": USER_AGENT})
    if status != "ok":
        return {"status": status}
    try:
        result = data.get("message", {})
        if not doi:
            result = result["items"][0]
        return {"status": "ok", "title": (result.get("title") or [""])[0],
                "year": str((result.get("issued") or {}).get("date-parts", [[""]])[0][0]),
                "doi": canonical_doi(result.get("DOI", "")),
                "url": "https://doi.org/" + canonical_doi(result.get("DOI", ""))
                if canonical_doi(result.get("DOI", "")) else ""}
    except (KeyError, IndexError, ValueError, TypeError):
        return {"status": "unavailable"}


def _openalex(entry, session):
    doi = entry["doi"]
    url = "https://api.openalex.org/works"
    params = {"search": entry["title"], "per_page": 1}
    if doi:
        url += "/doi:" + quote(doi, safe="")
        params = None
    key = os.getenv("OPENALEX_API_KEY")
    if key:
        params = dict(params or {})
        params["api_key"] = key
    data, status = _request(session, url, params=params, headers={"User-Agent": USER_AGENT})
    if status != "ok":
        return {"status": status}
    try:
        result = data if doi else data["results"][0]
        result_doi = canonical_doi(result.get("doi", ""))
        return {"status": "ok", "title": result.get("title") or result.get("display_name") or "",
                "year": str(result.get("publication_year", "")),
                "doi": result_doi, "url": str(result.get("id", ""))[:250]}
    except (KeyError, IndexError, TypeError):
        return {"status": "unavailable"}


def _semantic_scholar(entry, session):
    doi = entry["doi"]
    url = "https://api.semanticscholar.org/graph/v1/paper"
    params = {"fields": "title,year,externalIds,url"}
    if doi:
        url += "/DOI:" + quote(doi, safe="")
    else:
        url += "/search"
        params.update({"query": entry["title"], "limit": 1})
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    headers = {"User-Agent": USER_AGENT}
    if key:
        headers["x-api-key"] = key
    data, status = _request(session, url, params=params, headers=headers)
    if status != "ok":
        return {"status": status}
    try:
        result = data if doi else data["data"][0]
        ids = result.get("externalIds") or {}
        return {"status": "ok", "title": result.get("title") or "",
                "year": str(result.get("year") or ""),
                "doi": canonical_doi(ids.get("DOI", "")),
                "url": str(result.get("url", ""))[:250]}
    except (KeyError, IndexError, TypeError):
        return {"status": "unavailable"}


def classify(entry: dict, sources: dict) -> dict:
    confirmations = []
    discrepancies = []
    possible = []
    for provider, result in sources.items():
        if result["status"] != "ok":
            continue
        title_score = similarity(entry.get("title", ""), result.get("title", ""))
        doi_match = bool(entry.get("doi") and entry["doi"] == result.get("doi"))
        year_a = str(entry.get("year", "")).strip()
        year_b = str(result.get("year", "")).strip()
        year_conflict = bool(year_a and year_b and year_a != year_b)
        if doi_match:
            if title_score < 0.75 and entry.get("title") or year_conflict:
                discrepancies.append(provider)
            else:
                confirmations.append(provider)
        elif title_score >= 0.9:
            possible.append(provider)
    if discrepancies:
        state = "metadata_conflict"
    elif confirmations:
        state = "metadata_match"
    elif possible:
        state = "possible_match"
    elif any(x["status"] == "unavailable" for x in sources.values()):
        state = "inconclusive"
    else:
        state = "not_found"
    return {"classification": state, "confirmed_by": confirmations,
            "discrepant_sources": discrepancies, "possible_sources": possible}


def verify_bibliography(bib_text: str, max_references: int = MAX_REFERENCES,
                        session=None, pause: bool = True) -> dict:
    entries = parse_bibtex(bib_text)
    session = session or requests.Session()
    results = []
    limit = min(max(0, max_references), MAX_REFERENCES)
    for entry in entries[:limit]:
        if not entry["doi"] and not entry["title"].strip():
            results.append({"reference": entry, "classification": "insufficient_metadata",
                            "sources": {}})
            continue
        sources = {"crossref": _crossref(entry, session),
                   "openalex": _openalex(entry, session)}
        # Semantic Scholar possui limite de requisições menor; se não houver
        # chave, 429 não vira alegação de "referência inexistente".
        if pause and results:
            time.sleep(1.1)
        sources["semantic_scholar"] = _semantic_scholar(entry, session)
        results.append({"reference": entry, "sources": sources,
                        **classify(entry, sources)})
    return {
        "status": "completed_with_limitations",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": list(PROVIDERS),
        "checked": len(results),
        "skipped_by_limit": max(0, len(entries) - limit),
        "total_bibtex_entries": len(entries),
        "items": results,
        "limitations": [
            "Metadados encontrados não comprovam que as fontes sustentam as afirmações do artigo.",
            "Correspondência de DOI/título não verifica texto integral, autores, retratações ou rigor científico.",
            "APIs podem impor limites; indisponibilidade não significa referência inventada.",
            "Classificação heurística: casos conflitantes ou prováveis exigem conferência humana.",
            "A consulta foi limitada para controlar uso de rede e processamento.",
        ],
    }
