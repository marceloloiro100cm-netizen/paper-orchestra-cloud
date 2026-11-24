# Novo endereço Scriptorium — scriptorium.web.app

> **Situação em 24/11/2026 — ENDEREÇO EXATO INDISPONÍVEL.** O Firebase Hosting recusou a criação do site ID `scriptorium` (HTTP 400: `scriptorium is reserved by another project`). O workflow de cadastro foi pausado para evitar falhas recorrentes. Não houve mudança no domínio atual, no login, nos dados ou no Cloud Run. Para continuar, o responsável deve escolher outro identificador global (por exemplo, `scriptorium-mpie`, sujeito à verificação de disponibilidade). Não executar manualmente o workflow sem antes editar o SITE_ID e conferir a nova URL em todos os scripts. Os bloqueios de IAM BYOK da Issue #17 continuam independentes.

A implementação usa o [multisite oficial do Firebase Hosting](https://firebase.google.com/docs/hosting/multisites), **não** uma migração de projeto ou renomeação do site padrão.

## Objetivo

- Solicitar o identificador Firebase Hosting global `scriptorium` e o endereço `https://scriptorium.web.app`.
- Registrar o site no MESMO projeto `paperorchestra-mestrado` de Firebase Authentication, Firestore, Storage e Cloud Run.
- Manter `https://paperorchestra-mestrado.web.app` ativo e inalterado.
- Publicar o mesmo HTML/JavaScript/configuração pública nos dois domínios; preservar o rewrite `/api/**` -> `paper-orchestra-api` na região `southamerica-east1`.
- Autorizar `scriptorium.web.app` na lista de domínios Firebase Authentication, sem remover os existentes.
- Implantar futuras mudanças do front-end nos dois endereços por workflows separados, serializados com o mesmo grupo de concorrência.

## Implementação

O workflow `.github/workflows/deploy-scriptorium-alias.yml` ficou **somente manual e suspenso até a escolha de um nome disponível**. Não é executado automaticamente nas mudanças da interface.

1. Autentica no Google Cloud com a conta de serviço atual do publicador, via OIDC.
2. Consulta os sites de Hosting do projeto, cria `scriptorium` apenas se ainda não pertencer a este projeto; não tenta invadir nomes já registrados em outros projetos.
3. Usa um target temporário `scriptorium-alias` e um `firebase.json` temporário com a mesma configuração do site antigo; faz deploy SOMENTE no segundo site.
4. Compara `index.html`, `app.js`, `config.js` remotos com o repositório.
5. Lê a configuração atual do Firebase Authentication via API oficial e acrescenta o novo domínio com `updateMask=authorizedDomains`, preservando os anteriores.
6. Testa que `/api/health` responde e `/api/jobs` exige login mesmo no endereço novo.

**O site antigo é publicado pelo workflow original, que não foi alterado.** Falhas na criação do novo alias não afetam a hospedagem antiga.

## Limitações e verificações

- O nome `scriptorium` é **globalmente único**. Sua disponibilidade só é comprovada quando a criação no Firebase é aceita. Não existe substituição automática por outro nome.
- A conta de serviço atual pode não possuir permissões para criar sites Hosting (`firebasehosting.sites.create`) ou para modificar domínios autorizados do Firebase Auth. Nesse caso o workflow falhará de modo seguro e indicará a etapa bloqueadora; não são dados privilégios amplos automaticamente.
- O novo nome de domínio **não resolve** a pendência [#17](https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/issues/17) da API BYOK antiga. As rotas e os usuários continuam compartilhados.
- A tela de autenticação usa `authDomain: paperorchestra-mestrado.firebaseapp.com`, do mesmo projeto. A autorização do novo domínio é necessária para iniciar login Google a partir de `scriptorium.web.app`.
- A homologação de login real ainda depende de teste de conta Google (e, se houver restrição de API key por referer, ajuste com administrador).

## Como saber se foi concluído

No GitHub > Actions > **Scriptorium — publicar endereço scriptorium.web.app**, procurar conclusão `success` e mensagens:
- `CONFIRMADO: mesmo HTML, JS e Firebase config no novo domínio.`
- `CONFIRMADO: scriptorium.web.app autorizado no Firebase Authentication.`
- `SUCESSO: novo endereço publicado e protegido por login.`

Após isso, abrir `https://scriptorium.web.app`, entrar com Google e confirmar a mesma biblioteca (sem acesso cruzado) e os mesmos controles de conta.

## Rollback

Se o novo domínio causar problemas, desabilitar o workflow novo e continuar divulgando o endereço original. **Não excluir** o site criado nem alterar/excluir a base de usuários, dados ou segredos. A remoção de um site Hosting é irreversível, conforme a documentação do Firebase.
