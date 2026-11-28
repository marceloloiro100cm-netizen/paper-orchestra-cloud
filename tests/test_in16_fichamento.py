"""IN IFRS 16/2026 (M11) e fichamento por IA (M21). Sem rede e sem modelo."""
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "tests"))
from fastapi import HTTPException  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import advisor  # noqa: E402
import reading_notes  # noqa: E402
import reading_notes_api  # noqa: E402
from ai_declaration import build_declaration  # noqa: E402
from test_biblioteca_exportacao import DB, Bucket, endpoint  # noqa: E402

MANIFEST = {
    "title": "Agentes de IA na escrita", "run_id": "r1", "started_at": "2026-11-24T10:00:00",
    "finished_at": "2026-11-24T12:00:00",
    "request": {"model": "gemini-3-flash-preview", "reflection_model": "gemini-3-flash-preview",
                "provider": "Google Gemini API (chave pessoal do pesquisador)", "ai_auth_mode": "user_gemini"},
    "software": {"paper_orchestra": {"commit": "d9bae997", "repository": "x"}},
    "sources": [{"name": "Bergmann.pdf", "sha256": "f" * 64}],
}
AGENTS = {"outline": "completed", "literature": "completed", "plotting": "disabled",
          "writing": "completed", "refinement": "completed"}


class AdvisorTest(unittest.TestCase):
    def test_validation(self):
        ok = advisor.AdvisorAuthorization(advisor_name="Profa. Ana", authorized_on="2026-08-10",
                                          record_form="e-mail", scope=["X", "I", "I"])
        self.assertEqual(ok.scope, ["I", "X"])
        with self.assertRaises(ValidationError):
            advisor.AdvisorAuthorization(advisor_name="Profa. Ana", authorized_on="2026-08-10",
                                         record_form="e-mail", scope=["XX"])
        with self.assertRaises(ValidationError):
            advisor.AdvisorAuthorization(advisor_name="Profa. Ana", record_form="e-mail", scope=["I"],
                                         authorized_on=(date.today() + timedelta(days=3)).isoformat())

    def test_router_is_append_only_and_per_owner(self):
        db = DB()
        router = advisor.make_advisor_router(db, lambda: None)
        post = endpoint(router, "advisor-authorization", "POST")
        get = endpoint(router, "advisor-authorization", "GET")
        for name, day in (("Profa. Ana", "2026-08-10"), ("Prof. Rui", "2026-09-01")):
            post(payload=advisor.AdvisorAuthorization(advisor_name=name, authorized_on=day,
                                                      record_form="ata ou registro de reunião", scope=["I"]),
                 user={"uid": "u1"})
        data = get(user={"uid": "u1"})
        self.assertEqual(data["latest"]["advisor_name"], "Prof. Rui")
        self.assertEqual(len(data["history"]), 2)
        self.assertIsNone(get(user={"uid": "u2"})["latest"])

    def test_art9_blocks_unpublished_data_without_paid_tier(self):
        with self.assertRaises(HTTPException) as ctx:
            advisor.data_policy(True, False, True, project_ai=False)
        self.assertIn("Art. 9º", ctx.exception.detail)
        with self.assertRaises(HTTPException):
            advisor.data_policy(True, True, False, project_ai=False)
        self.assertTrue(advisor.data_policy(True, True, True, project_ai=False)["unpublished_data"])
        self.assertFalse(advisor.data_policy(False, False, False, project_ai=False)["unpublished_data"])
        self.assertIsNone(advisor.data_policy(True, False, True, project_ai=True)["paid_tier_confirmed"])

    def test_addendum(self):
        text = advisor.addendum({"advisor_name": "Profa. Ana", "authorized_on": "2026-08-10",
                                 "record_form": "e-mail", "record_reference": "Assunto: IA", "scope": ["I", "X"],
                                 "recorded_at": "2026-11-24T10:00:00"})
        self.assertIn("Adendo", text)
        self.assertIn("X (Elaboração parcial", text)


