"""Inspeção estática de arquivos enviados e quarentena (M13).

Origem: R27 (OWASP GenAI Security Project) e R45 (OWASP File Upload Cheat
Sheet); a lista de palavras-chave de PDF segue a ideia do pdfid (R46, Didier
Stevens), sem código copiado. Plano V2, módulo M13 "Segurança de documentos e
isolamento": "varredura de malware no upload e quarentena".

O que é verificado antes de o arquivo entrar na biblioteca:
- PDF: ações automáticas e conteúdo ativo (/JavaScript, /JS, /Launch,
  /EmbeddedFile, /RichMedia, /XFA, /AA, /OpenAction com script, /SubmitForm),
  inclusive nomes ofuscados com #xx e dentro de fluxos compactados
  (FlateDecode, até um limite de descompressão), e PDF criptografado;
- DOCX: macros (vbaProject.bin), objetos OLE/ActiveX incorporados, campos DDE,
  altChunk, modelo ou relação externa (injeção de modelo), caminhos com "..";
- BIB, RIS e TXT: bytes nulos e conteúdo binário.

Achado de risco alto => quarentena: o original vai para quarantine/{uid}/...,
fora da biblioteca, não pode ser usado em pesquisas e aparece para o dono com o
motivo. Achados informativos são só registrados.

Limite honesto: é verificação estática; NÃO é antivírus (não há assinaturas
de malware). O isolamento do worker (documentos tratados como dados, nunca
executados) continua sendo a principal proteção.
"""
from __future__ import annotations

import re
import zlib
from io import BytesIO
from zipfile import BadZipFile, ZipFile

VERSION = "upload-guard-1"
# Descompressão limitada: bombas de compressão não derrubam a API.
MAX_INFLATED_TOTAL = 40 * 1024 * 1024
MAX_STREAMS = 3000

PDF_HIGH = {
    "/JavaScript": "script JavaScript", "/JS": "script JavaScript",
    "/Launch": "ação que abre programa ou arquivo", "/EmbeddedFile": "arquivo incorporado",
    "/RichMedia": "mídia Flash/RichMedia", "/XFA": "formulário XFA dinâmico",
    "/SubmitForm": "envio automático de formulário", "/ImportData": "importação de dados externos",
}
PDF_INFO = {"/OpenAction": "ação ao abrir", "/AA": "ação automática em eventos",
            "/AcroForm": "formulário", "/URI": "links externos"}
RISKY_EXTERNAL = {"attachedTemplate", "oleObject", "frame", "subDocument", "package"}
_NAME = re.compile(rb"/[A-Za-z0-9#]+")
_HEX = re.compile(rb"#([0-9A-Fa-f]{2})")
_STREAM = re.compile(rb"stream\r?\n")


def _normalize_name(raw: bytes) -> str:
    return _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), raw).decode("latin-1")


def _pdf_names(blob: bytes) -> set[str]:
    return {_normalize_name(m.group()) for m in _NAME.finditer(blob)}


def _inflated_streams(data: bytes):
    """Fluxos FlateDecode descompactados, até MAX_INFLATED_TOTAL bytes no total."""
    total, count = 0, 0
    for match in _STREAM.finditer(data):
        if count >= MAX_STREAMS or total >= MAX_INFLATED_TOTAL:
            break
        start = match.end()
        end = data.find(b"endstream", start)
        if end == -1:
            break
        count += 1
        decompressor = zlib.decompressobj()
        try:
            chunk = decompressor.decompress(data[start:end], MAX_INFLATED_TOTAL - total)
        except zlib.error:
            continue
        total += len(chunk)
        yield chunk


