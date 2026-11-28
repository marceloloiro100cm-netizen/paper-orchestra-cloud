# Glossário

Termos próprios do Scriptorium, em ordem alfabética.

| Termo | Significado |
|---|---|
| **BYOK** | *Bring your own key*: cada pesquisador usa a própria chave Gemini no modo com API, e os tokens de IA são cobrados dele, não do projeto. |
| **Cabeça** | Papel que uma conversa de IA assume num projeto: **redatora** (planeja e escreve), **revisora** (critica) ou **verificadora** (confere afirmações). Na revisão sistemática há também a **triadora**. Uma cabeça que escreveu não revisa nem verifica. |
| **Chave de conexão** | Nome, no site, do token pessoal que conecta a IA do pesquisador ao Scriptorium. |
| **Compilar** | Gerar o PDF a partir do LaTeX das etapas. Sai **final** só com todas as referências confirmadas; senão sai **RASCUNHO**, com os motivos. |
| **Confiança da referência** | **confirmada** (DOI ou conferida no documento), **sugerida** (achada no OpenAlex, pode ser outra obra) ou **a conferir** (só o que o arquivo diz). |
| **Escudo de auditoria** | Lista de alertas por gravidade que junta as verificações de uma pesquisa (modo com API). Não dá nota nem selo. |
| **Etapa** | Cada passo do fluxo MCP. No artigo: planejamento, evidências, redação, revisão, reescrita e verificação. Cada entrega é conferida antes de ser aceita. |
| **Fichamento** | Notas de leitura por página de um item da biblioteca. |
| **Formato (norma)** | Pasta em `formatos/` com as regras de uma norma (ABNT, APA 7…): preâmbulo LaTeX, regras para a IA e estilo CSL. |
| **Gate G2** | Critério do plano V2: uma mudança na busca só é adotada se melhorar recall@10 e MRR no corpus de referência. |
| **Guia de escrita** | Passo a passo em 8 etapas, sem IA, para organizar um artigo ou projeto de pesquisa. Funciona sem login. |
| **IN IFRS 16/2026** | Instrução normativa do IFRS sobre uso de IA em trabalhos acadêmicos; o Scriptorium gera o rascunho da declaração. |
| **Independência** | Registro de quem fez cada etapa: `outra_ia`, `outra_conversa` ou `mesma_cabeca`. É declarado de boa-fé, não prova. |
| **MCP** | *Model Context Protocol*: protocolo pelo qual a IA do pesquisador usa as ferramentas do Scriptorium. |
| **Modo com API / sem API** | Com API: o servidor gera o texto com Gemini (oculto desde 25/11/2026). Sem API (MCP): a IA do pesquisador escreve e o Scriptorium confere. |
| **Modo pedagógico** | Quanto a IA pode sugerir de texto pronto; no modo **tutor socrático** ela pergunta e dá pistas antes de sugerir. |
| **PaperOrchestra** | Motor de redação da Google Research usado no modo com API. Também foi o primeiro nome deste projeto (até 28/11/2026). O nome antigo continua só onde o Google não permite trocar ou onde trocar exigiria migrar dados: o ID do projeto Google Cloud (`paperorchestra-mestrado`), os buckets, os serviços e as contas de serviço do Cloud Run (`paper-orchestra-*`) e o nome do alerta de orçamento. |
| **Passe** | Código que abre uma etapa de revisão ou verificação **numa conversa nova**, para que outra cabeça faça o trabalho. |
| **Plano V2** | Plano técnico de 27 módulos (M01–M27) aplicado em novembro de 2026; ver [V2-MODULOS.md](V2-MODULOS.md). |
| **PTT** | Produto técnico-tecnológico. O Scriptorium é o PTT do mestrado; ver [pesquisa/REPLICABILIDADE-PTT.md](pesquisa/REPLICABILIDADE-PTT.md). |
| **Trecho** | Pedaço de uma fonte com página e seção, usado na busca e na citação. |
| **Upstream** | Toda origem externa do projeto (biblioteca, API, norma, artigo), registrada em [upstreams.json](upstreams.json). |
| **Worker** | O Cloud Run Job que faz o trabalho pesado (fontes, bibliografia, PDF). |
