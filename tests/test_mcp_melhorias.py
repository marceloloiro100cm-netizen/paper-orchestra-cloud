"""Testes das melhorias P1 do plano Scriptorium (itens 6 a 11, 14, 15, pacote orientação)."""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

import bib_integrity as bi  # noqa: E402
import mcp_flow as flow  # noqa: E402
import mcp_jobs  # noqa: E402
import mcp_student as student  # noqa: E402
from test_mcp import DB, Bucket, UID, SOURCE_TEXT, latex_body, seed_project  # noqa: E402

try:
    import fastapi  # noqa: F401
    import mcp_server  # noqa: E402
    import mcp_site_api  # noqa: E402
    HAVE_SITE = True
except ImportError:
    HAVE_SITE = False


class P1MetadataAndKeysTest(unittest.TestCase):
    def test_item6_stable_keys_never_use_fonte_prefix(self):
        used = set()
        k1 = bi._key_for({"author": "Kitchenham, Barbara and Charters, Stuart",
                          "title": "Guidelines for performing Systematic Literature Reviews",
                          "year": "2007"}, used)
        k2 = bi._key_for({"title": "A gamificação no ensino médio", "year": "2023"}, used)
        k3 = bi._key_for({"title": "172633"}, used)
        self.assertEqual(k1, "kitchenham2007guidelines")
        self.assertEqual(k2, "gamificacao2023")
        self.assertFalse(k3.startswith("fonte"))
        self.assertEqual(flow.stable_bib_key({"author": "Kitchenham, Barbara",
                                              "title": "Guidelines for performing Systematic Literature Reviews",
                                              "year": "2007"}), "kitchenham2007guidelines")

    def test_item6_library_card_is_inherited_without_api_calls(self):
        calls = []
        card = {"type": "techreport", "key": "kitchenham2007guidelines", "how": "confirmada_pelo_pesquisador",
                "fields": {"author": "Kitchenham, Barbara", "title": "Guidelines for SLRs", "year": "2007"}}
        entries = bi.library_entries(
            [{"id": "s1", "name": "525444.pdf"}],
            lambda url: calls.append(url),
            library_cards={"s1": card},
        )
        self.assertEqual(calls, [])
        self.assertEqual(entries[0]["key"], "kitchenham2007guidelines")
        self.assertEqual(entries[0]["how"], "ficha_da_biblioteca")
        self.assertEqual(bi.ref_level(entries[0]), "confirmada")

    def test_item8_two_sources_agreement_confirms_automatically(self):
        text = "Guidelines for performing Systematic Literature Reviews in Software Engineering\nBarbara Kitchenham\n2007"
        oa = {"results": [{"title": "Guidelines for performing Systematic Literature Reviews in Software Engineering",
                           "publication_year": 2007, "type": "article",
                           "authorships": [{"author": {"display_name": "Barbara Kitchenham"}}]}]}
        cr = {"message": {"items": [{"title": ["Guidelines for performing Systematic Literature Reviews in Software Engineering"],
                                     "published-print": {"date-parts": [[2007]]}, "type": "journal-article",
                                     "author": [{"family": "Kitchenham", "given": "Barbara"}]}]}}
        entries = bi.library_entries([{"id": "k", "name": "kitchenham.pdf"}],
                                     lambda url: oa, {}, {"k": text}, crossref_get=lambda url: cr)
        self.assertEqual(entries[0]["how"], "confirmada_duas_fontes")
        self.assertEqual(bi.ref_level(entries[0]), "confirmada")

    def test_item8_oasisbr_finds_brazilian_dissertation(self):
        text = "Tecnologias digitais no ensino de ciências nos anos finais\nJosiane Souza\nBrasília 2022"
        ob = {"records": [{"title": "Tecnologias digitais no ensino de ciências nos anos finais",
                           "authors": {"primary": {"Souza, Josiane": {}}},
                           "publicationDates": ["2022"], "formats": ["masterThesis"],
                           "publishers": ["Universidade Católica de Brasília"]}]}
        entries = bi.library_entries([{"id": "d", "name": "souza.pdf"}],
                                     lambda url: {"results": []}, {}, {"d": text},
                                     oasisbr_get=lambda url: ob)
        self.assertEqual(entries[0]["how"], "oasisbr")
        self.assertEqual(entries[0]["type"], "mastersthesis")
        self.assertEqual(entries[0]["fields"]["school"], "Universidade Católica de Brasília")
        self.assertEqual(bi.ref_level(entries[0]), "sugerida")


