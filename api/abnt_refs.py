"""Motor bibliográfico ABNT (NBR 6023:2018 e NBR 10520:2023), RIS/BibTeX e coerência.

Reutiliza `csl_export.py` como fonte única de formatação ABNT e conversão BibTeX -> CSL,
adicionando:
- parser RIS (exportações do Zotero, Mendeley, SciELO, BDTD e Periódicos CAPES);
- geração de citação no texto (parentética e narrativa, com página opcional);
- exportação reversa da Biblioteca para `.bib` e `.ris` (interoperabilidade com Zotero/LaTeX);
- detecção de duplicatas por DOI, SHA-256 ou título+ano normalizados;
- conferência de coerência entre citações usadas no texto e fontes da Biblioteca.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from csl_export import format_abnt, parse_bibtex, to_csl

DOI_RE = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s,;<>\"')}\]]+)", re.IGNORECASE)

# Mapa RIS (TY) -> tipo interno usado em bib_entry (compatível com BibTeX / csl_export)
RIS_TYPES = {
    "JOUR": "article",
    "EJOUR": "article",
    "MGZN": "article",
    "CONF": "inproceedings",
    "CPAPER": "inproceedings",
    "BOOK": "book",
    "EBOOK": "book",
    "CHAP": "incollection",
    "THES": "mastersthesis",
    "RPRT": "techreport",
    "ELEC": "online",
    "GEN": "misc",
}

BIB_TO_RIS = {
    "article": "JOUR",
    "inproceedings": "CONF",
    "conference": "CONF",
    "book": "BOOK",
    "incollection": "CHAP",
    "inbook": "CHAP",
    "mastersthesis": "THES",
    "phdthesis": "THES",
    "techreport": "RPRT",
    "online": "ELEC",
    "misc": "GEN",
}

STUDY_ROLES = {"", "marco_teorico", "metodo", "evidencia", "contraponto"}
READING_STATUSES = {"a_ler", "lido", "incluido", "descartado"}


def normalize_doi(raw: str | None) -> str:
    if not raw:
        return ""
    match = DOI_RE.search(str(raw).strip())
    if not match:
        return ""
    return match.group(1).rstrip(".").lower()


def normalize_title(raw: str | None) -> str:
    if not raw:
        return ""
    norm = unicodedata.normalize("NFKD", str(raw)).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-z0-9]+", " ", norm.lower()).strip()
    return norm


def _strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _extract_year(raw: str | int | None) -> str:
    if raw is None:
        return ""
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(raw))
    return m.group(1) if m else ""


def _parse_people(author_str: str | list[str] | None) -> list[dict]:
    if not author_str:
        return []
    if isinstance(author_str, list):
        raw_parts = [str(a).strip() for a in author_str if str(a).strip()]
    else:
        text = str(author_str).strip()
        if re.search(r"\s+and\s+", text, re.IGNORECASE):
            raw_parts = [p.strip() for p in re.split(r"\s+and\s+", text, flags=re.IGNORECASE) if p.strip()]
        elif ";" in text:
            raw_parts = [p.strip() for p in text.split(";") if p.strip()]
        else:
            raw_parts = [text] if text else []

    people = []
    for raw in raw_parts:
        if raw.lower() in ("others", "et al.", "et al"):
            people.append({"literal": "et al."})
        elif "," in raw:
            family, given = [p.strip() for p in raw.split(",", 1)]
            people.append({"family": family, "given": given})
        elif " " in raw:
            tokens = raw.split()
            # Sobrenomes compostos comuns (Jr., Neto, Filho, Sobrinho)
            if len(tokens) >= 3 and tokens[-1].rstrip(".").lower() in ("jr", "junior", "neto", "filho", "sobrinho"):
                family = " ".join(tokens[-2:])
                given = " ".join(tokens[:-2])
            else:
                family = tokens[-1]
                given = " ".join(tokens[:-1])
            people.append({"family": family, "given": given})
        else:
            people.append({"literal": raw})
    return people


def bib_entry_to_csl(bib_entry: dict | None, fallback_name: str = "") -> dict | None:
    """Converte `item['bib_entry']` da Biblioteca para CSL-JSON compatível com `csl_export.format_abnt`."""
    if not isinstance(bib_entry, dict):
        return None
    fields = bib_entry.get("fields") if isinstance(bib_entry.get("fields"), dict) else bib_entry
    title = str(fields.get("title") or fields.get("titulo") or "").strip()
    author_raw = fields.get("author") or fields.get("autor") or ""
    if not title and not author_raw:
        return None
    entry = {
        "key": str(bib_entry.get("key") or "ref"),
        "type": str(bib_entry.get("type") or fields.get("tipo") or "article").lower(),
        "title": title or re.sub(r"\.\w+$", "", fallback_name),
        "author": " and ".join(
            (f"{p['family']}, {p['given']}" if p.get("family") and p.get("given")
             else p.get("family") or p.get("literal") or "")
            for p in _parse_people(author_raw)
        ),
        "year": _extract_year(fields.get("year") or fields.get("ano") or ""),
        "journal": str(fields.get("journal") or fields.get("veiculo") or "").strip(),
        "booktitle": str(fields.get("booktitle") or "").strip(),
        "publisher": str(fields.get("publisher") or fields.get("school") or fields.get("institution") or "").strip(),
        "address": str(fields.get("address") or "").strip(),
        "volume": str(fields.get("volume") or "").strip(),
        "number": str(fields.get("number") or "").strip(),
        "pages": str(fields.get("pages") or "").strip(),
        "edition": str(fields.get("edition") or "").strip(),
        "doi": normalize_doi(fields.get("doi")),
        "url": str(fields.get("url") or "").strip(),
    }
    return to_csl(entry)


def _surname(person: dict) -> str:
    return (person.get("family") or person.get("literal") or "").strip()


def format_abnt_citation(bib_entry: dict | None, *, narrative: bool = False, page: str = "") -> str:
    """Formata citação ABNT NBR 10520:2023 (parentética ou narrativa, com página opcional).

    - Até 3 autores: todos citados; 4 ou mais: primeiro + `et al.`.
    - NBR 10520:2023 permite caixa alta ou normal dentro de parênteses; mantemos o padrão
      tradicional em CAIXA ALTA entre parênteses (exigido na maioria dos templates ABNT/IFRS)
      e caixa normal fora de parênteses: `Freire (1996, p. 47)`.
    """
    csl = bib_entry_to_csl(bib_entry)
    if not csl:
        return ""
    people = [p for p in (csl.get("author") or []) if _surname(p)]
    year_val = ((csl.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    year = str(year_val) if year_val else "s. d."
    page_clean = re.sub(r"^(p\.?|pág\.?|pp\.?)\s*", "", str(page or "").strip(), flags=re.IGNORECASE)
    page_part = f", p. {page_clean}" if page_clean else ""

    if not people:
        first_word = (csl.get("title") or "OBRA").split()[0].rstrip(".,;:")
        if narrative:
            return f"{first_word} ({year}{page_part})"
        return f"({first_word.upper()}, {year}{page_part})"

    surnames = [_surname(p) for p in people]
    if len(surnames) > 3:
        if narrative:
            return f"{surnames[0]} et al. ({year}{page_part})"
        return f"({surnames[0].upper()} et al., {year}{page_part})"

    if narrative:
        if len(surnames) == 1:
            who = surnames[0]
        elif len(surnames) == 2:
            who = f"{surnames[0]} e {surnames[1]}"
        else:
            who = f"{surnames[0]}, {surnames[1]} e {surnames[2]}"
        return f"{who} ({year}{page_part})"

    who = "; ".join(s.upper() for s in surnames)
    return f"({who}, {year}{page_part})"


def format_abnt_bundle(bib_entry: dict | None, fallback_name: str = "") -> dict | None:
    """Devolve referência ABNT (markdown e texto puro) + citações parentética e narrativa."""
    csl = bib_entry_to_csl(bib_entry, fallback_name=fallback_name)
    if not csl:
        return None
    md_ref = format_abnt(csl)
    plain_ref = md_ref.replace("**", "")
    return {
        "reference_md": md_ref,
        "reference": plain_ref,
        "cite_parenthetical": format_abnt_citation(bib_entry, narrative=False),
        "cite_narrative": format_abnt_citation(bib_entry, narrative=True),
    }


def stable_key(fields: dict) -> str:
    people = _parse_people(fields.get("author"))
    first = _strip_accents(_surname(people[0]) if people else (fields.get("title") or "obra").split()[0])
    slug = re.sub(r"[^a-z0-9]", "", first.lower()) or "obra"
    year = _extract_year(fields.get("year")) or "sd"
    title_words = [
        w for w in normalize_title(fields.get("title")).split()
        if len(w) >= 4 and w not in ("para", "como", "sobre", "entre", "with", "from", "that", "this")
    ]
    tail = title_words[0][:10] if title_words else ""
    return f"{slug}{year}{tail}"


def parse_ris(text: str) -> list[dict]:
    """Parser simples e seguro para registros RIS (Zotero, Mendeley, SciELO, BDTD)."""
    entries: list[dict] = []
    cur: dict | None = None
    authors: list[str] = []
    start_page = ""
    end_page = ""

    def flush():
        nonlocal cur, authors, start_page, end_page
        if cur is None:
            return
        if authors:
            cur["author"] = " and ".join(authors)
        if start_page and end_page:
            cur["pages"] = f"{start_page}-{end_page}"
        elif start_page:
            cur["pages"] = start_page
        if cur.get("title") or cur.get("author") or cur.get("doi"):
            cur.setdefault("key", stable_key(cur))
            entries.append(cur)
        cur = None
        authors = []
        start_page = ""
        end_page = ""

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            flush()
            cur = {"type": RIS_TYPES.get(val.upper(), "misc")}
        elif tag == "ER":
            flush()
        elif cur is not None:
            if tag in ("AU", "A1", "A2") and val:
                authors.append(val)
            elif tag in ("TI", "T1") and val and not cur.get("title"):
                cur["title"] = val
            elif tag in ("JO", "JF", "T2", "JA") and val and not cur.get("journal"):
                cur["journal"] = val
            elif tag in ("PY", "Y1", "DA") and val and not cur.get("year"):
                yr = _extract_year(val)
                if yr:
                    cur["year"] = yr
            elif tag == "VL" and val:
                cur["volume"] = val
            elif tag == "IS" and val:
                cur["number"] = val
            elif tag == "SP" and val:
                start_page = val
            elif tag == "EP" and val:
                end_page = val
            elif tag == "DO" and val:
                cur["doi"] = normalize_doi(val) or val
            elif tag == "UR" and val and not cur.get("url"):
                cur["url"] = val
            elif tag == "PB" and val:
                cur["publisher"] = val
            elif tag == "CY" and val:
                cur["address"] = val
            elif tag == "ET" and val:
                cur["edition"] = val
            elif tag == "SN" and val:
                cur["issn"] = val
    flush()
    return entries


def parse_references_text(text: str) -> list[dict]:
    """Aceita BibTeX ou RIS colado pelo estudante e normaliza para o esquema interno de `bib_entry`."""
    raw = (text or "").strip()
    if not raw:
        return []
    if re.search(r"^\s*@\w+\s*[{(]", raw, re.MULTILINE):
        parsed = parse_bibtex(raw)
    elif re.search(r"^\s*TY\s*-\s*", raw, re.MULTILINE):
        parsed = parse_ris(raw)
    else:
        return []

    out = []
    for entry in parsed:
        fields = {
            k: str(v).strip()
            for k, v in entry.items()
            if k not in ("key", "type") and str(v or "").strip()
        }
        if fields.get("doi"):
            fields["doi"] = normalize_doi(fields["doi"]) or fields["doi"]
        if fields.get("year"):
            fields["year"] = _extract_year(fields["year"]) or fields["year"]
        if not fields.get("title") and not fields.get("author"):
            continue
        out.append({
            "type": str(entry.get("type") or "misc").lower(),
            "key": str(entry.get("key") or stable_key(fields)),
            "fields": fields,
        })
    return out


def bib_entry_to_bibtex(bib_entry: dict) -> str:
    kind = str(bib_entry.get("type") or "misc").lower()
    key = re.sub(r"[^A-Za-z0-9_:-]", "", str(bib_entry.get("key") or "obra")) or "obra"
    fields = bib_entry.get("fields") or {}
    lines = [f"@{kind}{{{key},"]
    order = ("author", "title", "journal", "booktitle", "publisher", "address",
             "year", "volume", "number", "pages", "edition", "doi", "url")
    seen = set()
    for k in order:
        val = str(fields.get(k) or "").strip()
        if val:
            lines.append(f"  {k} = {{{val}}},")
            seen.add(k)
    for k, v in fields.items():
        if k in seen or k in ("tipo", "veiculo", "titulo", "autor", "ano"):
            continue
        val = str(v or "").strip()
        if val:
            lines.append(f"  {k} = {{{val}}},")
    lines.append("}")
    return "\n".join(lines)


def bib_entry_to_ris(bib_entry: dict) -> str:
    kind = str(bib_entry.get("type") or "misc").lower()
    fields = bib_entry.get("fields") or {}
    lines = [f"TY  - {BIB_TO_RIS.get(kind, 'GEN')}"]
    for person in _parse_people(fields.get("author")):
        if person.get("family") and person.get("given"):
            lines.append(f"AU  - {person['family']}, {person['given']}")
        elif _surname(person):
            lines.append(f"AU  - {_surname(person)}")
    if fields.get("title"):
        lines.append(f"TI  - {fields['title']}")
    venue = fields.get("journal") or fields.get("booktitle")
    if venue:
        lines.append(f"JO  - {venue}")
    if fields.get("year"):
        lines.append(f"PY  - {_extract_year(fields['year']) or fields['year']}")
    if fields.get("volume"):
        lines.append(f"VL  - {fields['volume']}")
    if fields.get("number"):
        lines.append(f"IS  - {fields['number']}")
    if fields.get("pages"):
        parts = re.split(r"[-–]+", str(fields["pages"]), maxsplit=1)
        lines.append(f"SP  - {parts[0].strip()}")
        if len(parts) == 2 and parts[1].strip():
            lines.append(f"EP  - {parts[1].strip()}")
    if fields.get("publisher"):
        lines.append(f"PB  - {fields['publisher']}")
    if fields.get("address"):
        lines.append(f"CY  - {fields['address']}")
    if fields.get("doi"):
        lines.append(f"DO  - {normalize_doi(fields['doi']) or fields['doi']}")
    if fields.get("url"):
        lines.append(f"UR  - {fields['url']}")
    lines.append("ER  -")
    return "\n".join(lines)


def item_duplicate_keys(item: dict) -> set[str]:
    """Chaves estáveis de deduplicação para um item da biblioteca."""
    keys: set[str] = set()
    sha = str(item.get("sha256") or "").strip().lower()
    if sha:
        keys.add("sha:" + sha)
    bib = item.get("bib_entry") or {}
    fields = bib.get("fields") if isinstance(bib, dict) else {}
    origin = item.get("origin") or {}
    doi = normalize_doi((fields or {}).get("doi") or (origin.get("doi") if isinstance(origin, dict) else ""))
    if doi:
        keys.add("doi:" + doi)
    title = normalize_title((fields or {}).get("title") or "")
    year = _extract_year((fields or {}).get("year") or "")
    if len(title) >= 12:
        keys.add(f"ty:{title}|{year}")
    return keys


def find_duplicates(items: Iterable[dict]) -> list[dict]:
    """Detecta grupos de possíveis duplicatas na biblioteca (mesmo arquivo, DOI ou título+ano)."""
    buckets: dict[str, list[dict]] = {}
    for item in items:
        for key in item_duplicate_keys(item):
            buckets.setdefault(key, []).append(item)
    groups = []
    seen_sets: set[frozenset[str]] = set()
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        ids = frozenset(str(i.get("id")) for i in group)
        if ids in seen_sets:
            continue
        seen_sets.add(ids)
        reason = "mesmo arquivo (SHA-256)" if key.startswith("sha:") else (
            "mesmo DOI" if key.startswith("doi:") else "mesmo título e ano"
        )
        groups.append({
            "reason": reason,
            "key": key,
            "items": [{"id": i.get("id"), "name": i.get("name"), "collection": i.get("collection")} for i in group],
        })
    return groups


def export_library_references(items: Iterable[dict], fmt: str = "abnt") -> tuple[str, str, int]:
    """Exporta as referências bibliográficas da biblioteca em ABNT, BibTeX ou RIS."""
    entries = []
    for item in items:
        bib = item.get("bib_entry")
        if isinstance(bib, dict) and isinstance(bib.get("fields"), dict):
            entries.append((item, bib))
    if fmt == "bib":
        body = "\n\n".join(bib_entry_to_bibtex(bib) for _, bib in entries) + ("\n" if entries else "")
        return body, "application/x-bibtex; charset=utf-8", len(entries)
    if fmt == "ris":
        body = "\n\n".join(bib_entry_to_ris(bib) for _, bib in entries) + ("\n" if entries else "")
        return body, "application/x-research-info-systems; charset=utf-8", len(entries)

    # Padrão: ABNT NBR 6023:2018 em ordem alfabética
    csl_items = []
    for item, bib in entries:
        csl = bib_entry_to_csl(bib, fallback_name=str(item.get("name") or ""))
        if csl:
            csl_items.append(csl)

    def sort_key(csl):
        first = (csl.get("author") or [{}])[0]
        name = first.get("family") or first.get("literal") or csl.get("title", "")
        return _strip_accents(name).lower()

    lines = [format_abnt(c).replace("**", "") for c in sorted(csl_items, key=sort_key)]
    header = "REFERÊNCIAS (ABNT NBR 6023:2018)\n\n" if lines else ""
    return header + "\n\n".join(lines) + ("\n" if lines else ""), "text/plain; charset=utf-8", len(lines)


_PAREN_BLOCK_RE = re.compile(r"\(([^()]{4,260})\)")
_PAREN_ITEM_RE = re.compile(
    r"(?:^|;\s*)(?:(?:cf\.?|ver|veja|apud|e\.g\.|p\.?\s*ex\.?|vide)\s+)*"
    r"([A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þa-zà-öø-ÿ'\- ]{1,60}(?:;\s*[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þa-zà-öø-ÿ'\- ]{1,50}){0,2}(?:\s+et\s+al\.?)?)"
    r",\s*((?:1[89]|20)\d{2}[a-z]?)(?:,\s*p\.?\s*[\d\-–]+)?"
)
_NARR_CITE_RE = re.compile(
    r"\b([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]{1,30}"
    r"(?:,\s*[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]{1,30}){0,2}"
    r"(?:\s+(?:e|&)\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]{1,30}|\s+et\s+al\.?)?)"
    r"\s*\(((?:1[89]|20)\d{2}[a-z]?)(?:,\s*p\.?\s*[\d\-–]+)?\)"
)
_NON_AUTHOR_WORDS = {
    "segundo", "conforme", "em", "de", "no", "na", "para", "entre", "sobre",
    "como", "ano", "anos", "etapa", "fase", "versao", "versão", "artigo", "livro",
    "complementarmente", "adicionalmente", "paralelamente", "analogamente",
    "semelhantemente", "igualmente", "portanto", "contudo", "todavia", "entretanto",
    "assim", "logo", "ademais", "outrossim", "finalmente", "inicialmente",
    "primeiramente", "posteriormente", "atualmente", "recentemente", "ainda",
}


def extract_in_text_citations(text: str) -> list[dict]:
    """Extrai citações autor-data (ABNT NBR 10520:2023), inclusive múltiplas no mesmo parêntese e 3 autores."""
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(raw_label: str, raw_who: str, year_raw: str):
        year = re.sub(r"[a-z]$", "", year_raw.strip())
        # Remove advérbio/conector inicial seguido de vírgula (ex.: "Complementarmente, Silva, Oliveira e Silva")
        who = raw_who.strip()
        label = raw_label
        lead = re.match(r"^([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'\-]+),\s+(.+)$", who)
        if lead and _strip_accents(lead.group(1)).lower() in _NON_AUTHOR_WORDS:
            who = lead.group(2).strip()
            label = re.sub(r"^" + re.escape(lead.group(1)) + r",\s+", "", label)
        first = re.split(r"\s*[,;]\s*|\s+et\s+al\.?|\s+e\s+|\s*&\s*", who, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        norm_surname = _strip_accents(first).lower()
        if not norm_surname or len(norm_surname) < 2 or norm_surname in _NON_AUTHOR_WORDS:
            return
        sig = (norm_surname, year)
        if sig not in seen:
            seen.add(sig)
            found.append({"raw": label, "surname": norm_surname, "year": year})

    for block in _PAREN_BLOCK_RE.finditer(text or ""):
        inner = block.group(1).strip()
        if not re.search(r"\b(?:1[89]|20)\d{2}\b", inner):
            continue
        # Extrai uma ou múltiplas citações dentro do mesmo parêntese: (FAN et al., 2025; SILVA; OLIVEIRA; SILVA, 2025)
        for m in _PAREN_ITEM_RE.finditer(inner):
            piece = m.group(0).lstrip("; ").strip()
            _add(f"({piece})", m.group(1), m.group(2))

    for m in _NARR_CITE_RE.finditer(text or ""):
        _add(m.group(0), m.group(1), m.group(2))

    return found


def check_citation_coherence(text: str, library_items: Iterable[dict]) -> dict:
    """Cruza citações usadas no texto com as fontes da Biblioteca (Única Fonte de Verdade)."""
    citations = extract_in_text_citations(text)
    index: list[tuple[str, str, dict, dict]] = []
    for item in library_items:
        bib = item.get("bib_entry")
        csl = bib_entry_to_csl(bib, fallback_name=str(item.get("name") or ""))
        if not csl:
            continue
        people = csl.get("author") or []
        first = _strip_accents(_surname(people[0])).lower() if people else ""
        year_val = ((csl.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        year = str(year_val) if year_val else ""
        if first and year:
            index.append((first, year, item, csl))

    matched_ids: set[str] = set()
    matched_csls: list[dict] = []
    missing: list[dict] = []

    for cite in citations:
        hit = next(
            (row for row in index if (row[0] == cite["surname"] or row[0].endswith(" " + cite["surname"])) and row[1] == cite["year"]),
            None,
        )
        if hit:
            item_id = str(hit[2].get("id") or "")
            if item_id not in matched_ids:
                matched_ids.add(item_id)
                matched_csls.append(hit[3])
        else:
            missing.append(cite)

    uncited = [
        {"id": item.get("id"), "name": item.get("name"), "cite": format_abnt_citation(item.get("bib_entry"))}
        for _, _, item, _ in index
        if str(item.get("id") or "") not in matched_ids
    ]

    def sort_key(csl):
        first = (csl.get("author") or [{}])[0]
        return _strip_accents(first.get("family") or first.get("literal") or csl.get("title", "")).lower()

    abnt_lines = [format_abnt(c).replace("**", "") for c in sorted(matched_csls, key=sort_key)]
    return {
        "citations_found": len(citations),
        "matched_count": len(matched_ids),
        "missing_in_library": missing,
        "uncited_in_library": uncited,
        "abnt_references": abnt_lines,
        "abnt_references_text": "\n\n".join(abnt_lines),
    }


def prisma_summary(items: Iterable[dict]) -> dict:
    """Resumo PRISMA / triagem calculado diretamente da Biblioteca (Única Fonte de Verdade)."""
    records = list(items)
    total = len(records)
    dup_groups = find_duplicates(records)
    dup_extra = sum(max(0, len(g.get("items") or []) - 1) for g in dup_groups)
    unicos = max(0, total - dup_extra)

    triagem = {"a_ler": 0, "lido": 0, "incluido": 0, "descartado": 0}
    por_papel = {"marco_teorico": 0, "metodo": 0, "evidencia": 0, "contraponto": 0, "sem_papel": 0}
    motivos: dict[str, int] = {}
    fichamentos_total = 0
    sustentacao_conferida = 0

    for item in records:
        st = item.get("reading_status") or "a_ler"
        triagem[st if st in triagem else "a_ler"] += 1
        role = item.get("role") or ""
        por_papel[role if role in por_papel else "sem_papel"] += 1
        if st == "descartado":
            reason = str(item.get("exclude_reason") or "").strip() or "Motivo não informado"
            motivos[reason] = motivos.get(reason, 0) + 1
        notes = item.get("study_notes") or []
        fichamentos_total += len(notes)
        sustentacao_conferida += sum(1 for n in notes if isinstance(n, dict) and n.get("support_checked"))

    motivos_lista = [
        {"motivo": k, "quantidade": v}
        for k, v in sorted(motivos.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    ]
    avaliados = triagem["lido"] + triagem["incluido"] + triagem["descartado"]
    motivos_txt = "; ".join(f"{m['motivo']} (n={m['quantidade']})" for m in motivos_lista[:6])
    resumo = (
        f"Foram identificados {total} registro(s) na biblioteca do projeto"
        + (f" ({dup_extra} possível(is) duplicata(s) sinalizada(s), restando {unicos} único(s))" if dup_extra else "")
        + f". Destes, {avaliados} passaram por leitura/triagem ({triagem['a_ler']} aguardando leitura), "
        + f"resultando em {triagem['incluido']} fonte(s) incluída(s) no projeto e {triagem['descartado']} descartada(s)"
        + (f" ({motivos_txt})" if motivos_txt else "")
        + f". Foram registrados {fichamentos_total} fichamento(s) vinculados a páginas, "
        + f"dos quais {sustentacao_conferida} com conferência humana de sustentação."
    )
    return {
        "total_identificados": total,
        "duplicatas_detectadas": dup_extra,
        "unicos_estimados": unicos,
        "avaliados": avaliados,
        "triagem": triagem,
        "por_papel": por_papel,
        "motivos_descarte": motivos_lista,
        "fichamentos_total": fichamentos_total,
        "sustentacao_conferida": sustentacao_conferida,
        "resumo_metodologico": resumo,
    }
