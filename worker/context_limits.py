"""Tamanho do contexto das fontes por pesquisa (padrão ou ampliado).

Origem: R01. Pedido do responsável em 25/11/2026, depois do confronto com o
artigo da revista Tear: a revisão sistemática tinha 14 estudos e o limite era
8 fontes e 75 mil caracteres. O modo ampliado aumenta fontes e caracteres
(mais tokens por chamada, logo mais custo na chave pessoal).
A API tem a mesma tabela em api/library.py (tests/test_bib_integrity.py confere).
"""
CONTEXT_LIMITS = {
    "padrao": {"max_sources": 8, "per_source_chars": 20_000, "total_chars": 75_000},
    "ampliado": {"max_sources": 20, "per_source_chars": 30_000, "total_chars": 300_000},
}


def limits_for(record: dict) -> dict:
    return CONTEXT_LIMITS.get((record or {}).get("context_size") or "padrao", CONTEXT_LIMITS["padrao"])
