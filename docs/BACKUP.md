# Backup do Scriptorium

## O que já existe

- **Arquivos** (biblioteca, pesquisas, relatórios): o workflow `Backup semanal da biblioteca` copia o bucket `paperorchestra-mestrado-paper-storage` para `paperorchestra-mestrado-paper-backups` todo domingo às 02h15 (horário de Brasília). Testado em 25/11/2026.
- **Banco de dados (Firestore):** duas programações nativas, criadas em 24/11/2026 por `scripts/configure-guardrails.sh` e conferidas em 25/11/2026: diária com retenção de 7 dias e semanal (domingo) com retenção de 12 semanas.
- **Bucket de backup:** exclusão reversível (soft delete) de 14 dias, padrão do Google Cloud.

## O que a V1 precisa (item 4 da finalização, preparado em 25/11/2026)

1. **Exclusões:** sem configuração, o backup nunca apaga nada, então o que o pesquisador apaga no site continua no backup para sempre. Solução: versionamento no bucket de backup e uma regra que apaga versões antigas 90 dias depois de substituídas ou apagadas. O backup semanal passa a espelhar exclusões só quando o versionamento está ligado: o arquivo apagado fica recuperável por 90 dias e depois some.

## Como aplicar (com autorização do responsável)

1. Rode o workflow `Backup — diagnóstico e configuração` no modo `diagnosticar` e confira a saída.
2. Rode no modo `aplicar`. Ele liga o versionamento e grava a regra de 90 dias. O backup do Firestore já existe, então essa parte é pulada. Nenhuma permissão IAM é alterada.

Custos esperados: centavos por mês (o banco e a biblioteca são pequenos).
