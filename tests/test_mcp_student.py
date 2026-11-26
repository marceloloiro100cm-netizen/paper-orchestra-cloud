"""Visão do projeto para o estudante (próximo passo, provas e referências a conferir)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
import mcp_student as student  # noqa: E402

ACCEPT = {"status": "aceita"}


def project(stages=None, status="pronto", title="Tecnologias na escola"):
    return {"title": title, "status": status, "stages": stages or {}}


class NextStepTest(unittest.TestCase):
    def test_primeira_etapa_pede_para_continuar(self):
        step = student.next_step(project(), "artigo", 0)
        self.assertEqual(step["titulo"], "Próximo: Planejamento")
        self.assertIn("continue o projeto “Tecnologias na escola”", step["pedido"])

    def test_etapa_de_conversa_nova_com_passe(self):
        stages = {"planejamento": ACCEPT, "evidencias": ACCEPT, "redacao": ACCEPT,
                  "revisao": {"status": "pendente", "passe": "FKRU-8DDU-6U7W"}}
        step = student.next_step(project(stages), "artigo", 0)
        self.assertEqual(step["passe"], "FKRU-8DDU-6U7W")
        self.assertIn("abrir_passe com o código FKRU-8DDU-6U7W", step["pedido"])
        self.assertIn("conversa nova", step["titulo"])

    def test_etapa_de_conversa_nova_sem_passe(self):
        stages = {"planejamento": ACCEPT, "evidencias": ACCEPT, "redacao": ACCEPT}
        step = student.next_step(project(stages), "artigo", 0)
        self.assertNotIn("passe", step)
        self.assertIn("passe", step["texto"])

    def test_devolvida(self):
        step = student.next_step(project({"planejamento": {"status": "recusada"}}), "artigo", 0)
        self.assertIn("voltou com correções", step["texto"])

    def test_tudo_aceito_com_referencias(self):
        keys = ["planejamento", "evidencias", "redacao", "revisao", "reescrita", "verificacao"]
        stages = {k: ACCEPT for k in keys}
        self.assertIn("compile", student.next_step(project(stages), "artigo", 0)["pedido"])
        step = student.next_step(project(stages), "artigo", 3)
        self.assertIn("3 referência", step["texto"])
        self.assertIn(student.REF_FIX, step["pedido"])
        self.assertIn(student.COMPILE_DRAFT, step["pedido_rascunho"])

    def test_rascunho_explica_o_motivo_e_o_que_fazer(self):
        keys = ["planejamento", "evidencias", "redacao", "revisao", "reescrita", "verificacao"]
        p = {**project({k: ACCEPT for k in keys}, status="rascunho"), "error": "1 erro(s) de LaTeX."}
        step = student.next_step(p, "artigo", 0)
        self.assertIn("rascunho", step["titulo"])
        self.assertIn("1 erro(s) de LaTeX", step["texto"])
        self.assertIn("reabra a reescrita", step["pedido"])
        self.assertIn(student.REF_FIX, student.next_step(p, "artigo", 2)["pedido"])

    def test_estados_do_servidor(self):
        for status, words in (("preparando", "Aguarde"), ("compilando", "Gerando"), ("concluido", "PDF final pronto"),
                              ("falhou_preparo", "falhou"), ("refazendo_referencias", "Refazendo")):
            self.assertIn(words, student.next_step(project(status=status), "artigo", 0)["titulo"])

    def test_revisao_sistematica(self):
        step = student.next_step(project(), "revisao_sistematica", 0)
        self.assertEqual(step["titulo"], "Próximo: Protocolo")


class ProofsTest(unittest.TestCase):
    def test_frases(self):
        stages = {
            "evidencias": {"status": "aceita", "summary": {"conferidas": 19, "total": 19}},
            "redacao": {"status": "aceita", "summary": {"fontes_citadas": ["a", "b"]}},
            "revisao": {"status": "aceita", "summary": {"nota_geral": 7.5, "problemas": {"alta": 1, "media": 2}}},
            "verificacao": {"status": "aceita", "summary": {"vereditos": {"sustentada": 9, "parcial": 1, "sem_suporte": 0}}},
        }
        lines = student.proofs(stages, "artigo", {"kappa": 0.81})
        self.assertIn("Evidências: 19 de 19 citações", lines[0])
        self.assertIn("cita 2 fontes", lines[1])
        self.assertIn("não conferidas", lines[2])  # projeto anterior à checagem do texto final
        self.assertIn("nota 7.5 de 10", lines[3])
        self.assertIn("9 sustentadas", lines[4])
        self.assertIn("0.81", lines[5])

    def test_citacoes_do_texto_final(self):
        stages = {"reescrita": {"status": "aceita", "summary": {
            "fontes_citadas": ["a"], "citacoes_texto": {"total": 12, "conferidas": 11, "traduzidas": 1}}}}
        lines = student.proofs(stages, "artigo")
        self.assertIn("Texto final: 11 de 12 citações diretas conferidas", lines[1])
        self.assertIn("1 marcada(s) como tradução", lines[1])

    def test_sem_etapas_aceitas(self):
        self.assertEqual(student.proofs({"evidencias": {"status": "recusada", "summary": {"total": 5}}}, "artigo"), [])


class ReferencesTest(unittest.TestCase):
    def test_sugeridas_e_do_arquivo_pedem_confirmacao(self):
        refs = [{"key": "a", "how": "arquivo", "fields": {"title": "172633"}},
                {"key": "b", "how": "doi", "fields": {"title": "Ok"}},
                {"key": "c", "how": "corrigida_pelo_texto", "fields": {"title": "Ok"}},
                {"key": "d", "how": "texto_do_pdf", "fields": {"title": "Department of Computer Science"}}]
        out = student.view(project(), "artigo", refs)
        self.assertEqual([(r["chave"], r["nivel"]) for r in out["referencias_a_conferir"]],
                         [("a", "a_conferir"), ("d", "sugerida")])
        self.assertIn(student.REF_FIX, out["pedido_referencias"])
        self.assertEqual(student.view(project(), "artigo", refs[1:3])["pedido_referencias"], "")


if __name__ == "__main__":
    unittest.main()
