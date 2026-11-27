"""Referências e citações no estilo APA 7 a partir das entradas BibTeX do projeto.

Usado na exportação para Word (.docx). No PDF quem formata é o biblatex-apa
(formatos/apa7); aqui seguimos as mesmas regras do Publication Manual, 7ª ed.:
até 20 autores, "&" antes do último, "et al." no texto a partir de 3 autores,
título do periódico e volume em itálico, DOI como https://doi.org/.

Cada referência sai como lista de trechos (texto, itálico) para o Word.
"""
from __future__ import annotations

import re

Run = tuple[str, bool]

LABELS = {
    "pt-BR": {"sd": "s.d.", "and": "e", "eds": "Orgs.", "ed": "Org.", "in": "In", "pp": "pp.",
              "mestrado": "Dissertação de mestrado", "doutorado": "Tese de doutorado", "relatorio": "Relatório"},
    "en": {"sd": "n.d.", "and": "and", "eds": "Eds.", "ed": "Ed.", "in": "In", "pp": "pp.",
           "mestrado": "Master's thesis", "doutorado": "Doctoral dissertation", "relatorio": "Report"},
}


def _labels(language: str) -> dict:
    return LABELS.get(language, LABELS["pt-BR"])


def _clean(value) -> str:
    text = str(value or "")
    text = re.sub(r"\\[A-Za-z]+\s*", "", text).replace("{", "").replace("}", "")
    return " ".join(text.split()).strip()


def split_authors(raw: str) -> list[tuple[str, str]]:
    """'Silva, João Antônio and Maria Souza' -> [('Silva', 'João Antônio'), ('Souza', 'Maria')]."""
    people = []
    for part in re.split(r"\s+and\s+|;", _clean(raw)):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            surname, given = part.split(",", 1)
        else:
            tokens = part.split()
            surname, given = (tokens[-1], " ".join(tokens[:-1])) if len(tokens) > 1 else (part, "")
        people.append((surname.strip(), given.strip()))
    return people


def initials(given: str) -> str:
    """'João Antônio' -> 'J. A.'; 'Jean-Paul' -> 'J.-P.'; já abreviado continua igual."""
    out = []
    for name in given.split():
        pieces = [p for p in name.split("-") if p]
        out.append("-".join(p[0].upper() + "." for p in pieces if p[0].isalpha()))
    return " ".join(x for x in out if x)


def _name(person: tuple[str, str]) -> str:
    surname, given = person
    ini = initials(given)
    return f"{surname}, {ini}" if ini else surname


def authors_reference(raw: str) -> str:
    people = split_authors(raw)
    if not people:
        return ""
    names = [_name(p) for p in people]
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def _year(fields: dict, language: str) -> str:
    year = re.search(r"\d{4}[a-z]?", _clean(fields.get("year")))
    return year.group(0) if year else _labels(language)["sd"]


def _doi_or_url(fields: dict) -> str:
    doi = _clean(fields.get("doi"))
    if doi:
        return "https://doi.org/" + re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return _clean(fields.get("url"))


def _edition(raw: str, language: str) -> str:
    """'2' -> '2. ed.' (pt-BR) ou '2nd ed.' (en); a 1ª edição não aparece na APA."""
    number = re.match(r"\d+", raw or "")
    if not raw or (number and number.group(0) == "1"):
        return ""
    if not number:
        return raw
    n = int(number.group(0))
    if language == "en":
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix} ed."
    return f"{n}. ed."


