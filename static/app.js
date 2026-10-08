/**
 * Historisches Bildarchiv - Frontend Logik (Vanilla JS)
 */

let activeCluster = null;
let currentModalImageDetails = null;
let osdViewer = null;
// Laufende Sequenznummern, um überholte asynchrone Antworten zu verwerfen
// (z. B. schnelles Wechseln zwischen Clustern oder Bildern)
let clusterDetailSeq = 0;
let modalOpenSeq = 0;
let isDeepZoomActive = false;
let isModalCardFlipped = false;
let currentTwoSidedInfo = null;
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
  initModalZoomAndPan();
  initSplitSliderDrag();
  // Vorbelegung Suche falls gewünscht
  const urlParams = new URLSearchParams(window.location.search);
  const q = urlParams.get('q');
  if (q) {
    setQueryAndSearch(q);
  }

  // Hintergrund-Import sofort reaktivieren, wenn Tab wieder in den Vordergrund tritt
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      checkIndexingProgress();
    }
  });
});

// --- Tab Navigation ---
function switchTab(tab) {
  const searchSec = document.getElementById('tab-search');
  const facesSec = document.getElementById('tab-faces');
  const networkSec = document.getElementById('tab-network');
  const importSec = document.getElementById('tab-import');
  const dupSec = document.getElementById('tab-duplicates');
  const lightboxSec = document.getElementById('tab-lightbox');
  const searchBtn = document.getElementById('tab-search-btn');
  const facesBtn = document.getElementById('tab-faces-btn');
  const networkBtn = document.getElementById('tab-network-btn');
  const importBtn = document.getElementById('tab-import-btn');
  const dupBtn = document.getElementById('tab-duplicates-btn');
  const lightboxBtn = document.getElementById('tab-lightbox-btn');

  // Alle Sektionen ausblenden
  if (searchSec) searchSec.classList.add('hidden');
  if (facesSec) facesSec.classList.add('hidden');
  if (networkSec) networkSec.classList.add('hidden');
  if (importSec) importSec.classList.add('hidden');
  if (dupSec) dupSec.classList.add('hidden');
  if (lightboxSec) lightboxSec.classList.add('hidden');

  const activeCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all bg-amber-500 text-slate-950 font-semibold shadow-sm flex items-center gap-2';
  const inactiveCls = 'px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 transition-all flex items-center gap-2';

  if (searchBtn) searchBtn.className = inactiveCls;
  if (facesBtn) facesBtn.className = inactiveCls;
  if (networkBtn) networkBtn.className = inactiveCls;
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
  } else if (tab === 'network') {
    if (networkSec) networkSec.classList.remove('hidden');
    if (networkBtn) networkBtn.className = activeCls;
    initNetworkTab();
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

let currentSearchQuery = '';
let currentSearchLimit = 24;
let currentSearchOffset = 0;
let currentSearchFilter = 'all';
let hasMoreSearchResults = false;
let currentSearchResults = [];
let currentRenderedResults = [];

async function executeSearch(query, limit = 24) {
  const spinner = document.getElementById('search-spinner');
  const grid = document.getElementById('results-grid');
  const empty = document.getElementById('search-empty');
  const resultsBar = document.getElementById('results-bar');
  const resultsCount = document.getElementById('results-count');
  const resultsQuery = document.getElementById('results-query');
  const loadMoreContainer = document.getElementById('search-load-more-container');

  currentSearchQuery = query;
  currentSearchLimit = parseInt(limit) || 24;
  currentSearchOffset = 0;
  currentSearchFilter = 'all';
  currentSearchResults = [];

  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');
  resultsBar.classList.add('hidden');
  const thesaurusBanner = document.getElementById('results-thesaurus-banner');
  if (thesaurusBanner) thesaurusBanner.classList.add('hidden');
  if (loadMoreContainer) loadMoreContainer.classList.add('hidden');

  const thresholdElem = document.getElementById('search-threshold');
  const threshold = thresholdElem ? parseFloat(thresholdElem.value) : 0;
  const stackToggle = document.getElementById('search-stack-variants');
  const stackVariants = stackToggle ? stackToggle.checked : true;

  try {
    let url = `/search/semantic?q=${encodeURIComponent(query)}&limit=${currentSearchLimit}&offset=0&stack_variants=${stackVariants}`;
    if (threshold > 0) {
      url += `&score_threshold=${threshold}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Fehler bei der Suche (${res.status})`);
    const data = await res.json();

    spinner.classList.add('hidden');
    resultsBar.classList.remove('hidden');
    currentSearchResults = data || [];

    // Kirchlicher Thesaurus Check für Bannereinblendung
    checkAndDisplayThesaurusBanner(query);

    const personCount = currentSearchResults.filter(i => i.match_type === 'person').length;
    const metaCount = currentSearchResults.filter(i => i.match_type === 'metadata').length;
    const clipCount = currentSearchResults.filter(i => i.match_type === 'clip').length;

    let countHtml = `<span>${currentSearchResults.length} Treffer gefunden</span>`;
    if (personCount > 0) {
      countHtml = `<span class="text-emerald-400 font-semibold">👤 ${personCount} Personen-Treffer</span>` + 
                  (clipCount > 0 ? ` <span class="text-slate-400">(${clipCount} Motive)</span>` : '');
    }
    resultsCount.innerHTML = countHtml;
    resultsQuery.textContent = `Suchbegriff: "${query}"`;

    const addAllBtn = document.getElementById('add-all-results-to-lightbox-btn');
    if (addAllBtn) {
      if (data.length > 0) addAllBtn.classList.remove('hidden');
      else addAllBtn.classList.add('hidden');
    }

    if (data.length === 0) {
      empty.classList.remove('hidden');
      empty.querySelector('p').textContent = `Keine Treffer für "${query}"`;
      updateLoadMoreVisibility(0);
      return;
    }

    updateSearchFilterPills();
    updateLoadMoreVisibility(data.length);
    renderSearchResults(getFilteredSearchResults(), grid);
  } catch (err) {
    spinner.classList.add('hidden');
    showToast(`Fehler: ${err.message}`, true);
  }
}

function updateSearchFilterPills() {
  const container = document.getElementById('results-filter-pills');
  if (!container) return;

  const personCount = currentSearchResults.filter(i => i.match_type === 'person').length;
  const metaCount = currentSearchResults.filter(i => i.match_type === 'metadata').length;
  const clipCount = currentSearchResults.filter(i => i.match_type === 'clip').length;

  const typesCount = (personCount > 0 ? 1 : 0) + (metaCount > 0 ? 1 : 0) + (clipCount > 0 ? 1 : 0);
  if (typesCount <= 1) {
    container.innerHTML = '';
    return;
  }

  const pillClass = (type) => currentSearchFilter === type 
    ? 'px-2.5 py-0.5 rounded-lg text-xs font-semibold bg-amber-500 text-slate-950 shadow-sm cursor-pointer transition'
    : 'px-2.5 py-0.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer transition';

  let html = `
    <button type="button" onclick="setSearchFilter('all')" class="${pillClass('all')}">
      Alle (${currentSearchResults.length})
    </button>
  `;
  if (personCount > 0) {
    html += `
      <button type="button" onclick="setSearchFilter('person')" class="${pillClass('person')}">
        👤 Personen (${personCount})
      </button>
    `;
  }
  if (metaCount > 0) {
    html += `
      <button type="button" onclick="setSearchFilter('metadata')" class="${pillClass('metadata')}">
        📝 Metadaten (${metaCount})
      </button>
    `;
  }
  if (clipCount > 0) {
    html += `
      <button type="button" onclick="setSearchFilter('clip')" class="${pillClass('clip')}">
        🔍 Bildmotive (${clipCount})
      </button>
    `;
  }
  container.innerHTML = html;
}

function setSearchFilter(filterType) {
  currentSearchFilter = filterType;
  updateSearchFilterPills();
  const filtered = getFilteredSearchResults();
  const grid = document.getElementById('results-grid');
  renderSearchResults(filtered, grid);
  const resultsCount = document.getElementById('results-count');
  if (resultsCount) {
    if (filterType === 'all') {
      resultsCount.textContent = `${currentSearchResults.length} Treffer gefunden`;
    } else {
      resultsCount.textContent = `Zeige ${filtered.length} von ${currentSearchResults.length} Treffern (${filterType})`;
    }
  }
}

function getFilteredSearchResults() {
  if (currentSearchFilter === 'all') return currentSearchResults;
  return currentSearchResults.filter(i => i.match_type === currentSearchFilter);
}

function updateLoadMoreVisibility(lastBatchCount) {
  const container = document.getElementById('search-load-more-container');
  const info = document.getElementById('search-load-more-info');
  if (!container) return;

  if (lastBatchCount >= currentSearchLimit) {
    container.classList.remove('hidden');
    hasMoreSearchResults = true;
    if (info) {
      info.textContent = `${currentSearchResults.length} Ergebnisse geladen (Klicken zum Nachladen weiterer Treffer)`;
    }
  } else {
    container.classList.add('hidden');
    hasMoreSearchResults = false;
  }
}

async function loadMoreSearchResults() {
  const btn = document.getElementById('search-load-more-btn');
  const spinner = document.getElementById('search-load-more-spinner');
  const icon = document.getElementById('search-load-more-icon');
  const text = document.getElementById('search-load-more-text');

  if (spinner) spinner.classList.remove('hidden');
  if (icon) icon.classList.add('hidden');
  if (text) text.textContent = 'Lade weitere Treffer...';
  if (btn) btn.disabled = true;

  const thresholdElem = document.getElementById('search-threshold');
  const threshold = thresholdElem ? parseFloat(thresholdElem.value) : 0;
  const stackToggle = document.getElementById('search-stack-variants');
  const stackVariants = stackToggle ? stackToggle.checked : true;

  currentSearchOffset += currentSearchLimit;

  try {
    let url = `/search/semantic?q=${encodeURIComponent(currentSearchQuery)}&limit=${currentSearchLimit}&offset=${currentSearchOffset}&stack_variants=${stackVariants}`;
    if (threshold > 0) {
      url += `&score_threshold=${threshold}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Fehler beim Nachladen (${res.status})`);
    const newData = await res.json();

    if (newData.length === 0) {
      updateLoadMoreVisibility(0);
      showToast('Keine weiteren Treffer vorhanden.', false);
    } else {
      currentSearchResults = currentSearchResults.concat(newData);
      updateSearchFilterPills();
      updateLoadMoreVisibility(newData.length);
      const grid = document.getElementById('results-grid');
      renderSearchResults(getFilteredSearchResults(), grid);
      const resultsCount = document.getElementById('results-count');
      if (resultsCount) {
        resultsCount.textContent = `${currentSearchResults.length} Treffer geladen`;
      }
      showToast(`+${newData.length} weitere Treffer nachgeladen.`, false);
    }
  } catch (err) {
    showToast(`Fehler beim Nachladen: ${err.message}`, true);
  } finally {
    if (spinner) spinner.classList.add('hidden');
    if (icon) icon.classList.remove('hidden');
    if (text) text.textContent = 'Mehr Ergebnisse laden';
    if (btn) btn.disabled = false;
  }
}

function renderSearchResults(items, container) {
  container.innerHTML = '';
  currentRenderedResults = items || [];
  const hasPersonMatches = currentSearchResults.some(i => i.match_type === 'person');

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
          onclick="event.stopPropagation(); openStackModalByPath('${escapeHtml(item.file_path).replace(/'/g, "\\'")}')"
          class="absolute top-2 left-2 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500 text-slate-950 shadow-md hover:bg-amber-400 transition-all flex items-center gap-1 z-10 backdrop-blur-sm"
          title="Dieser Bildstapel fasst ${item.variants_count + 1} verwandte Aufnahmen/Duplikate zusammen. Klicken zum Vergleichen."
        >
          <span>📚</span>
          <span>+${item.variants_count} <span class="hidden sm:inline">Varianten</span></span>
        </button>`;
    }

    // Treffer-Typ Badge (Person / Metadaten / Bildmotiv)
    let matchTypeBadgeHtml = '';
    const badgeLeftClass = isStack ? 'left-28' : 'left-2';
    if (item.match_type === 'person') {
      const personName = item.matched_query || (item.persons && item.persons[0]) || 'Person';
      matchTypeBadgeHtml = `
        <span class="absolute top-2 ${badgeLeftClass} px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500 text-slate-950 shadow-md backdrop-blur-sm z-10 flex items-center gap-1" title="Namentlich bekannte Person: ${escapeHtml(personName)}">
          <span>👤</span>
          <span class="truncate max-w-[110px]">${escapeHtml(personName)}</span>
        </span>`;
    } else if (item.match_type === 'metadata') {
      matchTypeBadgeHtml = `
        <span class="absolute top-2 ${badgeLeftClass} px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500 text-slate-950 shadow-md backdrop-blur-sm z-10 flex items-center gap-1" title="Archivischer Metadaten-Treffer: ${escapeHtml(item.matched_query || '')}">
          <span>📝</span>
          <span class="truncate max-w-[110px]">${escapeHtml(item.matched_query || 'Metadaten')}</span>
        </span>`;
    } else if (item.match_type === 'clip' && hasPersonMatches) {
      matchTypeBadgeHtml = `
        <span class="absolute top-2 ${badgeLeftClass} px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900/85 text-slate-300 border border-slate-700/80 backdrop-blur-sm z-10 flex items-center gap-1" title="Optischer Bildinhalt (CLIP-Vektorsuche)">
          <span>🔍</span>
          <span>Bildmotiv</span>
        </span>`;
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
    if (item.iconclass) {
      metaBadgesHtml += `<span class="px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-500/40 text-purple-300 font-mono text-[10px] flex items-center gap-1" title="Iconclass: ${escapeHtml(item.iconclass)}${item.thesaurus_category ? ' (' + escapeHtml(item.thesaurus_category) + ')' : ''}">🏛️ ${escapeHtml(item.iconclass)}</span>`;
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
        ${matchTypeBadgeHtml}
        <span class="absolute top-2 right-2 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${scoreColor} backdrop-blur-md">
          ${scorePct}% Score
        </span>
        <!-- Leuchttisch Pin Button unten links -->
        <button
          type="button"
          onclick="toggleLightboxCard(event, '${escapeHtml(item.file_path).replace(/'/g, "\\'")}')"
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
        openStackModal(item);
      } else {
        openImageModal(item.file_path, item.file_name);
      }
    });
    container.appendChild(card);
  });
}

// --- Bildstapel & Varianten Modal ---

function openStackModal(target) {
  let item = null;
  if (typeof target === 'object' && target !== null) {
    item = target;
  } else if (typeof target === 'string') {
    item = (currentRenderedResults || []).find(i => i.file_path === target || i.id === target) ||
           (currentSearchResults || []).find(i => i.file_path === target || i.id === target);
  } else if (typeof target === 'number') {
    item = (currentRenderedResults && currentRenderedResults[target]) ||
           (currentSearchResults && currentSearchResults[target]);
  }
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

function openStackModalByPath(filePath) {
  openStackModal(filePath);
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

function normalizeClusterId(cid) {
  if (cid === null || cid === undefined) return '';
  const str = String(cid).trim();
  return str.startsWith('cluster_') ? str : `cluster_${str}`;
}

async function quickRenameClusterPrompt(clusterId, currentLabel) {
  const displayId = String(clusterId).replace('cluster_', '#');
  const newName = prompt(`Neuen Namen für Personen-Cluster ${displayId} eingeben:`, currentLabel || '');
  if (newName === null) return;
  const trimmed = newName.trim();
  if (!trimmed) {
    showToast('Name darf nicht leer sein.', true);
    return;
  }
  if (trimmed === (currentLabel || '')) return;

  try {
    showToast(`Speichere Name "${trimmed}"...`, false);
    const res = await fetch(`/faces/clusters/${encodeURIComponent(clusterId)}/label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: trimmed }),
    });
    if (!res.ok) throw new Error(`Fehler beim Speichern (${res.status})`);
    const data = await res.json();

    const normId = normalizeClusterId(clusterId);
    const target = allLoadedClusters.find(c => normalizeClusterId(c.cluster_id) === normId);
    if (target) {
      target.label = trimmed;
    }
    if (activeCluster && normalizeClusterId(activeCluster.cluster_id) === normId) {
      activeCluster.label = trimmed;
      const cdTitleText = document.getElementById('cd-title-text');
      if (cdTitleText) cdTitleText.textContent = trimmed;
      const cdBadge = document.getElementById('cd-named-badge');
      if (cdBadge) cdBadge.classList.remove('hidden');
      const cdInput = document.getElementById('cluster-label-input');
      if (cdInput) cdInput.value = trimmed;
    }

    updateClusterCounts();
    applyClusterFilters();
    showToast(`✓ Name "${trimmed}" für ${data.updated_faces} Gesichter gespeichert!`, false);
  } catch (err) {
    showToast(`Fehler beim Umbenennen: ${err.message}`, true);
  }
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

let clusterPageSize = 60;
let clusterCurrentLimit = 60;

function resetClusterPagination() {
  clusterCurrentLimit = clusterPageSize;
}

window.loadMoreClusters = function() {
  clusterCurrentLimit += clusterPageSize;
  applyClusterFilters(false);
};

