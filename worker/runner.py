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
import billing_alert
from run_manifest import RunManifest
from ai_declaration import build_declaration
from embeddings import make_embedder
from stage_budget import STAGES, Cancelled, StageBudget

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
BUCKET = os.environ["RESEARCH_BUCKET"]
RESEARCH_ID = os.environ["RESEARCH_ID"]
OWNER_UID = os.environ["RESEARCH_OWNER_UID"]
BASE = Path("/app/orchestra")
# Plano V2, Onda 1: contexto por trechos recuperados. Desligado por padrão.
V2_RETRIEVAL = os.getenv("SCRIPTORIUM_V2_RETRIEVAL", "false").lower() == "true"
# Separação de custos: o projeto paga infraestrutura; tokens de IA saem da chave
# Gemini pessoal de quem gera. Vertex do projeto só com exceção explícita.
ALLOW_PROJECT_AI = os.getenv("SCRIPTORIUM_ALLOW_PROJECT_AI", "false").lower() == "true"
# Onda 2: embeddings Gemini na busca e na matriz de evidências (envio de trechos
# autorizado pelo responsável em 24/11/2026). Só vale com V2_RETRIEVAL ligado.
V2_EMBEDDINGS = os.getenv("SCRIPTORIUM_V2_EMBEDDINGS", "true").lower() == "true"
# M17 experimental: classifica pares de trechos com o modelo (custo extra). Desligado.
V2_CONTRADICTIONS = os.getenv("SCRIPTORIUM_V2_CONTRADICTIONS", "false").lower() == "true"
# M22 experimental: verificação iterativa das afirmações (orçamento fixo). Desligado.
V2_FIRE = os.getenv("SCRIPTORIUM_V2_FIRE", "false").lower() == "true"
# M20: reranker opcional ("none", "bge" ou "inranker"); bibliotecas fora da imagem.
V2_RERANKER = os.getenv("SCRIPTORIUM_V2_RERANKER", "none").lower()

client = firestore.Client(project=PROJECT)
storage_client = storage.Client(project=PROJECT)
bucket = storage_client.bucket(BUCKET)
ref = client.collection("research_jobs").document(RESEARCH_ID)
prefix = f"research/{OWNER_UID}/{RESEARCH_ID}"
# Manifesto de proveniência da execução atual (M14). Criado em main().
MANIFEST: RunManifest | None = None
# M07: modo especial que só reconsulta avisos editoriais de uma pesquisa concluída.
RECHECK = os.getenv("RESEARCH_MODE") == "editorial_recheck"


def cancel_requested() -> bool:
    """M15: o navegador grava cancel_requested; o worker confere entre ciclos e etapas."""
    snap = ref.get()
    return bool(snap.exists and (snap.to_dict() or {}).get("cancel_requested"))


BUDGET = StageBudget(cancel_requested)


def stop_process(process, grace: int = 20) -> None:
    """Encerra o motor: SIGTERM, espera, depois SIGKILL."""
    process.terminate()
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def optional_stage(name: str) -> bool:
    """Confere cancelamento e orçamento antes de uma etapa opcional (M15).

    Etapas opcionais só rodam depois que o PDF já foi entregue; um cancelamento
    nesse ponto pula o que falta e conclui a pesquisa com o que já existe.
    """
    try:
        BUDGET.check_cancel()
    except Cancelled:
        BUDGET.records[name] = {"status": "pulada_por_cancelamento"}
        return False
    if not BUDGET.allows(name):
        print(f"Etapa {name} pulada: tempo restante insuficiente.", flush=True)
        return False
    BUDGET.start(name, check_cancel=False)
    return True


def update(**fields):
    ref.update(fields)
    if MANIFEST is not None and ("stage" in fields or "status" in fields):
        MANIFEST.event(fields.get("stage") or fields.get("status"), status=fields.get("status"))


def now():
    return datetime.now(timezone.utc).isoformat()


def key_worked() -> None:
    """A chave pessoal respondeu: some o aviso de saldo esgotado, se houver."""
    try:
        billing_alert.clear(client, OWNER_UID, firestore.DELETE_FIELD)
    except Exception as exc:  # aviso é auxiliar; nunca derruba a execução
        print("Aviso de saldo não atualizado:", repr(exc), flush=True)


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
    # M15: tempos por etapa, tetos e etapas puladas por orçamento.
    MANIFEST.data["stage_budget"] = BUDGET.report()
    manifest = MANIFEST.finish(status, error)
    path = MANIFEST.write(root / "run_manifest.json")
    put(path, "run_manifest.json", "application/json", record=False)
    return manifest


