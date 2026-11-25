#!/usr/bin/env python3
"""M01: compara o parser atual (PyMuPDF, R37) com o Docling (R03) no corpus.

Mede por documento: títulos detectados, tabelas encontradas (só o Docling extrai
tabelas), caracteres de texto e tempo. Roda no GitHub Actions (CPU); o Docling
não entra na imagem do worker por causa disso.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
from structured_extract import extract_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from docling.document_converter import DocumentConverter
    import docling
    converter = DocumentConverter()
    rows = []
    for path in sorted(args.corpus.glob("*.pdf"))[: args.limit]:
        t0 = time.time()
        doc = extract_document(path.read_bytes(), "pdf")
        mu_time = time.time() - t0
        mu_headings = sum(b.get("kind") == "heading" for b in doc["blocks"])
        mu_chars = sum(len(b["text"]) for b in doc["blocks"])
        t0 = time.time()
        try:
            result = converter.convert(str(path)).document
            dl_time = time.time() - t0
            texts = list(result.texts)
            dl_headings = sum(str(getattr(t, "label", "")).endswith(("section_header", "title")) for t in texts)
            dl_tables = len(result.tables)
            dl_chars = sum(len(getattr(t, "text", "") or "") for t in texts)
            error = None
        except Exception as exc:  # documento que o Docling não converte
            dl_time, dl_headings, dl_tables, dl_chars, error = time.time() - t0, None, None, None, type(exc).__name__
        rows.append({"file": path.name, "pymupdf": {"headings": mu_headings, "chars": mu_chars, "seconds": round(mu_time, 2)},
                     "docling": {"headings": dl_headings, "tables": dl_tables, "chars": dl_chars,
                                 "seconds": round(dl_time, 1), "error": error}})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    ok = [r for r in rows if r["docling"]["error"] is None]
    summary = {
        "docling_version": getattr(docling, "__version__", "?"), "documents": len(rows), "converted": len(ok),
        "tables_found_by_docling": sum(r["docling"]["tables"] or 0 for r in ok),
        "docs_with_tables": sum(1 for r in ok if r["docling"]["tables"]),
        "avg_seconds": {"pymupdf": round(sum(r["pymupdf"]["seconds"] for r in rows) / max(1, len(rows)), 2),
                        "docling": round(sum(r["docling"]["seconds"] for r in ok) / max(1, len(ok)), 1)},
        "headings_total": {"pymupdf": sum(r["pymupdf"]["headings"] for r in ok),
                           "docling": sum(r["docling"]["headings"] or 0 for r in ok)},
    }
    args.output.write_text(json.dumps({"summary": summary, "documents": rows}, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
