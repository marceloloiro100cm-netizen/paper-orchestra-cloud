# Novo endereço Scriptorium — scriptoriummpie.web.app

> **Atualização de 24/11/2026 (noite):** `https://scriptoriummpie.web.app/` passou a ser o endereço oficial, por decisão do responsável. O endereço antigo `paperorchestra-mestrado.web.app` não recebe mais a aplicação: responde só com redirecionamento permanente (301) para o novo (`hosting-redirect/` e `.github/workflows/deploy-hosting.yml`). O login Google continua funcionando porque o Firebase atende `/__/auth/*` antes de qualquer redirecionamento. As instruções abaixo, sobre manter o endereço antigo inalterado, ficaram só como histórico.

> **Nova tentativa em 24/11/2026:** O endereço anterior `scriptorium.web.app` foi recusado pelo Firebase porque pertence a outro projeto. Por solicitação do responsável, este procedimento passa a testar **`scriptoriummpie.web.app`**, nome ainda não confirmado como disponível. O endereço original continua em funcionamento, e a questão IAM BYOK da Issue #17 é independente.

A implementação usa o [multisite oficial do Firebase Hosting](https://firebase.google.com/docs/hosting/multisites), **não** uma migração de projeto ou renomeação do site padrão.

## Objetivo

- Solicitar o identificador Firebase Hosting global `scriptoriummpie` e o endereço `https://scriptoriummpie.web.app`.
- Registrar o site no MESMO projeto `paperorchestra-mestrado` de Firebase Authentication, Firestore, Storage e Cloud Run.
- Manter `https://paperorchestra-mestrado.web.app` ativo e inalterado.
- Publicar o mesmo HTML/JavaScript/configuração pública nos dois domínios; preservar o rewrite `/api/**` -> `paper-orchestra-api` na região `southamerica-east1`.
- Autorizar `scriptoriummpie.web.app` na lista de domínios Firebase Authentication, sem remover os existentes.
- Depois de comprovar o novo domínio e o login Google, estender a publicação das futuras mudanças do front-end para os dois endereços, serializados com o mesmo grupo de concorrência. Até lá, a publicação principal permanece independente.

## Implementação

O workflow `.github/workflows/deploy-scriptorium-alias.yml` é disparado ao integrar esta atualização de scripts na branch principal e também aceita execução manual. A disponibilidade só será comprovada pelo Google ao tentar criar o site.

1. Autentica no Google Cloud com a conta de serviço atual do publicador, via OIDC.
2. Consulta os sites de Hosting do projeto, cria `scriptoriummpie` apenas se ainda não pertencer a este projeto; não tenta invadir nomes já registrados em outros projetos.
3. Usa um target temporário `scriptorium-alias` e um `firebase.json` temporário com a mesma configuração do site antigo; faz deploy SOMENTE no segundo site.
4. Compara `index.html`, `app.js`, `config.js` remotos com o repositório.
5. Lê a configuração atual do Firebase Authentication via API oficial e acrescenta o novo domínio com `updateMask=authorizedDomains`, preservando os anteriores.
6. Testa que `/api/health` responde e `/api/jobs` exige login mesmo no endereço novo.

**O site antigo é publicado pelo workflow original, que não foi alterado.** Falhas na criação do novo alias não afetam a hospedagem antiga.

## Limitações e verificações

- O nome `scriptoriummpie` é **globalmente único**. Sua disponibilidade só é comprovada quando a criação no Firebase é aceita. Não existe substituição automática por outro nome.
- A conta de serviço atual pode não possuir permissões para criar sites Hosting (`firebasehosting.sites.create`) ou para modificar domínios autorizados do Firebase Auth. Nesse caso o workflow falhará de modo seguro e indicará a etapa bloqueadora; não são dados privilégios amplos automaticamente.
- O novo nome de domínio **não resolve** a pendência [#17](https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/issues/17) da API BYOK antiga. As rotas e os usuários continuam compartilhados.
- A tela de autenticação usa `authDomain: paperorchestra-mestrado.firebaseapp.com`, do mesmo projeto. A autorização do novo domínio é necessária para iniciar login Google a partir de `scriptoriummpie.web.app`.
- A homologação de login real ainda depende de teste de conta Google (e, se houver restrição de API key por referer, ajuste com administrador).

## Como saber se foi concluído

No GitHub > Actions > **Scriptorium — publicar endereço scriptoriummpie.web.app**, procurar conclusão `success` e mensagens:
- `CONFIRMADO: mesmo HTML, JS e Firebase config no novo domínio.`
- `CONFIRMADO: scriptoriummpie.web.app autorizado no Firebase Authentication.`
- `SUCESSO: novo endereço publicado e protegido por login.`

Após isso, abrir `https://scriptoriummpie.web.app`, entrar com Google e confirmar a mesma biblioteca (sem acesso cruzado) e os mesmos controles de conta.

## Rollback

Se o novo domínio causar problemas, desabilitar o workflow novo e continuar divulgando o endereço original. **Não excluir** o site criado nem alterar/excluir a base de usuários, dados ou segredos. A remoção de um site Hosting é irreversível, conforme a documentação do Firebase.
