# Identidade visual do Scriptorium MPIE

Fonte oficial: `public/brand/scriptorium-logo.svg` (símbolo Pena-Circuito, enviado pelo responsável em 24/11/2026).

## Regra: duas cores

O site usa só as duas famílias do símbolo, mais neutros (fundo, bordas e texto).

| Família | Tons do símbolo | Uso no site |
|---|---|---|
| Azul MPIE | `#6CB2EA` `#2779C9` `#1159A4` `#0E4B8C` | Ações principais, links, seleção, estados de sucesso ("concluído", "verificada") |
| Dourado MPIE | `#FAD46B` `#F4B93B` `#DF9B1D` | Destaques, avisos, erros e ações que apagam (laranja da mesma família) |

Não usar verde nem vermelho. Sucesso é azul; erro, alerta e exclusão são dourado/laranja.

## Variáveis CSS (public/index.html)

- Azul: `--mpie-blue`, `--mpie-blue-hover`, `--mpie-blue-soft`, `--mpie-blue-text`, `--ok-*`.
- Dourado: `--mpie-gold`, `--mpie-gold-soft`, `--mpie-gold-text`, `--warn-*`.
- Laranja da família dourada: `--danger`, `--danger-strong`, `--danger-text`, `--danger-soft`, `--danger-border`, `--err-text`.

Cada variável tem versão clara e versão Modo Black. Texto sobre fundo colorido segue o contraste mínimo do WCAG AA (4,5:1); por isso o botão de apagar usa o laranja escuro `--danger-strong` no modo claro.
