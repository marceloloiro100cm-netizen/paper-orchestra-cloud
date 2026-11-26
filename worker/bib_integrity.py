"""Integridade da bibliografia do manuscrito (achado do confronto de 25/11/2026).

Origem: R01 (Scriptorium); metadados por DOI e busca por título no OpenAlex
(R09). Plano V2, módulos M05 e M14.

Problemas que este módulo corrige:
1. O agente de refinamento pode escrever referências DENTRO do .tex (bloco
   filecontents). Elas escapavam da conferência, que só lia references.bib.
   Agora os blocos são extraídos, juntados ao references.bib e conferidos.
2. O modelo inventava autor, título e periódico até de fontes anexadas.
   Agora as fontes anexadas ganham BibTeX oficial (DOI/OpenAlex ou, sem
   correspondência segura, só o que o próprio arquivo diz) ANTES da redação,
   e depois a entrada do manuscrito que corresponde a uma fonte anexada é
   substituída pelos dados oficiais, mantendo a chave de citação.
3. Valores de enchimento ("Revista X", "Universidade Federal") viram alerta.

Nada aqui inventa dado: o que não tem fonte segura fica marcado para
conferência humana.
"""
from __future__ import annotations

import re
import subprocess
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from reference_verification import _balanced, _fields, canonical_doi, clean_title, similarity

ENTRY_START = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s{}()]+)\s*,", re.I)
FILECONTENTS = re.compile(
    r"\\begin\{filecontents\*?\}(?:\[[^\]]*\])?\s*\{([^}]+)\}(.*?)\\end\{filecontents\*?\}", re.S)
FIELD_ORDER = ("author", "title", "journal", "booktitle", "school", "publisher", "address",
               "year", "volume", "number", "pages", "doi", "url", "note")
PLACEHOLDER = re.compile(
    r"^(revista x|journal x|revista y|universidade federal|anais do (congresso|simp[oó]sio)"
    r"( de educa[cç][aã]o)?|revista de educa[cç][aã]o|revista de tecnologia|journal of education"
    r"|autor desconhecido|unknown|n/?a|s\.?\s?n\.?|xxx+|tbd)$", re.I)
TITLE_MATCH = 0.86
VERSION = "bib-integrity-3"

# Mesma tabela de api/mcp_flow.py (tests/test_mcp_jobs.py impede divergência):
# só DOI registrado, concordância de 2 bases, ficha confirmada ou conferência
# humana/no documento confirmam uma referência.
REF_LEVELS = {
    "doi": "confirmada",
    "corrigida_pelo_texto": "confirmada",
    "confirmada_pelo_pesquisador": "confirmada",
    "confirmada_duas_fontes": "confirmada",
    "ficha_da_biblioteca": "confirmada",
    "doi_no_texto": "sugerida",
    "texto_do_pdf": "sugerida",
    "titulo_do_pdf": "sugerida",
    "crossref": "sugerida",
    "oasisbr": "sugerida",
    "proposta_ia": "sugerida",
    "arquivo": "a_conferir",
}


def ref_level(entry: dict) -> str:
    return REF_LEVELS.get((entry or {}).get("how") or "", "a_conferir")


class LookupLog:
    """Registra o que aconteceu com as consultas ao OpenAlex de uma fonte.

    Achado de 25/11/2026: qualquer erro (inclusive a API recusando a chamada sem
    chave, exigida desde 13/02/2026) virava "sem correspondência", e não dava para
    saber se a fonte não existia na base ou se a consulta nem tinha sido feita.
    """

    def __init__(self, get_json):
        self.get_json, self.calls, self.refused, self.errors = get_json, 0, 0, []

    def __call__(self, url: str):
        self.calls += 1
        try:
            return self.get_json(url)
        except Exception as exc:  # noqa: BLE001 - registrado e devolvido como "sem resposta"
            self.refused += 1
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self.errors.append(f"{type(exc).__name__}{f' {status}' if status else ''}")
            return None

    def status(self, found: bool) -> str:
        if found:
            return "ok"
        if self.calls and self.refused == self.calls:
            return "api_recusou"
        if self.refused:
            return "parcial"
        return "sem_resultado" if self.calls else "sem_consulta"


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


