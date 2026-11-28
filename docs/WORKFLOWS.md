# Workflows do GitHub Actions

Os nomes começam pelo tipo, para a aba **Actions** ficar fácil de ler:

- **CI ·** confere cada PR e cada push. Não acessa a nuvem.
- **Deploy ·** publica em produção depois do merge em `main`.
- **Operação ·** roda sozinho, por agenda ou quando os scripts de proteção mudam.
- **Segurança ·** varreduras periódicas.
- **Manual ·** só roda quando alguém clica em *Run workflow*. Vários têm um modo `diagnosticar`, só de leitura, e um modo `aplicar`.

Todos os workflows que falam com o Google Cloud usam Workload Identity Federation (sem chave JSON) e só rodam neste repositório, na branch `main`.

| Workflow | Arquivo | Quando roda | O que faz |
|---|---|---|---|
| CI · Verificações | `check.yml` | todo push e PR | compila o Python, roda os testes, confere o registro de upstreams, valida JSON e JS e procura credenciais no repositório |
| CI · Acesso multiusuário e BYOK | `test-multiuser.yml` | PR que mexe em `api/`, `worker/`, `public/` ou nos scripts de acesso | testa o isolamento entre contas e a chave de cada pesquisador |
| CI · Build do worker com as normas | `formatos-build.yml` | PR (e push fora da `main`) que mexe em `formatos/`, no `worker/Dockerfile` ou na compilação | constrói a imagem do worker e compila um exemplo de cada norma |
| CI · OSV-Scanner no PR | `osv-scanner-pr.yml` | PR para `main` | procura vulnerabilidades conhecidas nas dependências novas |
| Deploy · API e worker | `deploy-services.yml` | merge em `main` que mexe em `api/`, `worker/` ou `formatos/` | constrói as duas imagens e atualiza o Cloud Run, preservando variáveis e dados |
| Deploy · Site | `deploy-scriptorium-alias.yml` | merge em `main` que mexe em `public/` ou `firebase.json` | publica `scriptoriummpie.web.app` |
| Deploy · Redirecionamento do endereço antigo | `deploy-hosting.yml` | merge que mexe em `hosting-redirect/` | mantém `paperorchestra-mestrado.web.app` redirecionando para o endereço atual |
| Operação · Backup semanal da biblioteca | `backup-weekly.yml` | domingo, 02h15 (Brasília) | copia o bucket de dados para o bucket de backup |
| Operação · Proteções e redução de acessos | `guardrails.yml` | quando mudam os scripts de proteção | reaplica backups do Firestore, alerta de orçamento e permissões mínimas do deployer |
| Operação · Vigiar upstreams | `watch-upstreams.yml` | segunda, 08h17 (Brasília) | procura versões novas, licenças divergentes e revisões vencidas; atualiza a issue de rastreio |
| Segurança · OSV-Scanner semanal | `osv-scanner-scheduled.yml` | segunda e a cada push em `main` | varredura completa das dependências |
| Manual · Backup: diagnóstico e configuração | `backup-config.yml` | manual | mostra ou aplica versionamento e retenção do bucket de backup |
| Manual · Bootstrap IAM do BYOK | `bootstrap-byok-iam.yml` | manual | cria os papéis IAM do modo BYOK (pendência da issue #17) |
| Manual · Corpus e avaliação da busca (G2) | `corpus-avaliacao.yml` | manual | coleta o corpus de referência e mede a qualidade da busca |
| Manual · Validar acesso ao Gemini Neon | `test-neon-access.yml` | manual, ou quando `smoke/neon/` muda | teste de fumaça do acesso do worker ao modelo Neon |

## Workflows removidos em 28/11/2026

Serviram uma vez e continuam no histórico do Git:

- `fix-auth-iam.yml`: deu à API a permissão de leitura de sessão no Firebase Auth (23/11/2026). O `scripts/deploy-cloud-shell.sh` já aplica a mesma permissão numa instalação nova.
- `testar-conexao-google.yml`: validou a identidade federada do GitHub no Google Cloud durante a configuração inicial.
- `deploy-manual.yml`: instalação completa pelo GitHub, nunca homologada. A instalação de referência é a do Cloud Shell ([IMPLANTACAO.md](IMPLANTACAO.md)).