def _end(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".?!" else text + "."


def reference_runs(ref: dict, language: str = "pt-BR") -> list[Run]:
    """Uma referência APA 7 como trechos (texto, itálico)."""
    fields = (ref or {}).get("fields") or {}
    kind = str((ref or {}).get("type") or fields.get("ENTRYTYPE") or "misc").lower()
    lab = _labels(language)
    title = _clean(fields.get("title")) or str((ref or {}).get("key") or "Sem título")
    authors = authors_reference(fields.get("author") or "")
    year = _year(fields, language)
    link = _doi_or_url(fields)
    runs: list[Run] = []
    head = f"{_end(authors)} ({year}). " if authors else ""
    if not authors:  # Sem autor: o título vai para a posição do autor.
        runs += [(title, kind not in ("article", "incollection", "inproceedings")), (f" ({year}). ", False)]
    else:
        runs.append((head, False))
    publisher = _clean(fields.get("publisher") or fields.get("institution") or fields.get("organization"))
    pages = _clean(fields.get("pages")).replace("--", "\u2013").replace("-", "\u2013")
    if kind == "article":
        if authors:
            runs.append((_end(title) + " ", False))
        journal = _clean(fields.get("journal"))
        volume, number = _clean(fields.get("volume")), _clean(fields.get("number"))
        if journal:
            runs.append((journal, True))
            if volume:
                runs += [(", ", False), (volume, True)]
            if number:
                runs.append((f"({number})", False))
            if pages:
                runs.append((f", {pages}", False))
            runs.append((". ", False))
    elif kind in ("incollection", "inbook", "inproceedings", "conference"):
        if authors:
            runs.append((_end(title) + " ", False))
        book = _clean(fields.get("booktitle"))
        editors = split_authors(fields.get("editor") or "")
        if book:
            runs.append((f"{lab['in']} ", False))
            if editors:
                names = [(initials(g) + " " + s).strip() for s, g in editors]
                if len(names) <= 2:
                    joined = " & ".join(names)
                else:
                    joined = ", ".join(names[:-1]) + ", & " + names[-1]
                runs.append((f"{joined} ({lab['eds'] if len(names) > 1 else lab['ed']}), ", False))
            runs.append((book, True))
            runs.append((f" ({lab['pp']} {pages}). " if pages else ". ", False))
        if publisher:
            runs.append((_end(publisher) + " ", False))
    elif kind in ("mastersthesis", "phdthesis"):
        if authors:
            runs.append((title, True))
        school = _clean(fields.get("school") or fields.get("institution"))
        label = lab["doutorado"] if kind == "phdthesis" else lab["mestrado"]
        runs.append((f" [{label}{', ' + school if school else ''}]. ", False))
    elif kind == "techreport":
        if authors:
            runs.append((title, True))
        number = _clean(fields.get("number"))
        runs.append((f" ({lab['relatorio']} {number}). " if number else ". ", False))
        if publisher:
            runs.append((_end(publisher) + " ", False))
    else:  # book, online, misc
        if authors:
            runs.append((title, True))
        edition = _edition(_clean(fields.get("edition")), language)
        runs.append((f" ({edition}). " if edition else ". ", False))
        venue = publisher or _clean(fields.get("howpublished"))
        if venue and kind != "online":
            runs.append((_end(venue) + " ", False))
    if link:
        runs.append((link, False))
    return _tidy(runs)


def _tidy(runs: list[Run]) -> list[Run]:
    out: list[Run] = []
    for text, italic in runs:
        if not text:
            continue
        if out and out[-1][1] == italic:
            out[-1] = (out[-1][0] + text, italic)
        else:
            out.append((text, italic))
    if out:
        out[-1] = (out[-1][0].rstrip(), out[-1][1])
    return [(re.sub(r"\.\s*\.", ".", t) if not i else t, i) for t, i in out]


def reference_text(ref: dict, language: str = "pt-BR") -> str:
    return "".join(t for t, _ in reference_runs(ref, language))


def sort_key(ref: dict) -> str:
    fields = (ref or {}).get("fields") or {}
    return (authors_reference(fields.get("author") or "") or _clean(fields.get("title"))).lower() + _clean(fields.get("year"))


def cite_label(ref: dict | None, key: str, *, narrative: bool, language: str = "pt-BR") -> str:
    """Silva (2020) / (Silva & Souza, 2020) / Silva et al. (2020)."""
    fields = (ref or {}).get("fields") or {}
    people = split_authors(fields.get("author") or "")
    year = _year(fields, language)
    if not people:
        who = _clean(fields.get("title"))[:60] or key
    elif len(people) == 1:
        who = people[0][0]
    elif len(people) == 2:
        who = f"{people[0][0]} {_labels(language)['and'] if narrative else '&'} {people[1][0]}"
    else:
        who = f"{people[0][0]} et al."
    return f"{who} ({year})" if narrative else f"{who}, {year}"
