/**
 * API-Client für das Historische Bildarchiv
 * Einheitliche Fetch-Logik mit Fehlerbehandlung, Timeout und JSON-Verarbeitung
 */

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Führt einen HTTP-Request durch und parst die JSON-Antwort.
 * @param {string} url - Ziel-URL
 * @param {RequestInit} [options={}] - Standard Fetch-Optionen
 * @param {number} [timeoutMs=30000] - Timeout in Millisekunden
 * @returns {Promise<any>}
 */
export async function apiFetch(url, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const mergedOptions = {
    ...options,
    signal: controller.signal,
    headers: {
      'Accept': 'application/json',
      ...(options.headers || {}),
    },
  };

  try {
    const res = await fetch(url, mergedOptions);
    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorDetail = null;
      let errorMsg = `Server-Fehler (${res.status} ${res.statusText})`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errorDetail = errJson.detail;
          errorMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch (_) {
        // Nicht-JSON Fehlerausgabe
      }
      throw new ApiError(errorMsg, res.status, errorDetail);
    }

    // Leere Antwort (204 No Content)
    if (res.status === 204) {
      return null;
    }

    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError('Zeitüberschreitung der Netzwerkanfrage (Timeout).', 408);
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(`Netzwerkfehler: ${err.message}`, 0);
  }
}

/**
 * Bequeme Hilfsmethoden
 */
export const api = {
  get: (url, options = {}) => apiFetch(url, { ...options, method: 'GET' }),
  post: (url, body, options = {}) => apiFetch(url, {
    ...options,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }),
  delete: (url, options = {}) => apiFetch(url, { ...options, method: 'DELETE' }),
};
