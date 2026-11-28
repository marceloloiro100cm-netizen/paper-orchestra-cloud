"""Ponto único de importação do PyMuPDF na API (M02: página com trecho destacado).

Origem: R37 (PyMuPDF, AGPL-3.0 ou licença comercial da Artifex). A API é um
serviço de rede: o código-fonte completo do Scriptorium é público em
https://github.com/marceloloiro100cm-netizen/scriptorium e o site
mostra esse link (exigência da AGPL-3.0, seção 13). Ver docs/upstreams.json.
"""
try:
    import pymupdf as fitz
except ImportError:  # versões antigas
    import fitz  # noqa: F401

__all__ = ["fitz"]