def parse_entries(text: str) -> list[dict]:
    """Entradas completas (todos os campos), na ordem do arquivo."""
    out = []
    for match in ENTRY_START.finditer(text or ""):
        kind, key = match.group(1).lower(), match.group(2)
        if kind in {"comment", "string", "preamble"}:
            continue
        start = text.find("{", match.start())
        full, _ = _balanced(text, start, "{", "}")
        body = full[len(key):].lstrip(" \t\r\n,")
        fields = {k.lower(): v for k, v in _fields(body).items()}
        if fields:
            out.append({"type": kind, "key": key, "fields": fields})
    return out


def render(entry: dict) -> str:
    fields = entry["fields"]
    names = [k for k in FIELD_ORDER if fields.get(k)] + sorted(
        k for k in fields if k not in FIELD_ORDER and fields.get(k))
    body = ",\n".join(f"  {k} = {{{fields[k]}}}" for k in names)
    return f"@{entry['type']}{{{entry['key']},\n{body}\n}}\n"


def extract_inline(tex: str) -> tuple[str, str, list[str]]:
    """(BibTeX dos blocos filecontents .bib, .tex sem esses blocos, nomes dos arquivos)."""
    found, names = [], []

    def drop(match):
        name = match.group(1).strip()
        if name.lower().endswith(".bib"):
            found.append(match.group(2))
            names.append(name)
            return "% Bibliografia movida para references.bib pela conferência do Scriptorium.\n"
        return match.group(0)

    cleaned = FILECONTENTS.sub(drop, tex or "")
    return "\n".join(found), cleaned, names


def surname(author_field: str) -> str:
    first = re.split(r"\s+and\s+", author_field or "", maxsplit=1)[0].strip()
    if "," in first:
        first = first.split(",", 1)[0]
    else:
        first = first.split()[-1] if first.split() else ""
    return re.sub(r"[^a-z]", "", fold(re.sub(r"[{}\\]", "", first)))


# ---------------------------------------------------------- fontes anexadas
def _authors_bibtex(authorships: list) -> str:
    names = []
    for item in authorships or []:
        name = ((item or {}).get("author") or {}).get("display_name") or ""
        parts = name.split()
        if len(parts) >= 2:
            names.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
        elif parts:
            names.append(parts[0])
    return " and ".join(names[:12])


def entry_from_openalex(work: dict, key: str) -> dict:
    biblio = work.get("biblio") or {}
    venue = (((work.get("primary_location") or {}).get("source")) or {}).get("display_name") or ""
    kind = {"article": "article", "dissertation": "phdthesis", "book": "book",
            "book-chapter": "incollection", "proceedings-article": "inproceedings"}.get(
        work.get("type") or "", "misc")
    fields = {"author": _authors_bibtex(work.get("authorships")), "title": work.get("title") or "",
              "year": str(work.get("publication_year") or ""), "doi": canonical_doi(work.get("doi") or "")}
    if kind == "inproceedings" and venue:
        fields["booktitle"] = venue
    elif kind == "phdthesis":
        # Em teses, a "fonte" do OpenAlex costuma ser o repositório agregador, não a
        # universidade: melhor deixar em branco para conferência do que errar.
        pass
    elif venue:
        fields["journal"] = venue
    if biblio.get("volume"):
        fields["volume"] = str(biblio["volume"])
    if biblio.get("issue"):
        fields["number"] = str(biblio["issue"])
    if biblio.get("first_page"):
        last = biblio.get("last_page")
        fields["pages"] = f"{biblio['first_page']}--{last}" if last else str(biblio["first_page"])
    return {"type": kind, "key": key, "fields": {k: v for k, v in fields.items() if v}}


KEY_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "sobre", "entre",
    "que", "como", "mais", "menos", "muito", "eles", "elas", "este", "esta", "esse", "essa",
    "the", "of", "and", "to", "in", "for", "on", "with", "by", "an", "at", "from", "into",
    "using", "towards", "toward", "study", "analysis", "review", "estudo", "analise",
}


def _first_title_word(title: str) -> str:
    words = re.findall(r"[a-z]{3,}", fold(title or ""))
    for w in words:
        if w not in KEY_STOPWORDS and len(w) >= 4:
            return w[:16]
    for w in words:
        if w not in KEY_STOPWORDS:
            return w[:16]
    return words[0][:16] if words else ""


