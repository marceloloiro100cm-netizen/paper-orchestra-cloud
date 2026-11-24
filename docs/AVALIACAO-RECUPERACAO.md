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

Os PDFs e as perguntas **não** devem ir para o repositório público.

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

