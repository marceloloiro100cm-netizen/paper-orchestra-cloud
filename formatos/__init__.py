"""Registro de formatos (normas) do Scriptorium.

Cada formato mora numa subpasta desta pasta, com um `formato.json` e os
arquivos que ele cita (preâmbulo LaTeX, regras para a IA, estilo CSL).
A API, o worker e o site leem só daqui; para criar uma norma nova basta
criar a pasta, sem mexer no código (passo a passo em formatos/README.md).

Só biblioteca padrão: o mesmo pacote é copiado para as imagens da API e do
worker no deploy (ver .github/workflows/deploy-services.yml).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent
PADRAO = "abnt-artigo"
TIPOS = ("artigo", "dissertacao", "tcc", "revisao_sistematica")
STATUS = ("estavel", "experimental")
MOTORES = ("bibtex", "biber")
ID_VALIDO = re.compile(r"[a-z0-9][a-z0-9-]{1,40}")
OBRIGATORIOS = ("id", "nome", "familia", "descricao", "status", "tipos", "no_site", "estrutura", "citacao", "latex")
# Placeholders do preâmbulo: %(nome)s. Os demais "%" do arquivo são comentários LaTeX e ficam intactos.
PLACEHOLDER = re.compile(r"%\((\w+)\)s")


class FormatoInvalido(ValueError):
    pass


def _ler_json(pasta: Path) -> dict:
    dados = json.loads((pasta / "formato.json").read_text(encoding="utf-8"))
    faltando = [c for c in OBRIGATORIOS if c not in dados]
    if faltando:
        raise FormatoInvalido(f"{pasta.name}: faltam campos {', '.join(faltando)}")
    if dados["id"] != pasta.name or not ID_VALIDO.fullmatch(dados["id"]):
        raise FormatoInvalido(f"{pasta.name}: o id precisa ser igual ao nome da pasta (minúsculas e hífens)")
    if dados["status"] not in STATUS:
        raise FormatoInvalido(f"{pasta.name}: status deve ser um de {STATUS}")
    if not dados["tipos"] or any(t not in TIPOS for t in dados["tipos"]):
        raise FormatoInvalido(f"{pasta.name}: tipos aceitos são {TIPOS}")
    est = dados["estrutura"]
    if not est.get("secoes") or not re.fullmatch(r"[a-z]+", est.get("resumo", "")):
        raise FormatoInvalido(f"{pasta.name}: estrutura precisa de secoes e do ambiente de resumo")
    lat = dados["latex"]
    if lat.get("bibliografia") not in MOTORES:
        raise FormatoInvalido(f"{pasta.name}: latex.bibliografia deve ser {MOTORES}")
    for chave in ("preambulo",):
        if not (PASTA / lat.get(chave, "")).is_file():
            raise FormatoInvalido(f"{pasta.name}: arquivo latex.{chave} não encontrado")
    for chave in ("regras", "csl"):
        if dados.get(chave) and not (pasta / dados[chave]).is_file():
            raise FormatoInvalido(f"{pasta.name}: arquivo {chave} não encontrado")
    return dados


@lru_cache(maxsize=1)
def _registro() -> dict[str, dict]:
    formatos = {}
    for pasta in sorted(p for p in PASTA.iterdir() if p.is_dir() and (p / "formato.json").is_file()):
        dados = _ler_json(pasta)
        formatos[dados["id"]] = dados
    if PADRAO not in formatos:
        raise FormatoInvalido(f"O formato padrão {PADRAO} precisa existir.")
    return formatos


def ids() -> tuple[str, ...]:
    return tuple(_registro())


def existe(formato_id: str | None) -> bool:
    return formato_id in _registro()


def obter(formato_id: str | None) -> dict:
    """Formato pelo id; id desconhecido ou vazio cai no padrão (ABNT artigo)."""
    reg = _registro()
    return reg.get(formato_id or PADRAO) or reg[PADRAO]


def aceita_tipo(formato_id: str, tipo: str) -> bool:
    return existe(formato_id) and tipo in obter(formato_id)["tipos"]


def ajustar_ao_tipo(formato_id: str, tipo: str) -> str:
    """Troca para o formato da mesma família que atende o tipo (ex.: ABNT artigo -> ABNT dissertação)."""
    if aceita_tipo(formato_id, tipo):
        return formato_id
    familia = obter(formato_id)["familia"] if existe(formato_id) else obter(PADRAO)["familia"]
    for fid, dados in _registro().items():
        if dados["familia"] == familia and tipo in dados["tipos"]:
            return fid
    return formato_id


def regras(formato_id: str) -> str:
    """Texto das regras da norma, entregue à IA em cada etapa."""
    dados = obter(formato_id)
    if not dados.get("regras"):
        return ""
    return (PASTA / dados["id"] / dados["regras"]).read_text(encoding="utf-8").strip()


def caminho_csl(formato_id: str) -> Path | None:
    dados = obter(formato_id)
    return (PASTA / dados["id"] / dados["csl"]) if dados.get("csl") else None


def preambulo(formato_id: str, valores: dict) -> str:
    """Preâmbulo LaTeX com os placeholders %(nome)s trocados pelos valores."""
    texto = (PASTA / obter(formato_id)["latex"]["preambulo"]).read_text(encoding="utf-8")
    return PLACEHOLDER.sub(lambda m: str(valores.get(m.group(1), "")), texto)


def preencher(texto: str, valores: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(valores.get(m.group(1), "")), texto or "")


def textos(formato_id: str, idioma: str) -> dict:
    """Rótulos fixos do PDF (capa, campos a preencher) no idioma do projeto."""
    por_idioma = obter(formato_id)["latex"].get("textos") or {}
    return dict(por_idioma.get(idioma) or por_idioma.get("pt-BR") or {})


def catalogo() -> list[dict]:
    """Versão pública para o site: só o que a tela precisa mostrar."""
    saida = []
    for dados in _registro().values():
        if not dados.get("no_site"):
            continue
        saida.append({
            "id": dados["id"], "nome": dados["nome"], "familia": dados["familia"],
            "descricao": dados["descricao"], "status": dados["status"], "tipos": list(dados["tipos"]),
            "areas": list(dados.get("areas") or []), "tem_csl": bool(dados.get("csl")),
            "exemplo_citacao": dados["citacao"].get("exemplos", {}),
        })
    return saida
