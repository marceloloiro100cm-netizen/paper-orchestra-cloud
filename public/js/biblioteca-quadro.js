// Extraído de public/index.html em 28/11/2026 (script clássico: roda na mesma ordem de antes).
(function () {
  const CHAR_LIMIT_TOTAL = 75000;
  const DEFAULT_COLS = [
    { id: 'col-1', name: 'A Triar', desc: 'Arquivos recém-enviados' },
    { id: 'col-2', name: 'Em Leitura', desc: 'Em fichamento crítico' },
    { id: 'col-3', name: 'Pronto para Citar', desc: 'Lidos e prontos para usar' },
    { id: 'col-4', name: 'Normas & Bases', desc: 'Manuais ABNT e .bib' }
  ];

  let columns = JSON.parse(JSON.stringify(DEFAULT_COLS));
  let itemColMap = {};
  let viewMode = 'kanban';
  let activeColFilter = 'todas';
  let activeFormat = 'todos';
  let editingColId = null;
  let draggedKey = null;

  // Preferências pertencem à conta Google ativa, nunca ao navegador inteiro.
  // O servidor continua sendo a fonte de verdade para os documentos.
  let libraryUid = null;
  const prefKey = (name) => 'scriptorium_library_' + libraryUid + '_' + name;
  function loadPrefs() {
    columns = JSON.parse(JSON.stringify(DEFAULT_COLS));
    itemColMap = {};
    viewMode = 'kanban';
    activeColFilter = 'todas';
    activeFormat = 'todos';
    editingColId = null;
    if (!libraryUid) return;
    try {
      const sc = JSON.parse(localStorage.getItem(prefKey('cols')) || 'null');
      if (Array.isArray(sc) && sc.length >= 2 &&
          sc.every(c => typeof c.id === 'string' && typeof c.name === 'string'))
        columns = sc.map(c => c.desc === 'Validados para os agentes' ? { ...c, desc: 'Lidos e prontos para usar' } : c);
      const sm = JSON.parse(localStorage.getItem(prefKey('items')) || '{}');
      if (sm && typeof sm === 'object' && !Array.isArray(sm)) itemColMap = sm;
      const sv = localStorage.getItem(prefKey('view'));
      if (sv === 'kanban' || sv === 'list') viewMode = sv;
    } catch (_) {}
  }
  function savePrefs() {
    if (!libraryUid) return;
    try {
      localStorage.setItem(prefKey('cols'), JSON.stringify(columns));
      localStorage.setItem(prefKey('items'), JSON.stringify(itemColMap));
      localStorage.setItem(prefKey('view'), viewMode);
    } catch (_) {}
  }

  
  /* 3. Sincronização Biblioteca Real (#library-list) <-> Kanban & Orçamento 75k chars */
  const libList = document.getElementById('library-list');
  const kanbanBoard = document.getElementById('kanban-board');
  const colPills = document.getElementById('col-pills');
  const viewKanbanBtn = document.getElementById('view-kanban-btn');
  const viewListBtn = document.getElementById('view-list-btn');
  const formatFilter = document.getElementById('format-filter');
  const datalist = document.getElementById('kanban-col-options');

  function updateDatalist() {
    datalist.replaceChildren();
    columns.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      datalist.appendChild(opt);
    });
  }

  function estimateCharsFromMeta(filename, metaText) {
    const ext = (filename.toLowerCase().match(/\.([a-z0-9]+)$/) || [])[1] || '';
    const m = (metaText || '').match(/([\d.,]+)\s*(kb|kib|mb|mib|b)\b/i);
    let kb = 250;
    if (m) {
      const val = parseFloat(m[1].replace(',', '.'));
      const unit = m[2].toLowerCase();
      if (unit === 'mb' || unit === 'mib') kb = val * 1024;
      else if (unit === 'kb' || unit === 'kib') kb = val;
      else kb = val / 1024;
    }
    // Estimativa realista de texto extraível por formato (teto real de 20k chars/arquivo)
    let est = 0;
    if (ext === 'txt' || ext === 'bib' || ext === 'ris') est = Math.round(kb * 900);
    else if (ext === 'docx') est = Math.round(kb * 35);
    else est = Math.round(kb * 14);
    return Math.max(1200, Math.min(20000, est));
  }

  function resolveColId(key, metaText) {
    if (itemColMap[key] && columns.some(c => c.id === itemColMap[key])) return itemColMap[key];
    const lowerMeta = (metaText || '').toLowerCase();
    for (const c of columns) {
      if (lowerMeta.includes(c.name.toLowerCase())) return c.id;
    }
    return columns[0].id;
  }

  function readRealLibraryItems() {
    const nodes = Array.from(libList.querySelectorAll('.library-item'));
    return nodes.map((node, idx) => {
      const cb = node.querySelector('input[type="checkbox"]');
      const label = node.querySelector('label');
      const metaEl = node.querySelector('.library-meta');
      const filename = (label ? label.textContent : `Documento ${idx + 1}`).trim();
      const metaText = (metaEl ? metaEl.textContent : '').trim();
      const ext = (filename.toLowerCase().match(/\.([a-z0-9]+)$/) || [])[1] || '';
      const key = filename + '|' + idx;
      const stableKey = node.dataset.libraryId || filename;
      const colId = resolveColId(stableKey, metaText);
      const buttons = Array.from(node.querySelectorAll('.library-actions button'));
      return {
        node, cb, filename, metaText, ext, stableKey, colId,
        checked: !!(cb && cb.checked),
        estChars: estimateCharsFromMeta(filename, metaText),
        buttons
      };
    });
  }

  function updateBudget(items) {
    const selected = items.filter(i => i.checked);
    const totalChars = selected.reduce((sum, i) => sum + i.estChars, 0);
    const lim = (window.SCRIPTORIUM_CONTEXT_LIMITS || {})[document.getElementById('context-size')?.value || 'padrao'] || {sources: 8, chars: CHAR_LIMIT_TOTAL};
    const isOver = totalChars > lim.chars;
    const pct = Math.min(100, Math.round((totalChars / lim.chars) * 100));

    const box = document.getElementById('budget-box');
    const srcEl = document.getElementById('budget-sources');
    const chrEl = document.getElementById('budget-chars');
    const fill = document.getElementById('budget-fill');
    const alertBox = document.getElementById('budget-alert');
    const sub1 = document.getElementById('step-sub-1');

    srcEl.textContent = `${selected.length}/${lim.sources} fontes anexadas`;
    chrEl.textContent = `${totalChars.toLocaleString('pt-BR')} / ${lim.chars.toLocaleString('pt-BR')} caracteres`;
    fill.style.width = pct + '%';
    box.classList.toggle('budget-over', isOver);
    alertBox.classList.toggle('hidden', !isOver);
    if (sub1) sub1.textContent = document.body.classList.contains('sem-api')
      ? `Biblioteca privada · ${viewMode === 'kanban' ? 'Kanban' : 'Lista'}`
      : `${selected.length}/${lim.sources} fonte(s) · ${viewMode === 'kanban' ? 'Kanban' : 'Lista'}`;
  }

  function renderLibraryViews() {
    updateDatalist();
    const items = readRealLibraryItems();
    updateBudget(items);

    viewKanbanBtn.classList.toggle('active', viewMode === 'kanban');
    viewListBtn.classList.toggle('active', viewMode === 'list');

    // Chips de filtro por coluna: só na Lista (no Kanban as próprias colunas já mostram isso)
    colPills.replaceChildren();
    colPills.hidden = viewMode === 'kanban';
    if (viewMode === 'kanban') activeColFilter = 'todas';
    const lbl = document.createElement('span');
    lbl.style.cssText = 'font-size:.74rem;font-weight:600;color:var(--text-muted);margin-right:4px';
    lbl.textContent = 'Filtro por coluna:';
    colPills.appendChild(lbl);

    const allBtn = document.createElement('button');
    allBtn.type = 'button';
    allBtn.className = 'col-pill' + (activeColFilter === 'todas' ? ' active' : '');
    allBtn.textContent = `Todas (${items.length})`;
    allBtn.addEventListener('click', () => { activeColFilter = 'todas'; renderLibraryViews(); });
    colPills.appendChild(allBtn);

    columns.forEach(col => {
      const count = items.filter(i => i.colId === col.id).length;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'col-pill' + (activeColFilter === col.id ? ' active' : '');
      b.textContent = `${col.name} (${count})`;
      b.addEventListener('click', () => { activeColFilter = col.id; renderLibraryViews(); });
      colPills.appendChild(b);
    });

    // Aplica filtros (coluna + formato) na lista real para o modo Lista
    items.forEach(it => {
      const matchCol = activeColFilter === 'todas' || it.colId === activeColFilter;
      const matchFmt = activeFormat === 'todos' || it.ext === activeFormat;
      it.node.style.display = (matchCol && matchFmt) ? '' : 'none';
    });

    if (viewMode === 'list') {
      kanbanBoard.classList.add('hidden');
      libList.classList.remove('kanban-source-hidden');
      return;
    }

    // Modo Kanban
    libList.classList.add('kanban-source-hidden');
    kanbanBoard.classList.remove('hidden');
    kanbanBoard.replaceChildren();

    if (!items.length) {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'kanban-empty';
      emptyMsg.style.gridColumn = '1 / -1';
      emptyMsg.textContent = (libList.textContent || 'Nenhum documento carregado na biblioteca ainda.').trim();
      kanbanBoard.appendChild(emptyMsg);
      return;
    }

    const visibleCols = activeColFilter === 'todas' ? columns : columns.filter(c => c.id === activeColFilter);
    visibleCols.forEach(col => {
      const colEl = document.createElement('section');
      colEl.className = 'kanban-col';
      colEl.dataset.dropCol = col.id;

      colEl.addEventListener('dragover', e => { e.preventDefault(); colEl.classList.add('drag-over'); });
      colEl.addEventListener('dragleave', e => { if (!colEl.contains(e.relatedTarget)) colEl.classList.remove('drag-over'); });
      colEl.addEventListener('drop', e => {
        e.preventDefault();
        colEl.classList.remove('drag-over');
        const key = draggedKey || e.dataTransfer.getData('text/plain');
        if (key) {
          itemColMap[key] = col.id;
          savePrefs();
          renderLibraryViews();
        }
      });

      const colItems = items.filter(i => i.colId === col.id && (activeFormat === 'todos' || i.ext === activeFormat));

      // Cabeçalho da coluna (com renomeação inline)
      const head = document.createElement('div');
      head.className = 'kanban-col-head';
      const left = document.createElement('div');
      left.style.minWidth = '0';
      left.style.flex = '1';

      if (editingColId === col.id) {
        const wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;gap:5px;align-items:center';
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.value = col.name;
        inp.maxLength = 40;
        inp.style.cssText = 'padding:4px 8px;font-size:.78rem;font-weight:700';
        const ok = document.createElement('button');
        ok.type = 'button';
        ok.className = 'kcard-btn on';
        ok.textContent = 'OK';
        const commit = () => {
          if (inp.value.trim()) col.name = inp.value.trim();
          editingColId = null;
          savePrefs();
          renderLibraryViews();
        };
        ok.addEventListener('click', commit);
        inp.addEventListener('keydown', e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { editingColId = null; renderLibraryViews(); } });
        wrap.append(inp, ok);
        left.appendChild(wrap);
        setTimeout(() => { inp.focus(); inp.select(); }, 10);
      } else {
        const h = document.createElement('h3');
        h.className = 'kanban-col-title';
        h.textContent = col.name;
        const rBtn = document.createElement('button');
        rBtn.type = 'button';
        rBtn.className = 'rename-btn';
        rBtn.title = 'Renomear coluna';
        rBtn.textContent = '✎';
        rBtn.addEventListener('click', () => { editingColId = col.id; renderLibraryViews(); });
        h.appendChild(rBtn);
        left.appendChild(h);
      }

      const d = document.createElement('div');
      d.className = 'kanban-col-desc';
      d.textContent = col.desc;
      left.appendChild(d);

      const cnt = document.createElement('span');
      cnt.className = 'kanban-count';
      cnt.textContent = String(colItems.length);
      head.append(left, cnt);
      colEl.appendChild(head);

      // Cartões da coluna
      const listWrap = document.createElement('div');
      listWrap.className = 'kanban-cards';

      if (!colItems.length) {
        const emp = document.createElement('div');
        emp.className = 'kanban-empty';
        emp.textContent = 'Arraste um documento para cá.';
        listWrap.appendChild(emp);
      } else {
        colItems.forEach(it => {
          const card = document.createElement('article');
          card.className = 'kanban-card' + (it.checked ? ' selected' : '');
          card.draggable = true;
          card.addEventListener('dragstart', e => {
            draggedKey = it.stableKey;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', it.stableKey);
          });
          card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            draggedKey = null;
            kanbanBoard.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
          });

          const t = document.createElement('div');
          t.className = 'kcard-title';
          t.textContent = it.filename;

          const m = document.createElement('div');
          m.className = 'kcard-meta';
          m.textContent = it.metaText || `${it.estChars.toLocaleString('pt-BR')} chars (est.)`;

          const foot = document.createElement('div');
          foot.className = 'kcard-foot';

          const toggleBtn = document.createElement('button');
          toggleBtn.type = 'button';
          toggleBtn.className = 'kcard-btn' + (it.checked ? ' on' : '');
          toggleBtn.textContent = it.checked ? 'Anexado ✓' : '+ Anexar';
          toggleBtn.addEventListener('click', () => {
            if (it.cb) { it.cb.click(); setTimeout(renderLibraryViews, 20); }
          });

          const selMove = document.createElement('select');
          selMove.className = 'kcard-move';
          selMove.setAttribute('aria-label', 'Mover para coluna');
          columns.forEach(c => {
            const o = document.createElement('option');
            o.value = c.id;
            o.textContent = c.name;
            if (c.id === col.id) o.selected = true;
            selMove.appendChild(o);
          });
          selMove.addEventListener('change', () => {
            itemColMap[it.stableKey] = selMove.value;
            savePrefs();
            renderLibraryViews();
          });

          // Fichamento & ABNT: abre o modal unificado (funciona igual no Kanban e na Lista)
          const studyBtn = document.createElement('button');
          studyBtn.type = 'button';
          studyBtn.className = 'kcard-btn';
          studyBtn.title = 'Abrir fichamento por página, papel na pesquisa e citação ABNT';
          studyBtn.textContent = 'Fichar / ABNT';
          studyBtn.addEventListener('click', () => {
            window.ScriptoriumBiblioteca?.abrirEstudo(it.stableKey);
          });

          // Apagar: usa o botão da lista original (app.js pede confirmação antes).
          const delBtn = document.createElement('button');
          delBtn.type = 'button';
          delBtn.className = 'kcard-btn kcard-del';
          delBtn.title = 'Apagar fonte';
          delBtn.setAttribute('aria-label', 'Apagar ' + it.filename);
          delBtn.textContent = 'Apagar';
          delBtn.addEventListener('click', () => {
            const real = it.node && it.node.querySelector('.library-delete');
            if (real) real.click();
          });
          const left2 = document.createElement('div');
          left2.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
          left2.append(toggleBtn, studyBtn, delBtn);
          foot.append(left2, selMove);
          card.append(t, m, foot);
          listWrap.appendChild(card);
        });
      }

      colEl.appendChild(listWrap);
      kanbanBoard.appendChild(colEl);
    });
  }

  /* 4. Modal Configurar Colunas */
  const cfgModal = document.getElementById('config-modal');
  const cfgBody = document.getElementById('cfg-body');

  function renderCfgModal() {
    cfgBody.replaceChildren();
    columns.forEach((col, i) => {
      const row = document.createElement('div');
      row.className = 'cfg-row';

      const top = document.createElement('div');
      top.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:.76rem';
      const lbl = document.createElement('strong');
      lbl.style.color = 'var(--mpie-blue-text)';
      lbl.textContent = `Coluna ${i + 1}`;
      top.appendChild(lbl);

      if (columns.length > 2) {
        const del = document.createElement('button');
        del.type = 'button';
        del.style.cssText = 'border:none;background:transparent;color:var(--danger-text);font-size:.76rem;font-weight:600';
        del.textContent = 'Remover';
        del.addEventListener('click', () => {
          const fb = columns.find(c => c.id !== col.id).id;
          Object.keys(itemColMap).forEach(k => { if (itemColMap[k] === col.id) itemColMap[k] = fb; });
          columns = columns.filter(c => c.id !== col.id);
          if (activeColFilter === col.id) activeColFilter = 'todas';
          savePrefs();
          renderCfgModal();
          renderLibraryViews();
        });
        top.appendChild(del);
      }

      const grid = document.createElement('div');
      grid.className = 'columns';
      grid.style.gap = '8px';

      const inpName = document.createElement('input');
      inpName.type = 'text';
      inpName.value = col.name;
      inpName.maxLength = 40;
      inpName.placeholder = 'Nome da coluna';
      inpName.addEventListener('input', () => { col.name = inpName.value.trim() || 'Sem nome'; savePrefs(); });

      const inpDesc = document.createElement('input');
      inpDesc.type = 'text';
      inpDesc.value = col.desc;
      inpDesc.maxLength = 80;
      inpDesc.placeholder = 'Descrição curta';
      inpDesc.addEventListener('input', () => { col.desc = inpDesc.value; savePrefs(); });

      grid.append(inpName, inpDesc);
      row.append(top, grid);
      cfgBody.appendChild(row);
    });
  }

  document.getElementById('open-config-cols').addEventListener('click', () => { renderCfgModal(); cfgModal.classList.remove('hidden'); });
  const closeCfg = () => { cfgModal.classList.add('hidden'); renderLibraryViews(); };
  document.getElementById('cfg-close').addEventListener('click', closeCfg);
  document.getElementById('cfg-done').addEventListener('click', closeCfg);
  cfgModal.addEventListener('click', e => { if (e.target === cfgModal) closeCfg(); });
  document.getElementById('cfg-add').addEventListener('click', () => {
    columns.push({ id: 'col-' + Date.now().toString().slice(-4), name: `Nova Coluna ${columns.length + 1}`, desc: 'Filtro personalizado' });
    savePrefs();
    renderCfgModal();
  });
  document.getElementById('cfg-reset').addEventListener('click', () => {
    columns = JSON.parse(JSON.stringify(DEFAULT_COLS));
    activeColFilter = 'todas';
    savePrefs();
    renderCfgModal();
  });

  viewKanbanBtn.addEventListener('click', () => { viewMode = 'kanban'; savePrefs(); renderLibraryViews(); });
  viewListBtn.addEventListener('click', () => { viewMode = 'list'; savePrefs(); renderLibraryViews(); });
  formatFilter.addEventListener('change', () => { activeFormat = formatFilter.value; renderLibraryViews(); });

  // Observa qualquer atualização feita por public/app.js em #library-list e #selected-count
  if (typeof MutationObserver !== 'undefined') {
    new MutationObserver(renderLibraryViews).observe(libList, { childList: true, subtree: true });
    const selCount = document.getElementById('selected-count');
    if (selCount) new MutationObserver(() => updateBudget(readRealLibraryItems())).observe(selCount, { childList: true, characterData: true, subtree: true });
  }
  libList.addEventListener('change', () => setTimeout(renderLibraryViews, 20));
  window.addEventListener('scriptorium:library-user-changed', (event) => {
    const uid = event.detail && event.detail.uid;
    if (libraryUid === uid) return;
    libraryUid = uid || null;
    loadPrefs();
    libList.textContent = 'Carregando biblioteca...';
    renderLibraryViews();
  });
  renderLibraryViews();

})();
