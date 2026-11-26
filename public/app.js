import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import { initializeAuth, getAuth, indexedDBLocalPersistence, browserLocalPersistence, browserSessionPersistence, browserPopupRedirectResolver, setPersistence, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';

const $ = (id) => document.getElementById(id);
// Modo com API Gemini (geração pelo servidor, chave pessoal, fichamento e testes com IA).
// Desligado desde 25/11/2026: a escrita é feita pela IA do pesquisador via MCP.
// Para voltar a mostrar tudo, troque para true.
const API_MODE = false;
document.body.classList.toggle('sem-api', !API_MODE);
// Com a API desligada, basta a conta estar liberada para usar a biblioteca e o MCP.
const canWork = () => API_MODE ? !!accountAccess?.research_generation_enabled : !!accountAccess && !accountAccess.legacy_backend;
const config = window.PAPER_FIREBASE_CONFIG;
if (!config || !config.apiKey || config.apiKey === 'SUBSTITUIR') {
  $('auth-status').textContent = 'Falta configurar public/config.js. Consulte README.md.';
  $('login').disabled = true;
  throw new Error('Firebase Web App não configurado');
}
const firebaseApp = initializeApp(config);
// Persistência explícita: localStorage primeiro (rápido e resistente a limpeza de IndexedDB),
// com IndexedDB e sessão como reserva. Evita pedir login toda vez que o site abre.
let auth;
try {
  auth = initializeAuth(firebaseApp, {
    persistence: [browserLocalPersistence, indexedDBLocalPersistence, browserSessionPersistence],
    popupRedirectResolver: browserPopupRedirectResolver,
  });
} catch (_) {
  auth = getAuth(firebaseApp);
}
const provider = new GoogleAuthProvider();
const SESSION_CACHE_KEY = 'scriptorium_session_cache_v1';
const uiCacheKey = (uid) => 'scriptorium_ui_cache_' + uid;
function readSessionCache() {
  try {
    const data = JSON.parse(localStorage.getItem(SESSION_CACHE_KEY) || 'null');
    if (data && data.uid && data.email && (Date.now() - (data.savedAt || 0)) < 30 * 86400 * 1000) return data;
  } catch (_) {}
  return null;
}
function writeSessionCache(u, access) {
  if (!u || !$('keep-signed-in')?.checked) return;
  try {
    localStorage.setItem(SESSION_CACHE_KEY, JSON.stringify({
      uid: u.uid, email: u.email || '', access: access || null, savedAt: Date.now()
    }));
  } catch (_) {}
}
function clearSessionCache(uid) {
  try {
    localStorage.removeItem(SESSION_CACHE_KEY);
    if (uid) localStorage.removeItem(uiCacheKey(uid));
  } catch (_) {}
}
function readUiCache(uid) {
  try { return JSON.parse(localStorage.getItem(uiCacheKey(uid)) || 'null'); } catch (_) { return null; }
}
function writeUiCache(uid, patch) {
  if (!uid) return;
  try {
    const prev = readUiCache(uid) || {};
    localStorage.setItem(uiCacheKey(uid), JSON.stringify({ ...prev, ...patch, savedAt: Date.now() }));
  } catch (_) {}
}
// Ponte para o Guia de escrita mostrar o estado do artigo ativo sem chamadas extras.
window.ScriptoriumProjetos = window.ScriptoriumProjetos || {
  _lista: [], _cbs: [],
  listar() { return this._lista; },
  aoMudar(cb) { this._cbs.push(cb); },
  definir(lista) { this._lista = Array.isArray(lista) ? lista : []; this._cbs.forEach(cb => { try { cb(this._lista); } catch (_) {} }); }
};
// Fase 1: Fonte única de verdade da Biblioteca compartilhada com o Guia (/citar, ABNT e Fichamentos).
const ROLE_LABELS = {
  '': 'Sem papel definido',
  marco_teorico: 'Marco Teórico',
  metodo: 'Método',
  evidencia: 'Evidência',
  contraponto: 'Contraponto',
};
const READING_LABELS = {
  a_ler: 'A ler',
  lido: 'Lido',
  incluido: 'Incluído no projeto',
  descartado: 'Descartado',
};
window.ScriptoriumBiblioteca = window.ScriptoriumBiblioteca || {
  _lista: [], _cbs: [],
  listar() { return this._lista; },
  aoMudar(cb) { this._cbs.push(cb); },
  definir(lista) { this._lista = Array.isArray(lista) ? lista : []; this._cbs.forEach(cb => { try { cb(this._lista); } catch (_) {} }); },
  abrirEstudo(id) {
    const it = this._lista.find(x => x.id === id);
    if (it) openLibraryStudyModal(it);
  },
  async checarCitacoes(text) {
    if (!user || !String(text || '').trim()) return null;
    const r = await request('/library/check-citations', { method: 'POST', body: JSON.stringify({ text }) });
    return await r.json();
  },
};
let user = null;
let refreshInterval = null;
let libraryItems = [];
let selectedSourceIds = new Set();


async function request(path, options = {}) {
  if (!user) throw new Error('Não autenticado');
  const token = await user.getIdToken();
  const r = await fetch(`/api${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.headers || {}) }
  });
  if (!r.ok) {
    let msg = `Erro HTTP ${r.status}`;
    try { const data = await r.json(); msg = typeof data.detail === 'string' ? data.detail : msg; } catch (_e) {}
    const error = new Error(msg);
    error.status = r.status;
    throw error;
  }
  return r;
}

$('login').addEventListener('click', async () => {
  $('auth-status').textContent = 'Abrindo login do Google…';
  const keep = $('keep-signed-in') ? $('keep-signed-in').checked : true;
  try {
    await setPersistence(auth, keep ? browserLocalPersistence : browserSessionPersistence);
  } catch (_) { /* segue com a persistência padrão */ }
  try { await signInWithPopup(auth, provider); }
  catch (err) {
    if (['auth/popup-blocked','auth/cancelled-popup-request'].includes(err.code)) {
      await signInWithRedirect(auth, provider);
    } else { $('auth-status').textContent = `Falha no login: ${err.message}`; }
  }
});
getRedirectResult(auth).catch(e => { $('auth-status').textContent = e.message; });
$('logout').addEventListener('click', () => {
  clearSessionCache(user?.uid);
  signOut(auth);
});


function libraryMessage(text) { $('library-message').textContent = text; }

// Contexto padrão (8 fontes, 75 mil caracteres) ou ampliado (20 fontes, 300 mil).
const CONTEXT_LIMITS = {padrao: {sources: 8, chars: 75000}, ampliado: {sources: 20, chars: 300000}};
window.SCRIPTORIUM_CONTEXT_LIMITS = CONTEXT_LIMITS;
function contextSize() { return $('context-size')?.value === 'ampliado' ? 'ampliado' : 'padrao'; }
function updateSelectedCount() {
  const max = CONTEXT_LIMITS[contextSize()].sources;
  $('selected-count').textContent = selectedSourceIds.size + ` fonte(s) selecionada(s) para a próxima pesquisa (máximo de ${max} no contexto ${contextSize()}).`;
}
$('context-size')?.addEventListener('change', () => {
  const max = CONTEXT_LIMITS[contextSize()].sources;
  if (selectedSourceIds.size > max) {
    $('context-size').value = 'ampliado';
    libraryMessage(`Há ${selectedSourceIds.size} fontes selecionadas; desmarque algumas para voltar ao contexto padrão (até 8).`);
  }
  updateSelectedCount();
});

function displayLibrary() {
  renderNewProjectSources();
  const target = $('library-list');
  target.replaceChildren();
  const filter = $('library-filter').value.trim().toLowerCase();
  const items = libraryItems.filter((i) =>
    [i.name, i.collection, i.description].some((v) => String(v || '').toLowerCase().includes(filter))
  );
  if (!items.length) {target.textContent='Nenhum documento encontrado. Adicione PDFs, DOCX ou bibliografias para começar.';return;}
  for (const item of items) {
    const line = document.createElement('div'); line.className = 'library-item'; line.dataset.libraryId = item.id;
    const body = document.createElement('div');
    const label = document.createElement('label');
    const check = document.createElement('input'); check.type='checkbox';
    check.checked = selectedSourceIds.has(item.id);
    check.setAttribute('aria-label','Usar fonte ' + item.name + ' na próxima pesquisa');
    check.addEventListener('change', () => {
      if (check.checked && selectedSourceIds.size >= CONTEXT_LIMITS.ampliado.sources) {
        check.checked=false;libraryMessage('Máximo de 20 fontes por pesquisa (contexto ampliado).');return;
      }
      if (check.checked && selectedSourceIds.size >= CONTEXT_LIMITS.padrao.sources && contextSize() === 'padrao') {
        $('context-size').value = 'ampliado';
        libraryMessage('Contexto ampliado ativado: até 20 fontes e 300 mil caracteres. Cada chamada à IA fica maior, então o custo na sua chave aumenta.');
      }
      if(check.checked) selectedSourceIds.add(item.id);
      else selectedSourceIds.delete(item.id);
      libraryMessage('');updateSelectedCount();
    });
    const name = document.createElement('span'); name.textContent = item.name;
    const bibOk = item.bib_entry && ['doi', 'corrigida_pelo_texto', 'confirmada_pelo_pesquisador', 'confirmada_duas_fontes', 'ficha_da_biblioteca'].includes(item.bib_entry.how);
    const refPill = el('span', bibOk ? '✓ Referência confirmada' : (item.bib_entry ? 'Referência para conferir' : 'Referência pendente'), 'lib-ref-pill' + (bibOk ? '' : ' pending'));
    label.append(check, name);
    const titleLine = document.createElement('div');
    titleLine.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:6px';
    titleLine.append(label, refPill);
    if (item.role && ROLE_LABELS[item.role]) titleLine.append(el('span', ROLE_LABELS[item.role], 'lib-role-pill'));
    if (item.reading_status && item.reading_status !== 'a_ler') {
      titleLine.append(el('span', READING_LABELS[item.reading_status] || item.reading_status, 'lib-status-pill ' + item.reading_status));
    }
    const notesCount = (item.study_notes || []).length;
    if (notesCount) titleLine.append(el('span', `${notesCount} fichamento(s)`, 'lib-status-pill'));
    body.append(titleLine);
    const meta = document.createElement('div');meta.className='library-meta';
    const bibHint = item.bib_entry?.fields?.author ? ` · ${item.bib_entry.fields.author.split(' and ')[0]} (${item.bib_entry.fields.year || '?'})` : '';
    meta.textContent = (item.collection||'Geral') + ' · ' + String(item.format||'').toUpperCase() +
      ' · ' + (item.size / 1024).toFixed(0) + ' KB' + bibHint;
    body.append(meta);
    if (item.description) {
      const desc = document.createElement('p');desc.className='library-note';
      desc.textContent=item.description;body.append(desc);
    }
    const actions = document.createElement('div');actions.className='library-actions';
    const studyBtn = document.createElement('button');studyBtn.type='button';
    studyBtn.textContent = notesCount ? `Fichar / ABNT (${notesCount})` : 'Fichar / ABNT';
    studyBtn.addEventListener('click', () => openLibraryStudyModal(item));
    const refBtn = document.createElement('button');refBtn.type='button';refBtn.textContent = bibOk ? 'Editar referência' : 'Conferir referência';
    refBtn.addEventListener('click', () => toggleLibraryRefEditor(item, body));
    const copyCiteBtns = [];
    if (item.abnt?.cite_parenthetical) {
      const cBtn = document.createElement('button'); cBtn.type = 'button';
      cBtn.textContent = `Copiar ${item.abnt.cite_parenthetical}`;
      cBtn.title = 'Copiar citação ABNT para colar no texto';
      cBtn.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(item.abnt.cite_parenthetical); libraryMessage('✓ Citação copiada: ' + item.abnt.cite_parenthetical); }
        catch (_) { libraryMessage(item.abnt.cite_parenthetical); }
      });
      copyCiteBtns.push(cBtn);
    }
    const down = document.createElement('button');down.type='button';down.textContent='Baixar original';
    down.addEventListener('click', async()=>{
      try{
        const r=await request('/library/items/'+item.id+'/download');
        const blob=await r.blob();
        const url=URL.createObjectURL(blob);
        const a=document.createElement('a');a.href=url;a.download=item.name;
        document.body.append(a);a.click();a.remove();
        setTimeout(()=>URL.revokeObjectURL(url),5000);
      }catch(e){libraryMessage(e.message)}
    });
    const archive = document.createElement('button');archive.type='button';archive.textContent='Arquivar';
    archive.addEventListener('click',async()=>{
      archive.disabled=true;
      try{await request('/library/items/'+item.id+'/archive',{method:'POST'});
        selectedSourceIds.delete(item.id);await loadLibrary();
      }catch(e){libraryMessage(e.message);archive.disabled=false}
    });
    const remove = document.createElement('button');remove.type='button';remove.textContent='Apagar';
    remove.className='library-delete btn-danger-text';
    remove.addEventListener('click',()=>deleteLibraryItem(item));
    actions.append(studyBtn, refBtn, ...copyCiteBtns, down, archive, remove);body.append(actions);line.append(body);target.append(line);
  }
  renderDuplicatesBanner();
}

function renderDuplicatesBanner() {
  const box = $('duplicates-banner');
  if (!box) return;
  const byKey = new Map();
  const addKey = (k, item) => { if (!k) return; if (!byKey.has(k)) byKey.set(k, []); byKey.get(k).push(item); };
  for (const item of libraryItems) {
    if (item.sha256) addKey('sha:' + item.sha256, item);
    const f = (item.bib_entry && item.bib_entry.fields) || {};
    const doi = String(f.doi || (item.origin && item.origin.doi) || '').trim().toLowerCase().replace(/^https?:\/\/(dx\.)?doi\.org\/|^doi:/i, '');
    if (doi) addKey('doi:' + doi, item);
    const title = String(f.title || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    if (title.length >= 12) addKey('ty:' + title + '|' + String(f.year || '').slice(0, 4), item);
  }
  const seen = new Set();
  const groups = [];
  for (const [k, arr] of byKey.entries()) {
    if (arr.length < 2) continue;
    const sig = arr.map(x => x.id).sort().join(',');
    if (seen.has(sig)) continue;
    seen.add(sig);
    const reason = k.startsWith('sha:') ? 'mesmo arquivo' : (k.startsWith('doi:') ? 'mesmo DOI' : 'mesmo título e ano');
    groups.push({ reason, items: arr });
  }
  box.replaceChildren();
  box.classList.toggle('hidden', !groups.length);
  if (!groups.length) return;
  const det = document.createElement('details');
  det.append(el('summary', `⚠ ${groups.length} possível(is) duplicata(s) detectada(s) na biblioteca. Ver e limpar`));
  for (const g of groups) {
    const p = el('p', `${g.reason}: ${g.items.map(i => i.name).join(' · ')}`);
    p.style.margin = '6px 0';
    det.append(p);
  }
  box.append(det);
}

function openLibraryStudyModal(item) {
  const back = document.createElement('div');
  back.className = 'modal-backdrop';
  back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true');
  const box = document.createElement('div'); box.className = 'modal-box study-modal-box';
  const head = document.createElement('div'); head.className = 'modal-head';
  const title = el('strong', 'Fichamento & ABNT · ' + item.name); title.id = 'study-modal-title';
  back.setAttribute('aria-labelledby', 'study-modal-title');
  const closeX = el('button', '✕', 'btn alt'); closeX.type = 'button'; closeX.setAttribute('aria-label', 'Fechar');
  head.append(title, closeX);

  const body = document.createElement('div'); body.className = 'modal-body';
  const close = () => { document.removeEventListener('keydown', onKey); back.remove(); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  closeX.addEventListener('click', close);
  back.addEventListener('click', (e) => { if (e.target === back) close(); });
  document.addEventListener('keydown', onKey);

  // 1) Bloco ABNT (cópia em 1 clique — NBR 10520 / 6023)
  const abntSec = document.createElement('section');
  if (item.abnt && item.abnt.reference) {
    abntSec.append(el('strong', 'Citação e Referência ABNT (NBR 6023 / 10520)'));
    const prev = el('div', item.abnt.reference, 'abnt-preview');
    const bar = document.createElement('div'); bar.className = 'cite-copy-bar';
    const copyStatus = el('span', '', 'subtle');
    const mkCopy = (label, txt) => {
      const b = el('button', label, 'btn alt'); b.type = 'button'; b.style.padding = '5px 10px'; b.style.fontSize = '.8rem';
      b.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(txt); copyStatus.textContent = '✓ Copiado!'; }
        catch (_) { copyStatus.textContent = txt; }
      });
      return b;
    };
    bar.append(
      mkCopy(`Copiar ${item.abnt.cite_parenthetical}`, item.abnt.cite_parenthetical),
      mkCopy(`Copiar ${item.abnt.cite_narrative}`, item.abnt.cite_narrative),
      mkCopy('Copiar referência ABNT', item.abnt.reference),
      copyStatus
    );
    abntSec.append(prev, bar);
  } else {
    abntSec.append(el('p', 'Esta fonte ainda não tem ficha bibliográfica confirmada. Use "Conferir referência" na lista para gerar citação e ABNT automáticas.', 'subtle'));
  }
  body.append(abntSec);

  // 2) Organização metodológica (Papel + Status)
  const orgSec = document.createElement('section');
  orgSec.style.marginTop = '12px';
  orgSec.append(el('strong', 'Organização na pesquisa'));
  const grid = document.createElement('div'); grid.className = 'study-grid'; grid.style.marginTop = '6px';
  const roleWrap = document.createElement('div');
  roleWrap.append(el('label', 'Papel metodológico'));
  const selRole = document.createElement('select');
  for (const [k, v] of Object.entries(ROLE_LABELS)) selRole.append(new Option(v, k));
  selRole.value = item.role || '';
  roleWrap.append(selRole);

  const stWrap = document.createElement('div');
  stWrap.append(el('label', 'Status de leitura / triagem'));
  const selStatus = document.createElement('select');
  for (const [k, v] of Object.entries(READING_LABELS)) selStatus.append(new Option(v, k));
  selStatus.value = item.reading_status || 'a_ler';
  stWrap.append(selStatus);
  grid.append(roleWrap, stWrap);

  const reasonWrap = document.createElement('div'); reasonWrap.style.marginTop = '6px';
  const inpReason = document.createElement('input'); inpReason.type = 'text'; inpReason.maxLength = 240;
  inpReason.value = item.exclude_reason || '';
  inpReason.placeholder = 'Motivo do descarte (opcional, útil para o resumo da revisão)';
  reasonWrap.append(el('label', 'Motivo de descarte (quando Descartado)'), inpReason);
  reasonWrap.hidden = selStatus.value !== 'descartado';
  selStatus.addEventListener('change', () => { reasonWrap.hidden = selStatus.value !== 'descartado'; });

  const orgRow = document.createElement('div'); orgRow.className = 'actions'; orgRow.style.marginTop = '8px';
  const saveOrg = el('button', 'Salvar organização', 'btn alt'); saveOrg.type = 'button';
  const orgMsg = el('span', '', 'subtle');
  saveOrg.addEventListener('click', async () => {
    saveOrg.disabled = true; orgMsg.textContent = 'Salvando…';
    try {
      const r = await (await request(`/library/items/${item.id}/study`, {
        method: 'PATCH',
        body: JSON.stringify({ role: selRole.value, reading_status: selStatus.value, exclude_reason: inpReason.value.trim() }),
      })).json();
      Object.assign(item, r.item || {});
      orgMsg.textContent = '✓ Organização salva.';
      await loadLibrary();
    } catch (e) { orgMsg.textContent = e.message; }
    finally { saveOrg.disabled = false; }
  });
  orgRow.append(saveOrg, orgMsg);
  orgSec.append(grid, reasonWrap, orgRow);
  body.append(orgSec);

  // 3) Fichamentos por página (usados direto no /citar do Guia)
  const notesSec = document.createElement('section');
  notesSec.style.marginTop = '16px';
  notesSec.append(el('strong', 'Fichamentos e citações salvas (conectados ao /citar no Guia)'));
  const notesList = document.createElement('div'); notesList.style.marginTop = '8px';

  const renderNotes = () => {
    notesList.replaceChildren();
    const notes = item.study_notes || [];
    if (!notes.length) {
      notesList.append(el('p', 'Nenhum fichamento salvo ainda. Registre abaixo um trecho com página e sua interpretação — ele aparecerá pronto ao digitar /citar no Guia.', 'subtle'));
      return;
    }
    for (const n of notes) {
      const card = document.createElement('div'); card.className = 'study-note-card';
      const top = document.createElement('div'); top.style.cssText = 'display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap';
      const meta = el('strong', (n.page ? `p. ${n.page}` : 'Sem página') + (n.tag ? ` · ${n.tag}` : ''));
      meta.style.fontSize = '.82rem';
      top.append(meta);
      if (item.abnt?.cite_parenthetical && n.page) {
        const citeWithP = item.abnt.cite_parenthetical.replace(/\)$/, `, p. ${n.page})`);
        const cBtn = el('button', `Copiar ${citeWithP}`, 'btn alt'); cBtn.type = 'button'; cBtn.style.padding = '3px 8px'; cBtn.style.fontSize = '.75rem';
        cBtn.addEventListener('click', () => { navigator.clipboard?.writeText(citeWithP).catch(() => {}); });
        top.append(cBtn);
      }
      card.append(top);
      if (n.quote) card.append(el('blockquote', `“${n.quote}”`, 'study-note-quote'));
      if (n.note) { const p = el('p', n.note); p.style.margin = '4px 0'; p.style.fontSize = '.88rem'; card.append(p); }
      const foot = document.createElement('div'); foot.className = 'study-note-foot';
      const chkLbl = document.createElement('label'); chkLbl.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin:0;cursor:pointer';
      const chk = document.createElement('input'); chk.type = 'checkbox'; chk.checked = Boolean(n.support_checked);
      chk.addEventListener('change', async () => {
        try {
          const r = await (await request(`/library/items/${item.id}/notes/${n.id}`, {
            method: 'PATCH', body: JSON.stringify({ support_checked: chk.checked }),
          })).json();
          item.study_notes = r.study_notes || item.study_notes;
          await loadLibrary();
        } catch (e) { chk.checked = !chk.checked; alert(e.message); }
      });
      chkLbl.append(chk, document.createTextNode('Conferi que a fonte sustenta minha leitura (Nível 3)'));
      const del = el('button', 'Remover', 'btn alt btn-danger-text'); del.type = 'button'; del.style.padding = '3px 8px'; del.style.fontSize = '.75rem';
      del.addEventListener('click', async () => {
        try {
          const r = await (await request(`/library/items/${item.id}/notes/${n.id}`, { method: 'DELETE' })).json();
          item.study_notes = r.study_notes || [];
          renderNotes();
          await loadLibrary();
        } catch (e) { alert(e.message); }
      });
      foot.append(chkLbl, del);
      card.append(foot);
      notesList.append(card);
    }
  };
  renderNotes();

  const form = document.createElement('div'); form.style.cssText = 'margin-top:10px;padding:12px;border:1px dashed var(--border-main);border-radius:10px';
  const row1 = document.createElement('div'); row1.className = 'study-grid';
  const inpPage = document.createElement('input'); inpPage.type = 'text'; inpPage.maxLength = 24; inpPage.placeholder = 'Ex.: 47 ou 490-492';
  const inpTag = document.createElement('input'); inpTag.type = 'text'; inpTag.maxLength = 40; inpTag.placeholder = 'Ex.: autonomia, método, lacuna';
  const pWrap = document.createElement('div'); pWrap.append(el('label', 'Página(s)'), inpPage);
  const tWrap = document.createElement('div'); tWrap.append(el('label', 'Etiqueta (opcional)'), inpTag);
  row1.append(pWrap, tWrap);
  const inpQuote = document.createElement('textarea'); inpQuote.rows = 2; inpQuote.placeholder = 'Trecho literal da obra (opcional)…';
  const inpNote = document.createElement('textarea'); inpNote.rows = 2; inpNote.placeholder = 'Sua nota: por que este trecho importa para o seu problema ou método?';
  const chkNewLbl = document.createElement('label'); chkNewLbl.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin:8px 0';
  const chkNew = document.createElement('input'); chkNew.type = 'checkbox'; chkNew.checked = true;
  chkNewLbl.append(chkNew, document.createTextNode('Conferi o contexto na fonte original (sustentação humana)'));
  const addRow = document.createElement('div'); addRow.className = 'actions'; addRow.style.marginTop = '6px';
  const addBtn = el('button', '+ Salvar fichamento', 'btn'); addBtn.type = 'button';
  const addMsg = el('span', '', 'subtle');
  addBtn.addEventListener('click', async () => {
    if (!inpQuote.value.trim() && !inpNote.value.trim()) { addMsg.textContent = 'Escreva um trecho ou uma anotação.'; return; }
    addBtn.disabled = true; addMsg.textContent = 'Salvando…';
    try {
      const r = await (await request(`/library/items/${item.id}/notes`, {
        method: 'POST',
        body: JSON.stringify({
          page: inpPage.value.trim(), tag: inpTag.value.trim(),
          quote: inpQuote.value.trim(), note: inpNote.value.trim(),
          support_checked: chkNew.checked,
        }),
      })).json();
      item.study_notes = r.study_notes || [];
      inpPage.value = ''; inpTag.value = ''; inpQuote.value = ''; inpNote.value = '';
      addMsg.textContent = '✓ Fichamento salvo e disponível no /citar do Guia!';
      renderNotes();
      await loadLibrary();
    } catch (e) { addMsg.textContent = e.message; }
    finally { addBtn.disabled = false; }
  });
  addRow.append(addBtn, addMsg);
  form.append(row1, el('label', 'Trecho literal (opcional)'), inpQuote, el('label', 'Sua nota crítica'), inpNote, chkNewLbl, addRow);
  notesSec.append(notesList, form);
  body.append(notesSec);

  const foot = document.createElement('div'); foot.className = 'modal-foot';
  const doneBtn = el('button', 'Fechar', 'btn alt'); doneBtn.type = 'button';
  doneBtn.addEventListener('click', close);
  foot.append(doneBtn);
  box.append(head, body, foot);
  back.append(box);
  document.body.append(back);
  closeX.focus();
}

async function loadLibrary() {
  if(!user)return;
  try{
    const r=await request('/library/items');
    const data=await r.json();
    libraryItems=data.items||[];
    window.ScriptoriumBiblioteca?.definir(libraryItems);
    writeUiCache(user.uid, { libraryItems });
    // M13: arquivos retidos na verificação de segurança (não podem ser usados).
    const held=data.quarantined||[];const q=$('quarantine-list');
    if(q){q.replaceChildren();q.classList.toggle('hidden',!held.length);
      if(held.length){const wrap=document.createElement('details');wrap.className='quarantine-line';
        wrap.append(el('summary',`${held.length} arquivo(s) não puderam ser lidos e ficaram de fora. Ver motivo`));q.append(wrap);
        for(const h of held){const reasons=((h.guard||{}).findings||[]).filter(f=>f.severity==='alta').map(f=>f.detail).join(' ');
          const row=el('p',`${h.name}: ${reasons}`);const drop=el('button','Apagar');drop.type='button';
          drop.addEventListener('click',()=>deleteLibraryItem(h));
          row.append(' ',drop);wrap.append(row);}
        wrap.append(el('small','Se o arquivo for legítimo, gere um PDF novo (imprimir como PDF) e envie de novo.'));}}
    updateStart('fontes', libraryItems.length > 0);
    if (!libraryItems.length && $('add-sources')) $('add-sources').open = true;
    const activeIds=new Set(libraryItems.map(i=>i.id));
    selectedSourceIds=new Set([...selectedSourceIds].filter(id=>activeIds.has(id)));
    updateSelectedCount();displayLibrary();
  }catch(e){$('library-list').textContent='Não foi possível consultar a biblioteca: '+e.message;}
}

$('refresh-library').addEventListener('click',loadLibrary);
for (const tab of document.querySelectorAll('[data-add-tab]')) {
  tab.addEventListener('click', () => {
    for (const t of document.querySelectorAll('[data-add-tab]')) { const on = t === tab; t.classList.toggle('active', on); t.setAttribute('aria-selected', String(on)); }
    for (const pane of document.querySelectorAll('[data-add-pane]')) pane.hidden = pane.dataset.addPane !== tab.dataset.addTab;
  });
}
$('library-filter').addEventListener('input',displayLibrary);
$('upload-library').addEventListener('click',async()=>{
  const file=$('library-file').files[0];
  if(!file){libraryMessage('Escolha um arquivo PDF, DOCX, BIB, RIS ou TXT.');return}
  const max=/\.(pdf|docx)$/i.test(file.name)?8*1024*1024:2*1024*1024;
  if(file.size>max){libraryMessage('Arquivo acima do limite permitido.');return}
  const btn=$('upload-library');btn.disabled=true;libraryMessage('Enviando arquivo…');
  try{
    const token=await user.getIdToken();
    const params=new URLSearchParams({
      filename:file.name,
      collection:$('library-collection').value||'Geral',
      description:$('library-description').value||''
    });
    const res=await fetch('/api/library/items?'+params,{
      method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/octet-stream'},
      body:file
    });
    if(!res.ok){
      let message='Erro HTTP '+res.status;
      try{const j=await res.json();message=typeof j.detail==='string'?j.detail:message}catch(_){}
      throw new Error(message)
    }
    $('library-file').value='';$('library-description').value='';
    libraryMessage('Documento guardado na biblioteca.');
    await loadLibrary();
  }catch(e){libraryMessage('Falha no envio: '+e.message)}
  finally{btn.disabled=false;}
});

async function download(id, kind) {
  try {
    const r = await request(`/jobs/${id}/download/${kind}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const names = {pdf: 'artigo.pdf', latex: 'latex.zip', manifest: 'manifesto_proveniencia.json', declaration: 'declaracao_uso_ia.md', evidence_csv: 'matriz_evidencias.csv'};
    a.href = url; a.download = `${id}_${names[kind] || 'execucao.log'}`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { alert(e.message); }
}

// Confirmação explícita para ações que não têm volta (apagar pesquisa ou fonte).
function confirmAction(title, message, confirmLabel) {
  return new Promise((resolve) => {
    const back = document.createElement('div');
    back.className = 'modal-backdrop';
    back.setAttribute('role', 'alertdialog'); back.setAttribute('aria-modal', 'true');
    const box = document.createElement('div'); box.className = 'modal-box';
    const head = document.createElement('div'); head.className = 'modal-head';
    const h = document.createElement('strong'); h.textContent = title; h.id = 'confirm-title';
    back.setAttribute('aria-labelledby', 'confirm-title');
    head.append(h);
    const body = document.createElement('div'); body.className = 'modal-body';
    for (const part of [].concat(message)) { const p = document.createElement('p'); p.textContent = part; p.style.margin = '0'; body.append(p); }
    const foot = document.createElement('div'); foot.className = 'modal-foot';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'btn alt'; cancel.textContent = 'Cancelar';
    const ok = document.createElement('button'); ok.type = 'button'; ok.className = 'btn btn-danger'; ok.textContent = confirmLabel;
    foot.append(cancel, ok); box.append(head, body, foot); back.append(box);
    const done = (value) => { document.removeEventListener('keydown', onKey); back.remove(); resolve(value); };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    cancel.addEventListener('click', () => done(false));
    ok.addEventListener('click', () => done(true));
    back.addEventListener('click', (e) => { if (e.target === back) done(false); });
    document.addEventListener('keydown', onKey);
    document.body.append(back); cancel.focus();
  });
}

async function deleteLibraryItem(item) {
  const ok = await confirmAction('Apagar fonte da biblioteca?', [
    `"${item.name}" será apagado de vez, com o arquivo original, a ficha de leitura e o fichamento guardados.`,
    'Pesquisas antigas que usaram esta fonte continuam no histórico, mas não conseguem mais abrir a página do PDF.',
    'Essa ação não pode ser desfeita.'], 'Apagar fonte');
  if (!ok) return;
  try { await request('/library/items/' + item.id, {method: 'DELETE'}); selectedSourceIds.delete(item.id); await loadLibrary(); libraryMessage('Fonte apagada.'); }
  catch (e) { libraryMessage(e.message); }
}

// Onda 6: arquivos gerados na hora pela API (matriz revisada, CSL-JSON, ABNT).
async function downloadPath(path, filename) {
  try {
    const blob = await (await request(path)).blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  } catch (e) { alert(e.message); }
}

// M02: abre a página do PDF com o trecho destacado (imagem gerada no servidor).
async function showOnPage(jobId, ev, holder, page) {
  const old = holder.querySelector('.page-view');
  if (old && !page) { old.remove(); return; }
  const box = old || document.createElement('div');
  box.className = 'page-view'; box.textContent = 'Abrindo a página...';
  if (!old) holder.append(box);
  try {
    const r = await request(`/jobs/${jobId}/evidence-view/${ev.chunk_id}` + (page ? `?page=${page}` : ''));
    const url = URL.createObjectURL(await r.blob());
    const shown = Number(r.headers.get('X-Scriptorium-Page'));
    const pages = (r.headers.get('X-Scriptorium-Pages') || '').split(',').filter(Boolean).map(Number);
    box.replaceChildren();
    box.append(el('small', `${ev.source_name || 'Fonte'} · página ${shown}` + (pages.length > 1 ? ` (o trecho ocupa as páginas ${pages.join(', ')})` : '') + ' · área destacada em amarelo'));
    if (pages.length > 1) {
      const nav = document.createElement('div'); nav.className = 'downloads';
      for (const p of pages) {
        const b = el('button', 'p. ' + p); b.type = 'button'; b.disabled = p === shown;
        b.addEventListener('click', () => showOnPage(jobId, ev, holder, p));
        nav.append(b);
      }
      box.append(nav);
    }
    const img = document.createElement('img');
    img.src = url; img.alt = `Página ${shown} do PDF com o trecho destacado`;
    img.style.maxWidth = '100%'; img.style.border = '1px solid var(--line, #444)'; img.style.marginTop = '6px';
    img.addEventListener('load', () => setTimeout(() => URL.revokeObjectURL(url), 1000));
    box.append(img);
  } catch (e) { box.textContent = 'Não foi possível abrir a página: ' + e.message; }
}

function el(tag, text, cls) { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; }

async function toggleReport(id, target, cls, kind, render, path) {
  const old = target.querySelector('.' + cls);
  if (old) { old.remove(); return; }
  const box = document.createElement('section');
  box.className = 'scientific-audit-report ' + cls;
  box.textContent = 'Carregando...';
  target.append(box);
  try {
    const data = await (await request(path || `/jobs/${id}/download/${kind}`)).json();
    box.replaceChildren();
    await render(box, data);
  } catch (err) { box.textContent = 'Não foi possível abrir o relatório: ' + err.message; }
}

function showGapReport(entry, target, decide) {
  return toggleReport(entry.id, target, 'gap-report', 'gap_report', (box, gap) => {
    box.append(el('strong', 'Diagnóstico das fontes (antes da redação)'));
    box.append(el('p', 'Mede o que as fontes anexadas cobrem para cada pergunta ou subtópico da sua ideia. "Lacuna" pode ser limitação da busca, não ausência de literatura.'));
    const s = gap.summary || {};
    box.append(el('p', `Boa: ${s.boa || 0} · parcial: ${s.parcial || 0} · lacuna: ${s.lacuna || 0} · ${s.sources || 0} fonte(s), ${s.chunks || 0} trecho(s)`));
    const names = {boa: 'Boa cobertura', parcial: 'Cobertura parcial', lacuna: 'Lacuna'};
    for (const q of gap.questions || []) {
      const d = document.createElement('details'); d.className = 'reference-item';
      d.append(el('summary', `${q.coverage === 'lacuna' ? '⚠ ' : ''}${names[q.coverage] || q.coverage}: ${q.text}`));
      d.append(el('small', `${q.evidence_count} trecho(s) de ${(q.sources_covering || []).length} fonte(s)` + ((q.missing_terms || []).length ? ` · termos sem cobertura: ${q.missing_terms.join(', ')}` : '')));
      for (const ev of q.evidence || []) {
        const pages = ev.pages ? `p. ${ev.pages[0]}${ev.pages[1] !== ev.pages[0] ? '-' + ev.pages[1] : ''}` : 'sem página';
        d.append(el('p', `${ev.source_name} · ${pages}`));
        d.append(el('small', ev.excerpt || ''));
      }
      box.append(d);
    }
    if ((gap.suggestions || []).length) {
      box.append(el('h4', 'Sugestões'));
      for (const tip of gap.suggestions) box.append(el('p', tip));
    }
    for (const problem of gap.source_problems || []) {
      box.append(el('p', `Atenção em "${problem.name}": ${problem.status}` + ((problem.ocr_pages_flagged || []).length ? ` · páginas sem texto (provável digitalização): ${problem.ocr_pages_flagged.join(', ')}` : ''), 'editorial-alert'));
    }
    if (!decide || entry.status !== 'awaiting_source_approval') return;
    box.append(el('h4', 'Fontes que seguem para a redação'));
    const checks = [];
    for (const source of entry.sources || []) {
      const label = document.createElement('label'); label.className = 'checkbox-line';
      const input = document.createElement('input'); input.type = 'checkbox'; input.checked = true; input.value = source.id;
      label.append(input, document.createTextNode(' ' + (source.name || source.id)));
      checks.push(input); box.append(label);
    }
    const bar = document.createElement('div'); bar.className = 'downloads';
    const approve = el('button', 'Aprovar e iniciar a redação'); approve.type = 'button';
    const discard = el('button', 'Descartar'); discard.type = 'button';
    const status = el('small', '');
    const decideNow = async (decision) => {
      approve.disabled = discard.disabled = true;
      try {
        const ids = checks.filter(c => c.checked).map(c => c.value);
        if (decision === 'approve' && !ids.length) { status.textContent = 'Mantenha ao menos uma fonte.'; return; }
        if (decision === 'approve' && entry.ai_billing === 'chave_pessoal' && entry.model === 'gemini-3.1-pro-preview'
            && !window.confirm('A redação vai usar Gemini Pro com sua chave. O Google poderá cobrar o uso. Continuar?')) return;
        await request(`/jobs/${entry.id}/checkpoint`, {method: 'POST', body: JSON.stringify({decision, source_ids: decision === 'approve' ? ids : null})});
        await loadJobs();
      } catch (e) { status.textContent = e.message; }
      finally { approve.disabled = discard.disabled = false; }
    };
    approve.addEventListener('click', () => decideNow('approve'));
    discard.addEventListener('click', () => { if (window.confirm('Descartar esta pesquisa? O diagnóstico continua no histórico.')) decideNow('discard'); });
    if (!API_MODE) approve.classList.add('hidden');
    bar.append(approve, discard, status); box.append(bar);
  });
}

// Revisão humana (M08/M12/M24): somente acréscimo; a mais recente aparece.
const REVIEW_OPTIONS = {
  claim: [['apoia', 'O trecho apoia'], ['contradiz', 'O trecho contradiz'], ['apenas_menciona', 'Só menciona'], ['nao_sustenta', 'Não sustenta'], ['pendente', 'Pendente']],
  fire: [['apoia', 'Concordo: apoiada'], ['contradiz', 'Concordo: contrariada'], ['apenas_menciona', 'Só menciona'], ['nao_sustenta', 'Não sustenta'], ['pendente', 'Pendente']],
  reference: [['referencia_confirmada', 'Conferi: referência correta'], ['referencia_incorreta', 'Conferi: referência incorreta'], ['pendente', 'Pendente']],
  quote: [['citacao_correta', 'Citação correta'], ['citacao_incorreta', 'Citação incorreta'], ['pendente', 'Pendente']],
};
async function loadReviews(jobId) {
  try { return (await (await request(`/jobs/${jobId}/reviews`)).json()).latest || {}; } catch (_) { return {}; }
}
function reviewControl(jobId, type, targetId, latest) {
  const wrap = document.createElement('div'); wrap.className = 'review-control';
  const current = latest[`${type}:${targetId}`];
  const select = document.createElement('select');
  select.append(new Option('Minha revisão...', ''));
  for (const [value, label] of REVIEW_OPTIONS[type]) select.append(new Option(label, value));
  if (current) select.value = current.decision;
  const note = document.createElement('input'); note.type = 'text'; note.maxLength = 1000; note.placeholder = 'Nota (opcional)';
  const save = el('button', 'Registrar'); save.type = 'button';
  const status = el('small', current ? `Última revisão: ${new Date(current.at).toLocaleString('pt-BR')}` : '');
  save.addEventListener('click', async () => {
    if (!select.value) { status.textContent = 'Escolha uma opção.'; return; }
    save.disabled = true;
    try {
      const r = await (await request(`/jobs/${jobId}/reviews`, {method: 'POST', body: JSON.stringify({target_type: type, target_id: targetId, decision: select.value, note: note.value})})).json();
      status.textContent = `Registrada em ${new Date(r.at).toLocaleString('pt-BR')} (histórico preservado).`;
      latest[`${type}:${targetId}`] = r; note.value = '';
    } catch (e) { status.textContent = e.message; }
    finally { save.disabled = false; }
  });
  wrap.append(select, note, save, status);
  return wrap;
}

function showFire(id, target) {
  return toggleReport(id, target, 'fire-report', 'fire', async (box, data) => {
    const latest = await loadReviews(id);
    box.append(el('strong', 'Verificação de afirmações nas fontes (experimental)'));
    box.append(el('p', 'Um modelo verificou cada afirmação só com trechos das fontes anexadas, buscando mais trechos quando incerto. "Evidência insuficiente" não significa afirmação falsa. Registre sua conclusão em cada item.'));
    const u = data.usage || {};
    box.append(el('small', `Chamadas ao modelo: ${u.calls || 0} de ${u.max_calls || '?'}`));
    const names = {apoiada_pelas_fontes: 'Apoiada pelas fontes', contrariada_pelas_fontes: 'Contrariada pelas fontes', evidencia_insuficiente: 'Evidência insuficiente', nao_verificada: 'Não verificada (orçamento)'};
    for (const r of data.claims || []) {
      const d = document.createElement('details'); d.className = 'reference-item';
      d.append(el('summary', `${r.label === 'contrariada_pelas_fontes' ? '⚠ ' : ''}${names[r.label] || r.label}: ${r.text}`));
      const last = (r.rounds || []).slice(-1)[0];
      if (last && last.justificativa) d.append(el('p', last.justificativa));
      d.append(el('small', `Ciclos: ${(r.rounds || []).length} · motivo da parada: ${r.stop_reason}`));
      for (const ev of r.evidence || []) {
        const pages = ev.pages ? `p. ${ev.pages[0]}${ev.pages[1] !== ev.pages[0] ? '-' + ev.pages[1] : ''}` : 'sem página';
        d.append(el('p', `${ev.cited_in_decision ? '★ ' : ''}${ev.source_name} · ${pages}`));
        d.append(el('small', ev.excerpt || ''));
      }
      d.append(reviewControl(id, 'fire', r.claim_id, latest));
      box.append(d);
    }
  });
}

function showContradictions(id, target) {
  return toggleReport(id, target, 'contradictions-report', 'contradictions', (box, data) => {
    box.append(el('strong', 'Possíveis divergências entre fontes (experimental)'));
    box.append(el('p', 'Pares de trechos de fontes diferentes sobre o mesmo assunto, classificados por modelo de linguagem. Leia os dois trechos: datas, populações e métodos podem explicar a diferença.'));
    const names = {convergente: 'Convergentes', divergente: 'Divergentes', contexto_diferente: 'Contextos diferentes', nao_comparavel: 'Não comparáveis', nao_classificado: 'Não classificado'};
    for (const pair of data.pairs || []) {
      const d = document.createElement('details'); d.className = 'reference-item';
      d.append(el('summary', `${pair.relacao === 'divergente' ? '⚠ ' : ''}${names[pair.relacao] || pair.relacao}: ${pair.a.source_name} x ${pair.b.source_name}`));
      if (pair.justificativa) d.append(el('p', pair.justificativa));
      for (const side of [pair.a, pair.b]) {
        const pages = side.pages ? `p. ${side.pages[0]}${side.pages[1] !== side.pages[0] ? '-' + side.pages[1] : ''}` : 'sem página';
        d.append(el('p', `${side.source_name} · ${pages}`));
        d.append(el('small', side.excerpt || ''));
      }
      if (!pair.citacoes_conferidas) d.append(el('small', 'As frases citadas pelo modelo não foram encontradas literalmente nos trechos e foram descartadas.'));
      box.append(d);
    }
  });
}

function showShield(id, target) {
  return toggleReport(id, target, 'shield-report', 'shield', (box, shield) => {
    box.append(el('strong', 'Escudo de auditoria: o que pede atenção'));
    box.append(el('p', 'Organiza os alertas de todas as verificações. Não há nota geral nem selo de "verificado": ausência de alertas não comprova validade científica.'));
    const c = shield.counts || {};
    box.append(el('p', `Alta: ${c.alta || 0} · média: ${c.media || 0} · baixa: ${c.baixa || 0}`));
    const stageNames = {'1_ponteiros_citacoes': '1. Ponteiros e citações literais', '2_metadados': '2. Metadados bibliográficos',
      '3_situacao_editorial': '3. Retratações e correções', '4_suporte_semantico': '4. Suporte nas fontes', 'triagem_heuristica': 'Triagem do texto'};
    for (const [key, stage] of Object.entries(shield.stages || {})) {
      box.append(el('small', `${stageNames[key] || key}: ${stage.status}${stage.motivo ? ' (' + stage.motivo + ')' : ''}`));
    }
    const levelNames = {alta: 'Alta', media: 'Média', baixa: 'Baixa'};
    for (const level of ['alta', 'media', 'baixa']) {
      const items = (shield.items || []).filter(i => i.level === level);
      if (!items.length) continue;
      box.append(el('h4', `${levelNames[level]} (${items.length})`));
      for (const item of items.slice(0, 80)) {
        const p = el('p', `${item.title}: ${item.detail}`, level === 'alta' ? 'editorial-alert' : '');
        box.append(p);
      }
    }
  });
}

function showCoverage(id, target) {
  return toggleReport(id, target, 'coverage-report', 'coverage', (box, cov) => {
    box.append(el('strong', 'Cobertura das fontes: o que os agentes leram'));
    box.append(el('p', 'Trechos não selecionados não foram lidos pelos agentes; isso não significa que sejam irrelevantes.'));
    const emb = cov.embeddings || {};
    box.append(el('p', `Estratégia: ${cov.strategy || '?'} · embeddings: ${emb.status || 'desligados'} · caracteres usados: ${cov.used_chars ?? '?'} de ${cov.total_budget_chars ?? '?'}`));
    if ((cov.query_terms || []).length) box.append(el('small', 'Termos da busca: ' + cov.query_terms.join(', ')));
    const modes = {bm25: 'por relevância', rrf: 'por relevância (híbrida)', opening_without_match: 'só o início (nenhum trecho correspondeu)', fallback_document_order: 'ordem do documento'};
    for (const [sourceId, info] of Object.entries(cov.sources || {})) {
      box.append(el('p', `${sourceId.slice(0, 8)}…: ${info.chunks_selected} de ${info.chunks_total} trechos selecionados (${info.chunks_matched} correspondências), ${modes[info.selection] || info.selection || ''}`));
    }
    // M09: o que os agentes leram, agrupado por autor, época e tema.
    const f = cov.facets;
    if (f && !f.status) {
      box.append(el('h4', 'Por autor'));
      for (const [name, v] of Object.entries(f.by_author || {})) box.append(el('p', `${name}: ${v.sources} fonte(s), ${v.chunks_selected} trecho(s) lido(s)`));
      box.append(el('h4', 'Por época'));
      for (const [name, v] of Object.entries(f.by_epoch || {})) box.append(el('p', `${name}: ${v.sources} fonte(s), ${v.chunks_selected} trecho(s) lido(s)`));
      for (const src of f.sources || []) box.append(el('small', `${src.name}: ${src.author} · ${src.year_note}`));
      box.append(el('h4', 'Por tema (perguntas e subtópicos da ideia)'));
      const covLabels = {lacuna: '⚠ nenhum trecho lido', uma_fonte: 'uma fonte só', varias_fontes: 'várias fontes'};
      for (const t of f.by_theme || []) {
        const names = Object.entries(t.sources || {}).map(([n, c]) => `${n} (${c})`).join('; ');
        box.append(el('p', `${covLabels[t.coverage] || t.coverage}: ${t.text}` + (names ? ` · ${names}` : ''), t.coverage === 'lacuna' ? 'editorial-alert' : ''));
      }
      for (const lim of f.limitations || []) box.append(el('small', lim));
    }
  });
}

async function showEvidenceReport(id, target) {
  const old = target.querySelector('.evidence-report');
  if (old) { old.remove(); return; }
  const box = document.createElement('section');
  box.className = 'scientific-audit-report evidence-report';
  box.textContent = 'Carregando citações e evidências...';
  target.append(box);
  const line = (tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el; };
  try {
    const report = await (await request(`/jobs/${id}/download/evidence`)).json();
    const latest = await loadReviews(id);
    box.replaceChildren();
    box.append(line('strong', 'Citações literais e matriz de evidências: revisão humana necessária'));
    box.append(line('p', 'Os trechos foram localizados automaticamente nas fontes anexadas. O sistema NÃO decide se um trecho apoia ou contradiz a afirmação, e "sem evidência no corpus" vale só para as fontes anexadas.'));
    const quotes = report.quotes || {};
    const qs = quotes.summary || {};
    box.append(line('h4', 'Citações entre aspas'));
    box.append(line('p', `Encontradas: ${qs.found || 0} · aproximadas: ${qs.approximate || 0} · não encontradas nas fontes: ${qs.not_found_in_sources || 0} · ponteiros desconhecidos: ${qs.pointers_unknown || 0}`));
    const qLabels = {found: 'Encontrada', approximate: 'Aproximada (conferir redação)', not_found_in_sources: 'Não encontrada nas fontes anexadas', no_sources_attached: 'Sem fontes anexadas'};
    for (const q of (quotes.quotes || []).slice(0, 40)) {
      const where = q.pages ? ` · ${q.source_name || q.source_id} p. ${q.pages[0]}${q.pages[1] !== q.pages[0] ? '-' + q.pages[1] : ''}` : '';
      box.append(line('p', `${q.status === 'not_found_in_sources' ? '⚠ ' : ''}${qLabels[q.status] || q.status}${where}: "${q.quote}"`,
        q.status === 'not_found_in_sources' ? 'editorial-alert' : ''));
      if (q.chunk_id && (q.locations || []).length) {
        const holder = document.createElement('div');
        const view = line('button', 'Ver na página do PDF'); view.type = 'button';
        view.addEventListener('click', () => showOnPage(id, q, holder));
        holder.append(view); box.append(holder);
      }
    }
    const matrix = report.matrix || {};
    const ms = matrix.summary || {};
    box.append(line('h4', 'Afirmações verificáveis'));
    box.append(line('p', `Afirmações: ${ms.claims || 0} · com trechos candidatos: ${ms.with_candidates || 0} · sem evidência nas fontes anexadas: ${ms.without_evidence_in_corpus || 0}`));
    for (const row of (matrix.claims || []).slice(0, 60)) {
      const detail = document.createElement('details');
      detail.className = 'reference-item';
      detail.append(line('summary', `${row.audit_state === 'sem_evidencia_no_corpus' ? '⚠ ' : ''}${row.claim_id}: ${row.text}`));
      if (row.cites && row.cites.length) detail.append(line('small', 'Citações BibTeX: ' + row.cites.join(', ')));
      for (const ev of row.evidence || []) {
        const pages = ev.pages ? `p. ${ev.pages[0]}${ev.pages[1] !== ev.pages[0] ? '-' + ev.pages[1] : ''}` : 'sem página';
        detail.append(line('p', `${ev.source_name || ev.source_id} · ${pages} · termos em comum: ${ev.shared_terms}${ev.similarity != null ? ' · similaridade: ' + ev.similarity : ''}`));
        detail.append(line('small', ev.excerpt || ''));
        if ((ev.locations || []).length) {
          const holder = document.createElement('div');
          const view = line('button', 'Ver na página do PDF'); view.type = 'button';
          view.addEventListener('click', () => showOnPage(id, ev, holder));
          holder.append(view); detail.append(holder);
        }
      }
      if (!(row.evidence || []).length) detail.append(line('p', 'Nenhum trecho candidato nas fontes anexadas.'));
      detail.append(reviewControl(id, 'claim', row.claim_id, latest));
      box.append(detail);
    }
  } catch (err) { box.textContent = 'Não foi possível abrir o relatório: ' + err.message; }
}

async function showScientificAudit(id, target) {
  const old = target.querySelector('.scientific-audit-report');
  if (old) { old.remove(); return; }
  const box = document.createElement('section');
  box.className = 'scientific-audit-report';
  box.textContent = 'Carregando a auditoria...';
  target.append(box);
  try {
    const r = await request(`/jobs/${id}/download/audit`);
    const report = await r.json();
    box.replaceChildren();
    const heading = document.createElement('strong');
    heading.textContent = 'Triagem científica — revisão humana necessária';
    box.append(heading);
    const limitations = document.createElement('p');
    limitations.textContent = 'Triagem automática local. Não verifica DOI, existência de fontes nem correção factual.';
    box.append(limitations);
    const summary = document.createElement('p');
    const counts = report.summary || {};
    summary.textContent = `Referências BibTeX: ${counts.bibliography_keys_found ?? '?'}; chaves sem correspondência: ${counts.citation_keys_missing ?? '?'}; alertas: ${counts.findings ?? '?'}.`;
    box.append(summary);
    for (const finding of (report.findings || []).slice(0, 30)) {
      const part = document.createElement('div');
      part.className = 'audit-finding';
      const title = document.createElement('strong');
      title.textContent = finding.title || finding.code || 'Verificação recomendada';
      const desc = document.createElement('p');
      desc.textContent = finding.detail || '';
      part.append(title, desc);
      for (const sample of (finding.examples || []).slice(0, 3)) {
        const quote = document.createElement('small');
        quote.textContent = String(sample);
        part.append(quote);
      }
      box.append(part);
    }
    if (!(report.findings || []).length) {
      const note = document.createElement('p');
      note.textContent = 'Nenhum alerta heurístico encontrado. Isso NÃO significa que as afirmações foram verificadas.';
      box.append(note);
    }
  } catch (err) {
    box.textContent = 'Não foi possível ler a auditoria: ' + err.message;
  }
}

async function showReferenceVerification(id, target) {
  const old = target.querySelector('.reference-report');
  if (old) { old.remove(); return; }
  const box = document.createElement('section');
  box.className = 'scientific-audit-report reference-report';
  box.textContent = 'Consultando relatório bibliográfico...';
  target.append(box);
  try {
    const response = await request(`/jobs/${id}/download/references`);
    const report = await response.json();
    const latest = await loadReviews(id);
    box.replaceChildren();
    const heading = document.createElement('strong');
    heading.textContent = 'Conferência de metadados bibliográficos';
    box.append(heading);
    const description = document.createElement('p');
    description.textContent = 'Fontes: Crossref, OpenAlex e Semantic Scholar; retratações e correções pela Crossref (inclui Retraction Watch). Metadados compatíveis NÃO provam que a fonte sustenta a afirmação citada, e a ausência de aviso não prova que a obra nunca foi retratada.';
    box.append(description);
    const count = document.createElement('p');
    count.textContent = `Consultadas: ${report.checked ?? 0} de ${report.total_bibtex_entries ?? 0} referências. Não consultadas por limite: ${report.skipped_by_limit ?? 0}.`;
    box.append(count);
    const labels = {
      metadata_match: 'Metadados compatíveis — conferir a publicação',
      metadata_conflict: 'Possível divergência de metadados',
      possible_match: 'Correspondência provável por título',
      not_found: 'Não localizada nas consultas',
      inconclusive: 'Consulta inconclusiva / base indisponível',
      insufficient_metadata: 'Metadados insuficientes'
    };
    for (const item of (report.items || []).slice(0, 20)) {
      const detail = document.createElement('details');
      detail.className = 'reference-item';
      const summary = document.createElement('summary');
      const ref = item.reference || {};
      summary.textContent = (ref.title || ref.key || 'Referência sem título') + ' — ' + (labels[item.classification] || 'Verificar manualmente');
      detail.append(summary);
      const meta = document.createElement('small');
      meta.textContent = `BibTeX: ${ref.key || ''} · ano: ${ref.year || '?'} · DOI: ${ref.doi || 'não informado'}`;
      detail.append(meta);
      const factors = item.quality_factors || {};
      if (factors.version) {
        const reviewNames = {periodico_provavelmente_revisado: 'periódico (provável revisão por pares)', preprint_ou_repositorio: 'preprint ou repositório', outro_tipo: 'outro tipo', desconhecido: 'tipo desconhecido'};
        const parts = [reviewNames[factors.peer_review_signal] || factors.peer_review_signal];
        if (factors.venue) parts.push(factors.venue);
        if (factors.age_years != null) parts.push(`${factors.age_years} anos`);
        if (factors.citations_openalex != null) parts.push(`${factors.citations_openalex} citações (OpenAlex)`);
        if (factors.scielo_doi) parts.push('DOI SciELO');
        detail.append(el('small', 'Contexto (sinais separados, não é nota de qualidade): ' + parts.join(' · ')));
      }
      const manual = item.manual_verification;
      if (manual && (manual.links || []).length) {
        detail.append(el('small', manual.reason || 'Conferir manualmente:'));
        for (const link of manual.links) {
          try {
            const parsed = new URL(link.url);
            if (parsed.protocol === 'https:' && ['scholar.google.com', 'search.scielo.org', 'brapci.inf.br'].includes(parsed.hostname)) {
              const a = document.createElement('a');
              a.href = link.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = 'Buscar em ' + link.name;
              detail.append(a);
            }
          } catch (_) { /* endereço inválido ignorado */ }
        }
      }
      if (ref.key && /^[\w.:\-\/]+$/.test(ref.key)) detail.append(reviewControl(id, 'reference', ref.key, latest));
      const editorial = item.editorial || {};
      if (editorial.editorial_status) {
        const status = document.createElement('p');
        const alert = ['retracted', 'withdrawn', 'expression_of_concern'].includes(editorial.editorial_status);
        status.className = alert ? 'editorial-alert' : 'editorial-status';
        status.textContent = 'Situação editorial (Crossref/Retraction Watch): ' + (editorial.label || editorial.editorial_status);
        detail.append(status);
        if (alert) summary.textContent = '⚠ ' + summary.textContent;
        for (const notice of (editorial.notices || []).slice(0, 3)) {
          const line = document.createElement('small');
          line.textContent = `${notice.label || notice.type} · ${notice.date || 'sem data'} · fonte: ${notice.source}` + (notice.notice_doi ? ` · aviso: ${notice.notice_doi}` : '');
          detail.append(line);
        }
      }
      for (const [provider, data] of Object.entries(item.sources || {})) {
        const line = document.createElement('p');
        line.textContent = provider + ': ' + (data.status === 'ok' ? (data.title || 'Metadados encontrados') : data.status === 'not_found' ? 'não localizado' : 'indisponível / limite de API');
        detail.append(line);
        if (typeof data.url === 'string') {
          try {
            const parsed = new URL(data.url);
            const allowed = ['doi.org','openalex.org','www.semanticscholar.org','semanticscholar.org'];
            if (parsed.protocol === 'https:' && allowed.includes(parsed.hostname)) {
              const a = document.createElement('a');
              a.href = data.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
              a.textContent = 'Abrir registro em ' + provider;
              detail.append(a);
            }
          } catch (_) { /* sem endereço confiável */ }
        }
      }
      box.append(detail);
    }
  } catch (error) { box.textContent = 'Não foi possível acessar a conferência: ' + error.message; }
}

async function showNeonReport(id, target) {
  const old = target.querySelector('.neon-report');
  if (old) {old.remove();return;}
  const box=document.createElement('section');box.className='neon-report';
  box.textContent='Carregando parecer crítico…';target.append(box);
  try {
    const r=await request('/jobs/'+id+'/download/neon');
    const data=await r.json();
    box.replaceChildren();
    const header=document.createElement('strong');
    header.textContent='Parecer crítico — Gemini 4 Neon';box.append(header);
    const warning=document.createElement('p');
    warning.textContent='Revisão assistida por IA. Não comprova referências, dados nem resultados científicos.';
    box.append(warning);
    if(data.sintese){const p=document.createElement('p');p.textContent=data.sintese;box.append(p);}
    const sections={
      pontos_fortes:'Pontos fortes',
      riscos_argumentativos:'Riscos argumentativos',
      afirmacoes_sem_evidencia:'Afirmações que exigem evidência',
      questoes_para_o_pesquisador:'Questões para o pesquisador',
      limitacoes_da_revisao:'Limitações da revisão'
    };
    for(const [key,label] of Object.entries(sections)){
      const items=Array.isArray(data[key])?data[key]:[];
      if(!items.length)continue;
      const heading=document.createElement('h4');heading.textContent=label;box.append(heading);
      const ul=document.createElement('ul');
      for(const item of items.slice(0,20)){
        const li=document.createElement('li');li.textContent=String(item);ul.append(li);
      }
      box.append(ul);
    }
    if(data.consumo_tokens){
      const c=document.createElement('small');
      c.textContent='Tokens desta revisão: entrada '+(data.consumo_tokens.entrada??'?')
        +' · saída '+(data.consumo_tokens.saida??'?')
        +' · raciocínio '+(data.consumo_tokens.raciocinio??'?');
      box.append(c);
    }
  } catch(e) {box.textContent='Não foi possível abrir o parecer Neon: '+e.message;}
}

async function loadCapabilities() {
  $('neon-panel').classList.add('hidden');
  $('neon-explanation').classList.add('hidden');
  $('neon-review').checked=false;
  try {
    const r=await request('/capabilities');
    const caps=await r.json();
    if(caps.neon_review === true && accountAccess?.admin === true) {
      $('neon-panel').classList.remove('hidden');
      $('neon-explanation').classList.remove('hidden');
    }
  } catch(_) { /* opção permanece oculta caso a API seja anterior */ }
}

function statusLabel(value) {
  return ({queued:'Na fila',running:'Em execução',completed:'Concluído',failed:'Falhou',
    awaiting_source_approval:'Aguardando sua aprovação',discarded:'Descartada',cancelled:'Cancelada'})[value] || value;
}

const AGENT_LABELS = {
  outline: 'Planejamento', literature: 'Revisão bibliográfica',
  plotting: 'Gráficos e diagramas', writing: 'Redação',
  refinement: 'Revisão e refinamento'
};
const AGENT_STATES = {
  waiting: 'Aguardando', running: 'Executando',
  completed: 'Etapa concluída', disabled: 'Desativado', failed: 'Falhou'
};

function agentPanel(states) {
  if (!states || typeof states !== 'object') return null; // trabalhos legados
  const detail = document.createElement('details');
  detail.className = 'agent-detail';
  const summary = document.createElement('summary');
  summary.textContent = 'Acompanhar agentes';
  detail.append(summary);
  const help = document.createElement('small');
  help.textContent = 'Etapas detectadas pelos arquivos gerados, não são validação científica.';
  detail.append(help);
  for (const [key, title] of Object.entries(AGENT_LABELS)) {
    const state = states[key] || 'waiting';
    const line = document.createElement('div');
    line.className = 'agent-row';
    const name = document.createElement('span');
    name.textContent = title;
    const value = document.createElement('span');
    value.className = 'agent-state agent-' + (AGENT_STATES[state] ? state : 'waiting');
    value.textContent = AGENT_STATES[state] || state;
    line.append(name, value);
    detail.append(line);
  }
  return detail;
}

// Modo sem API: cada pesquisa antiga mostra título, data e o PDF; o resto fica em "Mais arquivos".
function compactHistoryItem(entry, info) {
  const keep = [...info.children].slice(0, 2);
  const rest = [...info.children].slice(2);
  if (!rest.length) return;
  const more = document.createElement('details'); more.className = 'more-files';
  more.append(el('summary', 'Mais arquivos, relatórios e opções'));
  for (const node of rest) more.append(node);
  info.replaceChildren(...keep);
  if (entry.status === 'completed' && (entry.files || []).includes('pdf')) {
    const row = document.createElement('div'); row.className = 'downloads';
    const pdf = el('button', 'Baixar PDF'); pdf.type = 'button';
    pdf.addEventListener('click', () => download(entry.id, 'pdf'));
    row.append(pdf); info.append(row);
  }
  info.append(more);
}

// Onda 1 (G8): polling inteligente — pausa quando a aba está oculta ou sem tarefas ativas.
let lastJobsBusy = false;
let lastMcpBusy = false;
const BUSY_JOB_STATUSES = new Set(['queued', 'running']);
const BUSY_MCP_STATUSES = new Set(['preparando', 'compilando', 'refazendo_referencias']);

function stopSmartPolling() {
  if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
}

function syncSmartPolling() {
  stopSmartPolling();
  if (!user || document.hidden) return;
  if (!lastJobsBusy && !lastMcpBusy) return;
  refreshInterval = setInterval(() => {
    if (!user || document.hidden) { stopSmartPolling(); return; }
    if (lastJobsBusy) loadJobs();
    if (lastMcpBusy) loadMcpProjects();
  }, 12000);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopSmartPolling();
  } else if (user && canWork()) {
    if (lastJobsBusy) loadJobs();
    if (lastMcpBusy) loadMcpProjects();
    syncSmartPolling();
  }
});

