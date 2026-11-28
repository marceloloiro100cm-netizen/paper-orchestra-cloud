"""Testes da Onda 4: estudo piloto ético (TCLE, SUS, anonimização, transferência e retirada) e doc PTT."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


class SusCalculationTest(unittest.TestCase):
    def test_escala_sus_extremos_e_neutro(self):
        from pilot_eval import compute_sus, sus_band
        self.assertEqual(compute_sus([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]), 100.0)
        self.assertEqual(sus_band(100.0), "Excelente")
        self.assertEqual(compute_sus([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]), 0.0)
        self.assertEqual(compute_sus([3] * 10), 50.0)
        self.assertEqual(compute_sus([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]), 75.0)
        self.assertEqual(sus_band(75.0), "Boa")


@unittest.skipUnless(HAS_FASTAPI, "fastapi não instalado")
class PilotRoutesAndEthicsTest(unittest.TestCase):
    def test_tcle_obrigatorio_pseudonimizacao_retirada_e_csv_admin(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from pilot_eval import PILOT_VERSION, make_pilot_router

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

            def set(self, rec):
                self.store[self.key] = dict(rec)

            def delete(self):
                self.store.pop(self.key, None)

        class FakeCol:
            def __init__(self, store):
                self.store = store

            def document(self, key):
                return FakeDoc(self.store, key)

            def stream(self):
                return [FakeSnap(v) for v in self.store.values()]

        class FakeDB:
            def __init__(self):
                self.cols = {"pilot_responses": {}}

            def collection(self, name):
                return FakeCol(self.cols.setdefault(name, {}))

        db = FakeDB()
        current = {"uid": "uid-maria-secreto", "email": "maria.silva@ifrs.edu.br", "admin": False}
        app = FastAPI()
        app.include_router(make_pilot_router(db, lambda: current, lambda u: bool(u.get("admin")), salt="test-salt"))
        client = TestClient(app)

        # 1) Bloqueia sem TCLE
        bad = client.post("/api/piloto/avaliacao", json={"tcle_aceito": False, "sus": [4, 2, 4, 2, 4, 2, 4, 2, 4, 2]})
        self.assertEqual(bad.status_code, 422)

        # 2) Envia com TCLE + atividade de transferência
        ok = client.post("/api/piloto/avaliacao", json={
            "tcle_aceito": True, "vinculo": "graduacao", "familiaridade_digital": "iniciante",
            "sus": [5, 2, 4, 2, 5, 1, 4, 2, 5, 2],
            "o_que_ajudou": "Guia passo a passo e capa do PDF.",
            "percepcao_autoria": "Escrevi minhas próprias perguntas.",
            "transferencia": {
                "problema": "Estudantes do noturno enfrentam falta de tempo e acesso limitado pelo celular.",
                "pergunta": "Como adaptar atividades assíncronas curtas para acesso móvel?",
                "objetivo_geral": "Analisar estratégias pedagógicas móveis para turmas noturnas.",
                "como_coletar": "Questionário breve e entrevistas semiestruturadas com estudantes.",
            },
        })
        self.assertEqual(ok.status_code, 201, ok.text)
        body = ok.json()
        self.assertEqual(body["versao_piloto"], PILOT_VERSION)
        self.assertEqual(body["transferencia_completude"], 4)
        self.assertTrue(body["codigo_anonimo"].startswith("P-"))

        # Garante zero dado pessoal identificável no Firestore
        stored_text = str(db.cols["pilot_responses"])
        self.assertNotIn("maria.silva@ifrs.edu.br", stored_text)
        self.assertNotIn("uid-maria-secreto", stored_text)

        # 3) Estudante comum não pode baixar CSV geral
        self.assertEqual(client.get("/api/admin/piloto/resumo.csv").status_code, 403)

        # 4) Administrador baixa CSV 100% anonimizado com estatística no header
        current["admin"] = True
        csv_resp = client.get("/api/admin/piloto/resumo.csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.headers["x-scriptorium-pilot-n"], "1")
        csv_text = csv_resp.content.decode("utf-8-sig")
        self.assertIn(body["codigo_anonimo"], csv_text)
        self.assertNotIn("maria.silva@ifrs.edu.br", csv_text)

        # 5) Retirada de consentimento apaga resposta imediatamente
        current["admin"] = False
        wd = client.delete("/api/piloto/avaliacao")
        self.assertEqual(wd.status_code, 200)
        self.assertTrue(wd.json()["removido"])
        self.assertFalse(client.get("/api/piloto/meu-status").json()["enviado"])


class PttDocAndFrontendTest(unittest.TestCase):
    def test_doc_replicabilidade_e_ui_piloto_presentes(self):
        doc = (ROOT / "docs" / "pesquisa" / "REPLICABILIDADE-PTT.md").read_text(encoding="utf-8")
        for kw in ("v1.0-piloto", "CAPES", "SUS", "TCLE", "MPIE"):
            self.assertIn(kw, doc)
        html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn("pilot-eval-details", html)
        self.assertIn("admin-pilot-csv", html)


if __name__ == "__main__":
    unittest.main()
