> **Arquivo histórico** (novembro de 2026). Registra uma decisão ou um passo já concluído; pode citar nomes e caminhos antigos. Visão atual: [README](../../README.md).

# Gemini 4 Neon — integração controlada (23/11/2026)

## Documentação Google utilizada

- [Guia oficial do Neon](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-neon)
- [Ficha de capacidades, acesso e limitações](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/4-neon)
- [SDK Google Gen AI](https://googleapis.github.io/python-genai/)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [ADC / identidade de execução](https://cloud.google.com/docs/authentication/application-default-credentials)

**Modelo:** `gemini-4-neon`. **Endpoint:** `global`. **SDK:** `google-genai>=2.34.0,<3`, `genai.Client(enterprise=True, project='paperorchestra-mestrado', location='global')`, modo `generate_content`. Nível de raciocínio `LOW` para limitar custo da revisão inicial. Não confundir assinatura pessoal do Gemini com faturamento da API.

## Acesso validado com o worker

A execução real `paper-orchestra-neon-smoke-hzngv` do Cloud Run Job `paper-orchestra-neon-smoke`, com a identidade `paper-orchestra-worker@paperorchestra-mestrado.iam.gserviceaccount.com`, **terminou com sucesso** em 23/11/2026. O script apenas retorna código zero se a API Neon produzir uma resposta contendo `NEON_OK`.

O workflow original ficou vermelho porque a identidade do GitHub não possuía permissão de visualizar logs — uma checagem extra e desnecessária. Não foi um erro de autenticação do modelo; a verificação foi ajustada para confiar no código de saída validado pelo Job, sem aumentar permissões IAM.

## Operação da revisão adicional

1. Usuário gera o manuscrito como sempre, usando Flash ou Pro no pipeline PaperOrchestra.
2. O componente **Revisão crítica adicional com Gemini 4 Neon**, quando habilitado, usa uma única chamada à Agent Platform após existir o PDF.
3. Neon recebe extrato limitado do PDF (35 páginas / 24 mil caracteres), ideia (4 mil) e registros (4 mil) e retorna um relatório JSON de argumentos, alegações sem evidência, perguntas e limitações.
4. O relatório privado `neon_critical_review.json` é salvo no Cloud Storage e acessível apenas pelo dono via backend; **o texto do PDF não é reescrito**.
5. Se Neon falhar, a geração principal não falha; o status marca a revisão adicional como indisponível.
6. O frontend só exibe a opção caso `/api/capabilities` retorne `neon_review=true`, definida na API por `NEON_REVIEW_ENABLED=true`.
7. Uma chamada adicional por pesquisa significa custo adicional. A plataforma não interrompe cobrança automaticamente. O relatório não é validação bibliográfica independente nem substitui leitura das fontes.

### Não altera o modelo original do PaperOrchestra

A biblioteca upstream pode continuar usando `genai.Client(vertexai=True, ...)` para Flash/Pro. O novo parecer Neon fica isolado em `worker/neon_review.py`, com cliente enterprise, para evitar regressões nas etapas de literatura e redação.

**Ainda exige validação ponta a ponta:** criar uma nova pesquisa real com a opção habilitada, esperar o PDF e conferir o download do parecer. O teste do smoke apenas comprova autorização de API, não desempenho científico.