def _key_for(fields: dict, used: set) -> str:
    """Chave legível e estável: sobrenome + ano + primeira palavra forte do título (nunca 'fonte')."""
    who = surname(fields.get("author", ""))
    year = re.sub(r"[^0-9]", "", str(fields.get("year") or ""))[:4]
    word = _first_title_word(fields.get("title", ""))
    if who:
        base = f"{who}{year}{word}"
    elif word:
        base = f"{word}{year}"
    else:
        base = f"doc{year or 'ref'}"
    base = re.sub(r"[^a-z0-9]", "", base) or "docref"
    if base[0].isdigit():
        base = "ref" + base
    key, n = base, 2
    while key in used:
        key, n = f"{base}_{n}", n + 1
    used.add(key)
    return key


def entry_from_crossref(item: dict, key: str) -> dict:
    """Converte registro da Crossref REST API (R08) em entrada BibTeX."""
    authors = []
    for a in (item.get("author") or [])[:12]:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        if family and given:
            authors.append(f"{family}, {given}")
        elif family:
            authors.append(family)
        elif a.get("name"):
            authors.append(str(a["name"]).strip())
    title = ((item.get("title") or [""])[0] or "").strip()
    year = ""
    for k in ("published-print", "published-online", "issued", "created"):
        parts = ((item.get(k) or {}).get("date-parts") or [[]])[0]
        if parts and str(parts[0]).isdigit():
            year = str(parts[0])
            break
    venue = ((item.get("container-title") or [""])[0] or "").strip()
    raw_type = item.get("type") or ""
    kind = {"journal-article": "article", "proceedings-article": "inproceedings",
            "book-chapter": "incollection", "book": "book", "dissertation": "phdthesis",
            "report": "techreport"}.get(raw_type, "misc")
    fields = {"author": " and ".join(authors), "title": title, "year": year,
              "doi": canonical_doi(item.get("DOI") or "")}
    if kind in ("inproceedings", "incollection") and venue:
        fields["booktitle"] = venue
    elif kind == "article" and venue:
        fields["journal"] = venue
    elif kind == "book" and item.get("publisher"):
        fields["publisher"] = str(item["publisher"]).strip()
    if item.get("volume"):
        fields["volume"] = str(item["volume"])
    if item.get("issue"):
        fields["number"] = str(item["issue"])
    if item.get("page"):
        fields["pages"] = str(item["page"]).replace("-", "--")
    return {"type": kind, "key": key, "fields": {k: v for k, v in fields.items() if v}}


def entry_from_oasisbr(record: dict, key: str) -> dict:
    """Converte registro da BDTD / Oasisbr (IBICT) em entrada BibTeX."""
    title = str(record.get("title") or "").strip()
    if isinstance(record.get("title"), list):
        title = str((record.get("title") or [""])[0]).strip()
    raw_authors = record.get("authors") or record.get("author") or []
    authors = []
    if isinstance(raw_authors, dict):
        for group in ("primary", "secondary"):
            if isinstance(raw_authors.get(group), dict):
                authors.extend(raw_authors[group].keys())
            elif isinstance(raw_authors.get(group), list):
                authors.extend(str(a) for a in raw_authors[group])
    elif isinstance(raw_authors, list):
        authors = [str(a).strip() for a in raw_authors if str(a).strip()]
    elif isinstance(raw_authors, str) and raw_authors.strip():
        authors = [raw_authors.strip()]
    year = ""
    for y in (record.get("publicationDates") or [record.get("year") or ""]):
        m = re.search(r"(1[89]|20)\d{2}", str(y or ""))
        if m:
            year = m.group(0)
            break
    formats = " ".join(str(f).lower() for f in (record.get("formats") or []))
    if "master" in formats or "disserta" in formats:
        kind = "mastersthesis"
    elif "doctoral" in formats or "tese" in formats or "phd" in formats:
        kind = "phdthesis"
    elif "article" in formats or "artigo" in formats:
        kind = "article"
    else:
        kind = "misc"
    inst = ""
    publishers = record.get("publishers") or record.get("institution") or []
    if isinstance(publishers, list) and publishers:
        inst = str(publishers[0]).strip()
    elif isinstance(publishers, str):
        inst = publishers.strip()
    fields = {"author": " and ".join(authors[:12]), "title": title, "year": year}
    if inst and kind in ("mastersthesis", "phdthesis"):
        fields["school"] = inst
    elif inst and kind == "article":
        fields["journal"] = inst
    return {"type": kind, "key": key, "fields": {k: v for k, v in fields.items() if v}}


