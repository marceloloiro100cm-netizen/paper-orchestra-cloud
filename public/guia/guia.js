// Guia de escrita do Scriptorium MPIE: redesenhado no padrão visual do site
// com UX calmo e acessível para a comunidade acadêmica não nativa digital.
(function(){
const CSS=`
:host {
  display: block;
  zoom: var(--font, 1);
  color: var(--text-primary, #0F1C2E);
  font-family: var(--font-sans, 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif);
}
* { box-sizing: border-box; }
.guia-body {
  color: var(--text-primary, #0F1C2E);
  font-family: var(--font-sans, 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif);
  line-height: 1.6;
  font-size: 1rem;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
button, input, textarea, select { font: inherit; }
button { cursor: pointer; }
button:disabled { opacity: 0.45; cursor: not-allowed; }
a { color: var(--mpie-blue-text, #105396); text-decoration: underline; text-underline-offset: 2px; }
:focus-visible { outline: 3px solid var(--mpie-blue, #1466B8); outline-offset: 3px; }
h2, h3, h4, p { margin-top: 0; }
h2, h3 { font-family: var(--font-serif, 'Newsreader', Georgia, serif); letter-spacing: -0.01em; color: var(--text-primary, #0F1C2E); }
h2 { font-size: clamp(1.35rem, 2.4vw, 1.7rem); font-weight: 600; line-height: 1.2; margin-bottom: 6px; }
h3 { font-size: 1.12rem; font-weight: 600; line-height: 1.28; margin-bottom: 8px; }
h4 { font-size: 0.96rem; font-weight: 700; margin-bottom: 6px; color: var(--text-primary, #0F1C2E); }

.muted { color: var(--text-secondary, #3B4F68); }
.subtle { color: var(--text-muted, #5F748E); }
.small { font-size: 0.9rem; line-height: 1.55; }
.tiny { font-size: 0.78rem; }
.eyebrow {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mpie-gold-text, #8A5A00);
}
.bold { font-weight: 700; }
.flex { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.spread { justify-content: space-between; }

/* Painéis no padrão exato do Scriptorium */
.panel {
  background: var(--bg-surface, #FFFFFF);
  border: 1px solid var(--border-main, #D8E3F0);
  border-radius: 18px;
  padding: 24px 26px;
  box-shadow: var(--shadow-sm, 0 2px 10px rgba(15, 28, 46, 0.04));
}

/* Botões no padrão exato do Scriptorium (alvos grandes >= 42px) */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 9px 16px;
  border-radius: 11px;
  border: 1px solid var(--border-main, #D8E3F0);
  background: var(--bg-subtle, #EFF4FA);
  color: var(--text-primary, #0F1C2E);
  font-weight: 600;
  font-size: 0.88rem;
  text-decoration: none;
  transition: background-color 150ms ease, border-color 150ms ease;
}
.btn:hover:not(:disabled) { border-color: var(--mpie-blue, #1466B8); }
.btn.primary {
  background: var(--mpie-blue, #1466B8);
  border-color: var(--mpie-blue, #1466B8);
  color: #FFFFFF;
}
:host([data-theme="dark"]) .btn.primary { color: #070A0F; }
.btn.primary:hover:not(:disabled) {
  background: var(--mpie-blue-hover, #0E4F92);
  border-color: var(--mpie-blue-hover, #0E4F92);
}
.btn.danger {
  color: var(--danger-text, #8F4A00);
  border-color: var(--danger-border, #F0B867);
  background: var(--danger-soft, #FFF3E0);
}
.btn.sm { min-height: 36px; padding: 6px 12px; font-size: 0.82rem; }
.btn.ghost { background: transparent; border-color: transparent; color: var(--mpie-blue-text, #105396); padding: 6px 10px; }
.btn.ghost:hover:not(:disabled) { background: var(--mpie-blue-soft, #E8F2FC); }

/* Pílulas e seletor segmentado (iguais aos do Scriptorium) */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
  background: var(--bg-subtle, #EFF4FA);
  color: var(--text-secondary, #3B4F68);
  border: 1px solid var(--border-main, #D8E3F0);
  white-space: nowrap;
}
.pill.gold { background: var(--mpie-gold-soft, #FEF7E4); color: var(--mpie-gold-text, #8A5A00); border-color: var(--warn-border, #F4D88A); }
.pill.good { background: var(--ok-bg, #E8F2FC); color: var(--ok-text, #105396); border-color: var(--ok-border, #B9D4F0); }
.pill.warn { background: var(--warn-bg, #FFFBEB); color: var(--warn-text, #7A4F00); border-color: var(--warn-border, #F4D88A); }

.segmented {
  display: inline-flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
  gap: 4px;
  flex-wrap: wrap;
}
.seg-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary, #3B4F68);
  padding: 8px 14px;
  border-radius: 9px;
  font-size: 0.86rem;
  font-weight: 650;
  min-height: 38px;
}
.seg-btn.active { background: var(--mpie-blue, #1466B8); color: #FFFFFF; }
:host([data-theme="dark"]) .seg-btn.active { color: #070A0F; }

/* Cabeçalho calmo do Guia */
.guide-top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-soft, #E8EFF7);
}
.guide-top-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
}
.status-bar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 11px;
  background: var(--ok-bg, #E8F2FC);
  border: 1px solid var(--ok-border, #B9D4F0);
  color: var(--ok-text, #105396);
  font-size: 0.86rem;
  font-weight: 600;
}
.status-bar.alert {
  background: var(--danger-soft, #FFF3E0);
  border-color: var(--danger-border, #F0B867);
  color: var(--danger-text, #8F4A00);
}
.progress-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  color: var(--text-secondary, #3B4F68);
  font-weight: 600;
}
.progress-track {
  width: 130px;
  height: 8px;
  border-radius: 999px;
  background: var(--border-soft, #E8EFF7);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--mpie-blue, #1466B8);
  transition: width 200ms ease;
}

/* Menu retrátil "Mais ferramentas": mantém o topo limpo para não assustar iniciantes */
.tools-menu { margin-top: 12px; }
.tools-menu > summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  list-style: none;
  font-size: 0.86rem;
  font-weight: 650;
  color: var(--mpie-blue-text, #105396);
  padding: 6px 10px;
  border-radius: 9px;
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
}
.tools-menu > summary::-webkit-details-marker { display: none; }
.tools-menu-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
}

/* Ponte gentil com artigo ativo em Seus artigos */
.project-bridge {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
  padding: 11px 14px;
  border-radius: 12px;
  background: var(--mpie-blue-soft, #E8F2FC);
  border: 1px solid var(--ok-border, #B9D4F0);
  font-size: 0.86rem;
  color: var(--text-primary, #0F1C2E);
}

/* Fio condutor (substitui o bloco azul escuro antigo por faixa editorial calma) */
.chain-card {
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
  border-left: 4px solid var(--mpie-gold, #F4B93B);
  border-radius: 14px;
  padding: 14px 18px;
}
.chain-links { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
.chain-link {
  border: 1px solid var(--border-main, #D8E3F0);
  background: var(--bg-surface, #FFFFFF);
  color: var(--text-secondary, #3B4F68);
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 0.8rem;
  font-weight: 600;
}
.chain-link:hover { border-color: var(--mpie-blue, #1466B8); color: var(--mpie-blue-text, #105396); }
.chain-link.filled {
  background: var(--ok-bg, #E8F2FC);
  border-color: var(--ok-border, #B9D4F0);
  color: var(--ok-text, #105396);
}
.chain-arrow { color: var(--text-muted, #5F748E); font-size: 0.82rem; }

/* Grade das 8 etapas no estilo .step-btn do Scriptorium */
.stations {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.station {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  text-align: left;
  padding: 13px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-main, #D8E3F0);
  background: var(--bg-surface, #FFFFFF);
  color: var(--text-primary, #0F1C2E);
  min-height: 76px;
  transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
}
.station:hover { border-color: var(--mpie-blue, #1466B8); }
.station.selected {
  background: var(--mpie-blue-soft, #E8F2FC);
  border-color: var(--mpie-blue, #1466B8);
  box-shadow: inset 0 0 0 1px var(--mpie-blue, #1466B8);
}
.station .num {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.78rem;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--mpie-gold-soft, #FEF7E4);
  color: var(--mpie-gold-text, #8A5A00);
}
.station.done .num { background: var(--ok-bg, #E8F2FC); color: var(--ok-text, #105396); }
.station.selected .num { background: var(--mpie-blue, #1466B8); color: #FFFFFF; }
:host([data-theme="dark"]) .station.selected .num { color: #070A0F; }
.station-info { min-width: 0; flex: 1; }
.station b { display: block; font-size: 0.88rem; line-height: 1.25; }
.station small { display: block; font-size: 0.76rem; color: var(--text-muted, #5F748E); margin-top: 3px; }
.station.selected small { color: var(--mpie-blue-text, #105396); font-weight: 600; }

/* Cartão da etapa atual */
.sheet { scroll-margin-top: 88px; }
.sheet-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border-soft, #E8EFF7);
}
.tabbar {
  display: inline-flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
  gap: 4px;
  flex-wrap: wrap;
}
.tabbar button {
  border: none;
  border-radius: 9px;
  background: transparent;
  padding: 9px 14px;
  min-height: 40px;
  color: var(--text-secondary, #3B4F68);
  font-size: 0.88rem;
  font-weight: 650;
}
.tabbar button[aria-selected="true"] {
  background: var(--mpie-blue, #1466B8);
  color: #FFFFFF;
}
:host([data-theme="dark"]) .tabbar button[aria-selected="true"] { color: #070A0F; }

.section-max { max-width: 820px; }
.section-gap > * + * { margin-top: 18px; }

.card {
  background: var(--bg-subtle, #EFF4FA);
  border: 1px solid var(--border-main, #D8E3F0);
  border-radius: 14px;
  padding: 18px 20px;
}
.card.white { background: var(--bg-surface, #FFFFFF); }
.card.warning { background: var(--warn-bg, #FFFBEB); border-color: var(--warn-border, #F4D88A); }
.lead { font-size: 1.03rem; line-height: 1.65; color: var(--text-primary, #0F1C2E); }
.callouts { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.notice {
  padding: 13px 16px;
  border-radius: 12px;
  border-left: 3px solid var(--mpie-gold, #F4B93B);
  background: var(--bg-subtle, #EFF4FA);
  font-size: 0.88rem;
  color: var(--text-secondary, #3B4F68);
  line-height: 1.55;
}
.notice strong { color: var(--text-primary, #0F1C2E); }

/* Campos de escrita confortáveis em 1 coluna (fácil de ler e preencher sem se perder) */
.fieldgroup { display: flex; flex-direction: column; gap: 14px; }
.field {
  padding: 16px 18px;
  border: 1px solid var(--border-main, #D8E3F0);
  border-radius: 14px;
  background: var(--bg-subtle, #EFF4FA);
}
.field-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.field label { font-weight: 700; font-size: 0.96rem; color: var(--text-primary, #0F1C2E); display: block; }
.field .hint { font-size: 0.86rem; color: var(--text-secondary, #3B4F68); margin: 0 0 10px; line-height: 1.48; }
.field input, .field textarea, .field select, .form-control {
  width: 100%;
  padding: 11px 13px;
  background: var(--bg-input, #F8FAFD);
  border: 1.5px solid var(--border-main, #D8E3F0);
  border-radius: 11px;
  color: var(--text-primary, #0F1C2E);
  font-size: 0.96rem;
  min-height: 44px;
  line-height: 1.5;
}
.field textarea { min-height: 108px; resize: vertical; }
.field input:focus, .field textarea:focus, .field select:focus, .form-control:focus {
  outline: none;
  border-color: var(--mpie-blue, #1466B8);
  box-shadow: 0 0 0 3px var(--mpie-blue-soft, #E8F2FC);
}

/* Blocos repetíveis */
.repeat-block {
  padding: 18px;
  border-radius: 16px;
  border: 1px solid var(--border-main, #D8E3F0);
  background: var(--bg-subtle, #EFF4FA);
}
.repeat-intro { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.record {
  border: 1px solid var(--border-main, #D8E3F0);
  border-radius: 14px;
  padding: 14px 16px;
  margin-top: 12px;
  background: var(--bg-surface, #FFFFFF);
}
.record > summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-weight: 700;
  font-size: 0.94rem;
}
.record > summary::-webkit-details-marker { display: none; }
.record[open] > summary { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border-soft, #E8EFF7); }
.record-title { flex: 1; }
.record-index {
  background: var(--mpie-blue-soft, #E8F2FC);
  color: var(--mpie-blue-text, #105396);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.74rem;
  font-weight: 700;
  border-radius: 8px;
  width: 26px;
  height: 26px;
  display: inline-grid;
  place-items: center;
}
.record-controls { display: flex; justify-content: flex-end; margin-top: 12px; }

/* Checklist na aba Conferir */
.check-card {
  display: grid;
  grid-template-columns: 26px 1fr;
  gap: 12px;
  border: 1px solid var(--border-main, #D8E3F0);
  border-radius: 14px;
  padding: 15px 16px;
  background: var(--bg-subtle, #EFF4FA);
  margin: 10px 0;
}
.check-card input[type=checkbox] { accent-color: var(--mpie-blue, #1466B8); width: 20px; height: 20px; margin-top: 2px; cursor: pointer; }
.check-card label { cursor: pointer; font-weight: 650; font-size: 0.94rem; color: var(--text-primary, #0F1C2E); }
.check-note {
  width: 100%;
  padding: 9px 11px;
  border-radius: 9px;
  border: 1px solid var(--border-main, #D8E3F0);
  background: var(--bg-input, #F8FAFD);
  color: var(--text-primary, #0F1C2E);
  margin-top: 8px;
  font-size: 0.88rem;
}
.action-footer {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--border-soft, #E8EFF7);
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.status-steps { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.status-step { font-size: 0.78rem; border: 1px solid var(--border-main, #D8E3F0); border-radius: 999px; padding: 4px 10px; color: var(--text-muted, #5F748E); background: var(--bg-surface, #FFFFFF); }
.status-step.on { border-color: var(--mpie-blue, #1466B8); background: var(--ok-bg, #E8F2FC); color: var(--ok-text, #105396); font-weight: 700; }

.audit-list { padding: 0; list-style: none; margin: 12px 0 0; }
.audit-list li { border: 1px solid var(--border-main, #D8E3F0); border-radius: 12px; margin: 9px 0; padding: 12px 14px; background: var(--bg-subtle, #EFF4FA); font-size: 0.88rem; }
.audit-list li strong { display: block; margin-bottom: 4px; }
.audit-list li.warn { border-left: 4px solid var(--mpie-gold, #F4B93B); }
.audit-list li.info { border-left: 4px solid var(--mpie-blue, #1466B8); }
.audit-list li.good { border-left: 4px solid var(--mpie-blue, #1466B8); }
.audit-list li.high { border-left: 4px solid var(--danger-strong, #A85400); }

.timeline-wrap { overflow-x: auto; }
.table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.table th, .table td { border-bottom: 1px solid var(--border-main, #D8E3F0); padding: 10px 12px; text-align: left; vertical-align: top; }
.table th { color: var(--text-secondary, #3B4F68); font-weight: 700; background: var(--bg-subtle, #EFF4FA); }
.table td { overflow-wrap: anywhere; }
.empty { color: var(--text-muted, #5F748E); font-style: italic; }
.helper-list { margin: 0; padding-left: 22px; line-height: 1.75; }
.helper-list li { margin-bottom: 6px; }
.group-title { margin: 18px 0 10px; }
.test-note { font-size: 0.8rem; color: var(--text-muted, #5F748E); margin-top: 6px; }
.tag { font-size: 0.76rem; font-weight: 600; border-radius: 8px; padding: 3px 8px; background: var(--bg-surface, #FFFFFF); border: 1px solid var(--border-main, #D8E3F0); color: var(--text-secondary, #3B4F68); }
.example-text { white-space: pre-wrap; line-height: 1.6; background: var(--bg-subtle, #EFF4FA); border: 1px solid var(--border-main, #D8E3F0); padding: 14px 16px; border-radius: 12px; font-size: 0.92rem; }

/* Modais no padrão exato de #config-modal do Scriptorium */
.modal-wrap {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(7, 10, 15, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.modal {
  background: var(--bg-surface, #FFFFFF);
  color: var(--text-primary, #0F1C2E);
  border-radius: 18px;
  padding: 22px 24px;
  max-width: 740px;
  width: 100%;
  max-height: 88vh;
  overflow: auto;
  border: 1px solid var(--border-main, #D8E3F0);
  box-shadow: 0 20px 55px rgba(0, 0, 0, 0.35);
}
.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid var(--border-soft, #E8EFF7);
  margin-bottom: 16px;
  padding-bottom: 12px;
}
.modal-title { font-family: var(--font-serif, Georgia, serif); font-size: 1.32rem; font-weight: 600; }
.modal-footer {
  border-top: 1px solid var(--border-soft, #E8EFF7);
  margin-top: 18px;
  padding-top: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.modal-scroll { max-height: 54vh; overflow: auto; padding-right: 4px; }

#toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 90;
  max-width: min(420px, 90vw);
  background: var(--mpie-blue, #1466B8);
  color: #FFFFFF;
  padding: 12px 16px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 0.88rem;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.25);
  display: none;
}
:host([data-theme="dark"]) #toast { color: #070A0F; }
#printArea { display: none; }
[hidden] { display: none !important; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }

@media (max-width: 980px) {
  .stations { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .panel { padding: 16px; border-radius: 14px; }
  .callouts { grid-template-columns: 1fr; }
  .tabbar { width: 100%; }
  .tabbar button { flex: 1; padding: 8px 6px; font-size: 0.82rem; }
  .action-footer { flex-direction: column; }
  .action-footer .btn { width: 100%; }
  .modal { padding: 16px; }
}
@media (max-width: 440px) {
  .stations { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; }
}
@page { size: A4; margin: 17mm 14mm; }
@media print {
  .guia-body { background: #fff !important; color: #111 !important; font-size: 10pt !important; }
  .guia-screen, .modal-wrap, #toast { display: none !important; }
  #printArea { display: block !important; position: static; background: white; color: #111; }
  #printArea h1 { font-size: 20pt; margin-bottom: 5mm; }
  #printArea h2 { font-size: 14pt; margin: 7mm 0 3mm; }
  #printArea h3 { font-size: 11pt; margin: 5mm 0 1mm; }
  #printArea .print-p { white-space: pre-wrap; line-height: 1.45; margin: 1mm 0 4mm; }
  #printArea section { break-inside: avoid-page; }
  #printArea .small { font-size: 9pt; color: #555; }
  #printArea table { font-size: 9pt; border-collapse: collapse; width: 100%; }
  #printArea th, #printArea td { border: 1px solid #bbb; padding: 3mm; }
  #printArea .print-box { border: 1px solid #aaa; padding: 4mm; margin: 3mm 0; break-inside: avoid-page; }
}
`;

const MARKUP=`
<div class="guia-screen">
  <section class="panel" aria-labelledby="guia-heading">
    <div class="guide-top">
      <div>
        <h2 id="guia-heading">Guia de escrita passo a passo</h2>
        <p class="small muted" style="margin:0">Construa seu texto em 8 etapas calmas. Tudo o que você escreve fica salvo automaticamente.</p>
      </div>
      <div class="flex">
        <div class="segmented" role="radiogroup" aria-label="Tipo de trabalho">
          <button type="button" class="seg-btn" id="modeArtigo" role="radio" aria-checked="true" data-action="set-tipo" data-tipo="artigo">Artigo científico</button>
          <button type="button" class="seg-btn" id="modeProjeto" role="radio" aria-checked="false" data-action="set-tipo" data-tipo="projeto">Projeto de pesquisa</button>
        </div>
        <button type="button" class="btn primary" data-action="export">Baixar ou imprimir</button>
        <button type="button" class="btn" data-action="help">Como usar</button>
      </div>
    </div>

    <div class="guide-top-meta">
      <span id="saveStatus" class="status-bar" role="status" aria-live="polite">Carregando…</span>
      <div class="progress-wrap">
        <span id="projectInfo">0/8 etapas preenchidas</span>
        <div class="progress-track" aria-hidden="true"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
      </div>
    </div>

    <div id="projectBridge" class="project-bridge" hidden></div>

    <details class="tools-menu">
      <summary>Mais ferramentas (dicionário, exemplos, versões e tamanho da letra) ▾</summary>
      <div class="tools-menu-grid">
        <button type="button" class="btn sm" data-action="audit">Conferir coerência</button>
        <button type="button" class="btn sm" data-action="examples">Ver exemplos prontos</button>
        <button type="button" class="btn sm" data-action="glossary">Dicionário de termos</button>
        <button type="button" class="btn sm" data-action="versions">Versões salvas</button>
        <button type="button" class="btn sm" data-action="backup">Cópia de segurança</button>
        <button type="button" class="btn sm" data-action="settings">Tamanho da letra (Aa)</button>
      </div>
    </details>
  </section>

  <section class="chain-card" aria-label="Fio condutor do trabalho">
    <div class="flex spread">
      <div>
        <div class="eyebrow">Fio condutor do seu texto</div>
        <div class="small muted">Clique em qualquer ponto para ir direto à etapa correspondente.</div>
      </div>
      <button type="button" class="btn sm" data-action="audit">Conferir coerência</button>
    </div>
    <nav id="chain" class="chain-links" aria-label="Etapas do fio condutor"></nav>
  </section>

  <nav id="stations" class="stations" aria-label="Escolha uma das oito etapas"></nav>

  <section class="panel sheet" id="stageSheet">
    <div id="stageHeader" class="sheet-head"></div>
    <div id="stageBody"></div>
  </section>
</div>
<div id="modalMount"></div>
<div id="toast" role="status" aria-live="polite"></div>
<div id="printArea"></div>
<input type="file" id="importJSON" accept=".json,application/json" hidden aria-label="Restaurar cópia de segurança JSON">
`;
function montar(host){
if(host.shadowRoot)return;
const HOST=host;
const R=host.attachShadow({mode:'open'});
R.innerHTML='<style>'+CSS+'</style><div class="guia-body">'+MARKUP+'</div>';

const temaDoSite=()=>document.documentElement.getAttribute('data-theme')==='black'?'dark':'light';
new MutationObserver(()=>{HOST.dataset.theme=temaDoSite();}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});


'use strict';
// Conteúdo pedagógico preservado da versão enviada, enriquecido por modelos específicos.
const STAGES = [
      {
        id: 1,
        shortTitle: 'Preparação',
        title: 'Preparação do Projeto',
        models: 'Ficha Inicial',
        deliverable: 'Ficha inicial de projeto: identificação, contexto, demanda e prazo.',
        objective: 'Organizar o ponto de partida antes de formular o problema de pesquisa.',
        plainExplain: 'Antes de escrever o projeto, anote quem você é, onde sua inquietação nasceu e quanto tempo você tem. Escreva com suas próprias palavras, sem pressa: você poderá ajustar tudo depois.',
        aiRole: 'Faz perguntas para esclarecer o contexto e ajudar a delimitar a inquietação, mas nunca escolhe o tema no seu lugar.',
        guidingQuestions: [
          'Que situação chamou sua atenção na prática profissional ou acadêmica?',
          'Por que esse contexto merece ser compreendido?',
          'Qual é a relação possível entre essa situação e seu programa de pós-graduação?'
        ],
        fields: [
          { key: 'tituloProvisorio', label: 'Nome provisório do projeto', plainHint: 'Um título temporário para identificar sua ideia. Você poderá refiná-lo mais adiante.', placeholder: 'Ex.: Jogos digitais na aprendizagem da leitura no 2º ano', type: 'text', example: 'Uso de jogos digitais na aprendizagem da leitura no 2º ano' },
          { key: 'programaInstituicao', label: 'Programa de pós-graduação, instituição e orientador(a)', plainHint: 'Informe seu curso, instituição e área/linha de pesquisa (se já definidos).', placeholder: 'Ex.: MPIE, IFRS Campus Porto Alegre · Linha de Tecnologias Educacionais', type: 'text', example: 'MPIE, IFRS Campus Porto Alegre · Área: Informática na Educação' },
          { key: 'ambienteOrigem', label: 'Ambiente profissional ou educacional de origem', plainHint: 'Onde acontece a situação que motivou seu interesse (escola, turma, empresa, setor)?', placeholder: 'Ex.: Escola municipal de Ensino Fundamental, turmas de 2º ano', type: 'text', example: 'Turmas de 2º ano do Ensino Fundamental em escola pública municipal' },
          { key: 'inquietacaoLivre', label: 'Descrição livre da inquietação inicial', plainHint: 'Conte de forma simples o que você observou e por que isso incomoda ou desperta curiosidade.', placeholder: 'Escreva com suas próprias palavras...', type: 'textarea', example: 'Observo que parte dos estudantes do 2º ano demonstra desmotivação nas atividades tradicionais de leitura, mas se engaja rapidamente quando utiliza recursos interativos no tablet.' },
          { key: 'prazoRestricoes', label: 'Prazo, recursos e restrições iniciais', plainHint: 'Anote seu prazo até a defesa e eventuais limites de tempo, equipamentos ou acesso.', placeholder: 'Ex.: 18 meses; acesso a 1 laboratório com 15 tablets', type: 'text', example: 'Qualificação em 10 meses e defesa em 20 meses; acesso a 1 laboratório com 15 tablets.' }
        ],
        criteria: [
          'O contexto de pesquisa está identificado com clareza.',
          'Há uma inquietação inicial escrita com minhas próprias palavras.',
          'Os limites preliminares de tempo, recursos e acesso foram considerados.'
        ]
      },
      {
        id: 2,
        shortTitle: 'Tema e Problema',
        title: 'Tema, Problema e Questão de Pesquisa',
        models: 'M1',
        deliverable: 'M1 preenchido: tema, situação problemática, delimitação, pergunta única e lacuna provisória.',
        objective: 'Transformar uma inquietação em uma pergunta única, relevante e investigável.',
        plainExplain: 'Aqui vamos afunilar sua ideia: dar um nome curto ao tema, explicar o problema, definir o que fica de fora e chegar em UMA pergunta que comece com "Como", "De que maneira" ou "Em que medida".',
        aiRole: 'Sugere formas de afunilar o recorte e avisa se a pergunta pode ser respondida só com "sim" ou "não". A decisão é sempre sua.',
        guidingQuestions: [
          'Quem é afetado por esse problema, onde ele ocorre e por quais indícios você o percebe?',
          'O que precisa ficar DE FORA para você conseguir terminar a pesquisa no prazo?',
          'Sua pergunta pede explicação ("como", "em que medida") ou pode ser respondida com "sim/não"?'
        ],
        fields: [
          { key: 'tema', label: 'Tema da pesquisa (expressão curta)', plainHint: 'Use de 2 a 5 palavras. O tema não é o título nem a pergunta.', placeholder: 'Ex.: Alfabetização e Tecnologia', type: 'text', example: 'Alfabetização e Tecnologia' },
          { key: 'problema', label: 'Situação problemática (o que está acontecendo)', plainHint: 'Explique em poucas linhas a dificuldade, conflito ou necessidade observada na prática.', placeholder: 'Ex.: Baixo engajamento e dificuldade na fluência leitora...', type: 'textarea', example: 'Estudantes do 2º ano apresentam dificuldade na fluência leitora e baixo engajamento com materiais impressos repetitivos, enquanto professores relatam falta de roteiros pedagógicos para integrar jogos digitais.' },
          { key: 'delimitacao', label: 'Recorte e o que ficará de fora', plainHint: 'Defina sujeitos, local, período e diga explicitamente o que você NÃO vai investigar.', placeholder: 'Ex.: Foco em leitura no 2º ano por 1 semestre; ficam de fora outras séries', type: 'textarea', example: 'Recorte: uso de um jogo digital de leitura com crianças do 2º ano durante um semestre. Ficam de fora outras séries, produção textual escrita e uso doméstico.' },
          { key: 'pergunta', label: 'Pergunta de pesquisa (única e investigável)', plainHint: 'Prefira "Como...", "De que maneira..." ou "Em que medida...". Evite perguntas de Sim ou Não.', placeholder: 'Ex.: Em que medida o uso de determinado jogo pode contribuir para...', type: 'textarea', example: 'Em que medida o uso de um jogo digital educativo em contexto escolar pode contribuir para a aprendizagem da leitura em crianças do 2º ano do Ensino Fundamental?' },
          { key: 'lacuna', label: 'Lacuna provisória (o que ainda falta compreender)', plainHint: 'Indique o que parece pouco explorado. Não declare "ninguém estudou isso" antes da revisão na Etapa 3.', placeholder: 'Ex.: Faltam estudos sobre protocolos de mediação docente em turmas numerosas...', type: 'text', example: 'Faltam estudos aplicados sobre protocolos de mediação docente no uso de jogos digitais de leitura em turmas numerosas de escola pública.' }
        ],
        criteria: [
          'O tema é uma expressão curta, e não uma frase extensa.',
          'O problema contém contexto, sujeitos e evidências iniciais.',
          'A delimitação informa claramente o que ficará de fora.',
          'Existe uma única pergunta respondível no prazo do curso.',
          'A lacuna provisória foi registrada (pronta para conferir na Etapa 3).'
        ]
      },
      {
        id: 3,
        shortTitle: 'Revisão e Teoria',
        title: 'Revisão de Literatura e Referencial Teórico',
        models: 'M2–M6',
        deliverable: 'M2 a M6: descritores, protocolo de busca, quadro de leitura, síntese e Quadro 1 (Referencial).',
        objective: 'Compreender o que já foi pesquisado, confirmar a lacuna e definir os conceitos que sustentam sua análise.',
        plainExplain: 'Atenção à diferença: Revisão de literatura = o que outros estudos já investigaram sobre o tema; Referencial teórico = os conceitos e 2–3 autores centrais usados como "lente" para interpretar seus dados.',
        aiRole: 'Pode ajudar a organizar sinônimos em português/inglês e comparar conceitos; buscar nas bases e ler os estudos é responsabilidade humana.',
        guidingQuestions: [
          'Outra pessoa conseguiria repetir exatamente as suas buscas nas bases usando o seu protocolo?',
          'O que os 5 a 8 estudos principais têm em comum e onde eles divergem?',
          'Os autores escolhidos no Referencial Teórico realmente ajudam a analisar a sua pergunta?'
        ],
        fields: [
          { key: 'descritores', label: 'Blocos de descritores em Português e Inglês (M2)', plainHint: 'Palavras-chave combinadas com AND / OR para buscar nas bases acadêmicas.', placeholder: 'Ex.: ("alfabetização" OR "leitura") AND ("jogos digitais")', type: 'text', example: 'PT: ("alfabetização" OR "leitura") AND ("jogos digitais" OR "gamificação") | EN: ("literacy" OR "reading") AND ("digital games")' },
          { key: 'basesProtocolo', label: 'Bases de busca, período e critérios de seleção (M3)', plainHint: 'Ex.: Catálogo CAPES, Periódicos CAPES, SciELO, ERIC, Scopus, Web of Science.', placeholder: 'Ex.: SciELO e Periódicos CAPES (2021–2026), artigos revisados por pares', type: 'text', example: 'Catálogo de Teses CAPES, Portal de Periódicos CAPES e SciELO; período 2021–2026; inclusão: estudos empíricos em Ensino Fundamental; exclusão: revisões sem intervenção.' },
          { key: 'sinteseRevisao', label: 'Síntese dos 5 a 8 estudos-chave lidos (M4–M5)', plainHint: 'Resuma o que já se sabe, quais métodos são frequentes e o que segue em aberto.', placeholder: 'Ex.: Os estudos mostram ganho de motivação, mas divergem sobre...', type: 'textarea', example: 'Dos 6 estudos lidos em profundidade, 5 apontam aumento do engajamento inicial com jogos digitais, mas divergem sobre a retenção da leitura sem mediação estruturada do professor.' },
          { key: 'autoresConceitos', label: 'Referencial Teórico: conceitos e 2–3 autores centrais (M6 / Quadro 1)', plainHint: 'Apresente separado da revisão: informe Conceito + Autor + Contribuição para sua análise.', placeholder: 'Ex.: Magda Soares (alfabetização e letramento); Vygotsky (mediação)', type: 'textarea', example: '1) Alfabetização e Letramento: Magda Soares (lente para avaliar apropriação da leitura); 2) Mediação e aprendizagem lúdica: Vygotsky / Kishimoto (análise das interações mediadas pelo jogo).' }
        ],
        criteria: [
          'O protocolo permite que outra pessoa repita minhas buscas.',
          'Realizei leitura aprofundada de 5 a 8 estudos relevantes.',
          'A síntese sustenta ou corrige a lacuna e a pergunta (se mudou, registrei nova versão).',
          'O referencial traz conceitos e 2–3 autores centrais hierarquizados.',
          'Revisão de literatura e referencial teórico estão apresentados separadamente.'
        ]
      },
      {
        id: 4,
        shortTitle: 'Objetivos',
        title: 'Objetivos e Justificativa',
        models: 'M7',
        deliverable: 'M7: objetivo geral, 3–4 objetivos específicos, hipóteses ou questões norteadoras e justificativa.',
        objective: 'Converter a questão de pesquisa em objetivo geral e etapas investigativas coerentes, justificando sua relevância.',
        plainExplain: 'Dica importante: "Aplicar questionário" é uma tarefa operacional. Um objetivo específico sempre produz conhecimento. Por exemplo: "Identificar as percepções dos participantes".',
        aiRole: 'Questiona se o objetivo geral realmente responde à pergunta da Etapa 2 e sinaliza quando um objetivo parece apenas uma tarefa.',
        guidingQuestions: [
          'Se o seu Objetivo Geral for alcançado, a pergunta da Etapa 2 estará respondida?',
          'Seus objetivos específicos geram conhecimento ou são apenas passos operacionais?',
          'Quem se beneficia dos resultados desta investigação?'
        ],
        fields: [
          { key: 'objetivoGeral', label: 'Objetivo Geral (verbo no infinitivo)', plainHint: 'Uma frase direta começando com Analisar, Compreender, Investigar, Caracterizar ou Examinar.', placeholder: 'Ex.: Analisar em que medida o uso mediado de jogos digitais contribui...', type: 'textarea', example: 'Analisar em que medida o uso mediado de um jogo digital educativo contribui para a aprendizagem da leitura em crianças do 2º ano do Ensino Fundamental.' },
          { key: 'objetivosEspecificos', label: 'Objetivos Específicos (3 a 4 etapas de investigação)', plainHint: 'Escreva um por linha. Pense nos degraus de conhecimento até responder à pergunta central.', placeholder: '1. Caracterizar...\n2. Descrever...\n3. Avaliar...', type: 'textarea', example: '1. Caracterizar o nível inicial de fluência leitora e engajamento dos estudantes do 2º ano.\n2. Descrever como ocorre a mediação docente durante as sessões com o jogo digital.\n3. Avaliar a evolução da leitura e a percepção pedagógica após a intervenção.' },
          { key: 'hipotesesQuestoes', label: 'Hipóteses ou questões norteadoras', plainHint: 'Respostas provisórias ou subperguntas alinhadas ao desenho da pesquisa.', placeholder: 'Ex.: O jogo digital gera avanço consistente apenas com mediação estruturada?', type: 'text', example: 'Pressuposto: o jogo digital potencializa a fluência leitora quando articulado a roteiros breves de mediação docente.' },
          { key: 'justificativa', label: 'Justificativa (relevância, contribuição e viabilidade)', plainHint: 'Explique por que o estudo importa na prática e na ciência, e por que é realizável no prazo.', placeholder: 'Ex.: Atende demanda concreta da rede pública por estratégias viáveis...', type: 'textarea', example: 'A pesquisa responde a uma necessidade concreta da rede municipal por estratégias viáveis de alfabetização com tecnologia, gerando evidências empíricas e um roteiro replicável para docentes.' }
        ],
        criteria: [
          'O objetivo geral começa com verbo no infinitivo.',
          'Atingir o objetivo geral responde diretamente à questão de pesquisa.',
          'Os objetivos específicos são etapas científicas, e não lista de tarefas.',
          'Hipóteses ou questões norteadoras são pertinentes ao desenho.',
          'A justificativa explicita relevância, contribuição e viabilidade.'
        ]
      },
      {
        id: 5,
        shortTitle: 'Metodologia',
        title: 'Metodologia da Pesquisa',
        models: 'M8',
        deliverable: 'M8: matriz metodológica articulando problema, objetivos, estratégia, participantes, instrumentos e análise.',
        objective: 'Planejar como os dados serão produzidos, com quem, por quais instrumentos e de que modo serão analisados.',
        plainExplain: 'Aqui você explica o "como fazer" da investigação de forma transparente: qual estratégia vai usar, quem participa, quais instrumentos coleta e quais cuidados éticos precisa seguir.',
        aiRole: 'Ajuda a conferir se cada objetivo específico tem um instrumento e técnica de análise compatíveis na matriz M8.',
        guidingQuestions: [
          'Para cada objetivo específico da Etapa 4, qual dado concreto será produzido?',
          'Você tem autorização e acesso real aos participantes ou documentos escolhidos?',
          'Sua pesquisa envolve seres humanos e exige consentimento (TCLE/TALE) e Comitê de Ética?'
        ],
        fields: [
          { key: 'estrategia', label: 'Estratégia principal da pesquisa', plainHint: 'Escolha o caminho mais coerente com o seu objetivo.', placeholder: 'Selecione', type: 'select', options: [
            'Estudo de caso (compreender significados em um contexto)',
            'Pesquisa-ação (transformar uma prática junto aos participantes)',
            'Design-Based Research (DBR) (desenvolver e testar intervenção educacional)',
            'Design Science Research (DSR) (projetar e avaliar artefato)',
            'Pesquisa documental (examinar políticas e documentos)'
          ], example: 'Design-Based Research (DBR) (desenvolver e testar intervenção educacional)' },
          { key: 'participantes', label: 'Participantes, contexto e acesso', plainHint: 'Especifique quem participa, local, quantidade estimada e limites de representação.', placeholder: 'Ex.: 22 alunos do 2º ano e 1 professora regente', type: 'text', example: '22 estudantes do 2º ano do Ensino Fundamental e 1 professora regente de uma escola pública municipal.' },
          { key: 'instrumentos', label: 'Instrumentos de produção de dados', plainHint: 'Relacione os instrumentos aos objetivos (ex.: diagnóstico, diário de campo, entrevista, questionário).', placeholder: 'Ex.: Diagnóstico inicial/final, diário de campo e entrevista semiestruturada', type: 'textarea', example: 'Diagnóstico inicial e final de fluência leitora; diário de campo das sessões mediadas; entrevista semiestruturada com a professora regente.' },
          { key: 'analiseEtica', label: 'Técnica de análise dos dados + Ética e exequibilidade', plainHint: 'Informe como vai analisar (análise de conteúdo, triangulação, estatística) e cuidados éticos (CEP/TCLE).', placeholder: 'Ex.: Triangulação + análise de conteúdo; submissão ao CEP com TCLE e TALE', type: 'textarea', example: 'Triangulação entre evolução diagnóstica e análise de conteúdo dos registros; submissão ao Comitê de Ética (CEP), TCLE para responsáveis e TALE para as crianças.' }
        ],
        criteria: [
          'Estratégia, abordagem e perspectiva estão descritas e justificadas.',
          'Participantes, dados, instrumentos e momentos estão definidos.',
          'Há técnica de análise explícita e coerente.',
          'As exigências éticas e o prazo foram examinados.',
          'A matriz M8 está alinhada à pergunta e aos objetivos.'
        ]
      },
      {
        id: 6,
        shortTitle: 'Produto (PTT)',
        title: 'Produto Técnico-Tecnológico (PTT)',
        models: 'M10 (Quadro 3)',
        deliverable: 'M10: Quadro 3 completo com demanda, aplicabilidade, inovação, impacto, ODS, avaliação e depósito.',
        objective: 'Conceber uma resposta aplicada a uma demanda real, ligada à investigação e passível de avaliação.',
        plainExplain: 'No mestrado profissional, sua pesquisa gera também uma solução prática (guia, software, formação, processo). Descreva para quem serve, o que muda na prática e como será avaliado.',
        aiRole: 'Ajuda a revisar clareza e evitar promessas exageradas de inovação; a concepção e a validação são autorais.',
        guidingQuestions: [
          'Quem realmente precisa desse produto e qual problema concreto ele enfrenta?',
          'Como os dados da sua pesquisa (Etapa 5) vão ajudar a validar ou ajustar o produto?',
          'Onde o produto ficará disponível para que outras pessoas possam usá-lo (ex.: eduCAPES, DSpace IFRS)?'
        ],
        fields: [
          { key: 'tipoProduto', label: 'Tipo, nome e finalidade do Produto (PTT)', plainHint: 'Software, material didático, guia, formação ou processo coerente com o regulamento do programa.', placeholder: 'Ex.: Guia Prático de Mediação Pedagógica com Jogos Digitais', type: 'text', example: 'Guia Prático de Mediação Pedagógica com Jogos Digitais para o 2º Ano (e-book interativo + fichas imprimíveis)' },
          { key: 'publicoAplicabilidade', label: 'Público-alvo e aplicabilidade (realizada, potencial e replicabilidade)', plainHint: 'Diga quem vai testar agora e como outros locais poderão reaplicar.', placeholder: 'Ex.: 2 turmas da escola participante; replicável em toda a rede municipal', type: 'textarea', example: 'Aplicação inicial na escola participante (2 turmas); potencial de replicação gratuita em qualquer escola pública com acesso básico a tablets ou computadores.' },
          { key: 'inovacaoImpacto', label: 'Inovação, impacto esperado e vínculo direto com ODS', plainHint: 'Justifique sem exageros e inclua apenas ODS com relação direta (ex.: ODS 4).', placeholder: 'Ex.: Inovação incremental; impacto na autonomia docente; ODS 4', type: 'textarea', example: 'Inovação incremental ao traduzir evidências acadêmicas em roteiros de 15 minutos prontos para aula; impacto direto na autonomia docente; vínculo com ODS 4 (Educação de Qualidade).' },
          { key: 'avaliacaoDeposito', label: 'Plano de avaliação do PTT e disponibilização / depósito', plainHint: 'Como o produto será avaliado com os dados da pesquisa + repositório (eduCAPES, DSpace IFRS).', placeholder: 'Ex.: Avaliação em 2 ciclos com docentes; depósito no eduCAPES e DSpace IFRS', type: 'text', example: 'Avaliado em 2 ciclos de uso com docentes via roteiro de usabilidade e dados de leitura; licença aberta CC-BY no eduCAPES e DSpace IFRS.' }
        ],
        criteria: [
          'O produto está diretamente ligado à pergunta científica e a uma demanda real.',
          'Abrangência realizada, potencial e replicabilidade estão descritas.',
          'Inovação, impacto e complexidade são justificados sem superestimar.',
          'A avaliação do PTT se conecta aos dados da investigação.',
          'O plano de disponibilização e depósito foi registrado.'
        ]
      },
      {
        id: 7,
        shortTitle: 'Escrita e Prazo',
        title: 'Escrita do Projeto e Cronograma',
        models: 'Projeto + M11',
        deliverable: 'Projeto escrito nas 10 seções, referências conferidas e M11 (cronograma de trás para frente).',
        objective: 'Transformar suas decisões em texto acadêmico articulado e em um plano de execução realista.',
        plainExplain: 'Monte o cronograma de trás para frente: comece pela data da defesa e distribua as entregas até hoje. Se o plano não couber no prazo, reduza o recorte antes de começar a coleta!',
        aiRole: 'Pode revisar legibilidade e fluidez do texto que você escreveu; nunca delegue a redação das seções à IA.',
        guidingQuestions: [
          'Sua introdução percorre os 5 movimentos: contexto → o que já se sabe → o que falta → recorte → pergunta e objetivo?',
          'Cada bloco do cronograma tem uma entrega parcial verificável?',
          'O prazo previsto para Comitê de Ética e qualificação é realista?'
        ],
        fields: [
          { key: 'tituloFinal', label: 'Título de trabalho do projeto', plainHint: 'Deve refletir diretamente a pergunta (Etapa 2) e o objetivo geral (Etapa 4).', placeholder: 'Ex.: Mediação docente com jogos digitais na aprendizagem da leitura...', type: 'text', example: 'Mediação docente com jogos digitais na aprendizagem da leitura: um estudo com turmas do 2º ano' },
          { key: 'introducao5Mov', label: 'Rascunho da Introdução em 5 movimentos', plainHint: '1. Contexto · 2. O que já existe · 3. O que falta entender · 4. Recorte · 5. Pergunta e Objetivo.', placeholder: 'Escreva um rascunho conectando os 5 movimentos...', type: 'textarea', example: 'A alfabetização no 2º ano enfrenta desafios de engajamento. Estudos recentes apontam potencial dos jogos digitais, mas pouco exploram a mediação docente estruturada. Este projeto delimita-se ao uso mediado em escola pública, investigando em que medida essa prática contribui para a fluência leitora.' },
          { key: 'cronogramaM11', label: 'Cronograma de trás para frente (M11: marcos e entregáveis)', plainHint: 'Inclua revisão, referencial, Comitê de Ética, qualificação, coleta, avaliação do PTT, escrita e defesa.', placeholder: 'Ex.: Meses 1–4 Revisão | Mês 5 CEP | Mês 9 Qualificação | Mês 18 Defesa', type: 'textarea', example: 'Meses 1–4: Revisão e referencial | Mês 5: Submissão CEP | Mês 9: Qualificação | Meses 10–14: Intervenção e produção de dados | Meses 15–17: Avaliação do PTT e escrita | Mês 18: Defesa.' }
        ],
        criteria: [
          'As 10 seções exigidas do projeto estão planejadas.',
          'A escrita mantém coerência com os modelos M1–M10.',
          'A introdução apresenta questão e objetivo em sequência.',
          'O cronograma tem entregáveis parciais verificáveis e datas plausíveis.',
          'Citações e referências foram conferidas conforme as normas aplicáveis.'
        ]
      },
      {
        id: 8,
        shortTitle: 'Validação Final',
        title: 'Validação Final e Apresentação (8 min)',
        models: 'M6, M9, M10, M12',
        deliverable: 'Quadros consolidados, checklist de coerência final, declaração M12 e roteiro de 8 minutos.',
        objective: 'Revisar a consistência de ponta a ponta e preparar uma apresentação objetiva para a orientação ou banca.',
        plainExplain: 'Lembre-se: concluir este roteiro organiza o projeto, mas a aprovação acadêmica pertence sempre à orientação, ao Comitê de Ética e à banca. Use o roteiro de 8 minutos abaixo para ensaiar sua fala.',
        aiRole: 'Aponta lacunas ou desconexões na cadeia de coerência; toda validação final é humana.',
        guidingQuestions: [
          'Todos os quadros (Referencial, Síntese do Projeto e PTT) fazem sentido sem depender de explicação oral?',
          'O uso de IA está registrado de forma transparente (IN IFRS nº 16/2026)?',
          'Qual é a principal dúvida que você quer levar para a orientação nos 30 segundos finais?'
        ],
        fields: [
          { key: 'registroIA_M12', label: 'Declaração transparente de uso de IA e histórico (M12, IN IFRS 16/2026)', plainHint: 'Informe ferramenta, finalidade, instrução usada e conferência humana realizada.', placeholder: 'Ex.: Uso do Scriptorium para checar coerência e organizar sinônimos; busca, leitura e escrita autorais.', type: 'textarea', example: 'Versão 1.1: uso do assistente do Scriptorium apenas para verificar coerência entre pergunta e objetivos e organizar descritores em inglês. Todas as buscas nas bases, leituras e redação foram feitas e validadas pela autoria.' },
          { key: 'duvidaOrientacao', label: 'Dúvida principal para a orientação (30 segundos finais)', plainHint: 'Uma questão objetiva para destravar o próximo passo com seu orientador(a).', placeholder: 'Ex.: O número de sessões previstas é suficiente para o desenho DBR?', type: 'text', example: 'Validar com a orientação se 8 sessões mediadas ao longo de 2 meses são suficientes para o desenho DBR sem sobrecarregar a turma.' }
        ],
        criteria: [
          'Tema claro e pergunta única, delimitada e investigável.',
          'Lacuna examinada por revisão com protocolo documentado.',
          'Objetivo geral responde à pergunta; específicos não são tarefas.',
          'Referencial teórico e revisão são distintos e relevantes.',
          'Metodologia informa participantes, instrumentos, análise e ética.',
          'PTT atende demanda real, com plano de aplicação e avaliação.',
          'Cronograma, referências e declaração de uso de IA (M12) estão consistentes.'
        ]
      }
    ];

const byStage=id=>STAGES.find(s=>s.id===Number(id));
const ff=(key,label,plainHint='',type='textarea',opts=[])=>({key,label,plainHint,type,options:opts,placeholder:'Escreva com suas palavras…',example:''});
const fieldUpdates={
  1:{append:[ff('modalidade','Modalidade do curso e vínculo com a pesquisa','As exigências podem variar entre mestrado acadêmico, profissional e doutorado.','select',['Mestrado profissional','Mestrado acadêmico','Doutorado','Especialização','Outro']),ff('linhaPesquisa','Linha ou macroprojeto de pesquisa','Informe a linha oficial do programa, se conhecida.','text')]},
  2:{append:[ff('indiciosProblema','Evidências iniciais da situação problemática','Descreva observações, registros, documentos ou outras evidências. Não confunda percepção com prova.'),ff('testePar','Crítica externa: o que alguém questionou sobre o problema?','Registre dúvidas de colega ou orientação; se ainda não ocorreu, registre como pendência.')]},
  3:{remove:['descritores','basesProtocolo','sinteseRevisao','autoresConceitos'],append:[ff('m5_convergencias','M5 · Convergências entre os trabalhos','Quais afirmações são sustentadas por vários estudos? Referencie os trabalhos.'),ff('m5_divergencias','M5 · Divergências, contextos e limites','Em que os resultados discordam? Os métodos e populações explicam essas diferenças?'),ff('m5_lacuna','M5 · Síntese crítica e lacuna confirmada ou reformulada','Indique o que o campo já sabe, o que permanece em aberto e se a pergunta da Etapa 2 mudou.')]},
  4:{remove:['objetivosEspecificos'],append:[ff('impactoSocial','Impacto social e educacional esperado','Para quem e como os resultados poderão contribuir?')]},
  5:{remove:['instrumentos','analiseEtica'],append:[ff('epistemologia','Perspectiva epistemológica e justificativa','Como você compreende a produção do conhecimento nesta investigação?'),ff('abordagem','Abordagem dos dados','Distinta da estratégia metodológica.','select',['Qualitativa','Quantitativa','Mista']),ff('finalidade','Finalidade da investigação','Observe os verbos do objetivo geral.','select',['Descritiva','Explicativa','Exploratória','Outra / combinação justificada']),ff('natureza','Natureza da pesquisa','Em mestrados profissionais costuma ser aplicada.','select',['Aplicada','Básica']),ff('amostragem','Critérios de seleção ou amostragem','Quem pode participar? Como será recrutado? Limites de representação.'),ff('materialEmpirico','Material empírico / fontes dos dados','Dados que serão analisados: entrevistas, registros, produções etc. Não confunda com bibliografia.'),ff('analiseDados','Técnica de análise','Ex.: análise de conteúdo, triangulação, estatística descritiva; explique como será feita.'),ff('etica','Cuidados éticos e autorizações','Análise de necessidade de CEP, consentimento, assentimento, proteção e retenção de dados.'),ff('exequibilidade','Viabilidade de campo e calendário','Recursos, acesso aos participantes, infraestrutura e prazos.') ]},
  6:{remove:['publicoAplicabilidade','inovacaoImpacto','avaliacaoDeposito'],append:[ff('pttDemanda','Demanda concreta e evidências da necessidade','Qual problema o produto enfrenta? Quem o identificou?'),ff('pttPublico','Público demandante e usuários','Indique quem se beneficia do produto.','text'),ff('pttAplicacao','Abrangência realizada','Onde será aplicado nesta pesquisa?'),ff('pttPotencial','Abrangência potencial','Quais outros contextos seriam possíveis, sem prometer resultados não testados?'),ff('pttReplicacao','Replicabilidade e requisitos','Como outra pessoa reproduziria ou adaptaria o produto?'),ff('pttInovacao','Potencial de inovação','Selecione e justifique abaixo.','select',['Adaptação de conhecimentos existentes','Combinação de conhecimentos consolidados','Contribuição com conhecimento inédito','Não definido']),ff('pttInovJust','Justificativa do potencial de inovação','Explique concretamente por que essa classificação se aplica.'),ff('pttComplexidade','Complexidade do desenvolvimento','Selecione e justifique abaixo.','select',['Baixa','Média','Alta','Não definida']),ff('pttComplexJust','Justificativa da complexidade','Quais áreas de conhecimento e atores participam?'),ff('pttImpacto','Impacto esperado e indicador de observação','Demandante, foco, áreas de mudança e como serão identificadas.'),ff('pttODS','ODS diretamente relacionados e justificativas','Inclua somente os ODS que tenham relação demonstrável com a proposta.','text'),ff('pttAvaliacao','Plano de avaliação e aperfeiçoamento','Quais dados da Etapa 5 ajudarão a validar ou alterar o produto?'),ff('pttDeposito','Disponibilização, repositório e documentação','Ex.: eduCAPES, repositório institucional e licença, se compatível com as exigências.')]},
  7:{remove:['introducao5Mov','cronogramaM11'],append:[ff('sec_introducao','Introdução · cinco movimentos','Fenômeno, o que se sabe, o que falta, delimitação, pergunta e objetivo.'),ff('sec_revisao','Revisão de literatura','Escreva uma síntese argumentada do campo, fundamentada nos trabalhos analisados.'),ff('sec_justificativa','Justificativa','Relevância, pesquisabilidade e contribuição.'),ff('sec_objetivos','Objetivos','Apresente objetivo geral e específicos, preservando a formulação validada.'),ff('sec_referencial','Referencial teórico','Conceitos e autores centrais com relação explícita com o problema.'),ff('sec_metodologia','Metodologia','Detalhe perspectiva, desenho, participantes, instrumentos, análise e ética.'),ff('sec_produto','Produto técnico-tecnológico','Descreva demanda, público, aplicabilidade, desenvolvimento e avaliação.'),ff('sec_referencias','Referências','Referências verificadas e formatadas segundo as normas aplicáveis.')]},
  8:{append:[ff('m9_notas','M9 · Observações sobre a síntese do projeto','O Quadro 2 é consolidado automaticamente a partir das etapas anteriores. Registre decisões pendentes ou ajustes.'),ff('pendenciasOrientacao','Outras pendências para discutir com a orientação','Liste os pontos que ainda exigem decisão humana.')]}
};
for(const s of STAGES){const up=fieldUpdates[s.id];if(up){if(up.remove)s.fields=s.fields.filter(f=>!up.remove.includes(f.key));s.fields.push(...(up.append||[]));}}
const REPEAT={
  searchBlocks:{stage:3,model:'M2',title:'Blocos de descritores',help:'Registre fenômeno, contexto, foco e conceitos com termos em português e inglês. Teste combinações antes de fixar a estratégia.',fields:[['elemento','Elemento da pergunta','select',['Fenômeno','Contexto / população','Foco analítico','Conceito teórico','Outro']],['termosPT','Termos e sinônimos em português','textarea'],['termosEN','Termos e sinônimos em inglês','textarea'],['estrategia','Combinações testadas (AND/OR)','textarea']]},
  searchRuns:{stage:3,model:'M3',title:'Protocolo de busca: execuções',help:'Uma entrada por busca realmente realizada. É importante que outra pessoa consiga reproduzi-la.',fields:[['base','Base ou repositório','text'],['data','Data da busca','date'],['consulta','Expressão exata de busca','textarea'],['periodo','Período e filtros','text'],['inclusao','Critérios de inclusão','textarea'],['exclusao','Critérios de exclusão','textarea'],['encontrados','Registros encontrados','number'],['selecionados','Registros selecionados','number'],['motivo','Justificativas e observações','textarea']]},
  readings:{stage:3,model:'M4',title:'Fichamento e quadro de leitura',help:'Um registro por trabalho. A disciplina recomenda 5 a 8 estudos centrais lidos em profundidade; isto não limita o tamanho total da revisão.',fields:[['referencia','Referência bibliográfica / título','textarea'],['link','DOI ou endereço da fonte','text'],['problema','Problema e objetivos do estudo','textarea'],['metodo','Método utilizado','textarea'],['contexto','Contexto e participantes','textarea'],['resultados','Resultados e conclusões','textarea'],['limitacoes','Limitações reconhecidas','textarea'],['relacao','Como se relaciona ao meu problema','textarea'],['distancia','Em que difere do meu problema','textarea'],['paginas','Páginas e notas verificadas','text']]},
  theories:{stage:3,model:'M6',title:'Quadro 1: Referencial teórico',help:'Hierarquize os autores centrais e explique a contribuição analítica de cada um. Educação/Informática é exigência do guia de origem; outros programas podem pedir outra composição.',fields:[['conceito','Conceito ou eixo teórico','text'],['autor','Autor(es) de referência','text'],['obra','Obra ou referência verificada','text'],['area','Área de contribuição','select',['Educação','Informática / Tecnologia','EPT','Interdisciplinar','Outra']],['aspecto','Aspecto educacional e função na análise','textarea']]},
  objectives:{stage:4,model:'M7',title:'Objetivos específicos',help:'Cada objetivo deve expressar um resultado de investigação, não uma tarefa como “aplicar questionário”.',fields:[['texto','Objetivo específico','textarea'],['conhecimento','Que conhecimento será produzido ao cumpri-lo?','textarea']]},
  timeline:{stage:7,model:'M11',title:'Cronograma por entregável',help:'Planeje de trás para frente a partir da defesa. Registre atividades, datas e entregáveis; reserve prazo para ética e qualificação.',fields:[['fase','Fase/atividade','text'],['inicio','Início','month'],['fim','Fim','month'],['entrega','Entregável verificável','textarea'],['dependencia','Dependências e autorizações','text']]},
  aiUse:{stage:8,model:'M12',title:'Registro de uso de IA',help:'Registre ferramenta, data, finalidade, instrução/prompt relevante e verificação humana; siga a norma de seu programa.',fields:[['data','Data','date'],['ferramenta','Ferramenta e modelo, se conhecido','text'],['finalidade','Finalidade do uso','text'],['prompt','Instrução ou prompt utilizado','textarea'],['conferencia','Conferência, decisões e responsabilidade humana','textarea']]}
};
const EXTRA_GLOSSARY=[
['Questão de pesquisa','Pergunta principal, investigável e delimitada, cuja resposta a pesquisa pretende construir.'],
['Protocolo reproduzível','Registro suficiente de base, data, expressão, filtros e seleção para que outra pessoa possa repetir a busca.'],
['Material empírico','Dados analisados na pesquisa: entrevistas, documentos do campo, observações ou produções. É diferente do referencial teórico.'],
['Matriz metodológica','Quadro que conecta cada objetivo ao dado necessário, participante, instrumento, momento e técnica de análise.'],
['Autoverificação','Declaração do estudante de que revisou os critérios. Não é aprovação de orientador ou banca.'],
['Letramento científico','Capacidade de compreender, interpretar, argumentar e avaliar evidências em práticas científicas.'],
['DBR','Pesquisa baseada em design: desenvolve, experimenta e aperfeiçoa intervenções em contextos educacionais.'],
['DSR','Design Science Research: constrói e avalia artefatos para enfrentar problemas de um campo de atuação.'],
['PTT','Produto técnico-tecnológico: resposta aplicada vinculada à demanda e à investigação.'],
['Versão recuperável','Cópia completa dos dados feita em um momento específico, que pode ser restaurada.'],
['M9','Quadro 2: síntese do projeto. A estrutura aqui é uma adaptação, pois o modelo completo não estava no anexo da disciplina.'],
['M12','Histórico e usos de IA. A estrutura aqui é uma adaptação; confira o formulário original da disciplina.']
];
const STAGE_LABELS={1:'Preparação',2:'Tema e problema',3:'Revisão e referencial',4:'Objetivos',5:'Metodologia',6:'Produto (PTT)',7:'Escrita e cronograma',8:'Validação final'};

const isArticle=()=>state.tipo!=='projeto';
const PROJECT_STAGES=JSON.parse(JSON.stringify(STAGES));
const PROJECT_LABELS={...STAGE_LABELS};
const ARTICLE_STAGES={
  6:{id:6,shortTitle:'Resultados',title:'Resultados e Discussão',models:'Artigo',
    deliverable:'Resultados organizados por objetivo, interpretação à luz do referencial, comparação com a revisão e limitações.',
    objective:'Apresentar o que os dados mostram e discutir o que isso significa, sem ir além do que eles permitem.',
    plainExplain:'Resultados dizem o que você encontrou; a discussão diz o que isso significa. Organize os resultados pelos objetivos específicos da Etapa 4, compare com os estudos da revisão (Etapa 3) e declare os limites.',
    aiRole:'Pode apontar afirmações sem dado que as sustente e conferir se cada objetivo tem resultado; a interpretação é sua.',
    guidingQuestions:['Cada objetivo específico tem pelo menos um resultado apresentado?','Seus resultados confirmam, contradizem ou ampliam os estudos da revisão?','Que conclusão os seus dados NÃO permitem tirar?'],
    fields:[
      {key:'resultadosPorObjetivo',label:'Principais resultados, por objetivo específico',plainHint:'Um bloco por objetivo: o que os dados mostraram, com números ou exemplos.',placeholder:'Objetivo 1: ...\nObjetivo 2: ...',type:'textarea',example:'Objetivo 1: no diagnóstico inicial, 14 de 22 estudantes estavam abaixo do esperado em fluência.\nObjetivo 2: a mediação mais frequente foi a leitura compartilhada antes de cada fase do jogo.\nObjetivo 3: 16 estudantes avançaram um nível de fluência após oito sessões.'},
      {key:'tabelasFiguras',label:'Tabelas e figuras planejadas',plainHint:'Liste o que cada tabela ou figura vai mostrar. Cada uma precisa ser citada no texto.',placeholder:'Tabela 1: ...; Figura 1: ...',type:'text',example:'Tabela 1: fluência antes e depois; Figura 1: tipos de mediação por sessão.'},
      {key:'interpretacao',label:'Interpretação à luz do referencial teórico',plainHint:'Use os conceitos e autores da Etapa 3 para explicar os resultados.',placeholder:'À luz de ...',type:'textarea',example:'À luz do conceito de mediação, o avanço se concentrou nas sessões em que a professora retomava as palavras do jogo em voz alta.'},
      {key:'comparacaoRevisao',label:'Comparação com os estudos da revisão',plainHint:'Onde seus resultados concordam e onde divergem dos estudos lidos? Cite-os.',placeholder:'Como em ..., observou-se ...; diferente de ...',type:'textarea',example:'Como nos estudos que relatam ganho de engajamento, houve adesão inicial alta; diferente deles, a retenção dependeu da mediação estruturada.'},
      {key:'limitacoes',label:'Limitações e alcance das conclusões',plainHint:'O que restringe a generalização (amostra, tempo, contexto, instrumentos)?',placeholder:'O estudo foi realizado em ...',type:'textarea',example:'Uma única turma, sem grupo de comparação, durante oito semanas; os resultados não se generalizam para outras séries.'},
      {key:'implicacoes',label:'Implicações para a prática e para novas pesquisas',plainHint:'O que muda para quem atua no campo e o que ainda precisa ser investigado?',placeholder:'Para professores, ...; pesquisas futuras ...',type:'textarea',example:'Para professores, roteiros curtos de mediação antes do jogo; para pesquisas futuras, comparar turmas com e sem mediação.'}],
    criteria:['Os resultados estão organizados pelos objetivos específicos.','Cada afirmação dos resultados se apoia em um dado apresentado.','A discussão usa o referencial teórico da Etapa 3.','Há comparação explícita com os estudos da revisão.','As limitações e o alcance das conclusões estão declarados.']},
  7:{id:7,shortTitle:'Escrita',title:'Escrita do Artigo',models:'Artigo · M11',
    deliverable:'Artigo completo: título, resumo e palavras-chave, introdução em cinco movimentos, revisão, referencial, metodologia, resultados, discussão, considerações finais e referências.',
    objective:'Transformar as decisões das etapas anteriores em um texto acadêmico coeso, adequado à revista escolhida.',
    plainExplain:'Escolha a revista antes de escrever: ela define tamanho, estrutura e normas. Uma ordem que costuma funcionar: metodologia e resultados primeiro, depois discussão e introdução; resumo e título por último.',
    aiRole:'Pode revisar clareza e coesão do texto que você escreveu e conferir citações nas fontes; não delegue a redação das seções.',
    guidingQuestions:['A revista aceita o seu tipo de estudo e o tamanho do texto?','A introdução percorre os cinco movimentos e termina na pergunta e no objetivo?','O resumo informa objetivo, método, principais resultados e conclusão?'],
    fields:[
      {key:'revistaAlvo',label:'Revista-alvo, escopo e normas',plainHint:'Nome, escopo, limite de palavras ou páginas, norma de citação e se exige anonimização.',placeholder:'Ex.: Revista X · até 8.000 palavras · ABNT · avaliação cega',type:'text',example:'RENOTE · artigos de 8 a 15 páginas · ABNT · avaliação cega por pares'},
      {key:'tituloFinal',label:'Título do artigo',plainHint:'Deve refletir a pergunta (Etapa 2) e o objetivo geral (Etapa 4).',placeholder:'Ex.: Mediação docente com jogos digitais na aprendizagem da leitura',type:'text',example:'Mediação docente com jogos digitais na aprendizagem da leitura: um estudo com uma turma do 2º ano'},
      {key:'sec_resumo',label:'Resumo',plainHint:'Objetivo, método, principais resultados e conclusão, no limite da revista.',placeholder:'Este estudo analisou ...',type:'textarea',example:''},
      {key:'palavrasChave',label:'Palavras-chave',plainHint:'De 3 a 5, de preferência os mesmos descritores da Etapa 3.',placeholder:'Ex.: alfabetização; jogos digitais; mediação docente',type:'text',example:'alfabetização; jogos digitais; mediação docente'},
      {key:'sec_introducao',label:'Introdução · cinco movimentos',plainHint:'Fenômeno, o que se sabe, o que falta, delimitação, pergunta e objetivo.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_revisao',label:'Revisão de literatura',plainHint:'Síntese argumentada dos estudos da Etapa 3, separada do referencial.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_referencial',label:'Referencial teórico',plainHint:'Conceitos e autores centrais e como eles ajudam a analisar os dados.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_metodologia',label:'Metodologia',plainHint:'Desenho, participantes, instrumentos, análise e ética, coerentes com a Etapa 5.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_resultados',label:'Resultados',plainHint:'Escreva a partir da Etapa 6, na ordem dos objetivos.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_discussao',label:'Discussão',plainHint:'Interpretação, comparação com a revisão, limitações e implicações.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_conclusao',label:'Considerações finais',plainHint:'Responda à pergunta da Etapa 2, sem trazer dados novos.',placeholder:'Escreva com suas palavras…',type:'textarea',example:''},
      {key:'sec_referencias',label:'Referências',plainHint:'Somente fontes verificadas e citadas no texto, na norma da revista.',placeholder:'SOBRENOME, Nome. Título. Revista, v., n., p., ano.',type:'textarea',example:''}],
    criteria:['A revista-alvo e suas normas foram identificadas.','O resumo traz objetivo, método, resultados e conclusão.','A introdução apresenta os cinco movimentos e termina na pergunta e no objetivo.','Resultados e discussão estão coerentes com as Etapas 4 a 6.','Citações e referências foram conferidas nas fontes e na norma da revista.']},
  8:{id:8,shortTitle:'Submissão',title:'Revisão Final e Submissão',models:'Checklist · M12',
    deliverable:'Checklist de coerência, declaração de uso de IA (M12), revisão externa registrada e pacote de submissão.',
    objective:'Revisar o artigo de ponta a ponta e preparar a submissão.',
    plainExplain:'Antes de submeter, releia o texto seguindo a cadeia de coerência e peça a leitura de alguém de fora. Concluir o guia organiza o artigo; quem aprova é a orientação e, depois, os pareceristas da revista.',
    aiRole:'Aponta lacunas ou desconexões na cadeia de coerência; toda validação final é humana.',
    guidingQuestions:['O título, o resumo e as considerações finais contam a mesma história?','O uso de IA está registrado de forma transparente (IN IFRS nº 16/2026)?','O que a orientação precisa ler antes da submissão?'],
    fields:[
      {key:'checklistRevista',label:'Checklist da submissão',plainHint:'Itens exigidos pela revista: anonimização, formatação, limite de tamanho, metadados, carta ao editor.',placeholder:'[ ] anonimizado  [ ] dentro do limite  [ ] referências na norma ...',type:'textarea',example:'[x] anonimizado  [x] 12 páginas  [x] ABNT  [ ] carta ao editor  [ ] metadados no sistema da revista'},
      {key:'registroIA_M12',label:'Declaração transparente de uso de IA (M12, IN IFRS 16/2026)',plainHint:'Informe ferramenta, finalidade, instrução usada e conferência humana realizada.',placeholder:'Ex.: uso do Scriptorium para conferir citações; escrita autoral.',type:'textarea',example:'Uso do Scriptorium para conferir citações e coerência; leitura, análise e redação feitas e validadas pela autoria.'},
      {key:'cartaEditor',label:'Carta ao editor (se a revista pedir)',plainHint:'Por que o artigo interessa à revista, em poucas linhas.',placeholder:'Prezado(a) editor(a), ...',type:'textarea',example:''},
      {key:'duvidaOrientacao',label:'Dúvida principal para a orientação',plainHint:'Uma questão objetiva para destravar a submissão.',placeholder:'Ex.: a discussão está suficiente para a revista escolhida?',type:'text',example:'A comparação com a revisão está suficiente para a RENOTE ou preciso de mais estudos?'}],
    criteria:['Tema claro e pergunta única, delimitada e investigável.','Lacuna examinada por revisão com protocolo documentado.','Objetivo geral responde à pergunta; específicos não são tarefas.','Referencial teórico e revisão são distintos e relevantes.','Metodologia informa participantes, instrumentos, análise e ética.','Resultados respondem aos objetivos e a discussão declara limites.','Referências, normas da revista e declaração de uso de IA (M12) estão consistentes.']}
};
const ARTICLE_LABELS={6:'Resultados e discussão',7:'Escrita do artigo',8:'Revisão e submissão'};
function applyMode(){
  const base=JSON.parse(JSON.stringify(PROJECT_STAGES));
  const next=isArticle()?base.map(st=>ARTICLE_STAGES[st.id]?JSON.parse(JSON.stringify(ARTICLE_STAGES[st.id])):st):base;
  STAGES.splice(0,STAGES.length,...next);
  Object.assign(STAGE_LABELS,PROJECT_LABELS,isArticle()?ARTICLE_LABELS:{});
  REPEAT.timeline.title=isArticle()?'Cronograma até a submissão':'Cronograma por entregável';
  const bA=R.getElementById('modeArtigo'), bP=R.getElementById('modeProjeto');
  if(bA&&bP){
    const art=isArticle();
    bA.classList.toggle('active',art); bA.setAttribute('aria-checked',String(art));
    bP.classList.toggle('active',!art); bP.setAttribute('aria-checked',String(!art));
  }
}
const STORAGE_KEY='scriptorium_pesquisa_guiada_v2_independente';
const TRASH_KEY='scriptorium_pesquisa_guiada_v2_lixeira';
const OLD_KEY='scriptorium_pesquisa_guiada_estacoes_v1';
const MAX_VERSIONS=25;
const dateNow=()=>new Date().toLocaleString('pt-BR');
const uid=()=>`${Date.now().toString(36)}${Math.random().toString(36).slice(2,8)}`;
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const plain=s=>String(s??'').trim();
const val=k=>plain(state.values[k]);
const isFilled=k=>Boolean(val(k));
const copy=o=>JSON.parse(JSON.stringify(o));
function emptyState(){return {schema:2,tipo:'artigo',active:1,tab:'entender',theme:'light',font:1,values:{},records:{},criteria:{},evidence:{},reviews:{},versions:[],changedAt:Date.now(),startedAt:Date.now()};}
let state=emptyState(), saveTimer=null, savingError=false, writeConflict=false, lastKnownWrite=0, toastTimer=null, lastModalFocus=null, lastAutosnap=0;
function load(){try{const raw=localStorage.getItem(STORAGE_KEY);if(raw){const got=JSON.parse(raw);if(got&&got.schema===2&&got.values&&got.records){state={...emptyState(),...got};lastKnownWrite=state.changedAt||0;return;}}}catch(e){savingError=true;}
  try{const old=localStorage.getItem(OLD_KEY);if(old){const orig=JSON.parse(old);state.values={...orig.values};state.criteria={...orig.checks};state.active=Math.min(8,Math.max(1,Number(orig.activeStage)||1));state.tab=orig.subTab||'entender';state.theme=orig.theme||'light';state.font=orig.fontScale||1;state.versions.push({id:uid(),label:'Migração de campos antigos',date:dateNow(),stage:0,snapshot:snap(),note:'Migração preliminar dos campos da versão 1, mantendo os dados originais intactos. Revise os novos modelos estruturados.'});persist();}}catch(e){/* usuário poderá usar importação manual */}}
function snap(){return copy({values:state.values,records:state.records,criteria:state.criteria,evidence:state.evidence,reviews:state.reviews});}
function snapshot(label='Cópia manual',stage=state.active,note=''){state.versions.push({id:uid(),label,date:dateNow(),stage,note,snapshot:snap()});if(state.versions.length>MAX_VERSIONS)state.versions=state.versions.slice(-MAX_VERSIONS);return state.versions[state.versions.length-1];}
function persist(){try{const stored=localStorage.getItem(STORAGE_KEY);if(stored){const x=JSON.parse(stored);if(x.changedAt>lastKnownWrite){writeConflict=true;savingError=true;updateStatus();return false;}}if(writeConflict){savingError=true;updateStatus();return false;}state.changedAt=Date.now();localStorage.setItem(STORAGE_KEY,JSON.stringify(state));lastKnownWrite=state.changedAt;savingError=false;if(NUVEM)NUVEM.agendar();updateStatus();return true;}catch(e){savingError=true;updateStatus();return false;}}
function scheduleSave(){const s=R.getElementById('saveStatus');if(s)s.textContent='● Alterações locais ainda não gravadas…';clearTimeout(saveTimer);saveTimer=setTimeout(persist,320);}
function flush(){clearTimeout(saveTimer);return persist();}
function updateStatus(){
  const n=R.getElementById('saveStatus');if(!n)return;
  n.className='status-bar'+(savingError?' alert':'');
  n.textContent=writeConflict
    ?'⚠ Alterações em outra aba. Salve uma cópia de segurança antes de recarregar.'
    :savingError?'⚠ Não foi possível salvar aqui. Baixe uma cópia de segurança agora.'
    :(NUVEM&&NUVEM.texto()||'✓ Salvo neste aparelho às '+new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})+' · Entre com Google para salvar na sua conta');
  const filled=STAGES.filter(s=>info(s.id).complete).length;
  const worked=STAGES.filter(s=>info(s.id).code!=='empty').length;
  const infoEl=R.getElementById('projectInfo');
  if(infoEl)infoEl.textContent=`${worked} de 8 iniciadas · ${filled} de 8 prontas`;
  const fillEl=R.getElementById('progressFill');
  if(fillEl)fillEl.style.width=`${Math.round((filled/8)*100)}%`;
}
function notify(message){const node=R.getElementById('toast');node.textContent=message;node.style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.style.display='none',3500);}
function recs(k){return Array.isArray(state.records[k])?state.records[k]:[];}
function info(stage){const id=Number(stage);const f=byStage(id).fields;const present=f.filter(x=>isFilled(x.key)).length;let specialTotal=0,specialDone=0;const requireCount=(ok,total=1)=>{specialTotal+=total;specialDone+=ok?total:0;};
  if(id===3){requireCount(recs('searchBlocks').filter(r=>plain(r.elemento)&&plain(r.termosPT)).length>=2);requireCount(recs('searchRuns').filter(r=>plain(r.base)&&plain(r.consulta)&&plain(r.data)).length>=1);requireCount(recs('readings').filter(r=>plain(r.referencia)&&plain(r.metodo)&&plain(r.resultados)).length>=5);requireCount(recs('theories').filter(r=>plain(r.conceito)&&plain(r.autor)).length>=2);}
  if(id===4)requireCount(recs('objectives').filter(r=>plain(r.texto)).length>=3);
  if(id===5){const obs=recs('objectives').filter(r=>plain(r.texto));requireCount(obs.length>0&&obs.every(o=>{const x=(state.records.methodLinks||{})[o.id]||{};return plain(x.dados)&&plain(x.instrumento)&&plain(x.analise); }));}
  if(id===7)requireCount(recs('timeline').filter(r=>plain(r.fase)&&plain(r.entrega)).length>=2);
  if(id===8)requireCount(recs('aiUse').some(r=>plain(r.ferramenta)&&plain(r.finalidade)&&plain(r.conferencia))||/não utilizei/i.test(val('registroIA_M12')));
  const complete=present===f.length&&specialDone===specialTotal;
  const count=present+specialDone, max=f.length+specialTotal;
  const allChecked=byStage(id).criteria.every((_,i)=>Boolean(state.criteria[`${id}:${i}`]));
  const review=state.reviews[id];
  let code='empty',label='Não iniciado';
  if(count>0)code='draft',label='Em elaboração';
  if(complete)code='filled',label='Preenchido';
  if(complete&&allChecked)code='self',label='Autoverificado';
  if(review&&review.result==='revisado'&&!review.stale)code='review',label='Revisão externa registrada';
  return {code,label,complete,count,max,allChecked,present,fieldTotal:f.length};
}
function stageProgressLabel(){const worked=STAGES.filter(s=>info(s.id).code!=='empty').length;const filled=STAGES.filter(s=>info(s.id).complete).length;return `${worked}/8 iniciadas · ${filled}/8 preenchidas`;}
function badge(label,type=''){return `<span class="pill ${type}">${esc(label)}</span>`;}
function htmlLines(s){return esc(s||'').replace(/\n/g,'<br>');}
function safeDate(s){return plain(s)||'(vazio)';}

