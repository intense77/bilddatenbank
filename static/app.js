/**
 * Historisches Bildarchiv - Frontend Logik (Vanilla JS)
 */

let activeCluster = null;
let currentModalImageDetails = null;

// Initialisierung bei DOM-Ready
document.addEventListener('DOMContentLoaded', () => {
  checkSystemHealth();
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
  const searchBtn = document.getElementById('tab-search-btn');
  const facesBtn = document.getElementById('tab-faces-btn');

  if (tab === 'search') {
    searchSec.classList.remove('hidden');
    facesSec.classList.add('hidden');
    searchBtn.className = 'px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all bg-amber-500 text-slate-950 font-semibold shadow-sm flex items-center gap-2';
    facesBtn.className = 'px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 transition-all flex items-center gap-2';
  } else {
    searchSec.classList.add('hidden');
    facesSec.classList.remove('hidden');
    facesBtn.className = 'px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all bg-amber-500 text-slate-950 font-semibold shadow-sm flex items-center gap-2';
    searchBtn.className = 'px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 transition-all flex items-center gap-2';
    // Lade Cluster automatisch beim ersten Aufruf
    loadClusters();
  }
}

// --- Health Check ---
async function checkSystemHealth() {
  const badge = document.getElementById('health-badge');
  const status = document.getElementById('health-status');
  try {
    const res = await fetch('/api/system/health');
    if (res.ok) {
      const data = await res.json();
      badge.classList.remove('hidden');
      status.textContent = `Qdrant: ${data.status} (${data.device.toUpperCase()})`;
    }
  } catch (err) {
    status.textContent = 'Qdrant offline';
    badge.querySelector('span').className = 'w-2 h-2 rounded-full bg-rose-500';
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

  try {
    let url = `/search/semantic?q=${encodeURIComponent(query)}&limit=${limit}`;
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

function renderSearchResults(items, container) {
  container.innerHTML = '';
  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'group bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl overflow-hidden shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 cursor-pointer flex flex-col';
    
    // Score als Prozent
    const scorePct = Math.round(item.score * 100);
    const scoreColor = scorePct >= 65 ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' :
                       scorePct >= 45 ? 'text-amber-400 border-amber-500/30 bg-amber-500/10' :
                                        'text-slate-400 border-slate-500/30 bg-slate-500/10';

    const safePath = encodeURIComponent(item.file_path);
    card.innerHTML = `
      <div class="aspect-[4/3] bg-slate-950 relative overflow-hidden flex items-center justify-center">
        <img
          src="/images/serve?path=${safePath}&max_dim=400"
          alt="${escapeHtml(item.file_name)}"
          loading="lazy"
          class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\' fill=\\'%23334155\\'><text x=\\'50%\\' y=\\'50%\\' text-anchor=\\'middle\\' fill=\\'%2364748b\\' font-size=\\'12\\'>Scan</text></svg>'"
        >
        <span class="absolute top-2 right-2 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${scoreColor} backdrop-blur-md">
          ${scorePct}% Score
        </span>
      </div>
      <div class="p-3 flex-1 flex flex-col justify-between">
        <h5 class="text-xs font-medium text-slate-200 truncate group-hover:text-amber-400 transition" title="${escapeHtml(item.file_name)}">
          ${escapeHtml(item.file_name)}
        </h5>
        <div class="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <span class="truncate max-w-[120px] font-mono">${escapeHtml(item.file_path.split('/').slice(-2, -1)[0] || 'Archiv')}</span>
          <span class="text-amber-500/80 group-hover:translate-x-0.5 transition-transform">Details →</span>
        </div>
      </div>
    `;

    card.addEventListener('click', () => openImageModal(item.file_path, item.file_name));
    container.appendChild(card);
  });
}

// --- 2. Personen & Cluster ---

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

  try {
    const res = await fetch('/faces/clusters?include_preview=true');
    if (!res.ok) throw new Error(`Fehler beim Abruf der Cluster (${res.status})`);
    const clusters = await res.json();

    spinner.classList.add('hidden');

    if (clusters.length === 0) {
      empty.classList.remove('hidden');
      return;
    }

    clusters.forEach(c => {
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
        <span class="mt-3 text-[11px] text-amber-500/90 font-medium group-hover:underline">
          Archivbilder ansehen →
        </span>
      `;

      card.addEventListener('click', () => openClusterDetail(c));
      grid.appendChild(card);
    });

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
      </div>
      <div class="p-3 border-t border-slate-800 flex items-center justify-between text-xs">
        <div class="truncate max-w-[200px]">
          <span class="font-medium text-slate-200 truncate block">${escapeHtml(fileName)}</span>
          <span class="text-slate-500 font-mono text-[11px]">Konfidenz: ${(face.det_score * 100).toFixed(1)}%</span>
        </div>
        <button
          onclick="openImageModal('${escapeHtml(face.file_path)}', '${escapeHtml(fileName)}')"
          class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] font-medium transition"
        >
          Großansicht
        </button>
      </div>
    `;

    imagesGrid.appendChild(card);

    // Bounding Box über dem Bild positionieren
    const imgElem = card.querySelector(`#cluster-img-${idx}`);
    const wrapElem = card.querySelector(`#cluster-bbox-wrap-${idx}`);

    function renderBox() {
      // Entferne evtl. vorhandene Boxen
      wrapElem.querySelectorAll('.face-bbox').forEach(e => e.remove());
      if (!face.bbox || face.bbox.length !== 4) return;

      // Wir holen die natürlichen Dimensionen des Bildes
      const natW = imgElem.naturalWidth;
      const natH = imgElem.naturalHeight;
      if (!natW || !natH) return;

      const [x1, y1, x2, y2] = face.bbox;
      const left = (x1 / natW) * 100;
      const top = (y1 / natH) * 100;
      const width = ((x2 - x1) / natW) * 100;
      const height = ((y2 - y1) / natH) * 100;

      const box = document.createElement('div');
      box.className = 'face-bbox active';
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

    if (imgElem.complete && imgElem.naturalWidth) {
      renderBox();
    } else {
      imgElem.addEventListener('load', renderBox);
    }

    // Klick auf das Bild öffnet das große Modal
    wrapElem.addEventListener('click', () => openImageModal(face.file_path, fileName));
  });
}

function closeClusterDetail() {
  activeCluster = null;
  loadClusters();
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
    document.getElementById('cd-title').textContent = label;
    showToast(`Name "${label}" für ${data.updated_faces} Gesichter gespeichert!`);
  } catch (err) {
    showToast(`Fehler: ${err.message}`, true);
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

async function openImageModal(filePath, fileName) {
  const modal = document.getElementById('image-modal');
  const img = document.getElementById('modal-img');
  const title = document.getElementById('modal-filename');
  const pathElem = document.getElementById('modal-filepath');
  const rawLink = document.getElementById('modal-raw-link');
  const similarBtn = document.getElementById('modal-similar-btn');
  const wrapper = document.getElementById('modal-bbox-wrapper');
  const facesList = document.getElementById('modal-faces-list');

  currentModalImageDetails = { filePath, fileName };

  title.textContent = fileName || filePath.split('/').pop();
  pathElem.textContent = filePath;
  rawLink.href = `/images/serve?path=${encodeURIComponent(filePath)}`;

  // Vorherige Bounding Boxes und Tags leeren
  wrapper.querySelectorAll('.face-bbox').forEach(e => e.remove());
  facesList.innerHTML = '<span class="text-slate-500 font-mono">Lade Merkmale...</span>';

  // Ähnlichkeitssuche Button Event
  similarBtn.onclick = () => {
    closeImageModal();
    searchSimilarImages(filePath);
  };

  // Bildquelle setzen
  img.src = `/images/serve?path=${encodeURIComponent(filePath)}&max_dim=1200`;

  modal.classList.remove('hidden');

  // Lade Gesichtsdetails aus der Datenbank
  try {
    const res = await fetch(`/images/details?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) return;
    const data = await res.json();

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
      const natW = img.naturalWidth;
      const natH = img.naturalHeight;
      if (!natW || !natH || !data.faces) return;

      data.faces.forEach((f, idx) => {
        if (!f.bbox || f.bbox.length !== 4) return;
        const [x1, y1, x2, y2] = f.bbox;
        const left = (x1 / natW) * 100;
        const top = (y1 / natH) * 100;
        const width = ((x2 - x1) / natW) * 100;
        const height = ((y2 - y1) / natH) * 100;

        const box = document.createElement('div');
        box.className = 'face-bbox';
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

    if (img.complete && img.naturalWidth) {
      drawModalBoxes();
    } else {
      img.onload = drawModalBoxes;
    }

  } catch (err) {
    facesList.innerHTML = '<span class="text-rose-400">Details nicht geladen</span>';
  }
}

function closeImageModal() {
  const modal = document.getElementById('image-modal');
  modal.classList.add('hidden');
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

  try {
    const res = await fetch(`/search/similar?image_path=${encodeURIComponent(filePath)}&limit=20`);
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