def _entry_confirmed_by_text(entry: dict, text: str) -> bool:
    fields = entry.get("fields") or {}
    title = _plain(fields.get("title") or "")
    author = fields.get("author") or ""
    if len(title) < 25 or len(title.split()) < 5 or not author:
        return False
    surnames = []
    for part in re.split(r"\s+and\s+", author):
        if INSTITUTION.search(part):
            continue
        sn = surname(part)
        if len(sn) >= 3:
            surnames.append(sn)
    if not surnames:
        return False
    plain = " " + _plain(text) + " "
    if not any(f" {sn} " in plain for sn in surnames):
        return False
    if title in plain:
        return True
    return any(similarity(line, title) >= TITLE_MATCH for line in (text or "").splitlines()
               if 12 <= len(line.strip()) <= 300)


def sources_agree(a: dict | None, b: dict | None) -> bool:
    """Item 8: confirmar automaticamente só quando 2 bases independentes concordam em título, sobrenome e ano."""
    if not a or not b:
        return False
    fa, fb = a.get("fields") or {}, b.get("fields") or {}
    ta, tb = fa.get("title") or "", fb.get("title") or ""
    sa, sb = surname(fa.get("author", "")), surname(fb.get("author", ""))
    ya, yb = str(fa.get("year") or "").strip(), str(fb.get("year") or "").strip()
    return bool(ta and tb and sa and sb and ya and yb and sa == sb and ya == yb
                and similarity(ta, tb) >= TITLE_MATCH)


