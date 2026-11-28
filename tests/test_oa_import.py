"""Importação de PDFs de acesso aberto por DOI ou link. Sem rede."""
import json
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))
import oa_import  # noqa: E402
from test_biblioteca_exportacao import DB, Bucket, endpoint  # noqa: E402


def resolver_for(mapping):
    def resolve(host, port, proto=None):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in mapping.get(host, [])]
    return resolve


class SafetyTest(unittest.TestCase):
    def test_private_and_metadata_addresses_are_blocked(self):
        resolve = resolver_for({"ok.org": ["93.184.216.34"], "meta": ["169.254.169.254"],
                                "local": ["127.0.0.1"], "mixed": ["93.184.216.34", "10.0.0.5"]})
        self.assertTrue(oa_import.public_host("ok.org", resolve))
        for host in ("meta", "local", "mixed", "nada"):
            self.assertFalse(oa_import.public_host(host, resolve))

    def test_only_https_public(self):
        resolve = resolver_for({"meta": ["169.254.169.254"]})
        with self.assertRaises(ValueError):
            oa_import.safe_get("http://ok.org/a.pdf", 100, "*/*", resolve)
        with self.assertRaises(ValueError):
            oa_import.safe_get("https://meta/computeMetadata/v1/", 100, "*/*", resolve)


WORK = {"id": "https://openalex.org/W1", "title": "Ensino médio integrado: travessia", "publication_year": 2013,
        "authorships": [{"author": {"display_name": "Dante Henrique Moura"}}],
        "open_access": {"is_oa": True},
        "best_oa_location": {"pdf_url": "https://revista.org/landing", "license": "cc-by-nc"},
        "locations": [{"pdf_url": "https://revista.org/artigo.pdf"}]}


def fake_fetch(url, max_bytes, accept):
    if url.startswith(oa_import.OPENALEX):
        if "10.9999" in url:
            raise ValueError("HTTP 404")
        return json.dumps(WORK).encode()
    if url.endswith("landing"):
        return b"<html>pagina</html>"
    if url.endswith("ativo.pdf"):
        return b"%PDF-1.7 /JavaScript"
    return b"%PDF-1.7 conteudo"


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket = DB(), Bucket()
        self.route = endpoint(oa_import.make_oa_import_router(self.db, self.bucket, lambda: None, fetch=fake_fetch),
                              "/import-open-access")

    def test_doi_link_duplicates_and_errors(self):
        payload = oa_import.OpenAccessImport(items=[
            "https://doi.org/10.1590/S1517-97022013005000014", "10.1590/S1517-97022013005000014",
            "10.9999/naoexiste", "https://exemplo.org/ativo.pdf", "texto qualquer"])
        out = self.route(payload=payload, user={"uid": "u1"})
        statuses = [r["status"] for r in out["results"]]
        self.assertEqual(statuses, ["importado", "ja_existia", "falhou", "retido", "falhou"])
        item = out["results"][0]["library_item"]
        self.assertEqual(item["origin"]["doi"], "10.1590/S1517-97022013005000014")
        self.assertEqual(item["origin"]["license"], "cc-by-nc")
        self.assertEqual(item["origin"]["source_url"], "https://revista.org/artigo.pdf")  # pulou a página HTML
        self.assertTrue(item["name"].startswith("Moura 2013 Ensino médio integrado"))


    def test_follows_pdf_declared_by_article_page(self):
        pdf = b"%PDF-1.7 artigo da pagina"
        pages = {
            "https://anais.org/article/view/7/9": b'<meta name="citation_pdf_url" content="https://anais.org/article/download/7/9/1">',
            "https://anais.org/article/download/7/9/1": pdf,
            "https://loop.org/a": b'<meta name="citation_pdf_url" content="https://loop.org/b">',
            "https://loop.org/b": b'<meta name="citation_pdf_url" content="https://loop.org/c">',
            "https://loop.org/c": b'<meta name="citation_pdf_url" content="https://loop.org/d">',
            "https://loop.org/d": pdf,
            "https://interno.org/a": b'<meta name="citation_pdf_url" content="http://169.254.169.254/x">',
        }
        calls = []

        def fetch(url, limit, accept):
            calls.append(url)
            return pages[url]

        saved = []
        out = oa_import.import_one("https://anais.org/article/view/7/9", fetch,
                                   lambda name, data, origin: saved.append(origin) or {"id": "x", "name": name})
        self.assertEqual(saved[0]["source_url"], "https://anais.org/article/download/7/9/1")
        self.assertEqual(out["status"], "importado")
        # No máximo dois saltos a partir de páginas; nunca segue http (só https).
        self.assertEqual(oa_import.import_one("https://loop.org/a", fetch, lambda *a: {})["status"], "falhou")
        self.assertNotIn("https://loop.org/d", calls)
        self.assertEqual(oa_import.import_one("https://interno.org/a", fetch, lambda *a: {})["status"], "falhou")
        self.assertNotIn("http://169.254.169.254/x", calls)


    def test_openalex_http_pdf_is_tried_as_https(self):
        work = {"title": "T", "best_oa_location": {"pdf_url": "http://www.scielo.br/pdf/x.pdf"}, "locations": []}
        meta = oa_import.resolve_doi("10.1590/x", lambda *a: json.dumps(work).encode())
        self.assertEqual(meta["pdf_urls"], ["https://www.scielo.br/pdf/x.pdf"])


if __name__ == "__main__":
    unittest.main()
