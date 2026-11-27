"""Compila um exemplo de cada norma de formatos/ com o mesmo caminho do PDF real.

Roda no build da imagem do worker (worker/Dockerfile): se uma norma não gerar
PDF sem erro e com as citações resolvidas, o build para e o deploy não sobe.

  python format_smoke.py               # todas as normas, pt-BR e en
  python format_smoke.py apa7 --en     # só uma norma, só em inglês
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import mcp_jobs
from mcp_jobs import formatos

BIB = """@article{silva2020,
  author = {Silva, João Antônio and Souza, Maria},
  title = {Aprendizagem ativa e sala de aula invertida},
  journal = {Revista Brasileira de Educação},
  volume = {25}, number = {3}, pages = {10--25}, year = {2020},
  doi = {10.1590/exemplo.2020.001}
}
@book{lima2019,
  author = {Lima, Ana and Costa, Bruno and Dias, Carla},
  title = {Metodologias ativas na educação}, publisher = {Penso}, year = {2019}
}
"""


def sample_body(fmt: dict) -> str:
    cit = fmt["citacao"]
    paren = cit["parentetica"].replace("chave", "silva2020")
    narr = cit["narrativa"].replace("chave", "lima2019")
    env = fmt["estrutura"]["resumo"]
    sections = "\n".join(f"\\section{{Seção {n}}}\nTexto da seção {n}, conforme {narr} e {paren}.\n"
                         for n in range(1, 4))
    return f"\\begin{{{env}}}\nResumo de teste com acentuação: ação, ênfase.\n\\end{{{env}}}\n{sections}"


def check(formato_id: str, language: str) -> list[str]:
    fmt = formatos.obter(formato_id)
    project = {"template": formato_id, "language": language, "title": "Teste de formatação & norma", "tipo": fmt["tipos"][0]}
    tex = mcp_jobs.assemble(project, sample_body(fmt), today=datetime(2026, 1, 15, tzinfo=timezone.utc))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "references.bib").write_text(BIB, encoding="utf-8")
        pdf, report = mcp_jobs.compile_tex(work, tex, name="smoke")
    problems = []
    if not pdf:
        problems.append(f"{formato_id} ({language}): sem PDF ({report.get('motivo')})")
    if report.get("erros_latex"):
        problems.append(f"{formato_id} ({language}): erros LaTeX {report.get('erros_detalhe')}")
    if report.get("citacoes_indefinidas"):
        problems.append(f"{formato_id} ({language}): {report['citacoes_indefinidas']} citação(ões) indefinida(s)")
    if problems:
        problems.append((report.get("log_final") or "")[-1500:])
    return problems


def main(argv: list[str]) -> int:
    languages = ["en"] if "--en" in argv else ["pt-BR"] if "--pt" in argv else ["pt-BR", "en"]
    wanted = [a for a in argv if not a.startswith("--")] or list(formatos.ids())
    failures = []
    for fid in wanted:
        for language in languages:
            found = check(fid, language)
            print(("FALHOU " if found else "ok ") + f"{fid} ({language})", flush=True)
            failures += found
    for line in failures:
        print(line, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
