# Scriptorium MPIE — Guia de Replicabilidade e Protocolo do Produto Técnico-Tecnológico (PTT)

**Programa:** Mestrado Profissional em Informática na Educação (MPIE) — IFRS *Campus* Porto Alegre  
**Versão congelada de referência para coleta empírica:** `v1.0-piloto`  
**Endereço público:** https://scriptoriummpie.web.app/  
**Código aberto:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud

---

## 1. Caracterização do PTT segundo os critérios CAPES (2019)

| Critério | Evidência no Scriptorium MPIE (`v1.0-piloto`) |
| :--- | :--- |
| **Aderência** | Vinculado às Linhas 1 (*Tecnologia da Informação aplicada à educação*) e 2 (*Práxis educativa na sociedade digital*) do MPIE/IFRS. |
| **Impacto** | Reduz barreiras técnicas (LaTeX/ABNT/gestão de referências) e metodológicas para estudantes de graduação e pós-graduação — especialmente não nativos digitais —, preservando autoria humana e integridade científica. |
| **Aplicabilidade** | Acesso imediato via navegador (sem instalação local nem pagamento de API de IA pelo estudante); exportação em PDF ABNT e Word (`.docx`) editável para orientadores; link temporário somente leitura para mediação docente. |
| **Inovação** | Integra em um único ambiente aberto: (1) Guia de escrita passo a passo *sem IA* com ajuda progressiva em 3 níveis (*scaffolding* retirável); (2) protocolo aberto MCP conectando a IA do próprio estudante; (3) separação entre cabeças redatora, revisora e verificadora; (4) trava determinística de PDF final com conferência visual da capa do PDF; e (5) relatório transparente de proveniência (`proveniencia.json`). |
| **Complexidade** | Arquitetura distribuída em nuvem (Firebase Hosting/Auth, Cloud Firestore, Cloud Storage, FastAPI, Cloud Run Jobs com `abntex2`, servidor MCP, busca integrada OpenAlex/Crossref/BDTD-Oasisbr, exportação OOXML `.docx` e suíte de 350+ testes automatizados). |

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
   - O administrador autoriza os e-mails Google em **Minha conta → Convidar pesquisador**; os estudantes já podem usar o **Guia de escrita** imediatamente (inclusive antes da liberação da conta) e conectar sua própria IA gratuita/pessoal sem custo de API para a instituição.

---

## 3. Protocolo de Congelamento e Coleta Ética do Estudo Piloto (`v1.0-piloto`)

Para assegurar validade interna na avaliação empírica do mestrado:

1. **Versão congelada (`v1.0-piloto`):** durante o período de aplicação com estudantes de graduação e mestrado, nenhuma funcionalidade nova entra em produção (apenas correções emergenciais de segurança ou indisponibilidade, registradas em log).
2. **Consentimento e pseudonimização (CEP / LGPD):**
   - A participação na avaliação embutida (**Minha conta → Avaliação do Scriptorium**) é opcional e exige aceite explícito do **TCLE**.
   - As respostas são gravadas com código pseudonimizado (`P-XXXXXXXXXXXX` via SHA-256 com sal), sem e-mail, nome ou UID em texto puro.
   - O participante pode retirar o consentimento e excluir sua resposta em 1 clique a qualquer momento (`DELETE /api/piloto/avaliacao`).
3. **Instrumentos integrados:**
   - **Escala SUS (Brooke, 1996):** 10 itens Likert (1–5) com cálculo automático do escore (0–100).
   - **Percepção de autonomia e autoria:** 3 questões abertas fundamentadas na pedagogia da autonomia (Freire, 1996).
   - **Atividade de transferência de aprendizagem (sem IA):** mini-desafio de estruturação (problema, pergunta, objetivo geral e coleta de dados) para avaliar aprendizagem independente após o uso do ambiente.
4. **Exportação para análise:** o pesquisador administrador baixa o conjunto anonimizado em **Minha conta → Baixar dados anonimizados do piloto (.csv)** (`GET /api/admin/piloto/resumo.csv`).