def inspect_pdf(data: bytes) -> list[dict]:
    names = _pdf_names(data)
    for chunk in _inflated_streams(data):
        names |= _pdf_names(chunk)
    findings = []
    for name, label in PDF_HIGH.items():
        if name in names:
            findings.append({"severity": "alta", "code": "pdf" + name.replace("/", "_").lower(),
                             "detail": f"PDF contém {label} ({name})."})
    if "/Encrypt" in names:
        findings.append({"severity": "alta", "code": "pdf_encrypted",
                         "detail": "PDF criptografado: o conteúdo não pode ser inspecionado nem lido."})
    for name, label in PDF_INFO.items():
        if name in names:
            findings.append({"severity": "info", "code": "pdf" + name.replace("/", "_").lower(),
                             "detail": f"PDF contém {label} ({name})."})
    return findings


def inspect_docx(data: bytes) -> list[dict]:
    findings = []
    try:
        with ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            lowered = [n.lower() for n in names]
            if any(".." in n.replace("\\", "/").split("/") or n.startswith("/") for n in names):
                findings.append({"severity": "alta", "code": "docx_path_traversal",
                                 "detail": "Caminho interno suspeito (..) no pacote DOCX."})
            if any(n.endswith("vbaproject.bin") for n in lowered):
                findings.append({"severity": "alta", "code": "docx_macro",
                                 "detail": "DOCX contém macros VBA (vbaProject.bin)."})
            if any(n.startswith(("word/embeddings/", "word/activex/")) for n in lowered):
                findings.append({"severity": "alta", "code": "docx_embedded_object",
                                 "detail": "DOCX contém objeto OLE ou ActiveX incorporado."})
            for name in names:
                if not name.lower().endswith((".rels", ".xml")):
                    continue
                info = archive.getinfo(name)
                if info.file_size > 20 * 1024 * 1024:
                    continue
                text = archive.read(name).decode("utf-8", errors="replace")
                if name.lower().endswith(".rels"):
                    for element in re.findall(r"<Relationship\b[^>]*>", text):
                        if 'TargetMode="External"' not in element:
                            continue
                        rel_type = (re.search(r'Type="([^"]+)"', element) or [None, ""])[1]
                        target = (re.search(r'Target="([^"]+)"', element) or [None, ""])[1]
                        risky_type = rel_type.rsplit("/", 1)[-1] in RISKY_EXTERNAL
                        if risky_type or not re.match(r"(https?|mailto):", target, re.I):
                            findings.append({"severity": "alta", "code": "docx_external_template",
                                             "detail": "DOCX aponta para modelo, objeto ou recurso externo (injeção de modelo)."})
                            break
                elif re.search(r"\bDDE(AUTO)?\b", text):
                    findings.append({"severity": "alta", "code": "docx_dde",
                                     "detail": "DOCX contém campo DDE (execução de comando)."})
                if name.lower().endswith(".xml") and "altChunk" in text:
                    findings.append({"severity": "info", "code": "docx_altchunk",
                                     "detail": "DOCX incorpora outro documento (altChunk)."})
    except BadZipFile:
        findings.append({"severity": "alta", "code": "docx_invalid", "detail": "Pacote DOCX inválido."})
    unique = {f["code"]: f for f in findings}
    return list(unique.values())


def inspect_text(data: bytes) -> list[dict]:
    sample = data[:200_000]
    if b"\x00" in sample:
        return [{"severity": "alta", "code": "text_binary", "detail": "Arquivo de texto com bytes nulos (conteúdo binário)."}]
    controls = sum(1 for b in sample if b < 9 or 13 < b < 32)
    if sample and controls / len(sample) > 0.01:
        return [{"severity": "alta", "code": "text_control_chars",
                 "detail": "Arquivo de texto com muitos caracteres de controle."}]
    return []


def inspect(data: bytes, suffix: str) -> dict:
    if suffix == ".pdf":
        findings = inspect_pdf(data)
    elif suffix == ".docx":
        findings = inspect_docx(data)
    else:
        findings = inspect_text(data)
    high = [f for f in findings if f["severity"] == "alta"]
    return {"version": VERSION, "verdict": "quarantine" if high else "clean",
            "findings": findings, "upstream_ids": ["R27", "R45", "R46"],
            "note": "Verificação estática; não substitui antivírus."}
