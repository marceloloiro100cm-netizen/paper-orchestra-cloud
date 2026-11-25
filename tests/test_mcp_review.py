"""Modo revisão sistemática (MCP): protocolo, triagem dupla e kappa, consenso, qualidade e extração,
síntese com versão final do pesquisador e PRISMA 2020 com conservação dos números."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

import mcp_review as review  # noqa: E402
from test_mcp import HAVE_SDK, SOURCE_TEXT, UID, Bucket, DB, latex_body, seed_project  # noqa: E402

if HAVE_SDK:
    import mcp_server  # noqa: E402
    from test_mcp import McpHarness  # noqa: E402
else:  # pragma: no cover
    McpHarness = unittest.TestCase

PROTOCOL = {
    "pergunta": "Como a gamificação afeta o engajamento em cursos de programação?",
    "picoc": {"populacao": "estudantes de programação", "intervencao": "gamificação",
              "comparacao": "ensino sem gamificação", "resultado": "engajamento", "contexto": "ensino superior"},
    "questoes": ["Quais efeitos sobre o engajamento são relatados?", "Os efeitos se mantêm no tempo?"],
    "inclusao": ["Estudo empírico com estudantes"],
    "exclusao": ["Texto apenas opinativo"],
    "qualidade": ["O método está descrito?", "Há limitações declaradas?"],
    "escala": [{"descricao": "Sim", "peso": 1}, {"descricao": "Parcial", "peso": 0.5}, {"descricao": "Não", "peso": 0}],
    "nota_corte": 1.5, "excluir_abaixo_do_corte": True,
    "extracao": [{"campo": "Efeito", "descricao": "efeito relatado"}],
    "busca": {"bases": [{"nome": "Scopus", "registros": 5}, {"nome": "ERIC", "registros": 3}],
              "duplicados_removidos": 2, "excluidos_titulo_resumo": 3, "nao_recuperados": 1},
}


def screening(keys, decisions):
    out = []
    for n, key in enumerate(keys):
        d = decisions[n]
        item = {"chave": key, "decisao": d, "citacao_literal": SOURCE_TEXT[n % 3][:80],
                "checklist": {c: True for c in review.CHECKLIST}}
        if d != "fora_da_triagem":
            item["criterios"] = {"IC1": d == "incluir", "EC1": False}
        if d == "excluir":
            item["motivo"] = "IC1"
        out.append(item)
    return json.dumps(out, ensure_ascii=False)


class PureLogicTest(unittest.TestCase):
    def test_protocol_needs_scale_cut_and_criteria(self):
        self.assertTrue(review.validate_protocol(json.dumps(PROTOCOL))["ok"])
        bad = {**PROTOCOL, "escala": [{"descricao": "Sim", "peso": 1}], "nota_corte": 9}
        report = review.validate_protocol(json.dumps(bad))
        self.assertFalse(report["ok"])
        self.assertTrue(any("escala" in e for e in report["erros"]))

    def test_kappa_and_divergences(self):
        a = {"k1": "incluir", "k2": "excluir", "k3": "incluir", "k4": "excluir"}
        self.assertEqual(review.cohen_kappa(a, dict(a))["kappa"], 1.0)
        b = {**a, "k4": "incluir"}
        k = review.cohen_kappa(a, b)
        self.assertEqual(k["divergencias"], ["k4"])
        self.assertAlmostEqual(k["kappa"], 0.5)

    def test_prisma_conservation(self):
        protocol = review.parse_protocol(json.dumps(PROTOCOL))
        final = {"a": "incluir", "b": "excluir", "c": "fora_da_triagem"}
        out = review.prisma(protocol, final, {"b": "EC1"}, below_cut=[])
        self.assertEqual((out["avaliados"], out["incluidos"], out["motivos"]), (2, 1, {"EC1": 1}))
        # 8 identificados - 2 - 3 - 1 = 2 avaliados: fecha.
        self.assertTrue(out["fecha"], out["conferencias"])
        broken = review.prisma(protocol, {**final, "d": "incluir"}, {"b": "EC1"}, [])
        self.assertFalse(broken["fecha"])

    def test_zones(self):
        self.assertEqual(review.zone_of("3 Metodologia > 3.1 Participantes"), "metodo")
        self.assertEqual(review.zone_of("6. Limitações do estudo"), "limitacoes")
        self.assertEqual(review.zone_of("Results and discussion"), "resultados")
        self.assertEqual(review.zone_of("REFERÊNCIAS"), "referencias")


@unittest.skipUnless(HAVE_SDK, "SDK do MCP ausente")
class ReviewFlowTest(McpHarness):
    def setUp(self):
        super().setUp()
        self.db.collection("mcp_projects").document(self.pid).update({"tipo": "revisao_sistematica"})

    def deliver(self, stage, content, head):
        return self.run_calls([("entregar_etapa", {"projeto": self.pid, "etapa": stage, "cabeca": head,
                                                   "conteudo": content})])[0]

    def test_full_systematic_review(self):
        step = self.run_calls([("proxima_etapa", {"projeto": self.pid, "modelo_declarado": "Claude Opus 5.5"})])[0][1]
        self.assertEqual(step["etapa"], "protocolo")
        writer = step["cabeca"]
        self.assertFalse(self.deliver("protocolo", json.dumps(PROTOCOL, ensure_ascii=False), writer)[0])
        # Triagem: duas incluídas e uma fonte de método fora da triagem.
        decisions = ["incluir", "incluir", "fora_da_triagem"]
        err, out = self.deliver("triagem", screening(self.keys, decisions), writer)
        self.assertFalse(err, out)
        # Faltar uma fonte é recusado na triagem independente.
        handoff = self.run_calls([("proxima_etapa", {"projeto": self.pid, "cabeca": writer})])[0][1]
        self.assertTrue(handoff["precisa_de_conversa_nova"])
        opened = self.run_calls([("abrir_passe", {"codigo": handoff["passe"], "modelo_declarado": "Gemini 3 Pro"})])[0][1]
        self.assertNotIn("triagem", json.dumps(opened["material"].get("fontes_para_triar")))  # às cegas
        triadora = opened["cabeca"]
        refused = self.deliver("triagem_independente", screening(self.keys[:2], decisions[:2]), triadora)[1]
        self.assertFalse(refused["aceita"])
        accepted = self.deliver("triagem_independente", screening(self.keys, ["incluir", "excluir", "fora_da_triagem"]),
                                triadora)[1]
        self.assertTrue(accepted["aceita"], accepted)
        self.assertEqual(accepted["concordancia"]["divergencias"], [self.keys[1]])
        self.assertEqual(accepted["independencia"]["nivel"], "outra_ia")
        # Consenso resolve a divergência.
        consenso = json.dumps([{"chave": self.keys[1], "decisao_final": "incluir",
                                "justificativa": "Relê o método: é estudo empírico com estudantes."}])
        self.assertFalse(self.deliver("consenso", consenso, writer)[0])
        # Qualidade e extração: uma nota abaixo do corte, citações conferidas.
        def study(key, answers, n):
            text = SOURCE_TEXT[n % 3][:70]
            return {"chave": key, "qualidade": dict(zip(["AQ1", "AQ2"], answers)),
                    "extracao": {"Efeito": {"valor": "engajamento maior", "citacao_literal": text}},
                    "trechos": {"metodo": text, "resultados": text, "limitacoes": "nao_relatado"}}
        rows = [study(self.keys[0], ["Sim", "Sim"], 0), study(self.keys[1], ["Sim", "Não"], 1)]
        err, out = self.deliver("qualidade_extracao", json.dumps(rows, ensure_ascii=False), writer)
        self.assertFalse(err, out)
        self.assertEqual(out["resumo"]["abaixo_do_corte"], [self.keys[1]])
        # Síntese só pode usar a amostra final (o estudo abaixo do corte saiu).
        bad = {"QP1": {"resposta": "x" * 100, "chaves": [self.keys[1]]}, "QP2": {"resposta": "y" * 100, "chaves": []}}
        self.assertFalse(self.deliver("sintese", json.dumps(bad), writer)[1]["aceita"])
        good = {"QP1": {"resposta": "Os estudos relatam aumento de engajamento. " * 3, "chaves": [self.keys[0]]},
                "QP2": {"resposta": "Os estudos não acompanham os efeitos no tempo. " * 3, "chaves": []}}
        self.assertTrue(self.deliver("sintese", json.dumps(good, ensure_ascii=False), writer)[1]["aceita"])
        # Versão final do pesquisador substitui a da IA no material da redação.
        project = self.db.collection("mcp_projects").document(self.pid).get().to_dict()
        self.db.collection("mcp_projects").document(self.pid).update(
            {"sintese_final": {"QP1": "Versão do pesquisador para QP1."}})
        step = self.run_calls([("proxima_etapa", {"projeto": self.pid, "cabeca": writer})])[0][1]
        self.assertEqual(step["etapa"], "redacao")
        material = step["material"]
        self.assertEqual(material["sintese"]["QP1"]["versao"], "pesquisador")
        self.assertEqual(material["prisma"]["incluidos"], 1)
        self.assertEqual(material["prisma"]["excluidos_qualidade"], 1)
        self.assertTrue(material["prisma"]["fecha"])
        self.assertIn("%PRISMA", material["figura_prisma"])
        self.assertEqual(project["concordancia"]["divergencias"], [self.keys[1]])

    def test_no_divergence_skips_consensus(self):
        step = self.run_calls([("proxima_etapa", {"projeto": self.pid, "modelo_declarado": "Claude"})])[0][1]
        writer = step["cabeca"]
        self.deliver("protocolo", json.dumps(PROTOCOL), writer)
        decisions = ["incluir", "incluir", "incluir"]
        self.deliver("triagem", screening(self.keys, decisions), writer)
        code = self.run_calls([("proxima_etapa", {"projeto": self.pid, "cabeca": writer})])[0][1]["passe"]
        triadora = self.run_calls([("abrir_passe", {"codigo": code})])[0][1]["cabeca"]
        out = self.deliver("triagem_independente", screening(self.keys, decisions), triadora)[1]
        self.assertEqual(out["concordancia"]["kappa"], 1.0)
        nxt = self.run_calls([("proxima_etapa", {"projeto": self.pid, "cabeca": writer})])[0][1]
        self.assertEqual(nxt["etapa"], "qualidade_extracao")

    def test_zone_filter_in_search(self):
        out = self.run_calls([("buscar_trechos", {"projeto": self.pid, "consulta": "engajamento",
                                                  "zona": "resultados"})])[0][1]
        self.assertTrue(out["resultados"])
        self.assertTrue(all(r["zona"] == "resultados" for r in out["resultados"]))


if __name__ == "__main__":
    unittest.main()
