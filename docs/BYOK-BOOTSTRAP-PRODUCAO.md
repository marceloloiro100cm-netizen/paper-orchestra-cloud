# Scriptorium MPIE — bootstrap único de IAM para pesquisadores BYOK

**Projeto autorizado:** `paperorchestra-mestrado`.
**Ambiente:** Google Cloud Shell, com conta que tenha permissão para criar papéis IAM,
alterar IAM do projeto e habilitar APIs. Não usar credenciais de convidados.

## Por que existe esta etapa?

O GitHub Actions usa `paper-orchestra-deployer@paperorchestra-mestrado.iam.gserviceaccount.com`.
Esse publicador NÃO possui `iam.roles.create`, por projeto. Fazer esse grant
automaticamente seria dar ao pipeline acesso para alterar as próprias permissões.

O bootstrap é uma operação **única e privilegiada**:
- cria/atualiza `scriptoriumByokWriter` e concede à API somente ações de escrita
  em segredos com prefixo `scriptorium-byok-` (IAM Conditions);
- concede ao worker leitura apenas de versões do mesmo prefixo;
- cria `scriptoriumByokAuditor` com somente
  `resourcemanager.projects.getIamPolicy` e concede ao publicador;
- não lê, não exporta nem modifica o conteúdo de nenhuma chave Gemini;
- não altera Firestore, arquivos, pesquisas, contas Google nem Cormyr.

## Passo a passo

1. Entre em https://console.cloud.google.com/?project=paperorchestra-mestrado
   com uma conta que administra o projeto, e abra **Cloud Shell**.
2. No repositório GitHub `marceloloiro100cm-netizen/paper-orchestra-cloud`,
   abra **`scripts/bootstrap-cloudshell-unico.sh`** e baixe o arquivo pela
   opção **Download raw file**. No Cloud Shell, use **Upload file** para
   enviar esse único arquivo. Ele inclui o bootstrap e a auditoria.
   Não salve nem compartilhe nenhuma chave Gemini.
3. No Cloud Shell, confira o projeto e execute:

   ```bash
   gcloud config set project paperorchestra-mestrado
   gcloud auth list
   PROJECT_ID=paperorchestra-mestrado bash bootstrap-cloudshell-unico.sh
   ```

   Se estiver na raiz do repositório, use o caminho
   `scripts/bootstrap-cloudshell-unico.sh`.

4. O resultado esperado da segunda etapa é:
   `AUDITORIA BYOK: permissões condicionais esperadas presentes.`

5. Volte ao GitHub > **Actions** > **Atualizar API e agentes PaperOrchestra**
   e clique em **Run workflow** na branch `main` (ou solicite a reexecução
   do deploy que falhou). O workflow agora **somente audita** o IAM,
   sem tentar criar novos papéis.

6. O deploy só está aprovado quando o job final confirmar a revisão correta
   em `/api/health` e verificar que as rotas de administração, pesquisa e
   biblioteca exigem autenticação (HTTP 401 sem token).

7. No Scriptorium, valide com duas contas reais:
   administrador aprova pedido; convidado conecta chave; convidado não lê
   biblioteca do administrador nem utiliza seu projeto Gemini.

## Resolução de problemas

- `iam.roles.create`, `iam.roles.update` ou
  `resourcemanager.projects.setIamPolicy` negados na etapa manual:
  pare e solicite autorização a um administrador do projeto.
  **Não dê Owner/Editor/Role Admin ao deployer automático.**
- Auditoria identifica acesso irrestrito de API/worker a segredos:
  pare, revise as concessões IAM herdadas e ajuste antes de publicar.
- Auditoria com `getIamPolicy` negado para deployer:
  confirme o papel personalizado `scriptoriumByokAuditor` na SA do deployer.
- Deploy de API passa, mas frontend mostra a versão antiga:
  reabra o Scriptorium e use `Verificar atualização do servidor`,
  conferindo o log de smoke test do GitHub.
- Teste de chave retorna `429`: limite temporário não comprova que a conta
  é gratuita ou que ela não tenha acesso pago.

## Observação de segurança

O worker compartilha uma identidade de serviço para ler diferentes segredos
BYOK sob um mesmo prefixo. O código valida o UID da pesquisa e escolhe
`scriptorium-byok-<uid>`; isso é isolamento por aplicação, não
identidade IAM exclusiva por pesquisador. Uma homologação de duas contas
continua obrigatória antes de liberar o público.
