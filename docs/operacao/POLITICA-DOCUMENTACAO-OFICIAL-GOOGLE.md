# Política técnica — Scriptorium

**Regra permanente do projeto:** para qualquer alteração da integração Google, consultar **primeiro a documentação oficial do Google**. Não escolher nomes de modelos, endpoints, parâmetros, preços, capacidades, permissões ou limites por lembrança, exemplo comunitário ou suposição. Registrar a fonte oficial em cada PR relevante e verificar o estado real no código e nos workflows.

## Referências primárias (23/11/2026)

1. **Guia do Gemini 4 Neon e migração:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-neon
2. **Ficha técnica oficial do Neon:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/4-neon
3. **Versões e aposentadoria de modelos:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions
4. **Disponibilidade regional e endpoints:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations
5. **Preços e cobranças de IA generativa:** https://cloud.google.com/vertex-ai/generative-ai/pricing
6. **Guia oficial de migração entre modelos:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/migrate
7. **Autenticação ADC / contas de serviço:** https://cloud.google.com/docs/authentication/application-default-credentials
8. **Cloud Run Jobs:** https://cloud.google.com/run/docs/create-jobs
9. **Firebase Authentication:** https://firebase.google.com/docs/auth
10. **Firestore e backup agendado:** https://cloud.google.com/firestore/native/docs/backups
11. **Cloud Storage soft delete:** https://cloud.google.com/storage/docs/soft-delete

## Gemini 4 Neon: checklist específico

- **ID oficial:** `gemini-4-neon`.
- **Plataforma e acesso:** a documentação apresenta Neon no Gemini Enterprise Agent Platform, com disponibilidade limitada a clientes empresariais verificados em regiões selecionadas. Não confundir assinatura pessoal Google AI Pro com habilitação de API do projeto Cloud.
- **Endpoints:** `global`, `us` ou `eu`. O local `southamerica-east1` do Firebase e do Cloud Run não implica que o endpoint de inferência de Neon seja São Paulo.
- **SDK:** para continuação automática na Interactions API, `google-genai >= 2.34.0` em Python; verificar changelog antes da atualização.
- **Thinking:** `LOW`, `MEDIUM`, `HIGH` (padrão) e `XHIGH`; não usar `thinking_budget` ou `MINIMAL` com Neon. `temperature`, `top_p` e `top_k` são ignorados no Neon.
- **Caching:** somente cache implícito; remover chamadas de cache explícito em rotas Neon.
- **Custos:** medir tokens de entrada, saída e raciocínio, além das ferramentas chamadas; configurar alertas, teto operacional da aplicação e logs de custo.
- **Capacidade de modelo não é garantia de veracidade:** validações bibliográficas e científicas permanecem independentes.

## Estado do nosso código quando esta política foi registrada

Em `api/main.py` a criação de pesquisas aceita apenas `gemini-3-flash-preview` e `gemini-3.1-pro-preview`. Em `public/index.html`, o seletor de modelos também não oferece Neon. O `worker/runner.py` apenas encaminha os identificadores fornecidos pela API para o CLI do PaperOrchestra. O código upstream consultado (`utils/gemini_utils.py`) cria cliente `genai.Client(vertexai=True,...)`, enquanto o guia oficial do Neon apresenta cliente `genai.Client(enterprise=True, project=..., location=...)` e requisitos específicos para a versão do SDK.

**Conclusão:** uma eventual habilitação do Neon no console ou em uma integração separada NÃO prova que os agentes do site estejam usando Neon. Antes de anunciar integração concluída, verificar:

1. Conta/projeto e modo de acesso elegíveis para `gemini-4-neon`.
2. Adaptador compatível com a API oficial do produto; evitar alterar globalmente o cliente e quebrar Flash/Pro.
3. Configuração explícita por agente no backend e no seletor.
4. Teste de chamada real, não apenas teste de autenticação, e confirmação do ID do modelo nos logs.
5. Testes de custo, compatibilidade de parâmetros, tratamento de falhas e retorno para o modelo anterior.

## Fluxo obrigatório de mudança

**Documento oficial atual → hipótese/alteração → branch e PR → testes isolados → teste de integração → publicação → verificação em produção.**

Não alterar o projeto `cormyr`, não usar Vercel, não exigir ações do Lovable. Preservar os documentos privados no Firestore e Cloud Storage. Credenciais e chaves privadas nunca são enviadas ao GitHub.
