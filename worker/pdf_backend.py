"""Ponto único de importação do PyMuPDF.

Origem: R37 em docs/upstreams.json. O PyMuPDF 2.x marca o nome antigo `fitz`
como obsoleto ("será removido"); o nome atual é `pymupdf`. O fallback mantém
compatibilidade com versões antigas que só expõem `fitz`.
"""
try:
    import pymupdf as fitz
except ImportError:  # versões antigas
    import fitz  # noqa: F401

__all__ = ["fitz"]
