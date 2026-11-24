"""Executa o pipeline original em uma tarefa Cloud Run Jobs.

Nenhum manuscrito depende do disco efêmero da instância após a execução.

Rastreabilidade (plano V2): run_manifest.py (M14) registra versões, hashes e
eventos; ai_declaration.py (M11; Origem: R25) gera o rascunho de declaração
de uso de IA; editorial_status.py (M07; Origem: R11) sinaliza retratações.
"""
import os
import re
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import firestore, storage
from agent_progress import current_stage, inspect_agents
from scientific_audit import audit_pdf
from reference_verification import verify_bibliography
from source_materials import compose_library_context, compose_library_context_v2
from neon_review import generate_review
from byok import personal_agent_environment
from run_manifest import RunManifest
from ai_declaration import build_declaration
from embeddings import make_embedder

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
BUCKET = os.environ["RESEARCH_BUCKET"]
RESEARCH_ID = os.environ["RESEARCH_ID"]
OWNER_UID = os.environ["RESEARCH_OWNER_UID"]
BASE = Path("/app/orchestra")
# Plano V2, Onda 1: contexto por trechos recuperados. Desligado por padrão.
V2_RETRIEVAL = os.getenv("SCRIPTORIUM_V2_RETRIEVAL", "false").lower() == "true"
# Onda 2: embeddings Gemini na busca e na matriz de evidências (envio de trechos
# autorizado pelo responsável em 24/11/2026). Só vale com V2_RETRIEVAL ligado.
V2_EMBEDDINGS = os.getenv("SCRIPTORIUM_V2_EMBEDDINGS", "true").lower() == "true"

client = firestore.Client(project=PROJECT)
storage_client = storage.Client(project=PROJECT)
bucket = storage_client.bucket(BUCKET)
ref = client.collection("research_jobs").document(RESEARCH_ID)
prefix = f"research/{OWNER_UID}/{RESEARCH_ID}"
# Manifesto de proveniência da execução atual (M14). Criado em main().
MANIFEST: RunManifest | None = None


def update(**fields):
    ref.update(fields)
    if MANIFEST is not None and ("stage" in fields or "status" in fields):
        MANIFEST.event(fields.get("stage") or fields.get("status"), status=fields.get("status"))


def now():
    return datetime.now(timezone.utc).isoformat()


def put(local: Path, remote_name: str, mime: str, record: bool = True):
    bucket.blob(f"{prefix}/output/{remote_name}").upload_from_filename(str(local), content_type=mime)
    # O próprio manifesto e a declaração derivada dele não entram na lista de saídas.
    if record and MANIFEST is not None:
        MANIFEST.add_output(remote_name, local)


class DerivedCache:
    """Cache privado de documentos estruturados e trechos, por dono e conteúdo.

    Caminho: library/{uid}/derived/{parser}/{política}/{sha256}.json. É dado
    derivado e descartável; o original da biblioteca nunca é alterado.
    """
    KEY = re.compile(r"[a-z0-9-]+/[a-z0-9-]+/[0-9a-f]{64}")

    def _blob(self, key: str):
        if not self.KEY.fullmatch(key):
            raise ValueError("Chave de cache inválida")
        return bucket.blob(f"library/{OWNER_UID}/derived/{key}.json")

    def get(self, key: str):
        blob = self._blob(key)
        return blob.download_as_bytes() if blob.exists() else None

    def put(self, key: str, data: bytes) -> None:
        self._blob(key).upload_from_string(data, content_type="application/json")


def publish_manifest(root: Path, status: str, error: str = "") -> dict:
    """Finaliza e envia run_manifest.json; devolve o conteúdo final."""
    manifest = MANIFEST.finish(status, error)
    path = MANIFEST.write(root / "run_manifest.json")
    put(path, "run_manifest.json", "application/json", record=False)
    return manifest


