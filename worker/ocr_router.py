"""Detecção de páginas que precisariam de OCR (M23, primeira parte).

Origem: R01 (código próprio). Plano: Scriptorium V2, módulo M23 "OCR seletivo e
documentos complexos". A execução de OCR (R18 olmOCR ou alternativa) ainda NÃO
está implementada: aqui só se mede a densidade de texto por página e se
sinaliza o que ficou sem texto extraível, para que a falha não seja silenciosa.
"""
from __future__ import annotations

OCR_ROUTER_VERSION = "ocr-router/1"
# Abaixo disso a página praticamente não tem texto selecionável.
MIN_TEXT_CHARS = 40
# Texto "quebrado" (fontes sem mapa Unicode) aparece como U+FFFD ou área privada.
MAX_GARBLED_RATIO = 0.10


def garbled_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(1 for c in text if c == "�" or "" <= c <= "")
    return bad / len(text)


def classify_page(text_chars: int, image_count: int, sample_text: str = "") -> str | None:
    """Motivo pelo qual a página precisaria de OCR, ou None."""
    if text_chars < MIN_TEXT_CHARS and image_count > 0:
        return "scanned_image"
    if text_chars < MIN_TEXT_CHARS:
        return "no_text"
    if garbled_ratio(sample_text) > MAX_GARBLED_RATIO:
        return "garbled_text"
    return None


def ocr_summary(pages: list[dict]) -> dict:
    flagged = [{"page": p["index"], "reason": p["needs_ocr"]} for p in pages if p.get("needs_ocr")]
    return {
        "router_version": OCR_ROUTER_VERSION,
        "pages_flagged": flagged,
        "ocr_available": False,
        "note": ("Páginas sinalizadas não entram no contexto dos agentes; OCR ainda não implementado."
                 if flagged else ""),
    }
