"""Exportação bibliográfica: BibTeX -> CSL-JSON e lista ABNT (M27).

Origem: R24 (CSL Styles; esquema CSL-JSON e estilo
"associacao-brasileira-de-normas-tecnicas"), R23 (Citation.js, referência do
mapeamento BibTeX -> CSL) e R38 (abnTeX2, que já gera ABNT no LaTeX). Nenhum
código copiado: mapeamento próprio e testado por snapshot
(tests/test_biblioteca_exportacao.py). Plano V2, módulo M27 "Exportação bibliográfica e
estilos": "exportação CSL e testes de estilo".

CSL-JSON é o formato de troca que Zotero, Mendeley e processadores CSL
(citeproc) importam. A lista ABNT gerada aqui segue a NBR 6023:2018 nos
casos comuns (artigo, livro, capítulo, trabalho em evento, tese e documento
on-line) e deve ser conferida: casos raros pedem revisão manual.
"""
from __future__ import annotations

import re
import unicodedata

VERSION = "csl-export-1"
TYPES = {
    "article": "article-journal", "inproceedings": "paper-conference",
    "conference": "paper-conference", "book": "book", "incollection": "chapter",
    "inbook": "chapter", "phdthesis": "thesis", "mastersthesis": "thesis",
    "techreport": "report", "misc": "document", "online": "webpage", "manual": "book",
    "unpublished": "manuscript",
}
ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", '"': "\u0308",
           "c": "\u0327", "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c"}
_ENTRY = re.compile(r"@(\w+)\s*[{(]\s*([^,\s]+)\s*,", re.MULTILINE)


# ------------------------------------------------------------------ BibTeX
def _balanced(text: str, pos: int) -> tuple[str, int]:
    depth, start = 0, pos
    while pos < len(text):
        ch = text[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:pos], pos + 1
        pos += 1
    return text[start + 1:], len(text)


def latex_to_text(value: str) -> str:
    def accent(m):
        mark, letter = m.group(1), m.group(2)
        return unicodedata.normalize("NFC", letter + ACCENTS.get(mark, ""))
    value = re.sub(r"\\([`'^~\"=.uvc])\s*\{?\s*([A-Za-z])\s*\}?", accent, value)
    value = value.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("--", "–")
    value = re.sub(r"\\[a-zA-Z]+\s*", "", value)
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def parse_bibtex(text: str) -> list[dict]:
    entries = []
    for match in _ENTRY.finditer(text):
        kind, key = match.group(1).lower(), match.group(2)
        if kind in ("comment", "preamble", "string"):
            continue
        body_start = match.end()
        # Até a chave que fecha a entrada (equilíbrio de chaves a partir da abertura).
        opening = text.find("{", match.start(), match.end())
        body, _ = _balanced(text, opening) if opening != -1 else (text[body_start:], 0)
        body = body[len(key):].lstrip(" \t\r\n,") if body.startswith(key) else body
        fields, pos = {}, 0
        for field in re.finditer(r"([A-Za-z][\w-]*)\s*=\s*", body):
            if field.start() < pos:
                continue
            name, pos = field.group(1).lower(), field.end()
            if pos < len(body) and body[pos] == "{":
                value, pos = _balanced(body, pos)
            elif pos < len(body) and body[pos] == '"':
                end = body.find('"', pos + 1)
                value, pos = body[pos + 1:end], end + 1
            else:
                end = re.search(r"[,\n}]", body[pos:])
                value = body[pos:pos + (end.start() if end else len(body))]
                pos += len(value)
            fields[name] = latex_to_text(value)
        entries.append({"key": key, "type": kind, **fields})
    return entries


# --------------------------------------------------------------------- CSL
def _names(value: str) -> list[dict]:
    people = []
    for raw in re.split(r"\s+and\s+", value or ""):
        raw = raw.strip()
        if not raw:
            continue
        if raw.lower() == "others":
            people.append({"literal": "et al."})
        elif "," in raw:
            family, given = [p.strip() for p in raw.split(",", 1)]
            people.append({"family": family, "given": given})
        elif " " in raw:
            *given, family = raw.split()
            people.append({"family": family, "given": " ".join(given)})
        else:
            people.append({"literal": raw})
    return people


