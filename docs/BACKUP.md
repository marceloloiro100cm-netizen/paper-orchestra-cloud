# Backup do Scriptorium

## O que já existe

- **Arquivos** (biblioteca, pesquisas, relatórios): o workflow `Backup semanal da biblioteca` copia o bucket `paperorchestra-mestrado-paper-storage` para `paperorchestra-mestrado-paper-backups` todo domingo às 02h15 (horário de Brasília). Testado em 25/11/2026.

## O que a V1 precisa (item 4 da finalização, preparado em 25/11/2026)

1. **Banco de dados (Firestore):** registros das pesquisas, autorizações do orientador, revisões e convites não têm cópia. Solução: backup semanal nativo do Firestore, com retenção de 14 semanas (o máximo do serviço).
2. **Exclusões:** sem configuração, o backup nunca apaga nada, então o que o pesquisador apaga no site continua no backup para sempre. Solução: versionamento no bucket de backup e uma regra que apaga versões antigas 90 dias depois de substituídas ou apagadas. O backup semanal passa a espelhar exclusões só quando o versionamento está ligado: o arquivo apagado fica recuperável por 90 dias e depois some.

## Como aplicar (com autorização do responsável)

1. Rode o workflow `Backup — diagnóstico e configuração` no modo `diagnosticar` e confira a saída.
2. Rode no modo `aplicar`. Ele liga o versionamento, grava a regra de 90 dias e tenta criar o backup semanal do Firestore. Nenhuma permissão IAM é alterada.
3. Se o publicador automático não puder criar o backup do Firestore, crie pelo Console: **Firestore > Recuperação de desastres > Criar programação de backup**, banco `(default)`, semanal aos domingos, retenção de 14 semanas.

Custos esperados: centavos por mês (o banco e a biblioteca são pequenos).