function renderHeader(){
  const s=byStage(state.active),p=info(s.id);
  R.getElementById('stageHeader').innerHTML=`
    <div>
      <div class="flex" style="margin-bottom:8px">
        <span class="eyebrow">Etapa ${s.id} de 8</span>
        ${badge(p.label,p.code==='self'||p.code==='review'||p.code==='filled'?'good':'gold')}
      </div>
      <h2>${esc(s.title)}</h2>
      <div class="small muted">${esc(s.objective)}</div>
    </div>
    <div class="tabbar" role="tablist" aria-label="Três passos desta etapa">
      ${[['entender','1 · Entender'],['preencher','2 · Escrever'],['conferir','3 · Conferir']].map(([k,label])=>`<button type="button" role="tab" data-action="tab" data-tab="${k}" aria-selected="${state.tab===k}">${label}</button>`).join('')}
    </div>`;
}
function renderChain(){
  const arr=[['Problema',2,'problema'],['Pergunta',2,'pergunta'],['Revisão',3,'m5_lacuna'],['Objetivo',4,'objetivoGeral'],['Método',5,'estrategia'],['Análise',5,'analiseDados'],isArticle()?['Resultados',6,'resultadosPorObjetivo']:['Produto',6,'tipoProduto']];
  R.getElementById('chain').innerHTML=arr.map(([label,step,key],i)=>`<button type="button" class="chain-link ${isFilled(key)?'filled':''}" data-action="jump" data-stage="${step}">${isFilled(key)?'✓':'○'} ${esc(label)}</button>${i<arr.length-1?'<span class="chain-arrow" aria-hidden="true">→</span>':''}`).join('');
}
function renderStations(){
  const friendly={empty:'Começar',draft:'Em andamento',filled:'Preenchida ✓',self:'Conferida ✓',review:'Revisada ✓'};
  R.getElementById('stations').innerHTML=STAGES.map(s=>{
    const p=info(s.id);
    const done=p.code==='filled'||p.code==='self'||p.code==='review';
    return `<button type="button" class="station ${s.id===state.active?'selected':''} ${done?'done':''}" data-action="jump" data-stage="${s.id}" aria-current="${s.id===state.active?'step':'false'}">
      <span class="num">${String(s.id).padStart(2,'0')}</span>
      <span class="station-info">
        <b>${esc(STAGE_LABELS[s.id])}</b>
        <small>${esc(friendly[p.code]||p.label)}${done?'':` · ${p.count}/${p.max}`}</small>
      </span>
    </button>`;
  }).join('');
}
function renderEntender(s){
  return `<div class="section-max section-gap">
    <div class="card">
      <span class="eyebrow">Explicação simples</span>
      <p class="lead" style="margin:8px 0 0">${esc(s.plainExplain)}</p>
    </div>
    <div class="callouts">
      <div class="card white"><span class="eyebrow">O que você vai produzir aqui</span><p class="small" style="margin:6px 0 0">${esc(s.deliverable)}</p></div>
      <div class="card white"><span class="eyebrow">Como a IA pode ajudar</span><p class="small" style="margin:6px 0 0">${esc(s.aiRole)}</p><p class="test-note">Este guia não usa IA: você escreve com suas palavras e no seu ritmo.</p></div>
    </div>
    <div class="card white">
      <h3>Perguntas para ajudar a pensar</h3>
      <ul class="helper-list">${s.guidingQuestions.map(q=>`<li>${esc(q)}</li>`).join('')}</ul>
    </div>
    <div class="action-footer">
      <button type="button" class="btn" data-action="speak">🔊 Ouvir explicação</button>
      <button type="button" class="btn primary" data-action="tab" data-tab="preencher">Começar a escrever esta etapa →</button>
    </div>
  </div>`;
}
function renderInputControl(field,v,context={}){
  const key=field.key,typ=field.type||'textarea';
  const att=context.rec?`data-rec="${esc(context.rec)}" data-item="${esc(context.item)}" data-key="${esc(key)}"`:`data-field="${esc(key)}"`;
  const id=`ctrl-${context.rec||'simple'}-${context.item||'s'}-${key}`.replace(/[^a-zA-Z0-9_-]/g,'-');
  const hintId=`hint-${id}`;const hint=context.rec?'':field.plainHint;
  let input='';
  if(typ==='select'){input=`<select id="${id}" ${att} aria-describedby="${hintId}"><option value="">Escolha uma opção…</option>${(field.options||[]).map(o=>`<option value="${esc(o)}" ${v===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;}
  else if(typ==='textarea'){input=`<textarea id="${id}" ${att} rows="${context.rec?3:4}" aria-describedby="${hintId}" placeholder="${esc(field.placeholder||'Escreva aqui com suas palavras…')}">${esc(v)}</textarea>`;}
  else{input=`<input id="${id}" ${att} type="${['date','month','number','text'].includes(typ)?typ:'text'}" value="${esc(v)}" aria-describedby="${hintId}" placeholder="${esc(field.placeholder||'')}">`;}
  return `<div class="field"><div class="field-label"><label for="${id}">${esc(field.label)}</label>${!context.rec&&field.example?`<button class="btn sm" data-action="field-example" data-field="${esc(key)}" type="button">Ver exemplo</button>`:''}</div><p id="${hintId}" class="hint">${esc(hint||'Escreva com suas palavras, sem pressa: você pode editar depois.')}</p>${input}</div>`;
}
function renderStandard(s,onlyKeys=null){let fields=s.fields;if(onlyKeys)fields=fields.filter(f=>onlyKeys.includes(f.key));const body=fields.map(f=>renderInputControl(f,state.values[f.key]||'')).join('');return `<div class="fieldgroup">${body}</div>`;}
function renderRepeat(name){
  const cfg=REPEAT[name],arr=recs(name);
  const rowControls=(r)=>cfg.fields.map(([key,label,typ,opts])=>renderInputControl({key,label,type:typ,options:opts,placeholder:'Preencha com as informações verificadas…'},r[key]||'',{rec:name,item:r.id})).join('');
  return `<section class="repeat-block" id="repeat-${name}">
    <div class="repeat-intro">
      <div><div class="eyebrow">${esc(cfg.model)}</div><h3>${esc(cfg.title)} <span class="tag">${arr.length} registro(s)</span></h3><p class="small muted" style="max-width:680px;margin:0">${esc(cfg.help)}</p></div>
      <button type="button" class="btn sm primary" data-action="add-rec" data-rec="${name}">+ Adicionar</button>
    </div>
    ${arr.length?arr.map((r,i)=>`<details class="record" ${i===arr.length-1?'open':''}><summary><span class="record-index">${i+1}</span><span class="record-title">${esc(plain(r[cfg.fields[0][0]])||plain(r.referencia)||'Novo registro')}</span><span class="tiny muted">Abrir / editar ▾</span></summary><div class="fieldgroup">${rowControls(r)}</div><div class="record-controls"><button type="button" class="btn sm danger" data-action="remove-rec" data-rec="${name}" data-item="${esc(r.id)}">Remover este registro</button></div></details>`).join(''):`<p class="empty" style="margin:12px 0 0">Nenhum item adicionado ainda. Clique em "+ Adicionar" acima.</p>`}
  </section>`;
}
function renderMatrix(){const obs=recs('objectives');const objMap=(state.records.methodLinks||{});return `<section class="repeat-block"><div class="eyebrow">M8 · Matriz de coerência</div><h3>Correspondência entre objetivos, dados e análise</h3><p class="small muted">Cada linha é vinculada a um objetivo específico da Etapa 4. Se alterar os objetivos, revise as linhas. Nenhuma matriz é apagada automaticamente.</p>${obs.length?obs.map((o,i)=>{const v=objMap[o.id]||{};const fields=[['dados','Dados necessários'],['origem','Participantes ou documentos que produzem os dados'],['instrumento','Instrumento de produção de dados'],['momento','Momento de produção de dados'],['analise','Técnica de análise'],['ética','Questões éticas / autorizações']];return `<details class="record" open><summary><span class="record-index">${i+1}</span><span class="record-title">${esc(plain(o.texto)||'Objetivo ainda vazio')}</span></summary><div class="fieldgroup">${fields.map(([key,label])=>renderMatrixControl(o.id,key,label,v[key]||'')).join('')}</div></details>`;}).join(''):'<div class="notice">Para construir a matriz M8, registre primeiro os objetivos específicos na Etapa 4.</div>'}</section>`;}
function renderMatrixControl(id,key,label,value){const fld=`mx-${id}-${key}`;return `<div class="field"><label for="${esc(fld)}">${esc(label)}</label><textarea rows="2" id="${esc(fld)}" data-matrix="${esc(id)}" data-matrix-key="${esc(key)}">${esc(value)}</textarea></div>`;}
function renderM9(){const fields=[['Tema','tema'],['Situação problemática','problema'],['Questão de pesquisa','pergunta'],['Objetivo geral','objetivoGeral'],['Objetivos específicos','~objectives'],['Contexto e participantes','participantes'],['Método e estratégia','estrategia'],['Abordagem','abordagem'],['Material empírico','materialEmpirico'],['Análise','analiseDados'],['Impacto social','impactoSocial'],isArticle()?['Resultados','resultadosPorObjetivo']:['Produto','tipoProduto']];const vfield=(k)=>k==='~objectives'?recs('objectives').map((r,i)=>`${i+1}. ${plain(r.texto)}`).join('\n'):val(k);
  return `<div class="card white"><div class="eyebrow">M9 · Quadro 2 · Síntese automática do projeto</div><p class="small muted">A estrutura abaixo foi adaptada: o modelo M9 integral não estava incluído no guia enviado. Confira sua correspondência com o formulário da disciplina antes de usar academicamente.</p><div class="timeline-wrap"><table class="table"><tbody>${fields.map(([name,key])=>`<tr><th scope="row" style="width:30%">${esc(name)}</th><td>${htmlLines(vfield(key)||'(vazio)')}</td></tr>`).join('')}</tbody></table></div></div>`;}
function presentation(){const parts=[['1 min','Contexto',val('ambienteOrigem')||val('inquietacaoLivre')],['1,5 min','Quadro 1 · Referencial (M6)',recs('theories').map(r=>`${plain(r.conceito)}: ${plain(r.autor)}`).filter(Boolean).join('; ')],['3 min','Quadro 2 · Projeto (M9)',`Questão: ${val('pergunta')}\nObjetivo: ${val('objetivoGeral')}`],isArticle()?['2 min','Resultados e discussão',`${val('resultadosPorObjetivo')}\n${val('limitacoes')}`]:['2 min','Quadro 3 · PTT (M10)',`${val('tipoProduto')}\n${val('pttAvaliacao')}`],['0,5 min','Dúvida para a orientação',val('duvidaOrientacao')]];return `<section class="card white"><h3>Roteiro de apresentação: 8 minutos</h3><div class="fieldgroup">${parts.map(([tm,title,text])=>`<div class="card"><span class="tag">${esc(tm)}</span><h4>${esc(title)}</h4><p class="small">${htmlLines(text||'Campo ainda pendente')}</p></div>`).join('')}</div></section>`;}
function renderLegacy(s){const keys={3:['descritores','basesProtocolo','sinteseRevisao','autoresConceitos'],4:['objetivosEspecificos'],5:['instrumentos','analiseEtica'],6:['publicoAplicabilidade','inovacaoImpacto','avaliacaoDeposito'],7:['introducao5Mov','cronogramaM11']}[s.id]||[];const matches=keys.filter(k=>val(k));if(!matches.length)return '';return `<div class="card warning"><h3>Conteúdo preservado da versão anterior</h3><p class="small">Estes campos resumidos foram encontrados em uma versão antiga. Não foram apagados, mas precisam ser distribuídos nos novos modelos estruturados. Copie e revise antes de eliminar qualquer dado.</p>${matches.map(k=>`<details><summary>${esc(k)}</summary><div class="example-text">${htmlLines(val(k))}</div></details>`).join('')}</div>`;}
function renderPreencher(s){let body='';if(s.id===3){body=renderRepeat('searchBlocks')+renderRepeat('searchRuns')+renderRepeat('readings')+'<div class="group-title"><h3>Síntese crítica da revisão</h3></div>'+renderStandard(s)+renderRepeat('theories');}
  else if(s.id===4)body=renderStandard(s)+renderRepeat('objectives');
  else if(s.id===5)body=renderStandard(s)+renderMatrix();
  else if(s.id===7)body=renderStandard(s)+renderRepeat('timeline');
  else if(s.id===8)body=renderM9()+renderStandard(s)+renderRepeat('aiUse')+presentation();
  else body=renderStandard(s);
  return `<div class="section-max section-gap"><div class="notice"><strong>Escreva no seu tempo:</strong> tudo o que você digita fica salvo automaticamente. Você pode sair e voltar depois sem perder nada.</div>${renderLegacy(s)}${body}<div class="action-footer"><button type="button" class="btn" data-action="examples">Ver exemplos prontos</button><button type="button" class="btn primary" data-action="tab" data-tab="conferir">Revisar e avançar →</button></div></div>`;}
function renderConferir(s){const p=info(s.id);const items=s.criteria.map((c,i)=>{const k=`${s.id}:${i}`;return `<div class="check-card"><input type="checkbox" id="check-${s.id}-${i}" data-check="${esc(k)}" ${state.criteria[k]?'checked':''}><div><label for="check-${s.id}-${i}">${esc(c)}</label><textarea class="check-note" rows="2" data-evidence="${esc(k)}" aria-label="Anotação para o critério ${i+1}" placeholder="Anotação opcional (o que já está pronto ou o que falta revisar)…">${esc(state.evidence[k]||'')}</textarea></div></div>`;}).join('');
const rev=state.reviews[s.id];return `<div class="section-max section-gap"><div class="card warning"><span class="eyebrow">Revisão pessoal desta etapa</span><p class="small" style="margin:6px 0">Marque cada item abaixo quando sentir que ele está bem resolvido no seu texto. Você pode avançar e voltar quando quiser.</p><div class="status-steps">${['Em andamento','Preenchida','Conferida','Revisão da orientação'].map((q,i)=>`<span class="status-step ${(i===0&&p.count>0)||(i===1&&p.complete)||(i===2&&p.complete&&p.allChecked)||(i===3&&rev&&rev.result==='revisado')?'on':''}">${q}</span>`).join('')}</div></div><h3>Lista de conferência</h3><div class="small muted">Preenchido: ${p.count} de ${p.max} blocos · Marcados: ${s.criteria.filter((_,i)=>state.criteria[`${s.id}:${i}`]).length} de ${s.criteria.length}</div>${items}<div class="card white"><h3>Comentário da orientação (opcional)</h3>${rev?.stale?'<div class="notice" style="margin-bottom:10px">Você editou esta etapa depois do último parecer registrado.</div>':''}<p class="small">${rev?'Último registro: '+esc(rev.reviewer)+' · '+esc(rev.date)+': '+esc(rev.comment):'Nenhum comentário registrado ainda.'}</p><button type="button" class="btn sm" data-action="review">Registrar comentário recebido</button></div><div class="action-footer"><button type="button" class="btn" data-action="snapshot">Guardar uma versão</button><div class="flex"><button type="button" class="btn" data-action="jump" data-stage="${Math.max(1,s.id-1)}" ${s.id===1?'disabled':''}>← Etapa anterior</button><button type="button" class="btn primary" data-action="jump" data-stage="${Math.min(8,s.id+1)}">${s.id===8?'Concluir revisão':'Ir para a Etapa '+Math.min(8,s.id+1)+' →'}</button></div></div></div>`;}
function renderProjectBridge(){
  const box=R.getElementById('projectBridge');if(!box)return;
  const list=window.ScriptoriumProjetos?.listar()||[];
  if(!list.length){box.hidden=true;return;}
  const active=list[0];
  const step=active.proximo_passo||{};
  box.hidden=false;
  box.innerHTML=`<div><strong>Seu artigo em andamento:</strong> ${esc(active.titulo||'Sem título')} · <span class="muted">${esc(step.titulo||'Em elaboração')}</span></div><button type="button" class="btn sm" data-action="open-articles">Abrir em Seus artigos →</button>`;
}
function markChanged(stageId){const deps=stageId===2?[2,4,5,6,7,8]:stageId===3?[3,4,5,6,7,8]:stageId===4?[4,5,6,7,8]:stageId===5?[5,6,7,8]:stageId===6?[6,7,8]:stageId===7?[7,8]:[stageId];let invalidated=false;for(const id of deps){for(let i=0;i<byStage(id).criteria.length;i++){const k=`${id}:${i}`;if(state.criteria[k]){state.criteria[k]=false;invalidated=true;}}if(state.reviews[id]&&!state.reviews[id].stale){state.reviews[id].stale=true;invalidated=true;}}if(invalidated)notify('Como houve alterações, revise os critérios relacionados quando puder.');}
function render(){HOST.dataset.theme=temaDoSite();HOST.style.setProperty('--font',state.font);renderHeader();renderChain();renderStations();renderProjectBridge();R.getElementById('stageBody').innerHTML=state.tab==='entender'?renderEntender(byStage(state.active)):state.tab==='preencher'?renderPreencher(byStage(state.active)):renderConferir(byStage(state.active));updateStatus();}

function modal(title,content,buttons=''){lastModalFocus=R.activeElement;R.getElementById('modalMount').innerHTML=`<div class="modal-wrap" id="modalBackdrop"><div class="modal" id="activeModal" role="dialog" aria-modal="true" aria-labelledby="modalTitle" tabindex="-1"><div class="modal-header"><div id="modalTitle" class="modal-title">${esc(title)}</div><button type="button" class="btn sm" data-action="close-modal" aria-label="Fechar janela">✕</button></div><div class="modal-content">${content}</div>${buttons?`<div class="modal-footer">${buttons}</div>`:''}</div></div>`;R.getElementById('activeModal').focus();}
function closeModal(){R.getElementById('modalMount').innerHTML='';if(lastModalFocus&&lastModalFocus.focus)lastModalFocus.focus();}
function askConfirm(title,question,confirmText,onConfirm,danger=false){pendingConfirm=onConfirm;modal(title,`<p>${esc(question)}</p><p class="small muted">Seus dados anteriores podem ser recuperados em "Versões salvas" ou por cópia de segurança.</p>`,`<button type="button" class="btn" data-action="close-modal">Cancelar</button><button type="button" class="btn ${danger?'danger':'primary'}" data-action="do-confirm">${esc(confirmText)}</button>`);}
let pendingConfirm=null;
function audit(){const arr=[];const put=(lvl,title,text,step)=>arr.push({lvl,title,text,step});const q=val('pergunta');const og=val('objetivoGeral');const tema=val('tema');
  if(!val('problema'))put('high','Problema sem descrição','Descreva sujeitos, contexto e evidências iniciais.',2);
  if(q&&/^(é |existe |há |pode |funciona |vale |será )/i.test(q))put('warn','Questão possivelmente binária','Reformule para investigação aberta, quando pertinente ao desenho.',2);
  if(!q)put('high','Questão ausente','A questão de pesquisa deve orientar as etapas posteriores.',2);
  if(tema.split(/\s+/).filter(Boolean).length>8)put('warn','Tema extenso','Prefira expressão curta em vez de título completo.',2);
  if(!val('indiciosProblema'))put('warn','Indícios da situação não registrados','Diferencie inquietação pessoal de evidências documentadas.',2);
  if(recs('searchRuns').length===0)put('high','Protocolo da revisão ausente','Registre buscas com base, data, expressão, filtros e seleção (M3).',3);
  const rr=recs('readings').filter(r=>plain(r.referencia)&&plain(r.metodo)&&plain(r.resultados));if(rr.length<5)put('warn','Leitura aprofundada insuficiente para o guia','A disciplina recomenda pelo menos cinco trabalhos centrais registrados no M4.',3);
  if(recs('theories').filter(r=>plain(r.autor)&&plain(r.conceito)).length<2)put('warn','Referencial não hierarquizado','Indique pelo menos dois autores/conceitos centrais e suas funções analíticas.',3);
  if(!val('m5_lacuna'))put('high','Lacuna ainda não confrontada','Sintetize a revisão e registre se a pergunta precisou mudar.',3);
  if(!og)put('high','Objetivo geral ausente','Reformule a questão central como ação investigativa.',4);
  if(og&&!/^(analisar|compreender|investigar|examinar|caracterizar|avaliar|identificar|verificar|descrever|comparar|explicar|mapear|interpretar)\b/i.test(og))put('warn','Verbo do objetivo merece revisão','Confira o uso de um verbo de conhecimento no infinitivo.',4);
  const objectives=recs('objectives').filter(o=>plain(o.texto));if(objectives.length<3)put('warn','Objetivos específicos','A disciplina orienta três a quatro etapas investigativas (M7).',4);
  for(const [i,o] of objectives.entries())if(/\b(aplicar question[aá]rio|fazer entrevista|enviar formul[aá]rio|ler artigos|construir software)\b/i.test(o.texto))put('warn',`Objetivo específico ${i+1} pode ser tarefa`,'Reveja se descreve conhecimento produzido ou ação operacional.',4);
  if(!val('estrategia')||!val('abordagem')||!val('epistemologia'))put('high','Desenho metodológico incompleto','Informe estratégia, abordagem e perspectiva epistemológica.',5);
  for(const [i,o] of objectives.entries()){const mm=(state.records.methodLinks||{})[o.id]||{};for(const [key,label] of [['dados','dados'],['instrumento','instrumento'],['analise','técnica de análise']])if(!plain(mm[key]))put('high',`M8 · Objetivo específico ${i+1}`,`Falta vincular ${label} ao objetivo: ${o.texto.slice(0,65)}.`,5);}
  if(!val('etica'))put('warn','Ética e proteção de dados','Registre o enquadramento ético aplicável e as autorizações necessárias.',5);
  if(!isArticle()&&(!val('pttDemanda')||!val('pttAvaliacao')))put('high','Produto sem demanda ou avaliação','Especifique demanda concreta e como os dados da pesquisa o avaliarão.',6);
  if(!isArticle()&&!val('pttReplicacao'))put('warn','Replicabilidade não detalhada','Informe requisitos para reutilização do produto.',6);
  if(isArticle()&&!val('resultadosPorObjetivo'))put('high','Resultados não organizados','Apresente os resultados por objetivo específico (Etapa 6).',6);
  if(isArticle()&&!val('comparacaoRevisao'))put('warn','Discussão sem comparação com a revisão','Compare seus resultados com os estudos da Etapa 3.',6);
  if(isArticle()&&!val('limitacoes'))put('warn','Limitações não declaradas','Diga o que restringe o alcance das conclusões.',6);
  if(isArticle()&&!val('revistaAlvo'))put('warn','Revista-alvo não definida','A revista define tamanho, estrutura e normas do artigo.',7);
  if(isArticle()&&!val('sec_resumo'))put('warn','Resumo ausente','O resumo deve trazer objetivo, método, resultados e conclusão.',7);
  if(!val('sec_referencias'))put('warn','Referências do projeto ausentes','Inclua somente as fontes efetivamente verificadas.',7);
  if(!isArticle()&&recs('timeline').length===0)put('warn','Cronograma ausente','Inclua atividades, datas, dependências e entregáveis.',7);
  if(recs('aiUse').length===0&&!/não utilizei/i.test(val('registroIA_M12')))put('warn','Uso de IA não documentado','Registre usos efetivos ou declare explicitamente que não houve uso.',8);
  for(const s of STAGES)if(info(s.id).code==='empty')put('info',`Etapa ${s.id} não iniciada`,'É possível avançar livremente, mas ela precisa ser revisada antes da conclusão.',s.id);
  if(arr.length===0)put('good','Nenhuma pendência estrutural detectada','Isso não constitui validação científica. Confira a relevância, veracidade e coerência com a orientação.',8);
  return arr;}
function auditHTML(){const list=audit();const high=list.filter(x=>x.lvl==='high').length;return `<div class="card warning"><strong>${high} pendência(s) estruturais de maior prioridade</strong><p class="small muted">Estas verificações analisam presença e padrões simples de texto. Não são uma avaliação semântica da pesquisa e não utilizam IA neste arquivo.</p></div><ul class="audit-list">${list.map(a=>`<li class="${a.lvl}"><strong>${esc(a.title)} ${badge('Etapa '+a.step)}</strong>${esc(a.text)} <button type="button" class="btn sm" data-action="jump" data-stage="${a.step}">Ir para etapa</button></li>`).join('')}</ul>`;}
function openAudit(){modal('Conferência de coerência: indicadores locais',`<div class="modal-scroll">${auditHTML()}</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>`);}
function glossaryModal(){const entries=[...EXTRA_GLOSSARY];modal('Dicionário de pesquisa',`<p class="small muted">Definições resumidas para orientar a leitura; consulte a literatura especializada para fundamentação.</p><div class="modal-scroll">${entries.map(([term,def])=>`<div class="card white" style="margin:8px 0"><strong>${esc(term)}</strong><p class="small" style="margin:6px 0 0">${esc(def)}</p></div>`).join('')}</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>`);}
function helpModal(){modal('Como usar o guia',`<div class="section-gap"><p>O guia organiza a construção de um artigo (ou de um projeto de pesquisa) em oito etapas, sempre com <strong>Entender → Escrever → Conferir</strong>.</p><ol class="helper-list"><li>Comece pela preparação (Etapa 1) e avance até a validação final (Etapa 8).</li><li>Volte a qualquer etapa quando uma nova leitura alterar suas decisões.</li><li>Preencha modelos M1–M12; na Etapa 3, cada busca e cada trabalho têm um registro próprio.</li><li>Use “Conferir relações” para localizar possíveis omissões estruturais, sem presumir aprovação científica.</li><li>Escolha no topo se está construindo um artigo ou um projeto de pesquisa: as etapas 6 a 8 mudam conforme o tipo.</li><li>Use “Versões salvas” para criar cópias recuperáveis; mantenha também backups JSON em lugar seguro.</li><li>Na exportação, gere síntese, projeto ou memorial; use o navegador para imprimir/salvar em PDF.</li></ol><div class="notice"><strong>Limites:</strong> o guia não usa IA; com login no Scriptorium, fica salvo na sua conta; sem login, só neste navegador. As regras da disciplina de origem (PPIE) devem ser adaptadas às exigências do programa do estudante, como o ProfEPT. M9 e M12 foram estruturados como adaptações porque os modelos integrais não constavam do material anexado.</div><p class="small muted">Dados locais podem ser perdidos ao limpar o armazenamento, mudar de dispositivo ou usar navegação privativa. A interface nunca substitui orientação, CEP ou banca.</p></div>`,`<button type="button" class="btn primary" data-action="close-modal">Entendi</button>`);}
function examplesModal(){modal('Exemplos prontos (sem apagar o que você escreveu)',`<p>Os exemplos originais da disciplina servem apenas como referência. Você pode consultar cada campo sem inseri-los no seu texto.</p><p class="small">Se quiser testar uma demonstração, o botão abaixo preenche <strong>somente campos vazios</strong>, preserva tudo o que você já escreveu e cria uma versão recuperável.</p><div class="card warning"><strong>Aviso:</strong> exemplos ilustrativos não devem ser usados como evidências científicas ou dados reais.</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button><button type="button" class="btn primary" data-action="fill-examples">Inserir apenas nos campos vazios</button>`);}
function fieldExampleModal(key){const f=STAGES.flatMap(s=>s.fields).find(x=>x.key===key);if(!f)return;modal('Exemplo · '+f.label,`<p class="small muted">Apenas um exemplo ilustrativo da atividade, não uma resposta científica validada.</p><div class="example-text">${esc(f.example||'Não há exemplo preparado para este campo. Use a orientação do próprio campo.')}</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>${f.example?`<button type="button" class="btn primary" data-action="insert-example" data-field="${esc(key)}">Inserir neste campo</button>`:''}`);}
function versionModal(){const items=state.versions.slice().reverse();modal('Versões completas e recuperáveis',`<p class="small muted">Cada versão salva uma fotografia de campos, modelos, checklist e revisões. Limite local: ${MAX_VERSIONS} versões.</p><div class="card"><label for="versionNote" class="bold">Motivo da nova versão</label><input class="form-control" id="versionNote" placeholder="Ex.: pergunta revisada após leitura da literatura"><div style="margin-top:10px"><button type="button" class="btn sm primary" data-action="save-version">Salvar versão agora</button></div></div><div class="modal-scroll" style="margin-top:14px">${items.length?items.map(x=>`<div class="card white" style="margin-bottom:10px"><div class="flex spread"><div><strong>${esc(x.label)}</strong> <span class="tag">${esc(x.date)}</span></div><button type="button" class="btn sm" data-action="restore-version" data-version="${esc(x.id)}">Restaurar cópia</button></div><p class="small muted" style="margin-bottom:0">${esc(x.note||'Sem observações')} · ${x.stage?'Etapa '+x.stage:'Geral'}</p></div>`).join(''):'<p class="empty">Ainda não existem versões manuais.</p>'}</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>`);}
function reviewModal(){const prev=state.reviews[state.active]||{};modal('Registrar parecer recebido',`<p class="small muted">Este registro é preenchido manualmente por você e serve como histórico da orientação.</p><div class="fieldgroup"><div class="field"><label for="reviewer">Quem realizou a revisão?</label><input id="reviewer" class="form-control" value="${esc(prev.reviewer||'')}" placeholder="Docente, colega ou orientador(a)"></div><div class="field"><label for="reviewResult">Situação informada</label><select id="reviewResult" class="form-control"><option value="pendente">Há ajustes pendentes</option><option value="revisado" ${prev.result==='revisado'?'selected':''}>Revisão registrada</option></select></div><div class="field full"><label for="reviewComment">Comentários recebidos e providências</label><textarea id="reviewComment" rows="4">${esc(prev.comment||'')}</textarea></div></div>`,`<button type="button" class="btn" data-action="close-modal">Cancelar</button><button type="button" class="btn primary" data-action="save-review">Registrar parecer</button>`);}
function backupModal(){let trash=null;try{trash=JSON.parse(localStorage.getItem(TRASH_KEY)||'null')}catch(e){}modal('Cópia de segurança e recuperação',`<div class="section-gap"><div class="card warning"><strong>Onde seus dados ficam.</strong><p class="small" style="margin:6px 0 0">Com login no Scriptorium, o guia é salvo na sua conta e aparece em qualquer dispositivo. Sem login, fica só neste navegador e pode se perder ao limpar o histórico. O backup JSON funciona nos dois casos.</p></div><div class="flex"><button type="button" class="btn primary" data-action="download-json">Baixar cópia JSON</button><button type="button" class="btn" data-action="import-json">Restaurar de arquivo JSON</button></div><div class="card"><h3>Cópia local antes de limpar</h3><p class="small muted">${trash?'Última cópia temporária: '+esc(trash.date):'Nenhuma cópia na lixeira local.'}</p><div class="flex">${trash?'<button type="button" class="btn" data-action="restore-trash">Recuperar projeto anterior</button>':''}<button type="button" class="btn danger" data-action="reset-project">Limpar projeto…</button></div></div></div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>`);}
function settingsModal(){modal('Tamanho da letra e leitura',`<p class="small muted">Ajuste o tamanho da letra do guia para ficar mais confortável para ler. O tema claro/escuro é controlado pelo botão no topo do Scriptorium.</p><div class="flex"><button type="button" class="btn" data-action="font-down">Diminuir letra (A−)</button><button type="button" class="btn" data-action="font-reset">Tamanho normal</button><button type="button" class="btn primary" data-action="font-up">Aumentar letra (A+)</button></div><div class="notice" style="margin-top:16px">Este guia não usa IA: as conferências são regras simples de apoio e a decisão é sempre sua e da orientação.</div>`,`<button type="button" class="btn" data-action="close-modal">Fechar</button>`);}
function readableField(f){const v=val(f.key);return `<section><h3>${esc(f.label)}</h3><div class="print-p">${htmlLines(v||'[Não preenchido]')}</div></section>`;}
function recordPrint(name){const c=REPEAT[name];return `<section><h2>${esc(c.model)} · ${esc(c.title)}</h2>${recs(name).length?recs(name).map((r,i)=>`<div class="print-box"><h3>Registro ${i+1}</h3>${c.fields.map(([key,label])=>`<p class="print-p"><strong>${esc(label)}:</strong> ${htmlLines(r[key]||'(vazio)')}</p>`).join('')}</div>`).join(''):'<p class="empty">Nenhum registro preenchido.</p>'}</section>`;}
function m9HTML(){return renderM9().replace(/class="card white"/g,'class="print-box"');}
function exportContent(kind){let result=`<div class="small">Scriptorium MPIE · Guia de escrita · Gerado em ${esc(dateNow())}</div><h1>${kind==='resumo'?'Resumo para a orientação: M6, M9 e M10':kind==='projeto'?(isArticle()?'Artigo: versão de trabalho':'Projeto de pesquisa: versão de trabalho'):'Memorial formativo de decisões'}</h1><p class="small">Conteúdo autoral registrado no guia. Campos não preenchidos são indicados. Revisão acadêmica não substituída.</p>`;
  if(kind==='resumo'){result+=`<h2>Quadro 1: Referencial (M6)</h2>`+recs('theories').map((x,i)=>`<p class="print-p">${i+1}. ${esc(x.conceito)}: ${esc(x.autor)} · ${esc(x.aspecto)}</p>`).join('')+`<h2>Quadro 2: Projeto (M9, síntese adaptada)</h2>`+m9HTML()+(isArticle()?`<h2>Resultados e discussão</h2>`:`<h2>Quadro 3: Produto (M10)</h2>`)+byStage(6).fields.map(readableField).join('')+`<h2>Roteiro de apresentação</h2>`+presentation();return result;}
  if(kind==='projeto'&&isArticle()){const sections=[['Título','tituloFinal'],['Resumo','sec_resumo'],['Palavras-chave','palavrasChave'],['Introdução','sec_introducao'],['Revisão de literatura','sec_revisao'],['Referencial teórico','sec_referencial'],['Metodologia','sec_metodologia'],['Resultados','sec_resultados'],['Discussão','sec_discussao'],['Considerações finais','sec_conclusao'],['Referências','sec_referencias']];result+=`<p class="small">Revista-alvo: ${esc(val('revistaAlvo')||'não definida')}</p>`+sections.map(([name,key])=>`<section><h2>${esc(name)}</h2><div class="print-p">${htmlLines(val(key)||'[Não preenchido]')}</div></section>`).join('');return result;}
  if(kind==='projeto'){result+=`<h2>Identificação</h2>`+byStage(1).fields.map(readableField).join('');const sections=[['Título','tituloFinal'],['Introdução','sec_introducao'],['Revisão de literatura','sec_revisao'],['Justificativa','sec_justificativa'],['Objetivos','sec_objetivos'],['Referencial teórico','sec_referencial'],['Metodologia','sec_metodologia'],['Produto técnico-tecnológico','sec_produto'],['Referências','sec_referencias']];result+=sections.map(([name,key])=>`<section><h2>${esc(name)}</h2><div class="print-p">${htmlLines(val(key)||'[Não preenchido]')}</div></section>`).join('')+recordPrint('timeline');return result;}
  for(const s of STAGES){result+=`<section><h2>Etapa ${s.id}: ${esc(s.title)}</h2><p class="small">Estado: ${esc(info(s.id).label)}. Modelos: ${esc(s.models)}.</p>`+s.fields.map(readableField).join('');for(const [key,c] of Object.entries(REPEAT))if(c.stage===s.id)result+=recordPrint(key);if(s.id===5){const obs=recs('objectives');result+='<h2>M8 · Matriz metodológica</h2>'+obs.map(o=>`<div class="print-box"><h3>${esc(o.texto)}</h3>${Object.entries((state.records.methodLinks||{})[o.id]||{}).map(([key,v])=>`<p><strong>${esc(key)}:</strong> ${htmlLines(v)}</p>`).join('')}</div>`).join('');}if(s.id===8)result+=m9HTML();}
  result+='<h2>Campos herdados da versão anterior</h2>'+Object.entries(state.values).filter(([k,v])=>['descritores','basesProtocolo','sinteseRevisao','autoresConceitos','objetivosEspecificos','instrumentos','analiseEtica','publicoAplicabilidade','inovacaoImpacto','avaliacaoDeposito','introducao5Mov','cronogramaM11'].includes(k)&&plain(v)).map(([k,v])=>`<p><strong>${esc(k)}:</strong> ${htmlLines(v)}</p>`).join('')+'<h2>Versões registradas</h2>'+state.versions.map(x=>`<p>${esc(x.date)} · ${esc(x.label)} · ${esc(x.note||'')}</p>`).join('');result+='<h2>Alertas estruturais</h2>'+audit().map(x=>`<p>[${esc(x.lvl)}] Etapa ${x.step}: ${esc(x.title)}: ${esc(x.text)}</p>`).join('');return result;}
function exportModal(){modal('Exportar ou imprimir',`<p>Escolha o formato abaixo. Na opção “Imprimir / PDF”, selecione <strong>Salvar como PDF</strong> na janela de impressão do navegador.</p><div class="field"><label for="exportKind">Formato do documento</label><select id="exportKind" class="form-control"><option value="resumo">${isArticle()?'Resumo para a orientação: referencial, síntese, resultados e apresentação':'Resumo acadêmico: M6, M9, M10 e apresentação'}</option><option value="projeto">${isArticle()?'Artigo: seções na ordem da revista':'Projeto acadêmico: seções e cronograma'}</option><option value="memorial">Memorial completo: modelos, decisões e lacunas</option></select></div><div class="notice" style="margin-top:12px">A exportação organiza apenas o conteúdo que você registrou. Não cria seções nem inventa fontes, dados ou conclusões.</div>`,`<button type="button" class="btn" data-action="download-text">Baixar texto (.txt)</button><button type="button" class="btn" data-action="download-html">Baixar página (.html)</button><button type="button" class="btn primary" data-action="print-document">Imprimir / PDF</button>`);}
function download(filename,text,mime){const blob=new Blob([text],{type:mime});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=filename;document.body.appendChild(a);a.click();setTimeout(()=>{a.remove();URL.revokeObjectURL(u)},500);}
function exportKind(){return R.getElementById('exportKind')?.value||'resumo';}
function textExport(kind){const div=document.createElement('div');div.innerHTML=exportContent(kind);function walk(node){if(node.nodeType===3)return node.nodeValue||'';if(node.nodeType!==1)return '';const tag=node.tagName.toLowerCase();if(tag==='br')return '\n';const inner=Array.from(node.childNodes).map(walk).join('');if(tag==='td'||tag==='th')return inner.trim()+' | ';if(tag==='tr')return inner+'\n';if(['h1','h2','h3','p','section','div'].includes(tag))return inner+'\n';return inner;}return walk(div).replace(/\n[ \t]+/g,'\n').replace(/\n{3,}/g,'\n\n').trim();}
function standaloneDoc(kind){return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Guia de escrita: ${esc(kind)}</title><style>body{font:16px/1.55 Georgia,serif;max-width:900px;margin:2rem auto;padding:0 1rem}h1,h2{color:#1466B8}h2{border-bottom:1px solid #ddd}h3{font-size:1.08rem}section{break-inside:avoid-page}.print-p{white-space:pre-wrap}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;text-align:left;padding:8px}.print-box{border:1px solid #ddd;padding:12px;margin:12px 0} @media print{body{margin:0;max-width:none}}</style></head><body>${exportContent(kind)}</body></html>`;}
function printDoc(kind){R.getElementById('printArea').innerHTML=exportContent(kind);closeModal();setTimeout(()=>(document.body.classList.add('imprimindo-guia'),window.print()),100);}
function downloadBackup(){flush();const data={format:'scriptorium-pesquisa-guiada',schema:2,exportedAt:new Date().toISOString(),state:copy(state)};download('pesquisa-guiada-backup-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(data,null,2),'application/json;charset=utf-8');notify('Backup JSON baixado. Guarde-o fora deste navegador.');}
function migrateImported(obj){if(obj?.format==='scriptorium-pesquisa-guiada'&&obj.schema===2&&obj.state?.values&&obj.state?.records)return obj.state;
  if(obj?.values&&obj?.checks){const s=emptyState();s.values=obj.values;s.criteria=obj.checks;s.active=obj.activeStage||1;return s;}throw Error('Arquivo sem formato reconhecido.');}
function doImport(file){if(!file)return;if(file.size>8*1024*1024){notify('Backup acima do limite de 8 MB.');return;}const reader=new FileReader();reader.onload=()=>{try{const candidate=migrateImported(JSON.parse(reader.result));askConfirm('Importar backup','O backup substituirá o projeto que está aberto. Uma cópia do estado atual será guardada na lixeira local. Deseja continuar?','Importar backup',()=>{safeTrash();const preserved=state.theme,font=state.font;state={...emptyState(),...candidate};state.theme=preserved;state.font=font;state.active=Math.min(8,Math.max(1,Number(state.active)||1));if(flush()){closeModal();render();notify('Backup importado. Revise os modelos estruturados e os campos.');}else{notify('Falha ao gravar backup importado: exporte os dados.');}},true);}catch(e){notify('Falha na importação: '+e.message);}};reader.readAsText(file,'utf-8');}
function safeTrash(){try{localStorage.setItem(TRASH_KEY,JSON.stringify({date:dateNow(),state:copy(state)}));return true}catch(e){savingError=true;updateStatus();return false;}}
function restoreVersion(id){const ver=state.versions.find(v=>v.id===id);if(!ver||!ver.snapshot)return;askConfirm('Restaurar versão',`Restaurar a cópia de ${ver.date} (“${ver.label}”)? O estado atual será guardado antes como versão recuperável.`,'Restaurar',()=>{snapshot('Antes de restaurar '+ver.label,state.active,'Snapshot automático de segurança.');const oldVersions=state.versions;const oldTheme=state.theme,oldFont=state.font;Object.assign(state,copy(ver.snapshot));state.versions=oldVersions;state.theme=oldTheme;state.font=oldFont;flush();closeModal();render();notify('Versão restaurada e estado anterior preservado.');});}
function fillExamplesEmpty(){const count=STAGES.reduce((a,s)=>a+s.fields.filter(f=>f.example&&!val(f.key)).length,0);askConfirm('Inserir exemplos','Inserir até '+count+' exemplos somente nos campos que estão vazios? Campos já preenchidos e checklists serão preservados. Os exemplos são ilustrativos e não podem ser usados como evidência científica.','Inserir apenas nos vazios',()=>{snapshot('Antes de inserir exemplos',state.active,'Cópia preventiva.');markChanged(state.active);for(const s of STAGES)for(const f of s.fields)if(f.example&&!val(f.key))state.values[f.key]=f.example;flush();closeModal();render();notify('Exemplos inseridos somente nos campos vazios.');});}
function actionHandler(btn){const a=btn.dataset.action;const rec=btn.dataset.rec,item=btn.dataset.item;
  const openMenu=btn.closest('details.more-menu');if(openMenu)openMenu.open=false;
  if(a==='set-tipo'){const tipo=btn.dataset.tipo;if(tipo===state.tipo)return;for(const id of [6,7,8])for(const k of Object.keys(state.criteria))if(k.startsWith(id+':'))delete state.criteria[k];state.tipo=tipo;applyMode();scheduleSave();render();notify(tipo==='artigo'?'Modo Artigo científico selecionado (etapas 6 a 8 adaptadas).':'Modo Projeto de pesquisa selecionado (etapas 6 a 8 com produto e cronograma).');return;}
  if(a==='open-articles'){window.ScriptoriumNavegar?.('3');return;}
  if(a==='tab'){state.tab=btn.dataset.tab;flush();render();return;}
  if(a==='jump'){state.active=Math.min(8,Math.max(1,Number(btn.dataset.stage)||1));state.tab='entender';flush();closeModal();render();R.getElementById('stageSheet')?.scrollIntoView({behavior:'smooth',block:'start'});return;}
  if(a==='glossary'){glossaryModal();return;}if(a==='help'){helpModal();return;}if(a==='examples'){examplesModal();return;}if(a==='versions'){versionModal();return;}if(a==='audit'){openAudit();return;}if(a==='export'){exportModal();return;}if(a==='backup'){backupModal();return;}if(a==='settings'){settingsModal();return;}
  if(a==='close-modal'){closeModal();return;}if(a==='do-confirm'){const fn=pendingConfirm;pendingConfirm=null;if(fn)fn();return;}
  if(a==='field-example'){fieldExampleModal(btn.dataset.field);return;}
  if(a==='insert-example'){const f=STAGES.flatMap(s=>s.fields).find(f=>f.key===btn.dataset.field);if(!f||!f.example)return;const fill=()=>{snapshot('Antes de inserir exemplo',state.active,'Cópia preventiva.');markChanged(state.active);state.values[f.key]=f.example;flush();closeModal();render();notify('Exemplo inserido. Revise o texto antes de utilizá-lo.');};if(isFilled(f.key))askConfirm('Confirmar substituição','O campo já contém texto. Substituí-lo pelo exemplo? Uma versão será preservada antes da alteração.','Substituir campo',fill,true);else fill();return;}
  if(a==='fill-examples'){fillExamplesEmpty();return;}
  if(a==='add-rec'){markChanged(state.active);state.records[rec]=recs(rec);state.records[rec].push({id:uid()});scheduleSave();render();const details=R.querySelector(`#repeat-${rec} details:last-of-type`);if(details)details.open=true;return;}
  if(a==='remove-rec'){askConfirm('Remover registro','Remover este registro de '+(REPEAT[rec]?.model||'modelo')+'? Será criada uma versão recuperável antes da remoção.','Remover registro',()=>{snapshot('Antes de remover registro',state.active,'Cópia preventiva.');markChanged(state.active);state.records[rec]=recs(rec).filter(r=>r.id!==item);flush();closeModal();render();notify('Registro removido; versão anterior preservada.');},true);return;}
  if(a==='snapshot'){modal('Guardar versão recuperável',`<label for="snapshotNote" class="bold">Qual foi a principal mudança?</label><input id="snapshotNote" class="form-control" placeholder="Ex.: revisão da pergunta após fichamentos">`,`<button type="button" class="btn" data-action="close-modal">Cancelar</button><button type="button" class="btn primary" data-action="save-version">Salvar versão</button>`);return;}
  if(a==='save-version'){const note=plain(R.getElementById('versionNote')?.value||R.getElementById('snapshotNote')?.value);snapshot('Versão '+(state.versions.length+1),state.active,note||'Cópia manual sem descrição');flush();versionModal();notify('Versão completa guardada no histórico.');return;}
  if(a==='restore-version'){restoreVersion(btn.dataset.version);return;}
  if(a==='review'){reviewModal();return;}
  if(a==='save-review'){const name=plain(R.getElementById('reviewer')?.value),comment=plain(R.getElementById('reviewComment')?.value),result=R.getElementById('reviewResult')?.value;if(!name||!comment){notify('Identifique quem revisou e registre o comentário recebido.');return;}state.reviews[state.active]={reviewer:name,comment,result,date:dateNow(),stale:false};flush();closeModal();render();notify('Registro de revisão salvo localmente.');return;}
  if(a==='toggle-theme'){state.theme=state.theme==='dark'?'light':'dark';flush();render();settingsModal();return;}
  if(a==='font-up'||a==='font-down'||a==='font-reset'){state.font=a==='font-reset'?1:Math.max(.88,Math.min(1.3,+(state.font+(a==='font-up'?.08:-.08)).toFixed(2)));flush();render();settingsModal();return;}
  if(a==='download-json'){downloadBackup();return;}if(a==='import-json'){R.getElementById('importJSON').click();return;}
  if(a==='restore-trash'){let old;try{old=JSON.parse(localStorage.getItem(TRASH_KEY)||'null')}catch(e){}if(!old?.state)return;askConfirm('Recuperar projeto anterior','Restaurar a cópia local de '+old.date+'? O atual será preservado na lixeira antes de restaurar.','Restaurar cópia',()=>{const oldState=copy(old.state);safeTrash();state={...emptyState(),...oldState};flush();closeModal();render();notify('Cópia anterior restaurada.');});return;}
  if(a==='reset-project'){modal('Confirmar limpeza do projeto',`<p>Para limpar os campos, digite <strong>APAGAR</strong>. O sistema tentará guardar antes uma cópia local recuperável. <strong>Baixe um backup JSON</strong> para maior segurança.</p><label for="resetInput">Confirmação</label><input class="form-control" id="resetInput" autocomplete="off" placeholder="Digite APAGAR">`,`<button type="button" class="btn" data-action="close-modal">Cancelar</button><button type="button" class="btn danger" data-action="reset-final">Limpar e preservar cópia local</button>`);return;}
  if(a==='reset-final'){if(plain(R.getElementById('resetInput')?.value)!=='APAGAR'){notify('Digite APAGAR para confirmar.');return;}if(!safeTrash()){notify('A cópia preventiva falhou. Baixe um backup antes de limpar.');return;}const theme=state.theme,font=state.font;state=emptyState();state.theme=theme;state.font=font;flush();closeModal();render();notify('Novo projeto iniciado. Cópia anterior disponível na área Backup.');return;}
  if(a==='download-text'){const kind=exportKind();download('pesquisa-guiada-'+kind+'.txt',textExport(kind),'text/plain;charset=utf-8');return;}
  if(a==='download-html'){const kind=exportKind();download('pesquisa-guiada-'+kind+'.html',standaloneDoc(kind),'text/html;charset=utf-8');return;}
  if(a==='print-document'){printDoc(exportKind());return;}
  if(a==='speak'){if(!('speechSynthesis'in window)){notify('Leitura em voz alta indisponível neste navegador.');return;}speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(byStage(state.active).plainExplain);u.lang='pt-BR';speechSynthesis.speak(u);return;}
}
R.addEventListener('click',ev=>{const btn=ev.target.closest('[data-action]');if(btn){ev.preventDefault();actionHandler(btn);}else if(ev.target.id==='modalBackdrop')closeModal();});
R.addEventListener('input',ev=>{const el=ev.target;if(el.dataset.field){markChanged(state.active);state.values[el.dataset.field]=el.value;scheduleSave();}
  else if(el.dataset.rec){const obj=recs(el.dataset.rec).find(r=>r.id===el.dataset.item);if(obj){markChanged(state.active);obj[el.dataset.key]=el.value;scheduleSave();}}
  else if(el.dataset.matrix){if(!state.records.methodLinks||Array.isArray(state.records.methodLinks))state.records.methodLinks={};if(!state.records.methodLinks[el.dataset.matrix])state.records.methodLinks[el.dataset.matrix]={};markChanged(state.active);state.records.methodLinks[el.dataset.matrix][el.dataset.matrixKey]=el.value;scheduleSave();}
  else if(el.dataset.evidence){state.evidence[el.dataset.evidence]=el.value;scheduleSave();}});
R.addEventListener('change',ev=>{const el=ev.target;if(el.dataset.check){state.criteria[el.dataset.check]=Boolean(el.checked);flush();render();}
  else if(el.dataset.field||el.dataset.rec||el.dataset.matrix){flush();/* Não recriar botões ao perder foco: isso cancelaria cliques de navegação. */}
});
R.getElementById('importJSON').addEventListener('change',e=>{doImport(e.target.files?.[0]);e.target.value='';});
R.addEventListener('keydown',e=>{const mm=R.getElementById('activeModal');if(!mm)return;if(e.key==='Escape'){e.preventDefault();closeModal();return;}if(e.key==='Tab'){const list=[...mm.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]')].filter(x=>x.getClientRects().length);if(!list.length)return;let i=list.indexOf(R.activeElement);if(e.shiftKey&&i<=0){e.preventDefault();list[list.length-1].focus();}else if(!e.shiftKey&&i===list.length-1){e.preventDefault();list[0].focus();}}});
window.addEventListener('beforeunload',()=>{if(saveTimer)flush();});
window.addEventListener('storage',e=>{if(e.key===STORAGE_KEY&&e.newValue){try{const other=JSON.parse(e.newValue);if(other.changedAt>lastKnownWrite){savingError=true;R.getElementById('saveStatus').textContent='⚠ Alterações detectadas em outra aba. Faça backup e recarregue para evitar conflitos.';}}catch(err){}}});
window.addEventListener('afterprint',()=>{document.body.classList.remove('imprimindo-guia');R.getElementById('printArea').innerHTML='';});


// ---------------------------------------------------------------- conta (sem login próprio)
// O login é o do site: app.js expõe window.ScriptoriumConta. Sem login, o guia fica neste navegador.
const NUVEM=(()=>{
  let user=null,base=0,timer=null,saving=false,pending=false,status='';
  const hora=()=>new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
  const setStatus=t=>{status=t;GuiaApp.refresh();};
  async function call(method,query='',body){
    const token=await user.getIdToken();
    const r=await fetch('/api/guia/estado'+query,{method,headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
    let data=null;try{data=await r.json();}catch(_e){}
    return {ok:r.ok,status:r.status,data};
  }
  async function abrir(){
    setStatus('Conferindo o guia salvo na sua conta…');
    let r;try{r=await call('GET');}catch(_e){setStatus('Sem conexão com a conta agora; seguindo só neste navegador.');return;}
    if(r.status===403){user=null;setStatus('Sua conta ainda não foi liberada; o guia fica só neste navegador.');return;}
    if(!r.ok){setStatus('Não foi possível abrir o guia da conta agora; seguindo só neste navegador.');return;}
    const remote=r.data.estado,local=GuiaApp.getState();
    if(remote&&(remote.changedAt||0)>(local.changedAt||0)){base=remote.changedAt||0;GuiaApp.adopt(remote,true);setStatus('✓ Guia da sua conta aberto às '+hora());}
    else{base=remote?(remote.changedAt||0):0;await salvar();}
  }
  async function salvar(forcar=false){
    if(!user)return;if(saving){pending=true;return;}saving=true;
    try{
      const r=await call('PUT',`?base=${base}${forcar?'&forcar=true':''}`,GuiaApp.getState());
      if(r.ok){base=r.data.changedAt;setStatus('✓ Salvo na sua conta às '+hora());}
      else if(r.status===409){await conflito();}
      else if(r.status===413)setStatus('O guia passou do limite da conta (3 MB). Exporte um backup e apague versões antigas.');
      else setStatus('Salvo só neste navegador; a conta não respondeu ('+r.status+'). Tentaremos de novo na próxima alteração.');
    }catch(_e){setStatus('Salvo só neste navegador; sem conexão com a conta agora.');}
    finally{saving=false;if(pending){pending=false;agendar();}}
  }
  async function conflito(){
    const r=await call('GET');
    if(!r.ok||!r.data.estado){await salvar(true);return;}
    base=r.data.estado.changedAt||0;GuiaApp.adopt(r.data.estado,true);
    setStatus('O guia foi alterado em outro dispositivo. Abrimos a versão da conta; a deste navegador ficou em Versões.');
  }
  function agendar(){if(!user)return;clearTimeout(timer);timer=setTimeout(()=>salvar(),1500);}
  function conta(u){user=u||null;if(user)abrir();else setStatus('');}
  return {agendar,conta,texto:()=>status||null};
})();

const GuiaApp={
  getState:()=>state,
  adopt(remote,keepLocal){if(keepLocal&&Object.keys(state.values||{}).length){snapshot('Cópia deste navegador antes de sincronizar',0,'Guardada automaticamente ao abrir a versão salva na conta.');remote.versions=[...(remote.versions||[]),...state.versions.slice(-1)].slice(-MAX_VERSIONS);}
    state={...emptyState(),...remote};lastKnownWrite=state.changedAt||0;try{localStorage.setItem(STORAGE_KEY,JSON.stringify(state));}catch(e){}applyMode();render();},
  refresh(){updateStatus();}
};
load();applyMode();if(!lastKnownWrite&&!savingError)persist();render();
const CONTA=window.ScriptoriumConta;if(CONTA){NUVEM.conta(CONTA.usuario());CONTA.aoMudar(u=>NUVEM.conta(u));}
window.ScriptoriumProjetos?.aoMudar(()=>renderProjectBridge());

}
window.ScriptoriumGuia={montar};
})();
