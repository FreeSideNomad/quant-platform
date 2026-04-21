import { Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { models } from '@/lib/models';
import { useMe } from '@/lib/auth';

export function ModelsPage() {
  const me = useMe();
  const q = useQuery({
    queryKey: ['models'],
    queryFn: models.list,
    enabled: !!me.data,
  });

  return (
    <section>
      <h1 className="text-2xl font-medium mb-1">Models</h1>
      <p className="text-sm" style={{ color: 'var(--muted)' }}>
        Registered models. Click through for training runs, model versions, and inference.
      </p>
      <hr className="my-6" />

      {!me.data && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Sign in to view registered models.
        </p>
      )}

      {me.data && q.isLoading && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Loading…
        </p>
      )}

      {me.data && q.data && q.data.length === 0 && (
        <div
          className="border rounded px-4 py-10 text-center text-sm"
          style={{
            borderColor: 'var(--border)',
            background: 'var(--panel)',
            color: 'var(--muted)',
            borderRadius: 'var(--radius)',
          }}
        >
          No models yet.
        </div>
      )}

      {me.data && q.data && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <th className="font-normal text-xs pb-2">Name</th>
              <th className="font-normal text-xs pb-2">Algorithm</th>
              <th className="font-normal text-xs pb-2">Prod version</th>
              <th className="font-normal text-xs pb-2">Last run</th>
              <th className="font-normal text-xs pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((m) => (
              <tr key={m.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td className="py-2">
                  <div className="font-medium">{m.name}</div>
                  {m.description && (
                    <div className="text-xs" style={{ color: 'var(--muted)' }}>
                      {m.description}
                    </div>
                  )}
                </td>
                <td className="py-2 mono text-xs">{m.algorithm}</td>
                <td className="py-2 mono text-xs">{m.production_version ?? '—'}</td>
                <td className="py-2 mono text-xs">
                  {m.last_run_status ?? '—'}
                  {m.last_run_at && (
                    <div style={{ color: 'var(--muted)' }}>
                      {new Date(m.last_run_at).toLocaleString()}
                    </div>
                  )}
                </td>
                <td className="py-2 text-right">
                  <Link
                    to="/models/$modelId"
                    params={{ modelId: m.id }}
                    style={{ color: 'var(--accent)' }}
                    className="hover:underline"
                  >
                    Detail →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
