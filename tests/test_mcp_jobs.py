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

    def test_reference_levels_are_identical_in_api_and_worker(self):
        import bib_integrity
        self.assertEqual(mcp_flow.REF_LEVELS, bib_integrity.REF_LEVELS)

    def test_draft_marks_title_and_top_of_the_pdf(self):
        project = {"title": "T", "language": "pt-BR", "template": "abnt-artigo"}
        tex = mcp_jobs.assemble(project, latex_body(["k"]), draft=["2 referência(s) ainda não confirmada(s): a_b."])
        self.assertIn(r"\titulo{RASCUNHO: T}", tex)
        self.assertIn(r"\textbf{RASCUNHO}", tex)
        self.assertIn(r"a\_b.", tex)
        self.assertLess(tex.index("RASCUNHO}"), tex.index("\\begin{resumo}"))
        self.assertNotIn("RASCUNHO", mcp_jobs.assemble(project, latex_body(["k"])))

    def test_latex_errors_keep_the_line(self):
        log = "x\n! Undefined control sequence.\nl.42 Texto \\foo\n\n! Missing $ inserted.\n"
        self.assertEqual(mcp_jobs.latex_errors(log),
                         ["Undefined control sequence. (l.42 Texto \\foo)", "Missing $ inserted."])

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
        self.assertEqual(refs[0]["consulta"]["status"], "ok")
        self.assertEqual(summary["consultas_openalex"]["recusadas"], 0)
        manifest = json.loads(bucket.objects[prefix + "/sources.json"])
        self.assertTrue(all(m["key"] and m["derived"] in bucket.objects for m in manifest))
        self.assertEqual(db.collection("mcp_projects").document(pid).get().to_dict()["status"], "pronto")
        self.assertEqual(events[-1]["status"], "completed")

    def test_prepare_tells_refused_api_apart_from_no_match(self):
        db, bucket = DB(), Bucket()
        pid, _, _ = seed_project(db, bucket, status="preparando")
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        project["sources"][0]["origin"] = {"doi": "10.1234/abc"}

        def derive(entry, fetch, cache):
            return {"document": {"pages_total": 1}, "chunks": [{"chunk_id": "c1", "text": "t", "pages": [1, 1]}]}, "miss"

        class Refused(Exception):
            response = type("R", (), {"status_code": 429})()

        def refused(url):
            raise Refused("https://api.openalex.org/works?api_key=SEGREDO")

        summary = mcp_jobs.prepare({"mcp_project_id": pid, "sources": project["sources"]}, db=db, bucket=bucket,
                                   owner_uid=UID, cache=None, get_json=refused, update=lambda **f: None,
                                   derive=derive, metadata=lambda e, f, c: {"pdf_title": ""})
        refs = json.loads(bucket.objects[f"mcp/{UID}/{pid}/references.json"])
        self.assertEqual(refs[0]["consulta"]["status"], "api_recusou")
        self.assertEqual(refs[0]["consulta"]["erros"], ["Refused 429"])
        self.assertNotIn("SEGREDO", json.dumps(refs))
        self.assertIn("OpenAlex recusou", refs[0]["fields"]["note"])
        self.assertEqual(summary["consultas_openalex"]["recusadas"], 1)

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

    def _fake(self, seen, errors=0):
        def fake(workdir, tex):
            seen.append(tex)
            pdf = workdir / "scriptorium.pdf"
            pdf.write_bytes(b"%PDF-1.4" + b"0" * 2000)
            return pdf, {"status": "ok", "citacoes_indefinidas": 0, "erros_latex": errors,
                         "erros_detalhe": ["Undefined control sequence."] if errors else []}
        return fake

    def test_unconfirmed_reference_turns_the_pdf_into_a_draft(self):
        db, bucket = DB(), Bucket()
        pid = self._accepted(db, bucket, "abnt-artigo")
        path = f"mcp/{UID}/{pid}/references.json"
        refs = json.loads(bucket.objects[path])
        refs[1]["how"] = "texto_do_pdf"
        bucket.objects[path] = json.dumps(refs).encode()
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            record = mcp_jobs.compile_project({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                              update=lambda **f: None, workdir=Path(tmp), compiler=self._fake(seen))
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        self.assertEqual(project["status"], "rascunho")
        self.assertIn(refs[1]["key"], project["error"])
        self.assertIn("RASCUNHO", seen[0])
        self.assertEqual(record["compilacao"]["versao"], "rascunho")
        self.assertEqual(record["referencias_a_conferir"], [refs[1]["key"]])

    def test_latex_error_recompiles_as_draft(self):
        db, bucket = DB(), Bucket()
        pid = self._accepted(db, bucket, "abnt-artigo")
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            record = mcp_jobs.compile_project({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                              update=lambda **f: None, workdir=Path(tmp),
                                              compiler=self._fake(seen, errors=1))
        self.assertEqual(len(seen), 2)
        self.assertNotIn("RASCUNHO", seen[0])
        self.assertIn("1 erro(s) de LaTeX", seen[1])
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        self.assertEqual(project["status"], "rascunho")
        self.assertEqual(project["compile_report"]["erros_detalhe"], ["Undefined control sequence."])

    def test_requested_draft_is_marked(self):
        db, bucket = DB(), Bucket()
        pid = self._accepted(db, bucket, "abnt-artigo")
        db.collection("mcp_projects").document(pid).update({"compile_rascunho": True})
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            mcp_jobs.compile_project({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                     update=lambda **f: None, workdir=Path(tmp), compiler=self._fake(seen))
        self.assertIn("Rascunho pedido pelo pesquisador", seen[0])
        self.assertEqual(db.collection("mcp_projects").document(pid).get().to_dict()["status"], "rascunho")

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


class RebuildReferencesTest(unittest.TestCase):
    def test_keeps_keys_and_corrections_and_restores_status(self):
        db, bucket = DB(), Bucket()
        pid, manifest, refs = seed_project(db, bucket, status="refazendo_referencias")
        db.collection("mcp_projects").document(pid).update({"status_antes": "rascunho"})
        path = f"mcp/{UID}/{pid}/references.json"
        refs[0]["how"] = "corrigida_pelo_texto"
        refs[1]["how"], refs[1]["fields"] = "arquivo", {"title": "172633"}
        bucket.objects[path] = json.dumps(refs).encode()
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        project["sources"][1]["origin"] = {"doi": "10.1234/abc"}
        db.collection("mcp_projects").document(pid).update({"sources": project["sources"]})

        def openalex(url):
            if "doi:10.1234/abc" in url:
                return {"title": "Título oficial da tese", "publication_year": 2017, "type": "dissertation",
                        "authorships": [{"author": {"display_name": "Vania Cristina Lasalvia"}}]}
            return {"results": []}

        summary = mcp_jobs.rebuild_references({"mcp_project_id": pid}, db=db, bucket=bucket, owner_uid=UID,
                                              cache=None, get_json=openalex, update=lambda **f: None,
                                              metadata=lambda e, f, c: {"pdf_title": ""})
        new = json.loads(bucket.objects[path])
        self.assertEqual([r["key"] for r in new], [r["key"] for r in refs])
        self.assertEqual(new[0], refs[0])  # correção conferida no documento fica
        self.assertEqual((new[1]["how"], new[1]["fields"]["title"]), ("doi", "Título oficial da tese"))
        self.assertEqual(summary["alteradas"], [refs[1]["key"]])
        project = db.collection("mcp_projects").document(pid).get().to_dict()
        self.assertEqual(project["status"], "pronto")
        self.assertIn("compilar de novo", project["error"])
        self.assertIn(f"@phdthesis{{{refs[1]['key']},", bucket.objects[f"mcp/{UID}/{pid}/references.bib"].decode())


if __name__ == "__main__":
    unittest.main()
