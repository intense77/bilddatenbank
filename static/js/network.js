/**
 * Personennetzwerk & Graph-Visualisierung (Vis-Network)
 * Analyse historischer Co-Occurrences (gemeinsam abgebildete Personen)
 */

import { escapeHtml } from './utils.js';
import { showToast } from './dialogs.js';

export let networkInstance = null;
export let currentNetworkData = null;
export let networkSelectedNode = null;
export let networkPhysicsEnabled = true;
export let activeSharedFilter = null;

export async function loadClusterCoOccurrences(clusterId) {
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

      const thumbUrl = co.thumbnail_url || `/faces/preview/${encodeURIComponent(co.cluster_id)}`;
      const avatarImg = document.createElement('img');
      avatarImg.src = thumbUrl;
      avatarImg.alt = co.name;
      avatarImg.className = 'w-7 h-7 rounded-full object-cover border border-cyan-500/40 bg-slate-900';
      avatarImg.onerror = () => {
        avatarImg.outerHTML = '<div class="w-7 h-7 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center text-xs font-semibold">👤</div>';
      };

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

      const filterBtn = document.createElement('button');
      filterBtn.type = 'button';
      filterBtn.title = `Nur gemeinsame Fotos mit ${co.name} im Raster anzeigen`;
      filterBtn.className = 'p-1 rounded-lg bg-cyan-950/50 hover:bg-cyan-500/20 text-cyan-400 hover:text-cyan-200 transition text-xs border border-cyan-900/40 cursor-pointer';
      filterBtn.innerHTML = '🔍';
      filterBtn.onclick = (e) => {
        e.stopPropagation();
        filterClusterSharedImages(clusterId, co.cluster_id, co.name);
      };

      const jumpBtn = document.createElement('button');
      jumpBtn.type = 'button';
      jumpBtn.title = `Zu ${co.name} wechseln`;
      jumpBtn.className = 'p-1 rounded-lg bg-slate-900 hover:bg-slate-700 text-slate-400 hover:text-amber-400 transition text-xs border border-slate-800 cursor-pointer';
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

export async function filterClusterSharedImages(clusterA, clusterB, nameB) {
  const imagesGrid = document.getElementById('cluster-images-grid');
  const banner = document.getElementById('cluster-shared-filter-banner');
  const personElem = document.getElementById('cluster-shared-filter-person');
  const countElem = document.getElementById('cluster-shared-filter-count');
  const activeCluster = window.activeCluster;

  if (!imagesGrid) return;

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

    sharedImages.forEach((img) => {
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
            class="px-2.5 py-1 bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 rounded-lg text-[11px] font-medium transition cursor-pointer"
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

export function clearClusterSharedFilter(restoreGrid = true) {
  const banner = document.getElementById('cluster-shared-filter-banner');
  if (banner) banner.classList.add('hidden');
  const activeCluster = window.activeCluster;

  if (activeSharedFilter && restoreGrid && activeCluster) {
    activeCluster.faces = activeSharedFilter.originalFaces;
    activeSharedFilter = null;
    if (typeof window.openClusterDetail === 'function') {
      window.openClusterDetail(activeCluster);
    }
  } else {
    activeSharedFilter = null;
  }
}

export async function jumpToCluster(clusterId) {
  if (!clusterId) return;
  if (typeof window.closeImageModal === 'function') window.closeImageModal();
  if (typeof window.switchTab === 'function') window.switchTab('faces');

  const normId = String(clusterId).startsWith('cluster_') ? clusterId : `cluster_${clusterId}`;
  let allLoadedClusters = window.allLoadedClusters || [];
  let target = allLoadedClusters.find(c => String(c.cluster_id) === String(normId) || String(c.cluster_id) === String(clusterId));

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

  if (typeof window.openClusterDetail === 'function') {
    window.openClusterDetail(target);
  }
}

export function openNetworkForActiveCluster() {
  const activeCluster = window.activeCluster;
  if (!activeCluster) return;
  const cid = activeCluster.cluster_id;
  if (typeof window.switchTab === 'function') window.switchTab('network');
  setTimeout(() => {
    const sel = document.getElementById('network-person-select');
    if (sel) {
      sel.value = cid;
      reloadNetworkGraph();
    }
  }, 100);
}

export async function initNetworkTab() {
  const personSelect = document.getElementById('network-person-select');
  if (!personSelect) return;

  let allLoadedClusters = window.allLoadedClusters;
  if (!allLoadedClusters || allLoadedClusters.length === 0) {
    try {
      const res = await fetch('/faces/clusters?include_preview=false');
      if (res.ok) {
        allLoadedClusters = await res.json();
        window.allLoadedClusters = allLoadedClusters;
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

  const activeCluster = window.activeCluster;
  if (currentVal && sorted.some(c => String(c.cluster_id) === String(currentVal))) {
    personSelect.value = currentVal;
  } else if (activeCluster && sorted.some(c => String(c.cluster_id) === String(activeCluster.cluster_id))) {
    personSelect.value = activeCluster.cluster_id;
  } else {
    personSelect.value = sorted[0].cluster_id;
  }

  await reloadNetworkGraph();
}

export function handleNetworkPersonChange() {
  closeNetworkNodeCard();
  reloadNetworkGraph();
}

export async function reloadNetworkGraph() {
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

export function renderNetworkGraph(graphData, centerClusterId) {
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

export function showNetworkNodeCard(nodeId, centerId) {
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

export function closeNetworkNodeCard() {
  networkSelectedNode = null;
  const card = document.getElementById('network-node-card');
  if (card) card.classList.add('hidden');
}

export function centerNetworkOnSelectedNode() {
  if (!networkSelectedNode) return;
  const personSelect = document.getElementById('network-person-select');
  if (personSelect) {
    personSelect.value = networkSelectedNode.id;
    closeNetworkNodeCard();
    reloadNetworkGraph();
  }
}

export function openClusterFromNetworkCard() {
  if (!networkSelectedNode) return;
  const id = networkSelectedNode.id;
  closeNetworkNodeCard();
  jumpToCluster(id);
}

export function filterSharedFromNetworkCard() {
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

export function fitNetworkGraph() {
  if (networkInstance) {
    networkInstance.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
  }
}

export function toggleNetworkPhysics() {
  if (!networkInstance) return;
  networkPhysicsEnabled = !networkPhysicsEnabled;
  networkInstance.setOptions({ physics: { enabled: networkPhysicsEnabled } });
  const btn = document.getElementById('network-physics-btn');
  if (btn) {
    btn.innerHTML = networkPhysicsEnabled ? '<span>⏸️ Physik</span>' : '<span>▶️ Physik</span>';
    btn.className = networkPhysicsEnabled
      ? 'px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-slate-700 shadow-sm cursor-pointer'
      : 'px-3 py-1.5 bg-cyan-900/60 hover:bg-cyan-800 text-cyan-300 rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-cyan-700 shadow-sm cursor-pointer';
  }
}
