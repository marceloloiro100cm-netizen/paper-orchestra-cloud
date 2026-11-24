# Scriptorium MPIE — múltiplos pesquisadores, cada um com sua chave Gemini

> **Status: implementação em branch / PR de revisão; NÃO implantado em produção.**
> Antes de publicar: revisar as permissões de IAM, executar CI e realizar homologação
> com duas contas convidadas e projetos Gemini distintos.

## Funcionalidade entregue no código

- O login Google continua baseado em Firebase Authentication e exige convite ativo.
- O administrador existente em `ALLOWED_EMAILS` conserva a sua configuração de IA;
  somente ele consegue emitir ou revogar convites.
- O painel do Scriptorium permite cadastrar e revogar convites e conectar a chave
  Gemini pessoal do convidado. O valor é apagado do formulário após salvar.
- A API armazena a chave **exclusivamente no Google Secret Manager**,
  como `scriptorium-byok-{firebase_uid}`; Firestore mantém apenas status e
  endereço do segredo, nunca o seu conteúdo.
- A geração de um convidado só é admitida quando há convite ativo **e**
  credencial pessoal ativa. O modo `ai_auth_mode=user_gemini` é persistido na pesquisa.
- O worker valida `owner_uid`, carrega só a credencial desse UID, elimina as
  variáveis herdadas de chaves centrais e Vertex AI e fornece a chave exclusivamente
  ao subprocesso de agentes, com `GOOGLE_GENAI_USE_VERTEXAI=false`.
- Não há fallback de convidados para a chave central. A revisão Neon via
  infraestrutura do administrador está bloqueada para convidados.
- A biblioteca e histórico já são particionados por `owner_uid`.
- A chave é revogada no metadata **antes** de tentar excluir o segredo.
- Há testes unitários de convites, revogação e isolamento do ambiente do worker.

## Limites e alertas

1. Ainda não houve teste end-to-end com API/Cloud Run/Secret Manager reais.
2. Uma chave salva pode estar inválida: o cadastro verifica formato, não a
   disponibilidade de todos os modelos Gemini. Erros podem aparecer na geração.
3. Chaves pessoais do Gemini API não habilitam necessariamente modelos ou operações
   exclusivas de Vertex AI. A revisão Neon continua indisponível aos convidados.
4. A cobrança dos modelos Gemini segue o projeto de origem **da chave pessoal**.
   O mantenedor ainda paga Firebase Hosting, Firestore, Storage e Cloud Run.
5. Uma revogação impede novas pesquisas e novas leituras pelo worker, mas não
   encerra à força um subprocesso já iniciado com a chave na memória.
6. A autorização atual permite até um trabalho por conta ao mesmo tempo;
   é necessário monitorar quotas, abusos, custo de CPU, Storage e limites gerais.
7. O painel de convites recebe o e-mail individual; não existe cadastro aberto.

## Rotas API

- `GET /api/account/access`: resumo autorizado (`admin`,
  `byok_ready`, `research_generation_enabled`).
- `PUT /api/account/credential`: `{"key":"..."}`; cria uma nova versão da
  chave pessoal sem jamais retornar o valor.
- `DELETE /api/account/credential`: desativa acesso à chave e apaga o segredo.
- `POST /api/admin/invitations`: `{"email":"pessoa@exemplo.org"}`.
- `DELETE /api/admin/invitations/{email}`: revoga um convite.

## Pré-requisitos operacionais para publicar

O serviço API precisa de permissões de **criação e gestão de segredos** sob
`scriptorium-byok-*`, e o Cloud Run Job precisa de permissão para **ler somente**
esses segredos; a identidade do deploy precisa ter permissão para configurar IAM.
Não reutilizar permissões de usuários finais nem expor credenciais no Hosting.

O Secret Manager cobra por versões armazenadas e acessos. É necessário revisar
as políticas IAM com o princípio do menor privilégio antes de implantar.
**Não conceder automaticamente `roles/secretmanager.admin` a todas as contas.**

Foi adicionado o provisionamento controlado em
`scripts/setup-byok-iam.sh`, que cria uma função IAM personalizada para a API
e concede ao worker acesso de leitura **condicionado ao prefixo**
`scriptorium-byok-`. A API não recebe permissão para ler os valores dos
segredos; o worker não recebe permissão irrestrita de leitura de segredos.

Esse script **não é executado automaticamente** pelo deploy de serviços.
Deve ser revisado, executado explicitamente no projeto
`paperorchestra-mestrado` e verificado com IAM efetivo antes de promover o PR.
É necessário garantir que nenhuma outra concessão preexistente forneça acesso
não condicionado à chave administrativa.

A API precisa das permissões de criação, atualização de versão e exclusão dos
segredos BYOK; o worker precisa somente de
`secretmanager.versions.access`. A leitura do segredo individual continua
validando o `owner_uid` no backend.

**Não promover para produção sem esses passos e sem executar uma pesquisa
homologada com chave de um segundo projeto Gemini.**

Documentação oficial:
- https://cloud.google.com/secret-manager/docs/best-practices
- https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
- https://cloud.google.com/secret-manager/docs/access-secret-version
- https://ai.google.dev/gemini-api/docs/get-started

## Validação antes do merge

1. Confirmar execução de `test-multiuser.yml` no PR e testes existentes.
2. Verificar IAM e serviço deployado em ambiente de teste, com secrets separados.
3. Testar usuário administrador com pesquisa existente; ele nunca deve ser
   forçado a cadastrar chave pessoal.
4. Testar usuário sem convite: login API recusado.
5. Convidar usuário A: consegue entrar, mas não gerar sem chave.
6. Conectar chave de A e executar pesquisa; validar projeto faturado na
   conta de A (não no projeto do administrador).
7. Convidar usuário B: não consegue ler dados, fontes ou chave de A.
8. Revogar chave de A e tentar nova execução; deve falhar antes de iniciar Cloud Run.
9. Testar chave inválida, execução simultânea, logout, uploads e downloads.
10. Confirmar que logs e respostas HTTP não contêm chaves; testar modo Neon
    desabilitado para convidados.
