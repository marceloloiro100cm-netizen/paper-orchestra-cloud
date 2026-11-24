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
    const error = new Error(msg);
    error.status = r.status;
    throw error;
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
    const line = document.createElement('div'); line.className = 'library-item'; line.dataset.libraryId = item.id;
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
      if (entry.neon_review_requested && entry.neon_review_status === 'unavailable') {
        const warning = document.createElement('small');
        warning.className = 'scientific-warning';
        warning.textContent = 'A revisão adicional com Neon falhou. O PDF principal continua disponível.';
        info.append(warning);
      }
      if (entry.audit_status === 'unavailable') {
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
          if (kind === 'neon' && !accountAccess?.admin) continue;
          const button = document.createElement('button'); button.type='button';
          button.textContent=kind==='pdf'?'Baixar PDF':kind==='latex'?'Baixar LaTeX':kind==='audit'?'Ver auditoria':kind==='references'?'Conferir referências':kind==='neon'?'Parecer Neon':'Logs';
          button.addEventListener('click', ()=>kind==='audit' ? showScientificAudit(entry.id, info) : kind==='references' ? showReferenceVerification(entry.id, info) : kind==='neon' ? showNeonReport(entry.id, info) : download(entry.id,kind));
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
    if (!accountAccess?.research_generation_enabled) {
      $('submit-status').textContent = 'Primeiro conecte e verifique sua chave Gemini.';
      return;
    }
    if (!accountAccess.admin && $('model').value === 'gemini-3.1-pro-preview') {
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
      plotting:$('plotting').checked,
      neon_review:$('neon-review').checked
    };
    await request('/jobs', {method:'POST',body:JSON.stringify(payload)});
    $('submit-status').textContent='Pesquisa enviada. Você pode fechar o navegador.';
    $('new-paper').reset();applyModelAccess();selectedSourceIds.clear();updateSelectedCount();displayLibrary();await loadJobs();
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
  const canPlot = !!accountAccess?.admin;
  $('plotting').checked = canPlot && $('plotting').checked;
  $('plotting').disabled = !canPlot;
  $('plotting').closest('.switch-row')?.classList.toggle('hidden', !canPlot);
  const message = $('model-access-summary');
  if (accountAccess?.admin) {
    message.textContent = 'Modelos disponíveis na infraestrutura administrativa.';
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

async function loadAccountAccess() {
  $('account-panel').classList.remove('hidden');
  $('workspace').classList.remove('access-setup');
  $('workspace').classList.add('access-pending');
  $('access-pending').classList.add('hidden');
  $('guest-credential').classList.add('hidden');
  $('admin-invitations').classList.add('hidden');
  $('submit').disabled = true;
  $('account-state').textContent = 'Verificando...';
  $('pending-email').textContent = user?.email || '';
  $('pending-help').textContent = '';
  // Uma API demorada nunca deve bloquear a tela indefinidamente.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await request('/account/access', { signal: controller.signal });
    accountAccess = await response.json();
    $('workspace').classList.remove('access-pending', 'access-setup');
    $('account-state').textContent = accountAccess.admin ? 'Administrador' :
      (accountAccess.byok_ready ?
        (accountAccess.model_access?.status === 'verified' ? 'Conexão verificada' : 'Verifique sua chave') :
        'Conecte sua chave Gemini');
    $('admin-invitations').classList.toggle('hidden', !accountAccess.admin);
    $('guest-credential').classList.toggle('hidden', !!accountAccess.admin);
    const guestReady = !accountAccess.admin && !!accountAccess.byok_ready;
    const guestVerified = guestReady && accountAccess.model_access?.status === 'verified';
    const hasModels = !!accountAccess.research_generation_enabled;
    $('workspace').classList.toggle('access-setup', !hasModels);
    $('gemini-setup-details').open = !guestVerified;
    $('gemini-setup-title').textContent = guestReady
      ? 'Gerenciar ou trocar minha chave Gemini'
      : 'Conectar minha chave Gemini — primeiro acesso';
    $('gemini-key-ready').classList.toggle('hidden', !guestVerified);
    $('remove-personal-key').classList.toggle('hidden', !guestReady);
    $('submit').disabled = !hasModels;
    $('account-message').textContent = accountAccess.admin ? '' :
      (guestVerified ? '' : (guestReady
        ? 'Sua chave foi cadastrada, mas ainda não há um modelo confirmado. Confira a chave abaixo.'
        : 'Para começar, conecte sua chave Gemini seguindo as instruções.'));
    applyModelAccess();
    if (accountAccess.admin) loadAccessRequests();
  } catch (error) {
    accountAccess = null;
    // Compatibilidade exclusiva da conta administradora já autorizada na API antiga.
    if (error?.status === 404) {
      try {
        await request('/capabilities', { signal: controller.signal });
        accountAccess = {
          admin: true, byok_ready: false, multiuser_enabled: false,
          research_generation_enabled: true, legacy_backend: true,
          allowed_models: ['gemini-3-flash-preview', 'gemini-3.1-pro-preview']
        };
        $('workspace').classList.remove('access-pending');
        applyModelAccess();
        $('account-state').textContent = 'Administrador';
        $('account-message').textContent = '';
        $('submit').disabled = false;
        return;
      } catch (legacyError) {
        error = legacyError;
      }
    }
    const timedOut = error?.name === 'AbortError' || error?.name === 'TimeoutError';
    const awaitingAuthorization = error?.status === 403;
    $('account-state').textContent = timedOut ? 'Conexão indisponível' :
      (awaitingAuthorization ? 'Aguardando autorização' : 'Verificação falhou');
    $('account-message').textContent = awaitingAuthorization
      ? 'A conta Google está conectada, mas o Scriptorium ainda não liberou seu acesso.'
      : (timedOut
        ? 'A API não respondeu em 12 segundos. Tente verificar novamente.'
        : 'Não foi possível confirmar sua conta: ' + (error?.message || 'erro inesperado'));
    $('access-pending').classList.remove('hidden');
    $('workspace').classList.remove('access-setup');
    $('submit').disabled = true;
    accountAccess = null;
  } finally {
    clearTimeout(timeout);
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
  if (accountAccess?.research_generation_enabled) {
    await Promise.all([loadJobs(), loadLibrary(), loadCapabilities()]);
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(loadJobs, 12000);
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
    if (accountAccess?.research_generation_enabled) {
      await Promise.all([loadJobs(),loadLibrary(),loadCapabilities()]);
    }
    const models = saved.model_access?.models || {};
    const hasPro = models['gemini-3.1-pro-preview'] === 'supported';
    const hasFlash = models['gemini-3-flash-preview'] === 'supported';
    $('key-setup-result').textContent = hasPro ?
      'Conexão concluída. Seu modelo avançado está disponível!' :
      (hasFlash ? 'Conexão concluída. Você já pode pesquisar com o modelo econômico.' :
        'Chave cadastrada, mas o Google não liberou os modelos testados. Confira os limites da conta.');
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

onAuthStateChanged(auth, async (current) => {
  user=current;
  window.dispatchEvent(new CustomEvent('scriptorium:library-user-changed', {
    detail: { uid: current?.uid || null }
  }));
  if (user) $('workspace').classList.add('access-pending');
  $('login-panel').classList.toggle('hidden', !!user);
  $('workspace').classList.toggle('hidden', !user);
  $('logout').classList.toggle('hidden', !user);
  $('identity').textContent=user?.email || '';
  if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
  if (user) {
    await loadAccountAccess();
    if (accountAccess?.research_generation_enabled) {
      await Promise.all([loadJobs(),loadLibrary(),loadCapabilities()]);
      refreshInterval = setInterval(loadJobs, 12000);
    }
  } else {
    accountAccess = null;
    $('workspace').classList.remove('access-pending', 'access-setup');
    $('account-panel').classList.add('hidden');
    $('access-pending').classList.add('hidden');
    $('guest-credential').classList.add('hidden');
    $('personal-gemini-key').value = '';
    $('personal-gemini-key').type = 'password';
    libraryItems = [];
    selectedSourceIds.clear();
    updateSelectedCount();
  }
});