function applyClusterFilters(resetLimit = true) {
  const grid = document.getElementById('clusters-grid');
  const empty = document.getElementById('clusters-empty');
  const paginContainer = document.getElementById('clusters-pagination-container');
  const pageInfo = document.getElementById('clusters-page-info');
  const loadMoreCount = document.getElementById('clusters-load-more-count');
  if (!grid || !empty) return;

  if (resetLimit) {
    clusterCurrentLimit = clusterPageSize;
  }

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
    if (paginContainer) paginContainer.classList.add('hidden');
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

  const totalCount = filtered.length;
  const toRender = filtered.slice(0, clusterCurrentLimit);

  toRender.forEach(c => {
    const card = document.createElement('div');
    card.className = 'group bg-slate-900 border border-slate-800 hover:border-amber-500/40 rounded-xl overflow-hidden p-4 shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 cursor-pointer flex flex-col items-center text-center relative';

    const displayName = c.label || `Person ${String(c.cluster_id).replace('cluster_', '#')}`;
    const avatarSrc = c.preview_image || (`/faces/clusters/${encodeURIComponent(c.cluster_id)}/preview`);
    const defaultPlaceholder = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%231e293b"><circle cx="50" cy="50" r="40" fill="%23334155"/></svg>';

    card.innerHTML = `
      <!-- Quick Rename Button -->
      <button type="button"
        onclick="event.stopPropagation(); quickRenameClusterPrompt('${escapeHtml(c.cluster_id)}', '${escapeHtml(c.label || '')}')"
        class="absolute top-2.5 right-2.5 p-1.5 rounded-lg bg-slate-800/80 hover:bg-amber-500 hover:text-slate-950 text-slate-400 hover:text-slate-950 transition opacity-0 group-hover:opacity-100 focus:opacity-100 z-10 shadow-sm"
        title="Personenname direkt bearbeiten">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
        </svg>
      </button>

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

  if (paginContainer) {
    if (clusterCurrentLimit < totalCount) {
      paginContainer.classList.remove('hidden');
      const remaining = totalCount - clusterCurrentLimit;
      const nextBatch = Math.min(clusterPageSize, remaining);
      if (pageInfo) pageInfo.textContent = `Zeige ${toRender.length} von ${totalCount} Personen-Clustern`;
      if (loadMoreCount) loadMoreCount.textContent = `+${nextBatch}`;
    } else {
      paginContainer.classList.add('hidden');
    }
  }
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
  const mySeq = ++clusterDetailSeq;
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
  clearClusterSharedFilter(false);
  loadClusterCoOccurrences(cluster.cluster_id);

  const displayName = cluster.label || `Person ${String(cluster.cluster_id).replace('cluster_', '#')}`;
  const titleText = document.getElementById('cd-title-text');
  if (titleText) {
    titleText.textContent = displayName;
  } else if (title) {
    title.textContent = displayName;
  }
  const namedBadge = document.getElementById('cd-named-badge');
  if (namedBadge) {
    if (cluster.label && cluster.label.trim()) {
      namedBadge.classList.remove('hidden');
    } else {
      namedBadge.classList.add('hidden');
    }
  }
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
      if (mySeq === clusterDetailSeq) {
        showToast(`Fehler beim Laden der Bilder: ${err.message}`, true);
      }
    }
  }

  // Inzwischen wurde ein anderes Cluster geöffnet (oder die Ansicht geschlossen):
  // Diese veraltete Antwort darf das Bildergitter nicht mehr überschreiben.
  if (mySeq !== clusterDetailSeq || activeCluster !== cluster) return;

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
        <div class="min-w-0 flex-1 truncate">
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
            type="button"
            id="btn-cluster-inspect-${idx}"
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

    // Klick auf das Bild oder Großansicht öffnet das Modal mit hervorgehobener Zielperson
    const inspectBtn = card.querySelector(`#btn-cluster-inspect-${idx}`);
    const openThisModal = () => openClusterFaceModal(face.file_path, fileName, face.face_id, cluster.cluster_id, cluster.label);
    if (inspectBtn) inspectBtn.addEventListener('click', openThisModal);
    wrapElem.addEventListener('click', openThisModal);
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
  clearClusterSharedFilter(false);
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
  const saveBtn = document.getElementById('cluster-label-save-btn');
  const saveBtnIcon = document.getElementById('cluster-label-save-btn-icon');
  const saveBtnText = document.getElementById('cluster-label-save-btn-text');
  const feedback = document.getElementById('cluster-label-feedback');

  const label = input ? input.value.trim() : '';
  if (!label) return;

  // Immediate loading state feedback
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.classList.add('opacity-80', 'cursor-wait');
  }
  if (saveBtnIcon) saveBtnIcon.innerHTML = '<span class="inline-block animate-spin">⏳</span>';
  if (saveBtnText) saveBtnText.textContent = 'Speichern...';
  if (feedback) feedback.className = 'hidden';

  try {
    const res = await fetch(`/faces/clusters/${encodeURIComponent(activeCluster.cluster_id)}/label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    });

    if (!res.ok) throw new Error(`Fehler beim Speichern (${res.status})`);
    const data = await res.json();

    // 1. In-Memory Active Cluster aktualisieren
    activeCluster.label = label;

    // 2. Normalisierter Abgleich in allLoadedClusters
    const normActiveId = normalizeClusterId(activeCluster.cluster_id);
    const target = allLoadedClusters.find(c => normalizeClusterId(c.cluster_id) === normActiveId);
    if (target) {
      target.label = label;
    }

    // 3. Header im Detail-View sofort anpassen
    const cdTitle = document.getElementById('cd-title');
    const cdTitleText = document.getElementById('cd-title-text');
    if (cdTitleText) {
      cdTitleText.textContent = label;
    } else if (cdTitle) {
      cdTitle.textContent = label;
    }
    const cdNamedBadge = document.getElementById('cd-named-badge');
    if (cdNamedBadge) cdNamedBadge.classList.remove('hidden');

    // 4. Übersichtskarten & Zähler direkt und ohne Neuladen synchronisieren!
    updateClusterCounts();
    applyClusterFilters();

    // 5. Begleitpersonen-Netzwerk im Hintergrund mit neuem Namen auffrischen
    loadClusterCoOccurrences(activeCluster.cluster_id);

    // 6. Sofortiges visuelles Feedback am Eingabefeld & Button
    if (input) {
      input.classList.remove('border-slate-700', 'focus:ring-amber-500/50');
      input.classList.add('border-emerald-500', 'ring-2', 'ring-emerald-500/40', 'bg-emerald-950/20');
    }

    if (saveBtn) {
      saveBtn.classList.remove('bg-amber-500', 'hover:bg-amber-400', 'text-slate-950', 'opacity-80', 'cursor-wait');
      saveBtn.classList.add('bg-emerald-600', 'hover:bg-emerald-500', 'text-white');
    }
    if (saveBtnIcon) saveBtnIcon.textContent = '✓';
    if (saveBtnText) saveBtnText.textContent = 'Gespeichert!';

    if (feedback) {
      const faceCountStr = data.updated_faces ? `(${data.updated_faces} ${data.updated_faces === 1 ? 'Porträt' : 'Porträts'})` : '';
      feedback.innerHTML = `<span>✓ Gespeichert</span> <span class="opacity-80 font-normal">${faceCountStr}</span>`;
      feedback.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-semibold';
    }

    showToast(`✓ Name "${label}" erfolgreich für ${data.updated_faces} Gesichter gespeichert!`, false);

    // Nach 2,5 Sekunden den Button & das Feld wieder unaufdringlich zurücksetzen
    setTimeout(() => {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.classList.remove('bg-emerald-600', 'hover:bg-emerald-500', 'text-white', 'opacity-80', 'cursor-wait');
        saveBtn.classList.add('bg-amber-500', 'hover:bg-amber-400', 'text-slate-950');
      }
      if (saveBtnIcon) saveBtnIcon.textContent = '💾';
      if (saveBtnText) saveBtnText.textContent = 'Speichern';
      if (input) {
        input.classList.remove('border-emerald-500', 'ring-2', 'ring-emerald-500/40', 'bg-emerald-950/20');
        input.classList.add('border-slate-700', 'focus:ring-amber-500/50');
      }
      if (feedback) feedback.className = 'hidden';
    }, 2500);

  } catch (err) {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.classList.remove('opacity-80', 'cursor-wait');
    }
    if (saveBtnIcon) saveBtnIcon.textContent = '💾';
    if (saveBtnText) saveBtnText.textContent = 'Speichern';
    if (feedback) {
      feedback.innerHTML = `<span>⚠️ ${escapeHtml(err.message)}</span>`;
      feedback.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400 text-xs font-semibold';
    }
    showToast(`Fehler beim Speichern: ${err.message}`, true);
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

let currentModalTargetFaceContext = null;
let targetFaceBoxCoords = null;

function openClusterFaceModal(filePath, fileName, faceId, clusterId, clusterLabel) {
  const personName = clusterLabel || (clusterId ? `Person ${clusterId.replace('cluster_', '#')}` : 'Diese Person');
  openImageModal(filePath, fileName, null, {
    faceId: faceId || null,
    clusterId: clusterId || null,
    clusterLabel: clusterLabel || '',
    personName
  });
}

async function openImageModal(filePath, fileName, cacheBuster = null, targetFaceContext = null) {
  const modal = document.getElementById('image-modal');
  const img = document.getElementById('modal-img');
  const title = document.getElementById('modal-filename');
  const pathElem = document.getElementById('modal-filepath');
  const rawLink = document.getElementById('modal-raw-link');
  const similarBtn = document.getElementById('modal-similar-btn');
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const facesList = document.getElementById('modal-faces-list');

  const mySeq = ++modalOpenSeq;
  currentModalImageDetails = { filePath, fileName };
  targetFaceBoxCoords = null;

  toggleCropMode(false);
  toggleSplitSlider(false);
  toggleDeepZoomMode(false);
  toggleModalCardFlip(false);
  currentTwoSidedInfo = null;
  resetModalZoom();

  // Cluster-Personen-Kontrollleiste im Modal steuern
  const verifyBanner = document.getElementById('modal-cluster-verify-banner');
  const verifyPerson = document.getElementById('modal-cluster-verify-person');
  if (verifyBanner) {
    if (currentModalTargetFaceContext) {
      verifyBanner.classList.remove('hidden');
      if (verifyPerson) {
        verifyPerson.textContent = currentModalTargetFaceContext.personName;
      }
      // Gesichtsrahmen automatisch aktivieren
      setFaceBoundingBoxesVisible(true);
    } else {
      verifyBanner.classList.add('hidden');
    }
  }

  const backToOverviewBtn = document.getElementById('modal-back-to-overview-btn') || document.getElementById('modal-back-to-cluster-btn');
  const backToOverviewLabel = document.getElementById('modal-back-to-overview-label');
  if (backToOverviewBtn) {
    backToOverviewBtn.classList.remove('hidden');
    if (backToOverviewLabel) {
      if (currentModalTargetFaceContext || (typeof activeCluster !== 'undefined' && activeCluster)) {
        backToOverviewLabel.textContent = 'Zurück zum Cluster';
      } else {
        backToOverviewLabel.textContent = 'Zurück zur Übersicht';
      }
    }
  }

  const displayTitle = fileName || filePath.split('/').pop();
  title.textContent = displayTitle;
  title.title = displayTitle;
  pathElem.textContent = filePath;
  pathElem.title = filePath;
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
  // WICHTIG: Zuschnitt-Quelle des vorherigen Bildes verwerfen. Sonst stellen
  // loadModalEditSettings()/resetAllImageAdjustments() das ALTE Bild wieder her
  // (Symptom: "es bleibt immer dasselbe Bild stehen").
  delete img.dataset.uncroppedSrc;
  img.onload = () => {
    if (mySeq !== modalOpenSeq) return;
    scheduleHistogramRender();
    if (isSplitSliderActive) {
      const origImg = document.getElementById('modal-split-original-img');
      if (origImg) origImg.src = img.dataset.uncroppedSrc || img.src;
    }
  };
  img.src = `/images/serve?path=${encodeURIComponent(filePath)}&max_dim=1200${cbParam}`;

  // Duplikats- & Variantenprüfung im Hintergrund
  checkModalImageVariants(filePath);

  // Zweiblatt-Prüfung (Recto/Verso) & 3D-Karten-Flip vorbereiten
  loadTwoSidedModalInfo(filePath);

  modal.classList.remove('hidden');

  const metaContainer = document.getElementById('modal-metadata-content');
  if (metaContainer) {
    metaContainer.innerHTML = '<span class="text-slate-500 font-mono">Lade Archiv-Metadaten...</span>';
  }

  // Lade Gesichtsdetails und Metadaten aus der Datenbank
  try {
    const res = await fetch(`/images/details?path=${encodeURIComponent(filePath)}`);
    if (mySeq !== modalOpenSeq) return; // inzwischen anderes Bild geöffnet
    if (!res.ok) return;
    const data = await res.json();
    if (mySeq !== modalOpenSeq) return;

    // Titel anpassen, falls archivalischer Titel vorhanden ist
    if (data.metadata && data.metadata.title) {
      title.textContent = data.metadata.title;
      title.title = data.metadata.title;
      pathElem.textContent = `${fileName} • ${filePath}`;
      pathElem.title = `${fileName} • ${filePath}`;
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
    resetImageEditHistory();
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
            <div class="flex items-center justify-between mb-1">
              <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">Archivsignatur</span>
              <button type="button" onclick="copyArchivalSignature('${escapeHtml(meta.signature)}')" class="text-[10px] text-amber-400 hover:text-amber-300 transition flex items-center gap-1 font-medium" title="Archivsignatur in Zwischenablage kopieren">
                <span>📋</span> <span>Signatur kopieren</span>
              </button>
            </div>
            <span class="text-slate-200 font-mono text-xs bg-slate-950/80 px-2 py-1 rounded border border-slate-700/80 inline-block font-semibold select-all">${escapeHtml(meta.signature)}</span>
          </div>`;
      }
      if (meta.iconclass || data.iconclass) {
        const ic = meta.iconclass || data.iconclass;
        metaHtml += `
          <div>
            <span class="text-purple-400 text-[10px] uppercase tracking-wider font-semibold block">Iconclass &amp; Thesaurus</span>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="text-purple-300 font-mono text-xs bg-purple-950/80 px-2 py-0.5 rounded border border-purple-500/40">🏛️ ${escapeHtml(ic)}</span>
              ${data.thesaurus_category ? `<span class="text-slate-400 text-[11px]">(${escapeHtml(data.thesaurus_category)})</span>` : ''}
            </div>
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

      // Wissenschaftlicher Zitiervorschlag Button
      metaHtml += `
        <div class="pt-2 border-t border-slate-800/80">
          <button type="button" onclick="copyArchivalCitation()" class="w-full py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-amber-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1.5 shadow-sm" title="Zitierfähige Quellenangabe mit Signatur, Titel, Datum und Urheber kopieren">
            <span>📝</span> <span>Zitiervorschlag kopieren</span>
          </button>
        </div>`;

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
        let isTargetFace = false;
        if (currentModalTargetFaceContext) {
          if (currentModalTargetFaceContext.faceId && String(f.face_id) === String(currentModalTargetFaceContext.faceId)) {
            isTargetFace = true;
          } else if (!currentModalTargetFaceContext.faceId && currentModalTargetFaceContext.clusterId && f.cluster_id === currentModalTargetFaceContext.clusterId) {
            isTargetFace = true;
          }
        }

        const tagWrapper = document.createElement('div');
        tagWrapper.className = 'inline-flex items-center rounded-lg border border-slate-700 bg-slate-800 overflow-hidden';

        const tagBtn = document.createElement('button');
        tagBtn.type = 'button';
        tagBtn.title = 'Klicken, um auf dieses Gesicht im Bild zu zoomen';
        tagBtn.onclick = () => focusFaceByIndex(idx);

        if (isTargetFace) {
          tagWrapper.className = 'inline-flex items-center rounded-lg bg-amber-500 text-slate-950 font-bold border border-amber-400 text-xs shadow-md shadow-amber-500/30 ring-2 ring-amber-400/50';
          tagBtn.className = 'px-2.5 py-1 hover:bg-amber-400 transition cursor-pointer flex items-center gap-1.5';
          const pName = currentModalTargetFaceContext.personName || f.label || 'Diese Person';
          tagBtn.innerHTML = `<span>⭐ Diese Person: ${escapeHtml(pName)}</span> <span class="font-mono text-[10px]">(${(f.det_score * 100).toFixed(0)}%)</span>`;
        } else {
          tagBtn.className = 'px-2 py-0.5 text-slate-300 hover:bg-slate-700/80 font-mono text-[11px] transition';
          const name = f.label || (f.cluster_id ? `Person ${f.cluster_id.replace('cluster_', '#')}` : `Gesicht #${idx + 1}`);
          tagBtn.textContent = `${name} (${(f.det_score * 100).toFixed(0)}%)`;
        }
        tagWrapper.appendChild(tagBtn);

        if (f.cluster_id) {
          const jumpBtn = document.createElement('button');
          jumpBtn.type = 'button';
          jumpBtn.title = `Zu allen Bildern von ${f.label || f.cluster_id} springen`;
          jumpBtn.className = isTargetFace
            ? 'px-1.5 py-1 bg-amber-600/40 hover:bg-amber-600/70 text-slate-950 transition border-l border-amber-600 text-xs'
            : 'px-1.5 py-0.5 bg-slate-900/60 hover:bg-cyan-500/20 text-cyan-400 hover:text-cyan-300 transition border-l border-slate-700 text-xs';
          jumpBtn.innerHTML = '👤';
          jumpBtn.onclick = (e) => {
            e.stopPropagation();
            jumpToCluster(f.cluster_id);
          };
          tagWrapper.appendChild(jumpBtn);
        }

        if (isTargetFace) {
          facesList.prepend(tagWrapper);
        } else {
          facesList.appendChild(tagWrapper);
        }
      });
    }

    // Bounding Boxes auf dem vergrößerten Bild platzieren
    function drawModalBoxes() {
      if (mySeq !== modalOpenSeq) return;
      wrapper.querySelectorAll('.face-bbox').forEach(e => e.remove());
      if (!data.faces || data.faces.length === 0) return;

      targetFaceBoxCoords = null;

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

        let isTargetFace = false;
        if (currentModalTargetFaceContext) {
          if (currentModalTargetFaceContext.faceId && String(f.face_id) === String(currentModalTargetFaceContext.faceId)) {
            isTargetFace = true;
          } else if (!currentModalTargetFaceContext.faceId && currentModalTargetFaceContext.clusterId && f.cluster_id === currentModalTargetFaceContext.clusterId) {
            isTargetFace = true;
          }
        }

        const box = document.createElement('div');
        box.id = `modal-face-box-${idx}`;
        box.style.position = 'absolute';
        box.style.left = `${left}%`;
        box.style.top = `${top}%`;
        box.style.width = `${width}%`;
        box.style.height = `${height}%`;

        const tag = document.createElement('div');

        if (isTargetFace) {
          box.className = 'face-bbox highlight-target';
          const pName = currentModalTargetFaceContext.personName || f.label || 'Diese Person';
          targetFaceBoxCoords = { left, top, width, height, name: pName, idx };
          tag.className = 'face-bbox-tag highlight-target-tag';
          tag.innerHTML = `⭐ <b>${escapeHtml(pName)}</b> <span class="font-mono text-[10px] opacity-90">(${(f.det_score * 100).toFixed(0)}%)</span>`;
        } else {
          box.className = currentModalTargetFaceContext ? 'face-bbox other-face' : 'face-bbox';
          tag.className = 'face-bbox-tag';
          tag.textContent = f.label || (f.cluster_id ? `Person ${f.cluster_id.replace('cluster_', '#')}` : `Gesicht #${idx + 1}`);
        }

        box.appendChild(tag);
        wrapper.appendChild(box);
      });
    }

    drawModalBoxes();
    if (!img.complete) {
      img.addEventListener('load', drawModalBoxes, { once: true });
    }

  } catch (err) {
    if (mySeq !== modalOpenSeq) return;
    facesList.innerHTML = '<span class="text-rose-400">Details nicht geladen</span>';
  }
}

