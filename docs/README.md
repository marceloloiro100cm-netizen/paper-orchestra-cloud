# Documentação do Scriptorium

Escolha pelo que você quer fazer.

## Usar

| Documento | Para quem |
|---|---|
| [Guia de escrita](funcionalidades/GUIA.md) | estudantes: as 8 etapas, sem IA e sem login |
| [Escrever com a sua IA (MCP)](funcionalidades/MCP.md) | quem conecta Claude, Gemini ou ChatGPT: etapas, ferramentas, referências e trava do PDF |
| [Biblioteca e proteção](funcionalidades/BIBLIOTECA-E-PROTECAO.md) | envio de fontes, formatos aceitos e limites |
| [Normas de formatação](../formatos/README.md) | ABNT, APA 7 e como criar uma norma nova |
| [Vários pesquisadores e chave Gemini](funcionalidades/MULTIUSUARIO-BYOK.md) | administradores: convites e chave de cada pessoa |

## Entender

| Documento | Conteúdo |
|---|---|
| [Arquitetura](ARQUITETURA.md) | peças do sistema, os dois modos, dados, segurança e mapa do código |
| [Glossário](GLOSSARIO.md) | etapa, cabeça, passe, confiança da referência e outros termos |
| [Identidade visual](funcionalidades/IDENTIDADE-VISUAL.md) | logo e as duas cores |
| [Módulos do plano V2](V2-MODULOS.md) | situação dos 27 módulos (gerado de `upstreams.json`) |
| [Dependências e fontes externas](UPSTREAMS.md) | licença, versão e uso de cada upstream (gerado de `upstreams.json`) |

## Desenvolver e operar

| Documento | Conteúdo |
|---|---|
| [Como contribuir](../CONTRIBUTING.md) | ambiente, testes, fluxo de PR e regras do projeto |
| [Implantação](IMPLANTACAO.md) | colocar uma cópia no ar num projeto Google Cloud próprio |
| [Workflows](WORKFLOWS.md) | o que cada GitHub Action faz e quando roda |
| [Backup](operacao/BACKUP.md) | cópias do Storage e do Firestore, retenção e recuperação |
| [Bootstrap IAM do BYOK](operacao/BYOK-BOOTSTRAP-PRODUCAO.md) | passo único de permissões para o modo com API |
| [Política de documentação Google](operacao/POLITICA-DOCUMENTACAO-OFICIAL-GOOGLE.md) | regra: consultar a documentação oficial antes de mexer na integração Google |
| [Segurança](../SECURITY.md) | como relatar uma falha |

## Pesquisa (PTT)

| Documento | Conteúdo |
|---|---|
| [Replicabilidade e protocolo do PTT](pesquisa/REPLICABILIDADE-PTT.md) | caracterização CAPES, versão congelada, estudo piloto |
| [Avaliação da busca](AVALIACAO-RECUPERACAO.md) | recall@10 e MRR no corpus de referência (gate G2) |
| [`corpus/`](corpus/) | seleção, consultas e resultados do corpus de referência |
| [`normas/`](normas/) | cópias públicas da IN IFRS 16/2026 e do Anexo I |
| [Como citar](../CITATION.cff) | metadados de citação do software |
| [Histórico de versões](../CHANGELOG.md) | o que mudou em cada versão piloto |

## Histórico

Registros de decisões e passos já concluídos. Podem citar nomes e caminhos antigos.

| Documento | Conteúdo |
|---|---|
| [Implantação de novembro de 2026](historico/IMPLANTACAO-2026-11.md) | o antigo README: implantação e ondas V2 em ordem cronológica |
| [Etapas 1 a 3](historico/ETAPAS-1-3.md) | auditoria científica, idioma e primeiras decisões (23/11/2026) |
| [Novo endereço](historico/SCRIPTORIUM-NOVO-DOMINIO.md) | mudança para `scriptoriummpie.web.app` |
| [Integração Gemini 4 Neon](historico/INTEGRACAO-GEMINI-4-NEON.md) | revisor crítico opcional (23/11/2026) |
