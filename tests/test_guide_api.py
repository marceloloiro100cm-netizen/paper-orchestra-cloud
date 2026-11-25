"""Rotas do guia de escrita: guardar e devolver o estado do guia de cada pessoa."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def exists(self):
        return self.name in self.store

    def download_as_bytes(self):
        return self.store[self.name]

    def upload_from_string(self, data, content_type=None):
        self.store[self.name] = data if isinstance(data, bytes) else data.encode()


class FakeBucket:
    def __init__(self):
        self.files = {}

    def blob(self, name):
        return FakeBlob(self.files, name)


def state(changed, **extra):
    return {"schema": 2, "tipo": "artigo", "active": 1, "values": {"tema": "x"}, "records": {},
            "criteria": {}, "versions": [], "changedAt": changed, **extra}


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class GuideRoutesTest(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from guide_api import make_guide_router

        self.bucket = FakeBucket()
        self.uid = "ana"
        app = FastAPI()
        app.include_router(make_guide_router(self.bucket, lambda: {"uid": self.uid}, today=lambda: "2026-11-25"))
        self.client = TestClient(app)

    def test_vazio_depois_salvo(self):
        r = self.client.get("/api/guia/estado")
        self.assertEqual(r.json(), {"estado": None, "changedAt": 0})
        r = self.client.put("/api/guia/estado?base=0", json=state(100))
        self.assertEqual(r.status_code, 200)
        self.assertIn("guia/ana/estado.json", self.bucket.files)
        self.assertIn("guia/ana/historico/2026-11-25.json", self.bucket.files)
        self.assertEqual(self.client.get("/api/guia/estado").json()["estado"]["values"], {"tema": "x"})

    def test_conflito_e_forcar(self):
        self.client.put("/api/guia/estado?base=0", json=state(200))
        r = self.client.put("/api/guia/estado?base=100", json=state(300))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["changedAt"], 200)
        self.assertEqual(self.client.put("/api/guia/estado?base=200", json=state(300)).status_code, 200)
        self.assertEqual(self.client.put("/api/guia/estado?base=0&forcar=true", json=state(400)).status_code, 200)

    def test_formato_invalido(self):
        self.assertEqual(self.client.put("/api/guia/estado", json={"schema": 1}).status_code, 422)
        self.assertEqual(self.client.put("/api/guia/estado", json=state(1, tipo="tese")).status_code, 422)
        self.assertEqual(self.client.put("/api/guia/estado", json=state(1, values=[])).status_code, 422)

    def test_limite_de_tamanho(self):
        big = state(1, values={"t": "a" * (3 * 1024 * 1024)})
        self.assertEqual(self.client.put("/api/guia/estado", json=big).status_code, 413)

    def test_cada_pessoa_tem_o_seu(self):
        self.client.put("/api/guia/estado", json=state(10))
        self.uid = "bia"
        self.assertIsNone(self.client.get("/api/guia/estado").json()["estado"])
        self.assertEqual(json.loads(self.bucket.files["guia/ana/estado.json"])["changedAt"], 10)


class GuidePageTest(unittest.TestCase):
    """Conferências estáticas do guia integrado ao site (public/guia/guia.js)."""

    base = Path(__file__).resolve().parents[1] / "public"
    page = (base / "guia" / "guia.js").read_text(encoding="utf-8")
    site = (base / "index.html").read_text(encoding="utf-8")

    def test_sem_travessao_e_sem_prototipo(self):
        self.assertNotIn("—", self.page)
        self.assertNotIn("rotótipo", self.page)

    def test_sem_verde_e_vermelho(self):
        for color in ("#22664d", "#ae3e35", "#9adbbb", "#ff9b91", "#78c9a7"):
            self.assertNotIn(color, self.page)

    def test_componente_integrado(self):
        self.assertIn("tipo:'artigo'", self.page)
        self.assertIn("attachShadow", self.page)
        self.assertIn("window.ScriptoriumGuia", self.page)
        for global_dom in ("document.getElementById", "document.addEventListener", "window.GuiaNuvem"):
            self.assertNotIn(global_dom, self.page)

    def test_site_tem_a_aba_e_o_painel(self):
        self.assertIn('data-step="4"', self.site)
        self.assertIn('id="guia-host"', self.site)
        self.assertIn("/guia/guia.js", self.site)
        self.assertIn("ScriptoriumConta", self.site)

    def test_endereco_antigo_redireciona(self):
        old = (self.base / "guia" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/#guia", old)


if __name__ == "__main__":
    unittest.main()
