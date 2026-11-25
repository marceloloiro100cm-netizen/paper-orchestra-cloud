# Guia de escrita

Página `/guia/` do site: um passo a passo em oito etapas para estudantes que ficam perdidos na construção de um artigo. Vem do protótipo "Pesquisa Guiada v2" (M1 a M12 da disciplina), adaptado para produção.

## O que a pessoa encontra

- **Tipo de trabalho** no topo: *Artigo científico* (padrão) ou *Projeto de pesquisa (M1 a M12)*. As etapas 1 a 5 são iguais; as etapas 6 a 8 mudam:
  - Artigo: 6 Resultados e discussão, 7 Escrita do artigo (revista-alvo, título, resumo, palavras-chave e seções na ordem da revista), 8 Revisão final e submissão (checklist da revista, declaração de uso de IA M12, carta ao editor).
  - Projeto: 6 Produto (PTT), 7 Escrita e cronograma, 8 Validação final, como no protótipo.
- Em cada etapa: Entender (explicação, entregável, papel possível da IA, perguntas-guia), Preencher (campos com exemplo) e Conferir (critérios de autoverificação).
- Cadeia de coerência, conferência de relações (regras simples, sem IA), versões recuperáveis, dicionário, exemplos, exportações (artigo, resumo para a orientação, memorial) e backup JSON.

## Onde os dados ficam

- Sem login: só no navegador (`localStorage`, chave `scriptorium_pesquisa_guiada_v2_independente`).
- Com login no Scriptorium (conta autorizada): `public/guia/nuvem.js` salva o estado na conta 1,5 s depois de cada alteração.
  - `GET /api/guia/estado` devolve o estado guardado.
  - `PUT /api/guia/estado?base=<changedAt>` grava; responde 409 se outro dispositivo salvou depois de `base`. Nesse caso o guia abre a versão da conta e guarda a deste navegador em Versões.
  - Arquivos no bucket: `guia/{uid}/estado.json` e uma cópia por dia em `guia/{uid}/historico/AAAA-MM-DD.json`. Limite de 3 MB.
- O servidor não lê o conteúdo além de conferir o formato (`schema` 2, tipo `artigo` ou `projeto`).

## Arquivos

- `public/guia/index.html`: a página (um arquivo, script clássico). Gerada a partir do protótipo com estas mudanças: modo artigo, ponte `window.GuiaApp` para a nuvem, identidade azul e dourado (sem verde e vermelho), sem travessões e sem textos de "protótipo".
- `public/guia/nuvem.js`: login Google e sincronização.
- `api/guide_api.py`: rotas `/api/guia/estado`.
- `tests/test_guide_api.py`: rotas (no CI) e conferências estáticas da página.
