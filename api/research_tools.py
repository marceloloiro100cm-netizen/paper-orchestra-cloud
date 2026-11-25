"""Ferramentas sobre uma pesquisa existente (plano V2, onda 6).

Origem: R01 (Scriptorium), salvo indicação. Rotas:
- POST /api/jobs/{id}/cancel                 M15: cancelamento pelo navegador;
- POST /api/jobs/{id}/editorial-recheck      M07: reavaliar retratações (R08, R11);
- GET  /api/jobs/{id}/evidence-view/{chunk}  M02: página do PDF com o trecho
       destacado (R37 PyMuPDF renderiza a página no servidor);
- GET  /api/jobs/{id}/export/{kind}          M08: matriz com revisões humanas;
       M27: CSL-JSON e lista ABNT (R23, R24, R38); M07: resultado da reavaliação.

Todas exigem o dono da pesquisa (get_research). Nenhuma rota recebe caminho,
página ou coordenadas livres do navegador: o trecho é procurado no relatório
de evidências da própria pesquisa e a fonte precisa estar entre as dela.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from csl_export import VERSION as CSL_VERSION, abnt_list, bibtex_to_csl
from job_state import ACTIVE_STATUSES
from reviews import list_reviews

RENDER_DPI = 110
MAX_RENDER_PAGES = 400
RECHECK_COOLDOWN = timedelta(minutes=30)
CHUNK_ID = re.compile(r"[0-9a-f]{12}-\d{4}-[0-9a-f]{8}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(bucket, path: str) -> dict:
    blob = bucket.blob(path)
    if not blob.exists():
        raise HTTPException(404, "Relatório indisponível para esta pesquisa.")
    return json.loads(blob.download_as_bytes().decode("utf-8"))


def find_chunk(report: dict, chunk_id: str) -> dict | None:
    """Procura o trecho nas citações e na matriz do relatório de evidências."""
    quotes = report.get("quotes") or {}
    for ref in list(quotes.get("quotes") or []) + list(quotes.get("pointers") or []):
        if isinstance(ref, dict) and ref.get("chunk_id") == chunk_id:
            return ref
    for row in (report.get("matrix") or {}).get("claims", []):
        for evidence in row.get("evidence") or []:
            if evidence.get("chunk_id") == chunk_id:
                return evidence
    return None


def render_highlight(pdf_bytes: bytes, locations: list[dict], page: int | None) -> tuple[bytes, int, list[int]]:
    """PNG da página com as áreas do trecho destacadas; devolve (png, página, páginas)."""
    from pdf_render import fitz  # PyMuPDF (R37)
    pages = sorted({int(loc["page"]) for loc in locations if loc.get("page")})
    if not pages:
        raise HTTPException(404, "Este trecho não tem página no PDF (DOCX/TXT não têm coordenadas).")
    target = page if page in pages else pages[0]
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if target > min(doc.page_count, MAX_RENDER_PAGES):
            raise HTTPException(404, "Página fora do documento.")
        pdf_page = doc[target - 1]
        width = pdf_page.cropbox.width or pdf_page.rect.width
        height = pdf_page.cropbox.height or pdf_page.rect.height
        for loc in locations:
            if loc.get("page") != target or not loc.get("bbox"):
                continue
            x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in loc["bbox"])
            rect = fitz.Rect(x0 * width, y0 * height, x1 * width, y1 * height)
            pdf_page.draw_rect(rect, color=(0.85, 0.45, 0.0), fill=(1.0, 0.85, 0.2),
                               fill_opacity=0.35, width=1.2, overlay=True)
        png = pdf_page.get_pixmap(dpi=RENDER_DPI, alpha=False).tobytes("png")
    return png, target, pages


def reviewed_csv(csv_text: str, latest: dict) -> str:
    """M08: a matriz original + a decisão humana mais recente de cada afirmação."""
    reader = csv.reader(io.StringIO(csv_text.lstrip("﻿")))
    out = io.StringIO()
    writer = csv.writer(out)
    header = next(reader, None)
    if header is None:
        return ""
    writer.writerow(header + ["revisao_humana", "nota_da_revisao", "revisado_em"])
    for row in reader:
        review = latest.get(f"claim:{row[0]}") if row else None
        writer.writerow(row + ([review.get("decision", ""), review.get("note", ""), review.get("at", "")]
                               if review else ["", "", ""]))
    return out.getvalue()


def make_research_tools_router(db, bucket, verify_user: Callable, get_research: Callable,
                               start_job: Callable):
    router = APIRouter(prefix="/api/jobs", tags=["pesquisa"])
    dependency = Depends(verify_user)

    @router.post("/{job_id}/cancel")
    def cancel(job_id: str, user: dict = dependency):
        """M15: pede o cancelamento; o worker para o motor no próximo ciclo (até ~15 s)."""
        record = get_research(job_id, user)
        if record.get("status") not in ACTIVE_STATUSES:
            raise HTTPException(409, "Esta pesquisa não está em execução.")
        now = utc_now().isoformat()
        fields = {"cancel_requested": True, "cancel_requested_at": now,
                  "stage": "Cancelamento solicitado"}
        db.collection("research_jobs").document(job_id).update(fields)
        return {"id": job_id, "status": record.get("status"), "cancel_requested": True}

    @router.post("/{job_id}/editorial-recheck", status_code=202)
    def editorial_recheck(job_id: str, user: dict = dependency):
        """M07: reconsulta retratações e avisos das referências com DOI. Sem IA."""
        record = get_research(job_id, user)
        if record.get("status") != "completed" or "references" not in (record.get("files") or []):
            raise HTTPException(409, "Só pesquisas concluídas com conferência de referências.")
        current = record.get("editorial_recheck") or {}
        requested = current.get("requested_at")
        if current.get("status") in ("queued", "running") and requested:
            try:
                if utc_now() - datetime.fromisoformat(requested) < RECHECK_COOLDOWN:
                    raise HTTPException(409, "A reavaliação já está em andamento.")
            except ValueError:
                pass
        db.collection("research_jobs").document(job_id).update(
            {"editorial_recheck": {"status": "queued", "requested_at": utc_now().isoformat()}})
        try:
            start_job(job_id, user["uid"], "editorial_recheck")
        except Exception:
            db.collection("research_jobs").document(job_id).update(
                {"editorial_recheck": {"status": "failed", "error": "Falha ao iniciar a reavaliação"}})
            raise HTTPException(503, "Não foi possível iniciar a reavaliação.") from None
        return {"id": job_id, "editorial_recheck": "queued"}

    @router.get("/{job_id}/evidence-view/{chunk_id}")
    def evidence_view(job_id: str, chunk_id: str, page: int | None = Query(default=None, ge=1, le=5000),
                      user: dict = dependency):
        """M02: abre a página do PDF com as áreas do trecho destacadas."""
        if not CHUNK_ID.fullmatch(chunk_id):
            raise HTTPException(404, "Trecho não encontrado.")
        record = get_research(job_id, user)
        if record.get("status") != "completed":
            raise HTTPException(409, "Pesquisa ainda não concluída.")
        report = _read_json(bucket, f"research/{user['uid']}/{job_id}/output/evidence_report.json")
        found = find_chunk(report, chunk_id)
        if not found:
            raise HTTPException(404, "Trecho não encontrado nesta pesquisa.")
        source = next((s for s in record.get("sources") or [] if s.get("id") == found.get("source_id")), None)
        if not source or source.get("format") != "pdf":
            raise HTTPException(404, "O trecho não vem de um PDF desta pesquisa.")
        path = str(source.get("object_path", ""))
        if not path.startswith(f"library/{user['uid']}/{source['id']}/"):
            raise HTTPException(404, "Fonte indisponível.")
        blob = bucket.blob(path)
        if not blob.exists():
            raise HTTPException(404, "O PDF original não está mais disponível.")
        png, shown, pages = render_highlight(blob.download_as_bytes(), found.get("locations") or [], page)
        return Response(content=png, media_type="image/png", headers={
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
            "X-Scriptorium-Page": str(shown), "X-Scriptorium-Pages": ",".join(map(str, pages)),
        })

    @router.get("/{job_id}/export/{kind}")
    def export(job_id: str, kind: Literal["evidence_reviewed_csv", "csl_json", "abnt", "editorial_recheck"],
               user: dict = dependency):
        record = get_research(job_id, user)
        if record.get("status") != "completed":
            raise HTTPException(409, "Pesquisa ainda não concluída.")
        base = f"research/{user['uid']}/{job_id}/output"
        if kind == "evidence_reviewed_csv":
            blob = bucket.blob(f"{base}/evidence_matrix.csv")
            if not blob.exists():
                raise HTTPException(404, "Matriz de evidências indisponível.")
            latest = list_reviews(db, job_id, user["uid"])["latest"]
            body = "﻿" + reviewed_csv(blob.download_as_bytes().decode("utf-8-sig"), latest)
            return Response(content=body.encode("utf-8"), media_type="text/csv; charset=utf-8", headers={
                "Content-Disposition": 'attachment; filename="matriz_evidencias_revisada.csv"',
                "Cache-Control": "no-store"})
        if kind == "editorial_recheck":
            data = _read_json(bucket, f"{base}/editorial_recheck.json")
            return Response(content=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                            media_type="application/json", headers={"Cache-Control": "no-store"})
        blob = bucket.blob(f"{base}/references.bib")
        if not blob.exists():
            raise HTTPException(404, "BibTeX indisponível (pesquisas antigas não guardavam o arquivo separado).")
        items = bibtex_to_csl(blob.download_as_bytes().decode("utf-8", errors="replace"))
        if kind == "csl_json":
            return Response(content=json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8"),
                            media_type="application/vnd.citationstyles.csl+json", headers={
                                "Content-Disposition": 'attachment; filename="referencias.csl.json"',
                                "X-Scriptorium-Export": CSL_VERSION, "Cache-Control": "no-store"})
        return Response(content=abnt_list(items).encode("utf-8"), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="referencias_abnt.md"',
                                 "X-Scriptorium-Export": CSL_VERSION, "Cache-Control": "no-store"})

    return router