def run_preflight(root: Path, raw: Path, data: dict, evidence_inputs: dict,
                  source_records: list, embedder) -> None:
    """M16: diagnóstico das fontes; para no checkpoint de aprovação (M12)."""
    from gap_report import build_gap_report
    update(stage="Diagnosticando as fontes")
    idea = (raw / "idea_sparse.md").read_text(encoding="utf-8", errors="replace")
    # A ideia já tem as fontes anexadas ao final; o diagnóstico usa só o texto do autor.
    idea = idea.split("\n\n## MATERIAIS PRÓPRIOS ANEXADOS")[0]
    report = build_gap_report(data.get("title", ""), idea, evidence_inputs["chunks"],
                              evidence_inputs["sources"], source_records,
                              vectors=evidence_inputs["vectors"], embedder=embedder)
    path = root / "gap_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    put(path, "gap_report.json", "application/json")
    if embedder is not None:
        MANIFEST.add_ai_service("embeddings", embedder.info())
    publish_manifest(root, "awaiting_source_approval")
    update(status="awaiting_source_approval", stage="Aguardando sua aprovação das fontes",
           files=["gap_report", "manifest"], gap_summary=report["summary"],
           checkpoint={"name": "source_approval", "requested_at": now()})


def run_editorial_recheck(data: dict) -> None:
    """M07: reconsulta avisos editoriais (retratações etc.) de uma pesquisa concluída."""
    import requests
    from editorial_recheck import recheck
    from editorial_status import editorial_status
    from reference_verification import USER_AGENT, _request
    if data.get("status") != "completed":
        raise RuntimeError("Só pesquisas concluídas podem ser reavaliadas")
    ref.update({"editorial_recheck.status": "running", "editorial_recheck.started_at": now()})
    blob = bucket.blob(f"{prefix}/output/reference_verification.json")
    if not blob.exists():
        raise FileNotFoundError("Esta pesquisa não tem conferência de referências")
    report = json.loads(blob.download_as_bytes().decode("utf-8"))
    session = requests.Session()
    result = recheck(report, lambda doi: editorial_status(doi, session, _request, user_agent=USER_AGENT))
    bucket.blob(f"{prefix}/output/editorial_recheck.json").upload_from_string(
        json.dumps(result, ensure_ascii=False, indent=2), content_type="application/json")
    ref.update({"editorial_recheck": {"status": "completed", "checked_at": result["checked_at"],
                                      **result["summary"]},
                "files": firestore.ArrayUnion(["editorial_recheck"])})


def run_reading_notes(data: dict) -> None:
    """M21: fichamento por IA de um documento, com a identidade de IA da conta."""
    from google import genai
    from reading_notes import generate_notes, namespace
    from source_materials import derive_source
    auth_mode = data.get("ai_auth_mode")
    if auth_mode not in ("admin_vertex", "user_gemini"):
        raise RuntimeError("Modo de autenticação de IA inválido")
    if auth_mode == "admin_vertex" and not ALLOW_PROJECT_AI:
        raise RuntimeError("Uso de IA pelo projeto de infraestrutura desativado. Conecte sua chave Gemini pessoal.")
    entry = (data.get("sources") or [None])[0]
    if not entry or not str(entry.get("object_path", "")).startswith(f"library/{OWNER_UID}/{entry.get('id', '')}/"):
        raise ValueError("Referência inválida na biblioteca desta conta")
    update(status="running", stage="Lendo o documento", started_at=now())
    cache = DerivedCache()
    payload, _ = derive_source(entry, lambda path: bucket.blob(path).download_as_bytes(), cache)
    if auth_mode == "user_gemini":
        env = personal_agent_environment(os.environ, client, PROJECT, OWNER_UID)
        ai = genai.Client(api_key=env["GEMINI_API_KEY"])
    else:
        ai = genai.Client(enterprise=True, project=PROJECT, location="global")
    update(stage="Gerando o fichamento com IA")
    try:
        notes = generate_notes(ai, data.get("model") or "gemini-3-flash-preview", entry, payload["chunks"])
    finally:
        ai.close()
    key = f"{namespace(notes['model'])}/{notes['parser_version']}-{notes['chunk_policy']}/{entry['sha256']}"
    cache.put(key, json.dumps(notes, ensure_ascii=False).encode("utf-8"))
    if auth_mode == "user_gemini":
        key_worked()
    update(status="completed", stage="Fichamento pronto", finished_at=now(), files=["reading_notes"],
           notes_usage=notes.get("usage") or {})