# Confirmação pelo próprio documento (achado do teste MCP de 25/11/2026): sem
# DOI, a busca por título no OpenAlex aceitava registros sem autor ou de outra
# edição (Prensky 2001 saiu como 2012, sem autor). Agora um registro só vale se
# o título E o sobrenome de um autor aparecem nas primeiras páginas do arquivo.
def _plain(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", fold(text or "")))


INSTITUTION = re.compile(r"universit|universidad|department|departamento|faculdade|faculty|instituto|"
                         r"institute|college|school|science|centro|center|library|biblioteca|repositor", re.I)


def _work_surnames(work: dict) -> list[str]:
    """Sobrenomes de pessoas; autoria institucional ("Department of ...") não conta."""
    out = []
    for item in work.get("authorships") or []:
        name = ((item or {}).get("author") or {}).get("display_name") or ""
        if INSTITUTION.search(name):
            continue
        parts = _plain(name).split()
        if parts:
            out.append(parts[-1])
    return out


def confirmed_by_text(work: dict, text: str) -> bool:
    """Título no texto (ou numa linha quase idêntica, ex.: "Part 1") e um sobrenome de autor."""
    plain = " " + _plain(text) + " "
    title = _plain(work.get("title") or "")
    surnames = _work_surnames(work)
    # Títulos genéricos ("Department of Computer Science") aparecem em qualquer texto.
    if len(title) < 25 or len(title.split()) < 5 or not surnames:
        return False
    if not any(len(s) >= 3 and f" {s} " in plain for s in surnames):
        return False
    if title in plain:
        return True
    return any(similarity(line, title) >= TITLE_MATCH for line in (text or "").splitlines()
               if 12 <= len(line.strip()) <= 300)


def dois_in_text(text: str) -> list[str]:
    found = []
    for match in re.finditer(r"10\.\d{4,9}/[^\s\"<>,;]+", text or "", flags=re.I):
        doi = canonical_doi(match.group(0))
        if doi and doi not in found:
            found.append(doi)
    return found[:5]


NOISE = re.compile(r"https?:|www\.|doi|issn|isbn|e-?mail|@|revista|vol\.|v\.\s*\d|n\.\s*\d|p\.\s*\d|"
                   r"universidade|university|programa de p|faculdade|instituto|departamento|"
                   r"recebido|aprovado|submetido|copyright|licen", re.I)


def title_candidates(source: dict, meta: dict, text: str) -> list[str]:
    """Consultas de título: metadado do PDF, nome do arquivo e linhas longas do início."""
    out = []
    if meta.get("pdf_title") and len(meta["pdf_title"]) > 15:
        out.append(meta["pdf_title"])
    stem = re.sub(r"\.(pdf|docx|txt)$", "", source.get("name") or "", flags=re.I)
    stem = re.sub(r"\([^)]*\)", " ", stem)
    if len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", stem)) >= 4:
        out.append(stem)
    for line in (text or "").splitlines():
        line = " ".join(line.split())
        if 25 <= len(line) <= 220 and not NOISE.search(line) and len(line.split()) >= 4:
            out.append(line)
        if len(out) >= 5:
            break
    seen, unique = set(), []
    for item in out:
        key = clean_title(item)[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:4]


def _plausible_author(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and len(value) >= 5 and " " in value and not re.search(
        r"user|admin|microsoft|word|owner|autor|author|computer|pc\b|\d", value, re.I)


def first_pages_text(payload: dict, pages: int = 3, limit: int = 12000) -> str:
    """Texto das primeiras páginas de um documento derivado (capa, título, autoria, DOI)."""
    chunks = (payload or {}).get("chunks") or []
    early = [c.get("text", "") for c in chunks if (c.get("pages") or [1])[0] <= pages]
    text = "\n".join(early) if early else "\n".join(c.get("text", "") for c in chunks[:12])
    return text[:limit]


def _cached_fetcher(fn):
    """Onda 1 (G5): evita repetir a mesma URL HTTP entre fontes no mesmo job."""
    if fn is None:
        return None
    lock = threading.Lock()
    cache: dict[str, tuple[bool, object]] = {}

    def wrapped(url: str):
        with lock:
            hit = cache.get(url)
        if hit is not None:
            ok, value = hit
            if ok:
                return value
            raise value
        try:
            res = fn(url)
        except Exception as exc:
            with lock:
                cache[url] = (False, exc)
            raise
        with lock:
            cache[url] = (True, res)
        return res

    return wrapped


def _resolve_one_source(source: dict, get_json, meta: dict, text: str,
                        crossref_get=None, oasisbr_get=None, card=None) -> dict:
    """Resolve uma fonte de forma independente (thread-safe; chave atribuída depois em ordem)."""
    sid = source.get("id")
    # Item 6: ficha já confirmada na biblioteca vale para todos os projetos.
    if isinstance(card, dict) and ref_level(card) == "confirmada" and (card.get("fields") or {}).get("title"):
        return {
            "inherited": True,
            "preferred_key": card.get("key") or "",
            "type": card.get("type") or "misc",
            "fields": dict(card["fields"]),
            "source_id": sid,
            "how": "ficha_da_biblioteca",
            "consulta": {"status": "ficha_confirmada", "chamadas": 0, "erros": []},
        }

    origin = source.get("origin") or {}
    entry, how = None, ""
    doi = canonical_doi(origin.get("doi") or "")
    lookup = LookupLog(get_json)
    get = lookup
    cr_lookup = LookupLog(crossref_get) if crossref_get else None
    oa_entry, cr_entry, ob_entry = None, None, None
    try:
        if doi:
            work = get("https://api.openalex.org/works/doi:" + doi)
            if work and work.get("title"):
                oa_entry = entry_from_openalex(work, "")
                entry, how = oa_entry, "doi"
            elif cr_lookup:
                cr_raw = cr_lookup("https://api.crossref.org/works/" + doi)
                cr_msg = (cr_raw or {}).get("message") if isinstance(cr_raw, dict) else None
                if cr_msg and (cr_msg.get("title") or [""])[0]:
                    cr_entry = entry_from_crossref(cr_msg, "")
                    entry, how = cr_entry, "doi"
        if not entry and text:
            for found in dois_in_text(text):
                candidate = get("https://api.openalex.org/works/doi:" + found)
                if candidate and confirmed_by_text(candidate, text):
                    oa_entry = entry_from_openalex(candidate, "")
                    entry, how = oa_entry, "doi_no_texto"
                    if cr_lookup:
                        cr_raw = cr_lookup("https://api.crossref.org/works/" + found)
                        cr_msg = (cr_raw or {}).get("message") if isinstance(cr_raw, dict) else None
                        if cr_msg and (cr_msg.get("title") or [""])[0]:
                            cand_cr = entry_from_crossref(cr_msg, "")
                            if sources_agree(oa_entry, cand_cr):
                                how = "confirmada_duas_fontes"
                    break
        if not entry:
            queries = title_candidates(source, meta, text)
            # 3a. OpenAlex
            for query in queries:
                found = get("https://api.openalex.org/works?per-page=5&search="
                            + re.sub(r"\s+", "+", clean_title(query)))
                results = (found or {}).get("results", [])
                if text:
                    ok = [c for c in results if confirmed_by_text(c, text)]
                else:
                    ok = [c for c in results if c.get("authorships")
                          and similarity(c.get("title") or "", query) >= TITLE_MATCH]
                if ok:
                    ok.sort(key=lambda c: (-similarity(c.get("title") or "", query),
                                           c.get("publication_year") or 9999))
                    oa_entry = entry_from_openalex(ok[0], "")
                    break
            # 3b. Crossref (segunda opinião para confirmar ou fallback se OpenAlex falhar)
            if cr_lookup and queries:
                for query in queries[:2]:
                    cr_raw = cr_lookup("https://api.crossref.org/works?rows=5&query.bibliographic="
                                       + re.sub(r"\s+", "+", clean_title(query)))
                    items = ((cr_raw or {}).get("message") or {}).get("items", []) if isinstance(cr_raw, dict) else []
                    cands = [entry_from_crossref(it, "") for it in items]
                    if text:
                        ok_cr = [c for c in cands if _entry_confirmed_by_text(c, text)]
                    else:
                        ok_cr = [c for c in cands if c["fields"].get("author")
                                 and similarity(c["fields"].get("title", ""), query) >= TITLE_MATCH]
                    if ok_cr:
                        ok_cr.sort(key=lambda c: -similarity(c["fields"].get("title", ""), query))
                        cr_entry = ok_cr[0]
                        break
            # 3c. BDTD / Oasisbr (IBICT) — teses e dissertações brasileiras
            if oasisbr_get and queries and not (oa_entry and cr_entry and sources_agree(oa_entry, cr_entry)):
                for query in queries[:2]:
                    try:
                        ob_raw = oasisbr_get(
                            "https://oasisbr.ibict.br/vufind/api/v1/search?type=Title&limit=5&lookfor="
                            + re.sub(r"\s+", "+", clean_title(query)))
                    except Exception:
                        ob_raw = None
                    records = (ob_raw or {}).get("records", []) if isinstance(ob_raw, dict) else []
                    cands = [entry_from_oasisbr(rec, "") for rec in records]
                    if text:
                        ok_ob = [c for c in cands if _entry_confirmed_by_text(c, text)]
                    else:
                        ok_ob = [c for c in cands if c["fields"].get("author")
                                 and similarity(c["fields"].get("title", ""), query) >= TITLE_MATCH]
                    if ok_ob:
                        ok_ob.sort(key=lambda c: -similarity(c["fields"].get("title", ""), query))
                        ob_entry = ok_ob[0]
                        break
            # Decisão da cascata (Item 8): 2 fontes concordantes => confirmada_duas_fontes
            if oa_entry and cr_entry and sources_agree(oa_entry, cr_entry):
                entry, how = oa_entry, "confirmada_duas_fontes"
            elif oa_entry and ob_entry and sources_agree(oa_entry, ob_entry):
                entry, how = oa_entry, "confirmada_duas_fontes"
            elif cr_entry and ob_entry and sources_agree(cr_entry, ob_entry):
                entry, how = cr_entry, "confirmada_duas_fontes"
            elif oa_entry:
                entry, how = oa_entry, ("texto_do_pdf" if text else "titulo_do_pdf")
            elif cr_entry:
                entry, how = cr_entry, "crossref"
            elif ob_entry:
                entry, how = ob_entry, "oasisbr"
    except Exception:
        entry = None
    if entry and (entry.get("fields") or {}).get("title"):
        result = {"type": entry["type"], "fields": dict(entry["fields"]), "how": how}
    else:
        stem = re.sub(r"\.(pdf|docx|txt)$", "", source.get("name") or "", flags=re.I)
        title = meta.get("pdf_title") if len(meta.get("pdf_title") or "") > 15 else stem
        why = ("o OpenAlex recusou a consulta" if lookup.status(False) == "api_recusou"
               else "sem correspondência segura nas bases")
        result = {"type": "misc", "fields": {"title": title, "note": f"metadados a conferir: {why}"},
                  "how": "arquivo"}
    result["source_id"] = sid
    result["consulta"] = {"status": lookup.status(result["how"] != "arquivo"), "chamadas": lookup.calls,
                          "erros": lookup.errors[:3]}
    return result


def library_entries(sources: list[dict], get_json, pdf_meta=None, texts=None, *,
                    crossref_get=None, oasisbr_get=None, library_cards=None,
                    max_workers: int = 4) -> list[dict]:
    """BibTeX oficial das fontes anexadas (cascata P1 itens 6 e 8 + paralelismo Onda 1 G5)."""
    if not sources:
        return []
    cached_oa = _cached_fetcher(get_json)
    cached_cr = _cached_fetcher(crossref_get)
    cached_ob = _cached_fetcher(oasisbr_get)

    def task(src: dict) -> dict:
        sid = src.get("id")
        card = (library_cards or {}).get(sid) or src.get("bib_entry")
        return _resolve_one_source(
            src, cached_oa, (pdf_meta or {}).get(sid) or {}, (texts or {}).get(sid) or "",
            crossref_get=cached_cr, oasisbr_get=cached_ob, card=card,
        )

    if len(sources) > 1 and max_workers > 1:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(sources))) as pool:
            resolved = list(pool.map(task, sources))
    else:
        resolved = [task(s) for s in sources]

    # Atribui chaves determinísticas na ordem original das fontes.
    used, out = set(), []
    for item in resolved:
        if item.pop("inherited", False):
            pref = item.pop("preferred_key", "")
            key = pref if pref and pref not in used else _key_for(item["fields"], used)
            used.add(key)
        else:
            key = _key_for(item["fields"], used)
        out.append({
            "type": item["type"],
            "key": key,
            "fields": item["fields"],
            "source_id": item["source_id"],
            "how": item["how"],
            "consulta": item["consulta"],
        })
    return out