class P1FlowValidationTest(unittest.TestCase):
    def test_item9_extract_claims_prioritizes_numbers_and_enforces_assigned(self):
        tex = (
            "\\begin{resumo}Resumo.\\end{resumo}\n"
            "\\section{Introdução}\n"
            "Estudos indicam que 78\\% dos participantes melhoraram o desempenho \\cite{k1}.\n\n"
            "A discussão teórica aparece em diversos trabalhos relevantes do campo \\cite{k2}.\n\n"
            "Os dados demonstraram ganho significativo em 15 estudantes da turma \\cite{k1}.\n"
        )
        claims = flow.extract_claims_to_verify(tex, {"k1", "k2"}, limit=5)
        self.assertEqual(claims[0]["id"], "A1")
        self.assertEqual(claims[0]["prioridade"], "numero")
        self.assertTrue(any("78%" in c["afirmacao"] for c in claims))
        # Verificação que pula afirmação sorteada é recusada.
        chunks = {"k1": [{"chunk_id": "c1", "text": SOURCE_TEXT[0]}], "k2": [{"chunk_id": "c2", "text": SOURCE_TEXT[1]}]}
        items = [{"afirmacao": f"Fácil {n}", "chave": "k1", "veredito": "sustentada",
                  "chunk_id": "c1", "citacao_literal": SOURCE_TEXT[0][:60]} for n in range(10)]
        bad = flow.validate_verification(json.dumps(items), {"k1", "k2"}, lambda k: chunks[k], assigned_claims=claims)
        self.assertFalse(bad["ok"])
        self.assertIn("A1", " ".join(bad["erros"]))
        # Com os IDs das sorteadas, passa.
        for i, c in enumerate(claims):
            items[i]["id"] = c["id"]
        good = flow.validate_verification(json.dumps(items), {"k1", "k2"}, lambda k: chunks[k], assigned_claims=claims)
        self.assertTrue(good["ok"], good["erros"])

    def test_item10_rewrite_requires_response_to_high_severity_review_problems(self):
        problems = [
            {"id": "P1", "gravidade": "alta", "tipo": "sem_suporte", "trecho": "X", "sugestao": "Corrigir X"},
            {"id": "P2", "gravidade": "media", "tipo": "clareza", "trecho": "Y", "sugestao": "Melhorar Y"},
        ]
        body = latex_body(["k1"])
        missing = flow.validate_latex(body, {"k1"}, 100, "abnt-artigo", review_problems=problems)
        self.assertFalse(missing["ok"])
        self.assertIn("P1", " ".join(missing["erros"]))
        by_comment = flow.validate_latex(body + "\n% [P1] corrigido: removida afirmação sem suporte.\n",
                                         {"k1"}, 100, "abnt-artigo", review_problems=problems)
        self.assertTrue(by_comment["ok"], by_comment["erros"])
        by_json = flow.validate_latex(body, {"k1"}, 100, "abnt-artigo", review_problems=problems,
                                      review_responses=json.dumps([{"id": "P1", "acao": "corrigido",
                                                                    "justificativa": "Texto ajustado com base na fonte."}]))
        self.assertTrue(by_json["ok"], by_json["erros"])

    def test_item11_criteria_review_and_self_verification_flag(self):
        rev = json.dumps({
            "criterios": {"argumento": 7, "uso_das_fontes": 8, "metodo": 6, "estrutura": 8, "estilo": 7},
            "resumo": "Bom rascunho com ajustes necessários no método.",
            "problemas": [{"trecho": "T", "tipo": "logica", "gravidade": "media", "sugestao": "Explicar melhor"}] * 3,
        }) + " " * 200
        rep = flow.validate_review(rev)
        self.assertTrue(rep["ok"], rep["erros"])
        self.assertEqual(rep["nota_geral"], 7.2)
        self.assertEqual(rep["criterios"]["uso_das_fontes"], 8.0)
        ind_same = flow.independence({"id": "w", "model": "Claude Opus 5.5"},
                                     {"id": "r", "model": "Claude Sonnet 5.5"})
        self.assertTrue(ind_same["autoverificacao"])
        self.assertIn("Gemini ou ChatGPT", ind_same["explicacao"])
        ind_other = flow.independence({"id": "w", "model": "Claude Opus 5.5"},
                                      {"id": "r", "model": "Gemini 3 Pro"})
        self.assertFalse(ind_other["autoverificacao"])

    def test_item14_anchored_paraphrase_and_item15_quality_report(self):
        chunks = {"k1": [{"chunk_id": "c-real", "text": SOURCE_TEXT[0]}]}
        ev = [{"afirmacao": f"Afirmação {n}", "chave": "k1", "chunk_id": "c-real", "tipo": "parafrase"}
              for n in range(8)]
        rep = flow.validate_evidence(json.dumps(ev), {"k1"}, lambda k: chunks[k])
        self.assertTrue(rep["ok"], rep["erros"])
        self.assertEqual(rep["parafrases"], 8)
        q = flow.quality_report(latex_body(["k1"]), {"k1"})
        self.assertGreater(q["palavras"], 50)
        self.assertEqual(len(q["secoes_um_paragrafo"]), 4)


