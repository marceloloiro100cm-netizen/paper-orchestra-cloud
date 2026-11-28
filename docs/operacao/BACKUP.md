# Backup do Scriptorium

## O que já existe

- **Arquivos** (biblioteca, pesquisas, relatórios): o workflow `Backup semanal da biblioteca` copia o bucket `paperorchestra-mestrado-paper-storage` para `paperorchestra-mestrado-paper-backups` todo domingo às 02h15 (horário de Brasília). Testado em 25/11/2026.
- **Banco de dados (Firestore):** duas programações nativas, criadas em 24/11/2026 por `scripts/configure-guardrails.sh` e conferidas em 25/11/2026: diária com retenção de 7 dias e semanal (domingo) com retenção de 12 semanas.
- **Bucket de backup:** exclusão reversível (soft delete) de 14 dias, padrão do Google Cloud.

## Exclusões (item 4 da finalização, aplicado em 25/11/2026)

1. **Exclusões:** sem configuração, o backup nunca apaga nada, então o que o pesquisador apaga no site continua no backup para sempre. Solução: versionamento no bucket de backup e uma regra que apaga versões antigas 90 dias depois de substituídas ou apagadas. O backup semanal passa a espelhar exclusões só quando o versionamento está ligado: o arquivo apagado fica recuperável por 90 dias e depois some.

**Aplicado em 25/11/2026** com autorização do responsável, pelo Console (o publicador automático não tem `storage.buckets.update`, e não ganhou essa permissão). Configuração conferida pelo modo `diagnosticar`:

- versionamento ligado no bucket de backup;
- regra 1: apaga uma versão antiga quando já existem 2 mais novas (guarda a atual e a anterior);
- regra 2: apaga versões antigas 90 dias depois de substituídas ou apagadas.

## Como refazer em outro projeto

1. Rode o workflow `Backup — diagnóstico e configuração` no modo `diagnosticar` e confira a saída.
2. Rode no modo `aplicar` (precisa de `storage.buckets.update` no bucket de backup) ou faça pelo Console: bucket de backup > Proteção > Controle de versões de objetos > ativar, com regras de ciclo de vida (2 versões, expirar versões antigas após 90 dias). Nenhuma permissão IAM é alterada.

Custos esperados: centavos por mês (o banco e a biblioteca são pequenos).