function closeImageModal() {
  const modal = document.getElementById('image-modal');
  modal.classList.add('hidden');
  toggleModalFullscreen(false);
  toggleCropMode(false);
  toggleSplitSlider(false);
  toggleDeepZoomMode(false);
  resetModalZoom();
  closeModalXmpMenu();
  currentModalTargetFaceContext = null;
  targetFaceBoxCoords = null;
  document.getElementById('modal-cluster-verify-banner')?.classList.add('hidden');
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  resetAllImageAdjustments(true);
  resetImageEditHistory();
  toggleWideEditMode(false);
  toggleMetadataEditMode(false);
  switchModalSidebarTab('meta');
  toggleModalCardFlip(false);
  currentTwoSidedInfo = null;
  document.getElementById('modal-flip-btn')?.classList.add('hidden');
  document.getElementById('modal-verso-panel')?.classList.add('hidden');
  const versoImg = document.getElementById('modal-verso-img');
  if (versoImg) versoImg.src = '';
  currentModalImageDetails = null;
}

// Schließe Modal bei Klick auf den Hintergrund
document.getElementById('image-modal')?.addEventListener('click', (e) => {
  if (e.target.id === 'image-modal') {
    closeImageModal();
  }
});

// ================= ZWEIBLATT-LOGIK & 3D-KARTEN-FLIP (RECTO / VERSO) =================

