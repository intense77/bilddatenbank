/**
 * Kirchlicher Thesaurus & Ikonographie
 * Query-Expansion, Iconclass-Codes, GND-Referenzen und thematische Recherche
 */

import { escapeHtml } from './utils.js';

let thesaurusTermsCache = null;
let thesaurusCategoriesCache = [];
let activeThesaurusCategory = 'all';

/**
 * Prüft beim Absenden einer Suche, ob ein Thesaurus-Begriff zutrifft,
 * und blendet das lilafarbene Informationsbanner ein.
 * @param {string} query
 */
export async function checkAndDisplayThesaurusBanner(query) {
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

/**
 * Öffnet das Nachschlage-Modal für den kirchlichen Thesaurus.
 */
export async function openThesaurusModal() {
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

/**
 * Schließt das Thesaurus-Modal.
 */
export function closeThesaurusModal() {
  const modal = document.getElementById('thesaurus-modal');
  if (modal) modal.classList.add('hidden');
}

/**
 * Lädt Begriffe und Kategorien vom Backend.
 */
export async function loadThesaurusData() {
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

/**
 * Rendert die Kategorie-Reiter (z.B. Liturgie, Sakralbauten, Ämter & Orden).
 */
export function renderThesaurusTabs() {
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

/**
 * Wählt eine Thesaurus-Kategorie aus.
 * @param {string} cat
 */
export function selectThesaurusCategory(cat) {
  activeThesaurusCategory = cat;
  renderThesaurusTabs();
  const input = document.getElementById('thesaurus-filter-input');
  filterThesaurusModal(input ? input.value : '');
}

/**
 * Filtert die Begriffsliste im Modal live nach Benutzereingabe.
 * @param {string} query
 */
export function filterThesaurusModal(query) {
  const clearBtn = document.getElementById('thesaurus-filter-clear');
  const q = (query || '').trim().toLowerCase();

  if (clearBtn) {
    if (q) clearBtn.classList.remove('hidden');
    else clearBtn.classList.add('hidden');
  }

  if (!thesaurusTermsCache) return;

  const filtered = thesaurusTermsCache.filter(item => {
    if (activeThesaurusCategory !== 'all' && item.category !== activeThesaurusCategory) {
      return false;
    }
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

/**
 * Setzt den Filter im Thesaurus-Modal zurück.
 */
export function clearThesaurusFilter() {
  const input = document.getElementById('thesaurus-filter-input');
  if (input) input.value = '';
  filterThesaurusModal('');
  if (input) input.focus();
}

/**
 * Rendert das Begriffsgitter im Thesaurus-Modal.
 * @param {Array<any>} terms
 */
export function renderThesaurusGrid(terms) {
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
            class="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5 cursor-pointer">
            <span>🔍</span>
            <span>In Suche übernehmen</span>
          </button>
        </div>
      </div>`;
  });

  grid.innerHTML = html;
}

/**
 * Übernimmt einen Thesaurus-Begriff in das Suchfeld und startet die Suche.
 * @param {string} term
 */
export function applyThesaurusTermToSearch(term) {
  closeThesaurusModal();
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.value = term;
  }
  if (typeof window.executeSearch === 'function') {
    window.executeSearch(term);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
