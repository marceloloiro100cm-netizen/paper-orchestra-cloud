"""Testes da Onda 3: link revogável para orientador(a), ajuda progressiva, coerência e acessibilidade."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class AdvisorShareLinkTest(unittest.TestCase):
    def test_criar_ler_sem_dados_privados_e_revogar_link(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from mcp_server import Store
        from mcp_site_api import make_advisor_public_router, make_mcp_site_router

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
                self.cols = {"library_items": {}, "mcp_projects": {}, "research_jobs": {},
                             "mcp_tokens": {}, "advisor_shares": {}}

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

        class FakeBucket:
            def __init__(self):
                self.files = {}

            def blob(self, name):
                return FakeBlob(self.files, name)

        db, bucket = FakeDB(), FakeBucket()
        pid = "c" * 32
        db.cols["mcp_projects"][pid] = {
            "id": pid, "owner_uid": "ana", "title": "Dissertação Freire", "question": "Como democratizar a escrita?",
            "language": "pt-BR", "template": "abnt-dissertacao", "tipo": "dissertacao", "sources": [],
            "status": "pronto", "stages": {}, "heads": {}, "created_at": "2026-11-26T00:00:00Z",
            "updated_at": "2026-11-26T00:00:00Z", "files": [],
        }
        bucket.files[f"mcp/ana/{pid}/references.json"] = json.dumps([
            {"key": "freire1996autonomia", "type": "book", "how": "doi",
             "fields": {"author": "Paulo Freire", "title": "Pedagogia da autonomia", "year": "1996"}},
        ]).encode("utf-8")

        store = Store(db, bucket, lambda *_: None, lambda _i: True)
        app = FastAPI()
        app.include_router(make_mcp_site_router(store, lambda: {"uid": "ana", "email": "ana.privado@ifrs.edu.br"},
                                                "https://scriptoriummpie.web.app"))
        app.include_router(make_advisor_public_router(store))
        client = TestClient(app)

        # 1) Cria link de orientação
        r = client.post(f"/api/mcp-conta/projetos/{pid}/orientacao/link",
                        json={"dias": 7, "nota": "Professora, verifique se os objetivos respondem à pergunta."})
        self.assertEqual(r.status_code, 201, r.text)
        url = r.json()["url"]
        self.assertIn("?orientacao=adv_", url)
        token = url.split("orientacao=", 1)[1]

        # 2) Orientador abre sem login e vê dados pedagógicos sem nenhum dado sensível
        pub = client.get(f"/api/orientacao/{token}")
        self.assertEqual(pub.status_code, 200, pub.text)
        data = pub.json()
        self.assertEqual(data["titulo"], "Dissertação Freire")
        self.assertEqual(data["tipo"], "Dissertação de mestrado")
        self.assertIn("Professora", data["nota_estudante"])
        self.assertEqual(len(data["referencias_confirmadas"]), 1)
        raw_text = json.dumps(data)
        self.assertNotIn("ana.privado@ifrs.edu.br", raw_text)
        self.assertNotIn("owner_uid", raw_text)

        # 3) Revogação imediata bloqueia o acesso na hora
        rev = client.delete(f"/api/mcp-conta/projetos/{pid}/orientacao/link")
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(client.get(f"/api/orientacao/{token}").status_code, 404)
        self.assertEqual(client.get("/api/orientacao/invalido").status_code, 404)


class Onda3FrontendPedagogiaTest(unittest.TestCase):
    def test_guia_tem_ajuda_progressiva_decisoes_e_zero_travessao(self):
        guia = (ROOT / "public" / "guia" / "guia.js").read_text(encoding="utf-8")
        self.assertNotIn("—", guia)
        for marker in ("supportLevel", "set-support", "field-hint", "data-decision", "aria-expanded"):
            self.assertIn(marker, guia)

    def test_site_tem_tour_glossario_e_painel_orientacao(self):
        html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
        for marker in ("welcome-tour", "data-glossary", "advisor-share-view"):
            self.assertIn(marker, html)
        for marker in ("INLINE_GLOSSARY", "loadAdvisorShareView", "orientacao/link"):
            self.assertIn(marker, js)


if __name__ == "__main__":
    unittest.main()
