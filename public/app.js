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


function libraryMessage(text) { $('library-message').textContent = text; }

function updateSelectedCount() {
  $('selected-count').textContent = selectedSourceIds.size + ' fonte(s) selecionada(s) para a próxima pesquisa (máximo de 8).';
}

function displayLibrary() {
  const target = $('library-list');
  target.replaceChildren();
  const filter = $('library-filter').value.trim().toLowerCase();
  const items = libraryItems.filter((i) =>
    [i.name, i.collection, i.description].some((v) => String(v || '').toLowerCase().includes(filter))
  );
  if (!items.length) {target.textContent='Nenhum documento encontrado. Adicione PDFs, DOCX ou bibliografias para começar.';return;}
  for (const item of items) {
    const line = document.createElement('div'); line.className = 'library-item';
    const body = document.createElement('div');
    const label = document.createElement('label');
    const check = document.createElement('input'); check.type='checkbox';
    check.checked = selectedSourceIds.has(item.id);
    check.setAttribute('aria-label','Usar fonte ' + item.name + ' na próxima pesquisa');
    check.addEventListener('change', () => {
      if (check.checked && selectedSourceIds.size >= 8) {
        check.checked=false;libraryMessage('Máximo de 8 fontes por pesquisa.');return;
      }
      if(check.checked) selectedSourceIds.add(item.id);
      else selectedSourceIds.delete(item.id);
      libraryMessage('');updateSelectedCount();
    });
    const name = document.createElement('span'); name.textContent = item.name;
    label.append(check, name);body.append(label);
    const meta = document.createElement('div');meta.className='library-meta';
    meta.textContent = (item.collection||'Geral') + ' · ' + String(item.format||'').toUpperCase() +
      ' · ' + (item.size / 1024).toFixed(0) + ' KB';
    body.append(meta);
    if (item.description) {
      const desc = document.createElement('p');desc.className='library-note';
      desc.textContent=item.description;body.append(desc);
    }
    const actions = document.createElement('div');actions.className='library-actions';
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
    actions.append(down,archive);body.append(actions);line.append(body);target.append(line);
  }
}

async function loadLibrary() {
  if(!user)return;
  try{
    const r=await request('/library/items');
    const data=await r.json();
    libraryItems=data.items||[];
    const activeIds=new Set(libraryItems.map(i=>i.id));
    selectedSourceIds=new Set([...selectedSourceIds].filter(id=>activeIds.has(id)));
    updateSelectedCount();displayLibrary();
  }catch(e){$('library-list').textContent='Não foi possível consultar a biblioteca: '+e.message;}
}

$('refresh-library').addEventListener('click',loadLibrary);
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
    a.href = url; a.download = `${id}_${kind === 'pdf' ? 'artigo.pdf' : kind === 'latex' ? 'latex.zip' : 'execucao.log'}`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { alert(e.message); }
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
    box.replaceChildren();
    const heading = document.createElement('strong');
    heading.textContent = 'Conferência de metadados bibliográficos';
    box.append(heading);
    const description = document.createElement('p');
    description.textContent = 'Fontes: Crossref, OpenAlex e Semantic Scholar. Metadados compatíveis NÃO provam que a fonte sustenta a afirmação citada.';
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

function statusLabel(value) {
  return ({queued:'Na fila',running:'Em execução',completed:'Concluído',failed:'Falhou'})[value] || value;
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
      const agents = agentPanel(entry.agents);
      if (agents) info.append(agents);
      if (entry.status === 'completed') {
        const warning = document.createElement('small');
        warning.className = 'scientific-warning';
        warning.textContent = 'PDF gerado: números, resultados, referências e alegações de validação precisam de conferência humana.';
        info.append(warning);
      }
      if (entry.reference_status === 'completed_with_limitations') {
        const refStatus = document.createElement('small');
        refStatus.className = 'scientific-warning';
        refStatus.textContent = 'Metadados bibliográficos consultados em bases externas; confira cada referência antes de citar.';
        info.append(refStatus);
      }
      if (entry.audit_status === 'human_review_required') {
        const aud = document.createElement('small');
        aud.className = 'scientific-warning';
        aud.textContent = 'Triagem científica disponível' + (typeof entry.audit_findings === 'number' ? ` · ${entry.audit_findings} alerta(s)` : '') + '. A revisão humana continua obrigatória.';
        info.append(aud);
      } else if (entry.audit_status === 'unavailable') {
        const aud = document.createElement('small');
        aud.className = 'scientific-warning';
        aud.textContent = 'A auditoria não pôde ser gerada; confira manualmente o artigo.';
        info.append(aud);
      }
      if (entry.error) {const err=document.createElement('small'); err.textContent=entry.error; info.append(err);}
      if (entry.status === 'completed' || entry.status === 'failed') {
        const files = document.createElement('div'); files.className='downloads';
        const available = entry.status === 'failed' ? ['log'] : entry.files;
        for (const kind of available) {
          const button = document.createElement('button'); button.type='button';
          button.textContent=kind==='pdf'?'Baixar PDF':kind==='latex'?'Baixar LaTeX':kind==='audit'?'Ver auditoria':kind==='references'?'Conferir referências':'Logs';
          button.addEventListener('click', ()=>kind==='audit' ? showScientificAudit(entry.id, info) : kind==='references' ? showReferenceVerification(entry.id, info) : download(entry.id,kind));
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
      model:$('model').value,
      reflection_model:$('reflection-model').value || null,
      language:$('language').value,
      source_ids:[...selectedSourceIds],
      plotting:$('plotting').checked
    };
    await request('/jobs', {method:'POST',body:JSON.stringify(payload)});
    $('submit-status').textContent='Pesquisa enviada. Você pode fechar o navegador.';
    $('new-paper').reset();selectedSourceIds.clear();updateSelectedCount();displayLibrary();await loadJobs();
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
  if (user) { await Promise.all([loadJobs(),loadLibrary()]); refreshInterval=setInterval(loadJobs, 12000); }
  else { libraryItems=[];selectedSourceIds.clear();updateSelectedCount(); }
});
