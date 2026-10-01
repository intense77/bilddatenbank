/**
 * Historisches Bildarchiv - Frontend Logik (Vanilla JS)
 */

let activeCluster = null;
let currentModalImageDetails = null;
let systemConfig = {
  faceRecognitionEnabled: false,
  status: 'unknown',
  device: 'cpu'
};

// Initialisierung bei DOM-Ready
// Initialisierung bei DOM-Ready
document.addEventListener('DOMContentLoaded', () => {
  checkSystemHealth();
  setupDropzone();
  checkIndexingProgress();
  setupCropInteraction();
  // Vorbelegung Suche falls gewünscht
  const urlParams = new URLSearchParams(window.location.search);
  const q = urlParams.get('q');
  if (q) {
    setQueryAndSearch(q);
  }
});

// --- Tab Navigation ---
function switchTab(tab) {
  const searchSec = document.getElementById('tab-search');
  const facesSec = document.getElementById('tab-faces');
  const importSec = document.getElementById('tab-import');
  const dupSec = document.getElementById('tab-duplicates');
  const searchBtn = document.getElementById('tab-search-btn');
  const facesBtn = document.getElementById('tab-faces-btn');
  const importBtn = document.getElementById('tab-import-btn');
  const dupBtn = document.getElementById('tab-duplicates-btn');

  // Alle Sektionen ausblenden
  if (searchSec) searchSec.classList.add('hidden');
  if (facesSec) facesSec.classList.add('hidden');
  if (importSec) importSec.classList.add('hidden');
  if (dupSec) dupSec.classList.add('hidden');

  const activeCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all bg-amber-500 text-slate-950 font-semibold shadow-sm flex items-center gap-2';
  const inactiveCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 transition-all flex items-center gap-2';

  if (searchBtn) searchBtn.className = inactiveCls;
  if (facesBtn) facesBtn.className = inactiveCls;
  if (importBtn) importBtn.className = inactiveCls;
  if (dupBtn) dupBtn.className = inactiveCls;

  if (tab === 'search') {
    if (searchSec) searchSec.classList.remove('hidden');
    if (searchBtn) searchBtn.className = activeCls;
  } else if (tab === 'faces') {
    if (facesSec) facesSec.classList.remove('hidden');
    if (facesBtn) facesBtn.className = activeCls;
    loadClusters();
  } else if (tab === 'duplicates') {
    if (dupSec) dupSec.classList.remove('hidden');
    if (dupBtn) dupBtn.className = activeCls;
    loadArchiveDuplicates();
  } else if (tab === 'import') {
    if (importSec) importSec.classList.remove('hidden');
    if (importBtn) importBtn.className = activeCls;
    loadRegisteredFolders();
    checkIndexingProgress();
  }
}

// --- Health Check & System Settings ---
async function checkSystemHealth() {
  const badge = document.getElementById('health-badge');
  const status = document.getElementById('health-status');
  const toggle = document.getElementById('face-recognition-toggle');
  const toggleLabel = document.getElementById('face-toggle-status-label');

  try {
    const res = await fetch('/api/system/health');
    if (res.ok) {
      const data = await res.json();
      systemConfig.faceRecognitionEnabled = !!data.face_recognition_enabled;
      systemConfig.status = data.status;
      systemConfig.device = data.device;
      badge.classList.remove('hidden');

      if (toggle) toggle.checked = systemConfig.faceRecognitionEnabled;
      if (toggleLabel) {
        toggleLabel.textContent = systemConfig.faceRecognitionEnabled ? 'an' : 'aus';
        toggleLabel.className = systemConfig.faceRecognitionEnabled
          ? 'font-mono text-[10px] text-emerald-400 font-semibold min-w-[20px]'
          : 'font-mono text-[10px] text-slate-400 font-semibold min-w-[20px]';
      }

      const faceLabel = systemConfig.faceRecognitionEnabled ? 'Gesichter: an' : 'Gesichter: aus (DSGVO)';
      status.textContent = `Qdrant: ${data.status} | ${faceLabel}`;

      updateFaceRecognitionUI();
    }
  } catch (err) {
    status.textContent = 'Qdrant offline';
    badge.querySelector('span').className = 'w-2 h-2 rounded-full bg-rose-500';
  }
}

async function handleFaceToggleChange(event) {
  const isChecked = event.target.checked;
  await setFaceRecognition(isChecked);
}

async function setFaceRecognition(enabled) {
  const toggle = document.getElementById('face-recognition-toggle');
  const toggleLabel = document.getElementById('face-toggle-status-label');
  const status = document.getElementById('health-status');

  try {
    const res = await fetch('/api/system/settings/face-recognition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) throw new Error(`Server antwortete mit Status ${res.status}`);
    const data = await res.json();
    systemConfig.faceRecognitionEnabled = !!data.face_recognition_enabled;

    if (toggle) toggle.checked = systemConfig.faceRecognitionEnabled;
    if (toggleLabel) {
      toggleLabel.textContent = systemConfig.faceRecognitionEnabled ? 'an' : 'aus';
      toggleLabel.className = systemConfig.faceRecognitionEnabled
        ? 'font-mono text-[10px] text-emerald-400 font-semibold min-w-[20px]'
        : 'font-mono text-[10px] text-slate-400 font-semibold min-w-[20px]';
    }

    if (status) {
      const faceLabel = systemConfig.faceRecognitionEnabled ? 'Gesichter: an' : 'Gesichter: aus (DSGVO)';
      status.textContent = `Qdrant: ${systemConfig.status} | ${faceLabel}`;
    }

    updateFaceRecognitionUI();

    if (systemConfig.faceRecognitionEnabled) {
      showToast('Biometrische Gesichtserkennung aktiviert (KDG § 29 / Art. 9 DSGVO).');
      const facesSec = document.getElementById('tab-faces');
      if (facesSec && !facesSec.classList.contains('hidden')) {
        loadClusters();
      }
    } else {
      showToast('Gesichtserkennung deaktiviert (Speicher geschont).');
    }
  } catch (err) {
    showToast(`Fehler beim Ändern der Einstellung: ${err.message}`, true);
    if (toggle) toggle.checked = systemConfig.faceRecognitionEnabled;
  }
}

function updateFaceRecognitionUI() {
  const runBtn = document.getElementById('run-clustering-btn');
  const emptyElem = document.getElementById('clusters-empty');

  if (!systemConfig.faceRecognitionEnabled) {
    if (runBtn) {
      runBtn.classList.add('opacity-50', 'cursor-not-allowed');
      runBtn.title = 'Gesichtserkennung ist deaktiviert';
    }
    if (emptyElem) {
      emptyElem.innerHTML = `
        <div class="max-w-md mx-auto p-5 rounded-2xl bg-slate-900 border border-slate-800 text-center space-y-3">
          <div class="w-10 h-10 mx-auto rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
            </svg>
          </div>
          <p class="text-sm font-semibold text-slate-100">Biometrische Gesichtserkennung deaktiviert</p>
          <p class="text-xs text-slate-400 leading-relaxed">
            Aus Gründen der Datensparsamkeit und Ressourcenschonung (§ 26 KDG / Art. 9 DSGVO) ist die Gesichtsanalyse momentan abgeschaltet.
          </p>
          <button onclick="setFaceRecognition(true)" class="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold rounded-lg text-xs transition shadow-sm inline-flex items-center gap-1.5 mt-1">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
            </svg>
            <span>Jetzt für Personen-Suche aktivieren</span>
          </button>
        </div>
      `;
    }
  } else {
    if (runBtn) {
      runBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      runBtn.title = 'Startet das DBSCAN-Clustering aller erkannten Gesichter';
    }
    if (emptyElem && emptyElem.innerHTML.includes('Biometrische Gesichtserkennung deaktiviert')) {
      emptyElem.innerHTML = `
        <div class="w-16 h-16 mx-auto rounded-full bg-slate-800/50 flex items-center justify-center text-slate-500 mb-3">
          <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
          </svg>
        </div>
        <p class="text-sm font-medium text-slate-300">Noch keine Personen-Cluster vorhanden</p>
        <p class="text-xs text-slate-500 mt-1">Starten Sie die automatische Gruppierung mit dem Button oben rechts.</p>
      `;
    }
  }
}

// --- 1. Semantische Freitext-Suche ---

function setQueryAndSearch(term) {
  document.getElementById('search-input').value = term;
  switchTab('search');
  executeSearch(term, document.getElementById('search-limit').value);
}

function handleSearchSubmit(e) {
  e.preventDefault();
  const query = document.getElementById('search-input').value.trim();
  const limit = document.getElementById('search-limit').value;
  if (!query) return;
  executeSearch(query, limit);
}

async function executeSearch(query, limit = 20) {
  const spinner = document.getElementById('search-spinner');
  const grid = document.getElementById('results-grid');
  const empty = document.getElementById('search-empty');
  const resultsBar = document.getElementById('results-bar');
  const resultsCount = document.getElementById('results-count');
  const resultsQuery = document.getElementById('results-query');

  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');
  resultsBar.classList.add('hidden');

  const thresholdElem = document.getElementById('search-threshold');
  const threshold = thresholdElem ? parseFloat(thresholdElem.value) : 0;
  const stackToggle = document.getElementById('search-stack-variants');
  const stackVariants = stackToggle ? stackToggle.checked : true;

  try {
    let url = `/search/semantic?q=${encodeURIComponent(query)}&limit=${limit}&stack_variants=${stackVariants}`;
    if (threshold > 0) {
      url += `&score_threshold=${threshold}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Fehler bei der Suche (${res.status})`);
    const data = await res.json();

    spinner.classList.add('hidden');
    resultsBar.classList.remove('hidden');
    resultsCount.textContent = `${data.length} Treffer gefunden`;
    resultsQuery.textContent = `Suchbegriff: "${query}"`;

    if (data.length === 0) {
      empty.classList.remove('hidden');
      empty.querySelector('p').textContent = `Keine Treffer für "${query}"`;
      return;
    }

    renderSearchResults(data, grid);
  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler: ${err.message}`, true);
  }
}

let currentSearchResults = [];

function renderSearchResults(items, container) {
  currentSearchResults = items || [];
  container.innerHTML = '';
  items.forEach((item, itemIdx) => {
    const card = document.createElement('div');
    const isStack = !!item.is_stack && (item.variants_count > 0);
    const stackClass = isStack ? ' stack-card' : '';
    card.className = `group bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl overflow-hidden shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 cursor-pointer flex flex-col${stackClass}`;
    
    // Score als Prozent
    const scorePct = Math.round(item.score * 100);
    const scoreColor = scorePct >= 65 ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' :
                       scorePct >= 45 ? 'text-amber-400 border-amber-500/30 bg-amber-500/10' :
                                        'text-slate-400 border-slate-500/30 bg-slate-500/10';

    const safePath = encodeURIComponent(item.file_path);
    const displayTitle = item.title || item.file_name;
    const subTitle = item.title ? item.file_name : (item.creator || '');

    // Stack Badge oben links
    let stackBadgeHtml = '';
    if (isStack) {
      stackBadgeHtml = `
        <button
          type="button"
          onclick="event.stopPropagation(); openStackModal(${itemIdx})"
          class="absolute top-2 left-2 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500 text-slate-950 shadow-md hover:bg-amber-400 transition-all flex items-center gap-1 z-10 backdrop-blur-sm"
          title="Dieser Bildstapel fasst ${item.variants_count + 1} verwandte Aufnahmen/Duplikate zusammen. Klicken zum Vergleichen."
        >
          <span>📚</span>
          <span>+${item.variants_count} <span class="hidden sm:inline">Varianten</span></span>
        </button>`;
    }

    // Metadata Badges (Personen, Datierung, Signatur)
    let metaBadgesHtml = '';
    if (item.persons && item.persons.length > 0) {
      item.persons.forEach(p => {
        metaBadgesHtml += `<span class="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 font-medium text-[10px] flex items-center gap-1">👤 ${escapeHtml(p)}</span>`;
      });
    }
    if (item.date) {
      metaBadgesHtml += `<span class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-amber-400/90 font-mono text-[10px]">${escapeHtml(item.date)}</span>`;
    }
    if (item.signature) {
      metaBadgesHtml += `<span class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono text-[10px] truncate max-w-[100px]">${escapeHtml(item.signature)}</span>`;
    }

    const actionText = isStack 
      ? `<span class="text-amber-400 font-semibold group-hover:underline">Stapel prüfen (${item.variants_count + 1}) →</span>` 
      : `<span class="text-amber-500/80 group-hover:translate-x-0.5 transition-transform">Details →</span>`;

    card.innerHTML = `
      <div class="aspect-[4/3] bg-slate-950 relative overflow-hidden flex items-center justify-center">
        <img
          src="/images/serve?path=${safePath}&max_dim=400"
          alt="${escapeHtml(displayTitle)}"
          loading="lazy"
          class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\' fill=\\'%23334155\\'><text x=\\'50%\\' y=\\'50%\\' text-anchor=\\'middle\\' fill=\\'%2364748b\\' font-size=\\'12\\'>Scan</text></svg>'"
        >
        ${stackBadgeHtml}
        <span class="absolute top-2 right-2 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${scoreColor} backdrop-blur-md">
          ${scorePct}% Score
        </span>
        <button
          type="button"
          onclick="quickRotateCardImage(event, '${escapeHtml(item.file_path)}', 90)"
          class="absolute bottom-2 right-2 p-1.5 rounded-lg bg-slate-900/80 hover:bg-amber-500 hover:text-slate-950 text-slate-300 opacity-0 group-hover:opacity-100 transition-all shadow-md backdrop-blur-sm z-10"
          title="Bild verlustfrei um 90° im Uhrzeigersinn drehen"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
            <path d="M21 3v5h-5"></path>
          </svg>
        </button>
      </div>
      <div class="p-3 flex-1 flex flex-col justify-between">
        <div>
          <h5 class="text-xs font-medium text-slate-200 truncate group-hover:text-amber-400 transition" title="${escapeHtml(displayTitle)}">
            ${escapeHtml(displayTitle)}
          </h5>
          ${subTitle ? `<p class="text-[11px] text-slate-400 truncate mt-0.5" title="${escapeHtml(subTitle)}">${escapeHtml(subTitle)}</p>` : ''}
        </div>
        ${metaBadgesHtml ? `<div class="mt-2 flex flex-wrap items-center gap-1">${metaBadgesHtml}</div>` : ''}
        <div class="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <span class="truncate max-w-[110px] font-mono">${escapeHtml(item.file_path.split('/').slice(-2, -1)[0] || 'Archiv')}</span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              onclick="quickRotateCardImage(event, '${escapeHtml(item.file_path)}', 90)"
              class="px-2 py-0.5 rounded bg-slate-800/90 hover:bg-amber-500 hover:text-slate-950 text-slate-300 hover:border-amber-500 font-mono text-[10px] transition border border-slate-700 flex items-center gap-1 shadow-sm"
              title="Bild 90° im Uhrzeigersinn drehen (verlustfrei)"
            >
              <span>↻</span> 90°
            </button>
            ${actionText}
          </div>
        </div>
      </div>
    `;

    card.addEventListener('click', () => {
      if (isStack) {
        openStackModal(itemIdx);
      } else {
        openImageModal(item.file_path, item.file_name);
      }
    });
    container.appendChild(card);
  });
}

