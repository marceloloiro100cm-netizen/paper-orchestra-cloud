"""Exportação de manuscritos LaTeX do Scriptorium para Word (.docx) editável na norma do projeto.

ABNT é o padrão. Com `formato` (formatos/<id>/formato.json), margens, espaçamento, recuo,
títulos, citações e referências seguem a norma escolhida (ex.: APA 7 via apa_refs.py).

Zero dependências externas (usa apenas zipfile + xml.sax.saxutils da biblioteca padrão),
para que orientadores e estudantes não nativos digitais possam revisar com Controle de
Alterações no Microsoft Word, LibreOffice Writer ou Google Docs.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

import apa_refs

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# Estilos ABNT: Times New Roman 12pt, espaçamento 1,5 (360 twips), margens 3cm/3cm/2cm/2cm.
STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:sz w:val="24"/><w:szCs w:val="24"/>
      <w:lang w:val="pt-BR"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:line="360" w:lineRule="auto" w:after="120"/>
      <w:jc w:val="both"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="240" w:line="360" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:pPr><w:spacing w:before="360" w:after="160" w:line="360" w:lineRule="auto"/><w:jc w:val="left"/><w:keepNext/></w:pPr>
    <w:rPr><w:b/><w:caps/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:pPr><w:spacing w:before="280" w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="left"/><w:keepNext/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:pPr><w:spacing w:before="200" w:after="80" w:line="360" w:lineRule="auto"/><w:jc w:val="left"/><w:keepNext/></w:pPr>
    <w:rPr><w:b/><w:i/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Reference">
    <w:name w:val="Reference"/>
    <w:pPr><w:spacing w:line="240" w:lineRule="auto" w:after="160"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Notice">
    <w:name w:val="Notice"/>
    <w:pPr><w:spacing w:line="260" w:lineRule="auto" w:before="120" w:after="200"/><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
</w:styles>"""

CITE_ONLINE = re.compile(r"\\(?:citeonline|citet|citealt|citeauthor)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")
CITE_PAREN = re.compile(r"\\(?:cite|citep|citealp|citeyear|citeyearpar|apud)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")
# APA (biblatex): guarda os argumentos opcionais para página e "como citado em".
APA_NARRATIVE = re.compile(r"\\(?:textcite|Textcite|citeonline|citet|citealt|citeauthor)\*?((?:\[[^\]]*\]){0,2})\{([^}]*)\}")
APA_PAREN = re.compile(r"\\(?:parencite|Parencite|autocite|cite|citep|citealp|citeyear|citeyearpar)\*?"
                       r"((?:\[[^\]]*\]){0,2})\{([^}]*)\}")


def _surname(author_raw: str) -> str:
    first = re.split(r"\s+and\s+|;", (author_raw or "").strip(), maxsplit=1)[0].strip()
    if not first:
        return ""
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else first


def _cite_label(keys_str: str, ref_map: dict[str, dict], online: bool) -> str:
    parts = []
    for k in [x.strip() for x in keys_str.split(",") if x.strip()]:
        ref = ref_map.get(k)
        fields = (ref or {}).get("fields") or {}
        author = str(fields.get("author") or "").strip()
        year = str(fields.get("year") or "s.d.").strip() or "s.d."
        who = _surname(author) or k
        multi = len(re.split(r"\s+and\s+|;", author)) > 3 if author else False
        if online:
            label = f"{who} et al. ({year})" if multi else f"{who} ({year})"
        else:
            label = f"{who.upper()} et al., {year}" if multi else f"{who.upper()}, {year}"
        parts.append(label)
    if not parts:
        return ""
    return ", ".join(parts) if online else "(" + "; ".join(parts) + ")"


def _apa_cite(opts: str, keys_str: str, ref_map: dict[str, dict], narrative: bool, language: str) -> str:
    args = [a.replace("~", " ").strip() for a in re.findall(r"\[([^\]]*)\]", opts or "")]
    pre, post = (args[0], args[1]) if len(args) == 2 else ("", args[0] if args else "")
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    labels = [apa_refs.cite_label(ref_map.get(k), k, narrative=narrative, language=language) for k in keys]
    if not labels:
        return ""
    if narrative:
        text = ", ".join(labels)
        return text[:-1] + f", {post})" if post and text.endswith(")") else text
    inner = "; ".join(sorted(labels, key=str.lower))
    return "(" + (pre + " " if pre else "") + inner + (", " + post if post else "") + ")"