def main():
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("owner_uid") != OWNER_UID:
        raise ValueError("Pesquisa ou responsável inválidos")
    data = doc.to_dict()
    auth_mode = data.get("ai_auth_mode", "admin_vertex")
    if auth_mode not in ("admin_vertex", "user_gemini"):
        raise RuntimeError("Modo de autenticação de IA inválido")
    # Registros anteriores permanecem na modalidade administrativa legada.
    agent_env = (personal_agent_environment(os.environ, client, PROJECT, OWNER_UID)
                 if auth_mode == "user_gemini" else dict(os.environ))
    if auth_mode == "user_gemini" and data.get("neon_review_requested"):
        raise RuntimeError("Revisão Neon central bloqueada para pesquisadores BYOK")
    global MANIFEST
    # Recebe só campos selecionados do ambiente; nenhuma chave entra no manifesto.
    MANIFEST = RunManifest(RESEARCH_ID, OWNER_UID, data, os.environ, Path(__file__).resolve().parent)
    # Mesma identidade de IA da pesquisa: convidado usa a própria chave (BYOK).
    embedder = None
    if V2_RETRIEVAL and V2_EMBEDDINGS:
        try:
            embedder = make_embedder(auth_mode, agent_env, PROJECT)
        except Exception as exc:  # sem embeddings, a busca segue só com BM25
            print("Embeddings indisponíveis:", type(exc).__name__, flush=True)
    evidence_inputs = {"chunks": [], "vectors": {}, "sources": {}} if V2_RETRIEVAL else None
    update(status="running", stage="Preparando arquivos de entrada", started_at=now())
    with tempfile.TemporaryDirectory(prefix="orchestra_") as tmp:
        root = Path(tmp)
        raw = root / "raw_materials"
        output = root / "output"
        raw.mkdir(); output.mkdir()
        for filename in ("idea_sparse.md", "experimental_log.md"):
            bucket.blob(f"{prefix}/input/{filename}").download_to_filename(str(raw / filename))
            MANIFEST.add_input(filename, raw / filename)
        # Fontes próprias anexadas são extraídas como contexto limitado e não confiável.
        # Não apagamos nem alteramos os originais da biblioteca.
        if data.get("sources"):
            sources = data["sources"][:8]
            safe_sources = [
                x for x in sources
                if str(x.get("object_path", "")).startswith(
                    f"library/{OWNER_UID}/{x.get('id', '')}/"
                )
            ]
            if len(safe_sources) != len(sources):
                raise ValueError("Referência inválida na biblioteca desta conta")
            fetch = lambda object_path: bucket.blob(object_path).download_as_bytes()
            if V2_RETRIEVAL:
                # Consulta = título + ideia original (antes de anexar fontes e idioma).
                query = data.get("title", "") + "\n" + (raw / "idea_sparse.md").read_text(
                    encoding="utf-8", errors="replace")
                context, manifest, coverage = compose_library_context_v2(
                    safe_sources, fetch, query, cache=DerivedCache(),
                    embedder=embedder, collect=evidence_inputs)
                MANIFEST.set_context(coverage["strategy"], coverage)
                coverage_path = root / "retrieval_coverage.json"
                coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
                put(coverage_path, "retrieval_coverage.json", "application/json")
            else:
                context, manifest = compose_library_context(safe_sources, fetch)
                MANIFEST.set_context("v1-truncation-1")
            if context:
                with (raw / "idea_sparse.md").open("a", encoding="utf-8") as source_file:
                    source_file.write(context)
            MANIFEST.add_sources(manifest)
            manifest_path = root / "source_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            put(manifest_path, "source_manifest.json", "application/json")
            update(source_summary={
                "selected": len(safe_sources),
                "included": sum(m["status"] == "included" for m in manifest),
                "strategy": "v2" if V2_RETRIEVAL else "v1",
            })
        # Preferência aplicada somente aos dados temporários, não aos originais salvos.
        if data.get("language") == "pt-BR":
            with (raw / "idea_sparse.md").open("a", encoding="utf-8") as text:
                text.write(
                    "\n\n## Preferência de idioma\n"
                    "Redija o manuscrito em português brasileiro, incluindo resumo, títulos "
                    "e seções. Mantenha títulos de publicações, DOI e nomes próprios. "
                    "Não invente dados, citações ou resultados. "
                    "O template ICLR/CVPR continua o original e não é ABNT.\n"
                )
        # Hash do texto efetivamente entregue aos agentes (após anexos e idioma).
        for filename in ("idea_sparse.md", "experimental_log.md"):
            MANIFEST.add_agent_input(filename, raw / filename)
        command = [
            "python", "-u", "paper_writing_cli.py",
            "--raw_materials_dir", str(raw),
            "--output_dir", str(output),
            "--latex_template_dir", str(BASE / "templates" / data["template"]),
            "--writer_model_name", data["model"],
            "--reflection_model_name", data.get("reflection_model") or data["model"],
            "--use_plotting", "true" if data["plotting"] else "false",
        ]
        if data["plotting"]:
            command += ["--plotting_model_name", data["model"], "--image_model_name", "gemini-3-pro-image-preview"]
        update(stage="Iniciando agentes", agents=inspect_agents(output, bool(data["plotting"])))
        logpath = root / "execution.log"
        # Executa o motor original sem alterar sua ordem de agentes. A cada
        # intervalo, observa os artefatos reais produzidos no disco e atualiza
        # somente as mudanças de etapa (não inventa porcentagens de progresso).
        try:
            with open(logpath, "w", encoding="utf-8") as log:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        subprocess.run, command, cwd=str(BASE), stdout=log,
                        stderr=subprocess.STDOUT, timeout=10400, check=False,
                        env=agent_env
                    )
                    last_agents = None
                    while True:
                        agents = inspect_agents(output, bool(data["plotting"]))
                        if agents != last_agents:
                            update(agents=agents, stage=current_stage(agents))
                            last_agents = agents
                        try:
                            process = future.result(timeout=12)
                            break
                        except FutureTimeout:
                            continue
                    final_agents = inspect_agents(output, bool(data["plotting"]))
                    if final_agents != last_agents:
                        update(agents=final_agents, stage=current_stage(final_agents))
        finally:
            # Preserva o registro mesmo que o motor falhe ou exceda o timeout.
            if logpath.exists():
                # Logs do pipeline não podem revelar a chave em caso de erro externo.
                if auth_mode == "user_gemini":
                    contents = logpath.read_text(encoding="utf-8", errors="replace")
                    secret = agent_env["GEMINI_API_KEY"]
                    if secret in contents:
                        logpath.write_text(contents.replace(secret, "[REDACTED]"), encoding="utf-8")
                put(logpath, "execution.log", "text/plain; charset=utf-8")
        if process.returncode != 0:
            raise RuntimeError(f"O pipeline terminou com código {process.returncode}; consulte os logs do trabalho no Cloud Run.")
        update(stage="Armazenando o manuscrito")
        pdf = output / "final_paper.pdf"
        # O projeto salva este PDF na pasta principal do output.
        if not pdf.exists():
            matches = list(output.rglob("final_paper.pdf"))
            if not matches:
                raise FileNotFoundError("O motor concluiu sem gerar final_paper.pdf")
            pdf = matches[0]
        put(pdf, "final_paper.pdf", "application/pdf")
        files = ["pdf", "log"]
        # Auditoria local não gera texto ou evidências novas.
        try:
            refined_tex = output / "content_refinement_workdir" / "final_refined_paper.tex"
            raw_tex = output / "latex_writeup" / "raw_draft_paper.tex"
            bib = output / "latex_writeup" / "references.bib"
            report = audit_pdf(pdf, refined_tex if refined_tex.is_file() else raw_tex,
                               bib, raw / "experimental_log.md")
            report_file = root / "scientific_audit.json"
            report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            put(report_file, "scientific_audit.json", "application/json")
            files.append("audit")
            update(audit_status=report["status"], audit_findings=report["summary"]["findings"])
        except Exception as exc:
            print("Auditoria local indisponível:", repr(exc), flush=True)
            update(audit_status="unavailable")
        # Consulta metadados de referências somente depois que o PDF estiver pronto.
        # Nunca substitui citações nem marca publicações como cientificamente validadas.
        try:
            bib_path = output / "latex_writeup" / "references.bib"
            if bib_path.is_file():
                reference_report = verify_bibliography(bib_path.read_text(
                    encoding="utf-8", errors="replace"
                ))
                reference_file = root / "reference_verification.json"
                reference_file.write_text(
                    json.dumps(reference_report, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                put(reference_file, "reference_verification.json", "application/json")
                files.append("references")
                update(reference_status="completed_with_limitations",
                       references_checked=reference_report["checked"],
                       references_skipped=reference_report["skipped_by_limit"],
                       editorial_alerts=reference_report["editorial_summary"]["alerts"])
            else:
                update(reference_status="unavailable")
        except Exception as exc:
            print("Conferência bibliográfica externa indisponível:", repr(exc), flush=True)
            update(reference_status="unavailable")
        # M05 + M08/M10: citações literais e matriz de evidências (V2). Não
        # altera o manuscrito; falhas não invalidam o PDF já entregue.
        if evidence_inputs is not None:
            update(stage="Conferindo citações e evidências")
            try:
                from quote_verification import verify as verify_quotes
                from evidence_matrix import build_matrix, to_csv
                refined_tex = output / "content_refinement_workdir" / "final_refined_paper.tex"
                raw_tex = output / "latex_writeup" / "raw_draft_paper.tex"
                tex_path = refined_tex if refined_tex.is_file() else raw_tex
                tex = tex_path.read_text(encoding="utf-8", errors="replace")
                quotes = verify_quotes(tex, evidence_inputs["chunks"], evidence_inputs["sources"])
                matrix = build_matrix(tex, evidence_inputs["chunks"], evidence_inputs["sources"],
                                      vectors=evidence_inputs["vectors"], embedder=embedder)
                report = {"schema": "scriptorium.evidence_report/1", "manuscript": tex_path.name,
                          "quotes": quotes, "matrix": matrix}
                report_path = root / "evidence_report.json"
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                put(report_path, "evidence_report.json", "application/json")
                csv_path = root / "evidence_matrix.csv"
                csv_path.write_text(to_csv(matrix), encoding="utf-8-sig")
                put(csv_path, "evidence_matrix.csv", "text/csv; charset=utf-8")
                files += ["evidence", "evidence_csv"]
                update(evidence_status="completed", evidence_summary={
                    "quotes": quotes["summary"].get("quotes", 0),
                    "quotes_not_found": quotes["summary"].get("not_found_in_sources", 0),
                    "pointers_unknown": quotes["summary"].get("pointers_unknown", 0),
                    "claims": matrix["summary"]["claims"],
                    "claims_without_evidence": matrix["summary"]["without_evidence_in_corpus"],
                })
            except Exception as exc:
                print("Conferência de evidências indisponível:", repr(exc), flush=True)
                update(evidence_status="unavailable")
        if embedder is not None:
            MANIFEST.add_ai_service("embeddings", embedder.info())
        # Parecer Neon totalmente opcional, isolado do pipeline original.
        # Falhas não invalidam PDF já gerado nem disparam múltiplas cobranças.
        if data.get("neon_review_requested") and auth_mode == "admin_vertex":
            update(stage="Revisão crítica opcional com Gemini Neon", neon_review_status="running")
            try:
                review = generate_review(
                    pdf, raw / "idea_sparse.md", raw / "experimental_log.md"
                )
                review_path = root / "neon_critical_review.json"
                review_path.write_text(
                    json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                put(review_path, "neon_critical_review.json", "application/json")
                files.append("neon")
                update(neon_review_status="completed")
            except Exception as exc:
                print("Revisão Neon indisponível:", repr(exc), flush=True)
                update(neon_review_status="unavailable")
        latex_workdir = output / "latex_writeup"
        final_tex = output / "content_refinement_workdir" / "final_refined_paper.tex"
        if latex_workdir.is_dir() and final_tex.exists():
            assembled = root / "latex_source"
            shutil.copytree(latex_workdir, assembled)
            shutil.copy2(final_tex, assembled / "main.tex")
            zipfile = shutil.make_archive(str(root / "latex_source"), "zip", str(assembled))
            put(Path(zipfile), "latex_source.zip", "application/zip")
            files.append("latex")
        final_agents = inspect_agents(output, bool(data["plotting"]))
        # M14 + M11: manifesto e rascunho de declaração. Falha aqui não
        # invalida o manuscrito já entregue.
        try:
            update(stage="Registrando proveniência")
            manifest = publish_manifest(root, "completed")
            files.append("manifest")
            declaration = root / "declaracao_uso_ia.md"
            declaration.write_text(build_declaration(manifest, final_agents), encoding="utf-8")
            put(declaration, "declaracao_uso_ia.md", "text/markdown; charset=utf-8", record=False)
            files.append("declaration")
        except Exception as exc:
            print("Manifesto ou declaração indisponíveis:", repr(exc), flush=True)
        update(status="completed", stage="Concluído", agents=final_agents, finished_at=now(), files=files)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Guardar erro genérico para o navegador; detalhes somente nos Cloud Logs.
        print(traceback.format_exc(), flush=True)
        try:
            update(status="failed", stage="Falha", error=str(exc)[:400], finished_at=now())
        except Exception:
            pass
        # Manifesto também em falhas: mostra até onde a execução chegou.
        if MANIFEST is not None:
            try:
                with tempfile.TemporaryDirectory(prefix="manifest_") as tmp:
                    publish_manifest(Path(tmp), "failed", str(exc))
                ref.update({"files": firestore.ArrayUnion(["manifest"])})
            except Exception as manifest_error:
                print("Manifesto de falha indisponível:", repr(manifest_error), flush=True)
        raise
