"""Fragmentação de documentos estruturados em trechos citáveis (M19 e M03).

Origem: R01 (código próprio). Plano: Scriptorium V2, módulos M19
"Granularidade inteligente de fragmentos" e M03 "Fragmentação e indexação".

Política section-paragraph-1:
- títulos abrem um novo trecho e entram no heading_path dos seguintes;
- parágrafos são agrupados até ~TARGET caracteres, sem cruzar títulos;
- parágrafo maior que MAX é dividido por frases;
- cada trecho guarda páginas e bboxes dos blocos de origem (quando existem),
  hash do texto e as versões de parser e de política.

Trocar a política exige nova versão (CHUNK_POLICY) e reindexação, nunca
alteração silenciosa: o manifesto de cada execução registra a versão usada.
"""
from __future__ import annotations

import hashlib
import re

CHUNK_POLICY = "section-paragraph-1"
TARGET_CHARS = 1200
MAX_CHARS = 2000
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ý0-9\"'(\[])")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, current = [], ""
    for sentence in SENTENCE_END.split(text):
        while len(sentence) > MAX_CHARS:  # frase gigante (tabela, lista sem pontuação)
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:MAX_CHARS])
            sentence = sentence[MAX_CHARS:]
        if current and len(current) + 1 + len(sentence) > TARGET_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def chunk_document(document: dict, source_id: str) -> list[dict]:
    excluded_pages = {p["index"] for p in document.get("pages", []) if p.get("needs_ocr")}
    chunks: list[dict] = []
    headings: list[tuple[float, str]] = []  # (tamanho, texto) do nível mais alto ao mais baixo
    pending: list[tuple[str, dict]] = []

    def heading_path() -> list[str]:
        return [text for _, text in headings][-3:]

    def flush():
        if not pending:
            return
        text = "\n".join(t for t, _ in pending).strip()
        if text:
            pages = sorted({b["page"] for _, b in pending if b.get("page")})
            locations = [{"page": b["page"], "bbox": b["bbox"]} for _, b in pending
                         if b.get("page") and b.get("bbox")]
            digest = _sha(text)
            index = len(chunks)
            chunks.append({
                "chunk_id": f"{source_id[:12]}-{index:04d}-{digest[:8]}",
                "source_id": source_id,
                "index": index,
                "heading_path": heading_path(),
                "text": text,
                "text_sha256": digest,
                "pages": [pages[0], pages[-1]] if pages else None,
                "locations": locations,
                "char_count": len(text),
                "chunk_policy": CHUNK_POLICY,
                "parser_version": document.get("parser_version"),
            })
        pending.clear()

    for block in document.get("blocks", []):
        if block.get("page") in excluded_pages:
            continue
        text = block["text"].strip()
        if not text:
            continue
        if block.get("kind") == "heading":
            flush()
            size = block.get("font_size") or 0.0
            # Título do mesmo nível ou acima substitui os mais profundos.
            while headings and headings[-1][0] <= size:
                headings.pop()
            headings.append((size, text))
            continue
        for piece in _split_long(text):
            current = sum(len(t) for t, _ in pending)
            if pending and current + len(piece) > TARGET_CHARS:
                flush()
            pending.append((piece, block))
    flush()
    return chunks
