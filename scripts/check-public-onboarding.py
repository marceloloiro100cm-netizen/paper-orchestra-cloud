#!/usr/bin/env python3
"""Sonda pública de implantação (SEM logins, tokens nem dados pessoais).

Um /api/health=200 não garante que a API multiusuário esteja publicada.
Verificamos a versão do commit e as rotas autenticadas retornando 401
para requisições anônimas. Nunca cria convites nem pesquisas.

Uso no CI de revisão: --diagnostic
Uso no deploy de produção: --expected-release "$GITHUB_SHA"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from urllib import error, request

BASE = "https://scriptoriummpie.web.app"
EXPECTED_ROUTES = (
    ("GET", "/api/account/access"),
    ("GET", "/api/admin/access-requests"),
    ("POST", "/api/account/request-access"),
    ("GET", "/api/jobs"),
    ("GET", "/api/library/items"),
)


def fetch(method: str, path: str) -> tuple[int, dict]:
    req = request.Request(
        BASE + path, method=method,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with request.urlopen(req, timeout=18) as response:
            status = response.status
            body = response.read(10000)
            content_type = response.headers.get("Content-Type", "")
    except error.HTTPError as exc:
        status = exc.code
        body = exc.read(10000)
        content_type = exc.headers.get("Content-Type", "")
    except (error.URLError, TimeoutError, OSError) as exc:
        print(f"{method} {path}: ERRO DE CONEXÃO ({type(exc).__name__})")
        return 0, {}
    if "application/json" not in content_type.lower():
        print(f"{method} {path}: HTTP {status}, tipo inesperado ({content_type})")
        return status, {}
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        data = {}
    print(f"{method} {path}: HTTP {status} JSON")
    return status, data if isinstance(data, dict) else {}


def check_once(expected_release: str | None = None) -> bool:
    code, health = fetch("GET", "/api/health")
    healthy = code == 200 and health.get("ok") is True
    release = str(health.get("release_sha") or "")
    if healthy:
        print("API saudável; release=" + (release[:12] if release else "não identificada"))
    if expected_release and release != expected_release:
        print("ERRO: API não corresponde ao commit implantado.")
        healthy = False
    for method, path in EXPECTED_ROUTES:
        code, _ = fetch(method, path)
        if code != 401:
            print(f"ERRO: rota {path} não respondeu 401 sem credencial.")
            healthy = False
    return healthy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true",
                        help="Mostra estado publicado sem bloquear testes de PR.")
    parser.add_argument("--expected-release", default="")
    parser.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()
    if not args.diagnostic and not args.expected_release:
        parser.error("Informe --expected-release para validação obrigatória.")
    for attempt in range(1, max(1, args.attempts) + 1):
        print(f"Verificação {attempt}/{max(1, args.attempts)}")
        if check_once(args.expected_release or None):
            print("PASSOU: API esperada e rotas protegidas estão publicadas.")
            return 0
        if attempt < args.attempts:
            time.sleep(10)
    if args.diagnostic:
        print("DIAGNÓSTICO: publicação incompleta ou desatualizada; nenhum acesso foi concedido.")
        return 0
    print("FALHA: API pública não homologada.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