async function loadTwoSidedModalInfo(filePath) {
  const flipBtn = document.getElementById('modal-flip-btn');
  const versoPanel = document.getElementById('modal-verso-panel');
  const versoImg = document.getElementById('modal-verso-img');
  const flipBtnLabel = document.getElementById('modal-flip-btn-label');
  const notesInput = document.getElementById('modal-verso-notes-input');
  const badge = document.getElementById('modal-verso-companion-badge');
  const panelTitle = document.getElementById('modal-verso-panel-title');

  if (flipBtn) flipBtn.classList.add('hidden');
  if (versoPanel) versoPanel.classList.add('hidden');
  if (versoImg) versoImg.src = '';
  toggleModalCardFlip(false);

  try {
    const res = await fetch(`/api/archive/two-sided?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) return;
    const data = await res.json();
    currentTwoSidedInfo = data;

    if (data.is_two_sided && data.companion_exists) {
      if (flipBtn) {
        flipBtn.classList.remove('hidden');
        if (flipBtnLabel) {
          flipBtnLabel.textContent = data.role === 'recto' ? 'Rückseite' : 'Vorderseite';
        }
      }
      if (versoImg && data.companion_serve_url) {
        versoImg.src = data.companion_serve_url;
      }
      if (versoPanel) {
        versoPanel.classList.remove('hidden');
        if (notesInput) {
          notesInput.value = data.verso_notes || '';
        }
        if (badge) {
          badge.textContent = data.companion_name || 'Verknüpft';
          badge.title = data.companion_path || '';
          badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 border border-amber-500/30 text-amber-300 truncate max-w-[150px]';
        }
        if (panelTitle) {
          panelTitle.textContent = data.role === 'recto' ? 'Rückseite & Notizen (Verso)' : 'Vorderseite & Notizen (Recto)';
        }
      }
    } else if (data.is_two_sided && !data.companion_exists) {
      // Wenn Dateimuster erkannt wurde, aber Partnerdatei fehlt
      if (versoPanel) {
        versoPanel.classList.remove('hidden');
        if (notesInput) notesInput.value = data.verso_notes || '';
        if (badge) {
          badge.textContent = `Erwartet: ${data.companion_name}`;
          badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/10 border border-rose-500/30 text-rose-300 truncate max-w-[150px]';
        }
      }
    }
  } catch (err) {
    console.warn('Fehler beim Laden der Zweiblatt-Informationen:', err);
  }
}

function toggleModalCardFlip(forceState = null) {
  const cardCube = document.getElementById('modal-card-cube');
  const flipBtnLabel = document.getElementById('modal-flip-btn-label');
  const panelFlipText = document.getElementById('modal-verso-panel-flip-text');

  if (forceState !== null) {
    isModalCardFlipped = !!forceState;
  } else {
    isModalCardFlipped = !isModalCardFlipped;
  }

  if (cardCube) {
    if (isModalCardFlipped) {
      cardCube.classList.add('is-flipped');
    } else {
      cardCube.classList.remove('is-flipped');
    }
  }

  if (flipBtnLabel) {
    if (currentTwoSidedInfo && currentTwoSidedInfo.role === 'verso') {
      flipBtnLabel.textContent = isModalCardFlipped ? 'Rückseite' : 'Vorderseite';
    } else {
      flipBtnLabel.textContent = isModalCardFlipped ? 'Vorderseite' : 'Rückseite';
    }
  }

  if (panelFlipText) {
    panelFlipText.textContent = isModalCardFlipped ? 'Zurückdrehen' : 'Karte umdrehen';
  }
}

async function saveModalVersoNotes() {
  if (!currentModalImageDetails || !currentModalImageDetails.filePath) return;
  const input = document.getElementById('modal-verso-notes-input');
  if (!input) return;

  const notes = input.value.trim();
  const saveBtn = document.getElementById('modal-verso-notes-save-btn');
  const origText = saveBtn ? saveBtn.innerHTML : '';
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span>⏳</span> <span>Speichern...</span>';
  }

  try {
    const res = await fetch('/api/archive/two-sided/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: currentModalImageDetails.filePath,
        notes: notes
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Fehler beim Speichern');
    }

    if (currentTwoSidedInfo) {
      currentTwoSidedInfo.verso_notes = notes;
    }
    showToast('Rückseiten-Notiz gespeichert & für Suche indexiert!', false);
  } catch (err) {
    console.error('Fehler beim Speichern der Rückseiten-Notiz:', err);
    showToast(`Fehler: ${err.message}`, true);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = origText;
    }
  }
}

// ================= IIIF IMAGE API 3.0 & OPEN SEADRAGON DEEP ZOOM =================

function encodeBase64Url(str) {
  try {
    return btoa(unescape(encodeURIComponent(str)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  } catch (e) {
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
}

function toggleDeepZoomMode(forceState = null) {
  const wrapper = document.getElementById('modal-deepzoom-wrapper');
  const bboxWrapper = document.getElementById('modal-bbox-wrapper');
  const btn = document.getElementById('modal-deepzoom-btn');
  const btnText = document.getElementById('modal-deepzoom-btn-text');
  if (!wrapper || !bboxWrapper) return;

  const nextState = forceState !== null ? forceState : !isDeepZoomActive;
  isDeepZoomActive = nextState;

  if (isDeepZoomActive) {
    // Falls Crop oder Split aktiv war, ausschalten
    toggleCropMode(false);
    toggleSplitSlider(false);

    bboxWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');

    if (btn) {
      btn.classList.add('bg-cyan-950', 'border-cyan-500/60', 'text-cyan-300');
      btn.classList.remove('bg-slate-800', 'text-slate-300', 'border-slate-700');
    }
    if (btnText) btnText.textContent = 'Standard-Ansicht';

    const filePath = currentModalImageDetails?.filePath;
    if (!filePath) return;

    const iiifId = encodeBase64Url(filePath);
    const infoUrl = `/api/iiif/${iiifId}/info.json`;

    if (typeof OpenSeadragon === 'undefined') {
      console.warn("OpenSeadragon ist nicht geladen.");
      return;
    }

    if (!osdViewer) {
      osdViewer = OpenSeadragon({
        id: "openseadragon-viewer",
        prefixUrl: "",
        showNavigationControl: false,
        animationTime: 0.3,
        blendTime: 0.1,
        constrainDuringPan: true,
        maxZoomPixelRatio: 4,
        minZoomImageRatio: 0.8,
        visibilityRatio: 0.9,
        wrapHorizontal: false,
        wrapVertical: false,
        tileSources: infoUrl,
      });

      // Floating Toolbar Buttons verdrahten
      document.getElementById('osd-zoom-in')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (osdViewer?.viewport) osdViewer.viewport.zoomBy(1.4);
      });
      document.getElementById('osd-zoom-out')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (osdViewer?.viewport) osdViewer.viewport.zoomBy(0.7);
      });
      document.getElementById('osd-home')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (osdViewer?.viewport) osdViewer.viewport.goHome();
      });
      document.getElementById('osd-actual-size')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (osdViewer?.viewport) {
          const imageZoom = osdViewer.viewport.imageToViewportZoom(1);
          osdViewer.viewport.zoomTo(imageZoom);
        }
      });
      document.getElementById('osd-rotate')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (osdViewer?.viewport) {
          const curRot = osdViewer.viewport.getRotation();
          osdViewer.viewport.setRotation((curRot + 90) % 360);
        }
      });
    } else {
      osdViewer.open(infoUrl);
    }
  } else {
    wrapper.classList.add('hidden');
    bboxWrapper.classList.remove('hidden');

    if (btn) {
      btn.classList.remove('bg-cyan-950', 'border-cyan-500/60', 'text-cyan-300');
      btn.classList.add('bg-slate-800', 'text-slate-300', 'border-slate-700');
    }
    if (btnText) btnText.textContent = 'Deep Zoom';

    if (osdViewer) {
      try {
        osdViewer.close();
      } catch (err) {
        console.debug("OSD close:", err);
      }
    }
  }
}

// ================= VOLLBILD LEINWAND & TASTATUR-HILFE =================

function toggleModalFullscreen(forceState = null) {
  const modal = document.getElementById('image-modal');
  const dialog = document.getElementById('image-modal-dialog');
  const enterIcon = document.getElementById('icon-fullscreen-enter');
  const exitIcon = document.getElementById('icon-fullscreen-exit');
  if (!modal || !dialog) return;

  const isFullscreen = forceState !== null ? forceState : !dialog.classList.contains('fullscreen-canvas-mode');

  if (isFullscreen) {
    modal.classList.add('fullscreen-active');
    dialog.classList.add('fullscreen-canvas-mode');
    if (enterIcon) enterIcon.classList.add('hidden');
    if (exitIcon) exitIcon.classList.remove('hidden');
    showToast('⛶ Vollbild-Leinwand aktiviert (Taste: F oder Esc)', false);
  } else {
    modal.classList.remove('fullscreen-active');
    dialog.classList.remove('fullscreen-canvas-mode');
    if (enterIcon) enterIcon.classList.remove('hidden');
    if (exitIcon) exitIcon.classList.add('hidden');
  }

  if (typeof isSplitSliderActive !== 'undefined' && isSplitSliderActive) {
    setSplitDividerPosition(splitSliderPercent);
  }
}

function openShortcutsModal() {
  const modal = document.getElementById('shortcuts-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeShortcutsModal() {
  const modal = document.getElementById('shortcuts-modal');
  if (modal) modal.classList.add('hidden');
}

function toggleShortcutsModal() {
  const modal = document.getElementById('shortcuts-modal');
  if (modal) {
    if (modal.classList.contains('hidden')) {
      openShortcutsModal();
    } else {
      closeShortcutsModal();
    }
  }
}

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
  const loadMoreContainer = document.getElementById('search-load-more-container');

  currentSearchQuery = `similar:${filePath}`;
  currentSearchFilter = 'all';
  currentSearchResults = [];
  currentRenderedResults = [];

  grid.innerHTML = '';
  empty.classList.add('hidden');
  spinner.classList.remove('hidden');
  resultsBar.classList.add('hidden');
  if (loadMoreContainer) loadMoreContainer.classList.add('hidden');

  const thesaurusBanner = document.getElementById('results-thesaurus-banner');
  if (thesaurusBanner) thesaurusBanner.classList.add('hidden');

  const stackToggle = document.getElementById('search-stack-variants');
  const stackVariants = stackToggle ? stackToggle.checked : true;

  try {
    const res = await fetch(`/search/similar?image_path=${encodeURIComponent(filePath)}&limit=24&stack_variants=${stackVariants}`);
    if (!res.ok) throw new Error(`Fehler bei der Ähnlichkeitssuche (${res.status})`);
    const data = await res.json();

    spinner.classList.add('hidden');
    resultsBar.classList.remove('hidden');
    currentSearchResults = data || [];
    currentRenderedResults = currentSearchResults;

    resultsCount.textContent = `${currentSearchResults.length} optisch ähnliche Bilder`;
    resultsQuery.textContent = `Referenz: "${filePath.split('/').pop()}"`;

    const addAllBtn = document.getElementById('add-all-results-to-lightbox-btn');
    if (addAllBtn) {
      if (currentSearchResults.length > 0) addAllBtn.classList.remove('hidden');
      else addAllBtn.classList.add('hidden');
    }

    if (currentSearchResults.length === 0) {
      empty.classList.remove('hidden');
      updateLoadMoreVisibility(0);
      return;
    }

    updateSearchFilterPills();
    updateLoadMoreVisibility(0);
    renderSearchResults(currentSearchResults, grid);
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

    currentSearchResults = data || [];
    currentRenderedResults = currentSearchResults;
    currentSearchFilter = 'all';
    currentSearchQuery = `crop:${filePath}`;

    const pctW = Math.round(cropBox.width * 100);
    const pctH = Math.round(cropBox.height * 100);
    const displayName = fileName || filePath.split('/').pop();

    resultsCount.textContent = `${currentSearchResults.length} optisch ähnliche Treffer`;
    resultsQuery.textContent = `Ausschnitt aus "${displayName}" (${pctW}% × ${pctH}%)`;

    const addAllBtn = document.getElementById('add-all-results-to-lightbox-btn');
    if (addAllBtn) {
      if (currentSearchResults.length > 0) addAllBtn.classList.remove('hidden');
      else addAllBtn.classList.add('hidden');
    }

    if (currentSearchResults.length === 0) {
      empty.classList.remove('hidden');
      updateLoadMoreVisibility(0);
      return;
    }

    updateSearchFilterPills();
    updateLoadMoreVisibility(0);
    renderSearchResults(currentSearchResults, grid);
    showToast(`Bildausschnitt-Suche erfolgreich (${currentSearchResults.length} Treffer)`);
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

let lastFolderScanResult = null;

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
  preview.innerHTML = `
    <div class="flex items-center gap-2 text-slate-400 font-mono py-1">
      <div class="w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin"></div>
      <span>Prüfe Verzeichnis und bestehende Datenbank-Indizes...</span>
    </div>
  `;

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
    lastFolderScanResult = data;

    let samplesHtml = '';
    if (data.sample_files && data.sample_files.length > 0) {
      samplesHtml = `
        <div class="mt-2.5 pt-2.5 border-t border-slate-800/80 text-[11px] text-slate-400">
          <span class="font-medium text-slate-300 block mb-1">Beispieldateien:</span>
          <div class="flex flex-wrap gap-1 font-mono">
            ${data.sample_files.map(f => `<span class="bg-slate-900/90 px-1.5 py-0.5 rounded border border-slate-800 text-slate-300">${escapeHtml(f)}</span>`).join('')}
            ${data.image_count > 10 ? `<span class="text-slate-500 self-center text-[10px]">+${data.image_count - 10} weitere</span>` : ''}
          </div>
        </div>
      `;
    }

    if (data.image_count === 0) {
      // Keine Bilder gefunden
      preview.innerHTML = `
        <div class="rounded-xl border border-slate-700 bg-slate-900/80 p-3.5 space-y-1.5">
          <div class="font-semibold text-slate-300 flex items-center gap-2">
            <span>⚠️ Keine Bilddateien gefunden</span>
          </div>
          <p class="text-xs text-slate-400">
            In diesem Verzeichnis wurden keine unterstützten Bilddateien (.jpg, .png, .tif, .webp) gefunden.
          </p>
        </div>
      `;
      if (status) status.textContent = '0 Bilddateien gefunden';
    } else if (data.is_fully_indexed) {
      // 100% bereits im Archiv vorhanden!
      preview.innerHTML = `
        <div class="rounded-xl border border-blue-500/50 bg-blue-950/40 p-4 space-y-3 shadow-lg animate-fadeIn">
          <div class="flex items-center justify-between">
            <span class="font-bold text-blue-300 flex items-center gap-2 text-sm">
              <svg class="w-4 h-4 text-blue-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <span>Ordner ist bereits vollständig importiert</span>
            </span>
            <span class="px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-mono text-xs font-bold border border-blue-500/30">
              ${data.already_indexed_count} / ${data.image_count} im Archiv
            </span>
          </div>
          <p class="text-xs text-blue-100/90 leading-relaxed">
            Alle <strong>${data.image_count} Bilder</strong> aus diesem Ordner befinden sich bereits in der Datenbank. Ein erneuter Import ist nicht notwendig und erzeugt keine Duplikate.
          </p>
          <div class="pt-2 border-t border-blue-900/60 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
            <span class="flex items-center gap-1.5">
              <span>${data.is_registered ? '📁 Als Archiv-Pfad registriert' : '📁 Pfad bereit'}</span>
              <span>&bull;</span>
              <span>${data.sidecar_count} .json-Sidecars</span>
            </span>
            <button type="button" onclick="forceReindexFolder()" class="text-amber-400 hover:text-amber-300 font-medium underline underline-offset-4 flex items-center gap-1 transition">
              <span>↻ Trotzdem neu indexieren (Erzwingen)</span>
            </button>
          </div>
          ${samplesHtml}
        </div>
      `;
      if (status) status.textContent = `Bereits vollständig vorhanden (${data.already_indexed_count} Bilder)`;
    } else if (data.is_partially_indexed) {
      // Teilweise vorhanden (Inkrementell)
      preview.innerHTML = `
        <div class="rounded-xl border border-amber-500/50 bg-amber-950/30 p-4 space-y-3 shadow-lg animate-fadeIn">
          <div class="flex items-center justify-between">
            <span class="font-bold text-amber-300 flex items-center gap-2 text-sm">
              <svg class="w-4 h-4 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
              </svg>
              <span>Teilweise vorhanden: Inkrementeller Import</span>
            </span>
            <span class="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono text-xs font-bold border border-amber-500/30">
              ${data.new_images_count} neue Bilder
            </span>
          </div>
          <p class="text-xs text-slate-200 leading-relaxed">
            Von insgesamt <strong>${data.image_count} Bildern</strong> sind <strong>${data.already_indexed_count} bereits im Archiv</strong> erfasst. Es werden nur die <strong>${data.new_images_count} neuen Bilder</strong> eingelesen.
          </p>
          <div class="pt-2 border-t border-slate-800 text-[11px] text-slate-400">
            ${data.sidecar_count} .json-Sidecars gefunden
          </div>
          ${samplesHtml}
        </div>
      `;
      if (status) status.textContent = `${data.new_images_count} neue Bilder (${data.already_indexed_count} bereits erfasst)`;
    } else {
      // Komplett neu
      preview.innerHTML = `
        <div class="rounded-xl border border-emerald-500/50 bg-emerald-950/30 p-4 space-y-3 shadow-lg animate-fadeIn">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-300 flex items-center gap-2 text-sm">
              <svg class="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <span>Neuer Bestand: Bereit zum Einlesen</span>
            </span>
            <span class="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono text-xs font-bold border border-emerald-500/30">
              ${data.image_count} Bilder
            </span>
          </div>
          <p class="text-xs text-slate-200 leading-relaxed">
            Noch keine dieser Aufnahmen ist im Archiv vorhanden. Alle <strong>${data.image_count} Bilder</strong> werden neu indexiert und analysiert.
          </p>
          <div class="pt-2 border-t border-slate-800 text-[11px] text-slate-400">
            ${data.sidecar_count} .json-Sidecars gefunden
          </div>
          ${samplesHtml}
        </div>
      `;
      if (status) status.textContent = `${data.image_count} Bilder bereit`;
    }
  } catch (err) {
    preview.innerHTML = `
      <div class="text-rose-400 flex items-center gap-1.5 p-3 rounded-xl bg-rose-950/30 border border-rose-800/40">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        <span>${escapeHtml(err.message)}</span>
      </div>
    `;
    if (status) status.textContent = 'Fehler beim Scannen';
  }
}

function forceReindexFolder() {
  const skipCheckbox = document.getElementById('folder-skip-existing');
  if (skipCheckbox) skipCheckbox.checked = false;
  showToast('Modus geändert: Neuindexierung wird erzwungen (Force Re-Scan).', false);
  startFolderIndexing(true);
}

let progressPollTimer = null;
let activeIndexingJobId = null;
let lastHandledFinishedJobId = null;
let isActivelyTrackingIndexing = false;
let indexingInitialCheckDone = false;

const DEFAULT_FOLDER_INDEX_BTN_HTML = `
  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
      d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z">
    </path>
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
      d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
  </svg>
  <span>Ordner jetzt indexieren</span>
`;

function resetFolderIndexButton() {
  const btn = document.getElementById('start-folder-index-btn');
  if (btn) {
    btn.disabled = false;
    btn.classList.remove('opacity-50');
    btn.innerHTML = DEFAULT_FOLDER_INDEX_BTN_HTML;
  }
}

function startProgressPolling() {
  if (!progressPollTimer) {
    progressPollTimer = setInterval(checkIndexingProgress, 800);
  }
}

function stopProgressPolling() {
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
}

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
    const runningBadge = document.getElementById('tab-import-running-indicator');
    const healthStatus = document.getElementById('health-status');

    // Erster Check bei Initialisierung (z. B. Page Load): Altes 'finished' merken, um keinen veralteten Toast zu feuern
    if (!indexingInitialCheckDone) {
      indexingInitialCheckDone = true;
      if (!data.is_running && data.finished && data.job_id) {
        lastHandledFinishedJobId = data.job_id;
      }
    }

    if (data.is_running) {
      isActivelyTrackingIndexing = true;
      if (data.job_id) {
        activeIndexingJobId = data.job_id;
      }

      if (runningBadge) runningBadge.classList.remove('hidden');
      if (liveBox) liveBox.classList.remove('hidden');
      if (preview) preview.classList.add('hidden');
      if (percentSpan) percentSpan.textContent = `${data.percent}%`;
      if (bar) bar.style.width = `${data.percent}%`;
      if (countsSpan) {
        countsSpan.textContent = `${data.processed_count} / ${data.total_found} Bilder (${data.new_indexed} neu, ${data.skipped} vorh.)`;
      }
      if (facesSpan) facesSpan.textContent = `${data.faces_detected} Gesichter`;
      if (curFileSpan) curFileSpan.textContent = data.current_file || 'Verarbeite...';

      if (btn) {
        btn.disabled = true;
        btn.classList.add('opacity-50');
        if (!btn.innerHTML.includes('animate-spin')) {
          btn.innerHTML = `
            <svg class="animate-spin w-4 h-4 text-slate-950" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Indexiere Ordner...</span>
          `;
        }
      }
      if (status) status.textContent = `Indexierung läuft (${data.percent}%)...`;
      if (healthStatus && !healthStatus.textContent.startsWith('Indexierung')) {
        healthStatus.textContent = `Indexierung (${data.percent}%)`;
      }

      startProgressPolling();
    } else {
      if (runningBadge) runningBadge.classList.add('hidden');

      // Prüfen, ob dieser Job gerade neu abgeschlossen wurde
      const isNewCompletion = data.finished && (
        isActivelyTrackingIndexing ||
        (data.job_id && data.job_id !== lastHandledFinishedJobId)
      );

      if (isNewCompletion) {
        isActivelyTrackingIndexing = false;
        if (data.job_id) {
          lastHandledFinishedJobId = data.job_id;
        }

        stopProgressPolling();
        resetFolderIndexButton();
        if (liveBox) liveBox.classList.add('hidden');
        if (healthStatus && healthStatus.textContent.startsWith('Indexierung')) {
          healthStatus.textContent = 'Qdrant bereit';
        }

        if (data.error) {
          if (status) status.textContent = 'Indexierung fehlgeschlagen';
          if (preview) {
            preview.classList.remove('hidden');
            preview.innerHTML = `
              <div class="rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 space-y-2">
                <div class="text-rose-400 font-semibold flex items-center gap-2">
                  <svg class="w-4 h-4 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  <span>Indexierung mit Fehler beendet</span>
                </div>
                <p class="text-xs text-rose-300 font-mono">${escapeHtml(data.error)}</p>
              </div>
            `;
          }
          showToast(`Indexierung fehlgeschlagen: ${data.error}`, true);
        } else if (data.already_fully_indexed || (data.total_found > 0 && data.new_indexed === 0 && data.skipped > 0)) {
          // Explizite Rückmeldung: Bereits vollständig vorhanden!
          if (status) status.textContent = 'Bereits vollständig vorhanden (0 neue Bilder)';
          if (preview) {
            preview.classList.remove('hidden');
            preview.innerHTML = `
              <div class="rounded-xl border border-blue-500/50 bg-blue-950/40 p-4 space-y-2.5 shadow-lg animate-fadeIn">
                <div class="text-blue-300 font-bold flex items-center gap-2 text-sm">
                  <svg class="w-4 h-4 text-blue-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                  <span>Bereits vollständig im Archiv vorhanden!</span>
                </div>
                <p class="text-xs text-blue-100/90 leading-relaxed">
                  Alle <strong>${data.skipped || data.total_found} Bilder</strong> in diesem Ordner waren bereits vollständig in der Bilddatenbank erfasst. Es wurden keine Duplikate angelegt.
                </p>
                <div class="text-[11px] text-slate-400 font-mono pt-1">
                  0 neu indexiert &bull; ${data.skipped || data.total_found} vorhandene Bilder übersprungen
                </div>
              </div>
            `;
          }
          showToast(`Ordner ist bereits vollständig vorhanden (${data.skipped || data.total_found} Bilder).`, false);
        } else if (data.new_indexed > 0 && data.skipped > 0) {
          if (status) status.textContent = `${data.new_indexed} neue Bilder hinzugefügt (${data.skipped} vorh.)`;
          const clusterMsgHtml = data.clustering_message ? `
            <div class="mt-2.5 pt-2 border-t border-slate-700/60 text-[11px] text-amber-300 flex items-start gap-1.5 leading-relaxed">
              <span class="shrink-0 text-amber-400">💡</span>
              <span>${escapeHtml(data.clustering_message)}</span>
            </div>
          ` : '';
          if (preview) {
            preview.classList.remove('hidden');
            preview.innerHTML = `
              <div class="rounded-xl border border-emerald-500/50 bg-emerald-950/30 p-4 space-y-2.5 shadow-lg animate-fadeIn">
                <div class="text-emerald-400 font-bold flex items-center gap-2 text-sm">
                  <svg class="w-4 h-4 fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                  <span>Inkrementeller Import erfolgreich abgeschlossen!</span>
                </div>
                <div class="text-[11px] text-slate-300 font-mono space-y-1">
                  <p>&bull; Neu hinzugefügt: <strong class="text-emerald-400">${data.new_indexed}</strong> Bilder</p>
                  <p>&bull; Bereits vorhanden: <strong class="text-slate-400">${data.skipped}</strong> Bilder (übersprungen)</p>
                  <p>&bull; Erkannte Gesichter: <strong class="text-amber-400">${data.faces_detected}</strong></p>
                </div>
                ${clusterMsgHtml}
              </div>
            `;
          }
          showToast(`Inkrementeller Import: ${data.new_indexed} neue Bilder hinzugefügt (${data.skipped} übersprungen).`);
        } else {
          if (status) status.textContent = 'Indexierung abgeschlossen';
          const clusterMsgHtml = data.clustering_message ? `
            <div class="mt-2.5 pt-2 border-t border-slate-700/60 text-[11px] text-amber-300 flex items-start gap-1.5 leading-relaxed">
              <span class="shrink-0 text-amber-400">💡</span>
              <span>${escapeHtml(data.clustering_message)}</span>
            </div>
          ` : '';
          if (preview) {
            preview.classList.remove('hidden');
            preview.innerHTML = `
              <div class="rounded-xl border border-emerald-500/50 bg-emerald-950/30 p-4 space-y-2.5 shadow-lg animate-fadeIn">
                <div class="text-emerald-400 font-bold flex items-center gap-2 text-sm">
                  <svg class="w-4 h-4 fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                  <span>Indexierung erfolgreich abgeschlossen!</span>
                </div>
                <div class="text-[11px] text-slate-300 font-mono space-y-1">
                  <p>&bull; Neu indexiert: <strong class="text-amber-400">${data.processed_count || data.new_indexed || 0}</strong> Bilder</p>
                  <p>&bull; Erkannte Gesichter: <strong class="text-amber-400">${data.faces_detected || 0}</strong></p>
                </div>
                ${clusterMsgHtml}
              </div>
            `;
          }
          showToast(`Indexierung erfolgreich: ${data.processed_count || data.new_indexed || 0} Bilder erfasst.`);
        }
        loadRegisteredFolders();
      } else {
        stopProgressPolling();
        resetFolderIndexButton();
      }
    }
  } catch (err) {
    // Stiller Fehler beim Polling
  }
}

async function startFolderIndexing(forceExplicit = false) {
  const input = document.getElementById('folder-path-input');
  const recursive = document.getElementById('folder-recursive')?.checked ?? true;
  let skipExisting = document.getElementById('folder-skip-existing')?.checked ?? true;
  if (forceExplicit) {
    skipExisting = false;
  }
  const btn = document.getElementById('start-folder-index-btn');
  const status = document.getElementById('folder-index-status');
  const preview = document.getElementById('folder-scan-preview');
  const liveBox = document.getElementById('folder-live-progress');
  const percentSpan = document.getElementById('flp-percentage');
  const bar = document.getElementById('flp-bar');
  const countsSpan = document.getElementById('flp-counts');
  const facesSpan = document.getElementById('flp-faces');
  const curFileSpan = document.getElementById('flp-current-file');

  const folderPath = input.value.trim();
  if (!folderPath) {
    showToast('Bitte geben Sie einen Verzeichnispfad an.', true);
    input.focus();
    return;
  }

  // Sanity check: Wenn Ordner bereits zu 100% indexiert ist und skipExisting aktiv ist
  if (!forceExplicit && skipExisting && lastFolderScanResult && lastFolderScanResult.folder_path === folderPath && lastFolderScanResult.is_fully_indexed) {
    const confirmReindex = confirm(
      `Alle ${lastFolderScanResult.image_count} Bilder in diesem Ordner befinden sich bereits in der Datenbank.\n\nMöchten Sie eine vollständige Neuindexierung (z. B. für geänderte Metadaten oder Gesichter) trotzdem erzwingen?`
    );
    if (!confirmReindex) {
      showToast('Import übersprungen: Ordner ist bereits vollständig vorhanden.', false);
      if (status) status.textContent = 'Bereits vollständig vorhanden';
      return;
    }
    skipExisting = false;
    const skipCheckbox = document.getElementById('folder-skip-existing');
    if (skipCheckbox) skipCheckbox.checked = false;
  }

  // UI sofort in den aktiven Indexierungsmodus versetzen
  btn.disabled = true;
  btn.classList.add('opacity-50');
  btn.innerHTML = `
    <svg class="animate-spin w-4 h-4 text-slate-950" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
    <span>Indexiere Ordner...</span>
  `;

  if (status) status.textContent = 'Indexierung startet...';
  if (liveBox) liveBox.classList.remove('hidden');
  if (preview) preview.classList.add('hidden');
  if (percentSpan) percentSpan.textContent = '0%';
  if (bar) bar.style.width = '0%';
  if (countsSpan) countsSpan.textContent = 'Vorbereitung...';
  if (facesSpan) facesSpan.textContent = '0 Gesichter';
  if (curFileSpan) curFileSpan.textContent = 'Scanne Ordner nach Bilddateien...';

  isActivelyTrackingIndexing = true;

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

    const resData = await res.json().catch(() => ({}));

    if (!res.ok) {
      // Falls bereits ein Import im Hintergrund läuft (HTTP 409):
      // Nicht abbrechen, sondern Live-Fortschrittsanzeige sofort aktivieren und verbinden!
      if (res.status === 409 || (resData.detail && resData.detail.includes('bereits eine Indexierung'))) {
        showToast('Ein Hintergrund-Import läuft bereits – Live-Fortschrittsanzeige aktiviert.', false);
        if (liveBox) liveBox.classList.remove('hidden');
        if (status) status.textContent = 'Hintergrund-Indexierung aktiv...';
        startProgressPolling();
        checkIndexingProgress();
        return;
      }
      throw new Error(resData.detail || `HTTP ${res.status}`);
    }

    if (resData.job_id) {
      activeIndexingJobId = resData.job_id;
    }

    showToast('Indexierung im Hintergrund gestartet.', false);
    loadRegisteredFolders();

    // Polling aktivieren und direkt prüfen
    startProgressPolling();
    checkIndexingProgress();
  } catch (err) {
    showToast(`Start fehlgeschlagen: ${err.message}`, true);
    if (status) status.textContent = 'Fehlgeschlagen';
    if (liveBox) liveBox.classList.add('hidden');
    stopProgressPolling();
    resetFolderIndexButton();
    isActivelyTrackingIndexing = false;
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

// Tastatur-Shortcuts
document.addEventListener('keydown', (e) => {
  // 1. Wenn ein Textfeld fokussiert ist, Shortcuts nicht auslösen
  const isTyping = ['TEXTAREA'].includes(document.activeElement?.tagName) || 
    (document.activeElement?.tagName === 'INPUT' && !['range', 'button', 'checkbox', 'radio'].includes(document.activeElement?.type)) || 
    document.activeElement?.isContentEditable;

  // ESC-Taste Behandlung
  if (e.key === 'Escape') {
    // 0. Kirchlicher Thesaurus Modal schließen
    const thModal = document.getElementById('thesaurus-modal');
    if (thModal && !thModal.classList.contains('hidden')) {
      closeThesaurusModal();
      return;
    }
    // Tastaturkürzel Modal schließen
    const scModal = document.getElementById('shortcuts-modal');
    if (scModal && !scModal.classList.contains('hidden')) {
      closeShortcutsModal();
      return;
    }
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
      const dialog = document.getElementById('image-modal-dialog');
      if (dialog && dialog.classList.contains('fullscreen-canvas-mode')) {
        toggleModalFullscreen(false);
        return;
      }
      closeImageModal();
      return;
    }
    // 2. Wenn kein Modal offen ist, aber die Cluster-Einzelansicht aktiv ist:
    if (activeCluster) {
      closeClusterDetail();
    }
    return;
  }

  // Globale Shortcuts (sofern nicht im Textfeld getippt wird)
  if (isTyping) return;

  // Tastaturkürzel-Hilfe (?)
  if (e.key === '?' || (e.shiftKey && e.key === '/')) {
    e.preventDefault();
    toggleShortcutsModal();
    return;
  }

  // Schnelle Freitext-Suche (Taste: /)
  if (e.key === '/') {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      e.preventDefault();
      switchTab('search');
      searchInput.focus();
      searchInput.select();
    }
    return;
  }

  // Shortcuts im Bild-Modal
  const imgModal = document.getElementById('image-modal');
  const isImgModalOpen = imgModal && !imgModal.classList.contains('hidden');

  if (isImgModalOpen) {
    // Strg+Z / Cmd+Z: Rückgängig, Strg+Y / Strg+Shift+Z: Wiederholen
    if (e.ctrlKey || e.metaKey) {
      if ((e.key === 'z' || e.key === 'Z') && !e.shiftKey) {
        e.preventDefault();
        undoImageEdit();
        return;
      }
      if (((e.key === 'z' || e.key === 'Z') && e.shiftKey) || e.key === 'y' || e.key === 'Y') {
        e.preventDefault();
        redoImageEdit();
        return;
      }
      if (e.altKey && (e.key === '0' || e.key === 'Backspace')) {
        e.preventDefault();
        resetAllImageAdjustments();
        return;
      }
    }

    // F: Vollbild-Leinwand ein/aus
    if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      toggleModalFullscreen();
      return;
    }

    // S: Vorher/Nachher Split-Slider
    if (e.key === 's' || e.key === 'S') {
      e.preventDefault();
      toggleSplitSlider();
      return;
    }

    // L: Lupe (250% Vergrößerung)
    if (e.key === 'l' || e.key === 'L') {
      e.preventDefault();
      toggleModalLupe();
      return;
    }

    // R: 90° Drehung
    if (e.key === 'r' || e.key === 'R') {
      e.preventDefault();
      if (typeof currentActiveRightTab !== 'undefined' && currentActiveRightTab === 'edit') {
        rotateEditTransformation(90);
      } else {
        rotateCurrentModalImage(90);
      }
      return;
    }

    // V oder U: Zweiblatt 3D-Karten-Flip (Recto / Verso)
    if (e.key === 'v' || e.key === 'V' || e.key === 'u' || e.key === 'U') {
      if (currentTwoSidedInfo && currentTwoSidedInfo.companion_exists) {
        e.preventDefault();
        toggleModalCardFlip();
        return;
      }
    }

    // I: Negativ invertieren
    if (e.key === 'i' || e.key === 'I') {
      e.preventDefault();
      toggleEditInvert();
      return;
    }

    // + / =: Zoom hinein
    if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      adjustModalZoom(0.25);
      return;
    }

    // - / _: Zoom heraus
    if (e.key === '-' || e.key === '_') {
      e.preventDefault();
      adjustModalZoom(-0.25);
      return;
    }

    // 0: Zoom zurücksetzen
    if (e.key === '0') {
      e.preventDefault();
      resetModalZoom();
      return;
    }

    // Pfeiltasten Navigation im Bild-Modal (Vorheriges / Nächstes Bild)
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      if (cropperInstance) return; // Nicht während der Rahmenwahl blättern

      // 1. Navigation innerhalb eines Personen-Clusters (falls aus Cluster geöffnet)
      if (currentModalTargetFaceContext && activeCluster && activeCluster.faces && activeCluster.faces.length > 1) {
        const curFaceIdx = activeCluster.faces.findIndex(f => f.face_id === currentModalTargetFaceContext.faceId);
        if (curFaceIdx !== -1) {
          e.preventDefault();
          const nextFaceIdx = e.key === 'ArrowRight'
            ? (curFaceIdx + 1) % activeCluster.faces.length
            : (curFaceIdx - 1 + activeCluster.faces.length) % activeCluster.faces.length;
          const nextFace = activeCluster.faces[nextFaceIdx];
          if (nextFace && nextFace.file_path) {
            const fn = nextFace.file_path.split('/').pop();
            openClusterFaceModal(nextFace.file_path, fn, nextFace.face_id, activeCluster.cluster_id, activeCluster.label);
            return;
          }
        }
      }

      // 2. Navigation durch allgemeine Suchergebnisse
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

function toggleLightboxCard(event, itemOrPathOrIdx) {
  event.stopPropagation();
  let item = null;
  if (typeof itemOrPathOrIdx === 'object' && itemOrPathOrIdx !== null) {
    item = itemOrPathOrIdx;
  } else if (typeof itemOrPathOrIdx === 'string') {
    item = (currentRenderedResults || []).find(i => i.file_path === itemOrPathOrIdx) ||
           (currentSearchResults || []).find(i => i.file_path === itemOrPathOrIdx);
  } else if (typeof itemOrPathOrIdx === 'number') {
    item = (currentRenderedResults && currentRenderedResults[itemOrPathOrIdx]) ||
           (currentSearchResults && currentSearchResults[itemOrPathOrIdx]);
  }
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

    // Live-Histogramm berechnen
    setTimeout(scheduleHistogramRender, 50);
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

let editHistory = [];
let editRedoHistory = [];
let preSliderEditState = null;
let sliderCommitTimeout = null;
const MAX_EDIT_HISTORY = 40;

function cloneEditSettings(settings) {
  if (!settings) return null;
  return {
    brightness: Number(settings.brightness || 0),
    contrast: Number(settings.contrast || 0),
    gamma: Number(settings.gamma !== undefined ? settings.gamma : 1.0),
    sharpness: Number(settings.sharpness || 0),
    rotation: Number(settings.rotation || 0),
    fine_rotation: Number(settings.fine_rotation || 0.0),
    flip_h: Boolean(settings.flip_h),
    saturation: Number(settings.saturation !== undefined ? settings.saturation : 100),
    invert: Boolean(settings.invert),
    crop: settings.crop ? { ...settings.crop } : null
  };
}

function areEditSettingsEqual(a, b) {
  if (!a || !b) return a === b;
  if (a.brightness !== b.brightness) return false;
  if (a.contrast !== b.contrast) return false;
  if (Math.abs(a.gamma - b.gamma) > 0.001) return false;
  if (a.sharpness !== b.sharpness) return false;
  if (a.rotation !== b.rotation) return false;
  if (Math.abs(a.fine_rotation - b.fine_rotation) > 0.01) return false;
  if (a.flip_h !== b.flip_h) return false;
  if (a.saturation !== b.saturation) return false;
  if (a.invert !== b.invert) return false;

  if (!a.crop && !b.crop) return true;
  if (!a.crop || !b.crop) return false;
  return a.crop.x === b.crop.x &&
         a.crop.y === b.crop.y &&
         a.crop.width === b.crop.width &&
         a.crop.height === b.crop.height;
}

function isEditStateDefault(settings = currentEditSettings) {
  if (!settings) return true;
  return Number(settings.brightness || 0) === 0 &&
         Number(settings.contrast || 0) === 0 &&
         Math.abs(Number(settings.gamma !== undefined ? settings.gamma : 1.0) - 1.0) < 0.01 &&
         Number(settings.sharpness || 0) === 0 &&
         Number(settings.rotation || 0) === 0 &&
         Math.abs(Number(settings.fine_rotation || 0.0)) < 0.01 &&
         !settings.flip_h &&
         Number(settings.saturation !== undefined ? settings.saturation : 100) === 100 &&
         !settings.invert &&
         !settings.crop;
}

function resetImageEditHistory() {
  editHistory = [];
  editRedoHistory = [];
  preSliderEditState = null;
  clearTimeout(sliderCommitTimeout);
  updateUndoRedoButtonsState();
}

function recordEditStateForUndo(previousState = null) {
  const stateToPush = cloneEditSettings(previousState || currentEditSettings);
  if (!stateToPush) return;
  if (editHistory.length > 0 && areEditSettingsEqual(editHistory[editHistory.length - 1], stateToPush)) {
    return;
  }
  editHistory.push(stateToPush);
  if (editHistory.length > MAX_EDIT_HISTORY) {
    editHistory.shift();
  }
  editRedoHistory = [];
  updateUndoRedoButtonsState();
}

function updateUndoRedoButtonsState() {
  const undoBtn = document.getElementById('btn-edit-undo');
  const redoBtn = document.getElementById('btn-edit-redo');
  const resetBtn = document.getElementById('btn-edit-reset-all');
  const resetBottomBtn = document.getElementById('btn-edit-reset-bottom');

  const canUndo = editHistory.length > 0;
  const canRedo = editRedoHistory.length > 0;
  const isDefault = isEditStateDefault();

  if (undoBtn) {
    undoBtn.disabled = !canUndo;
    if (canUndo) {
      undoBtn.classList.remove('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
      undoBtn.classList.add('hover:text-amber-300', 'cursor-pointer');
      undoBtn.title = `Letzte Bearbeitung rückgängig machen (${editHistory.length} Schritt${editHistory.length > 1 ? 'e' : ''} im Verlauf, Strg+Z)`;
    } else {
      undoBtn.classList.add('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
      undoBtn.classList.remove('hover:text-amber-300', 'cursor-pointer');
      undoBtn.title = 'Keine weiteren Schritte zum Rückgängigmachen (Strg+Z)';
    }
  }

  if (redoBtn) {
    redoBtn.disabled = !canRedo;
    if (canRedo) {
      redoBtn.classList.remove('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
      redoBtn.classList.add('hover:text-amber-300', 'cursor-pointer');
      redoBtn.title = `Rückgängig gemachte Bearbeitung wiederherstellen (${editRedoHistory.length} Schritt${editRedoHistory.length > 1 ? 'e' : ''}, Strg+Y)`;
    } else {
      redoBtn.classList.add('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
      redoBtn.classList.remove('hover:text-amber-300', 'cursor-pointer');
      redoBtn.title = 'Keine Schritte zum Wiederherstellen (Strg+Y)';
    }
  }

  if (resetBtn) {
    if (!isDefault) {
      resetBtn.classList.remove('opacity-50');
      resetBtn.title = 'Alle Regler und Transformationen auf 0 zurücksetzen (kann mit Rückgängig wiederhergestellt werden)';
    } else {
      resetBtn.classList.add('opacity-50');
      resetBtn.title = 'Bereits auf 0 (Urzustand)';
    }
  }

  if (resetBottomBtn) {
    if (!isDefault) {
      resetBottomBtn.classList.remove('opacity-50');
    } else {
      resetBottomBtn.classList.add('opacity-50');
    }
  }
}

function undoImageEdit() {
  if (preSliderEditState) {
    preSliderEditState = null;
  }
  if (editHistory.length === 0) {
    showToast('Keine weiteren Änderungen zum Rückgängigmachen.', false);
    return;
  }

  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }

  editRedoHistory.push(cloneEditSettings(currentEditSettings));
  const prevState = editHistory.pop();
  currentEditSettings = cloneEditSettings(prevState);

  loadModalEditSettings(currentEditSettings);
  updateUndoRedoButtonsState();
  showToast('↶ Änderung rückgängig gemacht.', false);
}

function redoImageEdit() {
  if (preSliderEditState) {
    preSliderEditState = null;
  }
  if (editRedoHistory.length === 0) {
    showToast('Keine weiteren Schritte zum Wiederherstellen.', false);
    return;
  }

  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }

  editHistory.push(cloneEditSettings(currentEditSettings));
  const nextState = editRedoHistory.pop();
  currentEditSettings = cloneEditSettings(nextState);

  loadModalEditSettings(currentEditSettings);
  updateUndoRedoButtonsState();
  showToast('↷ Bearbeitung wiederhergestellt.', false);
}

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
    const img = document.getElementById('modal-img');
    if (img && img.dataset.uncroppedSrc) {
      img.src = img.dataset.uncroppedSrc;
      delete img.dataset.uncroppedSrc;
    }
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
  updateUndoRedoButtonsState();
}

function onEditSliderChange() {
  if (!preSliderEditState) {
    preSliderEditState = cloneEditSettings(currentEditSettings);
  }

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

  clearTimeout(sliderCommitTimeout);
  sliderCommitTimeout = setTimeout(() => {
    onEditSliderCommit();
  }, 600);
}

function onEditSliderCommit() {
  clearTimeout(sliderCommitTimeout);
  if (preSliderEditState) {
    if (!areEditSettingsEqual(preSliderEditState, currentEditSettings)) {
      recordEditStateForUndo(preSliderEditState);
    }
    preSliderEditState = null;
  }
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

  // Split-Screen Originalbild-Transformation synchronisieren
  if (isSplitSliderActive) {
    const origImg = document.getElementById('modal-split-original-img');
    if (origImg) {
      origImg.style.transform = img.style.transform;
      origImg.style.transformOrigin = img.style.transformOrigin;
    }
  }

  // Live-Histogramm berechnen & zeichnen
  scheduleHistogramRender();
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
  if (presetName === 'neutral') {
    resetAllImageAdjustments();
    return;
  }
  onEditSliderCommit();
  recordEditStateForUndo();
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
  }
}

function rotateEditTransformation(delta = 90) {
  onEditSliderCommit();
  recordEditStateForUndo();
  currentEditSettings.rotation = (currentEditSettings.rotation + delta) % 360;
  const rotBtnLabel = document.getElementById('label-edit-rotation-btn');
  if (rotBtnLabel) rotBtnLabel.textContent = `${currentEditSettings.rotation}°`;
  applyLiveImageTransformations();
  updateUndoRedoButtonsState();
}

function toggleEditFlipH() {
  onEditSliderCommit();
  recordEditStateForUndo();
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
  updateUndoRedoButtonsState();
}

function toggleEditInvert() {
  onEditSliderCommit();
  recordEditStateForUndo();
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
  updateUndoRedoButtonsState();
}

function resetAllImageAdjustments(silent = false) {
  if (cropperInstance) {
    cropperInstance.destroy();
    cropperInstance = null;
  }
  const img = document.getElementById('modal-img');
  if (img && img.dataset.uncroppedSrc) {
    img.src = img.dataset.uncroppedSrc;
    delete img.dataset.uncroppedSrc;
  }

  if (!silent) {
    if (isEditStateDefault()) {
      showToast('Alle Bildparameter stehen bereits auf Null.', false);
      return;
    }
    if (preSliderEditState) {
      recordEditStateForUndo(preSliderEditState);
      preSliderEditState = null;
    } else {
      recordEditStateForUndo();
    }
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
  if (isSplitSliderActive && img) {
    const origImg = document.getElementById('modal-split-original-img');
    if (origImg) origImg.src = img.src;
  }
  if (!silent) {
    showToast('↺ Alle Bildparameter auf Null zurückgesetzt.', false);
  }
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
    onEditSliderCommit();
    recordEditStateForUndo();
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
    updateUndoRedoButtonsState();
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
  onEditSliderCommit();
  recordEditStateForUndo();
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
  updateUndoRedoButtonsState();
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


// ================= CLUSTER-PERSONEN KONTROLLE & FOKUSSIERUNG =================

function focusTargetFaceInModal() {
  const img = document.getElementById('modal-img');
  if (!targetFaceBoxCoords || !img) return;

  const centerX = targetFaceBoxCoords.left + targetFaceBoxCoords.width / 2;
  const centerY = targetFaceBoxCoords.top + targetFaceBoxCoords.height / 2;

  modalZoomScale = 2.2;
  const w = img.offsetWidth || 800;
  const h = img.offsetHeight || 600;
  modalPanX = ((50 - centerX) / 100) * w * modalZoomScale;
  modalPanY = ((50 - centerY) / 100) * h * modalZoomScale;

  applyModalZoomPan();
  showToast(`🎯 Auf ${targetFaceBoxCoords.name || 'Person'} fokussiert (220% Lupe)`, false);
}

function focusFaceByIndex(idx) {
  const box = document.getElementById(`modal-face-box-${idx}`);
  const img = document.getElementById('modal-img');
  if (!box || !img) return;

  const left = parseFloat(box.style.left);
  const top = parseFloat(box.style.top);
  const width = parseFloat(box.style.width);
  const height = parseFloat(box.style.height);

  const centerX = left + width / 2;
  const centerY = top + height / 2;

  modalZoomScale = 2.2;
  const w = img.offsetWidth || 800;
  const h = img.offsetHeight || 600;
  modalPanX = ((50 - centerX) / 100) * w * modalZoomScale;
  modalPanY = ((50 - centerY) / 100) * h * modalZoomScale;

  applyModalZoomPan();

  // Temporäres aktives Pulsieren
  box.classList.add('active');
  setTimeout(() => {
    if (!box.classList.contains('highlight-target')) {
      box.classList.remove('active');
    }
  }, 2200);
}

async function removeTargetFaceFromClusterInModal() {
  if (!currentModalTargetFaceContext || !currentModalTargetFaceContext.faceId) {
    showToast('Keine Gesichts-ID für diese Person gefunden.', true);
    return;
  }

  const faceId = currentModalTargetFaceContext.faceId;
  const pName = currentModalTargetFaceContext.personName || 'diese Person';

  if (!confirm(`Möchten Sie dieses Gesicht wirklich aus dem Personen-Cluster „${pName}“ entfernen ("Nicht diese Person")?`)) {
    return;
  }

  try {
    const res = await fetch(`/faces/${encodeURIComponent(faceId)}/remove-from-cluster`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(`Fehler (${res.status})`);

    // Aktualisiere das aktive Cluster im Speicher
    if (activeCluster) {
      activeCluster.faces = (activeCluster.faces || []).filter(f => f.face_id !== faceId);
      activeCluster.face_count = activeCluster.faces.length;
      const statsElem = document.getElementById('cd-stats');
      if (statsElem) statsElem.textContent = `${activeCluster.face_count} Vorkommen in historischen Scans (Cluster ID: ${activeCluster.cluster_id})`;

      const target = allLoadedClusters.find(c => c.cluster_id === activeCluster.cluster_id);
      if (target) {
        target.faces = activeCluster.faces;
        target.face_count = activeCluster.face_count;
      }
      updateClusterCounts();
    }

    closeImageModal();
    showToast(`✓ Gesicht erfolgreich aus Cluster „${pName}“ entfernt.`, false);

    // Entferne die Karte in der Cluster-Galerie falls offen
    const cards = document.querySelectorAll('#cluster-images-grid .bg-slate-900');
    cards.forEach(card => {
      const btn = card.querySelector(`button[onclick*="${faceId}"]`);
      if (btn) {
        card.style.transition = 'all 0.3s ease';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.92)';
        setTimeout(() => card.remove(), 300);
      }
    });

  } catch (err) {
    showToast(`Fehler beim Entfernen: ${err.message}`, true);
  }
}

// ================= ARCHIV-SIGNATUR & ZITIERVORSCHLAG =================

function copyArchivalSignature(signature) {
  if (!signature) return;
  navigator.clipboard.writeText(signature).then(() => {
    showToast(`✓ Signatur „${signature}“ in Zwischenablage kopiert.`, false);
  }).catch(() => {
    prompt('Archivsignatur kopieren:', signature);
  });
}

function copyArchivalCitation() {
  if (!currentModalImageDetails) return;
  const d = currentModalImageDetails;
  const parts = [];
  if (d.signature) {
    parts.push(`Signatur: ${d.signature}`);
  }
  if (d.title) {
    parts.push(`„${d.title}“`);
  } else if (d.fileName) {
    parts.push(`Datei: ${d.fileName}`);
  }
  if (d.date) {
    parts.push(`Datierung: ${d.date}`);
  }
  if (d.creator) {
    parts.push(`Urheber/Fotograf: ${d.creator}`);
  }
  parts.push('Quelle: Bilddatenbank & Archivbestand');

  const citationText = parts.join('; ');
  navigator.clipboard.writeText(citationText).then(() => {
    showToast('✓ Zitiervorschlag in Zwischenablage kopiert!', false);
  }).catch(() => {
    prompt('Zitiervorschlag kopieren:', citationText);
  });
}

// ================= MODAL ZOOM, PAN & LUPE =================

let modalZoomScale = 1.0;
let modalPanX = 0;
let modalPanY = 0;
let isModalPanning = false;
let modalPanStartX = 0;
let modalPanStartY = 0;

function applyModalZoomPan() {
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const badge = document.getElementById('modal-zoom-level-badge');
  const lupeBtn = document.getElementById('btn-toggle-lupe');
  if (!wrapper) return;

  if (modalZoomScale <= 1.0) {
    modalZoomScale = 1.0;
    modalPanX = 0;
    modalPanY = 0;
    wrapper.style.transform = '';
    wrapper.classList.remove('can-pan', 'is-panning');
    if (lupeBtn) {
      lupeBtn.classList.remove('bg-amber-500/20', 'text-amber-300', 'border-amber-500/40');
    }
  } else {
    wrapper.style.transform = `translate(${modalPanX}px, ${modalPanY}px) scale(${modalZoomScale})`;
    wrapper.classList.add('can-pan');
    if (lupeBtn && modalZoomScale >= 2.0) {
      lupeBtn.classList.add('bg-amber-500/20', 'text-amber-300', 'border-amber-500/40');
    } else if (lupeBtn) {
      lupeBtn.classList.remove('bg-amber-500/20', 'text-amber-300', 'border-amber-500/40');
    }
  }

  if (badge) {
    badge.textContent = `${Math.round(modalZoomScale * 100)}%`;
  }
}

function adjustModalZoom(delta) {
  if (cropperInstance) return; // Nicht während Zuschnitt zoomen
  modalZoomScale = Math.min(5.0, Math.max(1.0, Math.round((modalZoomScale + delta) * 100) / 100));
  if (modalZoomScale === 1.0) {
    modalPanX = 0;
    modalPanY = 0;
  }
  applyModalZoomPan();
}

function resetModalZoom() {
  modalZoomScale = 1.0;
  modalPanX = 0;
  modalPanY = 0;
  applyModalZoomPan();
}

function toggleModalLupe() {
  if (modalZoomScale > 1.0) {
    resetModalZoom();
  } else {
    modalZoomScale = 2.5; // 250% Archival Lupe
    applyModalZoomPan();
  }
}

function initModalZoomAndPan() {
  const stage = document.querySelector('.modal-viewport-stage');
  const wrapper = document.getElementById('modal-bbox-wrapper');
  if (!stage || !wrapper) return;

  // Stufenloser Mausrad-Zoom
  stage.addEventListener('wheel', (e) => {
    const modal = document.getElementById('image-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    if (cropperInstance) return; // Nicht während des Zuschnitts

    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.25 : -0.25;
    adjustModalZoom(delta);
  }, { passive: false });

  // Drag-to-Pan bei Zoom > 100%
  wrapper.addEventListener('mousedown', (e) => {
    if (modalZoomScale <= 1.0) return;
    if (cropperInstance) return;
    if (e.target.closest('#modal-split-divider') || e.target.closest('.face-bbox-tag') || e.target.closest('button')) return;

    isModalPanning = true;
    modalPanStartX = e.clientX - modalPanX;
    modalPanStartY = e.clientY - modalPanY;
    wrapper.classList.add('is-panning');
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!isModalPanning) return;
    modalPanX = e.clientX - modalPanStartX;
    modalPanY = e.clientY - modalPanStartY;
    applyModalZoomPan();
  });

  window.addEventListener('mouseup', () => {
    if (isModalPanning) {
      isModalPanning = false;
      const w = document.getElementById('modal-bbox-wrapper');
      if (w) w.classList.remove('is-panning');
    }
  });
}

// ================= INTERAKTIVER VORHER/NACHHER SPLIT-SLIDER =================

let isSplitSliderActive = false;
let splitSliderPercent = 50;
let isDraggingSplitDivider = false;

function toggleSplitSlider(forceState = null) {
  const container = document.getElementById('modal-split-container');
  const btn = document.getElementById('btn-toggle-split');
  const origImg = document.getElementById('modal-split-original-img');
  const baseImg = document.getElementById('modal-img');
  if (!container || !btn || !baseImg) return;

  isSplitSliderActive = forceState !== null ? forceState : !isSplitSliderActive;

  if (isSplitSliderActive) {
    origImg.src = baseImg.dataset.uncroppedSrc || baseImg.src;
    origImg.style.transform = baseImg.style.transform;
    origImg.style.transformOrigin = baseImg.style.transformOrigin;

    container.classList.remove('hidden');
    btn.classList.add('bg-amber-500', 'text-slate-950', 'font-bold');
    btn.classList.remove('bg-slate-800', 'text-slate-300');
    setSplitDividerPosition(splitSliderPercent);
  } else {
    container.classList.add('hidden');
    btn.classList.remove('bg-amber-500', 'text-slate-950', 'font-bold');
    btn.classList.add('bg-slate-800', 'text-slate-300');
    isDraggingSplitDivider = false;
  }
}

function setSplitDividerPosition(percent) {
  splitSliderPercent = Math.max(0, Math.min(100, percent));
  const clipWrapper = document.getElementById('modal-split-clip-wrapper');
  const divider = document.getElementById('modal-split-divider');

  if (clipWrapper) {
    clipWrapper.style.clipPath = `inset(0 calc(100% - ${splitSliderPercent}%) 0 0)`;
  }
  if (divider) {
    divider.style.left = `${splitSliderPercent}%`;
  }
}

function initSplitSliderDrag() {
  const container = document.getElementById('modal-split-container');
  const divider = document.getElementById('modal-split-divider');
  if (!container || !divider) return;

  function onPointerDown(e) {
    if (!isSplitSliderActive) return;
    isDraggingSplitDivider = true;
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!isDraggingSplitDivider || !isSplitSliderActive) return;
    const rect = container.getBoundingClientRect();
    if (rect.width <= 0) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const x = clientX - rect.left;
    const pct = (x / rect.width) * 100;
    setSplitDividerPosition(pct);
  }

  function onPointerUp() {
    isDraggingSplitDivider = false;
  }

  divider.addEventListener('mousedown', onPointerDown);
  divider.addEventListener('touchstart', onPointerDown, { passive: false });

  window.addEventListener('mousemove', onPointerMove);
  window.addEventListener('touchmove', onPointerMove, { passive: true });

  window.addEventListener('mouseup', onPointerUp);
  window.addEventListener('touchend', onPointerUp);
}

// ================= LIVE TONWERT-HISTOGRAMM =================

let histogramMode = 'lum'; // 'lum' oder 'rgb'
let histCanvasOffscreen = null;
let histCtxOffscreen = null;
let histRenderRaf = null;

function setHistogramMode(mode) {
  histogramMode = mode;
  const lumBtn = document.getElementById('hist-mode-lum');
  const rgbBtn = document.getElementById('hist-mode-rgb');
  if (lumBtn && rgbBtn) {
    if (mode === 'lum') {
      lumBtn.className = 'px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold transition';
      rgbBtn.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 transition';
    } else {
      rgbBtn.className = 'px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold transition';
      lumBtn.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 transition';
    }
  }
  scheduleHistogramRender();
}

function scheduleHistogramRender() {
  if (histRenderRaf) cancelAnimationFrame(histRenderRaf);
  histRenderRaf = requestAnimationFrame(renderLiveHistogram);
}

function renderLiveHistogram() {
  const canvas = document.getElementById('edit-histogram-canvas');
  const baseImg = document.getElementById('modal-img');
  const editTab = document.getElementById('modal-tab-content-edit');
  if (!canvas || !baseImg || !baseImg.complete || !baseImg.naturalWidth) return;
  if (!editTab || editTab.classList.contains('hidden')) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  if (!histCanvasOffscreen) {
    histCanvasOffscreen = document.createElement('canvas');
    histCanvasOffscreen.width = 120;
    histCanvasOffscreen.height = 120;
    histCtxOffscreen = histCanvasOffscreen.getContext('2d', { willReadFrequently: true });
  }

  try {
    histCtxOffscreen.clearRect(0, 0, 120, 120);
    histCtxOffscreen.drawImage(baseImg, 0, 0, 120, 120);
    const imgData = histCtxOffscreen.getImageData(0, 0, 120, 120);
    const data = imgData.data;

    const rBins = new Uint32Array(256);
    const gBins = new Uint32Array(256);
    const bBins = new Uint32Array(256);
    const lumBins = new Uint32Array(256);

    const b = currentEditSettings.brightness || 0;
    const c = currentEditSettings.contrast || 0;
    const gamma = Math.max(0.1, currentEditSettings.gamma || 1.0);
    const inv = currentEditSettings.invert;
    const sat = (currentEditSettings.saturation ?? 100) / 100;

    const contrastFactor = (259 * (c + 255)) / (255 * (259 - c));
    const invGamma = 1.0 / gamma;
    const totalPixels = data.length / 4;

    for (let i = 0; i < data.length; i += 4) {
      let r = data[i];
      let g = data[i + 1];
      let bl = data[i + 2];

      if (b !== 0) {
        const bOffset = (b / 100) * 255;
        r += bOffset;
        g += bOffset;
        bl += bOffset;
      }

      if (c !== 0) {
        r = contrastFactor * (r - 128) + 128;
        g = contrastFactor * (g - 128) + 128;
        bl = contrastFactor * (bl - 128) + 128;
      }

      if (sat !== 1.0) {
        const gray = 0.299 * r + 0.587 * g + 0.114 * bl;
        r = gray + (r - gray) * sat;
        g = gray + (g - gray) * sat;
        bl = gray + (bl - gray) * sat;
      }

      if (inv) {
        r = 255 - r;
        g = 255 - g;
        bl = 255 - bl;
      }

      if (Math.abs(gamma - 1.0) > 0.01) {
        r = Math.min(255, Math.max(0, r));
        g = Math.min(255, Math.max(0, g));
        bl = Math.min(255, Math.max(0, bl));
        r = 255 * Math.pow(r / 255, invGamma);
        g = 255 * Math.pow(g / 255, invGamma);
        bl = 255 * Math.pow(bl / 255, invGamma);
      }

      const rClamped = Math.min(255, Math.max(0, Math.round(r)));
      const gClamped = Math.min(255, Math.max(0, Math.round(g)));
      const bClamped = Math.min(255, Math.max(0, Math.round(bl)));
      const lum = Math.min(255, Math.max(0, Math.round(0.299 * rClamped + 0.587 * gClamped + 0.114 * bClamped)));

      rBins[rClamped]++;
      gBins[gClamped]++;
      bBins[bClamped]++;
      lumBins[lum]++;
    }

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    let maxVal = 1;
    if (histogramMode === 'lum') {
      for (let i = 1; i < 255; i++) {
        if (lumBins[i] > maxVal) maxVal = lumBins[i];
      }
    } else {
      for (let i = 1; i < 255; i++) {
        if (rBins[i] > maxVal) maxVal = rBins[i];
        if (gBins[i] > maxVal) maxVal = gBins[i];
        if (bBins[i] > maxVal) maxVal = bBins[i];
      }
    }

    if (histogramMode === 'lum') {
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, 'rgba(245, 158, 11, 0.6)');
      grad.addColorStop(1, 'rgba(245, 158, 11, 0.05)');

      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let x = 0; x < 256; x++) {
        const val = Math.min(maxVal * 1.5, lumBins[x]);
        const y = h - (val / (maxVal * 1.1)) * (h - 4);
        ctx.lineTo(x, Math.max(2, y));
      }
      ctx.lineTo(255, h);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.beginPath();
      for (let x = 0; x < 256; x++) {
        const val = Math.min(maxVal * 1.5, lumBins[x]);
        const y = h - (val / (maxVal * 1.1)) * (h - 4);
        if (x === 0) ctx.moveTo(x, Math.max(2, y));
        else ctx.lineTo(x, Math.max(2, y));
      }
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    } else {
      const channels = [
        { bins: rBins, stroke: '#ef4444' },
        { bins: gBins, stroke: '#22c55e' },
        { bins: bBins, stroke: '#38bdf8' }
      ];

      channels.forEach(ch => {
        ctx.beginPath();
        for (let x = 0; x < 256; x++) {
          const val = Math.min(maxVal * 1.5, ch.bins[x]);
          const y = h - (val / (maxVal * 1.1)) * (h - 4);
          if (x === 0) ctx.moveTo(x, Math.max(2, y));
          else ctx.lineTo(x, Math.max(2, y));
        }
        ctx.strokeStyle = ch.stroke;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      });
    }

    const shadowDot = document.getElementById('hist-shadow-dot');
    const shadowLabel = document.getElementById('hist-shadows-indicator');
    const highlightDot = document.getElementById('hist-highlight-dot');
    const highlightLabel = document.getElementById('hist-highlights-indicator');

    const shadowClipping = (lumBins[0] / totalPixels) > 0.05;
    const highlightClipping = (lumBins[255] / totalPixels) > 0.05;

    if (shadowDot && shadowLabel) {
      if (shadowClipping) {
        shadowDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse inline-block';
        shadowLabel.className = 'flex items-center gap-1 transition text-rose-400 font-semibold';
      } else {
        shadowDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-600 inline-block';
        shadowLabel.className = 'flex items-center gap-1 transition text-slate-500';
      }
    }

    if (highlightDot && highlightLabel) {
      if (highlightClipping) {
        highlightDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse inline-block';
        highlightLabel.className = 'flex items-center gap-1 transition text-amber-400 font-semibold';
      } else {
        highlightDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-600 inline-block';
        highlightLabel.className = 'flex items-center gap-1 transition text-slate-500';
      }
    }
  } catch (err) {
    // Graceful error ignore
  }
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
        <div class="flex items-center justify-between mb-1">
          <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">Archivsignatur</span>
          <button type="button" onclick="copyArchivalSignature('${escapeHtml(meta.signature)}')" class="text-[10px] text-amber-400 hover:text-amber-300 transition flex items-center gap-1 font-medium" title="Archivsignatur in Zwischenablage kopieren">
            <span>📋</span> <span>Signatur kopieren</span>
          </button>
        </div>
        <span class="text-slate-200 font-mono text-xs bg-slate-950/80 px-2 py-1 rounded border border-slate-700/80 inline-block font-semibold select-all">${escapeHtml(meta.signature)}</span>
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

  // Wissenschaftlicher Zitiervorschlag Button
  metaHtml += `
    <div class="pt-2 border-t border-slate-800/80">
      <button type="button" onclick="copyArchivalCitation()" class="w-full py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-amber-400 border border-slate-700 text-[11px] font-medium transition flex items-center justify-center gap-1.5 shadow-sm" title="Zitierfähige Quellenangabe mit Signatur, Titel, Datum und Urheber kopieren">
        <span>📝</span> <span>Zitiervorschlag kopieren</span>
      </button>
    </div>`;

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

// =========================================================================
// PERSONEN-NETZWERKE & CO-OCCURRENCE ANALYSE
// =========================================================================

let networkInstance = null;
let currentNetworkData = null;
let networkSelectedNode = null;
let networkPhysicsEnabled = true;
let activeSharedFilter = null; // { clusterA, clusterB, nameB, originalFaces }

async function loadClusterCoOccurrences(clusterId) {
  const bar = document.getElementById('cluster-network-bar');
  const statusElem = document.getElementById('cluster-co-occurrences-status');
  const listElem = document.getElementById('cluster-co-occurrences-list');
  if (!bar || !listElem) return;

  listElem.innerHTML = '<span class="text-xs text-slate-500 font-mono">Ermittle Begleitpersonen...</span>';
  if (statusElem) statusElem.textContent = '';

  try {
    const res = await fetch(`/network/person/${encodeURIComponent(clusterId)}/co-occurrences?limit=15`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const companions = await res.json();

    if (!companions || companions.length === 0) {
      listElem.innerHTML = '<span class="text-xs text-slate-500 italic">Keine gemeinsamen Fotos mit anderen erfassten Personen gefunden.</span>';
      if (statusElem) statusElem.textContent = '(0 Begleiter)';
      return;
    }

    if (statusElem) statusElem.textContent = `(${companions.length} Begleitperson${companions.length === 1 ? '' : 'en'})`;
    listElem.innerHTML = '';

    companions.forEach(co => {
      const chip = document.createElement('div');
      chip.className = 'group flex items-center gap-2 bg-slate-950/80 hover:bg-slate-800 border border-slate-700/80 hover:border-cyan-500/50 rounded-xl px-2.5 py-1.5 transition-all shadow-sm shrink-0 select-none';

      // Thumbnail
      const thumbUrl = co.thumbnail_url || `/faces/preview/${encodeURIComponent(co.cluster_id)}`;
      const avatarImg = document.createElement('img');
      avatarImg.src = thumbUrl;
      avatarImg.alt = co.name;
      avatarImg.className = 'w-7 h-7 rounded-full object-cover border border-cyan-500/40 bg-slate-900';
      avatarImg.onerror = () => {
        avatarImg.outerHTML = '<div class="w-7 h-7 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center text-xs font-semibold">👤</div>';
      };

      // Info
      const infoDiv = document.createElement('div');
      infoDiv.className = 'flex flex-col cursor-pointer';
      infoDiv.title = `Gemeinsame Fotos mit ${co.name} anzeigen`;
      infoDiv.onclick = () => filterClusterSharedImages(clusterId, co.cluster_id, co.name);

      const nameSpan = document.createElement('span');
      nameSpan.className = 'text-xs font-medium text-slate-200 group-hover:text-cyan-300 transition-colors truncate max-w-[130px]';
      nameSpan.textContent = co.name;

      const badgeSpan = document.createElement('span');
      badgeSpan.className = 'text-[10px] text-cyan-400/90 font-mono';
      badgeSpan.textContent = `${co.shared_count} gemeinsame${co.shared_count === 1 ? 's Foto' : ' Fotos'}`;

      infoDiv.appendChild(nameSpan);
      infoDiv.appendChild(badgeSpan);

      // Action: Shared images filter button
      const filterBtn = document.createElement('button');
      filterBtn.type = 'button';
      filterBtn.title = `Nur gemeinsame Fotos mit ${co.name} im Raster anzeigen`;
      filterBtn.className = 'p-1 rounded-lg bg-cyan-950/50 hover:bg-cyan-500/20 text-cyan-400 hover:text-cyan-200 transition text-xs border border-cyan-900/40';
      filterBtn.innerHTML = '🔍';
      filterBtn.onclick = (e) => {
        e.stopPropagation();
        filterClusterSharedImages(clusterId, co.cluster_id, co.name);
      };

      // Action: Jump to this person's cluster
      const jumpBtn = document.createElement('button');
      jumpBtn.type = 'button';
      jumpBtn.title = `Zu ${co.name} wechseln`;
      jumpBtn.className = 'p-1 rounded-lg bg-slate-900 hover:bg-slate-700 text-slate-400 hover:text-amber-400 transition text-xs border border-slate-800';
      jumpBtn.innerHTML = '👤';
      jumpBtn.onclick = (e) => {
        e.stopPropagation();
        jumpToCluster(co.cluster_id);
      };

      chip.appendChild(avatarImg);
      chip.appendChild(infoDiv);
      chip.appendChild(filterBtn);
      chip.appendChild(jumpBtn);

      listElem.appendChild(chip);
    });

  } catch (err) {
    console.error('Fehler bei Co-Occurrences:', err);
    listElem.innerHTML = `<span class="text-xs text-rose-400">Begleiter konnten nicht geladen werden (${escapeHtml(err.message)})</span>`;
  }
}

async function filterClusterSharedImages(clusterA, clusterB, nameB) {
  const imagesGrid = document.getElementById('cluster-images-grid');
  const banner = document.getElementById('cluster-shared-filter-banner');
  const personElem = document.getElementById('cluster-shared-filter-person');
  const countElem = document.getElementById('cluster-shared-filter-count');

  if (!imagesGrid) return;

  // Save original faces if not saved
  if (!activeSharedFilter && activeCluster) {
    activeSharedFilter = {
      clusterA,
      clusterB,
      nameB,
      originalFaces: [...(activeCluster.faces || [])]
    };
  }

  if (banner) banner.classList.remove('hidden');
  if (personElem) personElem.textContent = nameB;
  if (countElem) countElem.textContent = '(Lade Fotos...)';

  imagesGrid.innerHTML = `
    <div class="col-span-full py-16 text-center text-slate-400 flex flex-col items-center justify-center gap-3">
      <div class="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-sm font-medium text-cyan-200">Suche Fotos mit beiden Personen gleichzeitig...</span>
    </div>
  `;

  try {
    const res = await fetch(`/network/shared-images?person_a=${encodeURIComponent(clusterA)}&person_b=${encodeURIComponent(clusterB)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const sharedImages = await res.json();

    if (countElem) countElem.textContent = `(${sharedImages.length} Foto${sharedImages.length === 1 ? '' : 's'})`;

    imagesGrid.innerHTML = '';

    if (!sharedImages || sharedImages.length === 0) {
      imagesGrid.innerHTML = `
        <div class="col-span-full py-12 text-center text-slate-500">
          Keine gemeinsamen Fotos gefunden.
        </div>
      `;
      return;
    }

    sharedImages.forEach((img, idx) => {
      const card = document.createElement('div');
      card.className = 'bg-slate-900 border border-cyan-900/60 rounded-xl overflow-hidden shadow-lg flex flex-col hover:border-cyan-500/50 transition';

      const safePath = encodeURIComponent(img.file_path);
      const fileName = img.file_name || img.file_path.split('/').pop();

      card.innerHTML = `
        <div class="relative bg-slate-950 flex items-center justify-center p-2 cursor-pointer group" onclick="openImageModal('${escapeHtml(img.file_path).replace(/'/g, "\\'")}', '${escapeHtml(fileName).replace(/'/g, "\\'")}')">
          <img
            src="/images/serve?path=${safePath}&max_dim=600"
            alt="${escapeHtml(fileName)}"
            class="rounded max-h-72 object-contain group-hover:scale-[1.02] transition-transform duration-200"
          >
          <div class="absolute bottom-2 left-2 flex items-center gap-1 bg-slate-950/80 backdrop-blur-sm px-2 py-0.5 rounded-lg border border-cyan-500/40 text-[10px] text-cyan-300 font-mono">
            <span>👥 Gemeinsames Foto</span>
          </div>
        </div>
        <div class="p-3 border-t border-slate-800 flex items-center justify-between text-xs gap-2">
          <div class="min-w-0 flex-1 truncate">
            <span class="font-medium text-slate-200 truncate block">${escapeHtml(fileName)}</span>
            <span class="text-cyan-400 font-mono text-[11px]">${(img.faces || []).length} erkannte Personen</span>
          </div>
          <button
            type="button"
            onclick="openImageModal('${escapeHtml(img.file_path).replace(/'/g, "\\'")}', '${escapeHtml(fileName).replace(/'/g, "\\'")}')"
            class="px-2.5 py-1 bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 rounded-lg text-[11px] font-medium transition"
          >
            Großansicht
          </button>
        </div>
      `;

      imagesGrid.appendChild(card);
    });

  } catch (err) {
    console.error('Fehler bei gemeinsamen Fotos:', err);
    showToast(`Fehler beim Laden der gemeinsamen Fotos: ${err.message}`, true);
    clearClusterSharedFilter();
  }
}

function clearClusterSharedFilter(restoreGrid = true) {
  const banner = document.getElementById('cluster-shared-filter-banner');
  if (banner) banner.classList.add('hidden');

  if (activeSharedFilter && restoreGrid && activeCluster) {
    activeCluster.faces = activeSharedFilter.originalFaces;
    activeSharedFilter = null;
    openClusterDetail(activeCluster);
  } else {
    activeSharedFilter = null;
  }
}

async function jumpToCluster(clusterId) {
  if (!clusterId) return;
  closeImageModal();
  switchTab('faces');

  const normId = String(clusterId).startsWith('cluster_') ? clusterId : `cluster_${clusterId}`;

  // In geladenen Clustern suchen
  let target = (allLoadedClusters || []).find(c => String(c.cluster_id) === String(normId) || String(c.cluster_id) === String(clusterId));

  if (!target) {
    try {
      const res = await fetch(`/faces/clusters/${encodeURIComponent(normId)}`);
      if (res.ok) {
        target = await res.json();
      }
    } catch (err) {
      console.warn('Cluster konnte nicht geladen werden:', err);
    }
  }

  if (!target) {
    target = {
      cluster_id: normId,
      label: null,
      face_count: 0,
      faces: []
    };
  }

  openClusterDetail(target);
}

function openNetworkForActiveCluster() {
  if (!activeCluster) return;
  const cid = activeCluster.cluster_id;
  switchTab('network');
  setTimeout(() => {
    const sel = document.getElementById('network-person-select');
    if (sel) {
      sel.value = cid;
      reloadNetworkGraph();
    }
  }, 100);
}

async function initNetworkTab() {
  const personSelect = document.getElementById('network-person-select');
  if (!personSelect) return;

  // Sicherstellen, dass Clusterliste für Dropdown vorliegt
  if (!allLoadedClusters || allLoadedClusters.length === 0) {
    try {
      const res = await fetch('/faces/clusters?include_preview=false');
      if (res.ok) {
        allLoadedClusters = await res.json();
      }
    } catch (err) {
      console.error('Cluster für Netzwerk konnten nicht geladen werden:', err);
    }
  }

  const clusters = allLoadedClusters || [];
  const sorted = [...clusters].sort((a, b) => (b.face_count || 0) - (a.face_count || 0));

  const currentVal = personSelect.value;
  personSelect.innerHTML = '';

  if (sorted.length === 0) {
    personSelect.innerHTML = '<option value="">Keine Personen im Archiv vorhanden</option>';
    return;
  }

  sorted.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.cluster_id;
    const name = c.label || `Person ${String(c.cluster_id).replace('cluster_', '#')}`;
    opt.textContent = `${name} (${c.face_count} Fotos)`;
    personSelect.appendChild(opt);
  });

  if (currentVal && sorted.some(c => String(c.cluster_id) === String(currentVal))) {
    personSelect.value = currentVal;
  } else if (activeCluster && sorted.some(c => String(c.cluster_id) === String(activeCluster.cluster_id))) {
    personSelect.value = activeCluster.cluster_id;
  } else {
    personSelect.value = sorted[0].cluster_id;
  }

  await reloadNetworkGraph();
}