async function loadJobs() {
  if (!user) return;
  const area = $('research-list');
  try {
    const r = await request('/jobs');
    const data = await r.json();
    const items = data.items || [];
    lastJobsBusy = items.some(e => BUSY_JOB_STATUSES.has(e.status));
    syncSmartPolling();
    area.replaceChildren();
    const historyPanel = $('history-panel');
    if (!API_MODE) historyPanel.classList.toggle('hidden', !items.length);
    else $('history-details').open = true;
    $('history-title').textContent = API_MODE ? 'Histórico de pesquisas' : `Pesquisas anteriores (${items.length})`;
    if (!items.length) { area.textContent = 'Nenhuma pesquisa criada até o momento.'; return; }
    for (const entry of items) {
      const item = document.createElement('div'); item.className='item';
      const info = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = entry.title; info.append(title);
      const date = document.createElement('small');
      date.textContent = `Criada em ${new Date(entry.created_at).toLocaleString('pt-BR')} • ${entry.stage || 'Aguardando'}`
        + (!API_MODE ? '' : entry.ai_billing === 'chave_pessoal' ? ' • tokens na sua chave Gemini' : entry.ai_billing === 'projeto' ? ' • tokens no projeto (anterior à separação)' : '');
      info.append(date);
      const agents = agentPanel(entry.agents);
      if (agents) info.append(agents);
      if (entry.status === 'completed') {
        const warning = document.createElement('small');
        warning.className = 'scientific-warning';
        warning.textContent = 'PDF gerado: números, resultados, referências e alegações de validação precisam de conferência humana.';
        info.append(warning);
      }
      if (entry.neon_review_requested && entry.neon_review_status === 'unavailable') {
        const warning = document.createElement('small');
        warning.className = 'scientific-warning';
        warning.textContent = API_MODE ? 'A revisão com Neon falhou. Ela usa a sua chave Gemini e exige o nível pago no AI Studio. O PDF principal continua disponível.' : 'A revisão com Neon falhou. O PDF principal continua disponível.';
        info.append(warning);
      }
      if (entry.audit_status === 'unavailable') {
        const aud = document.createElement('small');
        aud.className = 'scientific-warning';
        aud.textContent = 'A auditoria não pôde ser gerada; confira manualmente o artigo.';
        info.append(aud);
      }
      if (entry.error) {const err=document.createElement('small'); err.textContent=entry.error; info.append(err);}
      // M15: cancelamento pelo navegador enquanto a pesquisa roda.
      if (entry.status === 'queued' || entry.status === 'running') {
        const actions = document.createElement('div'); actions.className = 'downloads';
        const stop = el('button', entry.cancel_requested ? 'Cancelamento solicitado' : 'Cancelar pesquisa'); stop.type = 'button';
        stop.disabled = !!entry.cancel_requested;
        stop.addEventListener('click', async () => {
          if (!confirm('Cancelar esta pesquisa? O que já foi feito fica registrado, mas a redação para.')) return;
          stop.disabled = true;
          try { await request(`/jobs/${entry.id}/cancel`, {method: 'POST'}); stop.textContent = 'Cancelamento solicitado'; }
          catch (e) { alert(e.message); stop.disabled = false; }
        });
        actions.append(stop); info.append(actions);
      }
      if (entry.status === 'awaiting_source_approval') {
        const g = entry.gap_summary || {};
        info.append(el('small', `Diagnóstico pronto: ${g.boa || 0} ponto(s) com boa cobertura, ${g.parcial || 0} parcial(is), ${g.lacuna || 0} lacuna(s). A redação só começa depois da sua aprovação.`, 'scientific-warning'));
        const actions = document.createElement('div'); actions.className = 'downloads';
        const open = el('button', 'Ver diagnóstico e aprovar fontes'); open.type = 'button';
        open.addEventListener('click', () => showGapReport(entry, info, true));
        actions.append(open); info.append(actions);
      }
      if (entry.status === 'completed' || entry.status === 'failed') {
        const files = document.createElement('div'); files.className='downloads';
        const bi = entry.bibliography_integrity;
        if (entry.status === 'completed' && bi) {
          const note = document.createElement('p'); note.className = 'subtle';
          note.textContent = `Bibliografia conferida: ${bi.corrigidas || 0} referência(s) corrigida(s) pelos dados das fontes anexadas, `
            + `${bi.enchimento || 0} com valor genérico para conferir, ${bi.sem_referencia || 0} citação(ões) sem referência.`
            + (bi.status === 'corrigida_e_recompilada' ? ' O PDF foi recompilado com as correções.' : '');
          info.append(note);
        }
        const available = entry.status === 'failed'
          ? ['log', ...((entry.files || []).includes('manifest') ? ['manifest'] : [])]
          : entry.files;
        for (const kind of available) {
          if (kind === 'neon' && !accountAccess?.admin) continue;
          // Tratados pelos botões da onda 6 (exportação ABNT/CSL e reavaliação editorial).
          if (kind === 'bibtex' || kind === 'editorial_recheck') continue;
          const button = document.createElement('button'); button.type='button';
          if (kind === 'gap_report') {
            const gb = el('button', 'Diagnóstico das fontes'); gb.type = 'button';
            gb.addEventListener('click', () => showGapReport(entry, info, false));
            files.append(gb); continue;
          }
          const labels={pdf:'Baixar PDF',latex:'Baixar LaTeX',audit:'Ver auditoria',references:'Conferir referências',neon:'Parecer Neon',manifest:'Manifesto de proveniência',declaration:'Rascunho da declaração de IA',evidence:'Citações e evidências',evidence_csv:'Matriz de evidências (CSV)',shield:'Escudo de auditoria',coverage:'Cobertura das fontes',contradictions:'Divergências entre fontes (experimental)',fire:'Verificação de afirmações (experimental)',bib_integrity:'Integridade da bibliografia (JSON)'};
          button.textContent=labels[kind]||'Logs';
          if(kind==='shield'&&entry.shield_counts){const c=entry.shield_counts;button.textContent+=` (${c.alta||0} alta · ${c.media||0} média)`;}
          if(kind==='references'&&entry.editorial_alerts>0){button.textContent+=` (${entry.editorial_alerts} aviso${entry.editorial_alerts>1?'s':''} editorial${entry.editorial_alerts>1?'is':''})`;}
          button.addEventListener('click', ()=>kind==='fire' ? showFire(entry.id, info) : kind==='contradictions' ? showContradictions(entry.id, info) : kind==='shield' ? showShield(entry.id, info) : kind==='coverage' ? showCoverage(entry.id, info) : kind==='evidence' ? showEvidenceReport(entry.id, info) : kind==='audit' ? showScientificAudit(entry.id, info) : kind==='references' ? showReferenceVerification(entry.id, info) : kind==='neon' ? showNeonReport(entry.id, info) : download(entry.id,kind));
          files.append(button);
        }
        if (entry.status === 'completed') {
          const have = new Set(entry.files || []);
          const extra = (label, fn) => { const b = el('button', label); b.type = 'button'; b.addEventListener('click', fn); files.append(b); };
          // M08: matriz com as suas revisões; M27: referências em CSL-JSON e ABNT.
          if (have.has('evidence_csv')) extra('Matriz com suas revisões (CSV)', () => downloadPath(`/jobs/${entry.id}/export/evidence_reviewed_csv`, `${entry.id}_matriz_revisada.csv`));
          if (have.has('bibtex')) {
            extra('Referências ABNT', () => downloadPath(`/jobs/${entry.id}/export/abnt`, `${entry.id}_referencias_abnt.md`));
            extra('Referências CSL-JSON', () => downloadPath(`/jobs/${entry.id}/export/csl_json`, `${entry.id}_referencias.csl.json`));
          }
          // M07: reconsultar retratações e avisos editoriais (sem IA, sem custo de tokens).
          if (have.has('references')) {
            const rc = entry.editorial_recheck || {};
            const busy = rc.status === 'queued' || rc.status === 'running';
            const b = el('button', busy ? 'Reavaliando retratações...' : 'Reavaliar retratações agora'); b.type = 'button'; b.disabled = busy;
            b.addEventListener('click', async () => {
              b.disabled = true;
              try { await request(`/jobs/${entry.id}/editorial-recheck`, {method: 'POST'}); b.textContent = 'Reavaliando retratações...'; setTimeout(loadJobs, 20000); }
              catch (e) { alert(e.message); b.disabled = false; }
            });
            files.append(b);
            if (rc.status === 'completed') {
              extra(`Resultado da reavaliação (${rc.changed || 0} mudança(s))`, () => toggleReport(entry.id, info, 'recheck-report', null, (box, data) => {
                box.append(el('strong', `Reavaliação editorial de ${new Date(data.checked_at).toLocaleString('pt-BR')}`));
                const sm = data.summary || {};
                box.append(el('p', `DOIs reconsultados: ${sm.dois_checked || 0} · com mudança: ${sm.changed || 0} · com avisos: ${sm.with_notices || 0}`));
                for (const it of data.items || []) {
                  if (!it.changed && !((it.after || {}).notices || []).length) continue;
                  box.append(el('p', `${it.changed ? '⚠ ' : ''}${it.title || it.doi}: ${(it.before || {}).label || 'sem aviso'} → ${(it.after || {}).label || 'sem aviso'}`, 'editorial-alert'));
                }
                for (const lim of data.limitations || []) box.append(el('small', lim));
              }, `/jobs/${entry.id}/export/editorial_recheck`));
            } else if (rc.status === 'failed') {
              info.append(el('small', 'A reavaliação editorial falhou: ' + (rc.error || 'tente de novo mais tarde.'), 'scientific-warning'));
            }
          }
        }
        info.append(files);
      }
      // Apagar do histórico (pede confirmação; pesquisa em execução precisa ser cancelada antes).
      if (!['queued', 'running'].includes(entry.status)) {
        const del = document.createElement('div'); del.className = 'downloads';
        const b = el('button', 'Apagar do histórico', 'btn-danger-text'); b.type = 'button';
        b.addEventListener('click', async () => {
          const ok = await confirmAction('Apagar pesquisa?', [
            `"${entry.title}" será apagada de vez: PDF, LaTeX, relatórios, manifesto, declaração e as suas revisões.`,
            'As fontes da biblioteca não são apagadas. Baixe antes o que quiser guardar.',
            'Essa ação não pode ser desfeita.'], 'Apagar pesquisa');
          if (!ok) return;
          b.disabled = true;
          try { await request(`/jobs/${entry.id}`, {method: 'DELETE'}); await loadJobs(); }
          catch (e) { alert(e.message); b.disabled = false; }
        });
        del.append(b); info.append(del);
      }
      if (!API_MODE) compactHistoryItem(entry, info);
      const badge = document.createElement('span'); badge.className='pill'; badge.textContent=statusLabel(entry.status);
      item.append(info, badge); area.append(item);
    }
  } catch (e) { area.textContent = `Não foi possível consultar pesquisas: ${e.message}`; }
}