def bibtex_block(entries: list[dict]) -> str:
    """Bloco para a ideia: o motor recebe as chaves e os dados oficiais."""
    if not entries:
        return ""
    lines = ["\n\n## REFERÊNCIAS OFICIAIS DAS FONTES ANEXADAS",
             "Para citar uma fonte anexada, use EXATAMENTE a chave e os dados abaixo. Não altere autor, "
             "título, periódico ou ano, e não invente dados de referências que não estejam aqui ou na "
             "busca bibliográfica.\n", "```bibtex"]
    lines += [render(e).rstrip() for e in entries]
    lines.append("```\n")
    return "\n".join(lines)


# ---------------------------------------------------------- reconciliação
def _match(entry: dict, official: list[dict]) -> dict | None:
    fields = entry["fields"]
    for item in official:
        if item.get("how") == "arquivo" and not item["fields"].get("author"):
            # Só o título do arquivo: exige título muito parecido.
            if similarity(fields.get("title", ""), item["fields"].get("title", "")) >= TITLE_MATCH:
                return item
            continue
        if entry["key"] == item["key"]:
            return item
        same_author = surname(fields.get("author", "")) and \
            surname(fields.get("author", "")) == surname(item["fields"].get("author", ""))
        same_year = fields.get("year") and fields.get("year") == item["fields"].get("year")
        title_close = similarity(fields.get("title", ""), item["fields"].get("title", "")) >= TITLE_MATCH
        if title_close or (same_author and same_year):
            return item
    return None


