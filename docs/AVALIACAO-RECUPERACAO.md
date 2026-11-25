# Avaliação de recuperação (gate G2 do plano V2)

O plano V2 só aprova uma mudança na busca (lexical, híbrida, reranking) se a melhoria for **medida e reproduzível** num corpus de referência. O script `scripts/eval_retrieval.py` mede:

- **recall@10:** fração dos trechos relevantes que aparecem entre os 10 primeiros resultados;
- **MRR:** média de 1/posição do primeiro resultado relevante (1,0 = sempre em primeiro).

## Como montar o corpus de referência

1. Escolha **30 PDFs** representativos do mestrado: artigos em português e inglês, capítulos de livro, dissertações, PDFs com duas colunas, ao menos 3 digitalizados (para medir o M23) e ao menos 3 com tabelas. Coloque todos numa pasta, por exemplo `corpus-referencia/`.
2. Escreva de **30 a 50 perguntas** que você faria numa pesquisa real, num arquivo `consultas.jsonl`. Para cada pergunta, indique onde está a resposta, por página ou por um trecho do texto:

   ```json
   {"id": "q01", "query": "efeitos da sala de aula invertida na autonomia dos estudantes", "relevant": [{"file": "bergmann2012.pdf", "pages": [12, 13]}]}
   {"id": "q02", "query": "críticas à gamificação no ensino técnico", "relevant": [{"file": "silva2020.pdf", "contains": "efeito novidade"}]}
   ```

3. Rode a avaliação (no seu computador, com Python 3.11 e PyMuPDF instalado):

   ```bash
   python scripts/eval_retrieval.py --corpus corpus-referencia --queries consultas.jsonl --output resultado-lexical.json
   GEMINI_API_KEY=sua-chave python scripts/eval_retrieval.py --corpus corpus-referencia --queries consultas.jsonl --hybrid --output resultado-hibrido.json
   ```

   A opção `--hybrid` envia os trechos do corpus ao serviço de embeddings do Gemini (custo pequeno, cobrado na chave usada).

4. Guarde os arquivos de resultado. Eles são a linha de base: toda mudança futura de parser (Docling), trechos, embeddings ou reranker (InRanker/FlagEmbedding) é comparada com eles.

Num corpus próprio (PDFs da sua pesquisa), os PDFs e as perguntas **não** devem ir para o repositório público. O corpus de referência descrito abaixo é diferente: só tem documentos de acesso aberto, e mesmo assim o repositório guarda apenas metadados, consultas e métricas, nunca os PDFs ou o texto deles.

## Testar um reranker (M20)

O plano só adota um reranker se ele melhorar recall@10 e MRR de forma reproduzível. Para medir, instale o reranker no seu computador (não vai para o worker) e rode:

```bash
pip install FlagEmbedding            # R17, modelo BAAI/bge-reranker-v2-m3
python scripts/eval_retrieval.py --corpus corpus-referencia --queries consultas.jsonl --reranker bge --output resultado-bge.json

# InRanker (R16) fixa torch==2.1.1 e transformers==4.27.4: use um ambiente virtual separado.
pip install inranker
python scripts/eval_retrieval.py --corpus corpus-referencia --queries consultas.jsonl --reranker inranker --output resultado-inranker.json
```

O relatório traz cada estratégia com e sem reranking (por exemplo `lexical` e `lexical+rerank_bge`). Se o ganho for consistente, o reranker escolhido entra na imagem do worker (`SCRIPTORIUM_V2_RERANKER=bge` ou `inranker`), depois de conferir a licença dos pesos no model card.


## Resultado no corpus de referência (25/11/2026)

Corpus montado para uma tese teste da linha Práticas Educativas em EPT ("Entre a assistência e a autoria", IA generativa e formação científica crítica). Ficam no repositório:

- `docs/corpus/temas.json`: 7 temas (T1 pesquisa como princípio pedagógico, T2 formação humana integral, T3 letramento científico, T4 mediação tecnológica, T5 autonomia e autoria, T6 letramento em IA, T7 iniciação científica na EPT) e as buscas usadas no OpenAlex;
- `docs/corpus/selecao.json`: os 30 documentos escolhidos, com DOI, licença, link do PDF e SHA-256;
- `docs/corpus/consultas.jsonl`: 48 consultas (35 específicas, 7 temáticas, 6 sem resposta no corpus);
- `docs/corpus/resultados/`: métricas por consulta (sem texto dos PDFs).