class DeclarationIn16Test(unittest.TestCase):
    def test_without_authorization_keeps_fields_to_fill(self):
        text = build_declaration(MANIFEST, AGENTS)
        self.assertIn("RASCUNHO", text)
        self.assertIn("e712908ba1", text)
        for section in ("### 1. IDENTIFICAÇÃO DO AUTOR", "### 2. IDENTIFICAÇÃO DO TRABALHO ACADÊMICO",
                        "### 3. REGISTRO DO USO DE IAGen — Art. 6º", "### 4. AUTORIZAÇÃO DO(A) SERVIDOR(A) — Art. 8º",
                        "### 5. COMPROMISSO DO(A) AUTOR(A)", "responsabilidade intelectual, ética e legal integral",
                        "Art. 5º, parágrafo único"):
            self.assertIn(section, text)
        for article in ("Art. 3º", "Art. 4º", "Art. 7º", "Art. 9º", "(inc. X)", "(inc. XII)", "(inc. III)"):
            self.assertIn(article, text)
        self.assertNotIn("XX/2026", text)
        self.assertIn("| **Matrícula** | [PREENCHER] |", text)
        self.assertIn("Nenhuma autorização estava registrada", text)
        self.assertIn("ai.google.dev/gemini-api/terms", text)
        self.assertNotIn("está em conformidade", text.lower())

    def test_with_authorization_flags_uses_outside_scope(self):
        manifest = {**MANIFEST, "institutional": {
            "advisor_authorization": {"advisor_name": "Profa. Ana", "authorized_on": "2026-08-10",
                                      "record_form": "e-mail", "scope": ["I", "II", "III", "IV", "XII"],
                                      "recorded_at": "2026-09-01"},
            "academic_profile": {"full_name": "Marcelo Exemplo", "enrollment": "2026001", "unit": "Campus Porto Alegre",
                                 "program": "Mestrado Profissional em Informática na Educação"},
            "work_type": "dissertação",
            "data_policy": {"unpublished_data": True, "paid_tier_confirmed": True, "deidentified_confirmed": True,
                            "provider_training_policy": "Gemini API com chave pessoal"}}}
        text = build_declaration(manifest, AGENTS)
        self.assertIn("| **Servidor responsável** | Profa. Ana |", text)
        self.assertIn("| **Matrícula** | 2026001 |", text)
        self.assertIn("| **Natureza do trabalho acadêmico** | dissertação |", text)
        self.assertIn("fora da autorização registrada: incisos X", text)
        self.assertIn("| **Data** | 10/08/2026 |", text)
        self.assertIn("confirmado pelo(a) autor(a)", text)


class AcademicProfileTest(unittest.TestCase):
    def test_profile_saved_per_owner(self):
        db = DB()
        router = advisor.make_advisor_router(db, lambda: None)
        put = endpoint(router, "/academic-profile", "PUT")
        get = endpoint(router, "/academic-profile", "GET")
        put(payload=advisor.AcademicProfile(full_name="Marcelo  Exemplo", enrollment="2026/001",
                                            unit="Campus Porto Alegre", program="MPIE"), user={"uid": "u1"})
        self.assertEqual(get(user={"uid": "u1"})["profile"]["full_name"], "Marcelo Exemplo")
        self.assertIsNone(get(user={"uid": "u2"})["profile"])
        with self.assertRaises(ValidationError):
            advisor.AcademicProfile(full_name="Marcelo", enrollment="<script>")