def _clean_latex_inline(text: str, ref_map: dict[str, dict], cite_style: str = "abnt",
                        language: str = "pt-BR") -> str:
    s = re.sub(r"(?m)(?<!\\)%.*$", "", text or "")
    # \par vira espaço antes de desembrulhar \textit{...}, senão "\par\textit{X}" some inteiro.
    s = re.sub(r"\\par(?![A-Za-z])\s*", " ", s)
    if cite_style == "apa7":
        s = APA_NARRATIVE.sub(lambda m: _apa_cite(m.group(1), m.group(2), ref_map, True, language), s)
        s = APA_PAREN.sub(lambda m: _apa_cite(m.group(1), m.group(2), ref_map, False, language), s)
    s = CITE_ONLINE.sub(lambda m: _cite_label(m.group(1), ref_map, online=True), s)
    s = CITE_PAREN.sub(lambda m: _cite_label(m.group(1), ref_map, online=False), s)
    s = s.replace("``", "\u201c").replace("''", "\u201d")
    s = s.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\$", "$").replace("\\#", "#")
    s = s.replace("~", " ").replace("\\\\", "\n")
    # Desembrulha comandos de ênfase comuns preservando conteúdo.
    for _ in range(3):
        s = re.sub(r"\\(?:textbf|textit|emph|underline|texttt|textsc|text)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:label|ref|pageref|footnote|caption)\*?\{[^{}]*\}", "", s)
    s = re.sub(r"\\(?:begin|end)\{(?:itemize|enumerate|quote|quotation|center|figure|table|tabular)\}(?:\[[^\]]*\])?(?:\{[^}]*\})?", "", s)
    s = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", "", s)
    s = s.replace("{", "").replace("}", "")
    return " ".join(s.split())


def _format_abnt_reference(ref: dict) -> str:
    fields = (ref or {}).get("fields") or {}
    author = str(fields.get("author") or "").strip()
    title = str(fields.get("title") or ref.get("key") or "Sem título").strip().rstrip(".")
    year = str(fields.get("year") or "s.d.").strip()
    venue = (fields.get("journal") or fields.get("booktitle") or fields.get("school")
             or fields.get("publisher") or fields.get("institution") or "").strip().rstrip(".")
    volume = str(fields.get("volume") or "").strip()
    number = str(fields.get("number") or "").strip()
    pages = str(fields.get("pages") or "").strip()
    doi = str(fields.get("doi") or "").strip()
    pieces = []
    if author:
        authors = [a.strip() for a in re.split(r"\s+and\s+|;", author) if a.strip()]
        fmt_authors = []
        for a in authors[:3]:
            if "," in a:
                sn, rest = a.split(",", 1)
                fmt_authors.append(f"{sn.strip().upper()}, {rest.strip()}")
            else:
                toks = a.split()
                if len(toks) > 1:
                    fmt_authors.append(f"{toks[-1].upper()}, {' '.join(toks[:-1])}")
                else:
                    fmt_authors.append(a.upper())
        joined = "; ".join(fmt_authors) + (" et al." if len(authors) > 3 else "")
        pieces.append(joined.rstrip(".") + ".")
    pieces.append(f"{title}.")
    if venue:
        extra = []
        if volume:
            extra.append(f"v. {volume}")
        if number:
            extra.append(f"n. {number}")
        if pages:
            extra.append(f"p. {pages}")
        tail = (", " + ", ".join(extra)) if extra else ""
        pieces.append(f"{venue}{tail}, {year}.")
    else:
        pieces.append(f"{year}.")
    if doi:
        doi_clean = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
        pieces.append(f"DOI: https://doi.org/{doi_clean}.")
    return " ".join(pieces)


def _xml_paragraph(text: str, style: str = "Normal", indent_first: bool = False, first_line: int = 709) -> str:
    clean = escape((text or "").strip())
    if not clean:
        return ""
    ppr = [f'<w:pStyle w:val="{style}"/>']
    if indent_first and style == "Normal":
        # Recuo de primeira linha: ABNT 1,25 cm (~709 twips); outras normas pelo formato.json.
        ppr.append(f'<w:ind w:firstLine="{first_line}"/>')
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr><w:r><w:t xml:space="preserve">{clean}</w:t></w:r></w:p>'


