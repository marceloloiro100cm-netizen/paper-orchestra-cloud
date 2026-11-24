#!/usr/bin/env python3
"""Autoriza scriptorium.web.app na configuração de login Firebase do projeto.

Faz GET, acrescenta exclusivamente o domínio novo ao conjunto existente
e faz PATCH com updateMask=authorizedDomains, sem alterar provedores,
usuários, dados, tokens ou outros campos de autenticação.

Exige IAM próprio no projeto. Se não houver, falha de modo explícito.
"""
from __future__ import annotations

import json
import subprocess
from urllib import error, parse, request


PROJECT = "paperorchestra-mestrado"
NEW_DOMAIN = "scriptorium.web.app"
CONFIG_URL = f"https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config"


def access_token() -> str:
    proc = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return proc.stdout.strip()


def call(method: str, url: str, token: str, data: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/json",
               "x-goog-user-project": PROJECT}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=25) as result:
            response = json.load(result)
            if not isinstance(response, dict):
                raise RuntimeError("Resposta inesperada do Firebase Authentication")
            return response
    except error.HTTPError as exc:
        # Não imprimir o conteúdo retornado: o GET pode conter configurações privadas.
        raise RuntimeError(
            f"Firebase Authentication recusou {method} /config (HTTP {exc.code}); "
            "verifique as permissões IAM para consultar/alterar domínios autorizados."
        ) from None


def main() -> None:
    token = access_token()
    config = call("GET", CONFIG_URL, token)
    domains = config.get("authorizedDomains", [])
    if not isinstance(domains, list) or not all(isinstance(item, str) for item in domains):
        raise RuntimeError("Lista atual de domínios não retornada; nenhuma alteração realizada")
    if NEW_DOMAIN in domains:
        print("Domínio scriptorium.web.app já autorizado para login Google.")
        return

    # Falha fechada: não sobrescrever a lista de domínios se não houver confirmação
    # do domínio legado e da configuração original.
    legacy = "paperorchestra-mestrado.firebaseapp.com"
    if legacy not in domains:
        raise RuntimeError("Domínio de autenticação original ausente; alteração cancelada")

    # Field mask limita a atualização a este único campo; preserva o conteúdo anterior.
    updated = domains + [NEW_DOMAIN]
    url = CONFIG_URL + "?" + parse.urlencode({"updateMask": "authorizedDomains"})
    call("PATCH", url, token, {"authorizedDomains": updated})
    verified = call("GET", CONFIG_URL, token).get("authorizedDomains", [])
    if NEW_DOMAIN not in verified or not set(domains).issubset(set(verified)):
        raise RuntimeError("A autorização do novo domínio não foi confirmada; revisar IAM")

    print("CONFIRMADO: scriptorium.web.app autorizado no Firebase Authentication.")
    print("Domínios existentes preservados; nenhum usuário ou método de login alterado.")


if __name__ == "__main__":
    main()
