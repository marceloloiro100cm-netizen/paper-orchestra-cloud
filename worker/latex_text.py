"""Conversão simples de LaTeX em texto para auditoria (sem executar nada).

Origem: R01. Usado por quote_verification.py (M05) e evidence_matrix.py (M08).
Não é um parser completo de LaTeX: remove preâmbulo, comentários e comandos de
formatação, preservando as chaves de citação para a matriz de evidências.
"""
from __future__ import annotations

import re
import unicodedata

CITE = re.compile(r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|autocite|parencite|textcite)\*?"
                  r"(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}")


def body_of(tex: str) -> str:
    match = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|$)", tex, re.S)
    body = match.group(1) if match else tex
    body = re.sub(r"(?<!\\)%.*", "", body)  # comentários
    body = re.sub(r"\\begin\{(figure|table|tabular|equation|align|thebibliography)\*?\}.*?"
                  r"\\end\{\1\*?\}", " ", body, flags=re.S)
    body = re.sub(r"\\bibliography\{[^}]*\}|\\bibliographystyle\{[^}]*\}", " ", body)
    return body


def strip_commands(text: str, keep_cites: bool = False) -> str:
    if not keep_cites:
        text = CITE.sub(" ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph|chapter)\*?\{([^{}]*)\}", r"\1. ", text)
    text = re.sub(r"\\(?:textit|textbf|emph|enquote|textsc|texttt|underline)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:label|ref|eqref|url|footnote)\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", text)
    text = text.replace("~", " ").replace("``", '"').replace("''", '"').replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def fold(text: str) -> str:
    """Minúsculas, sem acentos e só letras/números separados por espaço."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))
