# Política de segurança

O Scriptorium guarda fontes e textos de pesquisa de estudantes. Relatos de falhas de segurança são muito bem-vindos.

## Como relatar

**Não abra uma issue pública.** Use o relato privado do GitHub:
[Security → Report a vulnerability](https://github.com/marceloloiro100cm-netizen/scriptorium/security/advisories/new).

Inclua, se puder: o que encontrou, como reproduzir, o impacto esperado e uma sugestão de correção. Não acesse, altere nem baixe dados de outras pessoas para demonstrar a falha.

## O que esperar

- Confirmação do recebimento em até 7 dias.
- Correção priorizada conforme a gravidade, com crédito a quem relatou (se desejar).

## Versões cobertas

Só a versão em produção (`main`, publicada em https://scriptoriummpie.web.app) recebe correções. As tags `v*-piloto` são versões congeladas de pesquisa e não recebem atualizações.

## Medidas já existentes

Resumo em [docs/ARQUITETURA.md](docs/ARQUITETURA.md#segurança): login Google com convite, regras do Firestore que negam acesso direto, tokens do MCP guardados só como hash, chaves no Secret Manager, varredura de dependências com OSV-Scanner e Dependabot.
