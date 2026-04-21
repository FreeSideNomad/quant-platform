/**
 * Fetch wrapper for the quant platform frontend.
 *
 * Security posture:
 *  - always sends cookies (credentials: 'include') so the __Host- session
 *    cookie accompanies the request
 *  - on mutating methods, echoes the qp_csrf cookie value as X-CSRF-Token
 *    (double-submit defence that the BFF enforces server-side)
 *  - on 401, triggers a full-page redirect to /auth/login?return_to=...
 *    — the SPA does not try to handle auth in-place; the BFF's redirect
 *    chain is the source of truth
 */

const CSRF_COOKIE = 'qp_csrf';
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function redirectToLogin(): void {
  const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/auth/login?return_to=${returnTo}`;
}

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: unknown) {
    super(`api error ${status}`);
  }
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = {
    accept: 'application/json',
    ...(options.headers ?? {}),
  };

  if (MUTATING.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers['X-CSRF-Token'] = csrf;
    if (options.body !== undefined && !headers['content-type']) {
      headers['content-type'] = 'application/json';
    }
  }

  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });

  if (response.status === 401) {
    redirectToLogin();
    throw new ApiError(401, null);
  }

  const contentType = response.headers.get('content-type') ?? '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) throw new ApiError(response.status, payload);
  return payload as T;
}

export const api = {
  get: <T>(path: string, init?: Omit<ApiOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...init, method: 'GET' }),
  post: <T>(path: string, body?: unknown, init?: Omit<ApiOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...init, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, init?: Omit<ApiOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...init, method: 'PUT', body }),
  delete: <T>(path: string, init?: Omit<ApiOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...init, method: 'DELETE' }),
};