O workflow `Corpus de referência e avaliação (gate G2)` refaz tudo: modo `coletar` busca candidatos, modo `avaliar` baixa a seleção, confere o SHA-256 e mede. Na última execução, 29 dos 30 PDFs baixaram (o servidor de `T3_oliveira2015` não respondeu em 60 s); as consultas desse documento saem da conta, e nenhum rótulo precisou cair para o nível do arquivo.

**Atenção:** os rótulos (qual documento responde a cada pergunta) foram escritos a partir dos resumos, não por leitura humana do texto completo. Servem como linha de base técnica; para uso na dissertação, convém que a pessoa pesquisadora revise as 48 linhas.

### Trechos (M19) e busca lexical (M04)

42 consultas com resposta, BM25:

| Política de trechos | Trechos | recall@5 | recall@10 | MRR |
|---|---|---|---|---|
| seção/parágrafo, 800 caracteres | 2409 | 0,872 | 0,906 | 0,908 |
| seção/parágrafo, 1200 (padrão) | 1734 | 0,872 | 0,901 | 0,902 |
| seção/parágrafo, 1800 | 1258 | 0,901 | 0,913 | 0,911 |
| janela móvel 1200, sobreposição 200 | 1850 | 0,906 | 0,925 | 0,935 |

- Consultas específicas (35): recall@10 = 1,0 e MRR = 0,91. Consultas temáticas (7): recall@10 = 0,41, com MRR = 0,86 (o primeiro resultado costuma ser bom, mas os demais documentos do tema ficam fora dos 10 primeiros).
- A janela móvel ganha cerca de 0,03 de MRR, o que equivale a uma ou duas consultas em 42: dentro do ruído deste corpus. **Decisão:** manter a política seção/parágrafo de 1200 caracteres, porque ela preserva página e caminho de títulos, que a interface usa para "Ver na página do PDF".
- Ponto fraco claro: a consulta q39 ("letramento em inteligência artificial na educação") não achou nada, porque os documentos de T6 estão em inglês. É o caso que a busca híbrida com embeddings (M04) deve resolver.
- **Busca híbrida não medida:** exige uma chave Gemini, e o teste rodou sem chave. Para medir, use `--hybrid` com a sua chave (custo baixo) e compare com `docs/corpus/resultados/lexical-2026-11-25.json`.

### Limiar de evidência (M10 e M16)

Um trecho conta como "evidência forte" quando tem pelo menos *t* termos da pergunta. Resultado nos 10 primeiros trechos de cada consulta, incluindo as 6 sem resposta:

| t | precisão | cobertura | consultas sem resposta acusadas (de 6) |
|---|---|---|---|
| 1 | 0,563 | 0,977 | 5 |
| 2 | 0,630 | 0,942 | 1 |
| **3 (atual)** | **0,667** | **0,895** | **0** |
| 4 | 0,748 | 0,728 | 0 |
| 5 | 0,825 | 0,533 | 0 |

**Decisão:** o limiar 3 fica. É o menor valor que não acusa evidência em nenhuma das perguntas sem resposta e ainda cobre quase 90% dos trechos relevantes.

### Docling contra PyMuPDF (M01)

12 documentos, Docling 2.152.0, CPU do GitHub Actions:

- convertidos: 12 de 12; tabelas encontradas pelo Docling: 9, em 2 documentos;
- tempo médio por documento: 31,2 s (Docling) contra 0,16 s (PyMuPDF), cerca de 200 vezes mais lento;
- títulos detectados: 188 (Docling) contra 197 (PyMuPDF); num documento o PyMuPDF achou só 2 títulos e o Docling 9.

**Decisão:** o PyMuPDF continua como extrator padrão. O Docling só compensa para tabelas, que apareceram em poucos documentos; fica como extração opcional sob demanda, não no caminho de toda pesquisa.

### Reranker bge (M20)

O `BAAI/bge-reranker-v2-m3` (cerca de 568 milhões de parâmetros) rodou por mais de 68 minutos na CPU do GitHub Actions sem terminar as 42 consultas × 50 trechos, e a execução foi cancelada. **Decisão:** não entra no worker. Próximo teste, se fizer sentido: um modelo pequeno (InRanker-small, cerca de 60 milhões de parâmetros) ou reranking só dos 20 primeiros trechos, rodado no seu computador.
