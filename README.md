# Scriptorium MPIE

**Escrita acadêmica guiada, com as fontes do próprio pesquisador.**
Produto técnico-tecnológico do Mestrado Profissional em Informática na Educação (MPIE), IFRS *Campus* Porto Alegre.

- Site: https://scriptoriummpie.web.app
- Código: este repositório (licença [AGPL-3.0](LICENSE))

O Scriptorium ajuda estudantes a construir um artigo, TCC ou dissertação a partir das fontes que eles mesmos reuniram. A IA ajuda a ler e a escrever, mas o sistema confere cada entrega: as citações precisam existir nas fontes, as referências precisam ser confirmadas e o PDF final só sai quando tudo foi conferido.

> O Scriptorium não certifica resultados científicos. Revise referências, citações e afirmações antes de divulgar qualquer texto.

## O que ele faz

| Área | O que a pessoa encontra |
|---|---|
| **Guia de escrita** | Passo a passo em 8 etapas, do tema à submissão, para artigo ou projeto de pesquisa. Funciona sem login e salva no próprio aparelho. Ver [docs/GUIA.md](docs/GUIA.md). |
| **Biblioteca** | Upload de PDF, DOCX, BIB, RIS e TXT; importação do Zotero e de DOIs de acesso aberto; fichamento por página; duplicatas; resumo PRISMA; checagem de citações. |
| **Escrita com a sua IA (modo MCP)** | A IA que o pesquisador já usa (Claude, Gemini, ChatGPT…) conecta ao Scriptorium com um token pessoal. O Scriptorium entrega trechos das fontes, controla a ordem das etapas e confere cada entrega. Não chama modelo pago. Ver [docs/MCP.md](docs/MCP.md). |
| **Escrita com chave Gemini (modo API)** | O motor [PaperOrchestra](https://github.com/google-research/paper-orchestra) roda num Cloud Run Job, usando a chave Gemini pessoal de quem gera. |
| **Normas** | ABNT (artigo, TCC, dissertação) e APA 7. Cada norma é uma pasta em [`formatos/`](formatos/README.md): uma norma nova não exige código. |
| **Conferência** | Referências em três níveis (confirmada, sugerida, a conferir); busca de retratações na Crossref; citações literais procuradas nas fontes; escudo de auditoria; trava do PDF final. |
| **Orientação** | Link temporário para o orientador ler o andamento e comentar por etapa, sem criar conta; pacote de orientação em .zip. |
| **Pedagogia** | Tutor socrático, rubrica 0–15, modos de autonomia e declaração de uso de IA conforme a IN IFRS 16/2026. |
| **Exportação** | PDF (LaTeX), Word (.docx), matriz de evidências (CSV), referências em CSL-JSON e ABNT. |

## Como usar

1. Abra https://scriptoriummpie.web.app e entre com a conta Google. O acesso é por convite; quem não tem convite pode pedir pelo próprio site.
2. Envie suas fontes para a **Biblioteca**.
3. Em **Novo artigo**, escolha o tipo de trabalho, a norma e as fontes.
4. Conecte a sua IA em **Minha conta → Conectar sua IA** (modo MCP) ou cadastre uma chave Gemini (modo API).
5. Siga as etapas. Antes de compilar, confirme ou corrija as referências marcadas como "a conferir".

O **Guia de escrita** (botão no topo do site) pode ser usado antes de tudo isso, sem login.

## Arquitetura

```
Navegador ──► Firebase Hosting (public/) ──/api/**──► Cloud Run: API (api/, FastAPI)
                                                          │
                              Firebase Auth ◄─────────────┤ verifica o ID token e o convite
                              Firestore     ◄─────────────┤ projetos, biblioteca, tokens, estado
                              Cloud Storage ◄─────────────┤ fontes, PDFs, LaTeX, relatórios
                                                          ▼
                                            Cloud Run Job: worker (worker/, Python + LaTeX)
                                            compila PDFs, lê fontes, roda o PaperOrchestra
```

- **Projeto Google Cloud:** `paperorchestra-mestrado`, região `southamerica-east1` (São Paulo).
- **Firestore:** as regras negam todo acesso direto do navegador; só a API, com Admin SDK, lê e grava. Backups diários (7 dias) e semanais (12 semanas); proteção contra exclusão ativada.
- **Custos separados:** a infraestrutura é paga pelo projeto; tokens de IA saem sempre da chave Gemini pessoal de quem gera. Ver [docs/MULTIUSUARIO-BYOK.md](docs/MULTIUSUARIO-BYOK.md).
- O endereço antigo `paperorchestra-mestrado.web.app` redireciona para o atual ([`hosting-redirect/`](hosting-redirect)).

## Organização do repositório

```
api/               API FastAPI: autenticação, biblioteca, projetos MCP, orientação, exportações
worker/            Cloud Run Job: compilação LaTeX, leitura de fontes, PaperOrchestra, auditorias
formatos/          normas de formatação, uma pasta por norma
public/            site (index.html, app.js) e Guia de escrita (public/guia/)
tests/             testes unitários (python -m unittest discover -s tests)
scripts/           implantação, IAM, orçamento, backup, avaliação de recuperação, upstreams
docs/              documentação detalhada (índice abaixo)
.github/workflows/ CI, deploy, backup, varreduras de segurança e vigia de upstreams
```

## Desenvolvimento

```bash
python -m pip install requests fastapi google-api-core "PyMuPDF>=2.1,<3" "numpy>=1.26,<3" "mcp>=2.3,<3"
python -m compileall -q api worker
python -m unittest discover -s tests -v
python scripts/upstreams.py check    # registro de dependências externas e documentos gerados
```

Fluxo de mudança: branch → PR → CI (`Check`, testes multiusuário, OSV-Scanner, build da imagem do worker) → merge em `main`. O merge publica automaticamente:

- **Atualizar API e agentes** (`deploy-services.yml`): constrói as imagens da API e do worker e atualiza o Cloud Run.
- **Publicar scriptoriummpie.web.app** (`deploy-scriptorium-alias.yml`): publica o site.

O deploy usa Workload Identity Federation, sem chave JSON. A primeira implantação de um projeto novo está descrita no [histórico de implantação](docs/HISTORICO-IMPLANTACAO.md).

Toda origem externa (bibliotecas, APIs, normas) está registrada em [`docs/upstreams.json`](docs/upstreams.json), com licença e versão fixada; o CI falha se o código divergir do registro.

## Segurança e dados

- Cada endpoint verifica o Firebase ID token (com `email_verified`) e o convite da conta.
- Tokens do MCP: só o hash SHA-256 fica no Firestore; o token aparece uma vez e pode ser revogado.
- Chaves Gemini ficam no Secret Manager, nunca no navegador nem no repositório. `public/config.js` contém só a configuração pública do Firebase Web App.
- Nunca coloque manuscritos, dados de pesquisa ou credenciais em commits, issues, logs do Actions ou variáveis do repositório.
- Dados inéditos ou sensíveis exigem chave Gemini em projeto com faturamento ativo (Art. 9º da IN IFRS 16/2026).

## Documentação

| Documento | Assunto |
|---|---|
| [docs/MCP.md](docs/MCP.md) | Modo sem API: endereço, token e ferramentas do MCP |
| [docs/GUIA.md](docs/GUIA.md) | Guia de escrita em 8 etapas |
| [formatos/README.md](formatos/README.md) | Como criar ou ajustar uma norma |
| [docs/BIBLIOTECA-E-PROTECAO.md](docs/BIBLIOTECA-E-PROTECAO.md) | Biblioteca, upload e proteção de documentos |
| [docs/MULTIUSUARIO-BYOK.md](docs/MULTIUSUARIO-BYOK.md) | Convites e chave Gemini de cada pesquisador |
| [docs/BACKUP.md](docs/BACKUP.md) | Backups do Storage e do Firestore |
| [docs/REPLICABILIDADE-PTT.md](docs/REPLICABILIDADE-PTT.md) | Protocolo do produto técnico-tecnológico e estudo piloto |
| [docs/V2-MODULOS.md](docs/V2-MODULOS.md) | Situação dos 27 módulos do plano V2 |
| [docs/UPSTREAMS.md](docs/UPSTREAMS.md) | Dependências e fontes externas |
| [docs/HISTORICO-IMPLANTACAO.md](docs/HISTORICO-IMPLANTACAO.md) | Histórico da implantação e das ondas V2 (antigo README) |

## Limitações conhecidas

- Os modelos ABNT e APA 7 são rascunhos: não garantem conformidade com NBR 6022, 10520, 6023 nem com o manual da instituição ou da revista.
- A auditoria automática não prova que uma fonte existe, que um DOI está certo ou que uma afirmação é verdadeira; ela sinaliza o que precisa de leitura humana.
- Modelos Gemini *preview* podem mudar de nome ou preço durante o mestrado.

## Licença e créditos

Distribuído sob a **GNU Affero General Public License v3.0** ([LICENSE](LICENSE)). A licença acompanha o uso do PyMuPDF (AGPL-3.0) e garante que quem usa o site possa obter o código-fonte.

Baseado no [PaperOrchestra](https://github.com/google-research/paper-orchestra) (Google Research), que não é um produto Google oficialmente suportado. Demais créditos e licenças em [docs/UPSTREAMS.md](docs/UPSTREAMS.md).