// --- Bildstapel & Varianten Modal ---

function openStackModal(itemIdx) {
  const item = currentSearchResults[itemIdx];
  if (!item) return;

  const modal = document.getElementById('stack-modal');
  const title = document.getElementById('stack-modal-title');
  const subtitle = document.getElementById('stack-modal-subtitle');
  const itemsContainer = document.getElementById('stack-modal-items');
  const info = document.getElementById('stack-modal-info');

  const allItems = [
    {
      ...item,
      is_primary: true,
      variant_label: 'Haupttreffer (Primäre Aufnahme)',
      variant_similarity: item.score,
    },
    ...(item.variants || [])
  ];

  title.textContent = `Bildstapel: ${item.file_name || 'Varianten'}`;
  subtitle.textContent = `${allItems.length} Aufnahmen zusammengefasst • ${allItems.length - 1} redundante Treffer vermieden`;
  if (info) info.textContent = `Archivisch verlustfrei: Alle ${allItems.length} Aufnahmen bleiben im physischen Bestand erhalten.`;

  renderStackComparisonItems(allItems, itemsContainer);
  modal.classList.remove('hidden');
}

function closeStackModal() {
  const modal = document.getElementById('stack-modal');
  if (modal) modal.classList.add('hidden');
}

function renderStackComparisonItems(items, container) {
  container.innerHTML = '';

  let maxPixels = 0;
  let masterIdx = -1;
  items.forEach((it, idx) => {
    const px = (it.width || 0) * (it.height || 0);
    if (px > maxPixels) {
      maxPixels = px;
      masterIdx = idx;
    }
  });

  items.forEach((it, idx) => {
    const card = document.createElement('div');
    const isMaster = (idx === masterIdx && maxPixels > 0);
    const safePath = encodeURIComponent(it.file_path || '');
    const isPrimary = !!it.is_primary;

    const relBadge = isPrimary 
      ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">⭐ Hauptaufnahme</span>'
      : (it.variant_type === 'EXACT_DUPLICATE'
        ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">100% Identischer Scan</span>'
        : (it.variant_type === 'FORMAT_VARIANT'
          ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">Zuschnitt / Format</span>'
          : '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40">Serienaufnahme</span>'));

    const masterBadge = isMaster 
      ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">Höchste Auflösung</span>' 
      : '';

    const simPct = it.variant_similarity ? Math.round(it.variant_similarity * 100) : (it.score ? Math.round(it.score * 100) : 100);

    card.className = 'bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col shadow-md hover:border-slate-700 transition';
    card.innerHTML = `
      <div class="aspect-[4/3] bg-slate-900 relative overflow-hidden flex items-center justify-center">
        <img
          src="/images/serve?path=${safePath}&max_dim=600"
          alt="${escapeHtml(it.file_name || '')}"
          loading="lazy"
          class="w-full h-full object-contain"
        >
        <span class="absolute top-2 right-2 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-950/80 border border-slate-700 text-slate-300 backdrop-blur-md">
          ${simPct}% Ähnlichkeit
        </span>
      </div>
      <div class="p-3.5 flex-1 flex flex-col justify-between space-y-3">
        <div>
          <div class="flex flex-wrap items-center gap-1.5 mb-1.5">
            ${relBadge}
            ${masterBadge}
          </div>
          <h5 class="text-xs font-semibold text-slate-100 truncate" title="${escapeHtml(it.file_name || '')}">
            ${escapeHtml(it.file_name || (it.file_path ? it.file_path.split('/').pop() : 'Bild'))}
          </h5>
          <p class="text-[11px] text-slate-400 font-mono truncate mt-0.5" title="${escapeHtml(it.file_path || '')}">
            ${escapeHtml(it.file_path || '')}
          </p>
        </div>

        <div class="space-y-1 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-400">
          <div class="flex justify-between">
            <span class="text-slate-500">Auflösung:</span>
            <span class="text-slate-200">${it.width && it.height ? `${it.width} &times; ${it.height} px` : 'Unbekannt'}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-500">Datierung:</span>
            <span class="text-amber-400/90">${it.date ? escapeHtml(it.date) : 'Keine Angabe'}</span>
          </div>
          ${it.file_size ? `
          <div class="flex justify-between">
            <span class="text-slate-500">Dateigröße:</span>
            <span class="text-slate-300">${(it.file_size / (1024 * 1024)).toFixed(2)} MB</span>
          </div>` : ''}
        </div>

        <div class="pt-2 flex items-center gap-2">
          <button
            type="button"
            onclick="quickRotateCardImage(event, '${escapeHtml(it.file_path || '').replace(/'/g, "\\'")}', 90)"
            class="px-2 py-1.5 bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-300 rounded-lg text-xs font-medium border border-slate-700 transition flex items-center gap-1 shadow-sm"
            title="Bild 90° im Uhrzeigersinn drehen (verlustfrei)"
          >
            <span>↻</span> 90°
          </button>
          <button
            type="button"
            onclick="closeStackModal(); openImageModal('${escapeHtml(it.file_path || '').replace(/'/g, "\\'")}', '${escapeHtml(it.file_name || '').replace(/'/g, "\\'")}')"
            class="flex-1 py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition text-center"
          >
            Details &amp; Zoom
          </button>
          <a
            href="/images/serve?path=${safePath}"
            target="_blank"
            class="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 rounded-lg border border-slate-700 transition"
            title="Original im neuen Tab öffnen"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
            </svg>
          </a>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

// --- 2. Personen & Cluster ---

let allLoadedClusters = [];
let clusterSearchQuery = '';
let clusterCategoryFilter = 'all'; // 'all' | 'named' | 'unnamed'

function handleClusterSearchInput(val) {
  clusterSearchQuery = (val || '').trim();
  const clearBtn = document.getElementById('clusters-search-clear');
  if (clearBtn) {
    if (clusterSearchQuery) {
      clearBtn.classList.remove('hidden');
    } else {
      clearBtn.classList.add('hidden');
    }
  }
  applyClusterFilters();
}

function clearClusterFilter() {
  clusterSearchQuery = '';
  const input = document.getElementById('clusters-search-input');
  if (input) input.value = '';
  const clearBtn = document.getElementById('clusters-search-clear');
  if (clearBtn) clearBtn.classList.add('hidden');
  applyClusterFilters();
}

function setClusterCategoryFilter(category) {
  clusterCategoryFilter = category;

  ['all', 'named', 'unnamed'].forEach(cat => {
    const btn = document.getElementById(`cluster-filter-btn-${cat}`);
    if (!btn) return;
    if (cat === category) {
      btn.className = 'px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-medium transition';
    } else {
      btn.className = 'px-2.5 py-1 rounded-lg bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 font-medium transition';
    }
  });

  applyClusterFilters();
}

function updateClusterCounts() {
  const allCount = allLoadedClusters.length;
  const namedCount = allLoadedClusters.filter(c => c.label && c.label.trim().length > 0).length;
  const unnamedCount = allCount - namedCount;

  const countAll = document.getElementById('count-all-clusters');
  const countNamed = document.getElementById('count-named-clusters');
  const countUnnamed = document.getElementById('count-unnamed-clusters');

  if (countAll) countAll.textContent = allCount;
  if (countNamed) countNamed.textContent = namedCount;
  if (countUnnamed) countUnnamed.textContent = unnamedCount;
}

function applyClusterFilters() {
  const grid = document.getElementById('clusters-grid');
  const empty = document.getElementById('clusters-empty');
  if (!grid || !empty) return;

  updateClusterCounts();

  let filtered = allLoadedClusters;

  if (clusterCategoryFilter === 'named') {
    filtered = filtered.filter(c => c.label && c.label.trim().length > 0);
  } else if (clusterCategoryFilter === 'unnamed') {
    filtered = filtered.filter(c => !c.label || c.label.trim().length === 0);
  }

  if (clusterSearchQuery) {
    const qLower = clusterSearchQuery.toLowerCase();
    filtered = filtered.filter(c => {
      const labelMatch = c.label && c.label.toLowerCase().includes(qLower);
      const idMatch = c.cluster_id && (c.cluster_id.toLowerCase().includes(qLower) || c.cluster_id.replace('cluster_', '#').includes(qLower));
      return labelMatch || idMatch;
    });
  }

  grid.innerHTML = '';

  if (filtered.length === 0) {
    empty.classList.remove('hidden');
    if (clusterSearchQuery || clusterCategoryFilter !== 'all') {
      empty.innerHTML = `
        <div class="py-12 text-center space-y-3">
          <p class="text-sm font-medium text-slate-300">Keine Personen-Cluster gefunden für diesen Filter</p>
          <p class="text-xs text-slate-500 font-mono">Suchfilter: "${escapeHtml(clusterSearchQuery || clusterCategoryFilter)}"</p>
          <button onclick="clearClusterFilter(); setClusterCategoryFilter('all')" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-amber-400 font-medium transition">
            Filter zurücksetzen
          </button>
        </div>
      `;
    } else {
      empty.innerHTML = `
        <p class="text-base text-slate-400 font-medium">Keine Personen-Cluster vorhanden</p>
        <p class="text-xs text-slate-500 mt-1">Indexieren Sie Bilder mit Gesichtern und starten Sie die Cluster-Berechnung.</p>
      `;
    }
    return;
  }

  empty.classList.add('hidden');

  filtered.forEach(c => {
    const card = document.createElement('div');
    card.className = 'group bg-slate-900 border border-slate-800 hover:border-amber-500/40 rounded-xl overflow-hidden p-4 shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 cursor-pointer flex flex-col items-center text-center';

    const displayName = c.label || `Person ${c.cluster_id.replace('cluster_', '#')}`;
    const avatarSrc = c.preview_image || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%231e293b"><circle cx="50" cy="50" r="40" fill="%23334155"/></svg>';

    card.innerHTML = `
      <div class="w-20 h-20 rounded-full overflow-hidden bg-slate-950 border-2 border-slate-700 group-hover:border-amber-400 transition-colors shadow-inner flex items-center justify-center mb-3">
        <img src="${avatarSrc}" alt="Avatar" class="w-full h-full object-cover">
      </div>
      <h4 class="text-sm font-semibold text-slate-100 group-hover:text-amber-400 transition truncate w-full" title="${escapeHtml(displayName)}">
        ${escapeHtml(displayName)}
      </h4>
      <span class="mt-1 text-xs text-slate-400 font-mono">
        ${c.face_count} ${c.face_count === 1 ? 'Porträt' : 'Porträts'}
      </span>
      ${c.label ? `<span class="mt-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-medium truncate max-w-full">✓ Benannt</span>` : `<span class="mt-1.5 px-2 py-0.5 rounded bg-slate-800 text-slate-500 text-[10px] font-medium">Unbenannt</span>`}
      <span class="mt-3 text-[11px] text-amber-500/90 font-medium group-hover:underline">
        Archivbilder ansehen →
      </span>
    `;

    card.addEventListener('click', () => openClusterDetail(c));
    grid.appendChild(card);
  });
}

async function loadClusters() {
  const spinner = document.getElementById('clusters-spinner');
  const grid = document.getElementById('clusters-grid');
  const empty = document.getElementById('clusters-empty');
  const container = document.getElementById('clusters-container');
  const detailView = document.getElementById('cluster-detail-view');

  // Stelle sicher, dass die Listenansicht aktiv ist
  container.classList.remove('hidden');
  detailView.classList.add('hidden');
  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');

  if (!systemConfig.faceRecognitionEnabled) {
    spinner.classList.add('hidden');
    empty.classList.remove('hidden');
    return;
  }

  try {
    const res = await fetch('/faces/clusters?include_preview=true');
    if (!res.ok) throw new Error(`Fehler beim Abruf der Cluster (${res.status})`);
    const clusters = await res.json();

    spinner.classList.add('hidden');
    allLoadedClusters = clusters;
    applyClusterFilters();

  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler beim Laden der Cluster: ${err.message}`, true);
  }
}

