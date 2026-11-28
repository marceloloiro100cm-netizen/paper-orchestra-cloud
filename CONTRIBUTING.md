# Como contribuir com o Scriptorium

Obrigado pelo interesse! O Scriptorium é um produto técnico-tecnológico de mestrado e é código aberto (AGPL-3.0). Correções, novas normas de formatação, melhorias de texto e relatos de uso são bem-vindos.

## Antes de começar

- Leia o [README](README.md) e a [visão da arquitetura](docs/ARQUITETURA.md).
- Para dúvidas e ideias, abra uma [issue](../../issues/new/choose). Para falhas de segurança, **não** abra issue: siga o [SECURITY.md](SECURITY.md).
- Ao participar, você concorda com o [Código de Conduta](CODE_OF_CONDUCT.md).

## Preparar o ambiente

Requisitos: Python 3.11+, Node.js 20+ (só para checar a sintaxe do site) e Git.

```bash
git clone https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud.git
cd paper-orchestra-cloud
python -m pip install requests fastapi google-api-core "PyMuPDF>=2.1,<3" "numpy>=1.26,<3" "mcp>=2.3,<3"
python -m unittest discover -s tests -v
```

Os testes rodam sem rede, sem chaves e sem custo: Firestore, Storage e modelos são simulados. Para rodar a API ou o worker de verdade é preciso um projeto Google Cloud próprio (ver [docs/IMPLANTACAO.md](docs/IMPLANTACAO.md)).

## Fluxo de trabalho

1. Crie uma branch a partir de `main` com um prefixo que diga o tipo da mudança:
   `feat/…` (recurso), `fix/…` (correção), `docs/…`, `ci/…`, `chore/…` (manutenção), `test/…`.
2. Faça commits pequenos no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português:
   `feat(biblioteca): importa RIS com várias obras`, `fix(guia): …`.
3. Antes de abrir o PR, rode:
   ```bash
   python -m compileall -q api worker
   python -m unittest discover -s tests
   python scripts/upstreams.py check
   node --check public/app.js
   ```
4. Abra o PR para `main` e preencha o modelo. A `main` é protegida: nada entra sem PR, e o check `static-checks` (CI · Verificações) precisa passar.
5. Depois do merge, o deploy é automático (ver [docs/WORKFLOWS.md](docs/WORKFLOWS.md)).

## Onde mexer

| Quero… | Pasta | Documento |
|---|---|---|
| criar ou ajustar uma norma (Vancouver, IEEE, norma de revista) | `formatos/` | [formatos/README.md](formatos/README.md) |
| mudar uma tela do site | `public/` | [docs/ARQUITETURA.md](docs/ARQUITETURA.md) |
| mudar uma etapa do fluxo com a IA (MCP) | `api/mcp_*.py` | [docs/funcionalidades/MCP.md](docs/funcionalidades/MCP.md) |
| mudar o processamento de fontes ou a compilação do PDF | `worker/` | [docs/ARQUITETURA.md](docs/ARQUITETURA.md) |
| adicionar uma dependência ou fonte externa | `docs/upstreams.json` | [docs/UPSTREAMS.md](docs/UPSTREAMS.md) |

## Regras do projeto

- **Nenhum dado real** em commits, issues, testes ou logs: manuscritos, fontes de pesquisa, e-mails, tokens e chaves ficam fora do repositório.
- **Toda dependência ou fonte externa nova** entra em `docs/upstreams.json` com licença e versão fixada; depois rode `python scripts/upstreams.py render`.
- **Testes:** um arquivo por módulo ou recurso, com o nome `tests/test_<assunto>.py`, sem rede e sem custo.
- **Textos do site** em português do Brasil, claros para quem não é da área de computação.
- **Não use IA para afirmar o que não foi verificado:** o Scriptorium existe para conferir; mudanças que relaxem uma conferência precisam explicar o motivo no PR.

## Licença das contribuições

Ao enviar uma contribuição, você concorda que ela seja distribuída sob a [AGPL-3.0](LICENSE), a mesma licença do projeto.
