"""Proteção do texto extraído de documentos anexados pelo pesquisador (M13).

Origem: R27 (OWASP GenAI Security Project, risco LLM01 "prompt injection").
Plano: Scriptorium V2, módulo M13 "Segurança de documentos e isolamento".

O texto de PDFs, DOCX e afins é DADO não confiável. Antes de entrar no
contexto dos agentes, este módulo:
1. remove caracteres invisíveis e de controle (texto oculto, inversão bidi);
2. neutraliza marcas que imitam o delimitador <fonte_usuario>, impedindo que um
   documento "feche" o bloco de fonte e escreva fora dele;
3. sinaliza frases típicas de instrução embutida, sem bloquear o documento.

Somente códigos e contagens vão para o manifesto: o texto privado nunca é
copiado para logs.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

GUARD_VERSION = "document_guard/1"

# Largura zero, marcas e isolamentos bidirecionais, hífen suave, BOM.
INVISIBLE = re.compile("[­​-‏‪-‮⁠-⁤⁦-⁩﻿]")
# Controles ASCII, exceto tab, quebra de linha e retorno de carro.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Qualquer abertura ou fechamento que imite o delimitador do Scriptorium.
DELIMITER = re.compile(r"<\s*/?\s*fonte_usuario\b[^>]*>", re.IGNORECASE)
# Não pode conter "<" nem o nome do delimitador, senão viraria outra marca.
NEUTRALIZED = "[marca de delimitador removida pelo sistema]"

SUSPICIOUS = {
    "ignore_instructions": re.compile(
        r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|all|earlier)\b.{0,20}\binstructions?\b"
        r"|\b(ignore|desconsidere|esque[cç]a)\b.{0,40}\binstru[cç][oõ]es\b.{0,30}\b(anteriores|acima|pr[eé]vias)\b",
        re.IGNORECASE | re.DOTALL),
    "role_override": re.compile(
        r"\byou are now\b|\bfrom now on,? you\b|\ba partir de agora,? voc[eê]\b|\bvoc[eê] agora [eé]\b",
        re.IGNORECASE),
    "system_prompt_reference": re.compile(
        r"\bsystem prompt\b|\bprompt d[eo] sistema\b|\bdeveloper message\b|\bmensagem do desenvolvedor\b",
        re.IGNORECASE),
    "chat_template_tokens": re.compile(
        r"<\|im_start\|>|<\|im_end\|>|\[/?INST\]|<<SYS>>|<\|system\|>|<\|assistant\|>|<start_of_turn>",
        re.IGNORECASE),
    "concealment_request": re.compile(
        r"\bdo not (tell|inform|reveal to) the user\b|\bn[aã]o (conte|informe|revele) ao usu[aá]rio\b",
        re.IGNORECASE),
    "exfiltration_request": re.compile(
        r"\b(send|post|upload|envie|publique)\b.{0,40}\b(api[_ -]?key|token|secret|senha|password|credencia)",
        re.IGNORECASE | re.DOTALL),
}


@dataclass
class GuardResult:
    text: str
    removed_invisible: int = 0
    removed_control: int = 0
    neutralized_delimiters: int = 0
    flags: list[dict] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        if self.neutralized_delimiters or self.flags:
            return "attention"
        if self.removed_invisible > 20:
            return "attention"
        return "none_detected"

    def summary(self) -> dict:
        """Metadados seguros para o manifesto (sem trechos do documento)."""
        return {
            "guard_version": GUARD_VERSION,
            "risk_level": self.risk_level,
            "risk_flags": self.flags,
            "removed_invisible_characters": self.removed_invisible,
            "removed_control_characters": self.removed_control,
            "neutralized_delimiters": self.neutralized_delimiters,
        }


def guard_text(text: str) -> GuardResult:
    text = unicodedata.normalize("NFC", text or "")
    text, invisible = INVISIBLE.subn("", text)
    text, control = CONTROL.subn("", text)
    text, delimiters = DELIMITER.subn(NEUTRALIZED, text)
    flags = []
    for code, pattern in SUSPICIOUS.items():
        count = len(pattern.findall(text))
        if count:
            flags.append({"code": code, "count": count})
    return GuardResult(text, invisible, control, delimiters, flags)