function openClusterDetail(cluster) {
  activeCluster = cluster;
  const container = document.getElementById('clusters-container');
  const detailView = document.getElementById('cluster-detail-view');
  const title = document.getElementById('cd-title');
  const stats = document.getElementById('cd-stats');
  const input = document.getElementById('cluster-label-input');
  const imagesGrid = document.getElementById('cluster-images-grid');

  container.classList.add('hidden');
  detailView.classList.remove('hidden');

  const displayName = cluster.label || `Person ${cluster.cluster_id.replace('cluster_', '#')}`;
  title.textContent = displayName;
  stats.textContent = `${cluster.face_count} Vorkommen in historischen Scans (Cluster ID: ${cluster.cluster_id})`;
  input.value = cluster.label || '';

  imagesGrid.innerHTML = '';

  // Rendere jedes Archivbild dieses Clusters mit hervorgehobener Bounding Box
  cluster.faces.forEach((face, idx) => {
    if (!face.file_path) return;

    const card = document.createElement('div');
    card.className = 'bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg flex flex-col';

    const safePath = encodeURIComponent(face.file_path);
    const fileName = face.file_path.split('/').pop();

    card.innerHTML = `
      <div class="relative bg-slate-950 flex items-center justify-center p-2">
        <div class="bbox-container cursor-pointer" id="cluster-bbox-wrap-${idx}">
          <img
            src="/images/serve?path=${safePath}&max_dim=600"
            alt="${escapeHtml(fileName)}"
            class="rounded max-h-72 object-contain"
            id="cluster-img-${idx}"
          >
          <!-- Bounding Box Overlay will be positioned once image loads -->
        </div>
        <!-- Schnell-Dreh Button oben rechts auf dem Bild -->
        <button
          type="button"
          onclick="rotateClusterCardImage(event, '${escapeHtml(face.file_path).replace(/'/g, "\\'")}', 90, ${idx})"
          class="absolute top-3 right-3 p-1.5 rounded-lg bg-slate-900/80 hover:bg-amber-500 hover:text-slate-950 text-slate-300 border border-slate-700/80 transition-all shadow-md backdrop-blur-sm z-20"
          title="Bild 90° im Uhrzeigersinn drehen (verlustfrei)"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
            <path d="M21 3v5h-5"></path>
          </svg>
        </button>
      </div>
      <div class="p-3 border-t border-slate-800 flex items-center justify-between text-xs gap-2">
        <div class="truncate max-w-[170px]">
          <span class="font-medium text-slate-200 truncate block">${escapeHtml(fileName)}</span>
          <span class="text-slate-500 font-mono text-[11px]">Konfidenz: ${(face.det_score * 100).toFixed(1)}%</span>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <!-- Verlustfreies Drehen Buttons direkt in der Cluster-Karte -->
          <div class="flex items-center rounded-lg bg-slate-800 border border-slate-700 p-0.5 shadow-sm" title="Verlustfreies Drehen (JPEG DCT / Lossless)">
            <button
              type="button"
              onclick="rotateClusterCardImage(event, '${escapeHtml(face.file_path).replace(/'/g, "\\'")}', -90, ${idx})"
              class="px-2 py-1 text-slate-300 hover:text-amber-400 text-[11px] font-medium transition"
              title="90° gegen den Uhrzeigersinn drehen"
            >
              ↺ 90°
            </button>
            <div class="w-[1px] h-3 bg-slate-700"></div>
            <button
              type="button"
              onclick="rotateClusterCardImage(event, '${escapeHtml(face.file_path).replace(/'/g, "\\'")}', 90, ${idx})"
              class="px-2 py-1 text-slate-300 hover:text-amber-400 text-[11px] font-medium transition"
              title="90° im Uhrzeigersinn drehen"
            >
              ↻ 90°
            </button>
          </div>
          <button
            onclick="openImageModal('${escapeHtml(face.file_path)}', '${escapeHtml(fileName)}')"
            class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] font-medium transition"
          >
            Großansicht
          </button>
          <button
            onclick="handleRemoveFaceFromCluster('${escapeHtml(face.face_id)}', this)"
            title="Gesicht aus diesem Cluster entfernen (Nicht diese Person)"
            class="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 hover:border-rose-500/40 rounded-lg text-[11px] font-medium transition flex items-center gap-1"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
            <span class="hidden sm:inline">Entfernen</span>
          </button>
        </div>
      </div>
    `;

    imagesGrid.appendChild(card);

    // Bounding Box über dem Bild positionieren
    const imgElem = card.querySelector(`#cluster-img-${idx}`);
    const wrapElem = card.querySelector(`#cluster-bbox-wrap-${idx}`);

    function renderBox() {
      wrapElem.querySelectorAll('.face-bbox').forEach(e => e.remove());

      let left, top, width, height;

      if (face.bbox_percent) {
        left = face.bbox_percent.left;
        top = face.bbox_percent.top;
        width = face.bbox_percent.width;
        height = face.bbox_percent.height;
      } else if (face.orig_width && face.orig_height && face.bbox && face.bbox.length === 4) {
        const [x1, y1, x2, y2] = face.bbox;
        left = (x1 / face.orig_width) * 100;
        top = (y1 / face.orig_height) * 100;
        width = ((x2 - x1) / face.orig_width) * 100;
        height = ((y2 - y1) / face.orig_height) * 100;
      } else if (face.file_path) {
        // Robuster Fallback: Bild-Details abrufen, um exakte Prozent-Koordinaten zu erhalten
        fetch(`/images/details?path=${encodeURIComponent(face.file_path)}`)
          .then(r => r.json())
          .then(d => {
            if (d.faces && d.faces.length > 0) {
              const matched = d.faces.find(f => f.face_id === face.face_id) || d.faces[0];
              if (matched && matched.bbox_percent) {
                face.bbox_percent = matched.bbox_percent;
                renderBox();
              }
            }
          })
          .catch(() => {});
        return;
      } else {
        return;
      }

      const box = document.createElement('div');
      box.className = 'face-bbox active';
      box.style.position = 'absolute';
      box.style.border = '2px solid #f59e0b';
      box.style.zIndex = '15';
      box.style.pointerEvents = 'none';
      box.style.left = `${left}%`;
      box.style.top = `${top}%`;
      box.style.width = `${width}%`;
      box.style.height = `${height}%`;

      const tag = document.createElement('div');
      tag.className = 'face-bbox-tag';
      tag.textContent = cluster.label || 'Diese Person';
      box.appendChild(tag);

      wrapElem.appendChild(box);
    }

    renderBox();
    if (!imgElem.complete) {
      imgElem.addEventListener('load', renderBox, { once: true });
    }

    // Klick auf das Bild öffnet das große Modal
    wrapElem.addEventListener('click', () => openImageModal(face.file_path, fileName));
  });
}

