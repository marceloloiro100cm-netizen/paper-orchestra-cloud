# Regras APA 7 para a IA (etapas de planejamento, redação e revisão)

Resumo prático do Publication Manual of the American Psychological Association, 7ª edição (2020),
aplicado ao LaTeX que o Scriptorium monta. A lista de referências sai sozinha das fontes do projeto
(biblatex-apa): nunca escreva a lista à mão.

## Citações no texto (autor-data)
- Parentética: `\parencite{chave}` gera (Silva, 2020). Narrativa: `\textcite{chave}` gera Silva (2020).
- Dois autores: (Silva & Souza, 2020) na parentética e "Silva e Souza (2020)" na narrativa.
- Três ou mais autores: "et al." desde a primeira citação. O estilo faz isso sozinho.
- Várias obras no mesmo parêntese: `\parencite{chave1,chave2}`, em ordem alfabética, separadas por ponto e vírgula.
- Citação direta sempre com página: `\parencite[p.~12]{chave}` ou `\textcite[p.~12]{chave}`.
  Até 39 palavras: entre aspas no parágrafo. Com 40 palavras ou mais: em bloco, com
  `\begin{quote} ... \end{quote}`, sem aspas, e a citação depois do ponto final.
- Fonte secundária (o equivalente ao apud): `\parencite[Freire, 1987, como citado em][]{chave_da_fonte_lida}`.
  Só a fonte que você leu entra nas referências.
- Prefira paráfrase. Na paráfrase a página é opcional.

## Estrutura
- Comece pelo `\begin{abstract} ... \end{abstract}`: um parágrafo de 150 a 250 palavras, sem citações.
  Termine o resumo com `\par\textit{Palavras-chave}: termo um, termo dois, termo três`.
- A introdução vem logo depois do resumo e NÃO leva título de seção: o Scriptorium repete o título do
  trabalho no alto da primeira página do texto.
- Depois use `\section{Método}`, `\section{Resultados}`, `\section{Discussão}` (artigo empírico ou revisão).
  Em artigo teórico, troque por seções temáticas, mantendo uma conclusão.
- Títulos sem número. Níveis: `\section` (nível 1), `\subsection` (nível 2), `\subsubsection` (nível 3),
  `\paragraph` (nível 4). Não pule níveis.

## Estilo
- Números de zero a nove por extenso; a partir de 10, algarismos (exceto no início de frase).
- Voz ativa e primeira pessoa são aceitas ("Analisamos..."). Evite linguagem com viés sobre pessoas e grupos.
- Tabelas e figuras: número em negrito e título em itálico acima; nota explicativa abaixo, começando por "Nota.".
- Siglas: por extenso na primeira vez, com a sigla entre parênteses.
