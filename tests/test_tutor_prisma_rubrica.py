"""Testes da Fase 2: Tutor Socrático, Resumo PRISMA, Comentários da Orientação, Mapa Visual e Rubrica 0-15."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import abnt_refs
from library import make_library_router
import mcp_server
from mcp_site_api import make_advisor_public_router, make_mcp_site_router
from test_zotero_abnt_fichamento import _FakeBucket, _FakeDB


class Fase2BackendTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDB()
        self.bucket = _FakeBucket()
        self.user = {"uid": "u-aluno-2", "email": "estudante@ifrs.edu.br"}

    def test_prisma_summary_single_source_of_truth(self):
        app = FastAPI()
        app.include_router(make_library_router(self.db, self.bucket, lambda: self.user))
        client = TestClient(app)

        # Importa 3 referências distintas
        bib = "\n\n".join([
            "@book{freire1996, author={Freire, Paulo}, title={Pedagogia da autonomia}, year={1996}}",
            "@article{fan2025, author={Fan, Yizhou}, title={Beware of metacognitive laziness}, year={2025}}",
            "@article{outro2024, author={Silva, Ana}, title={Estudo fora do escopo escolar}, year={2024}}",
        ])
        r = client.post("/api/library/import-references", json={"text": bib})
        self.assertEqual(r.status_code, 201)
        items = [x["item"] for x in r.json()["results"]]
        self.assertEqual(len(items), 3)

        # Marca 1 incluído + fichamento verificado, 1 lido, 1 descartado com motivo
        client.patch(f"/api/library/items/{items[0]['id']}/study", json={"role": "marco_teorico", "reading_status": "incluido"})
        client.post(f"/api/library/items/{items[0]['id']}/notes", json={"page": "47", "note": "Autonomia", "support_checked": True})
        client.patch(f"/api/library/items/{items[1]['id']}/study", json={"role": "evidencia", "reading_status": "lido"})
        client.patch(f"/api/library/items/{items[2]['id']}/study", json={
            "reading_status": "descartado", "exclude_reason": "Fora do ensino superior",
        })

        rp = client.get("/api/library/prisma-summary")
        self.assertEqual(rp.status_code, 200)
        d = rp.json()
        self.assertEqual(d["total_identificados"], 3)
        self.assertEqual(d["triagem"]["incluido"], 1)
        self.assertEqual(d["triagem"]["lido"], 1)
        self.assertEqual(d["triagem"]["descartado"], 1)
        self.assertEqual(d["por_papel"]["marco_teorico"], 1)
        self.assertEqual(d["fichamentos_total"], 1)
        self.assertEqual(d["sustentacao_conferida"], 1)
        self.assertEqual(d["motivos_descarte"][0]["motivo"], "Fora do ensino superior")
        self.assertIn("1 fonte(s) incluída(s)", d["resumo_metodologico"])

    def test_socratic_mode_guardrail_and_advisor_comments_flow(self):
        # Cria uma fonte ativa para o projeto MCP
        sid = "a" * 32
        self.db.collection("library_items").document(sid).create({
            "id": sid, "owner_uid": self.user["uid"], "name": "Freire.pdf",
            "format": "pdf", "sha256": "b" * 64, "size": 1024,
            "object_path": f"library/{self.user['uid']}/{sid}/original.pdf",
            "status": "active",
        })

        store = mcp_server.Store(self.db, self.bucket, lambda *a, **kw: None, lambda _: True)
        app = FastAPI()
        app.include_router(make_mcp_site_router(store, lambda: self.user, "https://scriptoriummpie.web.app"))
        app.include_router(make_advisor_public_router(store))
        client = TestClient(app)

        # 1) Cria projeto no modo Tutor Socrático
        rc = client.post("/api/mcp-conta/projetos", json={
            "titulo": "Pré-projeto Scriptorium",
            "pergunta": "Como a mediação pedagógica com IA apoia a aprendizagem de projetos?",
            "fontes": [sid],
            "tipo": "artigo",
            "modelo": "abnt-artigo",
            "modo_pedagogico": "tutor_socratico",
        })
        self.assertEqual(rc.status_code, 201)
        pid = rc.json()["projeto"]
        self.assertEqual(rc.json()["modo_pedagogico"], "tutor_socratico")

        # 2) Marca projeto pronto e verifica que next_step injeta o guardrail Socrático
        store.update_project(pid, status="pronto")
        step_out = mcp_server.next_step(store, self.user["uid"], pid, None, "gemini", "test")
        self.assertIn("MODO TUTOR SOCRÁTICO", step_out["instrucoes"])
        self.assertEqual(step_out["modo_pedagogico"], "tutor_socratico")

        # 3) Troca modo para autônomo via endpoint e confirma mudança na instrução
        rm = client.patch(f"/api/mcp-conta/projetos/{pid}/modo-pedagogico", json={"modo_pedagogico": "autonomo"})
        self.assertEqual(rm.status_code, 200)
        step_auto = mcp_server.next_step(store, self.user["uid"], pid, None, "gemini", "test")
        self.assertIn("MODO AUTÔNOMO", step_auto["instrucoes"])

        # 4) Gera link de orientação e posta comentário público sem login
        rl = client.post(f"/api/mcp-conta/projetos/{pid}/orientacao/link", json={"dias": 14, "nota": "Revisar método"})
        self.assertEqual(rl.status_code, 201)
        token = rl.json()["url"].split("orientacao=")[1]

        rpost = client.post(f"/api/orientacao/{token}/comentarios", json={
            "autor": "Prof. Orientador",
            "etapa": "Planejamento",
            "tipo": "ajuste_obrigatorio",
            "texto": "Delimitar melhor a turma participante antes da coleta.",
        })
        self.assertEqual(rpost.status_code, 201)
        cid = rpost.json()["comentario"]["id"]

        # 5) Comentário aparece na visão pública do orientador e na visão do estudante
        rpub = client.get(f"/api/orientacao/{token}")
        self.assertEqual(rpub.status_code, 200)
        self.assertEqual(len(rpub.json()["comentarios"]), 1)
        self.assertEqual(rpub.json()["modo_pedagogico"], "autonomo")

        rstud = client.get(f"/api/mcp-conta/projetos/{pid}")
        self.assertEqual(rstud.json()["comentarios_pendentes"], 1)

        # 6) Estudante marca comentário como resolvido
        rres = client.patch(f"/api/mcp-conta/projetos/{pid}/orientacao/comentarios/{cid}", json={"resolvido": True})
        self.assertEqual(rres.status_code, 200)
        self.assertTrue(rres.json()["comentario"]["resolved"])
        self.assertEqual(client.get(f"/api/mcp-conta/projetos/{pid}").json()["comentarios_pendentes"], 0)

        # 7) Revogar link bloqueia novos comentários
        client.delete(f"/api/mcp-conta/projetos/{pid}/orientacao/link")
        rblocked = client.post(f"/api/orientacao/{token}/comentarios", json={
            "autor": "Alguém", "etapa": "Geral", "tipo": "sugestao", "texto": "Teste pós-revogação",
        })
        self.assertEqual(rblocked.status_code, 404)

    def test_delete_mcp_project_cleans_artifacts_revokes_link_and_preserves_library(self):
        sid = "d" * 32
        lib_blob = f"library/{self.user['uid']}/{sid}/original.pdf"
        self.bucket.blob(lib_blob).upload_from_string(b"%PDF-1.4 original library file")
        self.db.collection("library_items").document(sid).create({
            "id": sid, "owner_uid": self.user["uid"], "name": "Fonte.pdf",
            "format": "pdf", "sha256": "e" * 64, "size": 512,
            "object_path": lib_blob, "status": "active",
        })
        store = mcp_server.Store(self.db, self.bucket, lambda *a, **kw: None, lambda _: True)
        app = FastAPI()
        app.include_router(make_mcp_site_router(store, lambda: self.user, "https://scriptoriummpie.web.app"))
        app.include_router(make_advisor_public_router(store))
        client = TestClient(app)

        rc = client.post("/api/mcp-conta/projetos", json={
            "titulo": "Texto de teste para exclusão",
            "pergunta": "Como avaliar a exclusão segura de textos escritos sem apagar fontes?",
            "fontes": [sid], "tipo": "artigo", "modelo": "abnt-artigo",
        })
        self.assertEqual(rc.status_code, 201)
        pid = rc.json()["projeto"]

        # Enquanto preparando -> bloqueia exclusão (409)
        rbusy = client.delete(f"/api/mcp-conta/projetos/{pid}")
        self.assertEqual(rbusy.status_code, 409)

        # Marca concluído, grava artefatos do projeto e cria link de orientação
        store.update_project(pid, status="concluido")
        art_blob = f"mcp/{self.user['uid']}/{pid}/final/scriptorium.pdf"
        self.bucket.blob(art_blob).upload_from_string(b"%PDF-1.4 generated")
        rl = client.post(f"/api/mcp-conta/projetos/{pid}/orientacao/link", json={"dias": 7})
        token = rl.json()["url"].split("orientacao=")[1]

        # Exclui o texto com sucesso
        rdel = client.delete(f"/api/mcp-conta/projetos/{pid}")
        self.assertEqual(rdel.status_code, 200)
        self.assertTrue(rdel.json()["deleted"])
        self.assertEqual(rdel.json()["files_removed"], 1)

        # Projeto sumiu, artefato do projeto sumiu, link foi revogado, MAS a fonte da Biblioteca está intacta!
        self.assertEqual(client.get(f"/api/mcp-conta/projetos/{pid}").status_code, 404)
        self.assertFalse(self.bucket.blob(art_blob).exists())
        self.assertEqual(client.get(f"/api/orientacao/{token}").status_code, 404)
        self.assertTrue(self.bucket.blob(lib_blob).exists())

    def test_frontend_fase2_contracts_and_no_emdash_in_guia(self):
        html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
        guia_js = (ROOT / "public" / "guia" / "guia.js").read_text(encoding="utf-8")
        self.assertIn('id="open-prisma-summary"', html)
        self.assertIn('id="new-proj-pedagogical"', html)
        self.assertIn('id="how-to-use-btn"', html)
        self.assertNotIn('id="start-strip"', html)
        self.assertIn("/library/prisma-summary", app_js)
        self.assertIn("/modo-pedagogico", app_js)
        self.assertIn("/comentarios", app_js)
        self.assertIn("openFlowMapModal", guia_js)
        self.assertIn("openRubricModal", guia_js)
        self.assertIn("RUBRIC_DIMS", guia_js)
        self.assertIn("modo_pedagogico", guia_js)
        self.assertIn("ScriptoriumGuiaAcoes", guia_js)
        self.assertIn("adicionarLeituraM4", app_js)
        self.assertIn("inserirResumoPrisma", app_js)
        self.assertNotIn("—", guia_js)
        rep_doc = (ROOT / "docs" / "pesquisa" / "REPLICABILIDADE-PTT.md").read_text(encoding="utf-8")
        self.assertIn("v1.1-piloto", rep_doc)


if __name__ == "__main__":
    unittest.main()
