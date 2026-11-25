"""Onda 6 do plano V2 (lacunas de engenharia): M02, M03, M07, M08, M09, M13,
M15, M21, M24, M25, M26 e M27. Sem rede; PyMuPDF só nos testes que renderizam."""
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))
from fastapi import HTTPException  # noqa: E402

import csl_export  # noqa: E402
import library  # noqa: E402
import library_index  # noqa: E402
import manual_reviews  # noqa: E402
import research_tools  # noqa: E402
import reviews  # noqa: E402
import upload_guard  # noqa: E402
import zotero_import as zi  # noqa: E402
from coverage_facets import _year_from_text, build_facets  # noqa: E402
from editorial_recheck import recheck  # noqa: E402
from neon_review import build_review_prompt, evidence_digest  # noqa: E402
from stage_budget import Cancelled, StageBudget  # noqa: E402

try:
    import pymupdf  # noqa: F401
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz  # noqa: F401
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False


# ------------------------------------------------------------------ fakes
class Snap:
    def __init__(self, data):
        self.data, self.exists = data, data is not None

    def to_dict(self):
        return None if self.data is None else dict(self.data)


class Ref:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def get(self, transaction=None):
        return Snap(self.store.get(self.path))

    def set(self, value):
        self.store[self.path] = dict(value)

    def update(self, fields):
        self.store[self.path] = {**self.store[self.path], **fields}

    def create(self, value):
        assert self.path not in self.store
        self.store[self.path] = dict(value)


class Query:
    def __init__(self, store, name, conds=()):
        self.store, self.name, self.conds = store, name, conds

    def where(self, field, op, value):
        return Query(self.store, self.name, self.conds + ((field, value),))

    def limit(self, n):
        return self

    def stream(self):
        for (name, _), value in list(self.store.items()):
            if name == self.name and all(value.get(f) == v for f, v in self.conds):
                yield Snap(value)


class Collection(Query):
    def document(self, key):
        return Ref(self.store, (self.name, key))


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Collection(self.store, name)


class Blob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name
        self.generation, self.updated = 1, datetime(2026, 11, 24, tzinfo=timezone.utc)

    def exists(self):
        return self.name in self.bucket.objects

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        self.bucket.objects[self.name] = data.encode() if isinstance(data, str) else data

    def upload_from_filename(self, path, content_type=None):
        self.bucket.objects[self.name] = Path(path).read_bytes()

    def download_as_bytes(self):
        return self.bucket.objects[self.name]

    def download_to_filename(self, path):
        Path(path).write_bytes(self.bucket.objects[self.name])

    def delete(self):
        self.bucket.objects.pop(self.name, None)


class Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return Blob(self, name)

    def list_blobs(self, prefix=""):
        return [Blob(self, n) for n in sorted(self.objects) if n.startswith(prefix)]


def endpoint(router, suffix, method=None):
    return next(r.endpoint for r in router.routes if r.path.endswith(suffix)
                and (method is None or method in r.methods))


