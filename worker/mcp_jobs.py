"""Trabalhos do modo sem API (MCP) no worker. Nenhum deles usa modelo de linguagem.

- mcp_prepare: lê as fontes do projeto (documento estruturado + trechos, no
  mesmo cache privado das pesquisas) e monta o BibTeX oficial (DOI/OpenAlex ou
  título do PDF; sem correspondência segura, entrada mínima marcada "a conferir").
- mcp_compile: junta o corpo aceito no quadro com o preâmbulo do modelo e a
  bibliografia oficial e compila com o TeX em modo restrito (sem shell, sem
  leitura fora do diretório), além de gerar o relatório de proveniência
  (qual IA fez cada etapa e com que independência).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import bib_integrity

# Mesma lista do api/mcp_flow.py (tests/test_mcp_jobs.py impede divergência):
# a API já recusa estes comandos; aqui é a segunda barreira antes do TeX.
FORBIDDEN = re.compile(
    r"\\(?:write\d*|immediate|openin|openout|closein|closeout|read|readline|input|include|"
    r"includeonly|InputIfFileExists|usepackage|RequirePackage|documentclass|catcode|special|"
    r"directlua|luaexec|latelua|csname|expandafter|def|edef|gdef|xdef|let|futurelet|newcommand|"
    r"renewcommand|providecommand|DeclareRobustCommand|newenvironment|renewenvironment|"
    r"bibliography|bibliographystyle|addbibresource|includegraphics|verbatiminput|"
    r"lstinputlisting|pdffiledump|pdfximage|pdfobj|scantokens|everyeof|endinput|"
    r"newread|newwrite|loop|jobname|shipout|output|end\s*\{\s*document\s*\}|"
    r"begin\s*\{\s*document\s*\})(?![A-Za-z])")

MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
          "outubro", "novembro", "dezembro"]

ABNT_PREAMBLE = r"""\documentclass[article,12pt,oneside,a4paper,brazil]{abntex2}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[brazil]{babel}
\usepackage{lmodern}
\usepackage{amsmath,amssymb,booktabs,array}
\usepackage{hyperref,url}
\usepackage[alf]{abntex2cite}
\providecommand{\citep}[1]{\cite{#1}}
\providecommand{\citet}[1]{\citeonline{#1}}
\providecommand{\citealp}[1]{\cite{#1}}
\providecommand{\citealt}[1]{\citeonline{#1}}
\providecommand{\citeauthor}[1]{\citeonline{#1}}
\providecommand{\citeyear}[1]{\cite{#1}}
\titulo{%(title)s}
\autor{%(author)s}
\local{Brasil}
\data{%(date)s}
\begin{document}
\selectlanguage{brazil}
\maketitle
"""

SIMPLE_PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[%(babel)s]{babel}
\usepackage{lmodern}
\usepackage{amsmath,amssymb,booktabs,array,url}
\usepackage[hidelinks]{hyperref}
\usepackage[authoryear,round]{natbib}
\providecommand{\citeonline}[1]{\citet{#1}}
\title{%(title)s}
\author{%(author)s}
\date{%(date)s}
\begin{document}
\maketitle
"""


def latex_escape(text: str) -> str:
    table = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
             "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(table.get(c, c) for c in (text or ""))


def run_date(language: str, today: datetime | None = None) -> str:
    today = today or datetime.now(timezone.utc)
    if language == "en":
        return today.strftime("%B %d, %Y").replace(" 0", " ")
    return f"{today.day} de {MONTHS[today.month - 1]} de {today.year}"


LABELS = {
    "pt-BR": {"ident": "Registros identificados", "dup": "Removidos antes da triagem: duplicados",
              "screen": "Registros triados", "title": "Excluídos por título e resumo",
              "sought": "Relatórios buscados para recuperação", "lost": "Relatórios não recuperados",
              "assessed": "Relatórios avaliados para elegibilidade", "excl": "Relatórios excluídos",
              "quality": "Excluídos abaixo da nota de corte de qualidade", "included": "Estudos incluídos na revisão",
              "outside": "Referências teóricas ou metodológicas fora da triagem",
              "caption": "Fluxograma PRISMA 2020 da seleção dos estudos",
              "source": "Fonte: elaborado pelo autor, com as decisões registradas no Scriptorium."},
    "en": {"ident": "Records identified", "dup": "Removed before screening: duplicates",
           "screen": "Records screened", "title": "Excluded by title and abstract",
           "sought": "Reports sought for retrieval", "lost": "Reports not retrieved",
           "assessed": "Reports assessed for eligibility", "excl": "Reports excluded",
           "quality": "Excluded below the quality cut-off", "included": "Studies included in the review",
           "outside": "Theoretical or methodological references outside screening",
           "caption": "PRISMA 2020 flow diagram of study selection",
           "source": "Source: prepared by the author from the decisions recorded in Scriptorium."},
}


def prisma_figure(prisma: dict, language: str = "pt-BR") -> str:
    """Fluxograma PRISMA 2020 em LaTeX simples (caixas e setas, sem TikZ)."""
    t = LABELS.get(language, LABELS["pt-BR"])

    def box(text: str) -> str:
        return r"\fbox{\parbox{0.42\textwidth}{\centering " + text + "}}"

    def n(label: str, value) -> str:
        return label + r"\\(n = " + str(int(value or 0)) + ")"

    rows = []
    if prisma.get("bases"):
        bases = "; ".join(f"{latex_escape(b['nome'])}: {int(b['registros'])}" for b in prisma["bases"])
        rows.append((n(t["ident"], prisma["identificados"]) + r"\\\footnotesize " + bases,
                     n(t["dup"], prisma.get("duplicados"))))
        rows.append((n(t["screen"], prisma.get("triados")), n(t["title"], prisma.get("excluidos_titulo_resumo"))))
        rows.append((n(t["sought"], prisma.get("procurados")), n(t["lost"], prisma.get("nao_recuperados"))))
    reasons = "; ".join(f"{latex_escape(k)}: {v}" for k, v in sorted((prisma.get("motivos") or {}).items()))
    rows.append((n(t["assessed"], prisma.get("avaliados")),
                 n(t["excl"], prisma.get("excluidos_elegibilidade")) + (r"\\\footnotesize " + reasons if reasons else "")))
    if prisma.get("excluidos_qualidade"):
        rows.append(("", n(t["quality"], prisma["excluidos_qualidade"])))
    outside = len(prisma.get("fora_da_triagem") or [])
    rows.append((n(t["included"], prisma.get("incluidos")), n(t["outside"], outside) if outside else ""))
    lines = []
    for i, (left, right) in enumerate(rows):
        lines.append((box(left) if left else "") + " & " + (box(right) if right else "") + r" \\[2pt]")
        if i < len(rows) - 1:
            lines.append(r"$\downarrow$ & \\[2pt]")
    return ("\n" + r"\begin{figure}[htbp]" + "\n" + r"\centering\small" + "\n"
            + r"\begin{tabular}{@{}>{\centering\arraybackslash}p{0.46\textwidth}>{\centering\arraybackslash}p{0.46\textwidth}@{}}"
            + "\n" + "\n".join(lines) + "\n" + r"\end{tabular}" + "\n"
            + r"\caption{" + t["caption"] + "}\n" + r"\label{fig:prisma}" + "\n"
            + r"\par\footnotesize " + t["source"] + "\n" + r"\end{figure}" + "\n")


def place_prisma(body: str, figure: str) -> str:
    marker = re.compile(r"^[ \t]*%[ \t]*PRISMA[ \t]*$", re.M | re.I)
    if marker.search(body):
        return marker.sub(lambda m: figure, body, count=1)
    results = re.search(r"\\section\*?\{(Resultados|Results)", body)
    if results:
        return body[:results.start()] + figure + "\n" + body[results.start():]
    return body + "\n" + figure


def assemble(project: dict, body: str, today: datetime | None = None) -> str:
    if FORBIDDEN.search(body or "") or "^^" in (body or ""):
        raise ValueError("Corpo com comandos não permitidos")
    if project.get("tipo") == "revisao_sistematica" and project.get("prisma"):
        body = place_prisma(body, prisma_figure(project["prisma"], project.get("language", "pt-BR")))
    values = {"title": latex_escape(project.get("title", "")),
              "author": "Autoria a preencher pelo pesquisador",
              "date": run_date(project.get("language", "pt-BR"), today),
              "babel": "english" if project.get("language") == "en" else "brazil"}
    if project.get("template") == "artigo-simples":
        return (SIMPLE_PREAMBLE % values + body.strip() +
                "\n\n\\bibliographystyle{plainnat}\n\\bibliography{references}\n\\end{document}\n")
    text = body.strip()
    if "\\end{resumo}" in text:
        text = text.replace("\\end{resumo}", "\\end{resumo}\n\\textual", 1)
    else:
        text = "\\textual\n" + text
    return ABNT_PREAMBLE % values + text + "\n\n\\postextual\n\\bibliography{references}\n\\end{document}\n"


def tex_env() -> dict:
    """TeX restrito: sem \\write18 e sem ler ou escrever fora do diretório de trabalho."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TEXMFHOME")}
    env.update(openin_any="p", openout_any="p", shell_escape="f")
    return env


def compile_tex(workdir: Path, tex: str, name: str = "scriptorium", timeout: int = 120) -> tuple[Path | None, dict]:
    (workdir / f"{name}.tex").write_text(tex, encoding="utf-8")
    steps = [["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"],
             ["bibtex", name],
             ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"],
             ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"]]
    for command in steps:
        try:
            subprocess.run(command, cwd=str(workdir), capture_output=True, timeout=timeout, check=False,
                           env=tex_env())
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, {"status": "falhou", "motivo": f"{command[0]}: {type(exc).__name__}"}
    log_path = workdir / f"{name}.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    report = {"citacoes_indefinidas": len(re.findall(r"Citation `[^']+' (?:on page \d+ )?undefined", log)),
              "erros_latex": len(re.findall(r"^! ", log, flags=re.M)), "log_final": log[-3000:]}
    pdf = workdir / f"{name}.pdf"
    if not pdf.exists() or pdf.stat().st_size < 1000:
        return None, {**report, "status": "falhou", "motivo": "pdflatex não gerou o PDF"}
    return pdf, {**report, "status": "ok"}


def provenance(project: dict, refs: list[dict], manifest: list[dict]) -> dict:
    """Quem fez cada etapa, com que independência, e o que foi conferido."""
    stages = project.get("stages") or {}
    steps = []
    for key, state in stages.items():
        head = state.get("head") or {}
        steps.append({"etapa": key, "versao": state.get("version"), "tentativas": state.get("attempts"),
                      "aceita_em": state.get("accepted_at"), "ia_declarada": head.get("model", ""),
                      "cliente": head.get("client", ""), "cabeca": head.get("id"),
                      "papel": head.get("kind"), "independencia": state.get("independencia"),
                      "conferencia": state.get("summary")})
    order = ["planejamento", "evidencias", "redacao", "revisao", "reescrita", "verificacao"]
    steps.sort(key=lambda s: order.index(s["etapa"]) if s["etapa"] in order else 99)
    ais = sorted({s["ia_declarada"] or s["cliente"] for s in steps if s["ia_declarada"] or s["cliente"]})
    return {
        "schema": "scriptorium.mcp_provenance/1", "projeto": project["id"], "titulo": project.get("title"),
        "modo": "sem API: IA do próprio pesquisador via MCP", "fluxo": project.get("flow_version"),
        "etapas": steps, "ias_usadas": ais,
        "fontes": [{"chave": m.get("key"), "nome": m.get("name"), "trechos": m.get("chunks")} for m in manifest],
        "referencias_a_conferir": [r["key"] for r in refs if r.get("how") == "arquivo"],
        "revisao_sistematica": ({"prisma": project.get("prisma"), "concordancia": project.get("concordancia"),
                                 "sintese_editada_pelo_pesquisador": sorted((project.get("sintese_final") or {}).keys())}
                                if project.get("tipo") == "revisao_sistematica" else None),
        "declaracao_sugerida": (
            "Texto produzido com apoio de IA generativa (" + ", ".join(ais) + ") conduzida pelo "
            "pesquisador no Scriptorium, em etapas separadas de planejamento, levantamento de "
            "evidências, redação, revisão independente, reescrita e verificação. As citações literais "
            "foram conferidas automaticamente nas fontes; o conteúdo final é de responsabilidade do autor."),
    }


# ---------------------------------------------------------------- trabalhos
def _project(db, data: dict, owner_uid: str):
    pid = data.get("mcp_project_id") or ""
    if not re.fullmatch(r"[0-9a-f]{32}", pid):
        raise ValueError("Projeto MCP inválido")
    ref = db.collection("mcp_projects").document(pid)
    snap = ref.get()
    project = snap.to_dict() if snap.exists else None
    if not project or project.get("owner_uid") != owner_uid:
        raise ValueError("Projeto MCP inválido")
    return ref, project


def prepare(data: dict, *, db, bucket, owner_uid: str, cache, get_json, update, derive, metadata) -> dict:
    """derive(entry, fetch, cache) -> (payload, status); metadata(entry, fetch, cache) -> dict."""
    from source_materials import derived_key
    ref, project = _project(db, data, owner_uid)
    sources = data.get("sources") or []
    if any(not str(s.get("object_path", "")).startswith(f"library/{owner_uid}/{s.get('id', '')}/")
           for s in sources):
        raise ValueError("Referência inválida na biblioteca desta conta")
    update(status="running", stage="Lendo as fontes do projeto",
           started_at=datetime.now(timezone.utc).isoformat())
    fetch = lambda path: bucket.blob(path).download_as_bytes()  # noqa: E731
    manifest, failures, ok, texts = [], [], [], {}
    for source in sources:
        try:
            payload, _ = derive(source, fetch, cache)
            texts[source["id"]] = bib_integrity.first_pages_text(payload)
            path = f"library/{owner_uid}/derived/{derived_key(source)}.json"
            if not bucket.blob(path).exists():  # cache não gravou: grava aqui para a API ler
                bucket.blob(path).upload_from_string(json.dumps(payload, ensure_ascii=False),
                                                     content_type="application/json")
            document = payload.get("document") or {}
            manifest.append({"id": source["id"], "name": source.get("name"), "format": source.get("format"),
                             "sha256": source.get("sha256"), "derived": path,
                             "chunks": len(payload.get("chunks") or []),
                             "pages": document.get("pages_total"), "warnings": document.get("warnings", [])[:5]})
            ok.append(source)
        except Exception as exc:
            failures.append({"id": source.get("id"), "nome": source.get("name"), "erro": type(exc).__name__})
    update(stage="Montando as referências oficiais")
    meta = {}
    for source in ok:
        try:
            meta[source["id"]] = metadata(source, fetch, cache)
        except Exception:
            meta[source["id"]] = {}
    entries = bib_integrity.library_entries(ok, get_json, meta, texts)
    key_of = {e["source_id"]: e["key"] for e in entries}
    for entry in manifest:
        entry["key"] = key_of.get(entry["id"])
    prefix = f"mcp/{owner_uid}/{project['id']}"
    bucket.blob(prefix + "/references.json").upload_from_string(
        json.dumps(entries, ensure_ascii=False), content_type="application/json")
    bucket.blob(prefix + "/references.bib").upload_from_string(
        "".join(bib_integrity.render(e) for e in entries), content_type="text/plain; charset=utf-8")
    bucket.blob(prefix + "/sources.json").upload_from_string(
        json.dumps(manifest, ensure_ascii=False), content_type="application/json")
    readable = [m for m in manifest if m["chunks"]]
    summary = {"fontes": len(sources), "lidas": len(readable), "trechos": sum(m["chunks"] for m in manifest),
               "falhas": failures, "sem_texto": [m["name"] for m in manifest if not m["chunks"]],
               "referencias_a_conferir": [e["key"] for e in entries if e.get("how") == "arquivo"]}
    status = "pronto" if readable else "falhou_preparo"
    fields = {"status": status, "prepare_summary": summary,
              "updated_at": datetime.now(timezone.utc).isoformat(),
              "error": "" if readable else "Nenhuma fonte com texto extraível (PDF escaneado precisa de OCR)."}
    ref.update(fields)
    update(status="completed", stage="Fontes prontas para a IA do pesquisador",
           finished_at=datetime.now(timezone.utc).isoformat())
    return summary


def compile_project(data: dict, *, db, bucket, owner_uid: str, update, workdir: Path, compiler=compile_tex) -> dict:
    ref, project = _project(db, data, owner_uid)
    stages = project.get("stages") or {}
    final_key = "reescrita" if (stages.get("reescrita") or {}).get("status") == "aceita" else "redacao"
    state = stages.get(final_key) or {}
    if state.get("status") != "aceita":
        raise ValueError("Não há texto aceito para compilar")
    prefix = f"mcp/{owner_uid}/{project['id']}"
    update(status="running", stage="Montando o LaTeX", started_at=datetime.now(timezone.utc).isoformat())
    body = bucket.blob(f"{prefix}/etapas/{final_key}-v{state['version']}.txt").download_as_bytes().decode("utf-8")
    refs = json.loads(bucket.blob(prefix + "/references.json").download_as_bytes())
    manifest = json.loads(bucket.blob(prefix + "/sources.json").download_as_bytes())
    tex = assemble(project, body)
    (workdir / "references.bib").write_text("".join(bib_integrity.render(e) for e in refs), encoding="utf-8")
    update(stage="Compilando o PDF")
    pdf, report = compiler(workdir, tex)
    record = provenance(project, refs, manifest)
    record["compilacao"] = {k: v for k, v in report.items() if k != "log_final"}
    files = []
    uploads = [("scriptorium.tex", workdir / "scriptorium.tex", "text/x-tex"),
               ("references.bib", workdir / "references.bib", "text/x-bibtex")]
    if pdf:
        uploads.append(("scriptorium.pdf", pdf, "application/pdf"))
    for name, path, mime in uploads:
        if path.exists():
            bucket.blob(f"{prefix}/final/{name}").upload_from_filename(str(path), content_type=mime)
            files.append(name)
    (workdir / "proveniencia.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    bucket.blob(f"{prefix}/final/proveniencia.json").upload_from_filename(
        str(workdir / "proveniencia.json"), content_type="application/json")
    files.append("proveniencia.json")
    now = datetime.now(timezone.utc).isoformat()
    if pdf:
        ref.update({"status": "concluido", "files": files, "compiled_at": now, "updated_at": now,
                    "compile_report": record["compilacao"], "error": ""})
        update(status="completed", stage="PDF pronto", finished_at=now)
    else:
        ref.update({"status": "pronto", "files": files, "updated_at": now, "compile_report": record["compilacao"],
                    "error": "A compilação falhou: " + str(report.get("motivo", "")) +
                    ". O .tex foi salvo para conferência."})
        update(status="completed", stage="Compilação falhou; .tex salvo", finished_at=now)
    return record