function closeClusterDetail() {
  activeCluster = null;
  loadClusters();
}

async function rotateClusterCardImage(event, filePath, angle, idx) {
  event.stopPropagation();
  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="animate-spin inline-block">⏳</span>';

  try {
    showToast(`Drehe Bild um ${angle > 0 ? '+' : ''}${angle}° verlustfrei...`, false);
    const result = await rotateImageFile(filePath, angle);
    if (!result || !result.success) throw new Error(result?.message || 'Drehung fehlgeschlagen');

    const ts = Date.now();
    const imgElem = document.getElementById(`cluster-img-${idx}`);
    const wrapElem = document.getElementById(`cluster-bbox-wrap-${idx}`);

    if (imgElem) {
      let baseSrc = imgElem.src.split('&t=')[0].split('?t=')[0];
      const sep = baseSrc.includes('?') ? '&' : '?';
      imgElem.src = `${baseSrc}${sep}t=${ts}`;

      // Bounding-Box nach Bildladung neu aus der API ermitteln
      const updateBoxes = () => {
        fetch(`/images/details?path=${encodeURIComponent(filePath)}&t=${ts}`)
          .then(r => r.json())
          .then(d => {
            if (wrapElem) {
              wrapElem.querySelectorAll('.face-bbox').forEach(e => e.remove());
              if (d.faces && d.faces.length > 0) {
                d.faces.forEach((f) => {
                  let left, top, width, height;
                  if (f.bbox_percent) {
                    left = f.bbox_percent.left;
                    top = f.bbox_percent.top;
                    width = f.bbox_percent.width;
                    height = f.bbox_percent.height;
                  } else if (f.bbox && f.bbox.length === 4 && d.width && d.height) {
                    const [x1, y1, x2, y2] = f.bbox;
                    left = (x1 / d.width) * 100;
                    top = (y1 / d.height) * 100;
                    width = ((x2 - x1) / d.width) * 100;
                    height = ((y2 - y1) / d.height) * 100;
                  } else {
                    return;
                  }
                  const box = document.createElement('div');
                  box.className = 'face-bbox active';
                  box.style.position = 'absolute';
                  box.style.border = '2px solid #f59e0b';
                  box.style.zIndex = '15';
                  box.style.pointerEvents = 'none';
                  box.style.left = `${left}%`;
                  box.style.top = `${top}%`;
                  box.style.width = `${width}%`;
                  box.style.height = `${height}%`;

                  const tag = document.createElement('div');
                  tag.className = 'face-bbox-tag';
                  tag.textContent = activeCluster?.label || 'Diese Person';
                  box.appendChild(tag);
                  wrapElem.appendChild(box);
                });
              }
            }
          })
          .catch(() => {});
      };

      if (imgElem.complete) {
        updateBoxes();
      } else {
        imgElem.addEventListener('load', updateBoxes, { once: true });
      }
    }

    updateAllThumbnailsOnPage(filePath, ts);
    showToast(`✓ Bild in Clusteransicht verlustfrei gedreht (${result.faces_detected} Gesichter erkannt)`, false);
  } catch (err) {
    showToast(`Fehler beim Drehen: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
  }
}

async function handleClusterLabelSubmit(e) {
  e.preventDefault();
  if (!activeCluster) return;

  const input = document.getElementById('cluster-label-input');
  const label = input.value.trim();
  if (!label) return;

  try {
    const res = await fetch(`/faces/clusters/${encodeURIComponent(activeCluster.cluster_id)}/label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    });

    if (!res.ok) throw new Error(`Fehler beim Speichern (${res.status})`);
    const data = await res.json();

    activeCluster.label = label;
    const target = allLoadedClusters.find(c => c.cluster_id === activeCluster.cluster_id);
    if (target) target.label = label;
    updateClusterCounts();
    document.getElementById('cd-title').textContent = label;
    showToast(`Name "${label}" für ${data.updated_faces} Gesichter gespeichert!`);
  } catch (err) {
    showToast(`Fehler: ${err.message}`, true);
  }
}

async function handleRemoveFaceFromCluster(faceId, btnElement) {
  if (!confirm('Möchten Sie dieses Gesicht wirklich aus dem Personen-Cluster entfernen ("Nicht diese Person")?')) {
    return;
  }

  btnElement.disabled = true;
  try {
    const res = await fetch(`/faces/${encodeURIComponent(faceId)}/remove-from-cluster`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Fehler (${res.status})`);

    const card = btnElement.closest('.bg-slate-900');
    if (card) {
      card.style.transition = 'all 0.3s ease';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.92)';
      setTimeout(() => {
        card.remove();
        if (activeCluster) {
          activeCluster.faces = (activeCluster.faces || []).filter(f => f.face_id !== faceId);
          activeCluster.face_count = activeCluster.faces.length;
          document.getElementById('cd-stats').textContent = `${activeCluster.face_count} Vorkommen in historischen Scans (Cluster ID: ${activeCluster.cluster_id})`;

          const target = allLoadedClusters.find(c => c.cluster_id === activeCluster.cluster_id);
          if (target) {
            target.faces = activeCluster.faces;
            target.face_count = activeCluster.face_count;
          }
          updateClusterCounts();

          if (activeCluster.face_count === 0) {
            showToast('Cluster enthält keine Gesichter mehr und wurde aufgelöst.');
            closeClusterDetail();
          }
        }
      }, 300);
    }
    showToast('Gesicht erfolgreich aus dem Personen-Cluster entfernt.');
  } catch (err) {
    btnElement.disabled = false;
    showToast(`Fehler beim Entfernen: ${err.message}`, true);
  }
}

function openMergeClusterModal() {
  if (!activeCluster) return;

  const modal = document.getElementById('cluster-merge-modal');
  const sourceInfo = document.getElementById('merge-source-info');
  const targetSelect = document.getElementById('merge-target-select');

  const sourceDisplayName = activeCluster.label || `Person ${activeCluster.cluster_id.replace('cluster_', '#')}`;
  sourceInfo.textContent = `${sourceDisplayName} (${activeCluster.cluster_id}, ${activeCluster.face_count} Gesichter)`;

  // Andere Cluster herausfiltern
  const otherClusters = allLoadedClusters.filter(c => c.cluster_id !== activeCluster.cluster_id);
  if (otherClusters.length === 0) {
    showToast('Keine weiteren Personen-Cluster vorhanden zum Zusammenführen.', true);
    return;
  }

  targetSelect.innerHTML = otherClusters.map(c => {
    const cName = c.label ? `${c.label} (${c.cluster_id})` : `Person ${c.cluster_id.replace('cluster_', '#')}`;
    return `<option value="${escapeHtml(c.cluster_id)}">${escapeHtml(cName)} — ${c.face_count} Gesichter</option>`;
  }).join('');

  // Initialen Namen setzen
  handleMergeTargetChange();

  modal.classList.remove('hidden');
}

function handleMergeTargetChange() {
  const targetSelect = document.getElementById('merge-target-select');
  const nameInput = document.getElementById('merge-target-name-input');
  const selectedTargetId = targetSelect.value;
  const targetCluster = allLoadedClusters.find(c => c.cluster_id === selectedTargetId);

  // Bevorzuge Ziel-Label, sonst Quell-Label
  const suggestedLabel = (targetCluster && targetCluster.label) || (activeCluster && activeCluster.label) || '';
  nameInput.value = suggestedLabel;
}

function closeMergeClusterModal() {
  const modal = document.getElementById('cluster-merge-modal');
  modal.classList.add('hidden');
}

async function executeClusterMerge() {
  if (!activeCluster) return;

  const targetSelect = document.getElementById('merge-target-select');
  const nameInput = document.getElementById('merge-target-name-input');
  const confirmBtn = document.getElementById('confirm-merge-btn');

  const targetClusterId = targetSelect.value;
  const targetLabel = nameInput.value.trim();

  if (!targetClusterId) {
    showToast('Bitte wählen Sie ein Ziel-Cluster aus.', true);
    return;
  }

  confirmBtn.disabled = true;
  confirmBtn.classList.add('opacity-50');

  try {
    const res = await fetch('/faces/clusters/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_cluster_id: activeCluster.cluster_id,
        target_cluster_id: targetClusterId,
        target_label: targetLabel || null,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Serverfehler (${res.status})`);
    }

    const data = await res.json();
    closeMergeClusterModal();
    showToast(`Cluster erfolgreich zusammengeführt! Insgesamt ${data.total_faces} Gesichter nun unter "${data.label || data.target_cluster_id}".`);

    // Cluster neu laden und zur Übersicht zurückkehren
    closeClusterDetail();
  } catch (err) {
    showToast(`Fehler beim Zusammenführen: ${err.message}`, true);
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.classList.remove('opacity-50');
  }
}