$('refresh').addEventListener('click', loadJobs);

// M26: importação somente leitura do Zotero. A chave só trafega nestas requisições.
function zoteroMessage(text) { $('zotero-message').textContent = text; }
$('zotero-list').addEventListener('click', async () => {
  const key = $('zotero-key').value.trim();
  if (!key) { zoteroMessage('Cole a chave do Zotero.'); return; }
  zoteroMessage('Consultando o Zotero...');
  try {
    const data = await (await request('/library/zotero/collections', {method: 'POST', body: JSON.stringify({api_key: key})})).json();
    const select = $('zotero-collection');
    select.replaceChildren(new Option('Biblioteca inteira (até 500 itens)', ''));
    for (const c of data.items || []) select.append(new Option(`${c.name}${c.items != null ? ' (' + c.items + ')' : ''}`, c.key));
    select.disabled = false; $('zotero-import').disabled = false;
    zoteroMessage(`${(data.items || []).length} coleção(ões) encontrada(s).`);
  } catch (e) { zoteroMessage(e.message); }
});
$('zotero-import').addEventListener('click', async () => {
  const key = $('zotero-key').value.trim();
  if (!key) { zoteroMessage('Cole a chave do Zotero.'); return; }
  $('zotero-import').disabled = true; zoteroMessage('Importando metadados...');
  try {
    const body = {api_key: key, collection_key: $('zotero-collection').value || null,
      incremental: $('zotero-incremental').checked, attachments_consent: $('zotero-attachments').checked};
    const data = await (await request('/library/zotero/import', {method: 'POST', body: JSON.stringify(body)})).json();
    const att = data.attachments || {};
    zoteroMessage((data.up_to_date ? 'Nada mudou no Zotero desde a última importação.' :
      `${data.items_imported} item(ns) importado(s) como .bib${data.incremental ? ` (alterados desde a versão ${data.since_version})` : ''}.`)
      + (data.deleted_in_zotero ? ` ${data.deleted_in_zotero} item(ns) foram apagados no Zotero (a biblioteca daqui não muda sozinha).` : '')
      + ($('zotero-attachments').checked ? ` PDFs: ${att.imported || 0} importado(s), ${att.quarantined || 0} retido(s) na verificação, ${att.skipped || 0} ignorado(s).` : ''));
    $('zotero-key').value = '';
    await loadLibrary();
  } catch (e) { zoteroMessage(e.message); }
  finally { $('zotero-import').disabled = false; }
});
// M11: IN IFRS 16/2026. Dados inéditos (Art. 9º) e autorização do orientador (Art. 6º e 8º).
for (const radio of document.querySelectorAll('input[name="unpublished-data"]')) {
  radio.addEventListener('change', () => $('unpublished-confirm').classList.toggle('hidden',
    document.querySelector('input[name="unpublished-data"]:checked')?.value !== 'sim'));
}
async function loadAdvisor() {
  try {
    const prof = (await (await request('/account/academic-profile')).json()).profile;
    if (prof) {
      $('profile-name').value = prof.full_name || ''; $('profile-enrollment').value = prof.enrollment || '';
      $('profile-unit').value = prof.unit || ''; $('profile-program').value = prof.program || '';
    }
  } catch (_) { /* API anterior */ }
  try {
    const data = await (await request('/account/advisor-authorization')).json();
    const scope = $('advisor-scope');
    if (!scope.querySelector('input')) {
      for (const [code, label] of Object.entries(data.art6 || {})) {
        const l = document.createElement('label'); l.style.display = 'block';
        const c = document.createElement('input'); c.type = 'checkbox'; c.value = code;
        c.checked = ['I', 'II', 'III', 'IV', 'X', 'XII'].includes(code);
        l.append(c, ` ${code}: ${label}`); scope.append(l);
      }
      const form = $('advisor-form');
      for (const f of data.forms || []) { const o = document.createElement('option'); o.value = o.textContent = f; form.append(o); }
    }
    const last = data.latest;
    $('advisor-current').textContent = last
      ? `Registrada: ${last.advisor_name}, ${last.authorized_on}, por ${last.record_form}; incisos ${last.scope.join(', ')}.`
      : 'Nenhuma autorização registrada. As declarações de IA sairão com esse campo para preencher.';
    $('advisor-title').textContent = 'Declaração de uso de IA (IN IFRS 16/2026, Anexo I)' + (last ? ' · autorização registrada' : ' · autorização pendente');
  } catch (_) { /* API anterior: seção fica sem dados */ }
}
// Modo sem API (MCP): tokens pessoais e projetos escritos pela IA do pesquisador.
const MCP_STAGE_LABELS = {pendente: 'pendente', recusada: 'devolvida para correção', aceita: 'aceita'};
const MCP_STATUS = {preparando: 'Lendo as fontes', pronto: 'Em andamento', falhou_preparo: 'Falha na leitura das fontes',
  compilando: 'Compilando o PDF', concluido: 'PDF final pronto', rascunho: 'Rascunho (não é a versão final)',
  refazendo_referencias: 'Refazendo as referências'};
