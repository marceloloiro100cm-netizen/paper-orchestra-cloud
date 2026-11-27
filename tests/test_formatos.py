"""Registro de normas (formatos/): ABNT migrada sem mudança e APA 7 configurável."""
from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import formatos  # noqa: E402
import apa_refs  # noqa: E402
import docx_export  # noqa: E402
import mcp_flow as flow  # noqa: E402
import mcp_jobs  # noqa: E402

DATE = datetime(2026, 11, 27, tzinfo=timezone.utc)
APA_BODY = ("\\begin{abstract}\nResumo.\n\\par\\textit{Palavras-chave}: a, b\n\\end{abstract}\n"
            "Introdução sem título \\parencite{silva2020}.\n"
            "\\section{Método}\nSegundo \\textcite{silva2020}.\n"
            "\\section{Resultados}\nDados \\parencite[p.~12]{silva2020}.\n"
            "\\section{Discussão}\nFim.\n")
REF = {"key": "silva2020", "type": "article", "fields": {
    "author": "Silva, João Antônio and Souza, Maria", "title": "Aprendizagem ativa",
    "journal": "Revista Brasileira de Educação", "volume": "25", "number": "3", "pages": "10--25",
    "year": "2020", "doi": "10.1590/abc.123"}}


class RegistryTest(unittest.TestCase):
    def test_todas_as_pastas_sao_validas_e_tem_padrao(self):
        pastas = sorted(p.name for p in (ROOT / "formatos").iterdir() if (p / "formato.json").is_file())
        self.assertEqual(sorted(formatos.ids()), pastas)
        for fid in ("abnt-artigo", "abnt-dissertacao", "abnt-tcc", "apa7", "artigo-simples"):
            self.assertIn(fid, formatos.ids())
        self.assertEqual(formatos.obter("nao-existe")["id"], formatos.PADRAO)
        self.assertEqual(sorted(flow.TEMPLATES), sorted(formatos.ids()))

    def test_ajuste_por_tipo_dentro_da_mesma_familia(self):
        self.assertEqual(formatos.ajustar_ao_tipo("abnt-artigo", "dissertacao"), "abnt-dissertacao")
        self.assertEqual(formatos.ajustar_ao_tipo("abnt-artigo", "tcc"), "abnt-tcc")
        self.assertEqual(formatos.ajustar_ao_tipo("abnt-dissertacao", "artigo"), "abnt-artigo")
        self.assertEqual(formatos.ajustar_ao_tipo("apa7", "revisao_sistematica"), "apa7")
        self.assertFalse(formatos.aceita_tipo(formatos.ajustar_ao_tipo("apa7", "dissertacao"), "dissertacao"))

    def test_catalogo_do_site_mostra_familias_e_esconde_artigo_simples(self):
        cat = {f["id"]: f for f in formatos.catalogo()}
        self.assertNotIn("artigo-simples", cat)
        self.assertEqual(cat["apa7"]["familia"], "APA 7")
        self.assertTrue(cat["apa7"]["tem_csl"])
        self.assertIn("Psicologia", cat["apa7"]["areas"])
        json.dumps(cat)  # vai para o site como JSON

    def test_apa7_baixado_com_origem_registrada(self):
        fmt = formatos.obter("apa7")
        csl = formatos.caminho_csl("apa7").read_text(encoding="utf-8")
        self.assertIn("<title>APA Style 7th edition</title>", csl)
        origem = {o["arquivo"]: o for o in fmt["origem"]}
        self.assertEqual(origem["apa.csl"]["repositorio"], "https://github.com/citation-style-language/styles")
        import hashlib
        self.assertEqual(hashlib.sha256(formatos.caminho_csl("apa7").read_bytes()).hexdigest(),
                         origem["apa.csl"]["sha256"])
        registry = json.loads((ROOT / "docs" / "upstreams.json").read_text(encoding="utf-8"))
        ids = {u["id"] for u in registry["upstreams"]}
        for item in fmt["origem"]:
            self.assertIn(item["upstream"], ids)

    def test_regras_chegam_a_ia_no_material_da_etapa(self):
        project = {"id": "p", "template": "apa7", "language": "pt-BR"}
        base = flow.material("planejamento", project, {}, [])
        self.assertIn("\\parencite", base["como_citar"]["parentetica"])
        self.assertIn("et al.", base["regras_do_formato"])
        abnt = flow.material("planejamento", {"id": "p", "template": "abnt-artigo"}, {}, [])
        self.assertEqual(abnt["como_citar"]["narrativa"], "\\citeonline{chave}")


