#!/usr/bin/env python3
"""Monta um corpus de referência de PDFs de acesso aberto por tema (gate G2).

Origem: R09 (OpenAlex API) para a busca e os metadados; R37 (PyMuPDF) para
contar páginas e extrair o texto por página. Usado pelo workflow
.github/workflows/corpus-avaliacao.yml; não roda no Scriptorium.

Para cada busca de docs/corpus/temas.json, consulta o OpenAlex só por obras
de acesso aberto com link direto para PDF, baixa o arquivo, confere que é PDF
de verdade (assinatura %PDF, 3 a 80 páginas, até 15 MB) e grava:
- corpus/<arquivo>.pdf e textos/<arquivo>.json (texto por página);
- candidatos.json com título, autores, ano, DOI, revista, licença, tema e
  número de citações. Nada é enviado para o repositório: o workflow guarda a
  pasta como artefato temporário (1 dia).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
API = "https://api.openalex.org/works"
UA = "Scriptorium-corpus/1 (https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud; mailto:scriptorium@users.noreply.github.com)"
MAX_BYTES = 15 * 1024 * 1024


def get(url: str, timeout: int = 40, binary: bool = False):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*" if binary else "application/json"})
    with urlopen(req, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    return data if binary else json.loads(data.decode("utf-8"))


def slug(text: str, limit: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "documento"


def pdf_urls(work: dict) -> list[str]:
    urls = []
    for loc in [work.get("best_oa_location") or {}] + list(work.get("locations") or []):
        if loc and loc.get("pdf_url") and loc["pdf_url"] not in urls:
            urls.append(loc["pdf_url"])
    return urls


def search(query: str, per_page: int) -> list[dict]:
    params = {"search": query, "per-page": per_page,
              "filter": "open_access.is_oa:true,type:article|review|book-chapter|report,from_publication_date:2005-01-01",
              "mailto": "scriptorium@users.noreply.github.com"}
    return get(API + "?" + urlencode(params)).get("results", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--temas", type=Path, default=ROOT / "docs/corpus/temas.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-query", type=int, default=25)
    parser.add_argument("--keep-per-query", type=int, default=5)
    args = parser.parse_args()
    from pdf_backend import fitz
    (args.out / "corpus").mkdir(parents=True, exist_ok=True)
    (args.out / "textos").mkdir(exist_ok=True)
    temas = json.loads(args.temas.read_text(encoding="utf-8"))
    seen, kept = set(), []
    for tema in temas["temas"]:
        for query in tema["buscas"]:
            got = 0
            try:
                works = search(query, args.per_query)
            except Exception as error:
                print(f"[{tema['id']}] busca falhou: {query}: {error}", flush=True)
                continue
            for work in works:
                if got >= args.keep_per_query:
                    break
                wid = work.get("id", "")
                if wid in seen or not work.get("title"):
                    continue
                seen.add(wid)
                for url in pdf_urls(work):
                    try:
                        data = get(url, binary=True)
                    except Exception:
                        continue
                    if not data[:1024].lstrip().startswith(b"%PDF") or len(data) > MAX_BYTES:
                        continue
                    try:
                        with fitz.open(stream=data, filetype="pdf") as doc:
                            pages = [doc[i].get_text("text") for i in range(doc.page_count)]
                    except Exception:
                        continue
                    if not 3 <= len(pages) <= 80 or sum(len(p) for p in pages) < 4000:
                        continue
                    year = work.get("publication_year") or 0
                    first = ((work.get("authorships") or [{}])[0].get("author") or {}).get("display_name", "anon")
                    name = f"{tema['id']}_{slug(first.split()[-1] if first else 'anon', 20)}{year}_{slug(work['title'], 40)}.pdf"
                    (args.out / "corpus" / name).write_bytes(data)
                    (args.out / "textos" / (name[:-4] + ".json")).write_text(
                        json.dumps({"file": name, "pages": pages}, ensure_ascii=False), encoding="utf-8")
                    source = (work.get("primary_location") or {}).get("source") or {}
                    best = work.get("best_oa_location") or {}
                    kept.append({
                        "file": name, "tema": tema["id"], "busca": query, "openalex": wid,
                        "title": work["title"], "year": year, "doi": work.get("doi"),
                        "authors": [((a.get("author") or {}).get("display_name")) for a in (work.get("authorships") or [])][:8],
                        "venue": source.get("display_name"), "type": work.get("type"),
                        "language": work.get("language"), "cited_by": work.get("cited_by_count"),
                        "license": best.get("license"), "pdf_url": url, "pages": len(pages),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    })
                    got += 1
                    print(f"[{tema['id']}] ok {name} ({len(pages)} p.)", flush=True)
                    break
                time.sleep(0.3)
    (args.out / "candidatos.json").write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Total: {len(kept)} PDFs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
