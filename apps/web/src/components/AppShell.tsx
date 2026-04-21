import { Link } from '@tanstack/react-router';
import type { PropsWithChildren } from 'react';
import { login, logout, useMe } from '@/lib/auth';

export function AppShell({ children }: PropsWithChildren) {
  const me = useMe();
  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="border-b"
        style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
      >
        <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm" style={{ color: 'var(--muted)' }}>
              QP /
            </span>
            <span className="font-medium">Quant Platform</span>
          </div>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/" className="hover:underline">Overview</Link>
            <Link to="/models" className="hover:underline">Models</Link>
            <AuthControl me={me.data} loading={me.isLoading} />
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 py-8">{children}</div>
      </main>
      <footer
        className="border-t text-xs px-6 py-3"
        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
      >
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="mono">quant-platform · dev</span>
          <span>Reference implementation</span>
        </div>
      </footer>
    </div>
  );
}

function AuthControl({ me, loading }: { me: ReturnType<typeof useMe>['data']; loading: boolean }) {
  if (loading) {
    return <span className="text-xs" style={{ color: 'var(--muted)' }}>…</span>;
  }
  if (!me) {
    return (
      <button
        onClick={login}
        className="px-3 py-1 text-sm rounded"
        style={{
          background: 'var(--accent)',
          color: 'var(--accent-fg)',
          borderRadius: 'var(--radius)',
        }}
      >
        Sign in
      </button>
    );
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs mono" style={{ color: 'var(--muted)' }}>
        {me.email}
      </span>
      {me.roles.includes('admin') && (
        <span
          className="text-[10px] uppercase tracking-wider px-1.5 py-0.5"
          style={{
            background: 'var(--panel)',
            color: 'var(--muted)',
            borderRadius: 'var(--radius)',
          }}
        >
          admin
        </span>
      )}
      <button
        onClick={logout}
        className="text-sm hover:underline"
        style={{ color: 'var(--muted)' }}
      >
        Sign out
      </button>
    </div>
  );
}
