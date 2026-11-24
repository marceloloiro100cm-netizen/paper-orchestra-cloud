"""Extração estruturada de documentos com localizador de página (M01 e M02).

Origem: R37 (PyMuPDF) para PDFs; R03/R04 (Docling) ficam como evolução depois
do corpus de avaliação, como prevê o plano V2 ("fallback com PyMuPDF atual").
Plano: Scriptorium V2, módulos M01 "Parsing estrutural" e M02 "Evidência
visual por página e coordenadas".

Saída (document.json, schema scriptorium.document/1):
- pages: índice (1-based), dimensões, rotação, caracteres e sinal de OCR (M23);
- blocks: texto de cada bloco, tipo (heading/paragraph), página e bbox
  normalizada [x0, y0, x1, y1] em frações da página (0 a 1, origem no canto
  superior esquerdo da página sem rotação).

Regras do plano respeitadas:
- não inventar coordenadas: DOCX, TXT, BIB e RIS não têm página nem bbox;
- nada de truncamento silencioso: pages_total e pages_processed ficam registrados;
- texto passa pelo document_guard (M13) bloco a bloco.
"""
from __future__ import annotations

import re
from io import BytesIO
from statistics import median
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from document_guard import guard_text
from ocr_router import classify_page, ocr_summary

SCHEMA = "scriptorium.document/1"
PARSER_VERSION = "pymupdf-blocks-1"
TEXT_PARSER_VERSION = "plain-paragraphs-1"
MAX_PDF_PAGES = 400
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADING_RATIO = 1.15
MAX_HEADING_CHARS = 200


def _clean(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text or "").strip()


def _guard_blocks(blocks: list[dict]) -> dict:
    """Aplica o document_guard a cada bloco e devolve o resumo agregado."""
    totals = {"neutralized_delimiters": 0, "removed_invisible_characters": 0,
              "removed_control_characters": 0}
    flags: dict[str, int] = {}
    for block in blocks:
        guarded = guard_text(block["text"])
        block["text"] = guarded.text
        summary = guarded.summary()
        for key in totals:
            totals[key] += summary[key]
        for flag in summary["risk_flags"]:
            flags[flag["code"]] = flags.get(flag["code"], 0) + flag["count"]
    risky = totals["neutralized_delimiters"] or flags or totals["removed_invisible_characters"] > 20
    return {"guard_version": "document_guard/1",
            "risk_level": "attention" if risky else "none_detected",
            "risk_flags": [{"code": k, "count": v} for k, v in sorted(flags.items())],
            **totals}


