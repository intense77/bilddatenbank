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
  loadLightboxState();
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
  const lightboxSec = document.getElementById('tab-lightbox');
  const searchBtn = document.getElementById('tab-search-btn');
  const facesBtn = document.getElementById('tab-faces-btn');
  const importBtn = document.getElementById('tab-import-btn');
  const dupBtn = document.getElementById('tab-duplicates-btn');
  const lightboxBtn = document.getElementById('tab-lightbox-btn');

  // Alle Sektionen ausblenden
  if (searchSec) searchSec.classList.add('hidden');
  if (facesSec) facesSec.classList.add('hidden');
  if (importSec) importSec.classList.add('hidden');
  if (dupSec) dupSec.classList.add('hidden');
  if (lightboxSec) lightboxSec.classList.add('hidden');

  const activeCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all bg-amber-500 text-slate-950 font-semibold shadow-sm flex items-center gap-2';
  const inactiveCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 transition-all flex items-center gap-2';

  if (searchBtn) searchBtn.className = inactiveCls;
  if (facesBtn) facesBtn.className = inactiveCls;
  if (importBtn) importBtn.className = inactiveCls;
  if (dupBtn) dupBtn.className = inactiveCls;
  if (lightboxBtn) lightboxBtn.className = inactiveCls;

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
  } else if (tab === 'lightbox') {
    if (lightboxSec) lightboxSec.classList.remove('hidden');
    if (lightboxBtn) lightboxBtn.className = activeCls;
    renderLightboxView();
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

    const addAllBtn = document.getElementById('add-all-results-to-lightbox-btn');
    if (addAllBtn) {
      if (data.length > 0) addAllBtn.classList.remove('hidden');
      else addAllBtn.classList.add('hidden');
    }

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
        <!-- Leuchttisch Pin Button unten links -->
        <button
          type="button"
          onclick="toggleLightboxCard(event, ${itemIdx})"
          class="absolute bottom-2 left-2 p-1.5 rounded-lg border border-slate-700/80 text-xs transition-all shadow-md backdrop-blur-sm z-10 ${isItemInLightbox(item.file_path) ? 'bg-amber-500 text-slate-950 font-bold' : 'bg-slate-900/80 text-slate-300 hover:text-amber-400 hover:bg-slate-800'}"
          title="${isItemInLightbox(item.file_path) ? 'Vom Leuchttisch entfernen' : 'Auf den Leuchttisch legen'}"
        >
          <span>${isItemInLightbox(item.file_path) ? '★' : '💡'}</span>
        </button>
        <!-- Verlustfreies Drehen Button unten rechts -->
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
    const avatarSrc = c.preview_image || (`/faces/clusters/${encodeURIComponent(c.cluster_id)}/preview`);
    const defaultPlaceholder = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%231e293b"><circle cx="50" cy="50" r="40" fill="%23334155"/></svg>';

    card.innerHTML = `
      <div class="w-20 h-20 rounded-full overflow-hidden bg-slate-950 border-2 border-slate-700 group-hover:border-amber-400 transition-colors shadow-inner flex items-center justify-center mb-3">
        <img src="${avatarSrc}" alt="Avatar" class="w-full h-full object-cover" loading="lazy" onerror="this.onerror=null;this.src='${defaultPlaceholder}'">
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

async function openClusterDetail(cluster) {
  activeCluster = cluster;
  const container = document.getElementById('clusters-container');
  const detailView = document.getElementById('cluster-detail-view');
  const title = document.getElementById('cd-title');
  const stats = document.getElementById('cd-stats');
  const input = document.getElementById('cluster-label-input');
  const imagesGrid = document.getElementById('cluster-images-grid');

  container.classList.add('hidden');
  detailView.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'instant' });
  updateClusterFabVisibility();

  const displayName = cluster.label || `Person ${cluster.cluster_id.replace('cluster_', '#')}`;
  title.textContent = displayName;
  stats.textContent = `${cluster.face_count} Vorkommen in historischen Scans (Cluster ID: ${cluster.cluster_id})`;
  input.value = cluster.label || '';

  imagesGrid.innerHTML = `
    <div class="col-span-full py-16 text-center text-slate-400 flex flex-col items-center justify-center gap-3">
      <div class="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-sm font-medium text-slate-300">Lade Archivfotos für ${escapeHtml(displayName)}...</span>
    </div>
  `;

  if (!cluster.faces || cluster.faces.length === 0) {
    try {
      const res = await fetch(`/faces/clusters/${encodeURIComponent(cluster.cluster_id)}`);
      if (res.ok) {
        const details = await res.json();
        cluster.faces = details.faces || [];
        if (details.label) cluster.label = details.label;
      }
    } catch (err) {
      console.error('Fehler beim Laden der Cluster-Details:', err);
      showToast(`Fehler beim Laden der Bilder: ${err.message}`, true);
    }
  }

  imagesGrid.innerHTML = '';

  if (!cluster.faces || cluster.faces.length === 0) {
    imagesGrid.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500">
        Keine Archivbilder für dieses Cluster gefunden.
      </div>
    `;
    return;
  }

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

  // Komfortable Navigations-Karte am Ende der Bildergalerie
  if (cluster.faces && cluster.faces.length > 2) {
    const endCard = document.createElement('div');
    endCard.className = 'col-span-full py-8 px-6 bg-slate-900/60 border border-slate-800 rounded-2xl text-center space-y-3 mt-4';
    endCard.innerHTML = `
      <p class="text-sm text-slate-300 font-medium">Alle ${cluster.faces.length} Porträts dieser Person durchgesehen</p>
      <div class="flex items-center justify-center gap-3">
        <button onclick="closeClusterDetail()" class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-xs sm:text-sm rounded-xl transition flex items-center gap-2 shadow-md">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
          <span>Zurück zur Personen-Übersicht</span>
        </button>
        <button onclick="window.scrollTo({ top: 0, behavior: 'smooth' })" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-medium rounded-xl border border-slate-700 transition flex items-center gap-2">
          <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M5 10l7-7m0 0l7 7m-7-7v18"></path></svg>
          <span>Nach oben scrollen</span>
        </button>
      </div>
    `;
    imagesGrid.appendChild(endCard);
  }
}

function updateClusterFabVisibility() {
  const fab = document.getElementById('cluster-floating-bar');
  if (!fab) return;
  if (activeCluster && window.scrollY > 200) {
    fab.classList.remove('hidden-fab');
  } else {
    fab.classList.add('hidden-fab');
  }
}

window.addEventListener('scroll', updateClusterFabVisibility, { passive: true });

function closeClusterDetail() {
  activeCluster = null;
  updateClusterFabVisibility();
  const container = document.getElementById('clusters-container');
  const detailView = document.getElementById('cluster-detail-view');
  if (container) container.classList.remove('hidden');
  if (detailView) detailView.classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (allLoadedClusters && allLoadedClusters.length > 0) {
    applyClusterFilters();
  } else {
    loadClusters();
  }
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

    currentModalImageDetails = {
      filePath,
      fileName,
      title: data.metadata?.title || null,
      date: data.metadata?.date || null,
      creator: data.metadata?.creator || null,
      signature: data.metadata?.signature || null,
      description: data.metadata?.description || null,
      width: data.width,
      height: data.height,
      keywords: data.metadata?.keywords || [],
      copyright: data.metadata?.copyright || null,
      persons: (data.faces || []).map(f => f.label).filter(Boolean)
    };
    updateModalLightboxButtonState(filePath);
    toggleMetadataEditMode(false);
    switchModalSidebarTab('meta');
    loadModalEditSettings(data.edit_settings || null);

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

      metaHtml += `
        <div class="pt-3 border-t border-slate-800 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">XMP-Sidecar (Dublin Core)</span>
            <span class="text-[10px] text-emerald-400 font-mono">Adobe / IPTC</span>
          </div>
          <div class="grid grid-cols-2 gap-1.5">
            <button type="button" onclick="downloadCurrentModalXmp()" class="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-emerald-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1 shadow-sm" title="Lädt die XMP-Metadaten als XML-Datei herunter">
              <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
              <span>Download</span>
            </button>
            <button type="button" onclick="writeCurrentModalXmp()" class="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-blue-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1 shadow-sm" title="Speichert die .xmp Datei direkt neben das Master-Original auf Festplatte/NAS">
              <svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path></svg>
              <span>Speichern</span>
            </button>
          </div>
        </div>`;

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
  closeModalXmpMenu();
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  resetAllImageAdjustments();
  toggleWideEditMode(false);
  toggleMetadataEditMode(false);
  switchModalSidebarTab('meta');
  currentModalImageDetails = null;
}