class AssembleTest(unittest.TestCase):
    def test_apa7_usa_biblatex_apa_e_biber(self):
        tex = mcp_jobs.assemble({"template": "apa7", "language": "pt-BR", "title": "Título & teste"}, APA_BODY, DATE)
        self.assertIn("\\usepackage[style=apa,backend=biber,natbib=true]{biblatex}", tex)
        self.assertIn("\\usepackage[brazil]{babel}", tex)
        self.assertIn("Departamento e instituição a preencher", tex)
        self.assertIn("\\end{abstract}\n\\begin{center}\\bfseries Título \\& teste\\end{center}", tex)
        self.assertTrue(tex.rstrip().endswith("\\printbibliography\n\\end{document}"))
        self.assertNotIn("%(", tex.split("\\begin{document}")[1])
        self.assertEqual(mcp_jobs.bib_engine(tex), "biber")
        en = mcp_jobs.assemble({"template": "apa7", "language": "en", "title": "T"}, APA_BODY, DATE)
        self.assertIn("\\usepackage[english]{babel}", en)
        self.assertIn("Department and institution to be completed", en)

    def test_abnt_continua_com_bibtex(self):
        body = "\\begin{resumo}R\\end{resumo}\n\\section{A}\nx \\cite{k}"
        tex = mcp_jobs.assemble({"template": "abnt-artigo", "language": "pt-BR", "title": "T"}, body, DATE)
        self.assertIn("\\end{resumo}\n\\textual", tex)
        self.assertEqual(mcp_jobs.bib_engine(tex), "bibtex")

    def test_corpo_nao_pode_imprimir_bibliografia(self):
        with self.assertRaises(ValueError):
            mcp_jobs.assemble({"template": "apa7", "title": "T"}, APA_BODY + "\\printbibliography")
        self.assertEqual(flow.FORBIDDEN.pattern, mcp_jobs.FORBIDDEN.pattern)

    @unittest.skipUnless(shutil.which("biber") and shutil.which("pdflatex"), "biber/pdflatex ausentes")
    def test_smoke_apa7_compila(self):
        import format_smoke
        self.assertEqual(format_smoke.check("apa7", "pt-BR"), [])

    @unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex"), "pdflatex/bibtex ausentes")
    def test_smoke_artigo_simples_compila(self):
        import format_smoke
        self.assertEqual(format_smoke.check("artigo-simples", "en"), [])


class FlowTest(unittest.TestCase):
    def test_validacao_reconhece_citacoes_biblatex(self):
        self.assertEqual(flow.cited_keys("\\parencite[p.~3]{a,b} e \\textcite{c}"), ["a", "b", "c"])
        res = flow.validate_latex(APA_BODY, {"silva2020"}, 50, "apa7")
        self.assertTrue(res["ok"], res["erros"])
        res = flow.validate_latex(APA_BODY.replace("abstract", "resumo"), {"silva2020"}, 50, "apa7")
        self.assertIn("Inclua o ambiente \\begin{abstract} ... \\end{abstract}.", res["erros"])

    def test_metricas_contam_citacoes_biblatex(self):
        metrics = mcp_jobs.text_quality_metrics(APA_BODY, ["silva2020"])
        self.assertEqual(metrics["citacoes_por_fonte"]["silva2020"], 3)


