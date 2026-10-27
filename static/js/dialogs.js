/**
 * Dialog-, Modal- und Toast-System für das Historische Bildarchiv
 * Ersetzt native Browser-Dialoge und schützt vor Datenverlust.
 */

let confirmModalResolver = null;
let undoToastTimeout = null;
let currentUndoAction = null;

/**
 * Zeigt einen Toast-Hinweis an (Erfolg oder Fehler).
 * @param {string} msg
 * @param {boolean} [isError=false]
 */
export function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toast-message');
  const toastIcon = document.getElementById('toast-icon');
  if (!toast || !toastMsg) return;

  toastMsg.textContent = msg;

  if (isError) {
    if (toastIcon) {
      toastIcon.className = 'w-6 h-6 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0';
      toastIcon.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
    }
  } else {
    if (toastIcon) {
      toastIcon.className = 'w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0';
      toastIcon.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
    }
  }

  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 4000);
}

/**
 * Zeigt ein modales Bestätigungsfenster an (Promise-basiert).
 * @param {string} [title='Bestätigung erforderlich']
 * @param {string} [message='Möchten Sie diese Aktion wirklich durchführen?']
 * @param {string} [confirmText='Bestätigen']
 * @param {string} [cancelText='Abbrechen']
 * @param {boolean} [isDanger=false]
 * @returns {Promise<boolean>}
 */
export function showConfirmModal(
  title = 'Bestätigung erforderlich',
  message = 'Möchten Sie diese Aktion wirklich durchführen?',
  confirmText = 'Bestätigen',
  cancelText = 'Abbrechen',
  isDanger = false
) {
  return new Promise((resolve) => {
    const modal = document.getElementById('confirm-modal');
    if (!modal) {
      resolve(window.confirm(`${title}\n\n${message}`));
      return;
    }

    confirmModalResolver = resolve;

    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-message');
    const actBtn = document.getElementById('confirm-modal-action');
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    const iconContainer = document.getElementById('confirm-modal-icon-container');

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    if (cancelBtn) cancelBtn.textContent = cancelText;

    if (actBtn) {
      actBtn.textContent = confirmText;
      if (isDanger) {
        actBtn.className = 'px-4 py-1.5 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 transition shadow-sm cursor-pointer';
      } else {
        actBtn.className = 'px-4 py-1.5 rounded-xl text-xs font-semibold text-white bg-amber-600 hover:bg-amber-500 transition shadow-sm cursor-pointer';
      }
    }

    if (iconContainer) {
      if (isDanger) {
        iconContainer.className = 'w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center shrink-0';
      } else {
        iconContainer.className = 'w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0';
      }
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    actBtn?.focus();
  });
}

/**
 * Schließt das Confirm-Modal und löst das Promise auf.
 * @param {boolean} result
 */
export function resolveConfirmModal(result) {
  const modal = document.getElementById('confirm-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
  if (confirmModalResolver) {
    const res = confirmModalResolver;
    confirmModalResolver = null;
    res(result);
  }
}

/**
 * Zeigt einen dezenten Undo-Toast mit Rückgängig-Option an.
 * @param {string} message
 * @param {Function} undoCallback
 * @param {number} [durationMs=8000]
 */
export function showUndoToast(message, undoCallback, durationMs = 8000) {
  const toast = document.getElementById('undo-toast');
  const msgEl = document.getElementById('undo-toast-message');
  const btn = document.getElementById('undo-toast-btn');
  if (!toast || !msgEl) return;

  if (undoToastTimeout) {
    clearTimeout(undoToastTimeout);
    undoToastTimeout = null;
  }

  currentUndoAction = undoCallback;
  msgEl.textContent = message;

  if (undoCallback) {
    btn?.classList.remove('hidden');
  } else {
    btn?.classList.add('hidden');
  }

  toast.classList.remove('hidden');
  toast.classList.add('flex');

  undoToastTimeout = setTimeout(() => {
    dismissUndoToast();
  }, durationMs);
}

/**
 * Blendet den Undo-Toast aus.
 */
export function dismissUndoToast() {
  const toast = document.getElementById('undo-toast');
  if (toast) {
    toast.classList.add('hidden');
    toast.classList.remove('flex');
  }
  if (undoToastTimeout) {
    clearTimeout(undoToastTimeout);
    undoToastTimeout = null;
  }
  currentUndoAction = null;
}

/**
 * Initialisiert Event-Listener für das Confirm-Modal und den Undo-Toast.
 */
export function initConfirmAndUndoModals() {
  const confirmAction = document.getElementById('confirm-modal-action');
  const confirmCancel = document.getElementById('confirm-modal-cancel');
  const confirmModal = document.getElementById('confirm-modal');

  if (confirmAction) {
    confirmAction.addEventListener('click', () => resolveConfirmModal(true));
  }
  if (confirmCancel) {
    confirmCancel.addEventListener('click', () => resolveConfirmModal(false));
  }
  if (confirmModal) {
    confirmModal.addEventListener('click', (e) => {
      if (e.target.id === 'confirm-modal') {
        resolveConfirmModal(false);
      }
    });
  }

  const undoBtn = document.getElementById('undo-toast-btn');
  const undoClose = document.getElementById('undo-toast-close');
  if (undoBtn) {
    undoBtn.addEventListener('click', () => {
      if (currentUndoAction) {
        const action = currentUndoAction;
        dismissUndoToast();
        action();
      }
    });
  }
  if (undoClose) {
    undoClose.addEventListener('click', () => dismissUndoToast());
  }
}