def _mark_headings(blocks: list[dict]) -> None:
    sized = [b for b in blocks if b.get("font_size")]
    if not sized:
        return
    # Tamanho de corpo = mediana ponderada por caracteres (aproximação simples).
    weighted = [b["font_size"] for b in sized for _ in range(max(1, len(b["text"]) // 40))]
    body = median(weighted)
    for block in sized:
        short = len(block["text"]) <= MAX_HEADING_CHARS
        bigger = block["font_size"] >= body * HEADING_RATIO
        bold_line = block.get("bold") and short and not block["text"].endswith((".", ";", ","))
        block["kind"] = "heading" if short and (bigger or bold_line) else "paragraph"


def extract_pdf(data: bytes, max_pages: int = MAX_PDF_PAGES) -> dict:
    from pdf_backend import fitz  # PyMuPDF (R37)
    pages, blocks, warnings = [], [], []
    with fitz.open(stream=data, filetype="pdf") as doc:
        total = doc.page_count
        if total > max_pages:
            warnings.append(f"Documento com {total} páginas: processadas as primeiras {max_pages}.")
        for index in range(min(total, max_pages)):
            page = doc[index]
            # Coordenadas do PyMuPDF são relativas à página sem rotação.
            width = page.cropbox.width or page.rect.width
            height = page.cropbox.height or page.rect.height
            page_text = []
            for raw in page.get_text("dict").get("blocks", []):
                if raw.get("type") != 0:
                    continue
                spans = [s for line in raw.get("lines", []) for s in line.get("spans", [])]
                text = _clean(" ".join(
                    "".join(s.get("text", "") for s in line.get("spans", []))
                    for line in raw.get("lines", [])))
                if not text:
                    continue
                sizes = [s.get("size", 0) for s in spans if s.get("text", "").strip()]
                bold = bool(spans) and all(int(s.get("flags", 0)) & 16 for s in spans if s.get("text", "").strip())
                x0, y0, x1, y1 = raw["bbox"]
                bbox = [round(min(max(v, 0.0), 1.0), 4) for v in
                        (x0 / width, y0 / height, x1 / width, y1 / height)]
                blocks.append({"id": f"p{index + 1}-b{len(blocks):05d}", "page": index + 1,
                               "bbox": bbox, "text": text, "kind": "paragraph",
                               "font_size": round(median(sizes), 2) if sizes else None,
                               "bold": bold})
                page_text.append(text)
            joined = " ".join(page_text)
            images = len(page.get_images(full=False))
            pages.append({"index": index + 1, "width": round(width, 2), "height": round(height, 2),
                          "rotation": page.rotation, "text_chars": len(joined),
                          "image_count": images,
                          "needs_ocr": classify_page(len(joined), images, joined[:4000])})
        parser = {"name": "PyMuPDF", "version": getattr(fitz, "VersionBind", "desconhecida"),
                  "upstream_id": "R37"}
    if any(p["rotation"] for p in pages):
        warnings.append("Há páginas rotacionadas: a bbox segue a página sem rotação.")
    _mark_headings(blocks)
    return _document("pdf", parser, PARSER_VERSION, pages, blocks, warnings, total)


def extract_docx(data: bytes) -> dict:
    blocks = []
    with ZipFile(BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024:
            raise ValueError("Arquivo DOCX muito grande.")
        root = ET.fromstring(archive.read("word/document.xml"))
    for paragraph in root.iter(WORD_NS + "p"):
        text = _clean("".join(n.text or "" for n in paragraph.iter(WORD_NS + "t")))
        if not text:
            continue
        style = paragraph.find(f"{WORD_NS}pPr/{WORD_NS}pStyle")
        style_name = (style.get(WORD_NS + "val") if style is not None else "") or ""
        heading = bool(re.match(r"(heading|t[ií]tulo|ttulo)\s*\d", style_name, re.IGNORECASE))
        blocks.append({"id": f"b{len(blocks):05d}", "page": None, "bbox": None, "text": text,
                       "kind": "heading" if heading else "paragraph"})
    return _document("docx", {"name": "zipfile+ElementTree", "version": "stdlib"},
                     TEXT_PARSER_VERSION, [], blocks, [], None)


def extract_plain(data: bytes, fmt: str) -> dict:
    text = data.decode("utf-8-sig", errors="replace")
    blocks = [{"id": f"b{i:05d}", "page": None, "bbox": None, "text": _clean(part.replace("\n", " ")),
               "kind": "paragraph"}
              for i, part in enumerate(p for p in re.split(r"\n\s*\n", text) if p.strip())]
    return _document(fmt, {"name": "texto", "version": "stdlib"}, TEXT_PARSER_VERSION, [], blocks, [], None)


def _document(fmt, parser, version, pages, blocks, warnings, pages_total) -> dict:
    guard = _guard_blocks(blocks)
    blocks = [b for b in blocks if b["text"].strip()]
    return {
        "schema": SCHEMA, "format": fmt, "parser": parser, "parser_version": version,
        "pages_total": pages_total, "pages_processed": len(pages) if pages else None,
        "pages": pages, "blocks": blocks, "warnings": warnings,
        "ocr": ocr_summary(pages), "guard": guard,
    }


def extract_document(data: bytes, fmt: str) -> dict:
    if fmt == "pdf":
        return extract_pdf(data)
    if fmt == "docx":
        return extract_docx(data)
    if fmt in {"txt", "bib", "ris"}:
        return extract_plain(data, fmt)
    raise ValueError("Formato de arquivo não suportado.")


def parser_version_for(fmt: str) -> str:
    return PARSER_VERSION if fmt == "pdf" else TEXT_PARSER_VERSION