def to_csl(entry: dict) -> dict:
    kind = entry.get("type", "misc")
    item = {"id": entry["key"], "type": TYPES.get(kind, "document"), "title": entry.get("title", "")}
    if entry.get("author"):
        item["author"] = _names(entry["author"])
    if entry.get("editor"):
        item["editor"] = _names(entry["editor"])
    year = re.search(r"\d{4}", entry.get("year", "") or entry.get("date", ""))
    if year:
        item["issued"] = {"date-parts": [[int(year.group())]]}
    container = entry.get("journal") or entry.get("booktitle") or entry.get("journaltitle")
    if container:
        item["container-title"] = container
    mapping = {"volume": "volume", "number": "issue", "pages": "page", "doi": "DOI", "url": "URL",
               "publisher": "publisher", "address": "publisher-place", "isbn": "ISBN",
               "issn": "ISSN", "edition": "edition", "school": "publisher", "institution": "publisher",
               "note": "note"}
    for source, target in mapping.items():
        if entry.get(source) and target not in item:
            item[target] = entry[source]
    if kind in ("phdthesis", "mastersthesis"):
        item["genre"] = "Tese (Doutorado)" if kind == "phdthesis" else "Dissertação (Mestrado)"
    if item.get("DOI"):
        item["DOI"] = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", item["DOI"], flags=re.I)
    return item


def bibtex_to_csl(text: str) -> list[dict]:
    return [to_csl(e) for e in parse_bibtex(text)]


# -------------------------------------------------------------------- ABNT
def _abnt_name(person: dict) -> str:
    if "literal" in person:
        return person["literal"]
    given = " ".join(p for p in re.split(r"\s+", person.get("given", "")) if p)
    return f"{person.get('family', '').upper()}, {given}".strip(", ")


def _authors(item: dict) -> str:
    people = item.get("author") or []
    if not people:
        return ""
    # NBR 6023:2018 (8.1.1.2): até três autores, todos; mais de três, permite "et al.".
    if len(people) > 3:
        return _abnt_name(people[0]) + " et al."
    return "; ".join(_abnt_name(p) for p in people)


def format_abnt(item: dict) -> str:
    """Uma referência no padrão ABNT (NBR 6023:2018), com destaque em **negrito**."""
    item = {**item, **({"page": item["page"].replace("–", "-")} if item.get("page") else {})}
    authors = _authors(item)
    year = (item.get("issued") or {}).get("date-parts", [[None]])[0][0]
    year = str(year) if year else "[s. d.]"
    title = item.get("title", "").rstrip(".")
    place = item.get("publisher-place") or "[s. l.]"
    publisher = item.get("publisher") or "[s. n.]"
    head = (authors + ". ") if authors else ""
    kind = item.get("type")
    if kind == "article-journal":
        parts = [f"{head}{title}. **{item.get('container-title', '')}**"]
        if item.get("publisher-place"):
            parts.append(item["publisher-place"])
        for prefix, key in (("v.", "volume"), ("n.", "issue"), ("p.", "page")):
            if item.get(key):
                parts.append(f"{prefix} {item[key]}")
        parts.append(year)
        text = ", ".join(parts) + "."
    elif kind == "chapter":
        text = (f"{head}{title}. In: {item.get('container-title', '')}. {place}: {publisher}, {year}."
                + (f" p. {item['page']}." if item.get("page") else ""))
        text = text.replace(f"In: {item.get('container-title', '')}.",
                            f"In: **{item.get('container-title', '')}**.")
    elif kind == "paper-conference":
        text = (f"{head}{title}. In: {item.get('container-title', 'EVENTO')}. **Anais** [...]. "
                f"{place}: {publisher}, {year}." + (f" p. {item['page']}." if item.get("page") else ""))
    elif kind == "thesis":
        text = (f"{head}**{title}**. {year}. {item.get('genre', 'Trabalho acadêmico')} – "
                f"{publisher}, {place}, {year}.")
    elif kind in ("book", "report"):
        edition = f" {item['edition']}. ed." if item.get("edition") else ""
        text = f"{head}**{title}**.{edition} {place}: {publisher}, {year}."
    else:
        text = f"{head}**{title}**. {year}."
    if item.get("DOI"):
        text += f" DOI: https://doi.org/{item['DOI']}."
    elif item.get("URL"):
        text += f" Disponível em: {item['URL']}."
    return re.sub(r"\s+", " ", text).replace("..", ".").strip()


def abnt_list(items: list[dict]) -> str:
    """Lista em ordem alfabética (NBR 6023:2018, sistema autor-data)."""
    def sort_key(item):
        first = (item.get("author") or [{}])[0]
        name = first.get("family") or first.get("literal") or item.get("title", "")
        return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    lines = [format_abnt(i) for i in sorted(items, key=sort_key)]
    header = ("# Referências (ABNT NBR 6023:2018)\n\n"
              "Gerado automaticamente pelo Scriptorium a partir do BibTeX. Confira cada item: "
              "casos incomuns pedem ajuste manual. Destaque em **negrito**.\n\n")
    return header + "\n\n".join(lines) + "\n"