// Schließe Modal bei Klick auf den Hintergrund
document.getElementById('image-modal')?.addEventListener('click', (e) => {
  if (e.target.id === 'image-modal') {
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

// Tastatur-Shortcut (ESC schließt Modal bzw. wechselt zurück zur Cluster-Übersicht)
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    // 1. Modals mit Priorität schließen
    const fbModal = document.getElementById('folder-browser-modal');
    if (fbModal && !fbModal.classList.contains('hidden')) {
      closeFolderBrowserModal();
      return;
    }
    const stModal = document.getElementById('stack-modal');
    if (stModal && !stModal.classList.contains('hidden')) {
      closeStackModal();
      return;
    }
    const mergeModal = document.getElementById('merge-cluster-modal');
    if (mergeModal && !mergeModal.classList.contains('hidden')) {
      closeMergeClusterModal();
      return;
    }
    const pdfModal = document.getElementById('pdf-export-modal');
    if (pdfModal && !pdfModal.classList.contains('hidden')) {
      closePdfExportModal();
      return;
    }
    const imgModal = document.getElementById('image-modal');
    if (imgModal && !imgModal.classList.contains('hidden')) {
      closeImageModal();
      return;
    }
    // 2. Wenn kein Modal offen ist, aber die Cluster-Einzelansicht aktiv ist:
    if (activeCluster) {
      closeClusterDetail();
    }
  }

  // Pfeiltasten Navigation im Bild-Modal (Vorheriges / Nächstes Bild)
  const imgModal = document.getElementById('image-modal');
  if (imgModal && !imgModal.classList.contains('hidden') && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
    if (cropperInstance) return; // Nicht während der Rahmenwahl blättern

    if (currentSearchResults && currentSearchResults.length > 1 && currentModalImageDetails) {
      const curIdx = currentSearchResults.findIndex(it => it.file_path === currentModalImageDetails.filePath);
      if (curIdx !== -1) {
        e.preventDefault();
        const nextIdx = e.key === 'ArrowRight'
          ? (curIdx + 1) % currentSearchResults.length
          : (curIdx - 1 + currentSearchResults.length) % currentSearchResults.length;
        const nextItem = currentSearchResults[nextIdx];
        if (nextItem) {
          openImageModal(nextItem.file_path, nextItem.file_name);
        }
      }
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


// ================= DIGITALER LEUCHTTISCH & PDF-EXPORT =================

const LIGHTBOX_STORAGE_KEY = 'archive_lightbox_items';
const LIGHTBOX_TITLE_KEY = 'archive_lightbox_project_title';
let lightboxItems = [];

function loadLightboxState() {
  try {
    const raw = localStorage.getItem(LIGHTBOX_STORAGE_KEY);
    lightboxItems = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(lightboxItems)) lightboxItems = [];
  } catch (e) {
    console.error('Fehler beim Laden des Leuchttischs:', e);
    lightboxItems = [];
  }
  updateLightboxBadge();
  const titleInput = document.getElementById('lightbox-project-title');
  if (titleInput) {
    titleInput.value = localStorage.getItem(LIGHTBOX_TITLE_KEY) || '';
  }
}

function saveLightboxState() {
  try {
    localStorage.setItem(LIGHTBOX_STORAGE_KEY, JSON.stringify(lightboxItems));
  } catch (e) {
    console.error('Fehler beim Speichern des Leuchttischs:', e);
  }
  updateLightboxBadge();
}

function updateLightboxBadge() {
  const count = lightboxItems.length;
  const badge = document.getElementById('lightbox-badge');
  const countBadge = document.getElementById('lightbox-count-badge');
  if (badge) {
    badge.textContent = count;
    if (count > 0) {
      badge.classList.remove('bg-slate-800', 'text-slate-400');
      badge.classList.add('bg-amber-500/20', 'text-amber-400');
    } else {
      badge.classList.remove('bg-amber-500/20', 'text-amber-400');
      badge.classList.add('bg-slate-800', 'text-slate-400');
    }
  }
  if (countBadge) {
    countBadge.textContent = `${count} ${count === 1 ? 'Bild' : 'Bilder'}`;
  }
}

function isItemInLightbox(filePath) {
  if (!filePath) return false;
  return lightboxItems.some(it => it.file_path === filePath);
}

function addToLightbox(item) {
  if (!item || !item.file_path) return false;
  if (isItemInLightbox(item.file_path)) return false;

  const newItem = {
    file_path: item.file_path,
    file_name: item.file_name || item.file_path.split('/').pop(),
    title: item.title || null,
    date: item.date || null,
    creator: item.creator || null,
    signature: item.signature || null,
    persons: item.persons || [],
    notes: item.notes || '',
    added_at: Date.now()
  };

  lightboxItems.push(newItem);
  saveLightboxState();
  showToast(`"${newItem.title || newItem.file_name}" auf den Leuchttisch gelegt`, false);
  return true;
}

function removeFromLightbox(filePath) {
  const idx = lightboxItems.findIndex(it => it.file_path === filePath);
  if (idx === -1) return false;
  const removed = lightboxItems.splice(idx, 1)[0];
  saveLightboxState();
  showToast(`"${removed.title || removed.file_name}" vom Leuchttisch entfernt`, false);
  const activeTab = document.getElementById('tab-lightbox');
  if (activeTab && !activeTab.classList.contains('hidden')) {
    renderLightboxView();
  }
  return true;
}

function toggleLightboxItem(item) {
  if (isItemInLightbox(item.file_path)) {
    removeFromLightbox(item.file_path);
    return false;
  } else {
    addToLightbox(item);
    return true;
  }
}

function toggleLightboxCard(event, itemIdx) {
  event.stopPropagation();
  const item = currentSearchResults[itemIdx];
  if (!item) return;
  const added = toggleLightboxItem(item);
  const btn = event.currentTarget;
  if (btn) {
    if (added) {
      btn.className = 'absolute bottom-2 left-2 p-1.5 rounded-lg border border-slate-700/80 text-xs transition-all shadow-md backdrop-blur-sm z-10 bg-amber-500 text-slate-950 font-bold';
      btn.innerHTML = '<span>★</span>';
      btn.title = 'Vom Leuchttisch entfernen';
    } else {
      btn.className = 'absolute bottom-2 left-2 p-1.5 rounded-lg border border-slate-700/80 text-xs transition-all shadow-md backdrop-blur-sm z-10 bg-slate-900/80 text-slate-300 hover:text-amber-400 hover:bg-slate-800';
      btn.innerHTML = '<span>💡</span>';
      btn.title = 'Auf den Leuchttisch legen';
    }
  }
}

function addAllCurrentResultsToLightbox() {
  if (!currentSearchResults || currentSearchResults.length === 0) return;
  let addedCount = 0;
  currentSearchResults.forEach(item => {
    if (!isItemInLightbox(item.file_path)) {
      lightboxItems.push({
        file_path: item.file_path,
        file_name: item.file_name || item.file_path.split('/').pop(),
        title: item.title || null,
        date: item.date || null,
        creator: item.creator || null,
        signature: item.signature || null,
        persons: item.persons || [],
        notes: '',
        added_at: Date.now()
      });
      addedCount++;
    }
  });
  saveLightboxState();
  showToast(`${addedCount} Bilder zum Leuchttisch hinzugefügt (gesamt: ${lightboxItems.length})`, false);
  const grid = document.getElementById('results-grid');
  if (grid) renderSearchResults(currentSearchResults, grid);
}

function updateModalLightboxButtonState(filePath) {
  const btn = document.getElementById('modal-lightbox-btn');
  const icon = document.getElementById('modal-lightbox-icon');
  const text = document.getElementById('modal-lightbox-text');
  if (!btn || !icon || !text) return;

  const inLb = isItemInLightbox(filePath);
  if (inLb) {
    btn.classList.add('bg-amber-500', 'text-slate-950', 'border-amber-400');
    btn.classList.remove('bg-slate-800', 'text-slate-200', 'border-slate-700');
    icon.textContent = '★';
    text.textContent = 'Auf Leuchttisch';
    btn.title = 'Bild vom Leuchttisch entfernen';
  } else {
    btn.classList.remove('bg-amber-500', 'text-slate-950', 'border-amber-400');
    btn.classList.add('bg-slate-800', 'text-slate-200', 'border-slate-700');
    icon.textContent = '💡';
    text.textContent = 'Auf Leuchttisch';
    btn.title = 'Dieses Bild auf den Leuchttisch legen';
  }
}

function toggleCurrentModalLightbox() {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) return;
  const fp = currentModalImageDetails.filePath;
  const inLb = isItemInLightbox(fp);
  if (inLb) {
    removeFromLightbox(fp);
  } else {
    addToLightbox({
      file_path: fp,
      file_name: currentModalImageDetails.fileName,
      title: currentModalImageDetails.title || null,
      date: currentModalImageDetails.date || null,
      creator: currentModalImageDetails.creator || null,
      signature: currentModalImageDetails.signature || null,
      persons: currentModalImageDetails.persons || [],
    });
  }
  updateModalLightboxButtonState(fp);
}

function handleLightboxTitleChange(val) {
  localStorage.setItem(LIGHTBOX_TITLE_KEY, val || '');
}

function copyLightboxPaths() {
  if (lightboxItems.length === 0) {
    showToast('Der Leuchttisch ist leer.', true);
    return;
  }
  const paths = lightboxItems.map(it => it.file_path).join('\n');
  navigator.clipboard.writeText(paths).then(() => {
    showToast(`${lightboxItems.length} Dateipfade in Zwischenablage kopiert!`, false);
  }).catch(() => {
    showToast('Konnte Pfade nicht kopieren', true);
  });
}

function clearLightboxConfirm() {
  if (lightboxItems.length === 0) return;
  if (confirm(`Möchten Sie wirklich alle ${lightboxItems.length} Bilder vom Leuchttisch entfernen?`)) {
    lightboxItems = [];
    saveLightboxState();
    renderLightboxView();
    showToast('Leuchttisch geleert.', false);
  }
}

function updateLightboxItemNote(filePath, note) {
  const item = lightboxItems.find(it => it.file_path === filePath);
  if (item) {
    item.notes = note;
    saveLightboxState();
  }
}

function renderLightboxView() {
  const grid = document.getElementById('lightbox-grid');
  const empty = document.getElementById('lightbox-empty');
  const exportBtn = document.getElementById('lightbox-export-pdf-btn');
  if (!grid || !empty) return;

  updateLightboxBadge();

  if (lightboxItems.length === 0) {
    grid.innerHTML = '';
    grid.classList.add('hidden');
    empty.classList.remove('hidden');
    if (exportBtn) exportBtn.disabled = true;
    return;
  }

  empty.classList.add('hidden');
  grid.classList.remove('hidden');
  if (exportBtn) exportBtn.disabled = false;
  grid.innerHTML = '';

  lightboxItems.forEach((item, idx) => {
    const card = document.createElement('div');
    card.className = 'group bg-slate-900 border border-slate-800 hover:border-amber-500/40 rounded-xl overflow-hidden shadow-lg transition-all flex flex-col justify-between';

    const safePath = encodeURIComponent(item.file_path);
    const displayName = item.title || item.file_name;

    let metaLines = [];
    if (item.date) metaLines.push(`📅 ${escapeHtml(item.date)}`);
    if (item.signature) metaLines.push(`🏷️ ${escapeHtml(item.signature)}`);
    if (item.creator) metaLines.push(`📷 ${escapeHtml(item.creator)}`);

    let personsBadge = '';
    if (item.persons && item.persons.length > 0) {
      personsBadge = `<div class="mt-1 flex flex-wrap gap-1">${item.persons.map(p => `<span class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium text-[10px]">👤 ${escapeHtml(p)}</span>`).join('')}</div>`;
    }

    card.innerHTML = `
      <div>
        <div class="aspect-[4/3] bg-slate-950 relative overflow-hidden flex items-center justify-center cursor-pointer" onclick="openImageModal('${escapeHtml(item.file_path)}', '${escapeHtml(item.file_name)}')">
          <img
            src="/images/serve?path=${safePath}&max_dim=500"
            alt="${escapeHtml(displayName)}"
            loading="lazy"
            id="lb-img-${idx}"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          >
          <span class="absolute top-2 left-2 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500 text-slate-950 shadow-md">
            #${idx + 1}
          </span>
          <!-- Schnell-Dreh Button oben rechts -->
          <button
            type="button"
            onclick="rotateLightboxCardImage(event, '${escapeHtml(item.file_path).replace(/'/g, "\\'")}', 90, ${idx})"
            class="absolute top-2 right-2 p-1.5 rounded-lg bg-slate-900/80 hover:bg-amber-500 hover:text-slate-950 text-slate-300 border border-slate-700/80 transition-all shadow-md backdrop-blur-sm z-20"
            title="Bild 90° im Uhrzeigersinn drehen (verlustfrei)"
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
            </svg>
          </button>
        </div>

        <div class="p-3 space-y-2">
          <div>
            <h4 class="text-xs font-semibold text-slate-100 truncate group-hover:text-amber-400 transition" title="${escapeHtml(displayName)}">
              ${escapeHtml(displayName)}
            </h4>
            <p class="text-[11px] text-slate-400 font-mono truncate mt-0.5" title="${escapeHtml(item.file_path)}">
              ${escapeHtml(item.file_name)}
            </p>
          </div>

          ${metaLines.length > 0 ? `<p class="text-[11px] text-slate-400 leading-tight">${metaLines.join(' • ')}</p>` : ''}
          ${personsBadge}

          <!-- Kuratoren-Notizfeld -->
          <div class="pt-1">
            <label class="block text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">Kuratoren-Notiz:</label>
            <input
              type="text"
              value="${escapeHtml(item.notes || '')}"
              placeholder="Notiz hinzufügen (z. B. 'Katalog S. 12')..."
              onchange="updateLightboxItemNote('${escapeHtml(item.file_path).replace(/'/g, "\\'")}', this.value)"
              class="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 focus:border-amber-500/60 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
            >
          </div>
        </div>
      </div>

      <div class="p-3 pt-0 border-t border-slate-800/80 flex items-center justify-between mt-2 gap-2">
        <button
          onclick="openImageModal('${escapeHtml(item.file_path)}', '${escapeHtml(item.file_name)}')"
          class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] font-medium transition"
        >
          Großansicht
        </button>
        <button
          onclick="removeFromLightbox('${escapeHtml(item.file_path).replace(/'/g, "\\'")}')"
          class="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-[11px] font-medium transition flex items-center gap-1"
          title="Aus Mappe entfernen"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          <span>Entfernen</span>
        </button>
      </div>
    `;

    grid.appendChild(card);
  });
}

async function rotateLightboxCardImage(event, filePath, angle, idx) {
  event.stopPropagation();
  const btn = event.currentTarget;
  btn.disabled = true;
  btn.innerHTML = '<span class="animate-spin inline-block">⏳</span>';

  try {
    showToast(`Drehe Bild um ${angle}° verlustfrei...`, false);
    const result = await rotateImageFile(filePath, angle);
    if (!result || !result.success) throw new Error(result?.message || 'Drehung fehlgeschlagen');
    const ts = Date.now();
    const imgElem = document.getElementById(`lb-img-${idx}`);
    if (imgElem) {
      let baseSrc = imgElem.src.split('&t=')[0].split('?t=')[0];
      const sep = baseSrc.includes('?') ? '&' : '?';
      imgElem.src = `${baseSrc}${sep}t=${ts}`;
    }
    showToast('Bild erfolgreich gedreht', false);
  } catch (err) {
    showToast(`Fehler beim Drehen: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path></svg>`;
  }
}

// --- PDF Export Dialog ---
function openPdfExportModal() {
  if (lightboxItems.length === 0) {
    showToast('Fügen Sie zuerst Bilder zum Leuchttisch hinzu.', true);
    return;
  }
  const modal = document.getElementById('pdf-export-modal');
  const titleInput = document.getElementById('pdf-doc-title');
  const projTitle = localStorage.getItem(LIGHTBOX_TITLE_KEY);
  const countLabel = document.getElementById('pdf-items-count-label');

  if (titleInput) {
    titleInput.value = projTitle && projTitle.trim() ? projTitle.trim() : 'Historisches Bildarchiv – Kontaktabzug';
  }
  if (countLabel) {
    countLabel.textContent = `${lightboxItems.length} ${lightboxItems.length === 1 ? 'Bild' : 'Bilder'}`;
  }
  if (modal) modal.classList.remove('hidden');
}

function closePdfExportModal() {
  const modal = document.getElementById('pdf-export-modal');
  if (modal) modal.classList.add('hidden');
}

async function handlePdfExportSubmit(event) {
  event.preventDefault();
  if (lightboxItems.length === 0) return;

  const btn = document.getElementById('pdf-submit-btn');
  const btnText = document.getElementById('pdf-btn-text');
  const btnIcon = document.getElementById('pdf-btn-icon');
  const originalText = btnText ? btnText.textContent : 'Exportieren';

  const title = document.getElementById('pdf-doc-title')?.value || 'Archiv-Kontaktabzug';
  const subtitle = document.getElementById('pdf-doc-subtitle')?.value || null;
  const layout = document.querySelector('input[name="pdf-layout"]:checked')?.value || 'grid';
  const includeNotes = document.getElementById('pdf-include-notes')?.checked ?? true;

  if (btn) btn.disabled = true;
  if (btnIcon) btnIcon.innerHTML = '<span class="animate-spin inline-block">⏳</span>';
  if (btnText) btnText.textContent = 'Erstelle hochauflösendes PDF...';

  try {
    showToast('Generiere druckfähiges DIN-A4 PDF im Hintergrund...', false);

    const payload = {
      title: title,
      subtitle: subtitle,
      layout: layout,
      include_notes: includeNotes,
      items: lightboxItems.map(it => ({
        file_path: it.file_path,
        file_name: it.file_name,
        title: it.title,
        date: it.date,
        creator: it.creator,
        signature: it.signature,
        persons: it.persons || [],
        notes: it.notes || null,
      }))
    };

    const res = await fetch('/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler beim PDF-Export (${res.status})`);

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const safeTitle = (title.replace(/[^a-zA-Z0-9_-]/g, '_') || 'Kontaktabzug').substring(0, 30);
    a.download = `${safeTitle}_${layout}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast('PDF-Kontaktabzug erfolgreich heruntergeladen!', false);
    closePdfExportModal();
  } catch (err) {
    console.error('Fehler beim PDF-Export:', err);
    showToast(`PDF-Export fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (btn) btn.disabled = false;
    if (btnIcon) btnIcon.textContent = '⬇';
    if (btnText) btnText.textContent = originalText;
  }
}

// ================= XMP SIDECAR EXPORT & SYNCHRONISATION =================

function toggleModalXmpMenu(event) {
  if (event) event.stopPropagation();
  const menu = document.getElementById('modal-xmp-menu');
  if (menu) menu.classList.toggle('hidden');
}

function closeModalXmpMenu() {
  const menu = document.getElementById('modal-xmp-menu');
  if (menu) menu.classList.add('hidden');
}

// Schließe XMP-Menü bei Klicks außerhalb
document.addEventListener('click', (e) => {
  const container = document.getElementById('modal-xmp-container');
  if (container && !container.contains(e.target)) {
    closeModalXmpMenu();
  }
});

function downloadCurrentModalXmp() {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein aktives Bild im Detailfenster gefunden.', true);
    return;
  }
  closeModalXmpMenu();
  const filePath = currentModalImageDetails.filePath;
  const fileName = currentModalImageDetails.fileName || filePath.split('/').pop();
  const baseName = fileName.substring(0, fileName.lastIndexOf('.')) || fileName;

  const url = `/images/xmp?path=${encodeURIComponent(filePath)}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = `${baseName}.xmp`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast(`XMP-Sidecar für "${fileName}" heruntergeladen.`, false);
}

async function writeCurrentModalXmp() {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein aktives Bild im Detailfenster gefunden.', true);
    return;
  }
  closeModalXmpMenu();
  const filePath = currentModalImageDetails.filePath;
  showToast('Schreibe XMP-Sidecar...', false);

  try {
    const res = await fetch(`/images/xmp/write?path=${encodeURIComponent(filePath)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    if (data.location === 'alongside_master') {
      const fileName = data.target_path.split('/').pop();
      showToast(`XMP-Sidecar direkt neben Originaldatei gespeichert: ${fileName}`, false);
    } else {
      const fileName = data.target_path.split('/').pop();
      showToast(`XMP-Sidecar im lokalen Spiegelordner gesichert: ${fileName}`, false);
    }
  } catch (err) {
    console.error('Fehler beim Schreiben der XMP-Datei:', err);
    showToast(`Fehler beim Schreiben des XMP-Sidecars: ${err.message}`, true);
  }
}

async function exportLightboxXmpZip() {
  if (lightboxItems.length === 0) {
    showToast('Fügen Sie zuerst Bilder zum Leuchttisch hinzu.', true);
    return;
  }

  const btn = document.getElementById('lightbox-export-xmp-btn');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Exportiere...</span>';
  }

  try {
    showToast(`Bündle standardkonforme XMP-Sidecars für ${lightboxItems.length} Bilder...`, false);
    const payload = {
      items: lightboxItems.map(it => ({
        file_path: it.file_path,
        file_name: it.file_name,
        title: it.title,
        date: it.date,
        creator: it.creator,
        signature: it.signature,
        persons: it.persons || [],
        notes: it.notes || null,
      }))
    };

    const res = await fetch('/export/xmp-zip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler beim XMP-Export (${res.status})`);

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    a.download = `XMP_Sidecars_${now}.zip`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast(`${lightboxItems.length} XMP-Sidecars erfolgreich exportiert!`, false);
  } catch (err) {
    console.error('Fehler beim XMP-Export:', err);
    showToast(`XMP-Export fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

// ================= NON-DESTRUKTIVE BILDBEARBEITUNG (CROPPER, SLIDERS & PILLOW EXPORT) =================

let areFaceBoxesVisible = true;

function setFaceBoundingBoxesVisible(visible) {
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const label = document.getElementById('label-toggle-face-boxes');
  const icon = document.getElementById('icon-toggle-face-boxes');
  const btn = document.getElementById('btn-toggle-face-boxes');
  if (!wrapper) return;

  areFaceBoxesVisible = visible;
  if (visible) {
    wrapper.classList.remove('hide-face-boxes');
    if (label) label.textContent = 'Gesichter aus';
    if (icon) icon.textContent = '👤';
    if (btn) {
      btn.classList.remove('text-amber-400', 'border-amber-500/50', 'bg-amber-500/20');
      btn.classList.add('text-slate-300', 'bg-slate-900/80');
    }
  } else {
    wrapper.classList.add('hide-face-boxes');
    if (label) label.textContent = 'Gesichter an';
    if (icon) icon.textContent = '👁️';
    if (btn) {
      btn.classList.add('text-amber-400', 'border-amber-500/50', 'bg-amber-500/20');
      btn.classList.remove('text-slate-300', 'bg-slate-900/80');
    }
  }
}

function toggleFaceBoxesVisibility() {
  setFaceBoundingBoxesVisible(!areFaceBoxesVisible);
}

function switchModalSidebarTab(tabName) {
  const metaTab = document.getElementById('modal-tab-content-meta');
  const editTab = document.getElementById('modal-tab-content-edit');
  const metaBtn = document.getElementById('tab-btn-meta');
  const editBtn = document.getElementById('tab-btn-edit');
  const adjustHeaderBtn = document.getElementById('modal-adjust-btn');

  if (tabName === 'edit') {
    if (metaTab) metaTab.classList.add('hidden');
    if (editTab) editTab.classList.remove('hidden');

    if (metaBtn) {
      metaBtn.classList.remove('text-amber-400', 'bg-slate-800/90', 'font-semibold');
      metaBtn.classList.add('text-slate-400', 'font-medium');
    }
    if (editBtn) {
      editBtn.classList.add('text-amber-400', 'bg-slate-800/90', 'font-semibold');
      editBtn.classList.remove('text-slate-400', 'font-medium');
    }
    if (adjustHeaderBtn) {
      adjustHeaderBtn.classList.add('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
    }

    // Gesichtsrahmen im Bearbeiten/Workbench-Modus automatisch ausblenden, um das Bild ungestört zu optimieren
    setFaceBoundingBoxesVisible(false);
  } else {
    if (editTab) editTab.classList.add('hidden');
    if (metaTab) metaTab.classList.remove('hidden');

    if (metaBtn) {
      metaBtn.classList.add('text-amber-400', 'bg-slate-800/90', 'font-semibold');
      metaBtn.classList.remove('text-slate-400', 'font-medium');
    }
    if (editBtn) {
      editBtn.classList.remove('text-amber-400', 'bg-slate-800/90', 'font-semibold');
      editBtn.classList.add('text-slate-400', 'font-medium');
    }
    if (adjustHeaderBtn) {
      adjustHeaderBtn.classList.remove('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
    }

    // Gesichtsrahmen im Metadaten-Modus standardmäßig einblenden
    setFaceBoundingBoxesVisible(true);
  }
}

let currentEditSettings = {
  brightness: 0,
  contrast: 0,
  gamma: 1.0,
  sharpness: 0,
  rotation: 0,
  fine_rotation: 0.0,
  flip_h: false,
  saturation: 100,
  invert: false,
  crop: null
};

let cropperInstance = null;
let currentCropperRatio = NaN;
let isWideEditMode = false;

function loadModalEditSettings(settings) {
  currentEditSettings = {
    brightness: 0,
    contrast: 0,
    gamma: 1.0,
    sharpness: 0,
    rotation: 0,
    fine_rotation: 0.0,
    flip_h: false,
    saturation: 100,
    invert: false,
    crop: null
  };

  if (settings && typeof settings === 'object') {
    Object.assign(currentEditSettings, settings);
  }

  // Update UI Inputs
  const bSlider = document.getElementById('edit-slider-brightness');
  const cSlider = document.getElementById('edit-slider-contrast');
  const gSlider = document.getElementById('edit-slider-gamma');
  const sSlider = document.getElementById('edit-slider-sharpness');
  const rSlider = document.getElementById('edit-slider-fine-rotation');
  const satSlider = document.getElementById('edit-slider-saturation');

  if (bSlider) bSlider.value = currentEditSettings.brightness;
  if (cSlider) cSlider.value = currentEditSettings.contrast;
  if (gSlider) gSlider.value = currentEditSettings.gamma;
  if (sSlider) sSlider.value = currentEditSettings.sharpness;
  if (rSlider) rSlider.value = currentEditSettings.fine_rotation;
  if (satSlider) satSlider.value = currentEditSettings.saturation;

  const bLabel = document.getElementById('label-edit-brightness');
  const cLabel = document.getElementById('label-edit-contrast');
  const gLabel = document.getElementById('label-edit-gamma');
  const sLabel = document.getElementById('label-edit-sharpness');
  const rLabel = document.getElementById('label-edit-fine-rotation');
  const satLabel = document.getElementById('label-edit-saturation');

  if (bLabel) bLabel.textContent = `${currentEditSettings.brightness > 0 ? '+' : ''}${currentEditSettings.brightness}%`;
  if (cLabel) cLabel.textContent = `${currentEditSettings.contrast > 0 ? '+' : ''}${currentEditSettings.contrast}%`;
  if (gLabel) gLabel.textContent = Number(currentEditSettings.gamma).toFixed(2);
  if (sLabel) sLabel.textContent = `${currentEditSettings.sharpness}%`;
  if (rLabel) rLabel.textContent = `${currentEditSettings.fine_rotation > 0 ? '+' : ''}${Number(currentEditSettings.fine_rotation).toFixed(1)}°`;
  if (satLabel) satLabel.textContent = `${currentEditSettings.saturation}%`;

  const rotBtnLabel = document.getElementById('label-edit-rotation-btn');
  if (rotBtnLabel) rotBtnLabel.textContent = `${currentEditSettings.rotation}°`;

  const flipBtn = document.getElementById('edit-btn-flip-h');
  if (flipBtn) {
    if (currentEditSettings.flip_h) {
      flipBtn.classList.add('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    } else {
      flipBtn.classList.remove('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    }
  }

  const invBtn = document.getElementById('edit-btn-invert');
  if (invBtn) {
    if (currentEditSettings.invert) {
      invBtn.classList.add('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    } else {
      invBtn.classList.remove('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    }
  }

  const cropBadge = document.getElementById('cropper-status-badge');
  const clearCropBtn = document.getElementById('btn-clear-crop');
  const cancelCropBtn = document.getElementById('btn-cancel-crop');
  const cropperBtnLabel = document.getElementById('btn-cropper-label');
  const cropperBtnIcon = document.getElementById('btn-cropper-icon');
  const toggleBtn = document.getElementById('btn-toggle-cropper');

  if (currentEditSettings.crop) {
    if (cropBadge) {
      cropBadge.textContent = `Aktiv (${Math.round(currentEditSettings.crop.width)}×${Math.round(currentEditSettings.crop.height)} px)`;
      cropBadge.className = 'text-[10px] text-emerald-400 font-mono font-semibold';
    }
    if (clearCropBtn) clearCropBtn.classList.remove('hidden');
    if (cancelCropBtn) cancelCropBtn.classList.add('hidden');
    if (cropperBtnLabel) cropperBtnLabel.textContent = 'Zuschnitt ändern';
    if (cropperBtnIcon) cropperBtnIcon.textContent = '✂️';
    if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition flex items-center justify-center gap-1.5 shadow-sm';

    const img = document.getElementById('modal-img');
    if (img) {
      if (img.complete && img.naturalWidth > 0) {
        applyClientCropPreview(img, currentEditSettings.crop);
      } else {
        img.addEventListener('load', () => {
          applyClientCropPreview(img, currentEditSettings.crop);
        }, { once: true });
      }
    }
  } else {
    if (cropBadge) {
      cropBadge.textContent = 'inaktiv';
      cropBadge.className = 'text-[10px] text-slate-500 font-mono';
    }
    if (clearCropBtn) clearCropBtn.classList.add('hidden');
    if (cancelCropBtn) cancelCropBtn.classList.add('hidden');
    if (cropperBtnLabel) cropperBtnLabel.textContent = 'Rahmen aufziehen';
    if (cropperBtnIcon) cropperBtnIcon.textContent = '✂️';
    if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-sm';
  }

  applyLiveImageTransformations();
}

function onEditSliderChange() {
  const bSlider = document.getElementById('edit-slider-brightness');
  const cSlider = document.getElementById('edit-slider-contrast');
  const gSlider = document.getElementById('edit-slider-gamma');
  const sSlider = document.getElementById('edit-slider-sharpness');
  const rSlider = document.getElementById('edit-slider-fine-rotation');
  const satSlider = document.getElementById('edit-slider-saturation');

  currentEditSettings.brightness = bSlider ? parseInt(bSlider.value, 10) : 0;
  currentEditSettings.contrast = cSlider ? parseInt(cSlider.value, 10) : 0;
  currentEditSettings.gamma = gSlider ? parseFloat(gSlider.value) : 1.0;
  currentEditSettings.sharpness = sSlider ? parseInt(sSlider.value, 10) : 0;
  currentEditSettings.fine_rotation = rSlider ? parseFloat(rSlider.value) : 0.0;
  currentEditSettings.saturation = satSlider ? parseInt(satSlider.value, 10) : 100;

  const bLabel = document.getElementById('label-edit-brightness');
  const cLabel = document.getElementById('label-edit-contrast');
  const gLabel = document.getElementById('label-edit-gamma');
  const sLabel = document.getElementById('label-edit-sharpness');
  const rLabel = document.getElementById('label-edit-fine-rotation');
  const satLabel = document.getElementById('label-edit-saturation');

  if (bLabel) bLabel.textContent = `${currentEditSettings.brightness > 0 ? '+' : ''}${currentEditSettings.brightness}%`;
  if (cLabel) cLabel.textContent = `${currentEditSettings.contrast > 0 ? '+' : ''}${currentEditSettings.contrast}%`;
  if (gLabel) gLabel.textContent = Number(currentEditSettings.gamma).toFixed(2);
  if (sLabel) sLabel.textContent = `${currentEditSettings.sharpness}%`;
  if (rLabel) rLabel.textContent = `${currentEditSettings.fine_rotation > 0 ? '+' : ''}${Number(currentEditSettings.fine_rotation).toFixed(1)}°`;
  if (satLabel) satLabel.textContent = `${currentEditSettings.saturation}%`;

  applyLiveImageTransformations();
}

function applyLiveImageTransformations(isComparingOriginal = false) {
  const img = document.getElementById('modal-img');
  if (!img) return;

  if (isComparingOriginal) {
    img.style.filter = 'none';
    img.style.transform = 'none';
    return;
  }

  const b = currentEditSettings.brightness;
  const c = currentEditSettings.contrast;
  const g = currentEditSettings.gamma;
  const s = currentEditSettings.sharpness;
  const sat = currentEditSettings.saturation;
  const inv = currentEditSettings.invert;
  const rot = currentEditSettings.rotation || 0;
  const fineRot = currentEditSettings.fine_rotation || 0;
  const flipH = currentEditSettings.flip_h;

  const filters = [];
  const brightPct = Math.round(100 + b);
  if (brightPct !== 100) filters.push(`brightness(${brightPct}%)`);

  const contrastPct = Math.round(100 + c);
  if (contrastPct !== 100) filters.push(`contrast(${contrastPct}%)`);

  if (sat !== 100) filters.push(`saturate(${sat}%)`);

  if (inv) filters.push('invert(1)');

  // Hardware-beschleunigte SVG Filter für Gamma und Schärfung
  const hasGamma = Math.abs(g - 1.0) > 0.01;
  const hasSharpness = s > 0;

  if (hasGamma || hasSharpness) {
    const exp = (1.0 / Math.max(0.1, g)).toFixed(4);
    const rFunc = document.getElementById('svg-gamma-r');
    const gFunc = document.getElementById('svg-gamma-g');
    const bFunc = document.getElementById('svg-gamma-b');
    if (rFunc) rFunc.setAttribute('exponent', exp);
    if (gFunc) gFunc.setAttribute('exponent', exp);
    if (bFunc) bFunc.setAttribute('exponent', exp);

    const k = (s / 100.0).toFixed(2);
    const center = (1.0 + 4.0 * parseFloat(k)).toFixed(2);
    const matrix = document.getElementById('svg-sharpen-matrix');
    if (matrix) {
      matrix.setAttribute('kernelMatrix', `0 -${k} 0  -${k} ${center} -${k}  0 -${k} 0`);
    }

    filters.push('url(#archive-live-filter)');
  }

  img.style.filter = filters.length > 0 ? filters.join(' ') : 'none';

  // CSS Transform: Spiegelung & Rotation
  const totalAngle = (rot + fineRot) % 360;
  const scaleX = flipH ? -1 : 1;
  const transformParts = [];
  if (scaleX !== 1) transformParts.push(`scaleX(${scaleX})`);
  if (totalAngle !== 0) transformParts.push(`rotate(${totalAngle}deg)`);

  img.style.transform = transformParts.length > 0 ? transformParts.join(' ') : 'none';
  img.style.transformOrigin = 'center center';
  img.style.transition = 'filter 0.05s ease, transform 0.15s ease';
}

function startCompareOriginal() {
  const btn = document.getElementById('btn-compare-original');
  if (btn) btn.classList.add('bg-amber-500', 'text-slate-950', 'font-bold');
  applyLiveImageTransformations(true);
}

function stopCompareOriginal() {
  const btn = document.getElementById('btn-compare-original');
  if (btn) btn.classList.remove('bg-amber-500', 'text-slate-950', 'font-bold');
  applyLiveImageTransformations(false);
}

function toggleWideEditMode(forceState = null) {
  const dialog = document.getElementById('image-modal-dialog');
  const btnLabel = document.getElementById('label-wide-mode-btn');
  if (!dialog) return;

  isWideEditMode = forceState !== null ? forceState : !isWideEditMode;

  if (isWideEditMode) {
    dialog.classList.add('workbench-mode');
    if (btnLabel) btnLabel.textContent = 'Normal';
  } else {
    dialog.classList.remove('workbench-mode');
    if (btnLabel) btnLabel.textContent = 'Groß';
  }

  // Bei Großansicht hochauflösendes Preview laden
  if (isWideEditMode && currentModalImageDetails && currentModalImageDetails.filePath) {
    const img = document.getElementById('modal-img');
    if (img && !img.src.includes('max_dim=2400')) {
      img.src = `/images/serve?path=${encodeURIComponent(currentModalImageDetails.filePath)}&max_dim=2400`;
    }
  }

  // Bounding Boxes / Cropper Resize synchronisieren
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 100);
}

function applyArchivalPreset(presetName) {
  if (presetName === 'document') {
    currentEditSettings.brightness = 0;
    currentEditSettings.contrast = 30;
    currentEditSettings.gamma = 0.85;
    currentEditSettings.sharpness = 45;
    currentEditSettings.saturation = 80;
    loadModalEditSettings(currentEditSettings);
    showToast('Preset „Urkunde / Schrift“ angewendet.', false);
  } else if (presetName === 'unyellow') {
    currentEditSettings.brightness = 5;
    currentEditSettings.contrast = 20;
    currentEditSettings.gamma = 1.05;
    currentEditSettings.sharpness = 20;
    currentEditSettings.saturation = 0;
    loadModalEditSettings(currentEditSettings);
    showToast('Preset „Entgilben / S/W“ angewendet.', false);
  } else if (presetName === 'negative') {
    currentEditSettings.invert = true;
    currentEditSettings.contrast = 20;
    currentEditSettings.gamma = 1.1;
    loadModalEditSettings(currentEditSettings);
    showToast('Preset „Negativ-Invertierung“ angewendet.', false);
  } else if (presetName === 'neutral') {
    resetAllImageAdjustments();
  }
}

function rotateEditTransformation(delta = 90) {
  currentEditSettings.rotation = (currentEditSettings.rotation + delta) % 360;
  const rotBtnLabel = document.getElementById('label-edit-rotation-btn');
  if (rotBtnLabel) rotBtnLabel.textContent = `${currentEditSettings.rotation}°`;
  applyLiveImageTransformations();
}

function toggleEditFlipH() {
  currentEditSettings.flip_h = !currentEditSettings.flip_h;
  const flipBtn = document.getElementById('edit-btn-flip-h');
  if (flipBtn) {
    if (currentEditSettings.flip_h) {
      flipBtn.classList.add('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    } else {
      flipBtn.classList.remove('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    }
  }
  applyLiveImageTransformations();
}

function toggleEditInvert() {
  currentEditSettings.invert = !currentEditSettings.invert;
  const invBtn = document.getElementById('edit-btn-invert');
  if (invBtn) {
    if (currentEditSettings.invert) {
      invBtn.classList.add('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    } else {
      invBtn.classList.remove('bg-amber-500/30', 'text-amber-400', 'border-amber-500/50');
    }
  }
  applyLiveImageTransformations();
}

function resetAllImageAdjustments() {
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  const img = document.getElementById('modal-img');
  if (img && img.dataset.uncroppedSrc) {
    img.src = img.dataset.uncroppedSrc;
    delete img.dataset.uncroppedSrc;
  }
  currentEditSettings = {
    brightness: 0,
    contrast: 0,
    gamma: 1.0,
    sharpness: 0,
    rotation: 0,
    fine_rotation: 0.0,
    flip_h: false,
    saturation: 100,
    invert: false,
    crop: null
  };
  loadModalEditSettings(currentEditSettings);
  showToast('Alle Bildparameter auf neutralen Zustand zurückgesetzt.', false);
}

function setCropperRatio(ratio, btnElement) {
  const img = document.getElementById('modal-img');
  if (ratio === 'original') {
    if (img && img.naturalWidth && img.naturalHeight) {
      currentCropperRatio = img.naturalWidth / img.naturalHeight;
    } else {
      currentCropperRatio = NaN;
    }
  } else {
    currentCropperRatio = Number(ratio);
  }

  // Update preset buttons styling
  document.querySelectorAll('.crop-ratio-btn').forEach(b => {
    b.className = 'crop-ratio-btn flex-1 py-1 rounded bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 transition text-center';
  });
  if (btnElement) {
    btnElement.className = 'crop-ratio-btn flex-1 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 transition text-center font-bold';
  }

  if (cropperInstance) {
    cropperInstance.setAspectRatio(currentCropperRatio);
  } else {
    toggleCropperMode();
  }
}

function toggleCropperMode() {
  const img = document.getElementById('modal-img');
  const badge = document.getElementById('cropper-status-badge');
  const btnLabel = document.getElementById('btn-cropper-label');
  const btnIcon = document.getElementById('btn-cropper-icon');
  const toggleBtn = document.getElementById('btn-toggle-cropper');
  const cancelBtn = document.getElementById('btn-cancel-crop');
  const clearBtn = document.getElementById('btn-clear-crop');

  if (cropperInstance) {
    // 1. ZUSCHNITT ANWENDEN
    const data = cropperInstance.getData(true);
    currentEditSettings.crop = {
      x: Math.round(data.x),
      y: Math.round(data.y),
      width: Math.round(data.width),
      height: Math.round(data.height),
      is_percent: false
    };

    const croppedCanvas = cropperInstance.getCroppedCanvas();
    cropperInstance.destroy();
    cropperInstance = null;

    if (croppedCanvas) {
      if (!img.dataset.uncroppedSrc) {
        img.dataset.uncroppedSrc = img.src;
      }
      img.src = croppedCanvas.toDataURL('image/jpeg', 0.95);
    }

    if (badge) {
      badge.textContent = `Aktiv (${currentEditSettings.crop.width}×${currentEditSettings.crop.height} px)`;
      badge.className = 'text-[10px] text-emerald-400 font-mono font-semibold';
    }
    if (btnLabel) btnLabel.textContent = 'Zuschnitt ändern';
    if (btnIcon) btnIcon.textContent = '✂️';
    if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition flex items-center justify-center gap-1.5 shadow-sm';
    if (cancelBtn) cancelBtn.classList.add('hidden');
    if (clearBtn) clearBtn.classList.remove('hidden');

    showToast(`Bildausschnitt (${currentEditSettings.crop.width}×${currentEditSettings.crop.height} px) übernommen. Original bleibt 100% unberührt.`, false);
  } else {
    // 2. RAHMEN AUFZIEHEN
    if (typeof Cropper === 'undefined') {
      showToast('Cropper-Bibliothek wird initialisiert...', true);
      return;
    }

    if (img.dataset.uncroppedSrc) {
      const savedCrop = currentEditSettings.crop;
      const prevUncropped = img.dataset.uncroppedSrc;
      img.src = prevUncropped;

      img.onload = () => {
        img.onload = null;
        initCropperWithData(img, savedCrop);
      };
      return;
    }

    initCropperWithData(img, currentEditSettings.crop);
  }
}

function initCropperWithData(img, cropData) {
  const badge = document.getElementById('cropper-status-badge');
  const btnLabel = document.getElementById('btn-cropper-label');
  const btnIcon = document.getElementById('btn-cropper-icon');
  const toggleBtn = document.getElementById('btn-toggle-cropper');
  const cancelBtn = document.getElementById('btn-cancel-crop');
  const clearBtn = document.getElementById('btn-clear-crop');

  cropperInstance = new Cropper(img, {
    aspectRatio: currentCropperRatio,
    viewMode: 1,
    autoCropArea: 0.85,
    movable: false,
    zoomable: false,
    rotatable: false,
    scalable: false,
    ready() {
      if (cropData) {
        cropperInstance.setData(cropData);
      }
    }
  });

  if (badge) {
    badge.textContent = 'Rahmen ziehen...';
    badge.className = 'text-[10px] text-amber-400 font-mono animate-pulse';
  }
  if (btnLabel) btnLabel.textContent = 'Zuschnitt anwenden ✓';
  if (btnIcon) btnIcon.textContent = '✓';
  if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-md shadow-emerald-500/20';
  if (cancelBtn) cancelBtn.classList.remove('hidden');
  if (clearBtn) clearBtn.classList.add('hidden');
}

function cancelCropping() {
  const img = document.getElementById('modal-img');
  const badge = document.getElementById('cropper-status-badge');
  const btnLabel = document.getElementById('btn-cropper-label');
  const btnIcon = document.getElementById('btn-cropper-icon');
  const toggleBtn = document.getElementById('btn-toggle-cropper');
  const cancelBtn = document.getElementById('btn-cancel-crop');
  const clearBtn = document.getElementById('btn-clear-crop');

  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }

  if (currentEditSettings.crop) {
    if (img && img.dataset.uncroppedSrc) {
      applyClientCropPreview(img, currentEditSettings.crop);
    }
    if (badge) {
      badge.textContent = `Aktiv (${currentEditSettings.crop.width}×${currentEditSettings.crop.height} px)`;
      badge.className = 'text-[10px] text-emerald-400 font-mono font-semibold';
    }
    if (btnLabel) btnLabel.textContent = 'Zuschnitt ändern';
    if (clearBtn) clearBtn.classList.remove('hidden');
  } else {
    if (badge) {
      badge.textContent = 'inaktiv';
      badge.className = 'text-[10px] text-slate-500 font-mono';
    }
    if (btnLabel) btnLabel.textContent = 'Rahmen aufziehen';
    if (clearBtn) clearBtn.classList.add('hidden');
  }

  if (btnIcon) btnIcon.textContent = '✂️';
  if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-sm';
  if (cancelBtn) cancelBtn.classList.add('hidden');
}

function clearActiveCrop() {
  const img = document.getElementById('modal-img');
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  currentEditSettings.crop = null;

  if (img && img.dataset.uncroppedSrc) {
    img.src = img.dataset.uncroppedSrc;
    delete img.dataset.uncroppedSrc;
  }

  const badge = document.getElementById('cropper-status-badge');
  const btnLabel = document.getElementById('btn-cropper-label');
  const btnIcon = document.getElementById('btn-cropper-icon');
  const toggleBtn = document.getElementById('btn-toggle-cropper');
  const cancelBtn = document.getElementById('btn-cancel-crop');
  const clearBtn = document.getElementById('btn-clear-crop');

  if (badge) {
    badge.textContent = 'inaktiv';
    badge.className = 'text-[10px] text-slate-500 font-mono';
  }
  if (btnLabel) btnLabel.textContent = 'Rahmen aufziehen';
  if (btnIcon) btnIcon.textContent = '✂️';
  if (toggleBtn) toggleBtn.className = 'flex-1 px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-sm';
  if (cancelBtn) cancelBtn.classList.add('hidden');
  if (clearBtn) clearBtn.classList.add('hidden');

  showToast('Zuschnitt aufgehoben (Vollbild wiederhergestellt).', false);
}

function applyClientCropPreview(img, crop) {
  if (!img || !crop || !crop.width || !crop.height) return;
  const originalSrc = img.dataset.uncroppedSrc || img.src;
  if (!img.dataset.uncroppedSrc) {
    img.dataset.uncroppedSrc = originalSrc;
  }

  const tempImg = new Image();
  tempImg.crossOrigin = 'anonymous';
  tempImg.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = crop.width;
    canvas.height = crop.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(
      tempImg,
      crop.x, crop.y, crop.width, crop.height,
      0, 0, crop.width, crop.height
    );
    img.src = canvas.toDataURL('image/jpeg', 0.95);
  };
  tempImg.src = originalSrc;
}

async function saveEditSettingsToBackend() {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein aktives Bild im Detailfenster geöffnet.', true);
    return;
  }

  const saveBtn = document.getElementById('btn-save-edit-settings');
  const originalHtml = saveBtn ? saveBtn.innerHTML : '';
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Speichere Parameter...</span>';
  }

  try {
    const payload = {
      path: currentModalImageDetails.filePath,
      brightness: currentEditSettings.brightness,
      contrast: currentEditSettings.contrast,
      gamma: currentEditSettings.gamma,
      sharpness: currentEditSettings.sharpness,
      rotation: currentEditSettings.rotation,
      fine_rotation: currentEditSettings.fine_rotation,
      flip_h: currentEditSettings.flip_h,
      saturation: currentEditSettings.saturation,
      invert: currentEditSettings.invert,
      crop: currentEditSettings.crop
    };

    const res = await fetch('/images/edit-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Status ${res.status}`);
    showToast('Transformations-Parameter erfolgreich in SQLite & Qdrant gesichert!', false);
  } catch (err) {
    console.error('Fehler beim Speichern der edit_settings:', err);
    showToast(`Speichern fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = originalHtml;
    }
  }
}

function exportProcessedImage(format = 'jpg') {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein aktives Bild ausgewählt.', true);
    return;
  }

  showToast(`Rendere hochauflösendes ${format.toUpperCase()} via Pillow...`, false);

  const params = new URLSearchParams({
    path: currentModalImageDetails.filePath,
    format: format,
    brightness: currentEditSettings.brightness,
    contrast: currentEditSettings.contrast,
    gamma: currentEditSettings.gamma,
    sharpness: currentEditSettings.sharpness,
    rotation: currentEditSettings.rotation,
    fine_rotation: currentEditSettings.fine_rotation,
    flip_h: currentEditSettings.flip_h,
    saturation: currentEditSettings.saturation,
    invert: currentEditSettings.invert
  });

  if (currentEditSettings.crop) {
    params.set('crop', JSON.stringify(currentEditSettings.crop));
  }

  const exportUrl = `/images/export?${params.toString()}`;
  const a = document.createElement('a');
  a.href = exportUrl;
  const baseName = (currentModalImageDetails.fileName || 'archivbild').split('.')[0];
  a.download = `${baseName}_bearbeitet.${format === 'tiff' ? 'tif' : 'jpg'}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}


// ================= SQLITE METADATEN-BEARBEITUNG =================

function toggleMetadataEditMode(forceState = null) {
  const content = document.getElementById('modal-metadata-content');
  const form = document.getElementById('modal-metadata-edit-form');
  const btnText = document.getElementById('modal-edit-meta-btn-text');
  if (!content || !form) return;

  const isEditing = forceState !== null ? !forceState : !form.classList.contains('hidden');

  if (isEditing) {
    // Wechsel zu Lesemodus
    form.classList.add('hidden');
    content.classList.remove('hidden');
    if (btnText) btnText.textContent = 'Bearbeiten';
  } else {
    // Wechsel zu Bearbeitungsmodus
    if (!currentModalImageDetails) return;
    document.getElementById('edit-meta-signature').value = currentModalImageDetails.signature || '';
    document.getElementById('edit-meta-title').value = currentModalImageDetails.title || '';
    document.getElementById('edit-meta-date').value = currentModalImageDetails.date || '';
    document.getElementById('edit-meta-creator').value = currentModalImageDetails.creator || '';
    document.getElementById('edit-meta-description').value = currentModalImageDetails.description || '';

    content.classList.add('hidden');
    form.classList.remove('hidden');
    if (btnText) btnText.textContent = 'Ansicht';
  }
}

async function saveMetadataEdit(event) {
  if (event) event.preventDefault();
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) {
    showToast('Kein aktives Bild ausgewählt.', true);
    return;
  }

  const saveBtn = document.getElementById('edit-meta-save-btn');
  const originalHtml = saveBtn ? saveBtn.innerHTML : '';
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Speichere in SQLite...</span>';
  }

  const newSig = document.getElementById('edit-meta-signature')?.value.trim() || null;
  const newTitle = document.getElementById('edit-meta-title')?.value.trim() || null;
  const newDate = document.getElementById('edit-meta-date')?.value.trim() || null;
  const newCreator = document.getElementById('edit-meta-creator')?.value.trim() || null;
  const newDesc = document.getElementById('edit-meta-description')?.value.trim() || null;

  try {
    const payload = {
      path: currentModalImageDetails.filePath,
      signature: newSig,
      title: newTitle,
      date: newDate,
      creator: newCreator,
      description: newDesc
    };

    const res = await fetch('/images/metadata', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler (${res.status})`);
    const data = await res.json();

    // Zustand aktualisieren
    currentModalImageDetails.signature = newSig;
    currentModalImageDetails.title = newTitle;
    currentModalImageDetails.date = newDate;
    currentModalImageDetails.creator = newCreator;
    currentModalImageDetails.description = newDesc;

    // Header Titel aktualisieren
    const titleElem = document.getElementById('modal-filename');
    if (titleElem) {
      titleElem.textContent = newTitle || currentModalImageDetails.fileName;
    }

    // Re-render Lesemodus
    renderModalMetadataReadView();
    toggleMetadataEditMode(false);

    showToast('Metadaten erfolgreich in SQLite & XMP gesichert!', false);
  } catch (err) {
    console.error('Fehler beim Speichern der Metadaten:', err);
    showToast(`Speichern fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = originalHtml;
    }
  }
}

function renderModalMetadataReadView() {
  const metaContainer = document.getElementById('modal-metadata-content');
  if (!metaContainer || !currentModalImageDetails) return;

  const meta = {
    title: currentModalImageDetails.title,
    date: currentModalImageDetails.date,
    creator: currentModalImageDetails.creator,
    signature: currentModalImageDetails.signature,
    description: currentModalImageDetails.description,
    keywords: currentModalImageDetails.keywords || [],
    copyright: currentModalImageDetails.copyright || null
  };

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
  if (currentModalImageDetails.width && currentModalImageDetails.height) {
    metaHtml += `
      <div>
        <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Auflösung</span>
        <span class="text-slate-400 font-mono text-xs">${currentModalImageDetails.width} &times; ${currentModalImageDetails.height} px</span>
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

  metaHtml += `
    <div class="pt-3 border-t border-slate-800 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">XMP-Sidecar (Dublin Core)</span>
        <span class="text-[10px] text-emerald-400 font-mono">Adobe / IPTC</span>
      </div>
      <div class="grid grid-cols-2 gap-1.5">
        <button type="button" onclick="downloadCurrentModalXmp()" class="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-emerald-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1 shadow-sm" title="Lädt die XMP-Metadaten als XML-Datei herunter">
          <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          <span>Download</span>
        </button>
        <button type="button" onclick="writeCurrentModalXmp()" class="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-blue-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1 shadow-sm" title="Speichert die .xmp Datei direkt neben das Master-Original auf Festplatte/NAS">
          <svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path></svg>
          <span>Speichern</span>
        </button>
      </div>
    </div>`;

  if (!metaHtml) {
    metaHtml = `
      <div class="text-center py-6 text-slate-500 space-y-1">
        <p class="text-[11px]">Keine Metadaten hinterlegt.</p>
        <button type="button" onclick="toggleMetadataEditMode(true)" class="text-[11px] text-amber-400 hover:underline">
          Jetzt Metadaten erfassen
        </button>
      </div>`;
  }

  metaContainer.innerHTML = metaHtml;
}