async function triggerClustering() {
  const btn = document.getElementById('run-clustering-btn');
  btn.disabled = true;
  btn.classList.add('opacity-50');

  try {
    const res = await fetch('/faces/clusters/run', { method: 'POST' });
    if (!res.ok) throw new Error(`Serverfehler (${res.status})`);
    const data = await res.json();

    showToast(`DBSCAN abgeschlossen: ${data.clusters_found} Personen-Cluster (${data.clustered_faces} Gesichter zugeordnet).`);
    loadClusters();
  } catch (err) {
    showToast(`Clustering fehlgeschlagen: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.classList.remove('opacity-50');
  }
}

// --- 3. Bild-Detailansicht (Modal) mit Bounding-Boxen ---

async function openImageModal(filePath, fileName, cacheBuster = null) {
  const modal = document.getElementById('image-modal');
  const img = document.getElementById('modal-img');
  const title = document.getElementById('modal-filename');
  const pathElem = document.getElementById('modal-filepath');
  const rawLink = document.getElementById('modal-raw-link');
  const similarBtn = document.getElementById('modal-similar-btn');
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const facesList = document.getElementById('modal-faces-list');

  currentModalImageDetails = { filePath, fileName };
  toggleCropMode(false);

  title.textContent = fileName || filePath.split('/').pop();
  pathElem.textContent = filePath;
  const cbParam = cacheBuster ? `&t=${cacheBuster}` : '';
  rawLink.href = `/images/serve?path=${encodeURIComponent(filePath)}${cbParam}`;

  // Vorherige Bounding Boxes und Tags leeren
  wrapper.querySelectorAll('.face-bbox').forEach(e => e.remove());
  facesList.innerHTML = '<span class="text-slate-500 font-mono">Lade Merkmale...</span>';

  // Ähnlichkeitssuche Button Event
  similarBtn.onclick = () => {
    closeImageModal();
    searchSimilarImages(filePath);
  };

  // Bildquelle setzen
  img.src = `/images/serve?path=${encodeURIComponent(filePath)}&max_dim=1200${cbParam}`;

  // Duplikats- & Variantenprüfung im Hintergrund
  checkModalImageVariants(filePath);

  modal.classList.remove('hidden');

  const metaContainer = document.getElementById('modal-metadata-content');
  if (metaContainer) {
    metaContainer.innerHTML = '<span class="text-slate-500 font-mono">Lade Archiv-Metadaten...</span>';
  }

  // Lade Gesichtsdetails und Metadaten aus der Datenbank
  try {
    const res = await fetch(`/images/details?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) return;
    const data = await res.json();

    // Titel anpassen, falls archivalischer Titel vorhanden ist
    if (data.metadata && data.metadata.title) {
      title.textContent = data.metadata.title;
      pathElem.textContent = `${fileName} • ${filePath}`;
    }

    // Archivalische Metadaten Seitenleiste befüllen
    if (metaContainer) {
      const meta = data.metadata || {};
      let metaHtml = '';

      if (meta.title) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Titel / Bezeichnung</span>
            <span class="text-slate-200 font-medium text-xs">${escapeHtml(meta.title)}</span>
          </div>`;
      }
      if (meta.date) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Datierung</span>
            <span class="text-amber-400 font-mono text-xs">${escapeHtml(meta.date)}</span>
          </div>`;
      }
      if (meta.creator) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Urheber / Fotograf</span>
            <span class="text-slate-200 text-xs">${escapeHtml(meta.creator)}</span>
          </div>`;
      }
      if (meta.signature) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Archivsignatur</span>
            <span class="text-slate-300 font-mono text-xs bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60 inline-block">${escapeHtml(meta.signature)}</span>
          </div>`;
      }
      if (data.width && data.height) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Auflösung</span>
            <span class="text-slate-400 font-mono text-xs">${data.width} &times; ${data.height} px</span>
          </div>`;
      }
      if (meta.description) {
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Beschreibung</span>
            <p class="text-slate-300 leading-relaxed text-[11px] bg-slate-950/40 p-2 rounded-lg border border-slate-800/80 max-h-28 overflow-y-auto">${escapeHtml(meta.description)}</p>
          </div>`;
      }
      if (meta.keywords && meta.keywords.length > 0) {
        const chips = meta.keywords.map(kw => `
          <button onclick="setQueryAndSearch('${escapeHtml(kw)}'); closeImageModal();" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-amber-500/20 hover:text-amber-400 border border-slate-700 hover:border-amber-500/40 text-slate-300 font-mono text-[10px] transition" title="Nach '#${escapeHtml(kw)}' suchen">
            #${escapeHtml(kw)}
          </button>
        `).join('');
        metaHtml += `
          <div>
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block mb-1">Schlagwörter</span>
            <div class="flex flex-wrap gap-1">${chips}</div>
          </div>`;
      }
      if (meta.copyright) {
        metaHtml += `
          <div class="pt-2 border-t border-slate-800/80">
            <span class="text-slate-500 text-[10px] uppercase tracking-wider block">Rechte / Lizenz</span>
            <span class="text-slate-400 text-[10px] leading-tight block">${escapeHtml(meta.copyright)}</span>
          </div>`;
      }

      if (!metaHtml) {
        metaHtml = `
          <div class="text-center py-6 text-slate-500 space-y-1">
            <p class="text-[11px]">Keine EXIF-, IPTC- oder Sidecar-Metadaten hinterlegt.</p>
            <p class="text-[10px] text-slate-600">Legen Sie z. B. eine <code class="font-mono text-amber-500/70">${escapeHtml(fileName)}.json</code> an.</p>
          </div>`;
      }

      metaContainer.innerHTML = metaHtml;
    }

    facesList.innerHTML = '';
    if (!data.faces || data.faces.length === 0) {
      facesList.innerHTML = '<span class="text-slate-500">Keine Gesichter detektiert</span>';
    } else {
      data.faces.forEach((f, idx) => {
        const tag = document.createElement('span');
        tag.className = 'px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[11px]';
        const name = f.label || (f.cluster_id ? `Person ${f.cluster_id.replace('cluster_', '#')}` : `Gesicht #${idx + 1}`);
        tag.textContent = `${name} (${(f.det_score * 100).toFixed(0)}%)`;
        facesList.appendChild(tag);
      });
    }

    // Bounding Boxes auf dem vergrößerten Bild platzieren
    function drawModalBoxes() {
      wrapper.querySelectorAll('.face-bbox').forEach(e => e.remove());
      if (!data.faces || data.faces.length === 0) return;

      data.faces.forEach((f, idx) => {
        let left, top, width, height;

        if (f.bbox_percent) {
          left = f.bbox_percent.left;
          top = f.bbox_percent.top;
          width = f.bbox_percent.width;
          height = f.bbox_percent.height;
        } else if (f.bbox && f.bbox.length === 4) {
          const origW = f.orig_width || data.width || img.naturalWidth;
          const origH = f.orig_height || data.height || img.naturalHeight;
          if (!origW || !origH) return;
          const [x1, y1, x2, y2] = f.bbox;
          left = (x1 / origW) * 100;
          top = (y1 / origH) * 100;
          width = ((x2 - x1) / origW) * 100;
          height = ((y2 - y1) / origH) * 100;
        } else {
          return;
        }

        const box = document.createElement('div');
        box.className = 'face-bbox';
        box.style.position = 'absolute';
        box.style.border = '2px solid #38bdf8';
        box.style.zIndex = '15';
        box.style.pointerEvents = 'none';
        box.style.left = `${left}%`;
        box.style.top = `${top}%`;
        box.style.width = `${width}%`;
        box.style.height = `${height}%`;

        const tag = document.createElement('div');
        tag.className = 'face-bbox-tag';
        tag.textContent = f.label || (f.cluster_id ? `Person ${f.cluster_id.replace('cluster_', '#')}` : `Gesicht #${idx + 1}`);
        box.appendChild(tag);

        wrapper.appendChild(box);
      });
    }

    drawModalBoxes();
    if (!img.complete) {
      img.addEventListener('load', drawModalBoxes, { once: true });
    }

  } catch (err) {
    facesList.innerHTML = '<span class="text-rose-400">Details nicht geladen</span>';
  }
}

function closeImageModal() {
  const modal = document.getElementById('image-modal');
  modal.classList.add('hidden');
  toggleCropMode(false);
  currentModalImageDetails = null;
}

// Schließe Modal bei Klick auf den Hintergrund
document.getElementById('image-modal')?.addEventListener('click', (e) => {
  if (e.target.id === 'image-modal') {
    closeImageModal();
  }
});

// Tastatur-Shortcut ESC zum Schließen
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeImageModal();
  }
});

// ================= VERLUSTFREIES DREHEN =================

let isRotatingImage = false;

async function rotateImageFile(filePath, angle = 90) {
  if (isRotatingImage) return null;
  isRotatingImage = true;
  try {
    const res = await fetch('/images/rotate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: filePath, angle: angle }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Fehler beim Drehen' }));
      throw new Error(err.detail || `Serverfehler (${res.status})`);
    }

    const data = await res.json();
    return data;
  } finally {
    isRotatingImage = false;
  }
}

async function rotateCurrentModalImage(angle = 90) {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein Bild im Modal geöffnet', true);
    return;
  }
  const filePath = currentModalImageDetails.filePath;
  const fileName = currentModalImageDetails.fileName;
  const leftBtn = document.getElementById('modal-rotate-left-btn');
  const rightBtn = document.getElementById('modal-rotate-right-btn');
  const activeBtn = angle < 0 ? leftBtn : rightBtn;
  const originalHtml = activeBtn ? activeBtn.innerHTML : '';

  try {
    if (activeBtn) {
      activeBtn.disabled = true;
      activeBtn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Drehe...</span>';
    }
    showToast(`Drehe Bild verlustfrei um ${angle > 0 ? '+' : ''}${angle}°...`, false);

    const result = await rotateImageFile(filePath, angle);
    if (!result || !result.success) {
      throw new Error(result?.message || 'Drehung fehlgeschlagen');
    }

    const timestamp = Date.now();
    // Modal-Inhalt komplett mit Cache-Buster neu laden
    await openImageModal(filePath, fileName, timestamp);

    // Alle Thumbnails auf der Seite synchronisieren
    updateAllThumbnailsOnPage(filePath, timestamp);

    const methodNote = result.rotation_method === 'lossless_jpegtran_dct' ? ' (100% verlustfreies DCT-Transponieren)' : '';
    showToast(`✓ Bild verlustfrei um ${angle}° gedreht${methodNote} • ${result.faces_detected} Gesichter erkannt`, false);
  } catch (err) {
    showToast(`Fehler beim Drehen: ${err.message}`, true);
  } finally {
    if (activeBtn) {
      activeBtn.disabled = false;
      activeBtn.innerHTML = originalHtml;
    }
  }
}

async function quickRotateCardImage(event, filePath, angle = 90) {
  event.stopPropagation();
  try {
    showToast(`Drehe Bild verlustfrei um ${angle}°...`, false);
    const result = await rotateImageFile(filePath, angle);
    if (!result || !result.success) {
      throw new Error(result?.message || 'Drehung fehlgeschlagen');
    }
    const timestamp = Date.now();
    updateAllThumbnailsOnPage(filePath, timestamp);
    showToast(`✓ Bild verlustfrei gedreht (${result.faces_detected} Gesichter neu erfasst)`, false);
  } catch (err) {
    showToast(`Fehler beim Drehen: ${err.message}`, true);
  }
}

function updateAllThumbnailsOnPage(filePath, timestamp) {
  const encPath = encodeURIComponent(filePath);
  document.querySelectorAll('img').forEach(imgElem => {
    if (imgElem.src && (imgElem.src.includes(encPath) || imgElem.src.includes(filePath))) {
      let baseSrc = imgElem.src.split('&t=')[0].split('?t=')[0];
      const separator = baseSrc.includes('?') ? '&' : '?';
      imgElem.src = `${baseSrc}${separator}t=${timestamp}`;
    }
  });
}