class ReadingNotesTest(unittest.TestCase):
    CHUNKS = [
        {"chunk_id": "aaaaaaaaaaaa-0000-11111111", "index": 0, "pages": [1, 1],
         "text": "A sala de aula invertida aumentou o engajamento dos estudantes em 20%.",
         "parser_version": "pymupdf-structured-1", "chunk_policy": "section-paragraph-1"},
        {"chunk_id": "aaaaaaaaaaaa-0001-22222222", "index": 1, "pages": [2, 2],
         "text": "O estudo usou questionários com 120 participantes.",
         "parser_version": "pymupdf-structured-1", "chunk_policy": "section-paragraph-1"},
    ]

    def test_namespaces_match_between_api_and_worker(self):
        self.assertEqual(reading_notes.namespace("gemini-3-flash-preview"),
                         reading_notes_api.notes_namespace("gemini-3-flash-preview"))

    def test_check_notes_removes_unknown_ids_and_verifies_quotes(self):
        raw = {"tema": "Sala de aula invertida",
               "principais_achados": [{"texto": "Mais engajamento", "trechos": ["aaaaaaaaaaaa-0000-11111111", "inventado"]},
                                      {"texto": "Sem base", "trechos": ["inventado"]}],
               "citacoes_literais": [{"citacao": "aumentou o ENGAJAMENTO dos estudantes", "trecho": "x"},
                                     {"citacao": "frase que não existe no texto", "trecho": "aaaaaaaaaaaa-0001-22222222"}]}
        notes = reading_notes.check_notes(raw, self.CHUNKS)
        self.assertEqual(notes["checagem"]["ids_inexistentes_removidos"], 2)
        self.assertTrue(notes["principais_achados"][1]["sem_trecho_valido"])
        self.assertEqual(notes["citacoes_literais"][0]["situacao"], "conferida")
        self.assertEqual(notes["citacoes_literais"][0]["pages"], [1, 1])
        self.assertEqual(notes["citacoes_literais"][1]["situacao"], "nao_encontrada_no_documento")

    def test_select_chunks_respects_limit(self):
        chosen, truncated = reading_notes.select_chunks(self.CHUNKS, limit=80)
        self.assertEqual(len(chosen), 1)
        self.assertTrue(truncated)
        self.assertIn("[aaaaaaaaaaaa-0000-11111111 | p. 1-1]", reading_notes.build_prompt("X.pdf", chosen))


class ReadingNotesApiTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket, self.started = DB(), Bucket(), []
        self.item = {"id": "c" * 32, "owner_uid": "u1", "status": "active", "format": "pdf", "name": "B.pdf",
                     "sha256": "f" * 64, "object_path": f"library/u1/{'c' * 32}/original.pdf"}
        self.db.store[("library_items", self.item["id"])] = self.item
        access = lambda user: {"ai_auth_mode": "user_gemini", "models": ["gemini-3-flash-preview"]}  # noqa: E731
        self.router = reading_notes_api.make_reading_notes_router(
            self.db, self.bucket, lambda: None, access, lambda *a: self.started.append(a))

    def test_starts_once_then_serves_cache(self):
        post = endpoint(self.router, "/ai-notes", "POST")
        get = endpoint(self.router, "/ai-notes", "GET")
        self.assertEqual(get(item_id=self.item["id"], user={"uid": "u1"})["status"], "none")
        result = post(item_id=self.item["id"], user={"uid": "u1"})
        self.assertEqual(result["status"], "queued")
        job = self.db.store[("research_jobs", result["job_id"])]
        self.assertEqual((job["mode"], job["ai_auth_mode"]), ("reading_notes", "user_gemini"))
        self.assertEqual(self.started, [(result["job_id"], "u1", "reading_notes")])
        with self.assertRaises(HTTPException):  # já em andamento
            post(item_id=self.item["id"], user={"uid": "u1"})
        ns = reading_notes_api.notes_namespace()
        self.bucket.objects[f"library/u1/derived/{ns}/pymupdf-structured-1-section-paragraph-1/{'f' * 64}.json"] = \
            json.dumps({"tema": "T"}).encode()
        self.assertEqual(get(item_id=self.item["id"], user={"uid": "u1"})["notes"]["tema"], "T")
        self.assertTrue(post(item_id=self.item["id"], user={"uid": "u1"})["cached"])
        with self.assertRaises(HTTPException):
            get(item_id=self.item["id"], user={"uid": "outra"})


if __name__ == "__main__":
    unittest.main()
