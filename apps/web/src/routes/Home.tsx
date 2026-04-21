import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { useMe } from '@/lib/auth';

type Health = { status: string; role: string; version: string };
type PingResult = { event_id: string; enqueued_message_id: number };
type Ping = { event_id: string; message: string; projected_at: string };

export function HomePage() {
  const me = useMe();

  const health = useQuery<Health>({
    queryKey: ['health'],
    queryFn: () => api.get<Health>('/api/internal/health'),
    refetchInterval: 5_000,
  });

  const pings = useQuery<Ping[]>({
    queryKey: ['pings'],
    queryFn: () => api.get<Ping[]>('/api/queries/pings'),
    enabled: !!me.data,
  });

  const [message, setMessage] = useState('hello quant-platform');
  const send = useMutation<PingResult, ApiError, string>({
    mutationFn: (msg) => api.post<PingResult>('/api/commands/ping', { message: msg }),
    onSuccess: () => pings.refetch(),
  });

  return (
    <section>
      <h1 className="text-2xl font-medium mb-1">Overview</h1>
      <p className="text-sm" style={{ color: 'var(--muted)' }}>
        Reference implementation. Health is polled; the ping command exercises the CQRS path
        through the BFF, the API, PGMQ, and the projector.
      </p>
      <hr className="my-6" />

      <dl className="grid grid-cols-3 gap-6 text-sm mb-10">
        <div>
          <dt style={{ color: 'var(--muted)' }}>API status</dt>
          <dd className="mono mt-1">
            {health.isLoading && '…'}
            {health.error && <span style={{ color: 'var(--destructive)' }}>unreachable</span>}
            {health.data && health.data.status}
          </dd>
        </div>
        <div>
          <dt style={{ color: 'var(--muted)' }}>Role</dt>
          <dd className="mono mt-1">{health.data?.role ?? '—'}</dd>
        </div>
        <div>
          <dt style={{ color: 'var(--muted)' }}>Version</dt>
          <dd className="mono mt-1">{health.data?.version ?? '—'}</dd>
        </div>
      </dl>

      {me.data ? (
        <>
          <h2 className="text-sm uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
            Ping
          </h2>
          <form
            className="flex gap-2 mb-6"
            onSubmit={(e) => {
              e.preventDefault();
              send.mutate(message);
            }}
          >
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="flex-1 px-3 py-1.5 text-sm"
              style={{
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                background: 'var(--surface-1)',
              }}
            />
            <button
              type="submit"
              disabled={send.isPending}
              className="px-4 py-1.5 text-sm"
              style={{
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                borderRadius: 'var(--radius)',
              }}
            >
              {send.isPending ? 'Sending…' : 'Send'}
            </button>
          </form>

          <h2 className="text-sm uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
            Recent pings
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
                <th className="font-normal text-xs pb-1.5">event_id</th>
                <th className="font-normal text-xs pb-1.5">message</th>
                <th className="font-normal text-xs pb-1.5 tnum">at</th>
              </tr>
            </thead>
            <tbody>
              {(pings.data ?? []).map((p) => (
                <tr key={p.event_id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="mono text-xs py-1.5">{p.event_id.slice(0, 8)}…</td>
                  <td className="py-1.5">{p.message}</td>
                  <td className="mono text-xs tnum py-1.5">
                    {new Date(p.projected_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {pings.data && pings.data.length === 0 && (
                <tr>
                  <td
                    colSpan={3}
                    className="py-8 text-center text-sm"
                    style={{ color: 'var(--muted)' }}
                  >
                    No pings yet — send one above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      ) : (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Sign in to interact with the platform.
        </p>
      )}
    </section>
  );
}
