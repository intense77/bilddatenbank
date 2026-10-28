/**
 * KDG- und DSGVO-konformes Authentifizierungs- und Rollen-Modul (RBAC).
 * Verwaltet den aktuellen Benutzer-Status (Admin, Archivar/Kurator, Lesesaal/Gast),
 * steuert das Anmelde-Modal und schützt interaktive Aktionen.
 */

import { apiFetch } from './api.js';
import { showToast } from './dialogs.js';

export let currentUser = null;

export async function fetchCurrentUser() {
  try {
    const res = await apiFetch('/api/auth/me');
    if (res.ok) {
      currentUser = await res.json();
    } else {
      currentUser = { username: 'lesesaal_gast', role: 'viewer', display_name: 'Lesesaal-Gast' };
    }
  } catch (err) {
    currentUser = { username: 'lesesaal_gast', role: 'viewer', display_name: 'Lesesaal-Gast' };
  }
  updateAuthUI();
  return currentUser;
}

export function updateAuthUI() {
  const badge = document.getElementById('auth-role-badge');
  const roleIcon = document.getElementById('auth-role-icon');
  const roleText = document.getElementById('auth-role-text');
  const actionBtn = document.getElementById('auth-action-btn');

  if (!badge || !roleIcon || !roleText || !actionBtn) return;

  const role = currentUser ? currentUser.role : 'viewer';
  const isAnonymousViewer = !currentUser || currentUser.username === 'lesesaal_gast';

  if (role === 'admin') {
    roleIcon.textContent = '👑';
    roleText.textContent = 'Admin';
    badge.className = 'flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono text-[11px]';
    actionBtn.textContent = 'Abmelden';
    actionBtn.onclick = handleLogoutClick;
  } else if (role === 'curator') {
    roleIcon.textContent = '✍️';
    roleText.textContent = 'Archivar';
    badge.className = 'flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono text-[11px]';
    actionBtn.textContent = 'Abmelden';
    actionBtn.onclick = handleLogoutClick;
  } else {
    roleIcon.textContent = '👤';
    roleText.textContent = 'Lesesaal';
    badge.className = 'flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 font-mono text-[11px]';
    actionBtn.textContent = isAnonymousViewer ? 'Anmelden' : 'Abmelden';
    actionBtn.onclick = isAnonymousViewer ? openAuthModal : handleLogoutClick;
  }

  // Beschränkungen im Lesesaal-Modus anwenden (KDG § 11)
  const isViewer = role === 'viewer';
  const adminElements = document.querySelectorAll('.auth-require-admin');
  adminElements.forEach(el => {
    if (role === 'admin') {
      el.classList.remove('opacity-50', 'pointer-events-none');
      el.removeAttribute('title');
    } else {
      el.classList.add('opacity-50');
      el.setAttribute('title', 'Erfordert Administrator-Rechte');
    }
  });

  const curatorElements = document.querySelectorAll('.auth-require-curator');
  curatorElements.forEach(el => {
    if (role === 'admin' || role === 'curator') {
      el.classList.remove('opacity-50', 'pointer-events-none');
      el.removeAttribute('title');
    } else {
      el.classList.add('opacity-50');
      el.setAttribute('title', 'Erfordert Archivar-Rechte (Anmeldung nötig)');
    }
  });
}

export function openAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;

  const errorEl = document.getElementById('auth-error-msg');
  if (errorEl) errorEl.classList.add('hidden');

  const usernameInput = document.getElementById('auth-username');
  const passwordInput = document.getElementById('auth-password');
  if (usernameInput) usernameInput.value = '';
  if (passwordInput) passwordInput.value = '';

  modal.classList.remove('hidden');
  modal.classList.add('flex');
  if (usernameInput) setTimeout(() => usernameInput.focus(), 50);
}

export function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

export async function handleAuthFormSubmit(event) {
  if (event) event.preventDefault();

  const usernameInput = document.getElementById('auth-username');
  const passwordInput = document.getElementById('auth-password');
  const errorEl = document.getElementById('auth-error-msg');
  const submitBtn = document.getElementById('auth-submit-btn');

  const username = usernameInput ? usernameInput.value.trim() : '';
  const password = passwordInput ? passwordInput.value : '';

  if (!username || !password) {
    if (errorEl) {
      errorEl.textContent = 'Bitte Benutzername und Passwort eingeben.';
      errorEl.classList.remove('hidden');
    }
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Wird angemeldet...';
  }

  try {
    const res = await apiFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Anmeldung fehlgeschlagen.');
    }

    const data = await res.json();
    currentUser = data.user;
    updateAuthUI();
    closeAuthModal();

    showToast(`Erfolgreich angemeldet als ${currentUser.display_name} (${currentUser.role.toUpperCase()})`, 'info');

    // Aktualisiere Ansicht (z. B. Cluster und Gesichter-Berechtigungen neu laden)
    if (window.loadClusters) {
      window.loadClusters(false);
    }
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = err.message || 'Ungültige Anmeldedaten.';
      errorEl.classList.remove('hidden');
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Anmelden';
    }
  }
}

export async function handleLogoutClick() {
  try {
    await apiFetch('/api/auth/logout', { method: 'POST' });
  } catch (err) {
    console.debug('Logout request failed:', err);
  }
  currentUser = { username: 'lesesaal_gast', role: 'viewer', display_name: 'Lesesaal-Gast' };
  updateAuthUI();
  showToast('Erfolgreich abgemeldet. Lesesaal-Modus aktiv.', 'info');

  if (window.loadClusters) {
    window.loadClusters(false);
  }
}

export function fillQuickAuth(username, password) {
  const usernameInput = document.getElementById('auth-username');
  const passwordInput = document.getElementById('auth-password');
  if (usernameInput) usernameInput.value = username;
  if (passwordInput) passwordInput.value = password;
  handleAuthFormSubmit();
}