// Ähnliche Bilder via CLIP suchen
async function searchSimilarImages(filePath) {
  switchTab('search');
  const spinner = document.getElementById('search-spinner');
  const grid = document.getElementById('results-grid');
  const empty = document.getElementById('search-empty');
  const resultsBar = document.getElementById('results-bar');
  const resultsCount = document.getElementById('results-count');
  const resultsQuery = document.getElementById('results-query');

  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');
  resultsBar.classList.add('hidden');

  const stackToggle = document.getElementById('search-stack-variants');
  const stackVariants = stackToggle ? stackToggle.checked : true;

  try {
    const res = await fetch(`/search/similar?image_path=${encodeURIComponent(filePath)}&limit=20&stack_variants=${stackVariants}`);
    if (!res.ok) throw new Error(`Fehler bei der Ähnlichkeitssuche (${res.status})`);
    const data = await res.json();

    spinner.classList.add('hidden');
    resultsBar.classList.remove('hidden');
    resultsCount.textContent = `${data.length} optisch ähnliche Bilder`;
    resultsQuery.textContent = `Referenz: "${filePath.split('/').pop()}"`;

    if (data.length === 0) {
      empty.classList.remove('hidden');
      return;
    }

    renderSearchResults(data, grid);
    showToast('Ähnliche Bilder via CLIP gefunden.');
  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler: ${err.message}`, true);
  }
}

// --- Crop-to-Search (Bildausschnitt-Suche / ROI) ---

let isCropMode = false;
let isDrawingCrop = false;
let cropStart = { x: 0, y: 0 };
let currentCropBox = null;

function toggleCropMode(forcedState) {
  const btn = document.getElementById('modal-crop-btn');
  const btnText = document.getElementById('modal-crop-btn-text');
  const layer = document.getElementById('crop-selection-layer');
  const box = document.getElementById('crop-selection-box');
  const hint = document.getElementById('crop-mode-hint');

  if (typeof forcedState === 'boolean') {
    isCropMode = forcedState;
  } else {
    isCropMode = !isCropMode;
  }

  if (isCropMode) {
    if (btn) {
      btn.classList.add('bg-amber-500', 'text-slate-950', 'border-amber-400', 'font-semibold');
      btn.classList.remove('bg-slate-800', 'text-slate-300', 'border-slate-700');
    }
    if (btnText) btnText.textContent = 'Modus beenden';
    if (layer) layer.classList.remove('hidden');
    if (hint) hint.classList.remove('hidden');
    cancelCropSelection();
  } else {
    if (btn) {
      btn.classList.remove('bg-amber-500', 'text-slate-950', 'border-amber-400', 'font-semibold');
      btn.classList.add('bg-slate-800', 'text-slate-300', 'border-slate-700');
    }
    if (btnText) btnText.textContent = 'Ausschnitt suchen';
    if (layer) layer.classList.add('hidden');
    if (box) box.classList.add('hidden');
    if (hint) hint.classList.add('hidden');
    currentCropBox = null;
    isDrawingCrop = false;
  }
}

function setupCropInteraction() {
  const layer = document.getElementById('crop-selection-layer');
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const img = document.getElementById('modal-img');
  const box = document.getElementById('crop-selection-box');
  const actionsBar = document.getElementById('crop-actions-bar');

  if (!layer || !wrapper || !img || !box) return;

  function getImageMetrics() {
    const imgRect = img.getBoundingClientRect();
    const wrapperRect = wrapper.getBoundingClientRect();
    return {
      imgRect,
      wrapperRect,
      leftInWrapper: imgRect.left - wrapperRect.left,
      topInWrapper: imgRect.top - wrapperRect.top,
      width: imgRect.width,
      height: imgRect.height
    };
  }

  layer.addEventListener('mousedown', (e) => {
    if (!isCropMode) return;
    if (e.button !== 0) return; // nur linke Maustaste
    e.preventDefault();

    const m = getImageMetrics();
    if (m.width <= 0 || m.height <= 0) return;

    const relX = Math.max(0, Math.min(m.width, e.clientX - m.imgRect.left));
    const relY = Math.max(0, Math.min(m.height, e.clientY - m.imgRect.top));

    cropStart = { x: relX, y: relY };
    isDrawingCrop = true;
    currentCropBox = null;

    box.style.left = `${m.leftInWrapper + relX}px`;
    box.style.top = `${m.topInWrapper + relY}px`;
    box.style.width = '0px';
    box.style.height = '0px';
    box.classList.remove('hidden');
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDrawingCrop || !isCropMode) return;
    e.preventDefault();

    const m = getImageMetrics();
    const curX = Math.max(0, Math.min(m.width, e.clientX - m.imgRect.left));
    const curY = Math.max(0, Math.min(m.height, e.clientY - m.imgRect.top));

    const minX = Math.min(cropStart.x, curX);
    const minY = Math.min(cropStart.y, curY);
    const w = Math.abs(curX - cropStart.x);
    const h = Math.abs(curY - cropStart.y);

    box.style.left = `${m.leftInWrapper + minX}px`;
    box.style.top = `${m.topInWrapper + minY}px`;
    box.style.width = `${w}px`;
    box.style.height = `${h}px`;

    // Positioniere Aktionsleiste oberhalb oder unterhalb je nach Platz
    if (actionsBar) {
      if (m.topInWrapper + minY + h + 48 > m.wrapperRect.height) {
        actionsBar.style.bottom = 'auto';
        actionsBar.style.top = '-44px';
      } else {
        actionsBar.style.top = 'auto';
        actionsBar.style.bottom = '-44px';
      }
    }
  });

  window.addEventListener('mouseup', (e) => {
    if (!isDrawingCrop) return;
    isDrawingCrop = false;

    const m = getImageMetrics();
    const curX = Math.max(0, Math.min(m.width, e.clientX - m.imgRect.left));
    const curY = Math.max(0, Math.min(m.height, e.clientY - m.imgRect.top));

    const minX = Math.min(cropStart.x, curX);
    const minY = Math.min(cropStart.y, curY);
    const w = Math.abs(curX - cropStart.x);
    const h = Math.abs(curY - cropStart.y);

    if (w < 10 || h < 10) {
      box.classList.add('hidden');
      currentCropBox = null;
      return;
    }

    currentCropBox = {
      x: minX / m.width,
      y: minY / m.height,
      width: w / m.width,
      height: h / m.height
    };
  });
}

function cancelCropSelection(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const box = document.getElementById('crop-selection-box');
  if (box) box.classList.add('hidden');
  currentCropBox = null;
  isDrawingCrop = false;
}

function executeCropSearch(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  if (!currentCropBox) {
    showToast('Bitte ziehen Sie zuerst einen Rahmen um das gewünschte Bilddetail auf.', true);
    return;
  }
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein Bild für die Ausschnitt-Suche aktiv.', true);
    return;
  }

  const { filePath, fileName } = currentModalImageDetails;
  const cropData = { ...currentCropBox };

  closeImageModal();
  searchByCrop(filePath, cropData, fileName);
}

async function searchByCrop(filePath, cropBox, fileName) {
  switchTab('search');
  const spinner = document.getElementById('search-spinner');
  const grid = document.getElementById('results-grid');
  const empty = document.getElementById('search-empty');
  const resultsBar = document.getElementById('results-bar');
  const resultsCount = document.getElementById('results-count');
  const resultsQuery = document.getElementById('results-query');

  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');
  resultsBar.classList.add('hidden');

  try {
    const stackToggle = document.getElementById('search-stack-variants');
    const stackVariants = stackToggle ? stackToggle.checked : true;

    const res = await fetch('/search/crop', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        image_path: filePath,
        x: cropBox.x,
        y: cropBox.y,
        width: cropBox.width,
        height: cropBox.height,
        is_normalized: true,
        limit: 24,
        stack_variants: stackVariants
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Fehler bei der Bildausschnitt-Suche (${res.status})`);
    }

    const data = await res.json();
    spinner.classList.add('hidden');
    resultsBar.classList.remove('hidden');

    const pctW = Math.round(cropBox.width * 100);
    const pctH = Math.round(cropBox.height * 100);
    const displayName = fileName || filePath.split('/').pop();

    resultsCount.textContent = `${data.length} optisch ähnliche Treffer`;
    resultsQuery.textContent = `Ausschnitt aus "${displayName}" (${pctW}% × ${pctH}%)`;

    if (data.length === 0) {
      empty.classList.remove('hidden');
      return;
    }

    renderSearchResults(data, grid);
    showToast(`Bildausschnitt-Suche erfolgreich (${data.length} Treffer)`);
  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler: ${err.message}`, true);
  }
}

// --- Hilfsfunktionen ---

function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toast-message');
  const toastIcon = document.getElementById('toast-icon');

  toastMsg.textContent = msg;

  if (isError) {
    toastIcon.className = 'w-6 h-6 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0';
    toastIcon.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
  } else {
    toastIcon.className = 'w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0';
    toastIcon.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
  }

  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// --- 4. Archiv-Bestände einbinden & Upload-Logik ---

function setupDropzone() {
  const dropzone = document.getElementById('upload-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('border-amber-500', 'bg-amber-500/10');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-amber-500', 'bg-amber-500/10');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      uploadFilesDirectly(files);
    }
  });
}

async function loadRegisteredFolders() {
  const container = document.getElementById('registered-folders-list');
  if (!container) return;

  try {
    const res = await fetch('/api/archive/registered-folders');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const allowed = data.allowed_dirs || [];
    if (allowed.length === 0) {
      container.innerHTML = `<span class="text-slate-500">Keine Pfade registriert</span>`;
      return;
    }

    container.innerHTML = allowed.map(dir => {
      const isPrimary = dir === data.primary_dir;
      return `
        <span class="px-2.5 py-1 rounded-lg ${isPrimary ? 'bg-amber-500/10 border-amber-500/30 text-amber-300' : 'bg-slate-800 border-slate-700 text-slate-300'} border flex items-center gap-1.5" title="${escapeHtml(dir)}">
          <svg class="w-3.5 h-3.5 ${isPrimary ? 'text-amber-400' : 'text-slate-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
          </svg>
          <span class="truncate max-w-xs sm:max-w-md">${escapeHtml(dir)}</span>
          ${isPrimary ? '<span class="text-[9px] uppercase px-1 py-0.2 bg-amber-500/20 text-amber-400 rounded">Primär</span>' : ''}
        </span>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<span class="text-rose-400">Fehler beim Laden: ${err.message}</span>`;
  }
}

async function scanFolderPreview() {
  const input = document.getElementById('folder-path-input');
  const recursive = document.getElementById('folder-recursive')?.checked ?? true;
  const preview = document.getElementById('folder-scan-preview');
  const status = document.getElementById('folder-index-status');

  const folderPath = input.value.trim();
  if (!folderPath) {
    showToast('Bitte geben Sie einen Verzeichnispfad an.', true);
    input.focus();
    return;
  }

  preview.classList.remove('hidden');
  preview.innerHTML = '<span class="text-slate-400 font-mono">Scanne Ordner...</span>';

  try {
    const res = await fetch('/api/archive/scan-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath, recursive }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    let samplesHtml = '';
    if (data.sample_files && data.sample_files.length > 0) {
      samplesHtml = `
        <div class="mt-2 pt-2 border-t border-slate-800 text-[11px] text-slate-400">
          <span class="font-medium text-slate-300 block mb-1">Beispieldateien:</span>
          <div class="flex flex-wrap gap-1 font-mono">
            ${data.sample_files.map(f => `<span class="bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">${escapeHtml(f)}</span>`).join('')}
            ${data.image_count > 10 ? `<span class="text-slate-500 self-center">+${data.image_count - 10} weitere</span>` : ''}
          </div>
        </div>
      `;
    }

    preview.innerHTML = `
      <div class="flex items-center justify-between text-slate-200">
        <span class="font-medium flex items-center gap-1.5 text-emerald-400">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
          Gültiges Verzeichnis gefunden
        </span>
        <span class="font-mono text-amber-400 font-semibold">${data.image_count} Bilddateien</span>
      </div>
      <div class="text-[11px] text-slate-400 font-mono">
        ${data.sidecar_count} .json-Sidecars gefunden
      </div>
      ${samplesHtml}
    `;

    if (status) {
      status.textContent = `${data.image_count} Bilder bereit`;
    }
  } catch (err) {
    preview.innerHTML = `
      <div class="text-rose-400 flex items-center gap-1.5">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        <span>${escapeHtml(err.message)}</span>
      </div>
    `;
    if (status) status.textContent = 'Fehler beim Scannen';
  }
}

let progressPollTimer = null;

async function checkIndexingProgress() {
  try {
    const res = await fetch('/api/archive/index-progress');
    if (!res.ok) return;
    const data = await res.json();

    const liveBox = document.getElementById('folder-live-progress');
    const preview = document.getElementById('folder-scan-preview');
    const percentSpan = document.getElementById('flp-percentage');
    const bar = document.getElementById('flp-bar');
    const countsSpan = document.getElementById('flp-counts');
    const facesSpan = document.getElementById('flp-faces');
    const curFileSpan = document.getElementById('flp-current-file');
    const btn = document.getElementById('start-folder-index-btn');
    const status = document.getElementById('folder-index-status');

    if (data.is_running) {
      if (liveBox) liveBox.classList.remove('hidden');
      if (preview) preview.classList.add('hidden');
      if (percentSpan) percentSpan.textContent = `${data.percent}%`;
      if (bar) bar.style.width = `${data.percent}%`;
      if (countsSpan) {
        countsSpan.textContent = `${data.processed_count} / ${data.total_found} Bilder (${data.new_indexed} neu, ${data.skipped} vorh.)`;
      }
      if (facesSpan) facesSpan.textContent = `${data.faces_detected} Gesichter`;
      if (curFileSpan) curFileSpan.textContent = data.current_file || 'Verarbeite...';

      if (btn && !btn.disabled) {
        btn.disabled = true;
        btn.classList.add('opacity-50');
      }
      if (status) status.textContent = `Indexierung läuft (${data.percent}%)...`;

      if (!progressPollTimer) {
        progressPollTimer = setInterval(checkIndexingProgress, 1000);
      }
    } else if (data.finished && data.processed_count > 0) {
      if (progressPollTimer) {
        clearInterval(progressPollTimer);
        progressPollTimer = null;
      }
      if (liveBox) liveBox.classList.add('hidden');
      if (btn) {
        btn.disabled = false;
        btn.classList.remove('opacity-50');
      }
      if (status) status.textContent = 'Indexierung abgeschlossen';

      if (preview) {
        preview.classList.remove('hidden');
        preview.innerHTML = `
          <div class="text-emerald-400 font-medium flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
            Indexierung erfolgreich abgeschlossen!
          </div>
          <div class="text-[11px] text-slate-300 font-mono mt-1 space-y-0.5">
            <p>&bull; Verarbeitet: <strong class="text-amber-400">${data.processed_count}</strong> Bilder (${data.new_indexed} neu, ${data.skipped} übersprungen)</p>
            <p>&bull; Erkannte Gesichter: <strong class="text-amber-400">${data.faces_detected}</strong></p>
          </div>
        `;
      }
      loadRegisteredFolders();
    }
  } catch (err) {
    // Stiller Fehler beim Polling
  }
}

async function startFolderIndexing() {
  const input = document.getElementById('folder-path-input');
  const recursive = document.getElementById('folder-recursive')?.checked ?? true;
  const skipExisting = document.getElementById('folder-skip-existing')?.checked ?? true;
  const btn = document.getElementById('start-folder-index-btn');
  const status = document.getElementById('folder-index-status');
  const preview = document.getElementById('folder-scan-preview');
  const liveBox = document.getElementById('folder-live-progress');

  const folderPath = input.value.trim();
  if (!folderPath) {
    showToast('Bitte geben Sie einen Verzeichnispfad an.', true);
    input.focus();
    return;
  }

  btn.disabled = true;
  btn.classList.add('opacity-50');
  const origBtnHtml = btn.innerHTML;
  btn.innerHTML = `
    <svg class="animate-spin w-4 h-4 text-slate-950" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
    <span>Indexiere Ordner...</span>
  `;

  if (status) status.textContent = 'Indexierung startet...';
  if (liveBox) liveBox.classList.remove('hidden');

  // Starte sofort das Live-Polling für den Fortschrittsbalken
  if (!progressPollTimer) {
    progressPollTimer = setInterval(checkIndexingProgress, 800);
  }

  try {
    const res = await fetch('/api/archive/index-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_path: folderPath,
        recursive: recursive,
        force: !skipExisting,
        cluster_faces: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast('Indexierung im Hintergrund gestartet.');
    loadRegisteredFolders();
    // Das Polling checkIndexingProgress() läuft im Hintergrund automatisch weiter!
  } catch (err) {
    showToast(`Start fehlgeschlagen: ${err.message}`, true);
    if (status) status.textContent = 'Fehlgeschlagen';
    if (liveBox) liveBox.classList.add('hidden');
    if (progressPollTimer) {
      clearInterval(progressPollTimer);
      progressPollTimer = null;
    }
    btn.disabled = false;
    btn.classList.remove('opacity-50');
    btn.innerHTML = origBtnHtml;
  }
}

function handleFileUpload(event) {
  const files = event.target.files;
  if (files && files.length > 0) {
    uploadFilesDirectly(files);
  }
}

async function uploadFilesDirectly(files) {
  const container = document.getElementById('upload-results-container');
  const subfolderInput = document.getElementById('upload-subfolder-input');
  const subfolder = subfolderInput ? subfolderInput.value.trim() : '';

  if (!files || files.length === 0) return;

  container.classList.remove('hidden');
  container.innerHTML = `
    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-2 text-slate-300">
      <svg class="animate-spin w-4 h-4 text-amber-400 flex-shrink-0" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span>Lade ${files.length} Datei(en) hoch und berechne Embeddings...</span>
    </div>
  `;

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }
  if (subfolder) {
    formData.append('subfolder', subfolder);
  }
  formData.append('enable_clustering', 'true');

  try {
    const res = await fetch('/api/archive/upload', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();

    let itemsHtml = '';
    if (data.items && data.items.length > 0) {
      itemsHtml = data.items.map(item => `
        <div class="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono">
          <span class="text-slate-200 truncate max-w-[200px]" title="${escapeHtml(item.file_name)}">${escapeHtml(item.file_name)}</span>
          <div class="flex items-center gap-2">
            <span class="text-emerald-400">Indexiert</span>
            ${item.faces_detected > 0 ? `<span class="text-amber-400 font-semibold">${item.faces_detected} Gesicht(er)</span>` : ''}
            <button onclick="openImageModal('${escapeHtml(item.file_path)}', '${escapeHtml(item.file_name)}')" class="text-amber-400 hover:underline">Öffnen &rarr;</button>
          </div>
        </div>
      `).join('');
    }

    container.innerHTML = `
      <div class="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center justify-between">
        <span>${data.uploaded_images} Bild(er) hochgeladen &amp; indexiert</span>
        ${data.faces_detected > 0 ? `<span>${data.faces_detected} Gesichter erfasst</span>` : ''}
      </div>
      <div class="space-y-1 mt-2">
        ${itemsHtml}
      </div>
    `;

    showToast(`${data.uploaded_images} Bild(er) erfolgreich hochgeladen und indexiert.`);

    // Dateieingabe zurücksetzen
    const fileInput = document.getElementById('file-upload-input');
    if (fileInput) fileInput.value = '';
  } catch (err) {
    container.innerHTML = `
      <div class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
        Upload fehlgeschlagen: ${escapeHtml(err.message)}
      </div>
    `;
    showToast(`Fehler beim Upload: ${err.message}`, true);
  }
}

/* ==========================================================================
   GRAFISCHER ORDNER-BROWSER (SERVER-VERZEICHNIS-AUSWAHL)
   ========================================================================== */

let currentBrowsePath = '';
let currentParentPath = null;

function openFolderBrowserModal(startPath) {
  const modal = document.getElementById('folder-browser-modal');
  if (!modal) return;
  modal.classList.remove('hidden');

  const inputVal = document.getElementById('folder-path-input')?.value.trim();
  const target = startPath || inputVal || '';
  browseToFolder(target);
}

function closeFolderBrowserModal() {
  const modal = document.getElementById('folder-browser-modal');
  if (modal) modal.classList.add('hidden');
}

async function browseToFolder(path) {
  const loading = document.getElementById('fb-loading');
  const dirsList = document.getElementById('fb-dirs-list');
  const emptyState = document.getElementById('fb-empty-state');
  const breadcrumbs = document.getElementById('fb-breadcrumbs');
  const quickLinks = document.getElementById('fb-quick-links');
  const upBtn = document.getElementById('fb-up-btn');
  const selectedPathSpan = document.getElementById('fb-selected-path');
  const imgBadge = document.getElementById('fb-image-badge');
  const imgBadgeText = document.getElementById('fb-image-badge-text');

  if (loading) loading.classList.remove('hidden');
  if (dirsList) dirsList.innerHTML = '';
  if (emptyState) emptyState.classList.add('hidden');
  if (imgBadge) imgBadge.classList.add('hidden');

  try {
    const url = `/api/archive/browse-folders?path=${encodeURIComponent(path || '')}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    currentBrowsePath = data.current_path;
    currentParentPath = data.parent_path;

    if (selectedPathSpan) {
      selectedPathSpan.textContent = currentBrowsePath;
      selectedPathSpan.title = currentBrowsePath;
    }

    if (upBtn) {
      upBtn.disabled = !currentParentPath;
    }

    // Quick links rendern
    if (quickLinks && data.quick_links) {
      quickLinks.innerHTML = data.quick_links.map(ql => {
        const isCurrent = ql.path === currentBrowsePath;
        let iconSvg = '';
        if (ql.icon === 'home') {
          iconSvg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>';
        } else if (ql.icon === 'server') {
          iconSvg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path>';
        } else if (ql.icon === 'folder') {
          iconSvg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>';
        } else {
          iconSvg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7c-2 0-3 1-3 3z"></path>';
        }
        return `
          <button
            type="button"
            onclick="browseToFolder('${escapeHtml(ql.path)}')"
            class="px-2.5 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              isCurrent
                ? 'bg-amber-500 text-slate-950 font-semibold'
                : 'bg-slate-850 hover:bg-slate-800 text-slate-300 border border-slate-750'
            }"
            title="${escapeHtml(ql.path)}"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">${iconSvg}</svg>
            <span>${escapeHtml(ql.label)}</span>
          </button>
        `;
      }).join('');
    }

    // Breadcrumbs rendern
    if (breadcrumbs && data.breadcrumbs) {
      breadcrumbs.innerHTML = data.breadcrumbs.map((b, idx) => {
        const isLast = idx === data.breadcrumbs.length - 1;
        return `
          <button
            type="button"
            onclick="browseToFolder('${escapeHtml(b.path)}')"
            class="hover:text-amber-400 transition ${isLast ? 'text-amber-400 font-bold' : 'text-slate-400'}"
            title="${escapeHtml(b.path)}"
          >
            ${escapeHtml(b.name)}
          </button>
          ${!isLast ? '<span class="text-slate-600">/</span>' : ''}
        `;
      }).join('');
    }

    // Bilder-Badge
    if (imgBadge && data.direct_images_count > 0) {
      imgBadge.classList.remove('hidden');
      if (imgBadgeText) {
        imgBadgeText.textContent = `${data.direct_images_count} Bilddatei(en) direkt in diesem Ordner`;
      }
    }

    // Unterverzeichnisse rendern
    if (dirsList) {
      if (!data.subdirectories || data.subdirectories.length === 0) {
        if (emptyState) emptyState.classList.remove('hidden');
      } else {
        dirsList.innerHTML = data.subdirectories.map(sub => `
          <div
            onclick="browseToFolder('${escapeHtml(sub.path)}')"
            class="group flex items-center justify-between p-2.5 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-amber-500/40 cursor-pointer transition select-none"
          >
            <div class="flex items-center gap-2.5 truncate">
              <div class="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center flex-shrink-0 group-hover:bg-amber-500 group-hover:text-slate-950 transition">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                </svg>
              </div>
              <span class="text-xs font-medium text-slate-200 group-hover:text-amber-300 transition truncate">
                ${escapeHtml(sub.name)}
              </span>
            </div>
            <div class="flex items-center gap-1.5 text-slate-500 group-hover:text-slate-300 text-xs">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
              </svg>
            </div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    if (dirsList) {
      dirsList.innerHTML = `
        <div class="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          <span>Fehler beim Öffnen: ${escapeHtml(err.message)}</span>
        </div>
      `;
    }
  } finally {
    if (loading) loading.classList.add('hidden');
  }
}

function browseFolderUp() {
  if (currentParentPath) {
    browseToFolder(currentParentPath);
  }
}

function confirmFolderSelection() {
  if (!currentBrowsePath) return;
  const input = document.getElementById('folder-path-input');
  if (input) {
    input.value = currentBrowsePath;
  }
  closeFolderBrowserModal();
  scanFolderPreview();
}

// Tastatur-Shortcut (ESC schließt Modal)
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const fbModal = document.getElementById('folder-browser-modal');
    if (fbModal && !fbModal.classList.contains('hidden')) {
      closeFolderBrowserModal();
    }
    const stModal = document.getElementById('stack-modal');
    if (stModal && !stModal.classList.contains('hidden')) {
      closeStackModal();
    }
  }
});

// --- 5. Duplikate & Bildstapel (Tab 4 & Modal Inspection) ---

let currentModalVariantsData = null;

function checkModalImageVariants(filePath) {
  const variantsBtn = document.getElementById('modal-variants-btn');
  const variantsCountBadge = document.getElementById('modal-variants-count');
  if (!variantsBtn || !variantsCountBadge) return;

  variantsCountBadge.textContent = '...';
  currentModalVariantsData = null;

  fetch(`/images/variants?path=${encodeURIComponent(filePath)}&limit=15`)
    .then(r => r.ok ? r.json() : null)
    .then(varData => {
      if (varData && varData.total_variants > 0) {
        variantsCountBadge.textContent = varData.total_variants;
        variantsBtn.classList.remove('bg-slate-800', 'text-slate-300');
        variantsBtn.classList.add('bg-amber-500/20', 'border-amber-500/60', 'text-amber-300');
        variantsBtn.title = `${varData.total_variants} Duplikate / Varianten im Bestand gefunden! Klicken zum Vergleichen.`;
        currentModalVariantsData = varData;
      } else {
        variantsCountBadge.textContent = '0';
        variantsBtn.classList.remove('bg-amber-500/20', 'border-amber-500/60', 'text-amber-300');
        variantsBtn.classList.add('bg-slate-800', 'text-slate-300');
        variantsBtn.title = 'Keine weiteren Varianten im Bestand gefunden.';
        currentModalVariantsData = null;
      }
    })
    .catch(() => {
      if (variantsCountBadge) variantsCountBadge.textContent = '0';
    });
}

function openVariantsForCurrentModal() {
  if (!currentModalVariantsData || !currentModalVariantsData.variants || currentModalVariantsData.variants.length === 0) {
    showToast('Keine weiteren Varianten zu diesem Bild im Bestand gefunden.');
    return;
  }

  const modal = document.getElementById('stack-modal');
  const title = document.getElementById('stack-modal-title');
  const subtitle = document.getElementById('stack-modal-subtitle');
  const itemsContainer = document.getElementById('stack-modal-items');
  const info = document.getElementById('stack-modal-info');

  const ref = currentModalVariantsData.reference_image;
  const allItems = [
    {
      ...ref,
      is_primary: true,
      variant_label: 'Referenzbild (Aktuell geöffnet)',
      variant_similarity: 1.0,
    },
    ...currentModalVariantsData.variants
  ];

  title.textContent = `Varianten & Duplikate: ${ref.file_name || 'Aufnahme'}`;
  subtitle.textContent = `${allItems.length} Aufnahmen im Archiv gefunden (${currentModalVariantsData.total_variants} Varianten)`;
  if (info) info.textContent = `Archivisch verlustfrei: Alle Varianten verbleiben im physischen Bestand.`;

  renderStackComparisonItems(allItems, itemsContainer);
  modal.classList.remove('hidden');
}

let currentArchiveDuplicateGroups = [];

async function loadArchiveDuplicates() {
  const grid = document.getElementById('dup-grid');
  const spinner = document.getElementById('dup-spinner');
  const epsSelect = document.getElementById('dup-filter-eps');
  const countText = document.getElementById('dup-showing-count');
  const statGroups = document.getElementById('dup-stat-groups');
  const statImages = document.getElementById('dup-stat-images');

  if (!grid || !spinner) return;

  grid.innerHTML = '';
  spinner.classList.remove('hidden');
  if (countText) countText.textContent = 'Analysiere Bildbestände...';

  const eps = epsSelect ? parseFloat(epsSelect.value) : 0.075;

  try {
    const res = await fetch(`/archive/variant-clusters?eps=${eps}&limit_groups=100`);
    if (!res.ok) throw new Error(`Fehler beim Laden (${res.status})`);
    const data = await res.json();

    currentArchiveDuplicateGroups = data.groups || [];
    spinner.classList.add('hidden');

    if (statGroups) statGroups.textContent = data.total_groups || 0;
    if (statImages) statImages.textContent = data.total_stacked_images || 0;
    if (countText) countText.textContent = `Zeige ${data.showing_groups || 0} von ${data.total_groups || 0} Stapeln`;

    if (!data.groups || data.groups.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full text-center py-16 text-slate-500">
          <p class="text-base text-slate-400 font-medium">Keine Duplikate oder Varianten gefunden</p>
          <p class="text-xs text-slate-500 mt-1">Alle archivierten Bilder sind optisch eindeutig oder die Empfindlichkeit ist zu streng.</p>
        </div>`;
      return;
    }

    renderDuplicateGroups(data.groups, grid);
  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler bei Duplikatsuche: ${err.message}`, true);
  }
}

function renderDuplicateGroups(groups, container) {
  container.innerHTML = '';
  groups.forEach((grp, idx) => {
    const card = document.createElement('div');
    const rep = grp.representative || {};
    const safePath = encodeURIComponent(rep.file_path || '');
    const title = rep.title || rep.file_name || `Stapel #${idx + 1}`;

    card.className = 'group bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl overflow-hidden shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 cursor-pointer flex flex-col stack-card';

    card.innerHTML = `
      <div class="aspect-[4/3] bg-slate-950 relative overflow-hidden flex items-center justify-center">
        <img
          src="/images/serve?path=${safePath}&max_dim=400"
          alt="${escapeHtml(title)}"
          loading="lazy"
          class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\' fill=\\'%23334155\\'><text x=\\'50%\\' y=\\'50%\\' text-anchor=\\'middle\\' fill=\\'%2364748b\\' font-size=\\'12\\'>Scan</text></svg>'"
        >
        <span class="absolute top-2 left-2 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500 text-slate-950 shadow-md backdrop-blur-md">
          📚 ${grp.count} Aufnahmen
        </span>
        ${rep.width && rep.height ? `
        <span class="absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-950/80 border border-slate-800 text-slate-400">
          ${rep.width} &times; ${rep.height}
        </span>` : ''}
      </div>
      <div class="p-3.5 flex-1 flex flex-col justify-between">
        <div>
          <h5 class="text-xs font-semibold text-slate-200 truncate group-hover:text-amber-400 transition" title="${escapeHtml(title)}">
            ${escapeHtml(title)}
          </h5>
          <p class="text-[11px] text-slate-400 font-mono truncate mt-0.5" title="${escapeHtml(rep.file_path || '')}">
            ${escapeHtml(rep.file_path || '')}
          </p>
        </div>
        <div class="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
          <span class="text-slate-500 font-mono">${rep.date || 'Ohne Datum'}</span>
          <span class="text-amber-400 font-semibold group-hover:translate-x-0.5 transition-transform">Stapel vergleichen →</span>
        </div>
      </div>
    `;

    card.addEventListener('click', () => openDuplicateGroupModal(idx));
    container.appendChild(card);
  });
}

function openDuplicateGroupModal(groupIndex) {
  const grp = currentArchiveDuplicateGroups[groupIndex];
  if (!grp) return;

  const modal = document.getElementById('stack-modal');
  const title = document.getElementById('stack-modal-title');
  const subtitle = document.getElementById('stack-modal-subtitle');
  const itemsContainer = document.getElementById('stack-modal-items');
  const info = document.getElementById('stack-modal-info');

  title.textContent = `Variantengruppe: ${grp.representative.file_name || 'Archiv-Stapel'}`;
  subtitle.textContent = `${grp.count} identifizierte Aufnahmen &amp; Repros im Bestand`;
  if (info) info.textContent = `Archivischer Kontext bleibt zu 100% erhalten. Keine automatische Löschung von Quelldateien.`;

  renderStackComparisonItems(grp.items || [], itemsContainer);
  modal.classList.remove('hidden');
}