function mcpMessage(text) { $('mcp-message').textContent = text; }
// Comece aqui: três passos com estado. Some quando tudo foi feito.
const startState = {fontes: false, ia: false, artigo: false};
const startKnown = new Set();
function updateStart(part, value) {
  if (part) { startState[part] = value; startKnown.add(part); }
  const strip = $('start-strip'); if (!strip || API_MODE || startKnown.size < 3) return;
  const steps = [['start-1', startState.fontes], ['start-2', startState.ia], ['start-3', startState.artigo]];
  const current = steps.find(([, done]) => !done);
  for (const [id, done] of steps) {
    const li = $(id); li.classList.toggle('done', done); li.classList.toggle('current', current && current[0] === id);
    li.querySelector('.start-n').textContent = done ? '✓' : id.slice(-1);
    li.querySelector('button').setAttribute('aria-label', li.querySelector('b').textContent + (done ? ': feito' : current && current[0] === id ? ': próximo passo' : ''));
  }
  strip.classList.toggle('hidden', !current);
}
function openConnect() {
  const panel = $('account-panel');
  if (panel.classList.contains('as-modal')) setAccountPanelOpen(true);
  $('mcp-details').open = true;
  $('mcp-details').scrollIntoView({behavior: 'smooth', block: 'start'});
}
document.querySelector('[data-start="2"]')?.addEventListener('click', openConnect);

// Qual IA: mostra só os passos dela; a escolha fica neste navegador.
const AI_KEY = 'scriptorium_minha_ia';
function chooseAi(ai) {
  for (const b of document.querySelectorAll('#mcp-ai-choice [data-ai]')) {
    const on = b.dataset.ai === ai; b.classList.toggle('active', on); b.setAttribute('aria-checked', String(on));
  }
  for (const node of document.querySelectorAll('#mcp-details [data-ai-only]')) node.hidden = !node.dataset.aiOnly.split(' ').includes(ai);
  try { localStorage.setItem(AI_KEY, ai); } catch (_) { /* navegador sem armazenamento */ }
}
for (const b of document.querySelectorAll('#mcp-ai-choice [data-ai]')) b.addEventListener('click', () => chooseAi(b.dataset.ai));
try { chooseAi(['claude', 'chatgpt', 'gemini'].includes(localStorage.getItem(AI_KEY)) ? localStorage.getItem(AI_KEY) : 'claude'); }
catch (_) { chooseAi('claude'); }

async function loadMcp() {
  try {
    const data = await (await request('/mcp-conta/tokens')).json();
    $('mcp-details').classList.remove('hidden');
    const list = $('mcp-token-list'); list.replaceChildren();
    const active = (data.tokens || []).filter(t => !t.revoked);
    $('mcp-token-count').textContent = active.length;
    if (!active.length) list.append(el('p', 'Nenhuma chave ativa.'));
    for (const t of active) {
      const row = document.createElement('div'); row.className = 'actions';
      row.append(el('span', `${t.label} · criada em ${new Date(t.created_at).toLocaleDateString('pt-BR')}`));
      const revoke = el('button', 'Desativar', 'btn btn-danger'); revoke.type = 'button';
      revoke.addEventListener('click', async () => {
        const ok = await confirmAction('Desativar esta chave?', [
          `A IA conectada com "${t.label}" deixa de ver as suas fontes na hora.`,
          'Seus artigos continuam guardados. Para conectar de novo, gere outra chave.'], 'Desativar');
        if (!ok) return;
        try { await request('/mcp-conta/tokens/' + t.id, {method: 'DELETE'}); await loadMcp(); mcpMessage('Chave desativada.'); }
        catch (e) { mcpMessage(e.message); }
      });
      row.append(revoke); list.append(row);
    }
    $('mcp-title').textContent = 'Conectar sua IA' + (active.length ? ' · conectada' : '');
    if (!active.length && !$('mcp-details').dataset.seen) { $('mcp-details').open = true; }
    $('mcp-details').dataset.seen = '1';
    updateStart('ia', active.length > 0);
    await loadMcpProjects();
  } catch (_) { $('mcp-details').classList.add('hidden'); /* API anterior ou conta sem acesso */ }
}
const MCP_TYPES = {
  artigo: 'Artigo científico',
  dissertacao: 'Dissertação de mestrado',
  tcc: 'TCC / Monografia',
  revisao_sistematica: 'Revisão sistemática',
};
const MCP_FILES = {
  'scriptorium.pdf': 'PDF',
  'scriptorium.docx': 'Word (.docx)',
  'scriptorium.tex': 'LaTeX',
  'references.bib': 'BibTeX',
  'proveniencia.json': 'Proveniência',
};
const fmt = (n, d = 0) => (n === null || n === undefined || n === '') ? '–' : Number(n).toLocaleString('pt-BR', {maximumFractionDigits: d, minimumFractionDigits: d});

async function downloadFrom(path, name) {
  try {
    const blob = await (await request(path)).blob();
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (e) { mcpMessage(e.message); }
}

function mcpStepList(etapas) {
  const list = document.createElement('ul'); list.className = 'mcp-steps';
  const next = (etapas || []).find(s => s.status !== 'aceita');
  for (const s of etapas || []) {
    const li = document.createElement('li');
    const name = el('span', (s.status === 'aceita' ? '✓ ' : '') + s.titulo, s.status === 'aceita' ? 'done' : '');
    let meta = s.status === 'aceita' ? (s.ia || '') : s === next ? (s.status === 'recusada' ? 'devolvida para correção' : 'próxima') : '';
    if (s.status === 'aceita' && s.independencia) {
      meta += s.independencia === 'outra_ia' ? ' · outra IA' : s.independencia === 'outra_conversa' ? ' · conversa nova' : '';
    }
    li.append(name, el('span', meta, 'meta')); list.append(li);
  }
  return list;
}

function mcpReview(box, p, r) {
  const k = r.concordancia;
  if (k && k.kappa !== null && k.kappa !== undefined) {
    box.append(el('h4', 'Concordância da triagem'));
    box.append(el('p', `Kappa de Cohen ${fmt(k.kappa, 2)} (${k.leitura}) em ${k.n} fontes · ` +
      (k.divergencias.length ? `${k.divergencias.length} divergência(s), resolvidas no consenso` : 'sem divergências'), 'subtle'));
  }
  const pr = r.prisma;
  if (pr) {
    box.append(el('h4', 'PRISMA 2020'));
    const grid = document.createElement('div'); grid.className = 'mcp-figures';
    const cells = [];
    if (pr.identificados !== undefined) cells.push(['Identificados', pr.identificados], ['Duplicados', pr.duplicados], ['Excluídos no título e resumo', pr.excluidos_titulo_resumo]);
    cells.push(['Avaliados na íntegra', pr.avaliados], ['Excluídos na elegibilidade', pr.excluidos_elegibilidade]);
    if (pr.excluidos_qualidade) cells.push(['Abaixo da nota de corte', pr.excluidos_qualidade]);
    cells.push(['Incluídos', pr.incluidos]);
    for (const [label, value] of cells) {
      const c = document.createElement('div'); c.className = 'mcp-figure';
      c.append(el('strong', fmt(value)), el('span', label)); grid.append(c);
    }
    box.append(grid);
    const reasons = Object.entries(pr.motivos || {}).map(([m, n]) => `${m}: ${n}`).join(' · ');
    if (reasons) box.append(el('p', 'Motivos de exclusão: ' + reasons, 'subtle'));
    const broken = (pr.conferencias || []).filter(c => !c.ok);
    box.append(el('p', broken.length ? 'Os números não fecham: ' + broken.map(c => c.detalhe || c.regra).join('; ') : 'Os números do fluxo fecham.', broken.length ? 'warning' : 'subtle'));
  }
  if ((r.estudos || []).length) {
    box.append(el('h4', 'Qualidade e extração'));
    const wrap = document.createElement('div'); wrap.className = 'mcp-table-wrap';
    const table = document.createElement('table'); table.className = 'eval-table';
    const head = document.createElement('tr');
    for (const h of ['Estudo', 'Nota', ...(r.campos || [])]) head.append(el('th', h));
    table.append(head);
    for (const s of r.estudos) {
      const tr = document.createElement('tr');
      tr.append(el('td', s.chave), el('td', fmt(s.nota, 1) + (s.abaixo_do_corte ? ' (abaixo do corte)' : '')));
      for (const f of r.campos || []) tr.append(el('td', s[f] || ''));
      table.append(tr);
    }
    wrap.append(table); box.append(wrap);
    const csvBtn = el('button', 'Baixar matriz (CSV)', 'btn alt'); csvBtn.type = 'button';
    csvBtn.addEventListener('click', () => downloadFrom(`/mcp-conta/projetos/${p.projeto}/matriz.csv`, 'matriz_extracao.csv'));
    const actions = document.createElement('div'); actions.className = 'actions'; actions.append(csvBtn); box.append(actions);
  }
  const qps = Object.keys(r.sintese || {});
  if (qps.length) {
    box.append(el('h4', 'Síntese por questão'));
    box.append(el('p', 'A resposta da IA fica à vista. Se escrever a sua versão, ela substitui a da IA na redação.', 'subtle'));
    const texts = Object.fromEntries((r.questoes || []).map(q => [q.id, q.texto]));
    for (const qp of qps) {
      const item = r.sintese[qp]; const block = document.createElement('div'); block.className = 'mcp-qp';
      block.append(el('strong', `${qp}. ${texts[qp] || ''}`), el('div', item.ia || 'Sem resposta da IA.', 'ia'));
      const area = document.createElement('textarea'); area.value = item.final || '';
      area.placeholder = 'Sua versão final (opcional)'; area.setAttribute('aria-label', `Versão final de ${qp}`);
      const save = el('button', 'Salvar versão final', 'btn alt'); save.type = 'button';
      const status = el('span', '', 'subtle');
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          const out = await (await request(`/mcp-conta/projetos/${p.projeto}/sintese`, {method: 'PUT', body: JSON.stringify({qp, texto: area.value})})).json();
          status.textContent = out.aviso || 'Salvo.';
        } catch (e) { status.textContent = e.message; }
        finally { save.disabled = false; }
      });
      const actions = document.createElement('div'); actions.className = 'actions'; actions.append(save, status);
      block.append(area, actions); box.append(block);
    }
  }
}

