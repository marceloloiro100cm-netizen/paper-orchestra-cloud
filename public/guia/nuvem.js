// Guia de escrita: salva o guia na conta do Scriptorium quando a pessoa está logada.
// Sem login, o guia continua funcionando só neste navegador (localStorage).
import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import { getAuth, GoogleAuthProvider, signInWithPopup, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';

const app = initializeApp(window.PAPER_FIREBASE_CONFIG);
const auth = getAuth(app);
const loginButton = document.getElementById('guiaLogin');
let user = null;
let base = 0;          // changedAt da última versão que veio da conta ou foi salva nela
let timer = null;
let saving = false;
let pending = false;
let status = '';       // texto mostrado na faixa de status

function hora() { return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }); }
function setStatus(text) { status = text; window.GuiaApp?.refresh(); }

async function call(method, query = '', body) {
  const token = await user.getIdToken();
  const r = await fetch('/api/guia/estado' + query, {
    method,
    headers: { Authorization: 'Bearer ' + token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch (_e) { /* resposta sem JSON */ }
  return { ok: r.ok, status: r.status, data };
}

async function abrir() {
  setStatus('Conferindo o guia salvo na sua conta…');
  const r = await call('GET');
  if (r.status === 403) { user = null; setStatus('Sua conta ainda não foi autorizada no Scriptorium; o guia fica só neste navegador. Peça acesso na página inicial.'); return; }
  if (!r.ok) { setStatus('Não foi possível abrir o guia da conta agora; seguindo só neste navegador.'); return; }
  const remote = r.data.estado;
  const local = window.GuiaApp.getState();
  if (remote && (remote.changedAt || 0) > (local.changedAt || 0)) {
    base = remote.changedAt || 0;
    window.GuiaApp.adopt(remote, true);
    setStatus('✓ Guia da sua conta aberto às ' + hora());
  } else {
    base = remote ? (remote.changedAt || 0) : 0;
    await salvar();
  }
}

async function salvar(forcar = false) {
  if (!user) return;
  if (saving) { pending = true; return; }
  saving = true;
  const state = window.GuiaApp.getState();
  try {
    const r = await call('PUT', `?base=${base}${forcar ? '&forcar=true' : ''}`, state);
    if (r.ok) { base = r.data.changedAt; setStatus('✓ Salvo na sua conta às ' + hora()); }
    else if (r.status === 409) { await conflito(r.data?.detail?.changedAt || 0); }
    else if (r.status === 413) setStatus('O guia passou do limite da conta (3 MB). Exporte um backup e apague versões antigas.');
    else setStatus('Salvo só neste navegador; a conta não respondeu (' + r.status + '). Tentaremos de novo na próxima alteração.');
  } catch (_e) {
    setStatus('Salvo só neste navegador; sem conexão com a conta agora.');
  } finally {
    saving = false;
    if (pending) { pending = false; agendar(); }
  }
}

async function conflito() {
  // Outro dispositivo salvou depois: abre a versão da conta e guarda a deste navegador como versão recuperável.
  const r = await call('GET');
  if (!r.ok || !r.data.estado) { await salvar(true); return; }
  base = r.data.estado.changedAt || 0;
  window.GuiaApp.adopt(r.data.estado, true);
  setStatus('O guia foi alterado em outro dispositivo. Abrimos a versão da conta; a deste navegador ficou em Versões.');
}

function agendar() {
  if (!user) return;
  clearTimeout(timer);
  timer = setTimeout(() => salvar(), 1500);
}

window.GuiaNuvem = {
  agendar,
  texto: () => status || null,
};

loginButton.addEventListener('click', async () => {
  try { await signInWithPopup(auth, new GoogleAuthProvider()); }
  catch (_e) { setStatus('Login cancelado; o guia segue só neste navegador.'); }
});

onAuthStateChanged(auth, async (u) => {
  user = u;
  loginButton.hidden = Boolean(u);
  if (u) await abrir();
  else setStatus('');
});
