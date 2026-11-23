"""Executa o pipeline original em uma tarefa Cloud Run Jobs.

Nenhum manuscrito depende do disco efêmero da instância após a execução.
"""
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import firestore, storage
from agent_progress import current_stage, inspect_agents

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
BUCKET = os.environ["RESEARCH_BUCKET"]
RESEARCH_ID = os.environ["RESEARCH_ID"]
OWNER_UID = os.environ["RESEARCH_OWNER_UID"]
BASE = Path("/app/orchestra")

client = firestore.Client(project=PROJECT)
storage_client = storage.Client(project=PROJECT)
bucket = storage_client.bucket(BUCKET)
ref = client.collection("research_jobs").document(RESEARCH_ID)
prefix = f"research/{OWNER_UID}/{RESEARCH_ID}"


def update(**fields):
    ref.update(fields)


def now():
    return datetime.now(timezone.utc).isoformat()


def put(local: Path, remote_name: str, mime: str):
    bucket.blob(f"{prefix}/output/{remote_name}").upload_from_filename(str(local), content_type=mime)


def main():
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("owner_uid") != OWNER_UID:
        raise ValueError("Pesquisa ou responsável inválidos")
    data = doc.to_dict()
    update(status="running", stage="Preparando arquivos de entrada", started_at=now())
    with tempfile.TemporaryDirectory(prefix="orchestra_") as tmp:
        root = Path(tmp)
        raw = root / "raw_materials"
        output = root / "output"
        raw.mkdir(); output.mkdir()
        for filename in ("idea_sparse.md", "experimental_log.md"):
            bucket.blob(f"{prefix}/input/{filename}").download_to_filename(str(raw / filename))
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
                        stderr=subprocess.STDOUT, timeout=10400, check=False
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
        latex_workdir = output / "latex_writeup"
        final_tex = output / "content_refinement_workdir" / "final_refined_paper.tex"
        if latex_workdir.is_dir() and final_tex.exists():
            assembled = root / "latex_source"
            shutil.copytree(latex_workdir, assembled)
            shutil.copy2(final_tex, assembled / "main.tex")
            zipfile = shutil.make_archive(str(root / "latex_source"), "zip", str(assembled))
            put(Path(zipfile), "latex_source.zip", "application/zip")
            files.append("latex")
        update(status="completed", stage="Concluído", agents=inspect_agents(output, bool(data["plotting"])), finished_at=now(), files=files)


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
        raise