async function openMcpProject(p, holder, button) {
  if (!holder.hidden) { holder.hidden = true; button.textContent = 'Ver etapas'; button.setAttribute('aria-expanded', 'false'); return; }
  holder.hidden = false; button.textContent = 'Fechar etapas'; button.setAttribute('aria-expanded', 'true');
  holder.replaceChildren(el('p', 'Carregando...', 'subtle'));
  try {
    const data = await (await request(`/mcp-conta/projetos/${p.projeto}/detalhe`)).json();
    holder.replaceChildren();
    holder.append(mcpStepList(data.estado.etapas));
    if (data.revisao) mcpReview(holder, p, data.revisao);
    const files = (data.estado.arquivos || []).filter(f => MCP_FILES[f] && f !== 'scriptorium.pdf');
    if (files.length) {
      holder.append(el('h4', 'Outros arquivos'));
      const actions = document.createElement('div'); actions.className = 'actions';
      for (const name of files) {
        const b = el('button', MCP_FILES[name], 'btn alt'); b.type = 'button';
        b.addEventListener('click', () => downloadFrom(`/mcp-conta/projetos/${p.projeto}/arquivos/${name}`, name));
        actions.append(b);
      }
      holder.append(actions);
    }
  } catch (e) { holder.replaceChildren(el('p', e.message, 'warning')); }
}

function askBox(text) {
  const box = document.createElement('div'); box.className = 'art-ask';
  const code = el('code', text);
  const copy = el('button', 'Copiar pedido', 'btn alt'); copy.type = 'button';
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(text); copy.textContent = 'Copiado'; setTimeout(() => { copy.textContent = 'Copiar pedido'; }, 2000); }
    catch (_) { const r = document.createRange(); r.selectNodeContents(code); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); }
  });
  box.append(code, copy); return box;
}

const REF_TYPE_OPTIONS = [
  ['article', 'Artigo de revista'],
  ['inproceedings', 'Artigo em evento / anais'],
  ['mastersthesis', 'Dissertação de mestrado'],
  ['phdthesis', 'Tese de doutorado'],
  ['book', 'Livro'],
  ['incollection', 'Capítulo de livro'],
  ['techreport', 'Relatório técnico / guia'],
  ['misc', 'Outro documento'],
];

async function renderCoverPreview(coverBox, coverPath, page = 1) {
  coverBox.replaceChildren(el('p', 'Carregando imagem da capa…', 'subtle'));
  try {
    const r = await request(`${coverPath}?page=${page}`);
    const total = Number(r.headers.get('X-Scriptorium-Pages-Total') || page);
    const shown = Number(r.headers.get('X-Scriptorium-Page') || page);
    const url = URL.createObjectURL(await r.blob());
    coverBox.replaceChildren();
    const nav = document.createElement('div');
    nav.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap';
    const prev = el('button', '← Anterior', 'btn alt'); prev.type = 'button'; prev.style.padding = '4px 9px'; prev.disabled = shown <= 1;
    const lbl = el('small', `Página ${shown} de ${total}`);
    const next = el('button', 'Próxima →', 'btn alt'); next.type = 'button'; next.style.padding = '4px 9px'; next.disabled = shown >= Math.min(total, 5);
    prev.addEventListener('click', () => renderCoverPreview(coverBox, coverPath, shown - 1));
    next.addEventListener('click', () => renderCoverPreview(coverBox, coverPath, shown + 1));
    nav.append(prev, lbl, next);
    const img = document.createElement('img');
    img.src = url; img.alt = `Página ${shown} do PDF`;
    img.addEventListener('load', () => setTimeout(() => URL.revokeObjectURL(url), 2000));
    coverBox.append(nav, img);
  } catch (e) {
    coverBox.replaceChildren(el('p', 'Não foi possível mostrar a capa: ' + e.message, 'subtle'));
  }
}

function buildReferenceCard({ titleLabel, badgeText, initial, proposal, coverPath, onConfirm }) {
  const card = document.createElement('div'); card.className = 'ref-check-card';
  const head = document.createElement('div'); head.className = 'ref-check-head';
  head.append(el('strong', titleLabel), el('span', badgeText, 'pill'));
  card.append(head);

  const src = (proposal && proposal.fields) ? { ...proposal.fields, tipo: proposal.type } : initial;
  const venueVal = src.veiculo || src.journal || src.booktitle || src.school || src.publisher || src.institution || src.howpublished || '';

  if (proposal && proposal.fields) {
    const banner = document.createElement('div'); banner.className = 'ref-proposal-banner';
    banner.textContent = '✨ A sua IA já preencheu uma sugestão abaixo. Confira olhando a capa do PDF ao lado e clique em "Confirmar referência".';
    card.append(banner);
  }

  const grid = document.createElement('div'); grid.className = 'ref-check-grid';
  const form = document.createElement('div'); form.className = 'ref-check-form';
  const mkField = (labelText, value, placeholder, full = false) => {
    const wrap = document.createElement('div'); if (full) wrap.className = 'full';
    const lbl = el('label', labelText);
    const inp = document.createElement('input'); inp.type = 'text'; inp.value = value || ''; inp.placeholder = placeholder || '';
    wrap.append(lbl, inp); form.append(wrap);
    return inp;
  };
  const inpTitle = mkField('Título completo da obra', src.title || src.titulo || '', 'Ex.: Diretrizes para revisões sistemáticas', true);
  const inpAuthors = mkField('Autores (Sobrenome, Nome — separe vários com ";")',
    String(src.author || src.autor || '').replace(/\s+and\s+/g, '; '), 'Ex.: Kitchenham, Barbara; Charters, Stuart', true);
  const inpYear = mkField('Ano', src.year || src.ano || '', 'Ex.: 2024', false);

  const typeWrap = document.createElement('div');
  typeWrap.append(el('label', 'Tipo de publicação'));
  const selType = document.createElement('select');
  for (const [val, label] of REF_TYPE_OPTIONS) selType.append(new Option(label, val));
  selType.value = src.tipo || initial.tipo || 'article';
  typeWrap.append(selType); form.append(typeWrap);

  const inpVenue = mkField('Revista, evento ou instituição (opcional)', venueVal, 'Ex.: RENOTE ou IFRS', true);
  const inpDoi = mkField('DOI (opcional)', src.doi || '', 'Ex.: 10.1234/exemplo', true);

  const coverBox = document.createElement('div'); coverBox.className = 'ref-cover-box';
  if (coverPath) {
    const showCover = el('button', '👁 Ver capa do PDF', 'btn alt'); showCover.type = 'button';
    showCover.addEventListener('click', () => renderCoverPreview(coverBox, coverPath, 1));
    coverBox.append(el('small', 'Confira título, autor e ano direto na capa original:', 'subtle'), document.createElement('br'), showCover);
  } else {
    coverBox.append(el('small', 'Prévia de capa disponível apenas para arquivos PDF.', 'subtle'));
  }

  grid.append(form, coverBox);
  card.append(grid);

  const foot = document.createElement('div'); foot.className = 'actions'; foot.style.marginTop = '12px';
  const status = el('span', '', 'subtle');
  const saveBtn = el('button', '✓ Confirmar referência', 'btn'); saveBtn.type = 'button';
  saveBtn.addEventListener('click', async () => {
    const authors = inpAuthors.value.split(/\s*;\s*|\s+and\s+/).map(s => s.trim()).filter(Boolean);
    saveBtn.disabled = true; status.textContent = 'Salvando…';
    try {
      await onConfirm({
        aceitar_proposta: false,
        titulo: inpTitle.value.trim(),
        autores: authors,
        ano: inpYear.value.trim(),
        tipo: selType.value,
        veiculo: inpVenue.value.trim(),
        doi: inpDoi.value.trim(),
      });
      status.textContent = '✓ Confirmada e salva na sua biblioteca para futuros artigos!';
    } catch (e) {
      status.textContent = e.message; saveBtn.disabled = false;
    }
  });
  foot.append(saveBtn);
  if (proposal && proposal.fields) {
    const quick = el('button', '✓ Aceitar sugestão da IA (1 clique)', 'btn alt'); quick.type = 'button';
    quick.addEventListener('click', async () => {
      quick.disabled = saveBtn.disabled = true; status.textContent = 'Confirmando…';
      try { await onConfirm({ aceitar_proposta: true }); status.textContent = '✓ Confirmada!'; }
      catch (e) { status.textContent = e.message; quick.disabled = saveBtn.disabled = false; }
    });
    foot.append(quick);
  }
  foot.append(status);
  card.append(foot);
  return card;
}

function toggleLibraryRefEditor(item, holder) {
  const existing = holder.querySelector('.lib-ref-editor');
  if (existing) { existing.remove(); return; }
  const wrap = document.createElement('div'); wrap.className = 'lib-ref-editor'; wrap.style.marginTop = '10px';
  const bib = item.bib_entry || {};
  const card = buildReferenceCard({
    titleLabel: 'Ficha bibliográfica permanente (vale para todos os artigos)',
    badgeText: bib.how ? 'Confirmada' : 'Ainda não confirmada',
    initial: { ...(bib.fields || {}), tipo: bib.type || 'article', titulo: (bib.fields || {}).title || item.name.replace(/\.\w+$/, '') },
    proposal: null,
    coverPath: item.format === 'pdf' ? `/library/items/${item.id}/cover` : null,
    onConfirm: async (payload) => {
      await request(`/library/items/${item.id}/reference`, { method: 'PUT', body: JSON.stringify(payload) });
      await loadLibrary();
    },
  });
  wrap.append(card); holder.append(wrap);
}

function articleCard(p) {
  const card = document.createElement('article'); card.className = 'art-card';
  const head = document.createElement('div'); head.className = 'mcp-row-head';
  const info = document.createElement('div');
  const total = (p.etapas || []).length;
  const done = (p.etapas || []).filter(s => s.status === 'aceita').length;
  info.append(el('strong', p.titulo || p.projeto),
    el('p', `${MCP_TYPES[p.tipo] || 'Artigo'} · ${done} de ${total} etapas`, 'subtle'));
  const bar = document.createElement('div'); bar.className = 'art-progress';
  bar.setAttribute('role', 'progressbar'); bar.setAttribute('aria-valuemin', '0'); bar.setAttribute('aria-valuemax', String(total));
  bar.setAttribute('aria-valuenow', String(done)); bar.setAttribute('aria-label', `${done} de ${total} etapas`);
  const fill = document.createElement('span'); fill.style.width = total ? `${Math.round(100 * done / total)}%` : '0%';
  bar.append(fill); info.append(bar);
  const actions = document.createElement('div'); actions.className = 'actions'; actions.style.margin = '0';
  if ((p.arquivos || []).includes('scriptorium.pdf')) {
    const pdf = el('button', p.pdf_final ? 'Baixar PDF final' : 'Baixar PDF (rascunho)', 'btn'); pdf.type = 'button';
    pdf.addEventListener('click', () => downloadFrom(`/mcp-conta/projetos/${p.projeto}/arquivos/scriptorium.pdf`, 'scriptorium.pdf'));
    actions.append(pdf);
  }
  if ((p.arquivos || []).includes('scriptorium.tex') || (p.arquivos || []).includes('scriptorium.pdf')) {
    const docx = el('button', 'Baixar Word (.docx)', 'btn alt'); docx.type = 'button';
    docx.title = 'Baixa documento editável em padrão ABNT para abrir no Microsoft Word ou Google Docs.';
    docx.addEventListener('click', () => downloadFrom(`/mcp-conta/projetos/${p.projeto}/arquivos/scriptorium.docx`, 'scriptorium.docx'));
    actions.append(docx);
    const pkg = el('button', 'Pacote para orientação (.zip)', 'btn alt'); pkg.type = 'button';
    pkg.title = 'Baixa PDF, Word (.docx), BibTeX, proveniência e resumo legível para enviar à orientação.';
    pkg.addEventListener('click', () => downloadFrom(`/mcp-conta/projetos/${p.projeto}/pacote-orientacao.zip`, 'pacote_orientacao.zip'));
    actions.append(pkg);
  }
  const refs = p.referencias_a_conferir || [];
  const busy = ['preparando', 'compilando', 'refazendo_referencias'].includes(p.status);
  if (p.pode_compilar && !busy) {
    const wantDraft = refs.length > 0;
    const compBtn = el('button', wantDraft ? 'Gerar rascunho agora' : 'Gerar PDF final', wantDraft ? 'btn alt' : 'btn');
    compBtn.type = 'button';
    compBtn.addEventListener('click', async () => {
      compBtn.disabled = true; compBtn.textContent = 'Iniciando…';
      try {
        await request(`/mcp-conta/projetos/${p.projeto}/compilar`, { method: 'POST', body: JSON.stringify({ rascunho: wantDraft }) });
        await loadMcpProjects();
      } catch (e) {
        compBtn.disabled = false; compBtn.textContent = wantDraft ? 'Gerar rascunho agora' : 'Gerar PDF final';
        card.append(el('p', e.message, 'warning'));
      }
    });
    actions.append(compBtn);
  }
  const open = el('button', 'Ver etapas', 'btn alt'); open.type = 'button'; open.setAttribute('aria-expanded', 'false');
  const detail = document.createElement('div'); detail.className = 'mcp-detail'; detail.hidden = true;
  open.addEventListener('click', () => openMcpProject(p, detail, open));
  const shareBtn = el('button', p.tem_link_orientacao ? 'Link da orientação (ativo)' : 'Compartilhar com orientador(a)', 'btn alt');
  shareBtn.type = 'button'; shareBtn.setAttribute('aria-expanded', 'false');
  const shareBox = document.createElement('div'); shareBox.className = 'advisor-box'; shareBox.hidden = true;
  shareBtn.addEventListener('click', () => {
    const show = shareBox.hidden;
    shareBox.hidden = !show;
    shareBtn.setAttribute('aria-expanded', String(show));
    if (show && !shareBox.dataset.ready) {
      shareBox.dataset.ready = '1';
      shareBox.append(el('p', 'Gere um link temporário (somente leitura) para seu orientador acompanhar etapas, conferências e referências sem precisar criar conta. Você pode revogar quando quiser.', 'subtle'));
      const noteIn = document.createElement('input');
      noteIn.type = 'text'; noteIn.maxLength = 600;
      noteIn.placeholder = 'Recado ou dúvida opcional para a orientação (ex.: confira se a metodologia está alinhada)';
      noteIn.style.marginBottom = '8px';
      const row = document.createElement('div'); row.className = 'actions'; row.style.margin = '0';
      const st = el('span', p.tem_link_orientacao ? `Link ativo (expira em ${new Date(p.link_orientacao_expira).toLocaleDateString('pt-BR')}).` : '', 'subtle');
      const urlOut = document.createElement('input'); urlOut.type = 'text'; urlOut.readOnly = true; urlOut.className = 'hidden'; urlOut.style.marginTop = '8px';
      const genBtn = el('button', p.tem_link_orientacao ? 'Gerar novo link (14 dias)' : 'Gerar link de leitura (14 dias)', 'btn'); genBtn.type = 'button';
      const copyBtn = el('button', 'Copiar link', 'btn alt hidden'); copyBtn.type = 'button';
      const revBtn = el('button', 'Revogar link', 'btn alt'); revBtn.type = 'button';
      if (!p.tem_link_orientacao) revBtn.classList.add('hidden');
      genBtn.addEventListener('click', async () => {
        genBtn.disabled = true; st.textContent = 'Gerando link seguro…';
        try {
          const data = await (await request(`/mcp-conta/projetos/${p.projeto}/orientacao/link`, {
            method: 'POST', body: JSON.stringify({ dias: 14, nota: noteIn.value.trim() }),
          })).json();
          urlOut.value = data.url; urlOut.classList.remove('hidden'); copyBtn.classList.remove('hidden'); revBtn.classList.remove('hidden');
          shareBtn.textContent = 'Link da orientação (ativo)';
          st.textContent = `✓ Link criado! Válido até ${new Date(data.expira_em).toLocaleDateString('pt-BR')}.`;
        } catch (e) { st.textContent = e.message; }
        finally { genBtn.disabled = false; }
      });
      copyBtn.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(urlOut.value); st.textContent = '✓ Link copiado! Agora é só enviar para o(a) orientador(a).'; }
        catch (_) { urlOut.select(); st.textContent = 'Selecione e copie o link acima.'; }
      });
      revBtn.addEventListener('click', async () => {
        revBtn.disabled = true;
        try {
          await request(`/mcp-conta/projetos/${p.projeto}/orientacao/link`, { method: 'DELETE' });
          urlOut.value = ''; urlOut.classList.add('hidden'); copyBtn.classList.add('hidden'); revBtn.classList.add('hidden');
          shareBtn.textContent = 'Compartilhar com orientador(a)';
          st.textContent = 'Link revogado. Ninguém mais consegue abrir o endereço anterior.';
        } catch (e) { st.textContent = e.message; }
        finally { revBtn.disabled = false; }
      });
      row.append(genBtn, copyBtn, revBtn, st);
      shareBox.append(noteIn, row, urlOut);
    }
  });
  actions.append(shareBtn, open); head.append(info, actions); card.append(head, shareBox);

  // Fase 2: Seletor de salvaguarda pedagógica (Tutor Socrático / Intermediário / Autônomo)
  const pedRow = document.createElement('div');
  pedRow.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:8px;font-size:.8rem';
  const pedLbl = el('span', 'Mediação da IA:', 'subtle');
  const pedSel = document.createElement('select');
  pedSel.style.cssText = 'width:auto;padding:4px 8px;font-size:.8rem';
  pedSel.setAttribute('aria-label', 'Modo pedagógico da IA para ' + (p.titulo || p.projeto));
  for (const [val, txt] of [
    ['tutor_socratico', 'Tutor Socrático (perguntas e pistas)'],
    ['intermediario', 'Intermediário (feedback crítico)'],
    ['autonomo', 'Autônomo (revisão pontual)'],
  ]) pedSel.append(new Option(txt, val));
  pedSel.value = p.modo_pedagogico || 'tutor_socratico';
  const pedMsg = el('span', '', 'subtle');
  pedSel.addEventListener('change', async () => {
    pedSel.disabled = true; pedMsg.textContent = 'Salvando…';
    try {
      await request(`/mcp-conta/projetos/${p.projeto}/modo-pedagogico`, {
        method: 'PATCH', body: JSON.stringify({ modo_pedagogico: pedSel.value }),
      });
      pedMsg.textContent = '✓ Modo atualizado.';
    } catch (e) { pedMsg.textContent = e.message; }
    finally { pedSel.disabled = false; }
  });
  pedRow.append(pedLbl, pedSel, pedMsg);
  card.append(pedRow);

  // Fase 2: Apontamentos deixados pelo(a) orientador(a) no link compartilhado
  const advComments = p.comentarios_orientacao || [];
  if (advComments.length) {
    const cDet = document.createElement('details');
    cDet.className = 'advisor-box';
    cDet.style.marginTop = '10px';
    const pend = advComments.filter(c => !c.resolved).length;
    cDet.open = pend > 0;
    cDet.append(el('summary', `Apontamentos da orientação (${pend} pendente(s) de ${advComments.length})`));
    const kindLabels = { elogio: '✓ Elogio', sugestao: 'Sugestão', ajuste_obrigatorio: '⚠ Ajuste obrigatório' };
    for (const c of advComments) {
      const itemBox = document.createElement('div');
      itemBox.className = 'study-note-card';
      itemBox.style.marginTop = '8px';
      if (c.resolved) itemBox.style.opacity = '0.68';
      const top = document.createElement('div');
      top.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px;align-items:center';
      top.append(el('strong', `${c.author || 'Orientador(a)'} · ${c.stage || 'Geral'} · ${kindLabels[c.kind] || c.kind}`));
      const rBtn = el('button', c.resolved ? '✓ Resolvido (reabrir)' : 'Marcar como resolvido', 'btn alt');
      rBtn.type = 'button'; rBtn.style.cssText = 'padding:3px 9px;font-size:.76rem';
      rBtn.addEventListener('click', async () => {
        rBtn.disabled = true;
        try {
          await request(`/mcp-conta/projetos/${p.projeto}/orientacao/comentarios/${c.id}`, {
            method: 'PATCH', body: JSON.stringify({ resolvido: !c.resolved }),
          });
          await loadMcpProjects();
        } catch (e) { alert(e.message); rBtn.disabled = false; }
      });
      top.append(rBtn);
      const txt = el('p', c.text); txt.style.margin = '6px 0 0';
      itemBox.append(top, txt);
      cDet.append(itemBox);
    }
    card.append(cDet);
  }

  const step = p.proximo_passo;
  if (step) {
    const next = document.createElement('div'); next.className = 'art-next';
    next.append(el('strong', step.titulo), el('p', step.texto));
    if (step.detalhe) next.append(el('p', step.detalhe, 'subtle'));
    if (step.pedido) next.append(askBox(step.pedido));
    if (step.pedido_rascunho) {
      next.append(el('p', 'Para ler o texto antes, você pode clicar em "Gerar rascunho agora" acima ou pedir à sua IA:', 'subtle'));
      next.append(askBox(step.pedido_rascunho));
    }
    card.append(next);
  }
  if (refs.length && !p.pdf_final) {
    const box = document.createElement('details'); box.className = 'art-refs';
    if (refs.some(r => r.proposta_pendente)) box.open = true;
    box.append(el('summary', `${refs.length} referência(s) para confirmar antes do PDF final (clique para conferir ao lado da capa)`));
    box.append(el('p', 'Confira cada obra olhando a capa do PDF e clique em "Confirmar referência". Quando você confirma uma vez, ela fica salva na sua biblioteca para todos os próximos artigos.', 'subtle'));
    const listWrap = document.createElement('div'); listWrap.className = 'ref-check-list';
    for (const r of refs) {
      listWrap.append(buildReferenceCard({
        titleLabel: `${r.titulo || r.chave} (${r.chave})`,
        badgeText: r.proposta_pendente ? 'Proposta pronta da IA' : (r.nivel_texto || 'A conferir'),
        initial: r,
        proposal: r.proposta_pendente || null,
        coverPath: r.tem_capa ? `/mcp-conta/projetos/${p.projeto}/referencias/${encodeURIComponent(r.chave)}/capa` : null,
        onConfirm: async (payload) => {
          await request(`/mcp-conta/projetos/${p.projeto}/referencias/${encodeURIComponent(r.chave)}/confirmar`,
            { method: 'POST', body: JSON.stringify(payload) });
          await loadMcpProjects();
        },
      }));
    }
    box.append(listWrap);
    const helpDetails = document.createElement('details'); helpDetails.className = 'mini-details';
    helpDetails.append(el('summary', 'Preferir pedir para a sua IA conferir automaticamente?'));
    helpDetails.append(askBox(p.pedido_referencias));
    box.append(helpDetails);
    if (!busy) {
      const again = el('button', 'Refazer busca automática das referências', 'btn alt'); again.type = 'button';
      again.title = 'Consulta de novo as bases acadêmicas mantendo as chaves e as confirmações já feitas.';
      again.addEventListener('click', async () => {
        again.disabled = true;
        try { await request(`/mcp-conta/projetos/${p.projeto}/referencias/refazer`, {method: 'POST'}); await loadMcpProjects(); }
        catch (e) { again.disabled = false; box.append(el('p', e.message, 'warning')); }
      });
      const act = document.createElement('div'); act.className = 'actions'; act.append(again); box.append(act);
    }
    card.append(box);
  }
  if ((p.provas || []).length) {
    const ul = document.createElement('ul'); ul.className = 'art-proofs'; ul.setAttribute('aria-label', 'Já conferido pelo Scriptorium');
    for (const line of p.provas) ul.append(el('li', line));
    card.append(ul);
  }
  card.append(detail);
  return card;
}

