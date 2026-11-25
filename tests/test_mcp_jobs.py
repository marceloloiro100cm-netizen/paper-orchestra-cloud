"""Worker do modo sem API (MCP): preparo das fontes e compilação restrita, sem IA."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

import mcp_flow  # noqa: E402
import mcp_jobs  # noqa: E402
from test_mcp import DB, Bucket, UID, latex_body, seed_project  # noqa: E402

HAVE_TEX = bool(shutil.which("pdflatex") and shutil.which("bibtex") and subprocess.run(
    ["kpsewhich", "natbib.sty"], capture_output=True, text=True).stdout.strip())


class SharedRulesTest(unittest.TestCase):
    def test_forbidden_list_is_identical_in_api_and_worker(self):
        self.assertEqual(mcp_flow.FORBIDDEN.pattern, mcp_jobs.FORBIDDEN.pattern)

    def test_assemble_refuses_forbidden_body(self):
        project = {"title": "T", "language": "pt-BR", "template": "abnt-artigo"}
        with self.assertRaises(ValueError):
            mcp_jobs.assemble(project, latex_body(["k"], "\\input{/etc/passwd}"))

    def test_assemble_dates_and_escapes(self):
        project = {"title": "Custos & 100% de_teste", "language": "pt-BR", "template": "abnt-artigo"}
        tex = mcp_jobs.assemble(project, latex_body(["k"]), datetime(2026, 11, 25, tzinfo=timezone.utc))
        self.assertIn(r"\titulo{Custos \& 100\% de\_teste}", tex)
        self.assertIn(r"\data{25 de novembro de 2026}", tex)
        self.assertIn("\\end{resumo}\n\\textual", tex)
        self.assertTrue(tex.rstrip().endswith("\\end{document}"))


class PrismaFigureTest(unittest.TestCase):
    PRISMA = {"bases": [{"nome": "Scopus & ERIC", "registros": 8}], "identificados": 8, "duplicados": 2, "triados": 6,
              "excluidos_titulo_resumo": 3, "procurados": 3, "nao_recuperados": 1, "avaliados": 2,
              "excluidos_elegibilidade": 1, "motivos": {"EC1": 1}, "excluidos_qualidade": 0, "incluidos": 1,
              "fora_da_triagem": ["k"]}

    def test_marker_is_replaced_and_names_escaped(self):
        project = {"title": "T", "language": "pt-BR", "template": "abnt-artigo", "tipo": "revisao_sistematica",
                   "prisma": self.PRISMA}
        body = latex_body(["k"]).replace("\\section{Seção 1}", "%PRISMA\n\\section{Seção 1}")
        tex = mcp_jobs.assemble(project, body)
        self.assertNotIn("%PRISMA", tex)
        self.assertIn("Fluxograma PRISMA 2020", tex)
        self.assertIn("Scopus \\& ERIC: 8", tex)
        self.assertIn("(n = 1)", tex)

    def test_without_marker_goes_before_results_or_end(self):
        fig = mcp_jobs.prisma_figure(self.PRISMA)
        body = "\\section{Método}\nx\n\\section{Resultados}\ny"
        placed = mcp_jobs.place_prisma(body, fig)
        self.assertLess(placed.index("Fluxograma"), placed.index("\\section{Resultados}"))
        self.assertTrue(mcp_jobs.place_prisma("texto", fig).rstrip().endswith("\\end{figure}"))


class PrepareTest(unittest.TestCase):
    def test_prepare_writes_manifest_and_official_bib(self):
        db, bucket = DB(), Bucket()
        pid, _, _ = seed_project(db, bucket, status="preparando")
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        events = []
        data = {"mcp_project_id": pid, "sources": project["sources"]}

        def derive(entry, fetch, cache):
            return {"document": {"pages_total": 3}, "chunks": [{"chunk_id": "c1", "text": "t"}]}, "miss"

        def openalex(url):
            return {"title": "Estudo oficial", "publication_year": 2023, "type": "article",
                    "authorships": [{"author": {"display_name": "Ana Souza"}}],
                    "primary_location": {"source": {"display_name": "Revista Brasileira"}}}

        project["sources"][0]["origin"] = {"doi": "10.1234/abc"}
        data["sources"] = project["sources"]
        summary = mcp_jobs.prepare(data, db=db, bucket=bucket, owner_uid=UID, cache=None, get_json=openalex,
                                   update=lambda **f: events.append(f), derive=derive,
                                   metadata=lambda e, f, c: {"pdf_title": ""})
        self.assertEqual(summary["lidas"], 3)
        prefix = f"mcp/{UID}/{pid}"
        refs = json.loads(bucket.objects[prefix + "/references.json"])
        self.assertEqual(refs[0]["fields"]["journal"], "Revista Brasileira")
        self.assertEqual(len(summary["referencias_a_conferir"]), 2)  # sem DOI nem título do PDF
        manifest = json.loads(bucket.objects[prefix + "/sources.json"])
        self.assertTrue(all(m["key"] and m["derived"] in bucket.objects for m in manifest))
        self.assertEqual(db.collection("mcp_projects").document(pid).get().to_dict()["status"], "pronto")
        self.assertEqual(events[-1]["status"], "completed")

    def test_prepare_refuses_foreign_paths(self):
        db, bucket = DB(), Bucket()
        pid, _, _ = seed_project(db, bucket, status="preparando")
        data = {"mcp_project_id": pid, "sources": [{"id": "x", "object_path": "library/outra/x/a.pdf"}]}
        with self.assertRaises(ValueError):
            mcp_jobs.prepare(data, db=db, bucket=bucket, owner_uid=UID, cache=None, get_json=None,
                             update=lambda **f: None, derive=None, metadata=None)


class CompileTest(unittest.TestCase):
    def _accepted(self, db, bucket, template):
        pid, manifest, refs = seed_project(db, bucket)
        keys = [r["key"] for r in refs]
        ref = db.collection("mcp_projects").document(pid)
        prefix = f"mcp/{UID}/{pid}"
        bucket.blob(prefix + "/etapas/reescrita-v2.txt").upload_from_string(latex_body(keys).replace(
            "resumo", "abstract" if template == "artigo-simples" else "resumo"))
        stages = {k: {"status": "aceita", "version": 1, "head": {"id": "cab_w", "kind": "redatora",
                                                                "model": "Claude Opus 5.5"}}
                  for k in mcp_flow.STAGE_KEYS}
        stages["reescrita"]["version"] = 2
        stages["revisao"].update(head={"id": "cab_r", "kind": "revisora", "model": "Gemini 3 Pro"},
                                 independencia={"nivel": "outra_ia"})
        # Inglês no artigo simples: o TeX local pode não ter o babel em português (o worker tem).
        ref.update({"stages": stages, "template": template, "status": "compilando", "flow_version": "mcp-flow-1",
                    "language": "en" if template == "artigo-simples" else "pt-BR"})
        return pid

    def test_compile_with_fake_compiler_records_provenance(self):
        db, bucket = DB(), Bucket()
        pid = self._accepted(db, bucket, "abnt-artigo")
        seen = {}

        def fake(workdir, tex):
            seen["tex"] = tex
            pdf = workdir / "scriptorium.pdf"
            pdf.write_bytes(b"%PDF-1.4" + b"0" * 2000)
            return pdf, {"status": "ok", "citacoes_indefinidas": 0}

        with tempfile.TemporaryDirectory() as tmp:
            record = mcp_jobs.compile_project({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                              update=lambda **f: None, workdir=Path(tmp), compiler=fake)
        self.assertIn("\\bibliography{references}", seen["tex"])
        self.assertEqual(record["ias_usadas"], ["Claude Opus 5.5", "Gemini 3 Pro"])
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        self.assertEqual(project["status"], "concluido")
        self.assertIn(f"mcp/{UID}/{pid}/final/scriptorium.pdf", bucket.objects)

    @unittest.skipUnless(HAVE_TEX, "TeX ausente")
    def test_real_compile_simple_article(self):
        db, bucket = DB(), Bucket()
        pid = self._accepted(db, bucket, "artigo-simples")
        with tempfile.TemporaryDirectory() as tmp:
            record = mcp_jobs.compile_project({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                              update=lambda **f: None, workdir=Path(tmp))
        self.assertEqual(record["compilacao"]["status"], "ok", record["compilacao"])
        self.assertEqual(record["compilacao"]["citacoes_indefinidas"], 0)

    @unittest.skipUnless(HAVE_TEX, "TeX ausente")
    def test_tex_cannot_read_outside_workdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tex = "\\documentclass{article}\\begin{document}X\\input{/etc/hostname}\\end{document}\n"
            pdf, report = mcp_jobs.compile_tex(Path(tmp), tex, name="t")
            self.assertIsNone(pdf)
            self.assertIn("hostname.tex' not found", Path(tmp, "t.log").read_text(errors="replace"))


if __name__ == "__main__":
    unittest.main()
