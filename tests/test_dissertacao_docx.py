"""Testes da Onda 2: dissertação/TCC ABNT no MCP, exportação Word (.docx) e criação de projeto no site."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


class DissertationAndTccFlowTest(unittest.TestCase):
    def test_templates_e_modos_incluem_dissertacao_e_tcc(self):
        import mcp_flow as flow
        self.assertIn("abnt-dissertacao", flow.TEMPLATES)
        self.assertIn("abnt-tcc", flow.TEMPLATES)
        self.assertTrue(flow.TEMPLATES["abnt-dissertacao"]["usa_capitulos"])
        self.assertIn("dissertacao", flow.MODES)
        self.assertIn("tcc", flow.MODES)

    def test_validate_latex_aceita_capitulos_em_dissertacao(self):
        import mcp_flow as flow
        body = (
            "\\begin{resumo}\nResumo da dissertação sobre autonomia na pesquisa.\n\\end{resumo}\n\n"
            "\\chapter{Introdução}\n" + ("Texto introdutório fundamentado em \\citeonline{freire1996autonomia}. " * 15) + "\n\n"
            "\\chapter{Referencial teórico}\n" + ("Discussão teórica crítica \\cite{freire1996autonomia}. " * 15) + "\n\n"
            "\\chapter{Metodologia}\n" + ("Design Science Research aplicada no MPIE \\cite{freire1996autonomia}. " * 15) + "\n"
        )
        res = flow.validate_latex(body, {"freire1996autonomia"}, 200, "abnt-dissertacao")
        self.assertTrue(res["ok"], res["erros"])

    def test_worker_assemble_dissertacao_e_tcc_promove_secoes_para_capitulos(self):
        import mcp_jobs
        body = "\\begin{resumo}\nTexto.\n\\end{resumo}\n\\section{Introdução}\nParágrafo.\n\\subsection{Contexto}\nSub."
        tex_diss = mcp_jobs.assemble({"title": "Minha Dissertação", "template": "abnt-dissertacao", "language": "pt-BR"}, body)
        self.assertIn("\\documentclass[12pt,oneside,a4paper,brazil]{abntex2}", tex_diss)
        self.assertIn("\\tipotrabalho{Dissertação de Mestrado}", tex_diss)
        self.assertIn("\\imprimircapa", tex_diss)
        self.assertIn("\\tableofcontents*", tex_diss)
        self.assertIn("\\chapter{Introdução}", tex_diss)
        self.assertIn("\\section{Contexto}", tex_diss)

        tex_tcc = mcp_jobs.assemble({"title": "Meu TCC", "template": "abnt-tcc", "language": "pt-BR"},
                                    "\\begin{resumo}\nTexto.\n\\end{resumo}\n\\chapter{Introdução}\nOk.")
        self.assertIn("\\tipotrabalho{Trabalho de Conclusão de Curso (TCC)}", tex_tcc)
        self.assertIn("\\chapter{Introdução}", tex_tcc)


class DocxExportTest(unittest.TestCase):
    def test_build_docx_gera_ooxml_valido_com_citacoes_e_referencias_abnt(self):
        import docx_export
        refs = [{
            "key": "freire1996autonomia",
            "type": "book",
            "how": "confirmada_pelo_pesquisador",
            "fields": {
                "author": "Paulo Freire",
                "title": "Pedagogia da autonomia",
                "publisher": "Paz e Terra",
                "year": "1996",
                "doi": "10.1234/freire1996",
            },
        }]
        tex = (
            "\\begin{document}\n"
            "\\begin{resumo}\nEstudo sobre escrita científica.\n\\end{resumo}\n"
            "\\chapter{Introdução}\n"
            "Conforme \\citeonline{freire1996autonomia}, ensinar exige pesquisa \\cite{freire1996autonomia}.\n"
            "\\section{Problema}\n"
            "\\item Primeira barreira observada.\n"
            "\\end{document}\n"
        )
        raw = docx_export.build_docx("Scriptorium MPIE", tex, refs, is_final=False, work_label="Dissertação de mestrado")
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            names = set(zf.namelist())
            self.assertTrue({"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"} <= names)
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            # Garante XML bem formado.
            ET.fromstring(doc_xml)
        self.assertIn("RASCUNHO PARA ORIENTAÇÃO", doc_xml)
        self.assertIn("Freire (1996)", doc_xml)
        self.assertIn("(FREIRE, 1996)", doc_xml)
        self.assertIn("FREIRE, Paulo. Pedagogia da autonomia.", doc_xml)
        self.assertIn("https://doi.org/10.1234/freire1996", doc_xml)


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class SiteProjectAndDocxRouteTest(unittest.TestCase):
    def test_criar_projeto_dissertacao_e_baixar_word_e_pacote(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from mcp_server import Store
        from mcp_site_api import make_mcp_site_router

        class FakeSnap:
            def __init__(self, data):
                self._d = data
                self.exists = data is not None

            def to_dict(self):
                return self._d

        class FakeDoc:
            def __init__(self, store, key):
                self.store, self.key = store, key

            def get(self):
                return FakeSnap(self.store.get(self.key))

            def create(self, rec):
                self.store[self.key] = dict(rec)

            def set(self, rec):
                self.store[self.key] = dict(rec)

            def update(self, fields):
                self.store[self.key] = {**self.store[self.key], **fields}

        class FakeCol:
            def __init__(self, store):
                self.store = store

            def document(self, key):
                return FakeDoc(self.store, key)

            def where(self, field, _op, val):
                self._filter = (field, val)
                return self

            def limit(self, _n):
                return self

            def stream(self):
                f, v = getattr(self, "_filter", (None, None))
                return [FakeSnap(d) for d in self.store.values() if f is None or d.get(f) == v]

        class FakeDB:
            def __init__(self):
                self.cols = {"library_items": {}, "mcp_projects": {}, "research_jobs": {}, "mcp_tokens": {}}

            def collection(self, name):
                return FakeCol(self.cols.setdefault(name, {}))

        class FakeBlob:
            def __init__(self, files, name):
                self.files, self.name = files, name

            def exists(self):
                return self.name in self.files

            def download_as_bytes(self):
                if self.name not in self.files:
                    raise KeyError(self.name)
                return self.files[self.name]

            def upload_from_string(self, data, content_type=None):
                self.files[self.name] = data if isinstance(data, bytes) else data.encode("utf-8")

        class FakeBucket:
            def __init__(self):
                self.files = {}

            def blob(self, name):
                return FakeBlob(self.files, name)

        db, bucket = FakeDB(), FakeBucket()
        sid = "a" * 32
        db.cols["library_items"][sid] = {
            "id": sid, "owner_uid": "ana", "status": "active", "name": "freire.pdf",
            "format": "pdf", "sha256": "b" * 64, "size": 1000,
            "object_path": f"library/ana/{sid}/freire.pdf",
        }
        launched = []
        store = Store(db, bucket, lambda j, u, m: launched.append((j, u, m)), lambda _i: True)
        app = FastAPI()
        app.include_router(make_mcp_site_router(store, lambda: {"uid": "ana", "email": "ana@ifrs.edu.br"}, "https://scriptoriummpie.web.app"))
        client = TestClient(app)

        # 1) Cria dissertação direto pelo site
        r = client.post("/api/mcp-conta/projetos", json={
            "titulo": "Scriptorium no MPIE",
            "pergunta": "Como democratizar a escrita de dissertações para não nativos digitais?",
            "fontes": [sid],
            "tipo": "dissertacao",
            "modelo": "abnt-artigo",  # deve promover automaticamente para abnt-dissertacao
        })
        self.assertEqual(r.status_code, 201, r.text)
        pid = r.json()["projeto"]
        self.assertEqual(db.cols["mcp_projects"][pid]["template"], "abnt-dissertacao")
        self.assertEqual(len(launched), 1)

        # 2) Simula compilação já feita (.tex + references.json) e baixa Word .docx + pacote ZIP
        prefix = f"mcp/ana/{pid}"
        bucket.files[prefix + "/references.json"] = json.dumps([{
            "key": "freire1996autonomia", "type": "book", "how": "doi",
            "fields": {"author": "Paulo Freire", "title": "Pedagogia da autonomia", "year": "1996"},
        }]).encode("utf-8")
        bucket.files[prefix + "/final/scriptorium.tex"] = (
            "\\begin{document}\\chapter{Introdução}Texto \\cite{freire1996autonomia}.\\end{document}"
        ).encode("utf-8")
        db.cols["mcp_projects"][pid]["status"] = "concluido"
        db.cols["mcp_projects"][pid]["files"] = ["scriptorium.pdf", "scriptorium.tex"]
        db.cols["mcp_projects"][pid]["compile_report"] = {"versao": "final"}

        rdoc = client.get(f"/api/mcp-conta/projetos/{pid}/arquivos/scriptorium.docx")
        self.assertEqual(rdoc.status_code, 200)
        self.assertIn("wordprocessingml", rdoc.headers["content-type"])
        with zipfile.ZipFile(io.BytesIO(rdoc.content), "r") as zf:
            self.assertIn("(FREIRE, 1996)", zf.read("word/document.xml").decode("utf-8"))

        rzip = client.get(f"/api/mcp-conta/projetos/{pid}/pacote-orientacao.zip")
        self.assertEqual(rzip.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(rzip.content), "r") as zf:
            self.assertIn("scriptorium.docx", zf.namelist())
            self.assertIn("resumo_para_orientacao.md", zf.namelist())


if __name__ == "__main__":
    unittest.main()