function renderMcpProjectsList(projects) {
  const box = $('mcp-projects'); if (!box) return;
  box.replaceChildren();
  window.ScriptoriumProjetos?.definir(projects);
  updateStart('artigo', projects.length > 0);
  if (!projects.length) {
    const empty = document.createElement('div'); empty.className = 'art-empty';
    if (!startState.ia) {
      empty.append(el('p', 'Nenhum artigo ainda. Primeiro conecte a sua IA; depois é só pedir o artigo na conversa.', 'subtle'));
      const go = el('button', 'Conectar sua IA', 'btn'); go.type = 'button'; go.addEventListener('click', openConnect);
      empty.append(go);
    } else {
      empty.append(el('p', 'Nenhum artigo ainda. Na conversa com a sua IA, peça:', 'subtle'));
      empty.append(askBox($('mcp-first-prompt').value));
    }
    box.append(empty); return;
  }
  for (const p of projects) box.append(articleCard(p));
}

async function loadMcpProjects() {
  const box = $('mcp-projects'); if (!box) return;
  let projects = [];
  try { projects = (await (await request('/mcp-conta/projetos')).json()).projetos || []; }
  catch (e) { if (!box.children.length) box.replaceChildren(el('p', e.message, 'subtle')); return; }
  lastMcpBusy = projects.some(p => BUSY_MCP_STATUSES.has(p.status));
  syncSmartPolling();
  if (user) writeUiCache(user.uid, { mcpProjects: projects });
  renderMcpProjectsList(projects);
}
function renderNewProjectSources() {
  const box = $('new-proj-sources'); if (!box) return;
  const usable = (libraryItems || []).filter(i => ['pdf', 'docx', 'txt'].includes((i.format || '').toLowerCase()));
  if (!usable.length) {
    box.textContent = 'Envie primeiro ao menos 1 PDF, DOCX ou TXT na aba Biblioteca.';
    return;
  }
  const prev = new Set([...box.querySelectorAll('input:checked')].map(c => c.value));
  box.replaceChildren();
  for (const item of usable) {
    const row = document.createElement('label');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 2px;cursor:pointer;font-weight:500;font-size:0.88rem';
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.value = item.id; cb.checked = prev.has(item.id) || (prev.size === 0 && usable.length <= 8);
    const name = document.createElement('span'); name.textContent = item.name;
    row.append(cb, name);
    box.append(row);
  }
}

function readGuidePlanFallback() {
  if (typeof window.ScriptoriumGuiaResumo === 'function') return window.ScriptoriumGuiaResumo();
  try {
    const raw = JSON.parse(localStorage.getItem('scriptorium_pesquisa_guiada_v2') || 'null');
    if (!raw || !raw.values) return null;
    const v = raw.values;
    const titulo = (v.tituloFinal || v.tituloProvisorio || v.tema || '').trim();
    const parts = [
      v.pergunta && ('Pergunta de pesquisa: ' + v.pergunta.trim()),
      v.problema && ('Problema: ' + v.problema.trim()),
      v.objetivoGeral && ('Objetivo geral: ' + v.objetivoGeral.trim()),
      v.estrategia && ('Estratégia metodológica: ' + v.estrategia.trim()),
    ].filter(Boolean);
    if (!titulo && !parts.length) return null;
    const tipo = raw.tipo === 'projeto' ? 'dissertacao' : 'artigo';
    return { titulo, pergunta: parts.join('\n\n'), tipo, modelo: tipo === 'dissertacao' ? 'abnt-dissertacao' : 'abnt-artigo' };
  } catch (_) { return null; }
}

function applyGuidePlanToForm(plan) {
  const hint = $('new-proj-guide-hint');
  const data = plan || readGuidePlanFallback();
  if (!data || (!data.titulo && !data.pergunta)) {
    if (hint) hint.textContent = 'Preencha primeiro ao menos o tema ou a pergunta na aba Guia de escrita.';
    return false;
  }
  const box = $('new-mcp-project-box'); if (box) box.open = true;
  if ($('new-proj-title') && data.titulo) $('new-proj-title').value = data.titulo.slice(0, 120);
  if ($('new-proj-question') && data.pergunta) $('new-proj-question').value = data.pergunta.slice(0, 4000);
  if ($('new-proj-type')) {
    const targetVal = data.tipo === 'dissertacao' ? 'dissertacao|abnt-dissertacao'
      : data.tipo === 'tcc' ? 'tcc|abnt-tcc' : 'artigo|abnt-artigo';
    $('new-proj-type').value = targetVal;
  }
  if ($('new-proj-pedagogical') && data.modo_pedagogico) {
    $('new-proj-pedagogical').value = data.modo_pedagogico;
  }
  renderNewProjectSources();
  if (hint) hint.textContent = '✓ Plano trazido do Guia de Escrita! Confira as fontes e clique em Criar.';
  return true;
}

window.ScriptoriumPonteGuia = {
  enviar(plan) {
    window.ScriptoriumNavegar?.('3');
    applyGuidePlanToForm(plan);
    $('new-mcp-project-box')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },
};

$('fill-from-guide')?.addEventListener('click', () => applyGuidePlanToForm(null));
$('new-proj-select-all')?.addEventListener('click', () => {
  const cbs = [...($('new-proj-sources')?.querySelectorAll('input[type="checkbox"]') || [])];
  const allChecked = cbs.length > 0 && cbs.every(c => c.checked);
  cbs.slice(0, 20).forEach(c => { c.checked = !allChecked; });
});
$('create-mcp-project-btn')?.addEventListener('click', async () => {
  const btn = $('create-mcp-project-btn'), st = $('new-proj-status');
  const [tipo, modelo] = ($('new-proj-type')?.value || 'artigo|abnt-artigo').split('|');
  const titulo = ($('new-proj-title')?.value || '').trim();
  const pergunta = ($('new-proj-question')?.value || '').trim();
  const fontes = [...($('new-proj-sources')?.querySelectorAll('input:checked') || [])].map(c => c.value).slice(0, 20);
  if (titulo.length < 3) { st.textContent = 'Informe um título com pelo menos 3 caracteres.'; return; }
  if (pergunta.length < 20) { st.textContent = 'Escreva a pergunta ou objetivo (mínimo 20 caracteres).'; return; }
  if (!fontes.length) { st.textContent = 'Escolha pelo menos 1 fonte da sua biblioteca.'; return; }
  btn.disabled = true; st.textContent = 'Criando projeto e preparando fontes…';
  const modo_pedagogico = $('new-proj-pedagogical')?.value || 'tutor_socratico';
  try {
    await request('/mcp-conta/projetos', {
      method: 'POST',
      body: JSON.stringify({ titulo, pergunta, fontes, tipo, modelo, idioma: 'pt-BR', modo_pedagogico }),
    });
    st.textContent = '✓ Criado! O Scriptorium já está lendo suas fontes.';
    $('new-proj-title').value = ''; $('new-proj-question').value = '';
    if ($('new-mcp-project-box')) $('new-mcp-project-box').open = false;
    await loadMcpProjects();
  } catch (e) { st.textContent = e.message; }
  finally { btn.disabled = false; }
});

$('mcp-projects-refresh')?.addEventListener('click', () => loadMcpProjects());
if (API_MODE && $('step-sub-3')) $('step-sub-3').textContent = 'Histórico, agentes e pareceres';
$('mcp-create-token')?.addEventListener('click', async () => {
  const label = $('mcp-token-label').value.trim() || 'Minha IA';
  try {
    const data = await (await request('/mcp-conta/tokens', {method: 'POST', body: JSON.stringify({label})})).json();
    $('mcp-url-token').value = data.endereco_com_token;
    $('mcp-gemini-config').value = JSON.stringify({mcpServers: {scriptorium: {httpUrl: data.endereco,
      headers: {Authorization: 'Bearer ' + data.token}, timeout: 120000}}}, null, 2);
    $('mcp-new-token').classList.remove('hidden');
    $('mcp-token-label').value = '';
    mcpMessage('Chave gerada. Copie agora e siga o passo 3.');
    await loadMcp();
  } catch (e) { mcpMessage(e.message); }
});
for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const field = $(button.dataset.copy);
    try { await navigator.clipboard.writeText(field.value); mcpMessage('Copiado.'); }
    catch (_) { field.select(); mcpMessage('Selecione e copie manualmente.'); }
  });
}
$('save-profile').addEventListener('click', async () => {
  const body = {full_name: $('profile-name').value.trim(), enrollment: $('profile-enrollment').value.trim(),
    unit: $('profile-unit').value.trim(), program: $('profile-program').value.trim()};
  if (body.full_name.length < 3) { $('profile-message').textContent = 'Informe o nome completo.'; return; }
  try { await request('/account/academic-profile', {method: 'PUT', body: JSON.stringify(body)}); $('profile-message').textContent = 'Identificação salva.'; }
  catch (e) { $('profile-message').textContent = e.message; }
});
$('save-advisor').addEventListener('click', async () => {
  const scope = [...$('advisor-scope').querySelectorAll('input:checked')].map(c => c.value);
  const body = {advisor_name: $('advisor-name').value.trim(), authorized_on: $('advisor-date').value,
    record_form: $('advisor-form').value, record_reference: $('advisor-reference').value.trim(), scope};
  if (!body.advisor_name || !body.authorized_on || !scope.length) { $('advisor-message').textContent = 'Preencha nome, data e ao menos um uso.'; return; }
  try { await request('/account/advisor-authorization', {method: 'POST', body: JSON.stringify(body)}); $('advisor-message').textContent = 'Autorização registrada.'; await loadAdvisor(); }
  catch (e) { $('advisor-message').textContent = e.message; }
});

// M21: fichamento por IA sob demanda (gasta a sua chave Gemini; fica em cache).
function renderNotes(box, n) {
  box.append(el('h4', `Fichamento por IA (${n.model})`));
  for (const [label, value] of [['Tema', n.tema], ['Objetivo', n.objetivo], ['Método', n.metodo]]) if (value) box.append(el('p', `${label}: ${value}`));
  if ((n.principais_achados || []).length) {
    box.append(el('strong', 'Principais achados'));
    for (const a of n.principais_achados) {
      const where = (a.trechos || []).map(t => t.pages ? `p. ${t.pages[0]}` : t.id).join(', ');
      box.append(el('p', `${a.sem_trecho_valido ? '⚠ ' : ''}${a.texto}${where ? ' (' + where + ')' : ' (sem trecho que comprove)'}`, a.sem_trecho_valido ? 'editorial-alert' : ''));
    }
  }
  if ((n.conceitos_chave || []).length) box.append(el('p', 'Conceitos: ' + n.conceitos_chave.join(', ')));
  for (const q of n.citacoes_literais || []) box.append(el('p', `${q.situacao === 'conferida' ? '✓ conferida' : '⚠ não encontrada no documento'}${q.pages ? ' · p. ' + q.pages[0] : ''}: "${q.citacao}"`, q.situacao === 'conferida' ? '' : 'editorial-alert'));
  for (const l of n.limitacoes || []) box.append(el('small', 'Limitação do estudo: ' + l));
  for (const l of n.limitations || []) box.append(el('small', l));
}
async function aiNotes(itemId, box, start) {
  const area = box.querySelector('.ai-notes') || box.appendChild(Object.assign(document.createElement('div'), {className: 'ai-notes'}));
  area.textContent = start ? 'Pedindo o fichamento...' : 'Consultando...';
  try {
    if (start) {
      if (!confirm('Gerar o fichamento com IA usa tokens da sua chave Gemini (modelo Flash, uma chamada). Continuar?')) { area.textContent = ''; return; }
      await request(`/library/items/${itemId}/ai-notes`, {method: 'POST'});
    }
    for (let i = 0; i < 40; i++) {
      const d = await (await request(`/library/items/${itemId}/ai-notes`)).json();
      if (d.status === 'completed') { area.replaceChildren(); renderNotes(area, d.notes); return; }
      if (d.status === 'failed') { area.textContent = 'O fichamento falhou: ' + (d.error || 'tente de novo.'); return; }
      if (d.status === 'none') { area.textContent = ''; return; }
      area.textContent = d.stage || 'Gerando o fichamento...';
      await new Promise(r => setTimeout(r, 6000));
    }
    area.textContent = 'Ainda em andamento. Abra a ficha de novo em alguns minutos.';
  } catch (e) { area.textContent = e.message; }
}

// Fase 1: Importação unificada de referências (DOI, BibTeX ou RIS) com detecção de duplicatas.
$('refs-import')?.addEventListener('click', async () => {
  const text = ($('refs-text')?.value || '').trim();
  const msg = $('refs-message');
  const out = $('refs-results');
  if (!text) { if (msg) msg.textContent = 'Cole ao menos um DOI, BibTeX ou RIS.'; return; }
  const btn = $('refs-import'); btn.disabled = true; out?.replaceChildren();
  if (msg) msg.textContent = 'Importando e verificando duplicatas…';
  try {
    const data = await (await request('/library/import-references', {
      method: 'POST',
      body: JSON.stringify({
        text,
        collection: $('refs-collection')?.value || 'Referências',
        role: $('refs-role')?.value || '',
      }),
    })).json();
    const c = data.counts || {};
    if (msg) msg.textContent = `✓ Importadas: ${c.importado || 0} · duplicadas ignoradas: ${c.duplicado || 0} · falhas: ${c.falhou || 0}`;
    const labels = { importado: '✓ importada', duplicado: '○ duplicada (ignorada)', falhou: '⚠ falhou' };
    for (const r of data.results || []) {
      out?.append(el('small', `${labels[r.status] || r.status}: ${r.input || ''}${r.reason ? ' — ' + r.reason : ''}`), document.createElement('br'));
    }
    if ((c.importado || 0) > 0 && $('refs-text')) $('refs-text').value = '';
    await loadLibrary();
  } catch (e) { if (msg) msg.textContent = e.message; }
  finally { btn.disabled = false; }
});

// Fase 2: Modal de Resumo de Triagem & PRISMA (calculado da Única Fonte de Verdade da Biblioteca).
$('open-prisma-summary')?.addEventListener('click', async () => {
  const back = document.createElement('div'); back.className = 'modal-backdrop';
  back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true');
  const box = document.createElement('div'); box.className = 'modal-box study-modal-box';
  const head = document.createElement('div'); head.className = 'modal-head';
  head.append(el('strong', 'Resumo de Triagem & Funil PRISMA (Biblioteca)'));
  const close = () => back.remove();
  const closeX = el('button', '✕', 'btn alt'); closeX.type = 'button'; closeX.addEventListener('click', close);
  head.append(closeX);
  const body = document.createElement('div'); body.className = 'modal-body';
  body.textContent = 'Calculando resumo diretamente da sua Biblioteca…';
  const foot = document.createElement('div'); foot.className = 'modal-foot';
  const fBtn = el('button', 'Fechar', 'btn alt'); fBtn.type = 'button'; fBtn.addEventListener('click', close);
  foot.append(fBtn); box.append(head, body, foot); back.append(box);
  back.addEventListener('click', (e) => { if (e.target === back) close(); });
  document.body.append(back);
  try {
    const d = await (await request('/library/prisma-summary')).json();
    body.replaceChildren();
    body.append(el('p', 'Números calculados ao vivo diretamente da lista ativa da sua Biblioteca — sem divergência entre telas.', 'subtle'));
    const stats = document.createElement('div');
    stats.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:10px 0';
    for (const [lbl, val] of [
      ['Identificados', d.total_identificados],
      ['Únicos (est.)', d.unicos_estimados],
      ['A ler', d.triagem?.a_ler ?? 0],
      ['Lidos', d.triagem?.lido ?? 0],
      ['Incluídos', d.triagem?.incluido ?? 0],
      ['Descartados', d.triagem?.descartado ?? 0],
      ['Fichamentos', d.fichamentos_total ?? 0],
      ['Sustentação ✓', d.sustentacao_conferida ?? 0],
    ]) {
      const c = document.createElement('div');
      c.style.cssText = 'border:1px solid var(--border-main);border-radius:10px;padding:10px;background:var(--bg-subtle);text-align:center';
      const n = el('div', String(val)); n.style.cssText = 'font-size:1.35rem;font-weight:750;color:var(--mpie-blue-text)';
      const s = el('div', lbl, 'subtle'); s.style.fontSize = '.75rem';
      c.append(n, s); stats.append(c);
    }
    body.append(stats);
    const roles = d.por_papel || {};
    const roleLine = el('p', `Distribuição por papel: Marco Teórico (${roles.marco_teorico || 0}) · Método (${roles.metodo || 0}) · Evidência (${roles.evidencia || 0}) · Contraponto (${roles.contraponto || 0}) · Sem papel (${roles.sem_papel || 0}).`, 'subtle');
    body.append(roleLine);
    if ((d.motivos_descarte || []).length) {
      body.append(el('strong', 'Motivos de descarte registrados'));
      const ul = document.createElement('ul');
      for (const m of d.motivos_descarte) ul.append(el('li', `${m.motivo}: ${m.quantidade}`));
      body.append(ul);
    }
    body.append(el('strong', 'Texto pronto para a seção de Metodologia / Revisão'));
    const txtBox = el('div', d.resumo_metodologico || '', 'abnt-preview');
    body.append(txtBox);
    const bar = document.createElement('div'); bar.className = 'actions';
    const copyMsg = el('span', '', 'subtle');
    const cBtn = el('button', 'Copiar resumo PRISMA', 'btn'); cBtn.type = 'button';
    cBtn.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(d.resumo_metodologico || ''); copyMsg.textContent = '✓ Copiado!'; }
      catch (_) { copyMsg.textContent = 'Selecione o texto acima para copiar.'; }
    });
    bar.append(cBtn, copyMsg);
    body.append(bar);
  } catch (e) { body.textContent = 'Não foi possível gerar o resumo: ' + e.message; }
});

// Fase 1: Modal limpo de exportação ABNT / BibTeX / RIS (compatível com Zotero e Overleaf).
$('open-export-refs')?.addEventListener('click', () => {
  const back = document.createElement('div'); back.className = 'modal-backdrop';
  back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true');
  const box = document.createElement('div'); box.className = 'modal-box';
  const head = document.createElement('div'); head.className = 'modal-head';
  head.append(el('strong', 'Exportar Referências da Biblioteca'));
  const close = () => back.remove();
  const body = document.createElement('div'); body.className = 'modal-body';
  body.append(el('p', 'Exporte todas as obras com ficha bibliográfica da sua biblioteca em padrão ABNT (NBR 6023:2018), BibTeX (.bib) ou RIS (.ris — compatível com Zotero e Mendeley).', 'subtle'));
  const chkLbl = document.createElement('label'); chkLbl.style.cssText = 'display:inline-flex;align-items:center;gap:8px;margin:8px 0';
  const chkInc = document.createElement('input'); chkInc.type = 'checkbox';
  chkLbl.append(chkInc, document.createTextNode('Exportar somente fontes marcadas como "Incluído no projeto"'));
  body.append(chkLbl);
  const st = el('p', '', 'subtle'); body.append(st);
  const row = document.createElement('div'); row.className = 'actions';
  const runExport = async (fmt, filename) => {
    st.textContent = 'Gerando arquivo…';
    try {
      const q = `/library/export?fmt=${fmt}${chkInc.checked ? '&only_included=true' : ''}`;
      await downloadPath(q, filename);
      st.textContent = `✓ ${filename} baixado.`;
    } catch (e) { st.textContent = e.message; }
  };
  const bAbnt = el('button', 'Lista ABNT (.txt)', 'btn'); bAbnt.type = 'button';
  bAbnt.addEventListener('click', () => runExport('abnt', 'referencias_abnt.txt'));
  const bBib = el('button', 'BibTeX (.bib)', 'btn alt'); bBib.type = 'button';
  bBib.addEventListener('click', () => runExport('bib', 'referencias_scriptorium.bib'));
  const bRis = el('button', 'RIS / Zotero (.ris)', 'btn alt'); bRis.type = 'button';
  bRis.addEventListener('click', () => runExport('ris', 'referencias_scriptorium.ris'));
  row.append(bAbnt, bBib, bRis);
  body.append(row);
  const foot = document.createElement('div'); foot.className = 'modal-foot';
  const fBtn = el('button', 'Fechar', 'btn alt'); fBtn.type = 'button'; fBtn.addEventListener('click', close);
  foot.append(fBtn); box.append(head, body, foot); back.append(box);
  back.addEventListener('click', (e) => { if (e.target === back) close(); });
  document.body.append(back); fBtn.focus();
});