def reconcile(entries: list[dict], official: list[dict]) -> tuple[list[dict], list[dict]]:
    """Troca dados de fontes anexadas pelos oficiais (mantém a chave) e acusa enchimento."""
    fixed, findings = [], []
    for entry in entries:
        match = _match(entry, official)
        if match and match.get("how") != "arquivo":
            changed = [k for k in ("author", "title", "journal", "booktitle", "school", "year")
                       if fold(entry["fields"].get(k, "")) != fold(match["fields"].get(k, ""))
                       and (entry["fields"].get(k) or match["fields"].get(k))]
            if changed:
                findings.append({"code": "corrigida_pela_fonte_anexada", "priority": "high", "key": entry["key"],
                                 "fields": changed, "source_id": match.get("source_id"),
                                 "detail": "Dados do manuscrito diferiam da fonte anexada; substituídos pelos "
                                           "dados oficiais (" + match.get("how", "") + ")."})
            entry = {"type": match["type"], "key": entry["key"], "fields": dict(match["fields"])}
        bad = [k for k in ("journal", "booktitle", "school", "publisher", "title", "author")
               if PLACEHOLDER.match(fold(entry["fields"].get(k, "")).strip())]
        if bad:
            findings.append({"code": "valor_de_enchimento", "priority": "high", "key": entry["key"],
                             "fields": bad, "detail": "Valor genérico no lugar de um dado real; confira "
                                                      "a referência antes de publicar."})
        fixed.append(entry)
    return fixed, findings


