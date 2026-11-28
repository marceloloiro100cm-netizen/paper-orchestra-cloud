# DOI do software pelo Zenodo

Com o Zenodo ligado ao repositório, **cada Release do GitHub ganha um DOI** permanente, que pode ser citado na dissertação e no relatório do PTT. O Zenodo é mantido pelo CERN e é gratuito.

Os metadados (título, autor, licença, palavras-chave, resumo) vêm do [`CITATION.cff`](../../CITATION.cff), então mantenha esse arquivo correto antes de publicar uma versão.

## Ligar (uma vez, pelo responsável)

1. Entre em https://zenodo.org com **Log in → GitHub** e autorize o acesso.
2. No menu da conta, abra **GitHub**.
3. Na lista de repositórios, ative `marceloloiro100cm-netizen/scriptorium`.

As Releases anteriores (v1.0 a v1.1.2-piloto) **não** ganham DOI sozinhas: o Zenodo só arquiva as publicadas depois de ativado.

## Gerar o DOI de uma versão

1. Atualize `version` e `date-released` no `CITATION.cff` e a seção da versão no `CHANGELOG.md`.
2. Crie a tag e a Release no GitHub (por exemplo, `v1.2-piloto`).
3. Em alguns minutos, o Zenodo arquiva o código e mostra o DOI da versão e o **DOI conceitual**, que sempre aponta para a versão mais recente.
4. Acrescente o DOI ao `CITATION.cff` (campo `doi`) e um selo no README:

   ```markdown
   [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.NNNNNNN.svg)](https://doi.org/10.5281/zenodo.NNNNNNN)
   ```

## Qual DOI citar

- **Na dissertação**, para o produto em geral: o DOI conceitual.
- **No protocolo do estudo piloto**: o DOI da versão congelada usada na coleta, para que a pesquisa seja reproduzível.