// Importação de PDFs de acesso aberto por DOI ou link.
$('oa-import').addEventListener('click', async () => {
  const items = $('oa-items').value.split(/\n+/).map(x => x.trim()).filter(Boolean);
  if (!items.length) { $('oa-message').textContent = 'Cole ao menos um DOI ou link.'; return; }
  if (items.length > 30) { $('oa-message').textContent = 'Máximo de 30 por vez.'; return; }
  const btn = $('oa-import'); btn.disabled = true; $('oa-results').replaceChildren();
  $('oa-message').textContent = `Importando ${items.length} item(ns); pode levar alguns minutos...`;
  try {
    const data = await (await request('/library/import-open-access', {method: 'POST',
      body: JSON.stringify({items, collection: $('oa-collection').value || 'Acesso aberto'})})).json();
    const c = data.counts || {};
    $('oa-message').textContent = `Importados: ${c.importado || 0} · já existiam: ${c.ja_existia || 0} · sem PDF aberto: ${c.sem_pdf_aberto || 0} · retidos: ${c.retido || 0} · falharam: ${c.falhou || 0}`;
    const labels = {importado: '✓ importado', ja_existia: 'já estava na biblioteca', sem_pdf_aberto: 'sem PDF aberto', retido: '⚠ retido na verificação', falhou: '⚠ falhou'};
    for (const r of data.results || []) {
      $('oa-results').append(el('small', `${labels[r.status] || r.status}: ${r.library_item ? r.library_item.name : r.item}${r.reason ? ' (' + r.reason + ')' : ''}`));
      $('oa-results').append(document.createElement('br'));
    }
    await loadLibrary();
  } catch (e) { $('oa-message').textContent = e.message; }
  finally { btn.disabled = false; }
});

// M03/M21: busca no conteúdo já lido e ficha de leitura de cada documento.
async function showReadingCard(itemId, holder) {
  const old = holder.querySelector('.reading-card');
  if (old) { old.remove(); return; }
  const box = document.createElement('section'); box.className = 'scientific-audit-report reading-card';
  box.textContent = 'Carregando ficha...'; holder.append(box);
  try {
    const c = await (await request(`/library/items/${itemId}/card`)).json();
    box.replaceChildren();
    box.append(el('strong', 'Ficha de leitura: ' + (c.item.name || '')));
    box.append(el('p', `${c.pages_total ?? '?'} página(s) · ${c.chunks} trecho(s) · ${c.characters} caracteres · parser ${c.parser_version || '?'}`));
    const m = c.metadata || {};
    if (m.author || m.pdf_title) box.append(el('p', `Metadados do PDF: ${m.author || 'autor não informado'}${m.pdf_title ? ' · ' + m.pdf_title : ''}`));
    if ((c.structure || []).length) { box.append(el('h4', 'Estrutura')); for (const h of c.structure.slice(0, 20)) box.append(el('small', h)); }
    if ((c.frequent_terms || []).length) box.append(el('p', 'Termos frequentes: ' + c.frequent_terms.join(', ')));
    if (c.opening) { box.append(el('h4', 'Abertura')); box.append(el('small', c.opening)); }
    if ((c.ocr_pages_flagged || []).length) box.append(el('p', 'Páginas que precisam de OCR: ' + c.ocr_pages_flagged.join(', '), 'editorial-alert'));
    for (const lim of c.limitations || []) box.append(el('small', lim));
    if (API_MODE) {
      const gen = el('button', 'Fichamento com IA (usa sua chave Gemini)'); gen.type = 'button';
      gen.addEventListener('click', () => aiNotes(itemId, box, true));
      box.append(gen);
      aiNotes(itemId, box, false);
    }
  } catch (e) { box.textContent = e.message; }
}
async function runContentSearch() {
  const q = $('content-search').value.trim();
  const out = $('content-search-results'); const msg = $('content-search-message');
  if (q.length < 2) { msg.textContent = 'Digite ao menos uma palavra.'; return; }
  msg.textContent = 'Buscando...'; out.replaceChildren();
  try {
    const data = await (await request('/library/search?q=' + encodeURIComponent(q))).json();
    msg.textContent = `${data.results.length} resultado(s) · ${data.indexed_documents} de ${data.active_documents} documento(s) indexado(s).`;
    if (!data.results.length) out.append(el('small', data.note));
    for (const r of data.results) {
      const d = document.createElement('div'); d.className = 'reference-item';
      d.append(el('p', `${r.name}${r.pages ? ' · p. ' + r.pages : ''}${r.heading ? ' · ' + r.heading : ''}`));
      d.append(el('small', r.snippet));
      const b = el('button', 'Ficha do documento'); b.type = 'button';
      b.addEventListener('click', () => showReadingCard(r.item_id, d));
      d.append(b); out.append(d);
    }
  } catch (e) { msg.textContent = e.message; }
}
$('content-search-run').addEventListener('click', runContentSearch);
$('content-search').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); runContentSearch(); } });

$('new-paper').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button=$('submit'); button.disabled=true; $('submit-status').textContent='Salvando e iniciando...';
  try {
    if (!accountAccess?.research_generation_enabled) {
      $('submit-status').textContent = 'Primeiro conecte e verifique sua chave Gemini.';
      return;
    }
    if ($('model').value === 'gemini-3.1-pro-preview' && accountAccess.model_access?.status !== 'admin_vertex') {
      if (!window.confirm('A pesquisa vai usar Gemini Pro com sua chave. O Google poderá cobrar o uso da API no projeto dessa chave. Deseja continuar?')) {
        $('submit-status').textContent = 'Pesquisa não iniciada.';
        return;
      }
    }
    const payload = {
      title:$('title').value, idea:$('idea').value,
      experimental_log:$('log').value, template:$('template').value,
      model:$('model').value,
      reflection_model:$('reflection-model').value || null,
      language:$('language').value,
      source_ids:[...selectedSourceIds],
      context_size: contextSize(),
      plotting:$('plotting').checked,
      neon_review:$('neon-review').checked,
      preflight:$('preflight').checked,
      work_type: $('work-type').value,
      // M11 / IN IFRS 16/2026, Art. 9º
      unpublished_data: document.querySelector('input[name="unpublished-data"]:checked')?.value === 'sim',
      paid_tier_confirmed: $('paid-tier').checked,
      deidentified_confirmed: $('deidentified').checked
    };
    if (!document.querySelector('input[name="unpublished-data"]:checked')) {
      $('submit-status').textContent = 'Informe se o material tem dados inéditos ou sensíveis (IN IFRS 16/2026, Art. 9º).';
      return;
    }
    if (payload.source_ids.length > CONTEXT_LIMITS[payload.context_size].sources) {
      $('submit-status').textContent = `Máximo de ${CONTEXT_LIMITS[payload.context_size].sources} fontes no contexto ${payload.context_size}.`;
      return;
    }
    if (payload.preflight && !payload.source_ids.length) {
      $('submit-status').textContent = 'Selecione ao menos uma fonte da biblioteca para o diagnóstico.';
      return;
    }
    await request('/jobs', {method:'POST',body:JSON.stringify(payload)});
    $('submit-status').textContent = payload.preflight
      ? 'Diagnóstico enviado. Quando terminar, aprove as fontes no histórico para iniciar a redação.'
      : 'Pesquisa enviada. Você pode fechar o navegador.';
    $('new-paper').reset();$('unpublished-confirm').classList.add('hidden');applyModelAccess();selectedSourceIds.clear();updateSelectedCount();displayLibrary();await loadJobs();
  } catch (e) { $('submit-status').textContent=e.message; }
  finally {button.disabled = !accountAccess?.research_generation_enabled;}
});

let accountAccess = null;

// Sempre uma interface: o backend declara quais modelos a chave realmente permitiu
// no último teste. Nenhuma opção paga é exibida por mera presença da chave.
function applyModelAccess() {
  const allowed = new Set(accountAccess?.allowed_models || []);
  for (const id of ['model', 'reflection-model']) {
    const select = $(id);
    for (const option of select.options) {
      if (!option.value) continue; // "Mesmo modelo da redação"
      const visible = allowed.has(option.value);
      option.disabled = !visible;
      option.hidden = !visible;
    }
  }
  const pro = 'gemini-3.1-pro-preview', flash = 'gemini-3-flash-preview';
  const best = allowed.has(pro) ? pro : (allowed.has(flash) ? flash : '');
  $('model').value = best;
  $('reflection-model').value = '';
  // O modelo de imagem usado pelo worker é diferente do Pro textual;
  // não presumir que a chave possa criar imagens só porque gera texto Pro.
  // Só a exceção "IA pelo projeto" (ou a API anterior) libera gráficos; com chave
  // pessoal o modelo de imagem ainda não é testado na verificação da chave.
  const projectAi = accountAccess?.model_access?.status === 'admin_vertex' || !!accountAccess?.legacy_backend;
  const canPlot = projectAi;
  $('plotting').checked = canPlot && $('plotting').checked;
  $('plotting').disabled = !canPlot;
  $('plotting').closest('.switch-row')?.classList.toggle('hidden', !canPlot);
  const message = $('model-access-summary');
  if (projectAi) {
    message.textContent = 'Modelos pelo projeto do Scriptorium (exceção ou API anterior).';
  } else if (allowed.has(pro)) {
    message.textContent = 'Sua chave foi testada: modelo avançado disponível. O uso pode gerar custos na sua conta Google.';
  } else if (allowed.has(flash)) {
    message.textContent = 'Modelo econômico disponível. Os modelos avançados não aparecem nesta conta.';
  } else {
    message.textContent = 'Nenhum modelo confirmado. Conecte ou confira sua chave Gemini em Minha conta.';
  }
}

async function loadAccessRequests() {
  if (!accountAccess?.admin) return;
  const holder = $('pending-access-list');
  holder.textContent = 'Consultando solicitações...';
  try {
    const response = await request('/admin/access-requests');
    const data = await response.json();
    holder.replaceChildren();
    if (!(data.items || []).length) {
      holder.textContent = 'Nenhuma solicitação de acesso pendente.';
      return;
    }
    for (const item of data.items) {
      const entry = document.createElement('div');
      entry.className = 'access-request-entry';
      const text = document.createElement('span');
      text.textContent = item.email;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn';
      button.textContent = 'Autorizar';
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          await request('/admin/access-requests/' + encodeURIComponent(item.id) + '/approve',
            {method: 'POST'});
          $('account-message').textContent = 'Acesso autorizado para ' + item.email + '.';
          await loadAccessRequests();
        } catch (error) {
          $('account-message').textContent = 'Não foi possível autorizar: ' + error.message;
          button.disabled = false;
        }
      });
      entry.append(text, button);
      holder.append(entry);
    }
  } catch (error) {
    holder.textContent = 'Não foi possível consultar solicitações: ' + error.message;
  }
}
$('refresh-access-requests').addEventListener('click', loadAccessRequests);
$('request-invitation').addEventListener('click', async () => {
  const button = $('request-invitation');
  button.disabled = true;
  $('pending-help').textContent = 'Enviando solicitação...';
  try {
    await request('/account/request-access', {method: 'POST'});
    $('pending-help').textContent = 'Solicitação registrada. Após a autorização do administrador, toque em "Já fui autorizado".';
  } catch (error) {
    $('pending-help').textContent = 'Não foi possível registrar automaticamente. Use a opção de copiar mensagem. (' + error.message + ')';
  } finally {
    button.disabled = false;
  }
});

// "Minha conta" fica atrás do botão do cabeçalho. No primeiro acesso (aguardando
// autorização ou sem chave) o painel continua na página, porque é o único passo possível.
function setAccountPanelOpen(open) {
  const panel = $('account-panel');
  panel.classList.toggle('open', open && panel.classList.contains('as-modal'));
  const shown = panel.classList.contains('open');
  $('account-backdrop').classList.toggle('hidden', !shown);
  $('account-button').setAttribute('aria-expanded', String(shown));
  if (shown) { panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); $('account-close').focus(); }
  else { panel.removeAttribute('role'); panel.removeAttribute('aria-modal'); }
}
function updateAccountMode() {
  const ws = $('workspace');
  const firstAccess = ws.classList.contains('access-pending') || ws.classList.contains('access-setup');
  const panel = $('account-panel');
  const wasOpen = panel.classList.contains('open');
  panel.classList.toggle('as-modal', !firstAccess);
  setAccountPanelOpen(!firstAccess && wasOpen);
  const state = $('account-state').textContent || '';
  const dot = $('account-dot');
  const ok = canWork();
  dot.classList.toggle('ok', ok);
  dot.classList.toggle('warn', !ok);
  $('account-button').title = 'Minha conta · ' + state;
  $('account-button').setAttribute('aria-label', 'Minha conta: ' + state);
}
$('account-button').addEventListener('click', () => {
  const panel = $('account-panel');
  if (!panel.classList.contains('as-modal')) { panel.scrollIntoView({behavior: 'smooth', block: 'start'}); return; }
  setAccountPanelOpen(!panel.classList.contains('open'));
});
$('account-close').addEventListener('click', () => { setAccountPanelOpen(false); $('account-button').focus(); });
$('account-backdrop').addEventListener('click', () => setAccountPanelOpen(false));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && $('account-panel').classList.contains('open')) { setAccountPanelOpen(false); $('account-button').focus(); }
});

function applyAccountAccessUi(access) {
  accountAccess = access;
  $('workspace').classList.remove('access-pending', 'access-setup');
  const noCredit = accountAccess.model_access?.billing_alert?.state === 'prepay_depleted';
  const keyState = accountAccess.model_access?.status === 'admin_vertex' ? 'IA pelo projeto (exceção)' :
    noCredit ? 'Chave sem saldo pré-pago' :
    (accountAccess.byok_ready ?
      (accountAccess.model_access?.status === 'verified' ? 'Chave Gemini verificada' : 'Verifique sua chave') :
      'Conecte sua chave Gemini');
  $('account-state').textContent = (accountAccess.admin ? 'Administrador · ' : '') + (API_MODE ? keyState : 'Acesso liberado');
  $('admin-invitations').classList.toggle('hidden', !accountAccess.admin);
  $('guest-credential').classList.toggle('hidden', accountAccess.model_access?.status === 'admin_vertex');
  const guestReady = !!accountAccess.byok_ready;
  const guestVerified = guestReady && accountAccess.model_access?.status === 'verified';
  const hasModels = !!accountAccess.research_generation_enabled;
  $('workspace').classList.toggle('access-setup', API_MODE && !hasModels);
  $('gemini-setup-details').open = !guestVerified;
  $('gemini-setup-title').textContent = guestReady
    ? 'Gerenciar ou trocar minha chave Gemini'
    : 'Conectar minha chave Gemini — primeiro acesso';
  $('gemini-key-ready').classList.toggle('hidden', !guestVerified);
  $('remove-personal-key').classList.toggle('hidden', !guestReady);
  $('submit').disabled = !hasModels;
  $('account-message').textContent = accountAccess.model_access?.status === 'admin_vertex' ? '' :
    noCredit ? 'O Google recusou a última execução por falta de saldo pré-pago na sua chave (erro 402). Adicione créditos no Google AI Studio, em Faturamento; o aviso some na próxima execução que funcionar ou se você cadastrar a chave de novo.' :
    (guestVerified ? '' : (guestReady
      ? 'Sua chave foi cadastrada, mas ainda não há um modelo confirmado. Confira a chave abaixo.'
      : 'Para começar, conecte sua chave Gemini seguindo as instruções.'));
  if (!API_MODE) $('account-message').textContent = '';
  applyModelAccess();
}

async function fetchAccountAccessWithRetry() {
  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 18000);
    try {
      const response = await request('/account/access', { signal: controller.signal });
      clearTimeout(timeout);
      return await response.json();
    } catch (error) {
      clearTimeout(timeout);
      lastError = error;
      if (error?.status === 401 || error?.status === 403 || error?.status === 404) throw error;
    }
  }
  throw lastError;
}

async function loadAccountAccess(cachedAccess = null) {
  $('account-panel').classList.remove('hidden');
  $('access-pending').classList.add('hidden');
  $('legacy-api-notice').classList.add('hidden');
  $('pending-email').textContent = user?.email || '';
  $('pending-help').textContent = '';
  if (cachedAccess) {
    // Sessão em cache: libera a tela de imediato e revalida em segundo plano.
    applyAccountAccessUi(cachedAccess);
    updateAccountMode();
  } else {
    $('workspace').classList.remove('access-setup');
    $('workspace').classList.add('access-pending');
    $('guest-credential').classList.add('hidden');
    $('admin-invitations').classList.add('hidden');
    $('submit').disabled = true;
    $('account-state').textContent = 'Verificando...';
  }
  try {
    const fresh = await fetchAccountAccessWithRetry();
    applyAccountAccessUi(fresh);
    writeSessionCache(user, fresh);
    if (accountAccess.admin) { loadAccessRequests(); if (API_MODE) loadRetrievalEval(); }
  } catch (error) {
    // Se já havia acesso em cache e houve apenas lentidão/falha de rede, mantém a tela usable.
    if (cachedAccess && error?.status !== 403 && error?.status !== 401) {
      $('account-message').textContent = 'Conexão lenta com o servidor; mostrando os dados salvos neste aparelho.';
      updateAccountMode();
      return;
    }
    accountAccess = null;
    if (error?.status === 404) {
      try {
        await request('/capabilities');
        accountAccess = {
          admin: true, byok_ready: false, multiuser_enabled: false,
          research_generation_enabled: true, legacy_backend: true,
          allowed_models: ['gemini-3-flash-preview', 'gemini-3.1-pro-preview']
        };
        $('workspace').classList.remove('access-pending');
        applyModelAccess();
        $('account-state').textContent = 'Administrador · API anterior';
        $('account-message').textContent = 'As pesquisas existentes continuam acessíveis.';
        $('legacy-api-notice').classList.remove('hidden');
        $('admin-invitations').classList.add('hidden');
        $('submit').disabled = false;
        return;
      } catch (legacyError) {
        error = legacyError;
      }
    }
    const timedOut = error?.name === 'AbortError' || error?.name === 'TimeoutError';
    const awaitingAuthorization = error?.status === 403;
    if (awaitingAuthorization) clearSessionCache(user?.uid);
    $('account-state').textContent = timedOut ? 'Conexão indisponível' :
      (awaitingAuthorization ? 'Aguardando autorização' : 'Verificação falhou');
    $('account-message').textContent = awaitingAuthorization
      ? 'A conta Google está conectada, mas o Scriptorium ainda não liberou seu acesso.'
      : (timedOut
        ? 'O servidor demorou para responder. Toque em "Já fui autorizado" para tentar novamente.'
        : 'Não foi possível confirmar sua conta: ' + (error?.message || 'erro inesperado'));
    $('workspace').classList.add('access-pending');
    $('access-pending').classList.remove('hidden');
    $('workspace').classList.remove('access-setup');
    $('submit').disabled = true;
    accountAccess = null;
  } finally {
    updateAccountMode();
  }
}

// O navegador não recebe permissão para criar ou ler automaticamente chaves do AI Studio.
// Somente uma interação explícita permite ler do clipboard, e nada vai para localStorage.
$('paste-personal-key').addEventListener('click', async () => {
  const field = $('personal-gemini-key');
  try {
    if (!navigator.clipboard?.readText) throw new Error('clipboard_unavailable');
    const value = (await navigator.clipboard.readText()).trim();
    if (!/^[A-Za-z0-9_.-]{20,512}$/.test(value)) {
      $('key-setup-result').textContent =
        'O conteúdo copiado não parece ser uma chave Gemini. Confira no Google AI Studio.';
      return;
    }
    field.value = value;
    field.type = 'password';
    $('toggle-personal-key').textContent = 'Mostrar';
    $('toggle-personal-key').setAttribute('aria-pressed', 'false');
    $('key-setup-result').textContent = 'Chave colada. Revise e clique em Salvar.';
  } catch (_) {
    $('key-setup-result').textContent =
      'Seu navegador não permitiu a colagem automática. Toque no campo e use Colar.';
    field.focus();
  }
});
$('toggle-personal-key').addEventListener('click', () => {
  const field = $('personal-gemini-key');
  const visible = field.type === 'password';
  field.type = visible ? 'text' : 'password';
  $('toggle-personal-key').textContent = visible ? 'Ocultar' : 'Mostrar';
  $('toggle-personal-key').setAttribute('aria-pressed', String(visible));
});
$('copy-access-request').addEventListener('click', async () => {
  const message = 'Olá! Solicito um convite para usar o Scriptorium MPIE. Minha conta Google é: '
    + (user?.email || '(e-mail da conta)') + '.';
  try {
    await navigator.clipboard.writeText(message);
    $('pending-help').textContent = 'Pedido copiado. Envie a mensagem ao administrador.';
  } catch (_) {
    window.prompt('Copie e envie esta mensagem ao administrador:', message);
    $('pending-help').textContent = 'Envie o pedido ao administrador para autorizar sua conta.';
  }
});
$('retry-access').addEventListener('click', async () => {
  if (!user) return;
  await loadAccountAccess();
  if (canWork()) {
    await Promise.all([loadJobs(), loadLibrary(), loadCapabilities(), loadAdvisor(), loadMcp()]);
    syncSmartPolling();
  }
});

$('save-personal-key').addEventListener('click', async () => {
  const button = $('save-personal-key');
  const key = $('personal-gemini-key').value.trim();
  if (!/^[A-Za-z0-9_.-]{20,512}$/.test(key)) {
    $('key-setup-result').textContent =
      'Cole uma chave válida do Google AI Studio antes de salvar.';
    return;
  }
  button.disabled = true;
  $('key-setup-result').textContent = 'Salvando chave no cofre seguro...';
  try {
    $('key-setup-result').textContent = 'Verificando com o Google quais modelos sua chave pode usar...';
    const result = await request('/account/credential', {
      method:'PUT', body: JSON.stringify({key})
    });
    const saved = await result.json();
    $('personal-gemini-key').value = '';
    $('personal-gemini-key').type = 'password';
    $('toggle-personal-key').textContent = 'Mostrar';
    $('toggle-personal-key').setAttribute('aria-pressed','false');
    await loadAccountAccess();
    if (canWork()) {
      await Promise.all([loadJobs(),loadLibrary(),loadCapabilities(),loadAdvisor(),loadMcp()]);
    }
    const models = saved.model_access?.models || {};
    const hasPro = models['gemini-3.1-pro-preview'] === 'supported';
    const hasFlash = models['gemini-3-flash-preview'] === 'supported';
    $('key-setup-result').textContent = hasPro ?
      'Conexão concluída. Seu modelo avançado está disponível!' :
      (hasFlash ? 'Conexão concluída. Você já pode pesquisar com o modelo econômico.' :
        (Object.values(models).includes('no_credit')
          ? 'Chave cadastrada, mas o projeto dela está sem saldo de créditos pré-pagos (erro 402). Adicione créditos no Google AI Studio, em Faturamento, ou use uma chave de um projeto sem faturamento (nível gratuito, só com material público).'
          : 'Chave cadastrada, mas o Google não liberou os modelos testados. Confira os limites da conta.'));
  } catch(error) {
    $('key-setup-result').textContent = 'Não foi possível salvar a chave: ' + error.message;
  } finally { button.disabled = false; }
});
$('remove-personal-key').addEventListener('click', async () => {
  if (!window.confirm('Revogar sua chave de IA? Novas pesquisas serão bloqueadas.')) return;
  try {
    await request('/account/credential',{method:'DELETE'});
    $('personal-gemini-key').value = '';
    await loadAccountAccess();
  } catch(error) { $('account-message').textContent = error.message; }
});
async function changeInvite(revoke) {
  const email = $('invitation-email').value.trim();
  if (!email) { $('account-message').textContent='Informe um e-mail.';return; }
  try {
    await request(revoke ? '/admin/invitations/'+encodeURIComponent(email) : '/admin/invitations', {
      method: revoke ? 'DELETE' : 'POST',
      ...(revoke ? {} : {body:JSON.stringify({email})})
    });
    $('account-message').textContent = revoke ? 'Acesso revogado.' : 'Convite registrado. A pessoa já pode acessar com o Google.';
    $('invitation-email').value = '';
  } catch(error) { $('account-message').textContent = error.message; }
}
$('invite-researcher').addEventListener('click', () => changeInvite(false));
$('revoke-researcher').addEventListener('click', () => changeInvite(true));