def merge(file_entries: list[dict], inline_entries: list[dict]) -> tuple[list[dict], list[str]]:
    keys = {e["key"] for e in file_entries}
    added = [e for e in inline_entries if e["key"] not in keys]
    return file_entries + added, [e["key"] for e in added]


def cited_keys(tex: str) -> set[str]:
    keys = set()
    for group in re.findall(r"\\(?:cite[a-z]*|nocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex or ""):
        keys.update(k.strip() for k in group.split(",") if k.strip() and k.strip() != "*")
    return keys


def repair(tex: str, bib: str, official: list[dict]) -> dict:
    """Função pura: devolve .tex e .bib corrigidos e o relatório."""
    inline_bib, cleaned_tex, inline_files = extract_inline(tex)
    entries, added = merge(parse_entries(bib), parse_entries(inline_bib))
    entries, findings = reconcile(entries, official)
    keys = {e["key"] for e in entries}
    missing = sorted(cited_keys(cleaned_tex) - keys)
    if missing:
        findings.append({"code": "citacao_sem_referencia", "priority": "high", "keys": missing,
                         "detail": "Chaves citadas no texto sem entrada na bibliografia."})
    return {"tex": cleaned_tex, "bib": "\n".join(render(e) for e in entries), "entries": entries,
            "report": {"version": VERSION, "inline_blocks": inline_files, "inline_entries_added": added,
                       "entries_total": len(entries), "official_sources": [
                           {"key": o["key"], "source_id": o.get("source_id"), "how": o.get("how")} for o in official],
                       "findings": findings,
                       "summary": {"corrigidas": sum(f["code"] == "corrigida_pela_fonte_anexada" for f in findings),
                                   "enchimento": sum(f["code"] == "valor_de_enchimento" for f in findings),
                                   "sem_referencia": len(missing)}}}


# ---------------------------------------------------------- recompilação
def recompile(workdir: Path, tex: str, name: str = "scriptorium_final", timeout: int = 180) -> tuple[Path | None, str]:
    """pdflatex + bibtex + pdflatex x2 no diretório do motor. Falha devolve (None, motivo)."""
    tex_path = workdir / f"{name}.tex"
    tex_path.write_text(tex, encoding="utf-8")
    steps = [["pdflatex", "-interaction=nonstopmode", tex_path.name], ["bibtex", name],
             ["pdflatex", "-interaction=nonstopmode", tex_path.name],
             ["pdflatex", "-interaction=nonstopmode", tex_path.name]]
    for command in steps:
        try:
            subprocess.run(command, cwd=str(workdir), capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"{command[0]}: {type(exc).__name__}"
    pdf = workdir / f"{name}.pdf"
    log = (workdir / f"{name}.log").read_text(encoding="utf-8", errors="replace") if (workdir / f"{name}.log").exists() else ""
    undefined = len(re.findall(r"Citation `[^']+' (?:on page \d+ )?undefined", log))
    if not pdf.exists() or pdf.stat().st_size < 1000:
        return None, "pdflatex não gerou o PDF"
    return pdf, f"citações indefinidas: {undefined}"
