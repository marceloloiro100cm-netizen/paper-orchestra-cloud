// Extraído de public/index.html em 28/11/2026 (script clássico: roda na mesma ordem de antes).
(function () {
  // O núcleo do orquestrador mantém os valores reais dos campos.
  const template = document.getElementById('template');
  const language = document.getElementById('language');
  const title = document.getElementById('title');
  const idea = document.getElementById('idea');
  const log = document.getElementById('log');
  const form = document.getElementById('new-paper');
  const syncTemplate = () => document.querySelectorAll('.tpl-card').forEach(c => {
    const selected = c.dataset.tpl === template.value;
    c.classList.toggle('active', selected);
    c.setAttribute('aria-pressed', String(selected));
  });
  const syncLanguage = () => document.querySelectorAll('.lang-btn').forEach(b => {
    const selected = b.dataset.lang === language.value;
    b.classList.toggle('active', selected);
    b.setAttribute('aria-pressed', String(selected));
  });
  document.querySelectorAll('.tpl-card').forEach(c => c.addEventListener('click', () => {
    template.value = c.dataset.tpl;
    template.dispatchEvent(new Event('change', {bubbles:true}));
  }));
  document.querySelectorAll('.lang-btn').forEach(b => b.addEventListener('click', () => {
    language.value = b.dataset.lang;
    language.dispatchEvent(new Event('change', {bubbles:true}));
  }));
  template.addEventListener('change', syncTemplate);
  language.addEventListener('change', syncLanguage);
  function readiness() {
    const fields = [{id:'pill-title',el:title,min:3,max:120},{id:'pill-idea',el:idea,min:40},{id:'pill-log',el:log,min:40}];
    fields.forEach(({id,el,min,max}) => {
      const pill = document.getElementById(id);
      if (!pill) return;
      const n = el.value.trim().length;
      pill.textContent = max ? n + ' / ' + max : n >= min ? '✓ ' + n + ' caracteres' : 'faltam ' + (min-n) + ' caracteres';
      pill.classList.toggle('ok', n >= min);
    });
  }
  [title,idea,log].forEach(el=>el.addEventListener('input',readiness));
  form.addEventListener('reset',()=>queueMicrotask(()=>{syncTemplate();syncLanguage();readiness();}));
  function syncSources() {
    const rows = [...document.querySelectorAll('#library-list .library-item')];
    const marked = rows.filter(el => el.querySelector('input[type="checkbox"]')?.checked);
    document.getElementById('studio-sources-title').textContent = 'Fontes anexadas da Biblioteca (' + marked.length + '/8)';
    const chips = document.getElementById('studio-source-chips');
    chips.replaceChildren();
    if (!marked.length) {
      const span=document.createElement('span');span.className='subtle';span.textContent='Nenhuma fonte selecionada (opcional).';chips.append(span);
    }
    for (const row of marked) {
      const chip=document.createElement('span');chip.className='source-chip';
      chip.textContent=row.querySelector('label')?.textContent?.trim() || 'Documento selecionado';
      chips.append(chip);
    }
    const budget=document.getElementById('budget-chars');
    document.getElementById('studio-sources-chars').textContent = budget?.textContent || '';
    document.getElementById('studio-attached-strip').classList.toggle('over-limit',document.getElementById('budget-box')?.classList.contains('budget-over') || false);
  }
  const library=document.getElementById('library-list');
  const budget=document.getElementById('budget-chars');
  const observer=new MutationObserver(syncSources);
  observer.observe(library,{childList:true,subtree:true});
  if(budget)observer.observe(budget,{childList:true,characterData:true,subtree:true});
  library.addEventListener('change',()=>setTimeout(syncSources,0));
  syncTemplate();syncLanguage();readiness();syncSources();
})();