$('retry-api-version').addEventListener('click', async () => {
  if (!user) return;
  const button = $('retry-api-version');
  button.disabled = true;
  try {
    await loadAccountAccess();
    if (canWork() && (API_MODE ? !accountAccess.legacy_backend : true)) {
      await Promise.all([loadJobs(), loadLibrary(), loadCapabilities(), loadAdvisor(), loadMcp()]);
      syncSmartPolling();
    }
  } finally {
    button.disabled = false;
  }
});

let authInitialized = false;
if (typeof auth.authStateReady === 'function') {
  auth.authStateReady().then(() => {
    authInitialized = true;
    $('session-restoring')?.classList.add('hidden');
    if (!auth.currentUser) {
      clearSessionCache();
      $('login-panel').classList.remove('hidden');
    }
  }).catch(() => {
    authInitialized = true;
    $('session-restoring')?.classList.add('hidden');
  });
}

// Onda 3: glossário contextual inline, tour acolhedor de 3 passos e visão pública para orientação.
const INLINE_GLOSSARY = {
  doi: 'DOI (Identificador Digital de Objeto): é como o "CPF" de um artigo científico (ex.: 10.1590/...). Quando existe, o Scriptorium busca os dados oficiais automaticamente sem erros.',
  bibtex: 'BibTeX (.bib): é um arquivo simples de texto que guarda os dados das referências (autor, título, ano, revista) para montar a bibliografia ABNT automaticamente.',
  parafrase: 'Paráfrase é explicar a ideia do autor com as suas próprias palavras (mantendo a citação). Citação direta copia o trecho entre aspas, palavra por palavra.',
  proveniencia: 'Proveniência: é o relatório transparente que comprova quais fontes sustentam o texto e se houve revisão em conversa independente — muito útil para a orientação e a banca.',
  word: 'Word (.docx): arquivo editável em padrão ABNT (Times New Roman 12, espaçamento 1,5) para seu orientador comentar com Controle de Alterações no Word ou Google Docs.',
};
for (const btn of document.querySelectorAll('[data-glossary]')) {
  btn.addEventListener('click', () => {
    const pop = $('glossary-pop'); if (!pop) return;
    const key = btn.dataset.glossary;
    const isSame = btn.getAttribute('aria-expanded') === 'true';
    for (const b of document.querySelectorAll('[data-glossary]')) b.setAttribute('aria-expanded', 'false');
    if (isSame) { pop.classList.add('hidden'); return; }
    btn.setAttribute('aria-expanded', 'true');
    pop.textContent = INLINE_GLOSSARY[key] || '';
    pop.classList.remove('hidden');
  });
}
function syncWelcomeTour(uid) {
  const tour = $('welcome-tour'); if (!tour || !uid) return;
  try {
    const seen = localStorage.getItem('scriptorium_tour_seen_' + uid) === '1';
    tour.classList.toggle('hidden', seen);
  } catch (_) {}
}
$('welcome-tour-dismiss')?.addEventListener('click', () => {
  $('welcome-tour')?.classList.add('hidden');
  if (user?.uid) { try { localStorage.setItem('scriptorium_tour_seen_' + user.uid, '1'); } catch (_) {} }
});

async function loadAdvisorShareView() {
  const token = new URLSearchParams(location.search).get('orientacao');
  if (!token) return false;
  const view = $('advisor-share-view'), body = $('adv-view-body');
  if (!view || !body) return false;
  view.classList.remove('hidden');
  $('login-panel')?.classList.add('hidden');
  $('workspace')?.classList.add('hidden');
  $('session-restoring')?.classList.add('hidden');
  $('adv-view-print')?.addEventListener('click', () => window.print());
  try {
    const res = await fetch('/api/orientacao/' + encodeURIComponent(token));
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      $('adv-view-title').textContent = 'Link indisponível';
      body.textContent = err.detail || 'Este link de orientação expirou ou foi revogado pelo estudante.';
      return true;
    }
    const d = await res.json();
    $('adv-view-title').textContent = d.titulo || 'Trabalho acadêmico';
    $('adv-view-meta').textContent = `${d.tipo || 'Texto acadêmico'} · ${d.modo_pedagogico_rotulo || 'Tutor Socrático'} · ${d.pdf_final ? 'Versão final (todas as travas aprovadas)' : 'Em elaboração / rascunho'} · link válido até ${new Date(d.expira_em).toLocaleDateString('pt-BR')}`;
    body.replaceChildren();
    if (d.nota_estudante) {
      const note = document.createElement('div'); note.className = 'advisor-box'; note.style.marginBottom = '14px';
      note.append(el('strong', 'Recado / dúvida do estudante: '), document.createTextNode(d.nota_estudante));
      body.append(note);
    }
    if (d.pergunta) {
      body.append(el('h3', 'Pergunta e recorte do trabalho'), el('p', d.pergunta));
    }
    if ((d.etapas || []).length) {
      body.append(el('h3', 'Andamento das etapas'));
      const ul = document.createElement('ul');
      for (const e of d.etapas) {
        ul.append(el('li', `${e.status === 'aceita' ? '✓' : '○'} ${e.titulo}${e.independencia === 'outra_ia' ? ' (revisado por outra IA)' : ''}`));
      }
      body.append(ul);
    }
    if ((d.provas || []).length) {
      body.append(el('h3', 'O que o Scriptorium conferiu'));
      const ul = document.createElement('ul');
      for (const p of d.provas) ul.append(el('li', p));
      body.append(ul);
    }
    body.append(el('h3', `Referências confirmadas (${(d.referencias_confirmadas || []).length})`));
    if ((d.referencias_confirmadas || []).length) {
      const ul = document.createElement('ul');
      for (const r of d.referencias_confirmadas) ul.append(el('li', `${r.autor ? r.autor + ' · ' : ''}${r.titulo || r.chave}${r.ano ? ' (' + r.ano + ')' : ''}`));
      body.append(ul);
    } else {
      body.append(el('p', 'Nenhuma referência confirmada ainda.', 'subtle'));
    }
    if ((d.referencias_pendentes || []).length) {
      body.append(el('h3', `Referências ainda pendentes de conferência (${d.referencias_pendentes.length})`));
      const ul = document.createElement('ul');
      for (const r of d.referencias_pendentes) ul.append(el('li', `${r.titulo || r.chave} (${r.nivel})`));
      body.append(ul);
    }

    // Fase 2: Comentários da orientação por etapa (sem necessidade de criar conta)
    const commSec = document.createElement('section');
    commSec.style.marginTop = '18px';
    commSec.append(el('h3', 'Apontamentos da orientação por etapa'));
    const commList = document.createElement('div');
    const kindLabels = { elogio: '✓ Elogio', sugestao: 'Sugestão', ajuste_obrigatorio: '⚠ Ajuste obrigatório' };
    const renderAdvComments = (items) => {
      commList.replaceChildren();
      if (!items.length) {
        commList.append(el('p', 'Nenhum apontamento registrado ainda. Deixe um comentário abaixo para o(a) estudante acompanhar no painel.', 'subtle'));
        return;
      }
      for (const c of items) {
        const card = document.createElement('div'); card.className = 'study-note-card';
        card.append(el('strong', `${c.author || 'Orientador(a)'} · ${c.stage || 'Geral'} · ${kindLabels[c.kind] || c.kind}${c.resolved ? ' · ✓ Resolvido pelo estudante' : ''}`));
        const p = el('p', c.text); p.style.margin = '6px 0 0';
        card.append(p);
        commList.append(card);
      }
    };
    const commentsState = [...(d.comentarios || [])];
    renderAdvComments(commentsState);

    const form = document.createElement('div');
    form.className = 'advisor-box';
    form.style.marginTop = '12px';
    form.append(el('strong', 'Deixar apontamento para o(a) estudante'));
    const g = document.createElement('div'); g.className = 'study-grid'; g.style.marginTop = '8px';
    const inpName = document.createElement('input'); inpName.type = 'text'; inpName.maxLength = 80; inpName.placeholder = 'Seu nome (ex.: Prof.ª Maria)';
    const selStage = document.createElement('select');
    selStage.append(new Option('Geral (visão do trabalho)', 'Geral'));
    for (const e of (d.etapas || [])) selStage.append(new Option(e.titulo, e.titulo));
    const selKind = document.createElement('select');
    selKind.append(new Option('Sugestão', 'sugestao'), new Option('Ajuste obrigatório', 'ajuste_obrigatorio'), new Option('Elogio', 'elogio'));
    const w1 = document.createElement('div'); w1.append(el('label', 'Orientador(a)'), inpName);
    const w2 = document.createElement('div'); w2.append(el('label', 'Etapa'), selStage);
    g.append(w1, w2);
    const w3 = document.createElement('div'); w3.style.marginTop = '6px'; w3.append(el('label', 'Tipo de apontamento'), selKind);
    const txtArea = document.createElement('textarea'); txtArea.rows = 3; txtArea.maxLength = 1500;
    txtArea.placeholder = 'Escreva sua orientação objetiva para esta etapa…';
    const act = document.createElement('div'); act.className = 'actions';
    const sendBtn = el('button', 'Enviar apontamento', 'btn'); sendBtn.type = 'button';
    const sendMsg = el('span', '', 'subtle');
    sendBtn.addEventListener('click', async () => {
      if (txtArea.value.trim().length < 4) { sendMsg.textContent = 'Escreva pelo menos 4 caracteres.'; return; }
      sendBtn.disabled = true; sendMsg.textContent = 'Enviando…';
      try {
        const resp = await fetch('/api/orientacao/' + encodeURIComponent(token) + '/comentarios', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            autor: inpName.value.trim() || 'Orientador(a)',
            etapa: selStage.value,
            tipo: selKind.value,
            texto: txtArea.value.trim(),
          }),
        });
        const j = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(j.detail || 'Não foi possível enviar.');
        if (j.comentario) commentsState.push(j.comentario);
        renderAdvComments(commentsState);
        txtArea.value = '';
        sendMsg.textContent = '✓ Apontamento registrado! O estudante já verá no painel.';
      } catch (e) { sendMsg.textContent = e.message; }
      finally { sendBtn.disabled = false; }
    });
    act.append(sendBtn, sendMsg);
    form.append(g, w3, el('label', 'Comentário'), txtArea, act);
    commSec.append(commList, form);
    body.append(commSec);
  } catch (e) {
    $('adv-view-title').textContent = 'Não foi possível carregar';
    body.textContent = 'Verifique a conexão e tente recarregar a página.';
  }
  return true;
}
// Onda 4: avaliação ética do estudo piloto (TCLE + Escala SUS + Transferência sem IA)
let pilotItemsRendered = false;
function renderSusQuestions(items) {
  const host = $('pilot-sus-list'); if (!host || pilotItemsRendered) return;
  host.replaceChildren();
  (items || []).forEach((text, idx) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid var(--border-main);border-radius:10px;background:var(--bg-surface)';
    const lbl = document.createElement('label');
    lbl.htmlFor = `pilot-sus-${idx}`; lbl.style.cssText = 'margin:0;flex:1;min-width:220px;font-weight:500;font-size:0.86rem';
    lbl.textContent = `${idx + 1}. ${text}`;
    const sel = document.createElement('select');
    sel.id = `pilot-sus-${idx}`; sel.dataset.susIdx = String(idx); sel.style.width = 'auto'; sel.style.minWidth = '150px';
    for (const [val, label] of [['', 'Escolha (1 a 5)…'], ['1', '1 · Discordo totalmente'], ['2', '2 · Discordo'], ['3', '3 · Neutro'], ['4', '4 · Concordo'], ['5', '5 · Concordo totalmente']]) {
      const opt = document.createElement('option'); opt.value = val; opt.textContent = label; sel.append(opt);
    }
    row.append(lbl, sel);
    host.append(row);
  });
  pilotItemsRendered = true;
}

async function loadPilotStatus() {
  if (!user || !$('pilot-eval-details')) return;
  try {
    const d = await (await request('/piloto/meu-status')).json();
    renderSusQuestions(d.sus_itens || []);
    const st = $('pilot-eval-status'), wBtn = $('pilot-withdraw-btn');
    if (d.enviado) {
      if (st) st.textContent = `✓ Obrigado! Sua avaliação anônima (${d.versao_piloto}) foi registrada em ${new Date(d.enviado_em).toLocaleDateString('pt-BR')} · nota SUS: ${d.sus_score} (${d.sus_faixa}).`;
      wBtn?.classList.remove('hidden');
    } else {
      if (st) st.textContent = `Versão de referência em avaliação: ${d.versao_piloto}.`;
      wBtn?.classList.add('hidden');
    }
  } catch (_) {}
}

$('pilot-eval-details')?.addEventListener('toggle', e => { if (e.target.open) loadPilotStatus(); });
$('pilot-submit-btn')?.addEventListener('click', async () => {
  const msg = $('pilot-message'), btn = $('pilot-submit-btn');
  if (!$('pilot-tcle')?.checked) { msg.textContent = 'Marque o aceite do Termo de Consentimento (TCLE) antes de enviar.'; return; }
  const sus = [];
  for (let i = 0; i < 10; i++) {
    const v = Number($(`pilot-sus-${i}`)?.value || 0);
    if (v < 1 || v > 5) { msg.textContent = `Responda o item ${i + 1} da escala de facilidade de uso (1 a 5).`; return; }
    sus.push(v);
  }
  btn.disabled = true; msg.textContent = 'Enviando avaliação anônima…';
  try {
    const res = await (await request('/piloto/avaliacao', {
      method: 'POST',
      body: JSON.stringify({
        tcle_aceito: true,
        vinculo: $('pilot-vinculo')?.value || 'mestrado',
        familiaridade_digital: $('pilot-familiaridade')?.value || 'intermediaria',
        sus,
        o_que_ajudou: $('pilot-ajudou')?.value || '',
        o_que_dificultou: $('pilot-dificultou')?.value || '',
        percepcao_autoria: $('pilot-autoria')?.value || '',
        transferencia: {
          problema: $('pilot-tr-problema')?.value || '',
          pergunta: $('pilot-tr-pergunta')?.value || '',
          objetivo_geral: $('pilot-tr-objetivo')?.value || '',
          como_coletar: $('pilot-tr-coleta')?.value || '',
        },
      }),
    })).json();
    msg.textContent = `✓ Avaliação registrada (${res.codigo_anonimo}) · SUS: ${res.sus_score} (${res.sus_faixa}). Muito obrigado!`;
    await loadPilotStatus();
  } catch (e) { msg.textContent = e.message; }
  finally { btn.disabled = false; }
});
$('pilot-withdraw-btn')?.addEventListener('click', async () => {
  if (!window.confirm('Deseja retirar seu consentimento e apagar permanentemente sua avaliação do estudo piloto?')) return;
  try {
    await request('/piloto/avaliacao', { method: 'DELETE' });
    $('pilot-message').textContent = 'Consentimento retirado e avaliação apagada com sucesso.';
    await loadPilotStatus();
  } catch (e) { $('pilot-message').textContent = e.message; }
});
$('admin-pilot-csv')?.addEventListener('click', () => downloadFrom('/admin/piloto/resumo.csv', 'piloto_scriptorium_v1.0-piloto.csv'));

const IS_ADVISOR_SHARE = new URLSearchParams(location.search).has('orientacao');
if (IS_ADVISOR_SHARE) { loadAdvisorShareView(); }

onAuthStateChanged(auth, async (current) => {
  if (IS_ADVISOR_SHARE) return;
  user = current;
  syncWelcomeTour(current?.uid);
  $('session-restoring')?.classList.add('hidden');
  // Guia de escrita: mesma conta do site; com login, a aba do guia substitui o botão do cabeçalho.
  window.ScriptoriumConta?.definir(current);
  document.body.classList.toggle('guest', !current);
  $('guide-button')?.classList.toggle('hidden', !!current);
  window.dispatchEvent(new CustomEvent('scriptorium:library-user-changed', {
    detail: { uid: current?.uid || null }
  }));
  const cachedSession = current ? readSessionCache() : null;
  const cachedAccess = (cachedSession && cachedSession.uid === current?.uid) ? cachedSession.access : null;
  if (user && !cachedAccess) $('workspace').classList.add('access-pending');
  $('login-panel').classList.toggle('hidden', !!user);
  $('workspace').classList.toggle('hidden', !user);
  $('logout').classList.toggle('hidden', !user);
  $('account-button').classList.toggle('hidden', !user);
  $('identity').textContent = user?.email || '';
  if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
  if (user) {
    // Pinta biblioteca e artigos salvos em cache imediatamente (sem esperar cold start).
    const cachedUi = readUiCache(user.uid);
    if (cachedUi) {
      if (Array.isArray(cachedUi.libraryItems) && cachedUi.libraryItems.length) {
        libraryItems = cachedUi.libraryItems;
        window.ScriptoriumBiblioteca?.definir(libraryItems);
        updateSelectedCount(); displayLibrary();
      }
      if (Array.isArray(cachedUi.mcpProjects) && cachedUi.mcpProjects.length) {
        renderMcpProjectsList(cachedUi.mcpProjects);
      }
    }
    await loadAccountAccess(cachedAccess);
    if (canWork()) {
      await Promise.all([loadJobs(), loadLibrary(), loadCapabilities(), loadAdvisor(), loadMcp()]);
      syncSmartPolling();
    }
  } else {
    lastJobsBusy = false;
    lastMcpBusy = false;
    stopSmartPolling();
    if (authInitialized) clearSessionCache();
    accountAccess = null;
    window.ScriptoriumProjetos?.definir([]);
    window.ScriptoriumBiblioteca?.definir([]);
    $('workspace').classList.remove('access-pending', 'access-setup');
    $('account-panel').classList.add('hidden');
    setAccountPanelOpen(false);
    $('access-pending').classList.add('hidden');
    $('guest-credential').classList.add('hidden');
    $('personal-gemini-key').value = '';
    $('personal-gemini-key').type = 'password';
    libraryItems = [];
    selectedSourceIds.clear();
    updateSelectedCount();
  }
});

// Gate G2 (M04): teste de busca no corpus de referência (só administrador).
let retrievalEvalTimer = null;
let retrievalEvalJob = null;
const EVAL_LABELS = {lexical: 'Palavras (BM25)', vector: 'Significado (embeddings)', hybrid: 'Híbrida (as duas)'};
function renderRetrievalEval(last) {
  const status = $('retrieval-eval-status');
  const box = $('retrieval-eval-result');
  box.replaceChildren();
  $('retrieval-eval-download').classList.add('hidden');
  retrievalEvalJob = last;
  if (!last) { status.textContent = 'Nenhum teste rodado ainda.'; return; }
  const active = ['queued', 'running'].includes(last.status);
  $('retrieval-eval-start').disabled = active;
  if (active) { status.textContent = last.stage || 'Em andamento...'; return; }
  if (last.status === 'failed') { status.textContent = 'O teste falhou: ' + (last.error || 'erro desconhecido'); return; }
  if (last.status !== 'completed' || !last.summary) { status.textContent = last.stage || last.status; return; }
  const s = last.summary;
  status.textContent = `Concluído em ${new Date(last.finished_at).toLocaleString('pt-BR')}: ${s.corpus_files} PDFs, ${s.queries} perguntas, ${s.chunks} trechos. A busca híbrida mudou o resultado de ${s.changed_queries} perguntas.`;
  const table = document.createElement('table');
  table.className = 'eval-table';
  const head = table.createTHead().insertRow();
  for (const label of ['Busca', 'recall@5', 'recall@10', 'MRR', 'temáticas R@10']) {
    const th = document.createElement('th'); th.textContent = label; head.append(th);
  }
  const body = table.createTBody();
  for (const key of ['lexical', 'vector', 'hybrid']) {
    if (!s[key]) continue;
    const row = body.insertRow();
    const fmt = (v) => (typeof v === 'number' ? v.toFixed(3).replace('.', ',') : '');
    for (const value of [EVAL_LABELS[key], fmt(s[key]['recall@5']), fmt(s[key]['recall@10']), fmt(s[key].mrr),
                         fmt(s[key]['tematicas_recall@10'])]) {
      row.insertCell().textContent = value;
    }
  }
  box.append(table);
  $('retrieval-eval-download').classList.remove('hidden');
}
async function loadRetrievalEval() {
  clearTimeout(retrievalEvalTimer);
  try {
    const data = await (await request('/admin/retrieval-eval')).json();
    renderRetrievalEval(data.last);
    if (data.last && ['queued', 'running'].includes(data.last.status)) {
      retrievalEvalTimer = setTimeout(loadRetrievalEval, 15000);
    }
  } catch (e) { $('retrieval-eval-status').textContent = e.message; }
}
$('retrieval-eval-start').addEventListener('click', async () => {
  $('retrieval-eval-start').disabled = true;
  $('retrieval-eval-status').textContent = 'Iniciando...';
  try { await request('/admin/retrieval-eval', {method: 'POST'}); await loadRetrievalEval(); }
  catch (e) { $('retrieval-eval-status').textContent = e.message; $('retrieval-eval-start').disabled = false; }
});
$('retrieval-eval-download').addEventListener('click', () => {
  if (retrievalEvalJob) downloadPath('/admin/retrieval-eval/' + retrievalEvalJob.id + '/download', 'teste_busca_corpus.json');
});
