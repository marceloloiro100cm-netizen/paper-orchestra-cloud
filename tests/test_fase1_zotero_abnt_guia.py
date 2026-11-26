"""Testes da Fase 1: Núcleo Zotero + ABNT + Fichamento + /citar + Declaração IN 16/2026."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import abnt_refs
from library import make_library_router


class _FakeSnap:
    def __init__(self, doc_id: str, data: dict | None):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _FakeDoc:
    def __init__(self, store: dict, doc_id: str):
        self._store = store
        self._id = doc_id

    def get(self):
        return _FakeSnap(self._id, self._store.get(self._id))

    def create(self, data: dict):
        if self._id in self._store:
            raise RuntimeError("already exists")
        self._store[self._id] = dict(data)

    def update(self, patch: dict):
        if self._id not in self._store:
            raise KeyError(self._id)
        self._store[self._id].update(patch)

    def delete(self):
        self._store.pop(self._id, None)


class _FakeQuery:
    def __init__(self, store: dict, filters: list[tuple[str, str, object]]):
        self._store = store
        self._filters = filters
        self._limit = None

    def where(self, field, op, val):
        return _FakeQuery(self._store, [*self._filters, (field, op, val)])

    def limit(self, n):
        q = _FakeQuery(self._store, list(self._filters))
        q._limit = n
        return q

    def stream(self):
        out = []
        for doc_id, data in list(self._store.items()):
            ok = True
            for field, op, val in self._filters:
                if op == "==" and data.get(field) != val:
                    ok = False
                    break
            if ok:
                out.append(_FakeSnap(doc_id, data))
                if self._limit and len(out) >= self._limit:
                    break
        return out


class _FakeCollection:
    def __init__(self, store: dict):
        self._store = store

    def document(self, doc_id: str):
        return _FakeDoc(self._store, doc_id)

    def where(self, field, op, val):
        return _FakeQuery(self._store, [(field, op, val)])


class _FakeDB:
    def __init__(self):
        self._cols: dict[str, dict] = {}

    def collection(self, name: str):
        return _FakeCollection(self._cols.setdefault(name, {}))


class _FakeBlob:
    def __init__(self, store: dict, name: str):
        self._store = store
        self.name = name

    def exists(self):
        return self.name in self._store

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        self._store[self.name] = data if isinstance(data, bytes) else str(data).encode("utf-8")

    def download_as_bytes(self):
        return self._store[self.name]

    def delete(self):
        self._store.pop(self.name, None)


class _FakeBucket:
    def __init__(self):
        self._store: dict[str, bytes] = {}

    def blob(self, name: str):
        return _FakeBlob(self._store, name)

    def list_blobs(self, prefix=""):
        return [_FakeBlob(self._store, k) for k in list(self._store) if k.startswith(prefix)]


class AbntRefsUnitTests(unittest.TestCase):
    def test_abnt_citations_parenthetical_and_narrative(self):
        one = {"type": "book", "key": "freire1996", "fields": {
            "author": "Freire, Paulo", "title": "Pedagogia da autonomia", "year": "1996",
            "publisher": "Paz e Terra", "address": "São Paulo",
        }}
        self.assertEqual(abnt_refs.format_abnt_citation(one), "(FREIRE, 1996)")
        self.assertEqual(abnt_refs.format_abnt_citation(one, narrative=True), "Freire (1996)")
        self.assertEqual(abnt_refs.format_abnt_citation(one, page="p. 47"), "(FREIRE, 1996, p. 47)")
        self.assertEqual(abnt_refs.format_abnt_citation(one, narrative=True, page="47"), "Freire (1996, p. 47)")

        two = {"type": "article", "key": "lea2014", "fields": {
            "author": "Lea, Mary R. and Street, Brian V.", "title": "Letramentos acadêmicos", "year": "2014",
        }}
        self.assertEqual(abnt_refs.format_abnt_citation(two), "(LEA; STREET, 2014)")
        self.assertEqual(abnt_refs.format_abnt_citation(two, narrative=True), "Lea e Street (2014)")

        four = {"type": "article", "key": "fan2025", "fields": {
            "author": "Fan, Yizhou and Tang, L. and Le, H. and Shen, K.",
            "title": "Beware of metacognitive laziness", "year": "2025",
        }}
        self.assertEqual(abnt_refs.format_abnt_citation(four), "(FAN et al., 2025)")
        self.assertEqual(abnt_refs.format_abnt_citation(four, narrative=True), "Fan et al. (2025)")

    def test_ris_parse_and_roundtrip(self):
        ris = "\n".join([
            "TY  - JOUR",
            "AU  - Carlino, Paula",
            "TI  - Alfabetización académica diez años después",
            "JO  - Revista Mexicana de Investigación Educativa",
            "PY  - 2013",
            "VL  - 18",
            "IS  - 57",
            "SP  - 355",
            "EP  - 381",
            "DO  - 10.1234/carlino.2013",
            "ER  -",
        ])
        parsed = abnt_refs.parse_references_text(ris)
        self.assertEqual(len(parsed), 1)
        entry = parsed[0]
        self.assertEqual(entry["type"], "article")
        self.assertEqual(entry["fields"]["year"], "2013")
        self.assertEqual(entry["fields"]["pages"], "355-381")
        exported_ris = abnt_refs.bib_entry_to_ris(entry)
        self.assertIn("TY  - JOUR", exported_ris)
        self.assertIn("SP  - 355", exported_ris)
        self.assertIn("EP  - 381", exported_ris)

    def test_citation_coherence_matches_and_flags_missing(self):
        lib = [
            {"id": "1", "name": "Freire.pdf", "bib_entry": {
                "type": "book", "key": "freire1996",
                "fields": {"author": "Freire, Paulo", "title": "Pedagogia da autonomia", "year": "1996"},
            }},
            {"id": "2", "name": "Bastani.pdf", "bib_entry": {
                "type": "article", "key": "bastani2025",
                "fields": {"author": "Bastani, Hamsa and Bastani, Osbert and Sungu, Alp and Ge, Haosen",
                           "title": "Generative AI without guardrails", "journal": "PNAS", "year": "2025"},
            }},
            {"id": "3", "name": "Carlino.pdf", "bib_entry": {
                "type": "book", "key": "carlino2017",
                "fields": {"author": "Carlino, Paula", "title": "Escrever, ler e aprender", "year": "2017"},
            }},
        ]
        text = "Conforme Freire (1996, p. 47), ensinar exige pesquisa. Além disso (BASTANI et al., 2025) e (AUTORFANTASMA, 2022)."
        res = abnt_refs.check_citation_coherence(text, lib)
        self.assertEqual(res["matched_count"], 2)
        self.assertEqual(len(res["missing_in_library"]), 1)
        self.assertEqual(res["missing_in_library"][0]["surname"], "autorfantasma")
        self.assertEqual(len(res["uncited_in_library"]), 1)
        self.assertEqual(res["uncited_in_library"][0]["id"], "3")
        # Ordem alfabética ABNT: BASTANI antes de FREIRE
        self.assertTrue(res["abnt_references"][0].startswith("BASTANI"))
        self.assertTrue(res["abnt_references"][1].startswith("FREIRE"))


class LibraryFase1ApiTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDB()
        self.bucket = _FakeBucket()
        self.user = {"uid": "u-aluno-1", "email": "aluno@ifrs.edu.br"}

        def fake_fetch(url: str, max_bytes: int, accept: str) -> bytes:
            if "10.1073/pnas.2422633122" in url:
                return json.dumps({
                    "id": "https://openalex.org/W999",
                    "title": "Generative AI without guardrails can harm learning",
                    "publication_year": 2025,
                    "type": "article",
                    "authorships": [
                        {"author": {"display_name": "Hamsa Bastani"}},
                        {"author": {"display_name": "Osbert Bastani"}},
                        {"author": {"display_name": "Alp Sungu"}},
                        {"author": {"display_name": "Haosen Ge"}},
                    ],
                    "primary_location": {"source": {"display_name": "PNAS"}},
                    "biblio": {"volume": "122", "issue": "26", "first_page": "1", "last_page": "10"},
                    "open_access": {"is_oa": False},
                    "locations": [],
                }).encode("utf-8")
            raise ValueError("HTTP 404")

        app = FastAPI()
        app.include_router(make_library_router(self.db, self.bucket, lambda: self.user, fetch=fake_fetch))
        self.client = TestClient(app)

    def test_import_doi_bibtex_ris_with_dedup_and_export(self):
        # 1) Importa DOI fechado (sem PDF aberto!) via OpenAlex
        r1 = self.client.post("/api/library/import-references", json={
            "text": "https://doi.org/10.1073/pnas.2422633122",
            "collection": "Revisão",
            "role": "evidencia",
        })
        self.assertEqual(r1.status_code, 201)
        d1 = r1.json()
        self.assertEqual(d1["counts"]["importado"], 1)
        item = d1["results"][0]["item"]
        self.assertEqual(item["role"], "evidencia")
        self.assertEqual(item["abnt"]["cite_parenthetical"], "(BASTANI et al., 2025)")

        # 2) Repetir mesmo DOI é detectado como duplicata automaticamente
        r_dup = self.client.post("/api/library/import-references", json={
            "text": "10.1073/pnas.2422633122",
        })
        self.assertEqual(r_dup.status_code, 201)
        self.assertEqual(r_dup.json()["counts"]["duplicado"], 1)
        self.assertEqual(r_dup.json()["counts"]["importado"], 0)

        # 3) Importar BibTeX + verificar exportação ABNT, BibTeX e RIS
        r_bib = self.client.post("/api/library/import-references", json={
            "text": "@book{freire1996, author={Freire, Paulo}, title={Pedagogia da autonomia}, year={1996}, publisher={Paz e Terra}, address={São Paulo}}",
            "role": "marco_teorico",
        })
        self.assertEqual(r_bib.status_code, 201)
        self.assertEqual(r_bib.json()["counts"]["importado"], 1)

        for fmt, expected_fragment in (
            ("abnt", "FREIRE, Paulo. Pedagogia da autonomia."),
            ("bib", "@book{freire1996,"),
            ("ris", "TY  - BOOK"),
        ):
            rexp = self.client.get(f"/api/library/export?fmt={fmt}")
            self.assertEqual(rexp.status_code, 200)
            self.assertIn(expected_fragment, rexp.text)

    def test_study_meta_notes_and_citation_coherence_endpoint(self):
        r = self.client.post("/api/library/import-references", json={
            "text": "@book{freire1996, author={Freire, Paulo}, title={Pedagogia da autonomia}, year={1996}, publisher={Paz e Terra}, address={São Paulo}}",
        })
        item_id = r.json()["results"][0]["item"]["id"]

        # Atualiza papel e status de leitura
        rp = self.client.patch(f"/api/library/items/{item_id}/study", json={
            "role": "marco_teorico", "reading_status": "incluido",
        })
        self.assertEqual(rp.status_code, 200)
        self.assertEqual(rp.json()["item"]["role"], "marco_teorico")
        self.assertEqual(rp.json()["item"]["reading_status"], "incluido")

        # Adiciona, edita e remove fichamento por página
        rn = self.client.post(f"/api/library/items/{item_id}/notes", json={
            "page": "47", "quote": "Ensinar não é transferir conhecimento",
            "note": "Fundamenta a crítica à escrita bancária automatizada.",
            "tag": "autonomia", "support_checked": True,
        })
        self.assertEqual(rn.status_code, 201)
        note_id = rn.json()["note"]["id"]
        self.assertEqual(len(rn.json()["study_notes"]), 1)

        rne = self.client.patch(f"/api/library/items/{item_id}/notes/{note_id}", json={"support_checked": False})
        self.assertEqual(rne.status_code, 200)
        self.assertFalse(rne.json()["note"]["support_checked"])

        # Confere coerência bibliográfica via endpoint
        rc = self.client.post("/api/library/check-citations", json={
            "text": "Segundo Freire (1996, p. 47), a autonomia é construída. Ver também (NAOEXISTE, 2020).",
        })
        self.assertEqual(rc.status_code, 200)
        self.assertEqual(rc.json()["matched_count"], 1)
        self.assertEqual(len(rc.json()["missing_in_library"]), 1)

        # Remove nota
        rd = self.client.delete(f"/api/library/items/{item_id}/notes/{note_id}")
        self.assertEqual(rd.status_code, 200)
        self.assertEqual(rd.json()["study_notes"], [])

    def test_frontend_fase1_contracts(self):
        html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
        guia_js = (ROOT / "public" / "guia" / "guia.js").read_text(encoding="utf-8")
        # Zero novas abas no menu principal; tudo integrado nos módulos existentes
        self.assertIn('id="open-export-refs"', html)
        self.assertIn('data-add-tab="refs"', html)
        self.assertIn('id="duplicates-banner"', html)
        self.assertIn("window.ScriptoriumBiblioteca", app_js)
        self.assertIn("openLibraryStudyModal", app_js)
        self.assertIn("openCitePicker", guia_js)
        self.assertIn("/\\/citar$/i", guia_js)
        self.assertIn("sync-abnt-refs", guia_js)
        self.assertIn("buildIn16Declaration", guia_js)
        self.assertIn("quick-ai-decision", guia_js)


if __name__ == "__main__":
    unittest.main()
