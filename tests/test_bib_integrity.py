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
        self.assertEqual(official[0]["key"], "fonte_pischetola2018")
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