function handleNetworkPersonChange(clusterId) {
  closeNetworkNodeCard();
  reloadNetworkGraph();
}

async function reloadNetworkGraph() {
  const personSelect = document.getElementById('network-person-select');
  const depthSelect = document.getElementById('network-depth-select');
  const minSharedSelect = document.getElementById('network-minshared-select');
  const overlay = document.getElementById('network-loading-overlay');
  const statsBadge = document.getElementById('network-stats-badge');

  if (!personSelect || !personSelect.value) return;

  const clusterId = personSelect.value;
  const depth = depthSelect ? parseInt(depthSelect.value, 10) : 1;
  const minShared = minSharedSelect ? parseInt(minSharedSelect.value, 10) : 2;

  if (overlay) overlay.classList.remove('hidden');
  if (statsBadge) statsBadge.textContent = 'Berechne...';

  try {
    const res = await fetch(`/network/person/${encodeURIComponent(clusterId)}/graph?depth=${depth}&min_shared=${minShared}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const graphData = await res.json();

    currentNetworkData = graphData;
    renderNetworkGraph(graphData, clusterId);

    if (statsBadge) {
      statsBadge.textContent = `${graphData.nodes.length} Personen • ${graphData.edges.length} Beziehungen`;
    }
  } catch (err) {
    console.error('Fehler beim Laden des Netzwerk-Graphs:', err);
    showToast(`Graph-Fehler: ${err.message}`, true);
    if (statsBadge) statsBadge.textContent = 'Fehler';
  } finally {
    if (overlay) overlay.classList.add('hidden');
  }
}

function renderNetworkGraph(graphData, centerClusterId) {
  const container = document.getElementById('network-canvas');
  if (!container) return;

  if (typeof vis === 'undefined' || !vis.Network) {
    container.innerHTML = '<div class="p-8 text-center text-rose-400">vis-network Bibliothek nicht geladen.</div>';
    return;
  }

  const normCenter = String(centerClusterId);

  const visNodes = (graphData.nodes || []).map(n => {
    const isCenter = (String(n.id) === normCenter || String(n.id) === normCenter.replace('cluster_', ''));
    const photoCount = n.size || 1;
    const nodeSize = isCenter
      ? Math.max(26, Math.min(50, 20 + Math.sqrt(photoCount) * 4))
      : Math.max(16, Math.min(42, 12 + Math.sqrt(photoCount) * 3));

    return {
      id: String(n.id),
      label: n.label,
      shape: n.image ? 'circularImage' : 'dot',
      image: n.image || undefined,
      size: nodeSize,
      borderWidth: isCenter ? 4 : 2,
      borderWidthSelected: 5,
      color: {
        border: isCenter ? '#06b6d4' : '#38bdf8',
        background: '#090d16',
        highlight: {
          border: '#f59e0b',
          background: '#1e293b'
        },
        hover: {
          border: '#22d3ee',
          background: '#0f172a'
        }
      },
      font: {
        color: isCenter ? '#38bdf8' : '#e2e8f0',
        size: isCenter ? 14 : 12,
        face: 'ui-sans-serif, system-ui, sans-serif',
        bold: isCenter ? 'bold' : 'normal',
        strokeWidth: 3,
        strokeColor: '#030712'
      },
      meta: {
        id: String(n.id),
        label: n.label,
        size: n.size,
        image: n.image,
        isCenter
      }
    };
  });

  const visEdges = (graphData.edges || []).map(e => ({
    id: `${e.from}_${e.to}`,
    from: String(e.from),
    to: String(e.to),
    value: e.value,
    title: `${e.value} gemeinsame Fotos`,
    width: Math.max(1.5, Math.min(8, Math.log2(e.value + 1) * 2)),
    color: {
      color: 'rgba(6, 182, 212, 0.4)',
      highlight: '#f59e0b',
      hover: '#22d3ee'
    },
    smooth: {
      type: 'continuous',
      roundness: 0.2
    }
  }));

  const data = {
    nodes: new vis.DataSet(visNodes),
    edges: new vis.DataSet(visEdges)
  };

  const options = {
    nodes: {
      shadow: {
        enabled: true,
        color: 'rgba(0,0,0,0.6)',
        size: 10,
        x: 2,
        y: 2
      }
    },
    edges: {
      selectionWidth: 3,
      hoverWidth: 2
    },
    interaction: {
      hover: true,
      tooltipDelay: 120,
      zoomView: true,
      dragView: true,
      dragNodes: true
    },
    physics: {
      enabled: networkPhysicsEnabled,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -80,
        centralGravity: 0.015,
        springLength: 120,
        springConstant: 0.08,
        damping: 0.45,
        avoidOverlap: 0.6
      },
      stabilization: {
        iterations: 120,
        updateInterval: 25
      }
    }
  };

  if (networkInstance) {
    networkInstance.destroy();
  }

  networkInstance = new vis.Network(container, data, options);

  networkInstance.on('click', function(params) {
    if (params.nodes && params.nodes.length > 0) {
      const clickedId = params.nodes[0];
      showNetworkNodeCard(clickedId, centerClusterId);
    } else {
      closeNetworkNodeCard();
    }
  });

  networkInstance.on('doubleClick', function(params) {
    if (params.nodes && params.nodes.length > 0) {
      const clickedId = params.nodes[0];
      const personSelect = document.getElementById('network-person-select');
      if (personSelect) {
        personSelect.value = clickedId;
        reloadNetworkGraph();
      }
    }
  });
}

function showNetworkNodeCard(nodeId, centerId) {
  if (!currentNetworkData) return;
  const node = (currentNetworkData.nodes || []).find(n => String(n.id) === String(nodeId));
  if (!node) return;

  networkSelectedNode = node;
  const card = document.getElementById('network-node-card');
  const imgElem = document.getElementById('nnc-image');
  const nameElem = document.getElementById('nnc-name');
  const idElem = document.getElementById('nnc-id');
  const countElem = document.getElementById('nnc-face-count');
  const sharedRow = document.getElementById('nnc-shared-row');
  const sharedCount = document.getElementById('nnc-shared-count');
  const sharedBtn = document.getElementById('nnc-view-shared-btn');

  if (!card) return;

  if (nameElem) nameElem.textContent = node.label || 'Person';
  if (idElem) idElem.textContent = `Cluster #${String(node.id).replace('cluster_', '')}`;
  if (countElem) countElem.textContent = `${node.size || 1} Fotos`;

  const thumbUrl = node.image || `/faces/preview/${encodeURIComponent(node.id)}`;
  if (imgElem) {
    imgElem.src = thumbUrl;
    imgElem.onerror = () => {
      imgElem.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="%2306b6d4" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>';
    };
  }

  // Find shared count with center
  const isCenter = (String(node.id) === String(centerId) || String(node.id) === String(centerId).replace('cluster_', ''));
  if (isCenter) {
    if (sharedRow) sharedRow.classList.add('hidden');
    if (sharedBtn) sharedBtn.classList.add('hidden');
  } else {
    const edge = (currentNetworkData.edges || []).find(e =>
      (String(e.from) === String(centerId) && String(e.to) === String(node.id)) ||
      (String(e.to) === String(centerId) && String(e.from) === String(node.id)) ||
      (String(e.from) === String(centerId).replace('cluster_', '') && String(e.to) === String(node.id).replace('cluster_', '')) ||
      (String(e.to) === String(centerId).replace('cluster_', '') && String(e.from) === String(node.id).replace('cluster_', ''))
    );
    if (edge && sharedRow && sharedCount) {
      sharedRow.classList.remove('hidden');
      sharedCount.textContent = `${edge.value} Fotos`;
    } else if (sharedRow) {
      sharedRow.classList.add('hidden');
    }
    if (sharedBtn) sharedBtn.classList.remove('hidden');
  }

  card.classList.remove('hidden');
}

function closeNetworkNodeCard() {
  networkSelectedNode = null;
  const card = document.getElementById('network-node-card');
  if (card) card.classList.add('hidden');
}

function centerNetworkOnSelectedNode() {
  if (!networkSelectedNode) return;
  const personSelect = document.getElementById('network-person-select');
  if (personSelect) {
    personSelect.value = networkSelectedNode.id;
    closeNetworkNodeCard();
    reloadNetworkGraph();
  }
}

function openClusterFromNetworkCard() {
  if (!networkSelectedNode) return;
  const id = networkSelectedNode.id;
  closeNetworkNodeCard();
  jumpToCluster(id);
}

function filterSharedFromNetworkCard() {
  if (!networkSelectedNode) return;
  const personSelect = document.getElementById('network-person-select');
  if (!personSelect || !personSelect.value) return;

  const centerId = personSelect.value;
  const targetId = networkSelectedNode.id;
  const targetName = networkSelectedNode.label;

  closeNetworkNodeCard();
  jumpToCluster(centerId);
  setTimeout(() => {
    filterClusterSharedImages(centerId, targetId, targetName);
  }, 300);
}

function fitNetworkGraph() {
  if (networkInstance) {
    networkInstance.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
  }
}

function toggleNetworkPhysics() {
  if (!networkInstance) return;
  networkPhysicsEnabled = !networkPhysicsEnabled;
  networkInstance.setOptions({ physics: { enabled: networkPhysicsEnabled } });
  const btn = document.getElementById('network-physics-btn');
  if (btn) {
    btn.innerHTML = networkPhysicsEnabled ? '<span>⏸️ Physik</span>' : '<span>▶️ Physik</span>';
    btn.className = networkPhysicsEnabled
      ? 'px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-slate-700 shadow-sm'
      : 'px-3 py-1.5 bg-cyan-900/60 hover:bg-cyan-800 text-cyan-300 rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-cyan-700 shadow-sm';
  }
}

// ================= KIRCHLICHER THESAURUS & IKONOGRAPHIE =================

let thesaurusTermsCache = null;
let thesaurusCategoriesCache = [];
let activeThesaurusCategory = 'all';

async function checkAndDisplayThesaurusBanner(query) {
  const banner = document.getElementById('results-thesaurus-banner');
  const bannerText = document.getElementById('thesaurus-banner-text');
  const bannerIconclass = document.getElementById('thesaurus-banner-iconclass');
  const bannerGnd = document.getElementById('thesaurus-banner-gnd');
  if (!banner || !query || query.trim().length === 0) {
    if (banner) banner.classList.add('hidden');
    return;
  }

  try {
    const res = await fetch(`/thesaurus/expand?q=${encodeURIComponent(query.trim())}`);
    if (res.ok) {
      const data = await res.json();
      if (data && data.has_expansion && data.canonical) {
        const synList = (data.synonyms || []).slice(0, 4).join(', ');
        bannerText.innerHTML = `<strong>Kirchlicher Thesaurus aktiv:</strong> "${escapeHtml(data.canonical)}" <span class="text-purple-300">(${escapeHtml(data.category || '')})</span> &bull; <em>Query-Expansion:</em> ${escapeHtml(synList || data.canonical)}`;
        if (data.iconclass) {
          bannerIconclass.textContent = `Iconclass ${data.iconclass}`;
          bannerIconclass.classList.remove('hidden');
        } else {
          bannerIconclass.classList.add('hidden');
        }
        if (data.gnd) {
          bannerGnd.textContent = `GND ${data.gnd}`;
          bannerGnd.classList.remove('hidden');
        } else {
          bannerGnd.classList.add('hidden');
        }
        banner.classList.remove('hidden');
        return;
      }
    }
  } catch (err) {
    console.debug('Thesaurus expand check error:', err);
  }
  banner.classList.add('hidden');
}

async function openThesaurusModal() {
  const modal = document.getElementById('thesaurus-modal');
  if (!modal) return;
  modal.classList.remove('hidden');

  if (!thesaurusTermsCache) {
    await loadThesaurusData();
  } else {
    renderThesaurusTabs();
    filterThesaurusModal(document.getElementById('thesaurus-filter-input')?.value || '');
  }

  const input = document.getElementById('thesaurus-filter-input');
  if (input) {
    setTimeout(() => input.focus(), 100);
  }
}

function closeThesaurusModal() {
  const modal = document.getElementById('thesaurus-modal');
  if (modal) modal.classList.add('hidden');
}

async function loadThesaurusData() {
  const grid = document.getElementById('thesaurus-terms-grid');
  if (grid) {
    grid.innerHTML = '<div class="col-span-2 py-8 text-center text-slate-500 font-mono text-xs">Lade Thesaurus-Daten...</div>';
  }

  try {
    const [termsRes, catRes] = await Promise.all([
      fetch('/thesaurus/terms'),
      fetch('/thesaurus/categories')
    ]);

    if (termsRes.ok) {
      thesaurusTermsCache = await termsRes.json();
    } else {
      thesaurusTermsCache = [];
    }

    if (catRes.ok) {
      const catData = await catRes.json();
      thesaurusCategoriesCache = Array.isArray(catData) ? catData : (catData.categories || []);
    } else {
      thesaurusCategoriesCache = [];
    }

    renderThesaurusTabs();
    filterThesaurusModal('');
  } catch (err) {
    console.error('Fehler beim Laden des Thesaurus:', err);
    if (grid) {
      grid.innerHTML = `<div class="col-span-2 py-8 text-center text-rose-400 text-xs">Fehler beim Laden: ${escapeHtml(err.message)}</div>`;
    }
  }
}

function renderThesaurusTabs() {
  const tabsContainer = document.getElementById('thesaurus-category-tabs');
  if (!tabsContainer) return;

  const totalCount = (thesaurusTermsCache || []).length;
  let html = `
    <button type="button" onclick="selectThesaurusCategory('all')"
      class="px-2.5 py-1 rounded-lg font-medium transition text-xs flex items-center gap-1.5 ${activeThesaurusCategory === 'all' ? 'bg-purple-600 text-white shadow-sm' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
      <span>Alle</span>
      <span class="text-[10px] px-1.5 py-0.2 rounded-full ${activeThesaurusCategory === 'all' ? 'bg-purple-800 text-purple-200' : 'bg-slate-900 text-slate-400'}">${totalCount}</span>
    </button>`;

  thesaurusCategoriesCache.forEach(catName => {
    const catCount = (thesaurusTermsCache || []).filter(t => t.category === catName).length;
    const isActive = activeThesaurusCategory === catName;
    html += `
      <button type="button" onclick="selectThesaurusCategory('${escapeHtml(catName)}')"
        class="px-2.5 py-1 rounded-lg font-medium transition text-xs flex items-center gap-1.5 ${isActive ? 'bg-purple-600 text-white shadow-sm' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
        <span>${escapeHtml(catName)}</span>
        <span class="text-[10px] px-1.5 py-0.2 rounded-full ${isActive ? 'bg-purple-800 text-purple-200' : 'bg-slate-900 text-slate-400'}">${catCount}</span>
      </button>`;
  });

  tabsContainer.innerHTML = html;
}

function selectThesaurusCategory(cat) {
  activeThesaurusCategory = cat;
  renderThesaurusTabs();
  const input = document.getElementById('thesaurus-filter-input');
  filterThesaurusModal(input ? input.value : '');
}

function filterThesaurusModal(query) {
  const clearBtn = document.getElementById('thesaurus-filter-clear');
  const q = (query || '').trim().toLowerCase();

  if (clearBtn) {
    if (q) clearBtn.classList.remove('hidden');
    else clearBtn.classList.add('hidden');
  }

  if (!thesaurusTermsCache) return;

  const filtered = thesaurusTermsCache.filter(item => {
    // 1. Kategorie Filter
    if (activeThesaurusCategory !== 'all' && item.category !== activeThesaurusCategory) {
      return false;
    }
    // 2. Text Query Filter
    if (!q) return true;
    const can = (item.canonical || item.canonical_de || '').toLowerCase();
    const desc = (item.description || '').toLowerCase();
    const ic = (item.iconclass || '').toLowerCase();
    const gnd = (item.gnd || item.gnd_id || '').toLowerCase();
    if (can.includes(q) || desc.includes(q) || ic.includes(q) || gnd.includes(q)) return true;
    if (item.synonyms && item.synonyms.some(s => s.toLowerCase().includes(q))) return true;
    return false;
  });

  renderThesaurusGrid(filtered);
}

function clearThesaurusFilter() {
  const input = document.getElementById('thesaurus-filter-input');
  if (input) input.value = '';
  filterThesaurusModal('');
  if (input) input.focus();
}

function renderThesaurusGrid(terms) {
  const grid = document.getElementById('thesaurus-terms-grid');
  const empty = document.getElementById('thesaurus-empty-state');
  if (!grid || !empty) return;

  if (terms.length === 0) {
    grid.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }

  empty.classList.add('hidden');

  let html = '';
  terms.forEach(term => {
    const canonicalName = term.canonical || term.canonical_de || '';
    const gndVal = term.gnd || term.gnd_id || '';
    const synChips = (term.synonyms || []).map(s => 
      `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] border border-slate-700/60">${escapeHtml(s)}</span>`
    ).join(' ');

    html += `
      <div class="bg-slate-950/70 border border-slate-800 hover:border-purple-500/50 rounded-xl p-3.5 flex flex-col justify-between transition-all group shadow-sm">
        <div>
          <div class="flex items-start justify-between gap-2 mb-1.5">
            <h4 class="text-sm font-semibold text-slate-100 group-hover:text-purple-300 transition">
              ${escapeHtml(canonicalName)}
            </h4>
            <span class="px-2 py-0.5 rounded-full bg-purple-950/70 border border-purple-500/40 text-purple-300 text-[10px] shrink-0 font-medium">
              ${escapeHtml(term.category)}
            </span>
          </div>
          <p class="text-xs text-slate-400 leading-relaxed mb-2.5">
            ${escapeHtml(term.description || '')}
          </p>
          <div class="flex flex-wrap items-center gap-1.5 mb-2.5">
            ${term.iconclass ? `
              <span class="px-2 py-0.5 rounded bg-purple-900/40 border border-purple-500/30 text-purple-300 font-mono text-[10px] flex items-center gap-1" title="Iconclass Ikonographie-Code">
                <span>🏛️</span>
                <span>${escapeHtml(term.iconclass)}</span>
              </span>` : ''}
            ${gndVal ? `
              <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700/80 text-slate-300 font-mono text-[10px] flex items-center gap-1" title="Gemeinsame Normdatei (GND) ID">
                <span>🏷️ GND: ${escapeHtml(gndVal)}</span>
              </span>` : ''}
          </div>
          ${synChips ? `
            <div class="text-[11px] text-slate-500 mb-2">
              <span class="text-slate-400 font-semibold block text-[10px] uppercase tracking-wider mb-1">Synonyme / Unterbegriffe:</span>
              <div class="flex flex-wrap gap-1">${synChips}</div>
            </div>` : ''}
        </div>
        <div class="pt-2.5 mt-2 border-t border-slate-800/80 flex items-center justify-end">
          <button type="button" onclick="applyThesaurusTermToSearch('${escapeHtml(canonicalName)}')"
            class="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5">
            <span>🔍</span>
            <span>In Suche übernehmen</span>
          </button>
        </div>
      </div>`;
  });

  grid.innerHTML = html;
}

function applyThesaurusTermToSearch(term) {
  closeThesaurusModal();
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.value = term;
  }
  executeSearch(term);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

