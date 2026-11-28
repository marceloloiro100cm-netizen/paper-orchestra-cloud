# Scriptorium MPIE — Guia de Replicabilidade e Protocolo do Produto Técnico-Tecnológico (PTT)

**Programa:** Mestrado Profissional em Informática na Educação (MPIE) — IFRS *Campus* Porto Alegre  
**Versão congelada de referência para coleta empírica:** `v1.1-piloto` *(evolução da `v1.0-piloto` com Núcleo Zotero/ABNT, Fichamento, `/citar`, Tutor Socrático, Resumo PRISMA, Comentários da Orientação e Rubrica 0–15)*  
**Endereço público:** https://scriptoriummpie.web.app/  
**Código aberto:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud

---

## 1. Caracterização do PTT segundo os critérios CAPES (2019)

| Critério | Evidência no Scriptorium MPIE (`v1.1-piloto`) |
| :--- | :--- |
| **Aderência** | Vinculado à Linha 1 (*Tecnologia da Informação aplicada à educação*) com interface na Linha 2 (*Práxis educativa na sociedade digital*) do MPIE/IFRS e aderente à **IN IFRS nº 16/2026**. |
| **Impacto** | Busca reduzir barreiras situadas de compreensão metodológica, acesso técnico (LaTeX/ABNT/gestão de referências) e participação acadêmica para estudantes adultos de graduação e pós-graduação, preservando autoria humana, esforço cognitivo e integridade científica (a ser avaliado empiricamente no piloto). |
| **Aplicabilidade** | Acesso imediato via navegador (sem instalação local nem exigência de API paga pelo estudante); importação por DOI/BibTeX/RIS/Zotero com detecção de duplicatas; exportação em ABNT, `.bib`, `.ris`, PDF (`abntex2`) e Word editável (`.docx`); e link temporário para mediação docente com apontamentos por etapa sem conta. |
| **Inovação** | Integra em uma **Fonte Única de Verdade** (sem fragmentação de módulos): (1) Guia de escrita *sem IA* com apoio gradual em 3 níveis (*scaffolding* retirável), Mapa Visual do Fio Condutor e Autoavaliação pela Rubrica 0–15; (2) Biblioteca com fichamento por página, conferência humana de sustentação (3 níveis), resumo PRISMA ao vivo e ponte bidirecional `/citar` ↔ M4; (3) Modo **Tutor Socrático** no protocolo MCP (perguntas e pistas antes de sugerir texto) + registro de decisões autorais (*Aceitei / Adaptei / Rejeitei*) e Declaração automática **IN IFRS 16/2026**; (4) separação entre cabeças redatora, revisora e verificadora; e (5) trava determinística de PDF final com conferência visual da capa. |
| **Complexidade** | Arquitetura distribuída em nuvem (Firebase Hosting/Auth, Cloud Firestore, Cloud Storage, FastAPI, Cloud Run Jobs com `abntex2`, servidor MCP, busca integrada OpenAlex/Crossref/BDTD-Oasisbr, motor ABNT NBR 6023/10520 + RIS/BibTeX, exportação OOXML `.docx` e suíte de 365+ testes automatizados). |

---

## 2. Como outra instituição ou PPG pode replicar o Scriptorium

Qualquer curso de graduação, pós-graduação ou campus da Rede Federal pode subir sua própria instância independente seguindo 5 passos:

1. **Clonar o repositório e configurar o projeto GCP/Firebase:**
   - Criar projeto no Google Cloud com Firestore (modo nativo), Cloud Storage (bucket privado) e Firebase Authentication (login Google).
   - Definir a variável `ALLOWED_EMAILS` com o(s) e-mail(s) administrador(es) do programa.
2. **Publicar regras e índices do Firestore:**
   ```bash
   firebase deploy --only firestore:rules,firestore:indexes
   ```
   *(Todas as coleções são fechadas ao acesso direto do navegador; toda leitura/escrita passa pela API autenticada.)*
3. **Configurar a chave gratuita do OpenAlex no Secret Manager (recomendado):**
   ```bash
   PROJECT_ID=<seu-projeto-gcp> bash scripts/setup-openalex-key.sh
   ```
4. **Publicar API, Worker e Hosting:**
   - Configurar OIDC (Workload Identity Federation) para o GitHub Actions ou executar o deploy via Cloud Build (`api/Dockerfile`, `worker/Dockerfile`) e `firebase deploy --only hosting`.
5. **Convidar estudantes e orientadores:**
   - O administrador autoriza os e-mails Google em **Minha conta → Convidar pesquisador**; os estudantes já podem usar o **Guia de escrita** imediatamente e compartilhar o link temporário `/?orientacao=...` com seu(sua) orientador(a) para receber apontamentos por etapa sem precisar criar conta.

> **Nota sobre licenciamento:** antes do depósito definitivo no EduCAPES e no Repositório Institucional do IFRS, será concluída a conferência formal de titularidade e compatibilidade de licenças de dependências de terceiros (em especial `PyMuPDF`, distribuído sob AGPL-3.0).

---

## 3. Protocolo de Congelamento e Coleta Ética do Estudo Piloto (`v1.1-piloto`)

Para assegurar validade interna na avaliação empírica do mestrado:

1. **Versão congelada (`v1.1-piloto`):** durante a aplicação em campo (após aprovação no CEP/IFRS), nenhuma funcionalidade nova entra em produção — apenas correções emergenciais de segurança ou indisponibilidade, registradas em log.
2. **Consentimento e pseudonimização (Resolução CNS nº 510/2016 e LGPD):**
   - A participação na avaliação embutida (**Minha conta → Avaliação do Scriptorium**) é totalmente voluntária, desvinculada de notas, e exige aceite explícito do **TCLE**.
   - As respostas são gravadas com código pseudonimizado (`P-XXXXXXXXXXXX` via SHA-256 com sal), sem e-mail, nome ou UID em texto puro.
   - O participante pode retirar o consentimento e excluir sua resposta em 1 clique a qualquer momento (`DELETE /api/piloto/avaliacao`).
3. **Instrumentos integrados:**
   - **Escala SUS (Brooke, 1996):** 10 itens Likert (1–5) com cálculo automático do escore (0–100).
   - **Percepção de autonomia e autoria:** questões abertas + registro de decisões autorais (*Aceitei / Adaptei / Rejeitei*) fundamentadas em Freire (1996).
   - **Autoavaliação e transferência sem IA (Rubrica 0–15):** 5 dimensões conceituais (*Problema, Objetivos, Método, Evidências, Justificativa*) + 2 perguntas obrigatórias de justificativa metodológica.
4. **Exportação para análise:** o pesquisador administrador baixa o conjunto pseudonimizado em **Minha conta → Baixar dados anonimizados do piloto (.csv)** (`GET /api/admin/piloto/resumo.csv`).
