import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';

const $ = (id) => document.getElementById(id);
const config = window.PAPER_FIREBASE_CONFIG;
if (!config || !config.apiKey || config.apiKey === 'SUBSTITUIR') {
  $('auth-status').textContent = 'Falta configurar public/config.js. Consulte README.md.';
  $('login').disabled = true;
  throw new Error('Firebase Web App não configurado');
}
const auth = getAuth(initializeApp(config));
const provider = new GoogleAuthProvider();
let user = null;
let refreshInterval = null;

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
    throw new Error(msg);
  }
  return r;
}

$('login').addEventListener('click', async () => {
  $('auth-status').textContent = 'Autenticando…';
  try { await signInWithPopup(auth, provider); }
  catch (err) {
    if (['auth/popup-blocked','auth/cancelled-popup-request'].includes(err.code)) {
      await signInWithRedirect(auth, provider);
    } else { $('auth-status').textContent = `Falha no login: ${err.message}`; }
  }
});
getRedirectResult(auth).catch(e => { $('auth-status').textContent = e.message; });
$('logout').addEventListener('click', () => signOut(auth));

async function download(id, kind) {
  try {
    const r = await request(`/jobs/${id}/download/${kind}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${id}_${kind === 'pdf' ? 'artigo.pdf' : kind === 'latex' ? 'latex.zip' : 'execucao.log'}`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { alert(e.message); }
}

function statusLabel(value) {
  return ({queued:'Na fila',running:'Em execução',completed:'Concluído',failed:'Falhou'})[value] || value;
}

async function loadJobs() {
  if (!user) return;
  const area = $('research-list');
  try {
    const r = await request('/jobs');
    const data = await r.json();
    area.replaceChildren();
    if (!data.items.length) { area.textContent = 'Nenhuma pesquisa criada até o momento.'; return; }
    for (const entry of data.items) {
      const item = document.createElement('div'); item.className='item';
      const info = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = entry.title; info.append(title);
      const date = document.createElement('small');
      date.textContent = `Criada em ${new Date(entry.created_at).toLocaleString('pt-BR')} • ${entry.stage || 'Aguardando'}`;
      info.append(date);
      if (entry.error) {const err=document.createElement('small'); err.textContent=entry.error; info.append(err);}
      if (entry.status === 'completed' || entry.status === 'failed') {
        const files = document.createElement('div'); files.className='downloads';
        const available = entry.status === 'failed' ? ['log'] : entry.files;
        for (const kind of available) {
          const button = document.createElement('button'); button.type='button';
          button.textContent=kind==='pdf'?'Baixar PDF':kind==='latex'?'Baixar LaTeX':'Logs';
          button.addEventListener('click', ()=>download(entry.id,kind));
          files.append(button);
        }
        info.append(files);
      }
      const badge = document.createElement('span'); badge.className='pill'; badge.textContent=statusLabel(entry.status);
      item.append(info, badge); area.append(item);
    }
  } catch (e) { area.textContent = `Não foi possível consultar pesquisas: ${e.message}`; }
}

$('refresh').addEventListener('click', loadJobs);
$('new-paper').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button=$('submit'); button.disabled=true; $('submit-status').textContent='Salvando e iniciando...';
  try {
    const payload = {
      title:$('title').value, idea:$('idea').value,
      experimental_log:$('log').value, template:$('template').value,
      model:$('model').value, plotting:$('plotting').checked
    };
    await request('/jobs', {method:'POST',body:JSON.stringify(payload)});
    $('submit-status').textContent='Pesquisa enviada. Você pode fechar o navegador.';
    $('new-paper').reset(); await loadJobs();
  } catch (e) { $('submit-status').textContent=e.message; }
  finally {button.disabled=false;}
});

onAuthStateChanged(auth, async (current) => {
  user=current;
  $('login-panel').classList.toggle('hidden', !!user);
  $('workspace').classList.toggle('hidden', !user);
  $('logout').classList.toggle('hidden', !user);
  $('identity').textContent=user?.email || '';
  if (refreshInterval) clearInterval(refreshInterval);
  if (user) { await loadJobs(); refreshInterval=setInterval(loadJobs, 12000); }
});