class ApaWordTest(unittest.TestCase):
    def test_referencia_e_citacoes_apa7(self):
        self.assertEqual(apa_refs.reference_text(REF),
                         "Silva, J. A., & Souza, M. (2020). Aprendizagem ativa. Revista Brasileira de Educação, "
                         "25(3), 10\u201325. https://doi.org/10.1590/abc.123")
        italic = [t for t, i in apa_refs.reference_runs(REF) if i]
        self.assertEqual(italic, ["Revista Brasileira de Educação", "25"])
        self.assertEqual(apa_refs.cite_label(REF, "k", narrative=True), "Silva e Souza (2020)")
        self.assertEqual(apa_refs.cite_label(REF, "k", narrative=False, language="en"), "Silva & Souza, 2020")
        many = {"fields": {"author": " and ".join(f"Autor{n}, A." for n in range(25)), "year": "2021", "title": "X"}}
        self.assertEqual(apa_refs.cite_label(many, "m", narrative=False), "Autor0 et al., 2021")
        self.assertIn(", . . . Autor24, A.", apa_refs.authors_reference(many["fields"]["author"]))
        book = {"type": "book", "fields": {"author": "Lima, Ana", "title": "Livro", "publisher": "Penso",
                                           "year": "2019", "edition": "2"}}
        self.assertEqual(apa_refs.reference_text(book), "Lima, A. (2019). Livro (2. ed.). Penso.")

    def test_docx_apa7_espaco_duplo_recuo_deslocado_e_citacoes(self):
        tex = mcp_jobs.assemble({"template": "apa7", "language": "pt-BR", "title": "Título"}, APA_BODY, DATE)
        data = docx_export.build_docx("Título", tex, [REF], formato=formatos.obter("apa7"))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            doc = z.read("word/document.xml").decode("utf-8")
            styles = z.read("word/styles.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", "", doc)
        self.assertIn("padrão APA 7", text)
        self.assertIn("Segundo Silva e Souza (2020).", text)
        self.assertIn("(Silva &amp; Souza, 2020, p. 12)", text)
        self.assertIn("Palavras-chave: a, b", text)
        self.assertNotIn("Departamento e instituição", text)  # capa fica fora do Word
        self.assertIn("<w:i/>", doc)
        self.assertIn('w:line="480"', styles)
        self.assertIn('w:hanging="720"', styles)
        self.assertIn('w:top="1440"', doc)

    def test_docx_abnt_sem_formato_fica_igual(self):
        data = docx_export.build_docx("T", "\\section{A}\nx", [REF])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read("word/styles.xml").decode("utf-8"), docx_export.STYLES_XML)
            self.assertIn('w:top="1701"', z.read("word/document.xml").decode("utf-8"))


class DeployTest(unittest.TestCase):
    def test_imagens_e_deploy_levam_a_pasta_formatos(self):
        for service in ("api", "worker"):
            self.assertIn("COPY formatos/ /app/formatos/", (ROOT / service / "Dockerfile").read_text(encoding="utf-8"))
        worker = (ROOT / "worker" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn(" biber ", worker)
        self.assertIn("python format_smoke.py", worker)
        deploy = (ROOT / ".github" / "workflows" / "deploy-services.yml").read_text(encoding="utf-8")
        self.assertIn("- formatos/**", deploy)
        self.assertLess(deploy.index("cp -r formatos worker/formatos"), deploy.index('build worker "$WORKER_IMAGE"'))
        self.assertIn("cp -r formatos api/formatos", (ROOT / "scripts" / "deploy-cloud-shell.sh").read_text(encoding="utf-8"))


class StoreTest(unittest.TestCase):
    def test_store_recusa_norma_sem_modelo_para_o_tipo(self):
        try:
            import mcp_server
            from test_mcp import DB, Bucket
        except ImportError as exc:  # pragma: no cover - mcp ausente
            self.skipTest(str(exc))
        store = mcp_server.Store(DB(), Bucket(), lambda *a: None, lambda i: True)
        with self.assertRaises(mcp_server.Falha) as ctx:
            store.create_project("u", "Título", "Pergunta de pesquisa longa o bastante", ["f1"], "pt-BR",
                                 "apa7", "dissertacao")
        self.assertIn("APA 7", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
