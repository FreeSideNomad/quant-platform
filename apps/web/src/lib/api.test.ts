import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';

type FetchCall = [string, RequestInit];

describe('api', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    document.cookie = 'qp_csrf=csrf-fixture; path=/';
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    document.cookie = 'qp_csrf=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    vi.restoreAllMocks();
  });

  it('sends credentials on GET and does not add CSRF header', async () => {
    const mock = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    globalThis.fetch = mock as unknown as typeof fetch;

    await api.get('/api/hello');
    const [, opts] = mock.mock.calls[0] as unknown as FetchCall;
    expect(opts.credentials).toBe('include');
    const headers = opts.headers as Record<string, string>;
    expect(headers['X-CSRF-Token']).toBeUndefined();
  });

  it('adds X-CSRF-Token header on POST', async () => {
    const mock = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    globalThis.fetch = mock as unknown as typeof fetch;

    await api.post('/api/hello', { a: 1 });
    const [, opts] = mock.mock.calls[0] as unknown as FetchCall;
    const headers = opts.headers as Record<string, string>;
    expect(headers['X-CSRF-Token']).toBe('csrf-fixture');
    expect(headers['content-type']).toBe('application/json');
    expect(opts.body).toBe(JSON.stringify({ a: 1 }));
  });

  it('redirects to /auth/login on 401', async () => {
    const mock = vi.fn(async () => new Response('', { status: 401 }));
    globalThis.fetch = mock as unknown as typeof fetch;

    const locationAssign = vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      pathname: '/models',
      search: '',
      href: 'http://localhost/models',
    } as Location);

    await expect(api.get('/api/protected')).rejects.toBeInstanceOf(ApiError);
    locationAssign.mockRestore();
  });

  it('throws ApiError on non-ok non-401', async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ detail: 'bad' }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      })) as unknown as typeof fetch;

    const err = await api.get('/api/bad').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(400);
    expect((err as ApiError).body).toEqual({ detail: 'bad' });
  });
});