@unittest.skipUnless(HAVE_SITE, "FastAPI/MCP ausente")
class P1SiteAndProposalTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket, self.jobs = DB(), Bucket(), []
        self.store = mcp_server.Store(self.db, self.bucket, lambda *a: self.jobs.append(a), lambda i: True)
        self.router = mcp_site_api.make_mcp_site_router(self.store, lambda: None, "https://s.example")
        self.user = {"uid": UID, "email": "p@example.org"}
        self.pid, self.manifest, self.refs = seed_project(self.db, self.bucket)
        # Seed library_items para testar propagação (Item 6).
        for s in self.db.collection("mcp_projects").document(self.pid).get().to_dict()["sources"]:
            self.db.collection("library_items").document(s["id"]).set({**s, "owner_uid": UID, "status": "active"})

    def route(self, suffix, method):
        return next(r.endpoint for r in self.router.routes if r.path.endswith(suffix) and method in r.methods)

    def test_item7_failed_auto_fix_saves_proposal_and_human_confirms_in_one_click(self):
        project = self.store.project(UID, self.pid)
        head = self.store.new_head(project, "redatora", None, "claude", "Claude")
        key = self.refs[0]["key"]
        sid = self.refs[0]["source_id"]
        # Capa em imagem (título não está no texto extraído): salva proposta pendente.
        with self.assertRaises(mcp_server.Falha) as ctx:
            self.store.correct_reference(project, key, head["id"], {
                "autores": ["Kitchenham, Barbara"], "titulo": "Procedures for Performing Systematic Reviews",
                "ano": "2004", "tipo": "techreport", "veiculo": "Keele University",
            })
        self.assertIn("1 clique", str(ctx.exception))
        refs = self.store.references(project)
        self.assertIn("proposta_pendente", refs[0])
        # Pesquisador confirma em 1 clique no site -> confirma no projeto E salva na biblioteca!
        confirm = self.route("/referencias/{key}/confirmar", "POST")
        res = confirm(self.pid, key, mcp_site_api.ConfirmReference(aceitar_proposta=True), self.user)
        self.assertTrue(res["confirmada"])
        updated_refs = self.store.references(project)
        self.assertEqual(updated_refs[0]["how"], "confirmada_pelo_pesquisador")
        self.assertNotIn("proposta_pendente", updated_refs[0])
        lib_doc = self.db.collection("library_items").document(sid).get().to_dict()
        self.assertEqual(lib_doc["bib_entry"]["key"], "kitchenham2004procedures")
        self.assertEqual(lib_doc["bib_entry"]["how"], "confirmada_pelo_pesquisador")

    def test_advisor_package_zip_contains_pdf_and_summary(self):
        prefix = f"mcp/{UID}/{self.pid}/final/"
        self.bucket.blob(prefix + "scriptorium.pdf").upload_from_string(b"%PDF-1.4")
        self.bucket.blob(prefix + "proveniencia.json").upload_from_string(b"{}")
        pkg = self.route("/pacote-orientacao.zip", "GET")(self.pid, self.user)
        with zipfile.ZipFile(io.BytesIO(pkg.body)) as zf:
            names = set(zf.namelist())
            self.assertIn("scriptorium.pdf", names)
            self.assertIn("resumo_para_orientacao.md", names)
            self.assertIn("Pacote para orientação", zf.read("resumo_para_orientacao.md").decode("utf-8"))

    def test_token_revocation_invalidates_verifier_cache(self):
        import asyncio
        created = self.store.create_token(UID, "p@example.org", "Teste")
        verifier = mcp_server.TokenVerifier(self.store, ttl=60.0)
        tok = asyncio.run(verifier.verify_token(created["token"]))
        self.assertIsNotNone(tok)
        self.assertIn(flow.token_hash(created["token"]), verifier.cache)
        self.assertNotIn(created["token"], verifier.cache)
        self.store.revoke_token(UID, created["id"])
        self.assertNotIn(flow.token_hash(created["token"]), verifier.cache)
        self.assertIsNone(asyncio.run(verifier.verify_token(created["token"])))


if __name__ == "__main__":
    unittest.main()
