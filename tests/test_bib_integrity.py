"""Integridade da bibliografia e contexto ampliado (achados do confronto de 25/11/2026)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

import bib_integrity as bi  # noqa: E402
import context_limits  # noqa: E402

TEX = r"""\documentclass{abntex2}
\begin{filecontents*}{references.bib}
@article{Pischetola2018,
  author = {Pischetola, Magda and Heinsfeld, Adriana S.},
  title = {O mito dos nativos digitais},
  journal = {Revista de Educação},
  year = {2018}
}
@article{Brasil2021,
  author = {Brasil, L. and Gabry, I.},
  title = {Competências do século XXI e metodologias ativas},
  journal = {Revista X},
  year = {2021}
}
\end{filecontents*}
\begin{filecontents}{nota.txt}
nao e bibliografia
\end{filecontents}
\begin{document}
Texto \citet{Pischetola2018} e \cite{Brasil2021, Ptzsch2019} e \citep{Fantasma2020}.
\nocite{Kitchenham2007}
\end{document}
"""
BIB = """@article{Ptzsch2019,
  title = {Critical Digital Literacy},
  author = {Holger Pötzsch},
  journal = {tripleC},
  year = {2019}
}
@manual{Kitchenham2007,
  author = {Kitchenham, Barbara},
  title = {Guidelines for performing Systematic Literature Reviews in Software Engineering},
  year = {2007}
}
"""
WORK = {"title": "“Eles já nascem sabendo!”: desmistificando o conceito de nativos digitais no contexto educacional",
        "publication_year": 2018, "type": "article", "doi": "https://doi.org/10.22456/1679-1916.85929",
        "authorships": [{"author": {"display_name": "Magda Pischetola"}},
                        {"author": {"display_name": "Bruna Damiana Heinsfeld"}}],
        "primary_location": {"source": {"display_name": "RENOTE"}},
        "biblio": {"volume": "16", "issue": "1", "first_page": "1", "last_page": "10"}}


class InlineBibTest(unittest.TestCase):
    def test_extracts_only_bib_blocks(self):
        bib, tex, names = bi.extract_inline(TEX)
        self.assertEqual(names, ["references.bib"])
        self.assertIn("Pischetola2018", bib)
        self.assertNotIn("filecontents*}{references.bib}", tex)
        self.assertIn("nota.txt", tex)  # outros arquivos ficam

    def test_repair_merges_corrects_and_flags(self):
        official = bi.library_entries(
            [{"id": "s1", "name": "Pischetola 2018.pdf", "origin": {"doi": "10.22456/1679-1916.85929"}}],
            lambda url: WORK)
        self.assertEqual(official[0]["key"], "pischetola2018nascem")
        out = bi.repair(TEX, BIB, official)
        keys = [e["key"] for e in out["entries"]]
        self.assertEqual(keys, ["Ptzsch2019", "Kitchenham2007", "Pischetola2018", "Brasil2021"])
        fixed = next(e for e in out["entries"] if e["key"] == "Pischetola2018")
        self.assertEqual(fixed["fields"]["journal"], "RENOTE")  # chave mantida, dados oficiais
        self.assertIn("Bruna Damiana", fixed["fields"]["author"])
        codes = {(f["code"], f.get("key")) for f in out["report"]["findings"]}
        self.assertIn(("corrigida_pela_fonte_anexada", "Pischetola2018"), codes)
        self.assertIn(("valor_de_enchimento", "Brasil2021"), codes)
        missing = next(f for f in out["report"]["findings"] if f["code"] == "citacao_sem_referencia")
        self.assertEqual(missing["keys"], ["Fantasma2020"])
        self.assertEqual(out["report"]["inline_entries_added"], ["Pischetola2018", "Brasil2021"])
        self.assertIn("@article{Brasil2021", out["bib"])
        self.assertNotIn("filecontents", out["tex"].split("% Bibliografia movida")[0][-40:])


class OfficialEntriesTest(unittest.TestCase):
    def test_title_search_accepts_only_near_identical(self):
        def get_json(url):
            return {"results": [{"title": "Outro trabalho qualquer sobre tecnologia", "publication_year": 2017},
                                {"title": "Ambientes virtuais de aprendizagem: limites e possibilidades para utilização no ensino médio",
                                 "publication_year": 2021, "type": "article",
                                 "authorships": [{"author": {"display_name": "Claudinete de Jesus da Silva"}}],
                                 "primary_location": {"source": {"display_name": "RECIMA21"}}}]}
        meta = {"s2": {"pdf_title": "AMBIENTES VIRTUAIS DE APRENDIZAGEM: LIMITES E POSSIBILIDADES PARA UTILIZAÇÃO NO ENSINO MÉDIO"},
                "s3": {"pdf_title": "Texto sem correspondência nenhuma no OpenAlex"}}
        entries = bi.library_entries([{"id": "s2", "name": "452.pdf"}, {"id": "s3", "name": "x.pdf"}],
                                     get_json, meta)
        self.assertEqual(entries[0]["how"], "titulo_do_pdf")
        self.assertEqual(entries[0]["fields"]["journal"], "RECIMA21")
        self.assertEqual(entries[1]["how"], "arquivo")
        self.assertIn("metadados a conferir", entries[1]["fields"]["note"])
        block = bi.bibtex_block(entries)
        self.assertIn("use EXATAMENTE a chave", block)

    def test_text_confirmation_rejects_authorless_reprint(self):
        """Achado do teste MCP: Prensky 2001 saía como 2012, sem autor."""
        text = ("Digital Natives, Digital Immigrants\nBy Marc Prensky\nFrom On the Horizon (MCB University "
                "Press, Vol. 9 No. 5, October 2001)\nIt is amazing to me how in all the hoopla...")
        results = {"results": [
            {"title": "Digital Natives, Digital Immigrants", "publication_year": 2012, "type": "book-chapter",
             "authorships": []},
            {"title": "Digital Natives, Digital Immigrants Part 1", "publication_year": 2001, "type": "article",
             "authorships": [{"author": {"display_name": "Marc Prensky"}}],
             "primary_location": {"source": {"display_name": "On the Horizon"}}}]}
        entries = bi.library_entries([{"id": "p", "name": "Prensky2001-DigitalNativesDigitalImmigrants.pdf"}],
                                     lambda url: results, {}, {"p": text})
        self.assertEqual(entries[0]["how"], "texto_do_pdf")
        self.assertEqual(entries[0]["fields"]["year"], "2001")
        self.assertEqual(entries[0]["key"], "prensky2001digital")

    def test_doi_printed_in_text_needs_confirmation(self):
        own = {"title": "Ambientes virtuais de aprendizagem no ensino médio", "publication_year": 2021,
               "type": "article", "authorships": [{"author": {"display_name": "Claudinete de Jesus da Silva"}}]}
        cited = {"title": "Outro artigo citado", "publication_year": 2015, "type": "article",
                 "authorships": [{"author": {"display_name": "Fulano Beltrano"}}]}
        text = ("AMBIENTES VIRTUAIS DE APRENDIZAGEM NO ENSINO MÉDIO\nClaudinete de Jesus da Silva\n"
                "DOI: 10.47820/recima21.v2i1.452\nVer também doi.org/10.9999/citado.1")
        def get_json(url):
            if url.endswith("10.47820/recima21.v2i1.452"):
                return own
            if url.endswith("10.9999/citado.1"):
                return cited
            return {"results": []}
        entries = bi.library_entries([{"id": "r", "name": "452.pdf"}], get_json, {}, {"r": text})
        self.assertEqual(entries[0]["how"], "doi_no_texto")
        self.assertEqual(entries[0]["fields"]["year"], "2021")
        # Um DOI citado no texto não vira a referência da fonte.
        entries = bi.library_entries([{"id": "r", "name": "452.pdf"}],
                                     lambda url: cited if "citado" in url else {"results": []}, {},
                                     {"r": "Texto qualquer\ndoi.org/10.9999/citado.1"})
        self.assertEqual(entries[0]["how"], "arquivo")

    def test_fallback_skips_fake_authors(self):
        entries = bi.library_entries([{"id": "u", "name": "6.pdf"}], lambda url: {"results": []},
                                     {"u": {"author": "user", "pdf_title": ""}},
                                     {"u": "Letramento digital e o DigComp na formação docente\nThais Cilli"})
        self.assertNotIn("author", entries[0]["fields"])
        self.assertEqual(entries[0]["fields"]["title"], "6")  # nada de linha do texto como título

    def test_generic_institutional_record_is_not_confirmed(self):
        work = {"title": "Department of Computer Science", "publication_year": 2013, "type": "article",
                "authorships": [{"author": {"display_name": "Colorado State University. Department of Computer Science"}}]}
        text = "Procedures for Performing Systematic Reviews\nBarbara Kitchenham\nDepartment of Computer Science"
        entries = bi.library_entries([{"id": "k", "name": "525444systematicreviewsguide.pdf"}],
                                     lambda url: {"results": [work]}, {}, {"k": text})
        self.assertEqual(entries[0]["how"], "arquivo")

    def test_network_failure_never_invents(self):
        def boom(url):
            raise TimeoutError()
        entries = bi.library_entries([{"id": "s", "name": "Lasalvia tese.pdf", "origin": {"doi": "10.1/x"}}], boom)
        self.assertEqual(entries[0]["type"], "misc")
        self.assertNotIn("author", entries[0]["fields"])

    def test_recompile_without_latex_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf, note = bi.recompile(Path(tmp), "\\documentclass{article}\\begin{document}x\\end{document}", timeout=20)
        self.assertTrue(pdf is None or pdf.name.endswith(".pdf"))
        if pdf is None:
            self.assertTrue(note)


class ContextLimitsTest(unittest.TestCase):
    def test_api_and_worker_tables_match(self):
        text = (ROOT / "api" / "library.py").read_text(encoding="utf-8")
        for name, limits in context_limits.CONTEXT_LIMITS.items():
            self.assertIn(f'"{name}": {{"max_sources": {limits["max_sources"]}, '
                          f'"per_source_chars": {limits["per_source_chars"]:_}, '
                          f'"total_chars": {limits["total_chars"]:_}}}', text)
        self.assertEqual(context_limits.limits_for({"context_size": "ampliado"})["max_sources"], 20)
        self.assertEqual(context_limits.limits_for({})["max_sources"], 8)

    def test_v1_context_respects_limits(self):
        from source_materials import compose_library_context
        sources = [{"id": f"{i:032x}", "name": f"f{i}.txt", "format": "txt", "object_path": f"p{i}"}
                   for i in range(12)]
        text = "palavra " * 3000
        _, manifest = compose_library_context(sources, lambda path: text.encode(), max_sources=10,
                                              per_file=5000, total=60_000)
        self.assertEqual(len(manifest), 10)
        self.assertLessEqual(sum(m.get("extracted_characters", 0) for m in manifest), 60_000)


if __name__ == "__main__":
    unittest.main()
