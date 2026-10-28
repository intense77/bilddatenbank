/**
 * Digitaler Leuchttisch & Findbuch- / PDF-Export
 * Merkzettel für Kuration, Bildvergleiche und archivischen Export
 */

import { escapeHtml } from './utils.js';
import { showToast, showConfirmModal, showUndoToast } from './dialogs.js';

export const LIGHTBOX_STORAGE_KEY = 'archive_lightbox_items';
export const LIGHTBOX_TITLE_KEY = 'archive_lightbox_project_title';
export let lightboxItems = [];

/**
 * Lädt den Zustand des Leuchttischs aus dem localStorage.
 */
export function loadLightboxState() {
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

/**
 * Speichert den Leuchttisch im localStorage und aktualisiert Zähler.
 */
export function saveLightboxState() {
  try {
    localStorage.setItem(LIGHTBOX_STORAGE_KEY, JSON.stringify(lightboxItems));
  } catch (e) {
    console.error('Fehler beim Speichern des Leuchttischs:', e);
  }
  updateLightboxBadge();
}

/**
 * Aktualisiert die Zähler-Badges in Navigation und Werkzeugleiste.
 */
export function updateLightboxBadge() {
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

/**
 * Prüft, ob ein Bild auf dem Leuchttisch liegt.
 * @param {string} filePath
 * @returns {boolean}
 */
export function isItemInLightbox(filePath) {
  if (!filePath) return false;
  return lightboxItems.some(it => it.file_path === filePath);
}

/**
 * Legt ein Bild auf den Leuchttisch.
 * @param {any} item
 * @returns {boolean}
 */
export function addToLightbox(item) {
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

/**
 * Entfernt ein Bild vom Leuchttisch.
 * @param {string} filePath
 * @returns {boolean}
 */
export function removeFromLightbox(filePath) {
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

/**
 * Schaltet ein Bild auf dem Leuchttisch an/aus.
 * @param {any} item
 * @returns {boolean}
 */
export function toggleLightboxItem(item) {
  if (isItemInLightbox(item.file_path)) {
    removeFromLightbox(item.file_path);
    return false;
  } else {
    addToLightbox(item);
    return true;
  }
}

/**
 * Schaltet den Leuchttisch-Status über einen Suchkarten-Button um.
 * @param {Event} event
 * @param {any} itemOrPathOrIdx
 */
export function toggleLightboxCard(event, itemOrPathOrIdx) {
  event.stopPropagation();
  let item = null;
  const rendered = window.currentRenderedResults || [];
  const searchResults = window.currentSearchResults || [];

  if (typeof itemOrPathOrIdx === 'object' && itemOrPathOrIdx !== null) {
    item = itemOrPathOrIdx;
  } else if (typeof itemOrPathOrIdx === 'string') {
    item = rendered.find(i => i.file_path === itemOrPathOrIdx) ||
           searchResults.find(i => i.file_path === itemOrPathOrIdx);
  } else if (typeof itemOrPathOrIdx === 'number') {
    item = rendered[itemOrPathOrIdx] || searchResults[itemOrPathOrIdx];
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

/**
 * Fügt alle aktuellen Suchergebnisse auf einmal zum Leuchttisch hinzu.
 */
export function addAllCurrentResultsToLightbox() {
  const currentSearchResults = window.currentSearchResults || [];
  if (currentSearchResults.length === 0) return;
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
  if (grid && typeof window.renderSearchResults === 'function') {
    window.renderSearchResults(currentSearchResults, grid);
  }
}

/**
 * Aktualisiert den Leuchttisch-Button im Bilddetail-Modal.
 * @param {string} filePath
 */
export function updateModalLightboxButtonState(filePath) {
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

/**
 * Schaltet das aktuelle Bild im Modal auf den Leuchttisch oder herunter.
 */
export function toggleCurrentModalLightbox() {
  const currentModalImageDetails = window.currentModalImageDetails;
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

export function handleLightboxTitleChange(val) {
  localStorage.setItem(LIGHTBOX_TITLE_KEY, val || '');
}

export function copyLightboxPaths() {
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

export async function clearLightboxConfirm() {
  if (lightboxItems.length === 0) return;
  const count = lightboxItems.length;
  const ok = await showConfirmModal(
    'Leuchttisch leeren',
    `Möchten Sie wirklich alle ${count} Bilder vom Leuchttisch entfernen?`,
    'Leeren',
    'Abbrechen',
    true
  );
  if (ok) {
    const prevItems = [...lightboxItems];
    lightboxItems = [];
    saveLightboxState();
    renderLightboxView();
    showUndoToast(`${count} Bild(er) vom Leuchttisch entfernt.`, () => {
      lightboxItems = prevItems;
      saveLightboxState();
      renderLightboxView();
      showToast('Leuchttisch wiederhergestellt.', false);
    });
  }
}

export function updateLightboxItemNote(filePath, note) {
  const item = lightboxItems.find(it => it.file_path === filePath);
  if (item) {
    item.notes = note;
    saveLightboxState();
  }
}

export function renderLightboxView() {
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
          <button
            type="button"
            onclick="rotateLightboxCardImage(event, '${escapeHtml(item.file_path).replace(/'/g, "\\'")}', 90, ${idx})"
            class="absolute top-2 right-2 p-1.5 rounded-lg bg-slate-900/80 hover:bg-amber-500 hover:text-slate-950 text-slate-300 border border-slate-700/80 transition-all shadow-md backdrop-blur-sm z-20 cursor-pointer"
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
          class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] font-medium transition cursor-pointer"
        >
          Großansicht
        </button>
        <button
          onclick="removeFromLightbox('${escapeHtml(item.file_path).replace(/'/g, "\\'")}')"
          class="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-[11px] font-medium transition flex items-center gap-1 cursor-pointer"
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

export async function rotateLightboxCardImage(event, filePath, angle, idx) {
  event.stopPropagation();
  const btn = event.currentTarget;
  btn.disabled = true;
  btn.innerHTML = '<span class="animate-spin inline-block">⏳</span>';

  try {
    showToast(`Drehe Bild um ${angle}° verlustfrei...`, false);
    if (typeof window.rotateImageFile !== 'function') {
      throw new Error('Dreh-Funktion nicht verfügbar');
    }
    const result = await window.rotateImageFile(filePath, angle);
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

export function openPdfExportModal() {
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

export function closePdfExportModal() {
  const modal = document.getElementById('pdf-export-modal');
  if (modal) modal.classList.add('hidden');
}

export async function handlePdfExportSubmit(event) {
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

export async function exportLightboxFindbuchCsv() {
  if (lightboxItems.length === 0) {
    showToast('Fügen Sie zuerst Bilder zum Leuchttisch hinzu.', true);
    return;
  }

  const btn = document.getElementById('lightbox-export-findbuch-btn');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Exportiere...</span>';
  }

  try {
    showToast(`Generiere archivisches Findbuch für ${lightboxItems.length} Verzeichnungseinheiten...`, false);
    const titleInput = document.getElementById('lightbox-title-input');
    const folderTitle = (titleInput && titleInput.value.trim()) || 'Leuchttisch-Mappe';

    const payload = {
      items: lightboxItems.map(it => ({
        file_path: it.file_path,
        file_name: it.file_name,
        title: it.title,
        date: it.date,
        creator: it.creator,
        signature: it.signature,
        persons: Array.isArray(it.persons) ? it.persons : (it.persons ? [it.persons] : []),
        notes: it.notes || null,
      })),
      archive_name: 'Historisches Bildarchiv',
      collection_title: folderTitle,
    };

    const res = await fetch('/export/findbuch-csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler beim Findbuch-Export (${res.status})`);

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    a.download = `Findbuch_${now}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast(`✓ Findbuch (${lightboxItems.length} Einträge) erfolgreich als CSV exportiert!`, false);
  } catch (err) {
    console.error('Fehler beim Findbuch-Export:', err);
    showToast(`Findbuch-Export fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

export async function exportLightboxEadXml() {
  if (lightboxItems.length === 0) {
    showToast('Fügen Sie zuerst Bilder zum Leuchttisch hinzu.', true);
    return;
  }

  const btn = document.getElementById('lightbox-export-ead-btn');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Exportiere...</span>';
  }

  try {
    showToast(`Generiere EAD3-XML nach ISAD(G) für ${lightboxItems.length} Verzeichnungseinheiten...`, false);
    const titleInput = document.getElementById('lightbox-project-title') || document.getElementById('lightbox-title-input');
    const folderTitle = (titleInput && titleInput.value.trim()) || 'Leuchttisch-Mappe';

    const payload = {
      items: lightboxItems.map(it => ({
        file_path: it.file_path,
        file_name: it.file_name,
        title: it.title,
        date: it.date,
        creator: it.creator,
        signature: it.signature,
        persons: Array.isArray(it.persons) ? it.persons : (it.persons ? [it.persons] : []),
        notes: it.notes || null,
      })),
      archive_name: 'Historisches Bildarchiv',
      collection_title: folderTitle,
    };

    const res = await fetch('/export/ead-xml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler beim EAD3-Export (${res.status})`);

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    a.download = `EAD3_${now}.xml`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast(`✓ EAD3-Findbuch (${lightboxItems.length} Einheiten) erfolgreich als XML exportiert!`, false);
  } catch (err) {
    console.error('Fehler beim EAD3-Export:', err);
    showToast(`EAD3-Export fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

export async function exportLightboxLidoXml() {
  if (lightboxItems.length === 0) {
    showToast('Fügen Sie zuerst Bilder zum Leuchttisch hinzu.', true);
    return;
  }

  const btn = document.getElementById('lightbox-export-lido-btn');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> <span>Exportiere...</span>';
  }

  try {
    showToast(`Generiere LIDO 1.1 XML für ${lightboxItems.length} Kulturgüter...`, false);
    const titleInput = document.getElementById('lightbox-project-title') || document.getElementById('lightbox-title-input');
    const folderTitle = (titleInput && titleInput.value.trim()) || 'Leuchttisch-Mappe';

    const payload = {
      items: lightboxItems.map(it => ({
        file_path: it.file_path,
        file_name: it.file_name,
        title: it.title,
        date: it.date,
        creator: it.creator,
        signature: it.signature,
        persons: Array.isArray(it.persons) ? it.persons : (it.persons ? [it.persons] : []),
        notes: it.notes || null,
      })),
      archive_name: 'Historisches Bildarchiv',
      collection_title: folderTitle,
    };

    const res = await fetch('/export/lido-xml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`Server-Fehler beim LIDO-Export (${res.status})`);

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    a.download = `LIDO_${now}.xml`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast(`✓ LIDO 1.1 Datensatz (${lightboxItems.length} Objekte) für DDB/Europeana exportiert!`, false);
  } catch (err) {
    console.error('Fehler beim LIDO-Export:', err);
    showToast(`LIDO-Export fehlgeschlagen: ${err.message}`, true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