def make_docx(extra: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:body>texto</w:body></w:document>")
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return buf.getvalue()


# ------------------------------------------------------------- M15
class StageBudgetTest(unittest.TestCase):
    def test_optional_stage_skipped_when_time_does_not_fit(self):
        now = [0.0]
        budget = StageBudget(clock=lambda: now[0], total_seconds=1000)
        now[0] = 900  # restam 100 s; a conferência de referências pede 720 s
        self.assertFalse(budget.allows("conferencia_de_referencias"))
        self.assertEqual(budget.records["conferencia_de_referencias"]["status"], "pulada_por_orcamento")
        self.assertTrue(budget.allows("agentes_de_redacao"))  # etapa obrigatória

    def test_cancel_and_report(self):
        flag = [False]
        now = [0.0]
        budget = StageBudget(lambda: flag[0], clock=lambda: now[0], total_seconds=1000)
        budget.start("triagem_cientifica")
        now[0] = 5
        budget.finish("triagem_cientifica", findings=2)
        report = budget.report()
        self.assertEqual(report["stages"]["triagem_cientifica"]["seconds"], 5)
        self.assertEqual(report["stages"]["triagem_cientifica"]["findings"], 2)
        flag[0] = True
        with self.assertRaises(Cancelled):
            budget.check_cancel()

    def test_firestore_error_does_not_cancel(self):
        def broken():
            raise RuntimeError("indisponível")
        StageBudget(broken).check_cancel()  # não levanta


# ------------------------------------------------------------- M09
class FacetsTest(unittest.TestCase):
    def test_groups_by_author_epoch_and_theme(self):
        chunks = [
            {"chunk_id": "a1", "source_id": "a", "index": 0,
             "text": "Revista X, 2019. Sala de aula invertida melhora engajamento dos estudantes."},
            {"chunk_id": "a2", "source_id": "a", "index": 1, "text": "Metodologia quantitativa."},
            {"chunk_id": "b1", "source_id": "b", "index": 0, "text": "Ensino remoto e avaliação formativa."},
        ]
        meta = {"a": {"name": "A.pdf"}, "b": {"name": "B.pdf"}}
        metadata = {"a": {"author": "Bergmann, J.", "file_year": 2021}, "b": {"author": "", "file_year": 2008}}
        questions = [{"kind": "pergunta", "text": "A sala de aula invertida melhora o engajamento?"},
                     {"kind": "pergunta", "text": "Como funciona a avaliação formativa no ensino remoto?"}]
        facets = build_facets(questions, chunks, ["a1", "b1"], meta, metadata, today=date(2026, 11, 24))
        self.assertEqual(facets["by_author"]["Bergmann, J."]["chunks_selected"], 1)
        self.assertIn("não informado", facets["by_author"])
        self.assertIn("2010s", facets["by_epoch"])  # 2019 na primeira página
        self.assertIn("2000s", facets["by_epoch"])  # ano do arquivo, rotulado
        b = next(s for s in facets["sources"] if s["source_id"] == "b")
        self.assertIn("data do arquivo", b["year_note"])
        self.assertEqual(facets["by_theme"][0]["coverage"], "uma_fonte")
        self.assertEqual(facets["by_theme"][1]["sources"], {"B.pdf": 1})

    def test_future_years_ignored(self):
        self.assertIsNone(_year_from_text("previsto para 2099", today=date(2026, 1, 1)))


# ------------------------------------------------------------- M24
class ManualHistoryTest(unittest.TestCase):
    def test_api_and_worker_fingerprints_match(self):
        ref = {"doi": "https://doi.org/10.1590/ABC", "title": "Educa{\\c c}ão {Ativa}: um estudo"}
        self.assertEqual(reviews.reference_fingerprint(ref), manual_reviews.fingerprint(ref))

    def test_previous_decision_applied_by_doi_and_title(self):
        history = [
            {"decision": "referencia_incorreta", "at": "2026-10-01", "job_id": "old1",
             "reference_fingerprint": {"doi": "10.1/x", "title_norm": "outra"}},
            {"decision": "referencia_confirmada", "at": "2026-11-01", "job_id": "old2",
             "reference_fingerprint": {"doi": "10.1/x", "title_norm": "outra"}},
            {"decision": "referencia_confirmada", "at": "2026-11-02", "job_id": "old3",
             "reference_fingerprint": {"doi": "", "title_norm": "metodologias ativas no ensino superior"}},
        ]
        report = {"items": [
            {"reference": {"key": "k1", "doi": "10.1/X", "title": "Qualquer"}},
            {"reference": {"key": "k2", "doi": "", "title": "Metodologias ativas no ensino superior"}},
            {"reference": {"key": "k3", "doi": "", "title": "Sem histórico algum"}},
        ]}
        manual_reviews.apply_history(report, history)
        items = report["items"]
        self.assertEqual(items[0]["manual_history"]["decision"], "referencia_confirmada")  # a mais recente
        self.assertEqual(items[0]["manual_history"]["matched_by"], "doi")
        self.assertEqual(items[1]["manual_history"]["matched_by"], "titulo")
        self.assertNotIn("manual_history", items[2])
        self.assertEqual(report["manual_history_summary"]["confirmadas"], 2)

    def test_load_history_ignores_current_job_and_other_owners(self):
        db = DB()
        fp = {"doi": "10.1/x", "title_norm": "t"}
        for i, (owner, job, ttype) in enumerate([("u1", "j1", "reference"), ("u1", "j2", "reference"),
                                                  ("u2", "j3", "reference"), ("u1", "j4", "claim")]):
            db.store[("research_reviews", f"r{i}")] = {
                "owner_uid": owner, "job_id": job, "target_type": ttype,
                "decision": "referencia_confirmada", "reference_fingerprint": fp, "at": str(i)}
        rows = manual_reviews.load_history(db, "u1", current_job="j2")
        self.assertEqual([r["job_id"] for r in rows], ["j1"])


# ------------------------------------------------------------- M07
class RecheckTest(unittest.TestCase):
    def test_reports_changes_without_touching_original(self):
        report = {"checked_at": "2026-01-01", "items": [
            {"reference": {"key": "a", "doi": "10.1/a", "title": "A"},
             "editorial": {"editorial_status": "no_notice_found", "label": "Sem aviso"}},
            {"reference": {"key": "b", "doi": "10.1/b", "title": "B"},
             "editorial": {"editorial_status": "no_notice_found"}},
            {"reference": {"key": "c", "doi": "", "title": "C"}},
        ]}
        states = {"10.1/a": {"editorial_status": "retracted", "label": "Retratada", "notices": [{"type": "retraction"}]},
                  "10.1/b": {"editorial_status": "no_notice_found", "query_status": "unavailable"}}
        result = recheck(report, lambda doi: states[doi])
        self.assertEqual(result["summary"]["dois_checked"], 2)
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertTrue(result["items"][0]["changed"])
        self.assertFalse(result["items"][1]["changed"])
        self.assertEqual(report["items"][0]["editorial"]["editorial_status"], "no_notice_found")


# ------------------------------------------------------------- M25
class NeonDigestTest(unittest.TestCase):
    def test_digest_is_restricted(self):
        matrix = {"claims": [{"claim_id": f"c_{i:03d}", "text": "x" * 900, "audit_state": "sem_evidencia_no_corpus",
                              "evidence": [{"source_name": "S", "pages": [1, 1], "excerpt": "y" * 900}] * 5}
                             for i in range(40)]}
        digest = evidence_digest(matrix)
        self.assertEqual(len(digest), 25)
        self.assertEqual(len(digest[0]["trechos"]), 2)
        self.assertLessEqual(len(digest[0]["trechos"][0]["trecho"]), 240)
        prompt = build_review_prompt("papel", "ideia", "log", digest)
        self.assertIn("MATRIZ DE EVIDÊNCIAS", prompt)
        self.assertNotIn("MATRIZ DE EVIDÊNCIAS", build_review_prompt("papel", "ideia", "log"))


# ------------------------------------------------------------- M13
class UploadGuardTest(unittest.TestCase):
    def test_pdf_javascript_plain_obfuscated_and_compressed(self):
        self.assertEqual(upload_guard.inspect(b"%PDF-1.7\n1 0 obj<</S/JavaScript>>", ".pdf")["verdict"], "quarantine")
        self.assertEqual(upload_guard.inspect(b"%PDF-1.7\n1 0 obj<</S/J#61vaScript>>", ".pdf")["verdict"], "quarantine")
        hidden = zlib.compress(b"<</Type/Action/S/Launch/F(cmd.exe)>>")
        pdf = b"%PDF-1.7\n2 0 obj<</Type/ObjStm/Filter/FlateDecode>>stream\n" + hidden + b"\nendstream"
        result = upload_guard.inspect(pdf, ".pdf")
        self.assertEqual(result["verdict"], "quarantine")
        self.assertIn("pdf_launch", [f["code"] for f in result["findings"]])

    def test_clean_pdf_keeps_info_findings(self):
        result = upload_guard.inspect(b"%PDF-1.7\n1 0 obj<</Type/Catalog/OpenAction 3 0 R>>\n<</URI(https://x)>>", ".pdf")
        self.assertEqual(result["verdict"], "clean")
        self.assertTrue(all(f["severity"] == "info" for f in result["findings"]))

    def test_docx_macro_dde_and_external_template(self):
        self.assertEqual(upload_guard.inspect(make_docx({"word/vbaProject.bin": "x"}), ".docx")["verdict"], "quarantine")
        rels = ('<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/attachedTemplate" Target="http://evil.example/t.dotm" TargetMode="External"/></Relationships>')
        self.assertEqual(upload_guard.inspect(make_docx({"word/_rels/settings.xml.rels": rels}), ".docx")["verdict"], "quarantine")
        field = '<w:instrText> DDEAUTO c:\\\\windows\\\\cmd.exe "/c calc" </w:instrText>'
        self.assertEqual(upload_guard.inspect(make_docx({"word/footer1.xml": field}), ".docx")["verdict"], "quarantine")
        link = ('<Relationships><Relationship Id="r2" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/hyperlink" Target="https://scielo.br" TargetMode="External"/></Relationships>')
        self.assertEqual(upload_guard.inspect(make_docx({"word/_rels/document.xml.rels": link}), ".docx")["verdict"], "clean")

    def test_text_with_null_bytes(self):
        self.assertEqual(upload_guard.inspect(b"@article{a,\x00}", ".bib")["verdict"], "quarantine")
        self.assertEqual(upload_guard.inspect("@article{a, title={Educação}}".encode(), ".bib")["verdict"], "clean")

    def test_quarantined_upload_stays_outside_library(self):
        db, bucket = DB(), Bucket()
        with self.assertRaises(HTTPException) as ctx:
            library.save_library_item(db, bucket, "u1", "x.pdf", ".pdf", b"%PDF-1.7 /JavaScript", "Geral", "")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("quarentena", ctx.exception.detail)
        stored = next(v for (name, _), v in db.store.items() if name == "library_items")
        self.assertEqual(stored["status"], "quarantined")
        self.assertTrue(stored["object_path"].startswith("quarantine/u1/"))
        self.assertFalse(any(k.startswith("library/") for k in bucket.objects))
        listing = endpoint(library.make_library_router(db, bucket, lambda: None), "/items", "GET")(user={"uid": "u1"})
        self.assertEqual(listing["items"], [])
        self.assertEqual(len(listing["quarantined"]), 1)


# ------------------------------------------------------------- M27
BIB = r"""@article{silva2020,
  author = {Silva, Jo{\~a}o and Souza, Maria and Lima, Ana and Costa, Rui},
  title = {Aprendizagem {Ativa} no ensino},
  journal = {Revista Brasileira de Inform{\'a}tica na Educa{\c c}{\~a}o},
  volume = {28}, number = {2}, pages = {10--20}, year = {2020},
  doi = {https://doi.org/10.5753/rbie.2020.28.0.10}
}
@book{freire1996, author={Paulo Freire}, title={Pedagogia da autonomia}, publisher={Paz e Terra},
  address={S{\~a}o Paulo}, year=1996, edition={25}}
@mastersthesis{cruz2027, author={Cruz, Marcelo}, title={Agentes de IA na escrita acadêmica},
  school={IFRS}, address={Porto Alegre}, year={2027}}
"""


class CslExportTest(unittest.TestCase):
    def test_csl_json_mapping(self):
        items = {i["id"]: i for i in csl_export.bibtex_to_csl(BIB)}
        article = items["silva2020"]
        self.assertEqual(article["type"], "article-journal")
        self.assertEqual(article["author"][0], {"family": "Silva", "given": "João"})
        self.assertEqual(article["container-title"], "Revista Brasileira de Informática na Educação")
        self.assertEqual(article["DOI"], "10.5753/rbie.2020.28.0.10")
        self.assertEqual(article["issued"], {"date-parts": [[2020]]})
        self.assertEqual(items["freire1996"]["author"][0], {"family": "Freire", "given": "Paulo"})
        self.assertEqual(items["cruz2027"]["genre"], "Dissertação (Mestrado)")

    def test_abnt_snapshot(self):
        text = csl_export.abnt_list(csl_export.bibtex_to_csl(BIB))
        lines = [line for line in text.splitlines() if line and not line.startswith(("#", "Gerado"))]
        self.assertEqual(lines, [
            "CRUZ, Marcelo. **Agentes de IA na escrita acadêmica**. 2027. Dissertação (Mestrado) – IFRS, Porto Alegre, 2027.",
            "FREIRE, Paulo. **Pedagogia da autonomia**. 25. ed. São Paulo: Paz e Terra, 1996.",
            "SILVA, João et al. Aprendizagem Ativa no ensino. **Revista Brasileira de Informática na Educação**, "
            "v. 28, n. 2, p. 10-20, 2020. DOI: https://doi.org/10.5753/rbie.2020.28.0.10.",
        ])


# ------------------------------------------------------------- M02, M08, M07, M15 (rotas)
JOB = "a" * 32
CHUNK = "aaaaaaaaaaaa-0003-12345678"


def research_setup(status="completed", files=("references", "evidence_csv", "bibtex")):
    db, bucket = DB(), Bucket()
    record = {"id": JOB, "owner_uid": "u1", "status": status, "files": list(files),
              "sources": [{"id": "s" * 32, "format": "pdf", "name": "Fonte.pdf",
                           "object_path": f"library/u1/{'s' * 32}/original.pdf"}]}
    db.store[("research_jobs", JOB)] = record
    started = []

    def get_research(job_id, user):
        snap = db.collection("research_jobs").document(job_id).get()
        if not snap.exists or snap.to_dict()["owner_uid"] != user["uid"]:
            raise HTTPException(404, "Pesquisa não encontrada")
        return snap.to_dict()

    router = research_tools.make_research_tools_router(db, bucket, lambda: None, get_research,
                                                       lambda *a: started.append(a))
    return db, bucket, router, started


class ResearchToolsTest(unittest.TestCase):
    def test_cancel_only_active(self):
        db, _, router, _ = research_setup(status="running")
        result = endpoint(router, "/cancel")(job_id=JOB, user={"uid": "u1"})
        self.assertTrue(result["cancel_requested"])
        self.assertTrue(db.store[("research_jobs", JOB)]["cancel_requested"])
        db2, _, router2, _ = research_setup(status="completed")
        with self.assertRaises(HTTPException) as ctx:
            endpoint(router2, "/cancel")(job_id=JOB, user={"uid": "u1"})
        self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            endpoint(router, "/cancel")(job_id=JOB, user={"uid": "intruso"})

    def test_editorial_recheck_starts_worker_once(self):
        db, _, router, started = research_setup()
        endpoint(router, "/editorial-recheck")(job_id=JOB, user={"uid": "u1"})
        self.assertEqual(started, [(JOB, "u1", "editorial_recheck")])
        self.assertEqual(db.store[("research_jobs", JOB)]["editorial_recheck"]["status"], "queued")
        with self.assertRaises(HTTPException):  # já em andamento
            endpoint(router, "/editorial-recheck")(job_id=JOB, user={"uid": "u1"})

    def test_reviewed_csv_adds_latest_decision(self):
        db, bucket, router, _ = research_setup()
        bucket.objects[f"research/u1/{JOB}/output/evidence_matrix.csv"] = (
            "\ufeffclaim_id,afirmacao\nc_001,Algo\nc_002,Outra\n").encode("utf-8")
        db.store[("research_reviews", "r1")] = {"job_id": JOB, "owner_uid": "u1", "target_type": "claim",
                                                 "target_id": "c_001", "decision": "apoia", "note": "ok", "at": "1"}
        db.store[("research_reviews", "r2")] = {"job_id": JOB, "owner_uid": "u1", "target_type": "claim",
                                                 "target_id": "c_001", "decision": "contradiz", "note": "", "at": "2"}
        response = endpoint(router, "/export/{kind}")(job_id=JOB, kind="evidence_reviewed_csv", user={"uid": "u1"})
        text = response.body.decode("utf-8-sig")
        self.assertIn("claim_id,afirmacao,revisao_humana,nota_da_revisao,revisado_em", text)
        self.assertIn("c_001,Algo,contradiz,,2", text)
        self.assertIn("c_002,Outra,,,", text)

    def test_abnt_and_csl_exports(self):
        _, bucket, router, _ = research_setup()
        bucket.objects[f"research/u1/{JOB}/output/references.bib"] = BIB.encode()
        export = endpoint(router, "/export/{kind}")
        csl = json.loads(export(job_id=JOB, kind="csl_json", user={"uid": "u1"}).body)
        self.assertEqual(len(csl), 3)
        abnt = export(job_id=JOB, kind="abnt", user={"uid": "u1"}).body.decode()
        self.assertIn("FREIRE, Paulo", abnt)

    def test_find_chunk_in_quotes_and_matrix(self):
        report = {"quotes": {"quotes": [{"chunk_id": "q1"}], "pointers": [{"chunk_id": "p1"}]},
                  "matrix": {"claims": [{"evidence": [{"chunk_id": CHUNK, "locations": []}]}]}}
        self.assertEqual(research_tools.find_chunk(report, "p1"), {"chunk_id": "p1"})
        self.assertEqual(research_tools.find_chunk(report, CHUNK)["chunk_id"], CHUNK)
        self.assertIsNone(research_tools.find_chunk(report, "nada"))

    def test_evidence_view_rejects_foreign_or_unknown_chunk(self):
        _, bucket, router, _ = research_setup()
        view = endpoint(router, "/evidence-view/{chunk_id}")
        with self.assertRaises(HTTPException):
            view(job_id=JOB, chunk_id="../../x", page=None, user={"uid": "u1"})
        bucket.objects[f"research/u1/{JOB}/output/evidence_report.json"] = json.dumps(
            {"matrix": {"claims": [{"evidence": [{"chunk_id": CHUNK, "source_id": "outra", "locations": []}]}]}}).encode()
        with self.assertRaises(HTTPException) as ctx:
            view(job_id=JOB, chunk_id=CHUNK, page=None, user={"uid": "u1"})
        self.assertEqual(ctx.exception.status_code, 404)

    @unittest.skipUnless(HAS_PYMUPDF, "PyMuPDF não instalado (roda no CI)")
    def test_evidence_view_renders_highlight(self):
        from pdf_render import fitz
        doc = fitz.open()
        for _ in range(3):
            doc.new_page()
        data = doc.tobytes()
        doc.close()
        db, bucket, router, _ = research_setup()
        source = db.store[("research_jobs", JOB)]["sources"][0]
        bucket.objects[source["object_path"]] = data
        locations = [{"page": 2, "bbox": [0.1, 0.1, 0.5, 0.2]}, {"page": 3, "bbox": [0.1, 0.1, 0.5, 0.2]}]
        bucket.objects[f"research/u1/{JOB}/output/evidence_report.json"] = json.dumps(
            {"matrix": {"claims": [{"evidence": [{"chunk_id": CHUNK, "source_id": source["id"],
                                                  "locations": locations}]}]}}).encode()
        response = endpoint(router, "/evidence-view/{chunk_id}")(job_id=JOB, chunk_id=CHUNK, page=3, user={"uid": "u1"})
        self.assertTrue(response.body.startswith(b"\x89PNG"))
        # FastAPI real expõe .headers; o stub local guarda os argumentos em .kwargs.
        headers = response.headers if hasattr(response, "headers") else response.kwargs["headers"]
        self.assertEqual(headers["X-Scriptorium-Page"], "3")
        self.assertEqual(headers["X-Scriptorium-Pages"], "2,3")


# ------------------------------------------------------------- M03, M21
def derived_payload(sha, item_id):
    return {"document": {"parser_version": "pymupdf-structured-1", "pages_total": 4},
            "chunks": [{"chunk_id": f"{item_id[:12]}-0000-aaaaaaaa", "text": "A sala de aula invertida amplia o engajamento.",
                        "heading_path": ["Introdução"], "pages": [1, 1], "char_count": 45,
                        "chunk_policy": "section-paragraph-1"},
                       {"chunk_id": f"{item_id[:12]}-0001-bbbbbbbb", "text": "Avaliação formativa com rubricas.",
                        "heading_path": ["Métodos"], "pages": [2, 2], "char_count": 33,
                        "chunk_policy": "section-paragraph-1"}]}


class LibraryIndexTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket = DB(), Bucket()
        self.item = {"id": "c" * 32, "owner_uid": "u1", "status": "active", "name": "Bergmann.pdf",
                     "format": "pdf", "sha256": "f" * 64}
        self.db.store[("library_items", self.item["id"])] = self.item
        base = "library/u1/derived/pymupdf-structured-1/section-paragraph-1/"
        self.bucket.objects[base + "f" * 64 + ".json"] = json.dumps(derived_payload("f" * 64, self.item["id"])).encode()
        self.bucket.objects["library/u1/derived/emb-gemini-768/x-y/" + "f" * 64 + ".json"] = b"{}"
        self.router = library_index.make_library_index_router(self.db, self.bucket, lambda: None)

    def test_search_builds_persistent_index_then_reuses_it(self):
        search = endpoint(self.router, "/search")
        first = search(q="engajamento invertida", user={"uid": "u1"})
        self.assertTrue(first["index_rebuilt"])
        self.assertEqual(first["results"][0]["name"], "Bergmann.pdf")
        self.assertIn("[engajamento]", first["results"][0]["snippet"])
        self.assertIn("library/u1/index/fts-1.sqlite", self.bucket.objects)
        second = search(q="rubricas", user={"uid": "u1"})
        self.assertFalse(second["index_rebuilt"])
        self.assertEqual(second["results"][0]["pages"], "2-2")
        self.assertEqual(search(q="engajamento", user={"uid": "outra"})["results"], [])

    def test_fts_query_is_sanitized(self):
        self.assertEqual(library_index.fts_query('a" OR 1=1 -- engajamento*'), '"engajamento"')
        self.assertEqual(library_index.fts_query('sala NEAR(aula) "x'), '"sala" OR "NEAR" OR "aula"')
        with self.assertRaises(HTTPException):
            library_index.fts_query("!!")

    def test_reading_card(self):
        card = endpoint(self.router, "/card")(item_id=self.item["id"], user={"uid": "u1"})
        self.assertEqual(card["chunks"], 2)
        self.assertEqual(card["structure"], ["Introdução", "Métodos"])
        with self.assertRaises(HTTPException):
            endpoint(self.router, "/card")(item_id=self.item["id"], user={"uid": "outra"})


# ------------------------------------------------------------- M26
KEY = "abcdefghijKLMNOP1234"


class ZoteroV2Transport:
    def __init__(self, version=50, since_items=0):
        self.version, self.since_items, self.calls = version, since_items, []

    def __call__(self, path, key):
        self.calls.append((path, key))
        if path.startswith("https://files.example/"):
            return (200, {}, b"%PDF-1.7 limpo") if "ok" in path else (200, {}, b"%PDF-1.7 /JavaScript")
        if path.startswith("/keys/"):
            return 200, {}, json.dumps({"userID": 4321}).encode()
        if "/deleted?" in path:
            return 200, {}, json.dumps({"items": ["AAAA1111"]}).encode()
        if "format=keys" in path:
            return 200, {}, b"PARENT01\nPARENT02\n"
        if path.endswith("/children"):
            parent = path.split("/items/")[1].split("/")[0]
            return 200, {}, json.dumps([{"key": "ATT" + parent[-5:], "data": {
                "itemType": "attachment", "contentType": "application/pdf", "linkMode": "imported_file",
                "filename": f"{parent}.pdf"}}]).encode()
        if path.endswith("/file"):
            target = "ok" if "ATTENT01" in path else "bad"
            return 302, {"Location": f"https://files.example/{target}"}, b""
        headers = {"Total-Results": "2", "Last-Modified-Version": str(self.version)}
        if "since=" in path:
            n = self.since_items
            return 200, {"Total-Results": str(n), "Last-Modified-Version": str(self.version)}, \
                "\n".join(f"@article{{n{i}, title={{N{i}}}}}" for i in range(n)).encode()
        return 200, headers, b"@article{a, title={A}}\n@article{b, title={B}}"


class ZoteroIncrementalTest(unittest.TestCase):
    def test_incremental_import_uses_saved_version_and_never_stores_key(self):
        db, bucket = DB(), Bucket()
        transport = ZoteroV2Transport(version=50)
        imp = endpoint(zi.make_zotero_router(db, bucket, lambda: None, transport=transport), "/import")
        first = imp(payload=zi.ZoteroImport(api_key=KEY, collection_key="ABCD2345"), user={"uid": "u1"})
        self.assertEqual((first["items_imported"], first["library_version"]), (2, 50))
        transport.version, transport.since_items = 57, 1
        second = imp(payload=zi.ZoteroImport(api_key=KEY, collection_key="ABCD2345", incremental=True),
                     user={"uid": "u1"})
        self.assertEqual((second["items_imported"], second["since_version"], second["deleted_in_zotero"]), (1, 50, 1))
        self.assertTrue(any("since=50" in p for p, _ in transport.calls))
        transport.since_items = 0
        third = imp(payload=zi.ZoteroImport(api_key=KEY, collection_key="ABCD2345", incremental=True),
                    user={"uid": "u1"})
        self.assertTrue(third["up_to_date"])
        self.assertNotIn(KEY, json.dumps(list(db.store.values()), default=str))

    def test_attachments_need_consent_and_go_through_guard(self):
        db, bucket = DB(), Bucket()
        transport = ZoteroV2Transport()
        imp = endpoint(zi.make_zotero_router(db, bucket, lambda: None, transport=transport), "/import")
        imp(payload=zi.ZoteroImport(api_key=KEY), user={"uid": "u1"})
        self.assertFalse(any(p.endswith("/file") for p, _ in transport.calls))
        result = imp(payload=zi.ZoteroImport(api_key=KEY, attachments_consent=True), user={"uid": "u1"})
        self.assertEqual(result["attachments"], {"imported": 1, "quarantined": 1, "skipped": 0})
        # O arquivo assinado é baixado SEM a chave do Zotero.
        downloads = [(p, k) for p, k in transport.calls if p.startswith("https://files.example/")]
        self.assertTrue(downloads and all(k is None for _, k in downloads))
        statuses = sorted(v["status"] for (name, _), v in db.store.items() if name == "library_items")
        self.assertEqual(statuses.count("quarantined"), 1)


if __name__ == "__main__":
    unittest.main()
