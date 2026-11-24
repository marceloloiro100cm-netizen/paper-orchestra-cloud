# Scriptorium MPIE — acesso multiusuário / BYOK

## Fase 1 — convites e isolamento (esta branch)

- Mantém os e-mails existentes em `ALLOWED_EMAILS` como administradores, sem alteração no fluxo próprio.
- Administradores podem convidar e revogar pesquisadores, autenticados pelo Firebase:
  - `POST /api/admin/invitations` com JSON `{"email":"pesquisador@example.org"}`
  - `DELETE /api/admin/invitations/{email}`
  - `GET /api/account/access` informa `admin`, `byok_ready` e `research_generation_enabled`.
- Convites ficam em `research_members/{sha256(email_normalizado)}`; o acesso Firestore pelo cliente continua totalmente negado.
- Sem convite ativo, o login API é negado.
- **Convidados ainda NÃO podem iniciar pesquisas:** `POST /api/jobs` retorna 409 antes de escrever objetos ou disparar Cloud Run Job. Isso impede o uso involuntário do Vertex AI e da chave central do administrador.
- Biblioteca e histórico já utilizam `owner_uid` e continuam separados.
- Nenhuma chave de API individual é solicitada nem armazenada nesta fase.

## Fase 2 — dependência obrigatória antes de liberar pesquisas

1. Implementar cofre por usuário para credenciais Gemini, criptografia/proteção pelo Google Cloud e rotas autenticadas de configuração/remoção/teste. Nunca persistir chave em Firestore, GitHub, logs, HTML ou localStorage.
2. Adaptar Cloud Run Job para buscar a **própria** chave autorizada do usuário com base no `owner_uid` validado e bloquear execução na ausência dela.
3. Garantir que **todas** as chamadas dos agentes, inclusive imagem, revisão e Neon, operem com a credencial individual, sem fallback para Vertex do projeto nem chave central.
4. Testes de isolamento entre contas, revogação, erros de chave, execução concorrente e registro de uso sem vazamento de segredos. Modo administrador legado continua isolado.
5. Só então habilitar a geração para convidados e oferecer formulário de conexão no site.

## Custos

A chave própria atribui o consumo da API Gemini ao projeto ao qual ela pertence. Hosting, Cloud Run, Firestore e Storage continuam sendo cobrados no projeto compartilhado do mantenedor. A chave não transfere esses custos.

## Publicação

A branch e o PR são deliberadamente separados de `main`. Não fazer merge antes de revisar e testar a fase 1. Jamais oferecer uma conta convidada com fallback silencioso para os créditos do administrador.
