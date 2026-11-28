# Scriptorium — biblioteca, backups e acesso mínimo

## Biblioteca acadêmica (versão 1)

A aplicação aceita **PDF, DOCX, BIB, RIS e TXT** mediante login Google autorizado. O backend armazena o original no bucket `paperorchestra-mestrado-paper-storage` e metadados na coleção Firestore `library_items`, sob o UID da conta. Dados não entram no GitHub público.

- Limite: 8 MiB para PDF/DOCX; 2 MiB para BIB/RIS/TXT; até 500 arquivos ativos por usuário.
- Arquivos são isolados por UID e ID gerado pelo servidor. Operações de listagem e download exigem token Firebase válido e conferência da propriedade.
- O usuário pode marcar até **oito** documentos ativos para uma nova pesquisa. A API valida todas as fontes antes de iniciar qualquer tarefa paga.
- O worker extrai texto localmente (até 60 páginas PDF, limites de 20 mil caracteres por fonte e 75 mil caracteres no total). Os materiais são identificados como **fontes não confiáveis** e nunca alteram a origem.
- Um PDF escaneado sem camada textual pode não fornecer conteúdo; a primeira versão não implementa OCR. DOCX, BIB, RIS e TXT são lidos como texto. Não se alega que toda referência seja válida.
- Arquivar oculta o documento da biblioteca ativa, mas não apaga a cópia: a pesquisa e sua proveniência permanecem reprodutíveis.
- As pesquisas anteriores continuam acessíveis na seção Histórico, sem anexos retroativos.

## Backups — execução via GitHub Actions

A rotina `Proteção inicial e redução de acessos` verifica a existência de um bucket principal e provisiona:

1. **Firestore diário**: cópias agendadas por 7 dias.
2. **Firestore semanal**: domingo, retido por 12 semanas.
3. **Cloud Storage principal**: soft delete de no mínimo 14 dias, nunca reduzindo uma retenção maior que já exista.
4. **Bucket secundário privado**: `gs://paperorchestra-mestrado-paper-backups`, região São Paulo, com bloqueio de acesso público e soft delete.
5. **Primeira cópia**: `gcloud storage rsync --recursive` sem nenhuma opção de exclusão. Preserva originais.
6. **Cópia semanal**: workflow `Backup semanal da biblioteca`, domingo às 05h15 UTC, que copia novos/alterados sem remover arquivos antigos do backup.

Backups geram custos adicionais de armazenamento e podem falhar por quotas ou IAM. O Cloud Firestore agenda backups independentemente do GitHub, enquanto a cópia semanal do bucket depende da execução de GitHub Actions; fluxos agendados em repositórios públicos podem ser desativados pelo GitHub após períodos prolongados sem atividade. Verifique regularmente o histórico de backup.

**Restaurar:** o backup Firestore deve ser restaurado inicialmente em outro banco de dados, conforme guia do Google Cloud. Objetos do backup secundário podem ser copiados individualmente ao bucket principal pelo proprietário; **nenhuma restauração automática ou exclusão da produção** é realizada pelos workflows.

## Orçamento e alerta de custos

A rotina tenta criar, uma única vez, um orçamento mensal limitado ao projeto `paperorchestra-mestrado`, com referência inicial de **50 unidades da moeda da conta de faturamento** e limiares de **50%, 80%, 100%**. Esse valor pode ser ajustado no console.

A função exige acesso de orçamento à conta de faturamento. Se não houver permissão, o workflow apenas emite aviso e continua com os backups; **não deve ser informado como orçamento ativo**. Destinatários padrão são os usuários com funções IAM da conta de faturamento. Orçamentos avisam, **não interrompem cobranças**.

Console: https://console.cloud.google.com/billing?project=paperorchestra-mestrado

## Redução de privilégios

Somente **depois** de confirmar que o backup Firestore diário/semanal existe e que o bucket secundário existe, o script reduz as funções **globais temporárias** do `paper-orchestra-deployer`, removendo Project IAM Admin, Service Account Admin, Service Usage Admin, Artifact Registry Admin e Storage Admin, além do papel global Service Account User. Reaplica `Service Account User` **apenas** nas duas contas Cloud Run e as permissões de armazenamento **apenas** nos buckets pertinentes.

Mantém funções estritamente necessárias aos processos atuais, como Cloud Run Admin, Cloud Build Editor, Firebase Hosting Admin e Firebase Rules Admin. Mantém somente leitura de políticas IAM para auditoria. Não altera as contas do projeto Cormyr.

O script de primeira implantação (`deploy-cloud-shell.sh`) pode exigir reautorização temporária caso seja necessário reconstruir a infraestrutura desde zero. Atualizações usuais de API/worker/Hosting não deveriam exigir essas funções removidas.

## Verificação obrigatória

Consulte o resultado do workflow GitHub:
https://github.com/marceloloiro100cm-netizen/scriptorium/actions/workflows/guardrails.yml

Confirme o orçamento diretamente no console se houver aviso de permissão, e teste um novo envio de documento pelo celular. Nunca envie documentos pessoais ou credenciais para o repositório público.
