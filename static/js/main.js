/**
 * Historisches Bildarchiv - Haupt-Einstiegspunkt (ES6 Modul-Architektur)
 * Orchestriert Submodule (api, dialogs, utils, thesaurus, lightbox, network)
 * und stellt die Window-Bridge für vollständige HTML-Abwärtskompatibilität bereit.
 */

import { api, apiFetch } from './api.js';
import {
  showToast,
  showConfirmModal,
  resolveConfirmModal,
  showUndoToast,
  dismissUndoToast,
  initConfirmAndUndoModals
} from './dialogs.js';
import {
  escapeHtml,
  formatBytes,
  debounce,
  triggerFileDownload
} from './utils.js';
import {
  openThesaurusModal,
  closeThesaurusModal,
  selectThesaurusCategory,
  filterThesaurusModal,
  clearThesaurusFilter,
  applyThesaurusTermToSearch,
  checkAndDisplayThesaurusBanner
} from './thesaurus.js';
import {
  loadLightboxState,
  saveLightboxState,
  updateLightboxBadge,
  isItemInLightbox,
  addToLightbox,
  removeFromLightbox,
  toggleLightboxItem,
  toggleLightboxCard,
  addAllCurrentResultsToLightbox,
  updateModalLightboxButtonState,
  toggleCurrentModalLightbox,
  handleLightboxTitleChange,
  copyLightboxPaths,
  clearLightboxConfirm,
  updateLightboxItemNote,
  renderLightboxView,
  rotateLightboxCardImage,
  openPdfExportModal,
  closePdfExportModal,
  handlePdfExportSubmit,
  exportLightboxFindbuchCsv,
  exportLightboxEadXml,
  exportLightboxLidoXml
} from './lightbox.js';
import {
  initNetworkTab,
  reloadNetworkGraph,
  renderNetworkGraph,
  showNetworkNodeCard,
  closeNetworkNodeCard,
  centerNetworkOnSelectedNode,
  openClusterFromNetworkCard,
  filterSharedFromNetworkCard,
  fitNetworkGraph,
  toggleNetworkPhysics,
  loadClusterCoOccurrences,
  filterClusterSharedImages,
  clearClusterSharedFilter,
  jumpToCluster,
  openNetworkForActiveCluster,
  handleNetworkPersonChange
} from './network.js';

// --- Window-Bridge für 100%ige Abwärtskompatibilität mit HTML onclick/onchange Attributen ---

window.api = api;
window.apiFetch = apiFetch;

// Dialoge & Benachrichtigungen
window.showToast = showToast;
window.showConfirmModal = showConfirmModal;
window.resolveConfirmModal = resolveConfirmModal;
window.showUndoToast = showUndoToast;
window.dismissUndoToast = dismissUndoToast;
window.initConfirmAndUndoModals = initConfirmAndUndoModals;

// Utilities
window.escapeHtml = escapeHtml;
window.formatBytes = formatBytes;
window.debounce = debounce;
window.triggerFileDownload = triggerFileDownload;

// Kirchlicher Thesaurus
window.openThesaurusModal = openThesaurusModal;
window.closeThesaurusModal = closeThesaurusModal;
window.selectThesaurusCategory = selectThesaurusCategory;
window.filterThesaurusModal = filterThesaurusModal;
window.clearThesaurusFilter = clearThesaurusFilter;
window.applyThesaurusTermToSearch = applyThesaurusTermToSearch;
window.checkAndDisplayThesaurusBanner = checkAndDisplayThesaurusBanner;

// Digitaler Leuchttisch & Export
window.loadLightboxState = loadLightboxState;
window.saveLightboxState = saveLightboxState;
window.updateLightboxBadge = updateLightboxBadge;
window.isItemInLightbox = isItemInLightbox;
window.addToLightbox = addToLightbox;
window.removeFromLightbox = removeFromLightbox;
window.toggleLightboxItem = toggleLightboxItem;
window.toggleLightboxCard = toggleLightboxCard;
window.addAllCurrentResultsToLightbox = addAllCurrentResultsToLightbox;
window.updateModalLightboxButtonState = updateModalLightboxButtonState;
window.toggleCurrentModalLightbox = toggleCurrentModalLightbox;
window.handleLightboxTitleChange = handleLightboxTitleChange;
window.copyLightboxPaths = copyLightboxPaths;
window.clearLightboxConfirm = clearLightboxConfirm;
window.updateLightboxItemNote = updateLightboxItemNote;
window.renderLightboxView = renderLightboxView;
window.rotateLightboxCardImage = rotateLightboxCardImage;
window.openPdfExportModal = openPdfExportModal;
window.closePdfExportModal = closePdfExportModal;
window.handlePdfExportSubmit = handlePdfExportSubmit;
window.exportLightboxFindbuchCsv = exportLightboxFindbuchCsv;
window.exportLightboxEadXml = exportLightboxEadXml;
window.exportLightboxLidoXml = exportLightboxLidoXml;

// Personen-Netzwerk
window.initNetworkTab = initNetworkTab;
window.reloadNetworkGraph = reloadNetworkGraph;
window.renderNetworkGraph = renderNetworkGraph;
window.showNetworkNodeCard = showNetworkNodeCard;
window.closeNetworkNodeCard = closeNetworkNodeCard;
window.centerNetworkOnSelectedNode = centerNetworkOnSelectedNode;
window.openClusterFromNetworkCard = openClusterFromNetworkCard;
window.filterSharedFromNetworkCard = filterSharedFromNetworkCard;
window.fitNetworkGraph = fitNetworkGraph;
window.toggleNetworkPhysics = toggleNetworkPhysics;
window.loadClusterCoOccurrences = loadClusterCoOccurrences;
window.filterClusterSharedImages = filterClusterSharedImages;
window.clearClusterSharedFilter = clearClusterSharedFilter;
window.jumpToCluster = jumpToCluster;
window.openNetworkForActiveCluster = openNetworkForActiveCluster;
window.handleNetworkPersonChange = handleNetworkPersonChange;

console.info('ArchiveApp ES6 Core Modules erfolgreich initialisiert.');