def run_retrieval_eval(data: dict) -> None:
    """M04 (gate G2): busca lexical, vetorial e híbrida no corpus de referência.

    Só administrador (a API confere). Os PDFs são de acesso aberto e vêm dos
    links fixos da imagem (corpus_ref/selecao.json), conferidos por SHA-256.
    Embeddings com a chave Gemini pessoal de quem pediu; nunca o projeto.
    """
    import tempfile
    from urllib.parse import urljoin

    import requests
    from google import genai
    from embeddings import PROVIDERS, GeminiEmbedder
    from retrieval_eval import MAX_PDF_BYTES, USER_AGENT, fetch_reference_corpus, reference_eval, summary
    if data.get("ai_auth_mode") != "user_gemini":
        raise RuntimeError("O teste de busca usa só a chave Gemini pessoal")
    base = Path(__file__).resolve().parent / "corpus_ref"
    selection = json.loads((base / "selecao.json").read_text(encoding="utf-8"))
    queries = [json.loads(line) for line in (base / "consultas.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    update(status="running", stage="Baixando os PDFs de acesso aberto", started_at=now())
    session = requests.Session()

    def http_get(url: str) -> bytes:
        # Links fixos da imagem; redirecionamento só para https.
        for _ in range(4):
            response = session.get(url, timeout=60, allow_redirects=False, stream=True,
                                   headers={"User-Agent": USER_AGENT})
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                if not url.startswith("https://"):
                    raise ValueError("redirecionamento inseguro")
                continue
            response.raise_for_status()
            data_bytes = b""
            for piece in response.iter_content(65536):
                data_bytes += piece
                if len(data_bytes) > MAX_PDF_BYTES:
                    raise ValueError("arquivo grande demais")
            return data_bytes
        raise ValueError("redirecionamentos demais")

    env = personal_agent_environment(os.environ, client, PROJECT, OWNER_UID)
    ai = genai.Client(api_key=env["GEMINI_API_KEY"])
    embedder = GeminiEmbedder(ai, PROVIDERS["user_gemini"])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            fetched = fetch_reference_corpus(selection, Path(tmp), http_get)
            if not fetched["downloaded"]:
                raise RuntimeError("Nenhum PDF do corpus pôde ser baixado")
            update(stage=f"Medindo a busca em {len(fetched['downloaded'])} PDFs (embeddings na sua chave)")
            report = reference_eval(Path(tmp), queries, embedder)
    finally:
        ai.close()
    report["download"] = fetched
    report["finished_at"] = now()
    bucket.blob(f"{prefix}/output/retrieval_eval.json").upload_from_string(
        json.dumps(report, ensure_ascii=False, indent=2), content_type="application/json")
    key_worked()
    update(status="completed", stage="Teste de busca concluído", finished_at=now(), files=["retrieval_eval"],
           retrieval_eval_summary=summary(report))


def main():
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("owner_uid") != OWNER_UID:
        raise ValueError("Pesquisa ou responsável inválidos")
    data = doc.to_dict()
    if RECHECK:
        # M07: não usa IA nem altera o estado da pesquisa concluída.
        run_editorial_recheck(data)
        return
    if data.get("mode") == "retrieval_eval":
        # M04 (gate G2): teste de busca no corpus de referência (administrador).
        run_retrieval_eval(data)
        return
    if data.get("mode") == "reading_notes":
        # M21: fichamento sob demanda de um documento da biblioteca.
        run_reading_notes(data)
        return
    # M15: cancelada ainda na fila? Não inicia nada.
    BUDGET.check_cancel()
    auth_mode = data.get("ai_auth_mode", "admin_vertex")
    if auth_mode not in ("admin_vertex", "user_gemini"):
        raise RuntimeError("Modo de autenticação de IA inválido")
    if auth_mode == "admin_vertex" and not ALLOW_PROJECT_AI:
        # Fail-closed: nenhum token de geração no projeto de infraestrutura.
        raise RuntimeError("Uso de IA pelo projeto de infraestrutura desativado. "
                           "Conecte sua chave Gemini pessoal e inicie a pesquisa novamente.")
    # Registros anteriores permanecem na modalidade administrativa legada.
    agent_env = (personal_agent_environment(os.environ, client, PROJECT, OWNER_UID)
                 if auth_mode == "user_gemini" else dict(os.environ))
    global MANIFEST
    # Recebe só campos selecionados do ambiente; nenhuma chave entra no manifesto.
    MANIFEST = RunManifest(RESEARCH_ID, OWNER_UID, data, os.environ, Path(__file__).resolve().parent)
    # Mesma identidade de IA da pesquisa: convidado usa a própria chave (BYOK).
    # M16/M12: "preflight" só diagnostica as fontes e para no checkpoint de
    # aprovação; "generate" é a pesquisa completa (direta ou já aprovada).
    mode = data.get("mode") or "generate"
    if mode not in ("preflight", "generate"):
        raise RuntimeError("Modo de execução inválido")
    # O diagnóstico usa a leitura por trechos mesmo com a flag V2 desligada:
    # foi pedido explicitamente pelo pesquisador e não gera texto.
    use_v2 = V2_RETRIEVAL or mode == "preflight"
    embedder = None
    if use_v2 and V2_EMBEDDINGS:
        try:
            embedder = make_embedder(auth_mode, agent_env, PROJECT)
        except Exception as exc:  # sem embeddings, a busca segue só com BM25
            print("Embeddings indisponíveis:", type(exc).__name__, flush=True)
    reranker, reranker_note = None, None
    if use_v2 and V2_RERANKER != "none":
        try:
            from reranker import make_reranker
            reranker = make_reranker(V2_RERANKER)
        except Exception as exc:  # biblioteca ausente: segue sem reranking
            reranker_note = {"status": "unavailable", "name": V2_RERANKER, "reason": type(exc).__name__}
    evidence_inputs = {"chunks": [], "vectors": {}, "sources": {}} if use_v2 else None
    # M06: relatórios reunidos no escudo de auditoria; M09: cobertura publicada.
    shield_inputs = {"audit": None, "references": None, "evidence": None, "contradictions": None,
                     "fire": None}
    coverage_published = False
    update(status="running", stage="Preparando arquivos de entrada", started_at=now(),
           # Identificador da execução do Cloud Run, para auditoria e suporte.
           execution=os.getenv("CLOUD_RUN_EXECUTION", ""))
    BUDGET.start("preparo_das_fontes")
    derived_cache = DerivedCache()
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
            if use_v2:
                # Consulta = título + ideia original (antes de anexar fontes e idioma).
                query = data.get("title", "") + "\n" + (raw / "idea_sparse.md").read_text(
                    encoding="utf-8", errors="replace")
                context, manifest, coverage = compose_library_context_v2(
                    safe_sources, fetch, query, cache=derived_cache,
                    embedder=embedder, reranker=reranker, collect=evidence_inputs)
                # M09: cobertura por autor, época e tema do que os agentes leram.
                try:
                    from coverage_facets import build_facets, source_metadata
                    from gap_report import extract_questions
                    metadata = {x["id"]: source_metadata(x, fetch, derived_cache) for x in safe_sources}
                    original_idea = (raw / "idea_sparse.md").read_text(encoding="utf-8", errors="replace")
                    coverage["facets"] = build_facets(
                        extract_questions(data.get("title", ""), original_idea),
                        evidence_inputs["chunks"], evidence_inputs.get("selected_ids") or [],
                        evidence_inputs["sources"], metadata)
                except Exception as exc:
                    coverage["facets"] = {"status": "unavailable", "reason": type(exc).__name__}
                if reranker_note and not coverage.get("reranker"):
                    coverage["reranker"] = reranker_note
                MANIFEST.set_context(coverage["strategy"], coverage)
                coverage_path = root / "retrieval_coverage.json"
                coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
                put(coverage_path, "retrieval_coverage.json", "application/json")
                coverage_published = True
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
        BUDGET.finish("preparo_das_fontes")
        if mode == "preflight":
            run_preflight(root, raw, data, evidence_inputs, manifest if data.get("sources") else [], embedder)
            return
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
        # M15: no mesmo ciclo confere se o pesquisador pediu o cancelamento.
        BUDGET.start("agentes_de_redacao")
        returncode = None
        try:
            with open(logpath, "w", encoding="utf-8") as log:
                process = subprocess.Popen(command, cwd=str(BASE), stdout=log,
                                           stderr=subprocess.STDOUT, env=agent_env)
                deadline = BUDGET.clock() + STAGES["agentes_de_redacao"]["max_seconds"]
                last_agents = None
                try:
                    while True:
                        agents = inspect_agents(output, bool(data["plotting"]))
                        if agents != last_agents:
                            update(agents=agents, stage=current_stage(agents))
                            last_agents = agents
                        try:
                            returncode = process.wait(timeout=12)
                            break
                        except subprocess.TimeoutExpired:
                            pass
                        BUDGET.check_cancel()
                        if BUDGET.clock() > deadline:
                            raise TimeoutError("O motor excedeu o tempo máximo da etapa de redação.")
                finally:
                    if process.poll() is None:
                        stop_process(process)
                final_agents = inspect_agents(output, bool(data["plotting"]))
                if final_agents != last_agents:
                    update(agents=final_agents, stage=current_stage(final_agents))
        finally:
            BUDGET.finish("agentes_de_redacao", "concluida" if returncode == 0 else "interrompida")
            # Preserva o registro mesmo que o motor falhe ou exceda o timeout.
            if logpath.exists():
                # Logs do pipeline não podem revelar a chave em caso de erro externo.
                if auth_mode == "user_gemini":
                    contents = logpath.read_text(encoding="utf-8", errors="replace")
                    secret = agent_env["GEMINI_API_KEY"]
                    if secret in contents:
                        logpath.write_text(contents.replace(secret, "[REDACTED]"), encoding="utf-8")
                put(logpath, "execution.log", "text/plain; charset=utf-8")
        if returncode != 0:
            if auth_mode == "user_gemini" and billing_alert.log_mentions_depleted(logpath):
                raise RuntimeError(billing_alert.MESSAGE)
            raise RuntimeError(f"O pipeline terminou com código {returncode}; consulte os logs do trabalho no Cloud Run.")
        update(stage="Armazenando o manuscrito")
        pdf = output / "final_paper.pdf"
        # O projeto salva este PDF na pasta principal do output.
        if not pdf.exists():
            matches = list(output.rglob("final_paper.pdf"))
            if not matches:
                raise FileNotFoundError("O motor concluiu sem gerar final_paper.pdf")
            pdf = matches[0]
        put(pdf, "final_paper.pdf", "application/pdf")
        files = (["pdf", "log"] + (["coverage"] if coverage_published else [])
                 # O diagnóstico aprovado (M16/M12) continua disponível no histórico.
                 + (["gap_report"] if "gap_report" in (data.get("files") or []) else []))
        # Auditoria local não gera texto ou evidências novas.
        if optional_stage("triagem_cientifica"):
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
                shield_inputs["audit"] = report
                BUDGET.finish("triagem_cientifica")
            except Exception as exc:
                print("Auditoria local indisponível:", repr(exc), flush=True)
                update(audit_status="unavailable")
                BUDGET.finish("triagem_cientifica", "indisponivel")
        else:
            update(audit_status="unavailable")
        # Consulta metadados de referências somente depois que o PDF estiver pronto.
        # Nunca substitui citações nem marca publicações como cientificamente validadas.
        bib_path = output / "latex_writeup" / "references.bib"
        if bib_path.is_file():
            # M27: BibTeX final disponível sozinho, base da exportação CSL-JSON e ABNT.
            put(bib_path, "references.bib", "application/x-bibtex")
            files.append("bibtex")
        if optional_stage("conferencia_de_referencias"):
            try:
                if bib_path.is_file():
                    reference_report = verify_bibliography(bib_path.read_text(
                        encoding="utf-8", errors="replace"
                    ))
                    # M24: decisões humanas de pesquisas anteriores, lado a lado.
                    try:
                        from manual_reviews import apply_history, load_history
                        apply_history(reference_report, load_history(client, OWNER_UID, RESEARCH_ID))
                    except Exception as exc:
                        print("Histórico de conferência manual indisponível:", repr(exc), flush=True)
                    reference_file = root / "reference_verification.json"
                    reference_file.write_text(
                        json.dumps(reference_report, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    put(reference_file, "reference_verification.json", "application/json")
                    files.append("references")
                    shield_inputs["references"] = reference_report
                    update(reference_status="completed_with_limitations",
                           references_checked=reference_report["checked"],
                           references_skipped=reference_report["skipped_by_limit"],
                           editorial_alerts=reference_report["editorial_summary"]["alerts"])
                    BUDGET.finish("conferencia_de_referencias", checked=reference_report["checked"])
                else:
                    update(reference_status="unavailable")
                    BUDGET.finish("conferencia_de_referencias", "sem_bibtex")
            except Exception as exc:
                print("Conferência bibliográfica externa indisponível:", repr(exc), flush=True)
                update(reference_status="unavailable")
                BUDGET.finish("conferencia_de_referencias", "indisponivel")
        else:
            update(reference_status="unavailable")
        # M05 + M08/M10: citações literais e matriz de evidências (V2). Não
        # altera o manuscrito; falhas não invalidam o PDF já entregue.
        if evidence_inputs is not None and optional_stage("citacoes_e_evidencias"):
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
                shield_inputs["evidence"] = report
                update(evidence_status="completed", evidence_summary={
                    "quotes": quotes["summary"].get("quotes", 0),
                    "quotes_not_found": quotes["summary"].get("not_found_in_sources", 0),
                    "pointers_unknown": quotes["summary"].get("pointers_unknown", 0),
                    "claims": matrix["summary"]["claims"],
                    "claims_without_evidence": matrix["summary"]["without_evidence_in_corpus"],
                })
                BUDGET.finish("citacoes_e_evidencias", claims=matrix["summary"]["claims"])
            except Exception as exc:
                print("Conferência de evidências indisponível:", repr(exc), flush=True)
                update(evidence_status="unavailable")
                BUDGET.finish("citacoes_e_evidencias", "indisponivel")
        # M22 (experimental): verificação iterativa das afirmações nas fontes.
        if (V2_FIRE and embedder is not None and shield_inputs["evidence"]
                and optional_stage("verificacao_fire")):
            update(stage="Verificando afirmações nas fontes (experimental)")
            try:
                from fire_audit import run_fire
                fire = run_fire(shield_inputs["evidence"]["matrix"], evidence_inputs["chunks"],
                                evidence_inputs["vectors"], evidence_inputs["sources"],
                                embedder.client, embedder)
                fire_path = root / "fire_audit.json"
                fire_path.write_text(json.dumps(fire, ensure_ascii=False, indent=2), encoding="utf-8")
                put(fire_path, "fire_audit.json", "application/json")
                files.append("fire")
                shield_inputs["fire"] = fire
                MANIFEST.add_ai_service("fire", {"model": fire["model"], "provider": embedder.provider,
                                                 **fire["usage"]})
                BUDGET.finish("verificacao_fire", model_calls=fire["usage"].get("calls"))
            except Exception as exc:
                print("Verificação iterativa indisponível:", repr(exc), flush=True)
                BUDGET.finish("verificacao_fire", "indisponivel")
        # M17 (experimental): possíveis divergências entre fontes.
        if (V2_CONTRADICTIONS and embedder is not None and evidence_inputs
                and evidence_inputs.get("vectors") and optional_stage("divergencias_entre_fontes")):
            update(stage="Comparando fontes (experimental)")
            try:
                from contradictions import detect
                selected = set(evidence_inputs.get("selected_ids") or [])
                result = detect([c for c in evidence_inputs["chunks"] if c["chunk_id"] in selected],
                                evidence_inputs["vectors"], evidence_inputs["sources"], embedder.client)
                result_path = root / "contradictions.json"
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                put(result_path, "contradictions.json", "application/json")
                files.append("contradictions")
                shield_inputs["contradictions"] = result
                MANIFEST.add_ai_service("contradictions", {"model": result["model"],
                                                           "provider": embedder.provider, **result["usage"]})
                BUDGET.finish("divergencias_entre_fontes", model_calls=result["usage"].get("calls"))
            except Exception as exc:
                print("Comparação de fontes indisponível:", repr(exc), flush=True)
                BUDGET.finish("divergencias_entre_fontes", "indisponivel")
        if embedder is not None:
            MANIFEST.add_ai_service("embeddings", embedder.info())
        # M06: escudo de auditoria em camadas (sem nota geral nem selo).
        try:
            from audit_shield import build_shield
            shield = build_shield(shield_inputs["audit"], shield_inputs["references"],
                                  shield_inputs["evidence"], shield_inputs["contradictions"],
                                  shield_inputs["fire"])
            shield_path = root / "audit_shield.json"
            shield_path.write_text(json.dumps(shield, ensure_ascii=False, indent=2), encoding="utf-8")
            put(shield_path, "audit_shield.json", "application/json")
            files.append("shield")
            update(shield_counts=shield["counts"])
        except Exception as exc:
            print("Escudo de auditoria indisponível:", repr(exc), flush=True)
        # Parecer Neon totalmente opcional, isolado do pipeline original.
        # Falhas não invalidam PDF já gerado nem disparam múltiplas cobranças.
        if data.get("neon_review_requested"):
            if optional_stage("parecer_neon"):
                update(stage="Revisão crítica opcional com Gemini Neon", neon_review_status="running")
                try:
                    # Tokens do Neon na chave pessoal de quem gera (não no projeto).
                    neon_client = None
                    if auth_mode == "user_gemini":
                        from google import genai
                        neon_client = genai.Client(api_key=agent_env["GEMINI_API_KEY"])
                    # M25: parecer com acesso restrito à matriz de evidências (M08).
                    review = generate_review(
                        pdf, raw / "idea_sparse.md", raw / "experimental_log.md", client=neon_client,
                        evidence_matrix=(shield_inputs["evidence"] or {}).get("matrix"),
                    )
                    review_path = root / "neon_critical_review.json"
                    review_path.write_text(
                        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    put(review_path, "neon_critical_review.json", "application/json")
                    files.append("neon")
                    update(neon_review_status="completed")
                    BUDGET.finish("parecer_neon")
                except Exception as exc:
                    print("Revisão Neon indisponível:", repr(exc), flush=True)
                    update(neon_review_status="unavailable")
                    BUDGET.finish("parecer_neon", "indisponivel")
            else:
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
            BUDGET.start("registro_final", check_cancel=False)
            update(stage="Registrando proveniência")
            manifest = publish_manifest(root, "completed")
            files.append("manifest")
            declaration = root / "declaracao_uso_ia.md"
            declaration.write_text(build_declaration(manifest, final_agents), encoding="utf-8")
            put(declaration, "declaracao_uso_ia.md", "text/markdown; charset=utf-8", record=False)
            files.append("declaration")
            BUDGET.finish("registro_final")
        except Exception as exc:
            print("Manifesto ou declaração indisponíveis:", repr(exc), flush=True)
        skipped = any(r.get("status") == "pulada_por_cancelamento" for r in BUDGET.records.values())
        if auth_mode == "user_gemini":
            key_worked()
        update(status="completed", agents=final_agents, finished_at=now(), files=files,
               stage="Concluído (etapas opcionais canceladas)" if skipped else "Concluído")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(traceback.format_exc(), flush=True)
        if RECHECK:
            # A pesquisa continua concluída; só a reavaliação falhou.
            try:
                ref.update({"editorial_recheck": {"status": "failed", "error": str(exc)[:300],
                                                  "checked_at": now()}})
            except Exception:
                pass
            raise
        cancelled = isinstance(exc, Cancelled)
        # Guardar erro genérico para o navegador; detalhes somente nos Cloud Logs.
        try:
            if cancelled:
                update(status="cancelled", stage="Cancelada pelo pesquisador", finished_at=now(),
                       error="")
            else:
                message = str(exc)
                if billing_alert.prepay_depleted(message) or message == billing_alert.MESSAGE:
                    # Erro 402 do Google: mensagem em português e selo na conta.
                    message = billing_alert.MESSAGE
                    try:
                        billing_alert.mark(client, OWNER_UID, now())
                    except Exception:
                        pass
                update(status="failed", stage="Falha", error=message[:400], finished_at=now())
        except Exception:
            pass
        # Manifesto também em falhas: mostra até onde a execução chegou.
        if MANIFEST is not None:
            try:
                with tempfile.TemporaryDirectory(prefix="manifest_") as tmp:
                    publish_manifest(Path(tmp), "cancelled" if cancelled else "failed", str(exc))
                ref.update({"files": firestore.ArrayUnion(["manifest"])})
            except Exception as manifest_error:
                print("Manifesto de falha indisponível:", repr(manifest_error), flush=True)
        if not cancelled:
            raise