def _xml_runs_paragraph(runs: list[tuple[str, bool]], style: str = "Reference") -> str:
    """Parágrafo com trechos em itálico (título do periódico, volume, livro)."""
    parts = []
    for text, italic in runs:
        if not text:
            continue
        rpr = "<w:rPr><w:i/></w:rPr>" if italic else ""
        parts.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')
    if not parts:
        return ""
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{"".join(parts)}</w:p>'


def _twips(cm: float) -> int:
    return round(float(cm) * 567)


def _styles_xml(word: dict | None) -> str:
    """ABNT usa STYLES_XML como está; outras normas trocam fonte, espaçamento e títulos."""
    if not word or word.get("referencias", "abnt") == "abnt":
        return STYLES_XML
    line = str(round(240 * float(word.get("espacamento", 1.5))))
    size = str(round(2 * float(word.get("tamanho_pt", 12))))
    font = escape(str(word.get("fonte") or "Times New Roman"), {'"': "&quot;"})
    hanging = str(_twips(word.get("recuo_cm", 1.27)))
    xml = STYLES_XML.replace('w:line="360"', f'w:line="{line}"').replace('w:after="120"/>', 'w:after="0"/>', 1)
    xml = xml.replace("Times New Roman", font).replace('<w:sz w:val="24"/><w:szCs w:val="24"/>',
                                                       f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    xml = xml.replace('<w:jc w:val="both"/>', '<w:jc w:val="left"/>', 1)
    # APA: nível 1 centralizado em negrito (sem caixa alta); referências com recuo deslocado.
    xml = xml.replace('<w:jc w:val="left"/><w:keepNext/></w:pPr>\n    <w:rPr><w:b/><w:caps/>',
                      '<w:jc w:val="center"/><w:keepNext/></w:pPr>\n    <w:rPr><w:b/>', 1)
    xml = xml.replace('<w:pPr><w:spacing w:line="240" w:lineRule="auto" w:after="160"/><w:jc w:val="left"/></w:pPr>',
                      f'<w:pPr><w:spacing w:line="{line}" w:lineRule="auto" w:after="0"/>'
                      f'<w:ind w:left="{hanging}" w:hanging="{hanging}"/><w:jc w:val="left"/></w:pPr>', 1)
    return xml


def _extract_body_blocks(tex: str, ref_map: dict[str, dict], cite_style: str = "abnt",
                         language: str = "pt-BR", abstract_heading: str = "Abstract") -> list[tuple[str, str]]:
    """Extrai blocos estruturados (estilo, texto) de um .tex completo ou corpo LaTeX."""
    src = tex or ""
    if "\\begin{document}" in src:
        src = src.split("\\begin{document}", 1)[1]
    if "\\end{document}" in src:
        src = src.split("\\end{document}", 1)[0]
    if "\\postextual" in src:
        src = src.split("\\postextual", 1)[0]
    src = re.sub(r"\\begin\{(titlingpage|titlepage)\}.*?\\end\{\1\}", "", src, flags=re.S)
    src = re.sub(r"\\begin\{center\}\\bfseries[^\n]*?\\end\{center\}", "", src)
    src = re.sub(r"(?m)^\\(?:selectlanguage|imprimircapa|maketitle|tableofcontents\*?|textual|bibliographystyle|bibliography|printbibliography|clearpage|setcounter)\b.*$", "", src)
    clean = lambda text: _clean_latex_inline(text, ref_map, cite_style, language)

    blocks: list[tuple[str, str]] = []
    # Resumo / Abstract
    for env_name, heading in (("resumo", "Resumo"), ("abstract", abstract_heading)):
        m = re.search(rf"\\begin\{{{env_name}\}}(.*?)\\end\{{{env_name}\}}", src, flags=re.S)
        if m:
            blocks.append(("Heading1", heading))
            for para in re.split(r"\n\s*\n", m.group(1)):
                t = clean(para)
                if t:
                    blocks.append(("Normal", t))
            src = src[:m.start()] + "\n" + src[m.end():]

    # Divide o restante preservando headings (\chapter, \section, \subsection, \subsubsection) e \item.
    token_re = re.compile(r"\\(chapter|section|subsection|subsubsection)\*?\{([^}]*)\}|\\item\s+([^\n]+)")
    pos = 0
    for m in token_re.finditer(src):
        before = src[pos:m.start()]
        for para in re.split(r"\n\s*\n", before):
            t = clean(para)
            if t:
                blocks.append(("Normal", t))
        if m.group(1):
            level = m.group(1)
            style = {"chapter": "Heading1", "section": "Heading1",
                     "subsection": "Heading2", "subsubsection": "Heading3"}[level]
            if "\\chapter" in src and level == "section":
                style = "Heading2"
            elif "\\chapter" in src and level == "subsection":
                style = "Heading3"
            heading_txt = clean(m.group(2))
            if heading_txt:
                blocks.append((style, heading_txt))
        elif m.group(3):
            item_txt = clean(m.group(3))
            if item_txt:
                blocks.append(("Normal", "• " + item_txt))
        pos = m.end()
    for para in re.split(r"\n\s*\n", src[pos:]):
        t = clean(para)
        if t:
            blocks.append(("Normal", t))
    return blocks


def build_docx(title: str, tex: str, refs: list[dict] | None = None, *,
               is_final: bool = True, work_label: str = "Artigo científico",
               formato: dict | None = None, idioma: str = "pt-BR") -> bytes:
    """Gera bytes de um arquivo Word (.docx) editável; ABNT sem `formato`, senão a norma indicada."""
    word = (formato or {}).get("word") or {}
    style_refs = word.get("referencias", "abnt")
    norma = (formato or {}).get("familia") or "ABNT"
    first_line = _twips(word.get("recuo_cm", 1.25)) if word else 709
    abstract_heading = "Abstract" if not formato or idioma == "en" else "Resumo"
    ref_list = list(refs or [])
    ref_map = {str(r.get("key") or ""): r for r in ref_list if r.get("key")}
    paragraphs = []
    if not is_final:
        paragraphs.append(_xml_paragraph(
            "RASCUNHO PARA ORIENTAÇÃO — Versão preliminar gerada pelo Scriptorium MPIE (conferir referências pendentes antes da entrega final).",
            style="Notice",
        ))
    paragraphs.append(_xml_paragraph(title or "Manuscrito Scriptorium MPIE", style="Title"))
    paragraphs.append(_xml_paragraph(f"{work_label} · Documento editável em padrão {norma} (Scriptorium MPIE)", style="Notice"))

    for style, text in _extract_body_blocks(tex, ref_map, style_refs, idioma, abstract_heading):
        is_bullet = text.startswith("• ")
        paragraphs.append(_xml_paragraph(text, style=style, indent_first=(style == "Normal" and not is_bullet),
                                         first_line=first_line))

    if ref_list:
        paragraphs.append(_xml_paragraph("References" if idioma == "en" and formato else "Referências", style="Heading1"))
        if style_refs == "apa7":
            for ref in sorted(ref_list, key=apa_refs.sort_key):
                paragraphs.append(_xml_runs_paragraph(apa_refs.reference_runs(ref, idioma)))
        else:
            formatted = sorted((_format_abnt_reference(r) for r in ref_list), key=lambda s: s.lower())
            for line in formatted:
                paragraphs.append(_xml_paragraph(line, style="Reference"))

    # Margens ABNT A4: superior 3cm (1701), esquerda 3cm (1701), inferior 2cm (1134), direita 2cm (1134).
    margins = {"superior": 3, "direita": 2, "inferior": 2, "esquerda": 3, **(word.get("margens_cm") or {})}
    top, right, bottom, left = (_twips(margins[k]) for k in ("superior", "direita", "inferior", "esquerda"))
    sect_pr = (
        '<w:sectPr>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        f'<w:pgMar w:top="{top}" w:right="{right}" w:bottom="{bottom}" w:left="{left}" w:header="708" w:footer="708" w:gutter="0"/>'
        '</w:sectPr>'
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(p for p in paragraphs if p)}{sect_pr}</w:body>'
        '</w:document>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES.encode("utf-8"))
        zf.writestr("_rels/.rels", RELS.encode("utf-8"))
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS.encode("utf-8"))
        zf.writestr("word/styles.xml", _styles_xml(word).encode("utf-8"))
        zf.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buf.getvalue()
