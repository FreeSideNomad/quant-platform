import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { models, type PredictResult } from '@/lib/models';
import { useMe } from '@/lib/auth';
import { ApiError } from '@/lib/api';

export function ModelDetailPage({ modelId }: { modelId: string }) {
  const me = useMe();
  const qc = useQueryClient();

  const detail = useQuery({
    queryKey: ['model', modelId],
    queryFn: () => models.get(modelId),
    enabled: !!me.data,
    refetchInterval: 3_000,
  });

  const log = useQuery({
    queryKey: ['inference-log', modelId],
    queryFn: () => models.inferenceLog(modelId),
    enabled: !!me.data,
    refetchInterval: 5_000,
  });

  const train = useMutation({
    mutationFn: (instruments: string[]) =>
      models.submitTraining({
        model_id: modelId,
        compute_profile: 'local-cpu',
        as_of: '2024-12-31',
        train_start: '2022-01-01',
        train_end: '2024-06-30',
        instruments,
        hyperparameters: {},
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['model', modelId] }),
  });

  const [instrument, setInstrument] = useState('QPX.A');
  const [asOf, setAsOf] = useState('2024-12-31');
  const [prediction, setPrediction] = useState<PredictResult | null>(null);
  const predict = useMutation<PredictResult, ApiError, void>({
    mutationFn: async () => models.predict(modelId, instrument, asOf),
    onSuccess: (r) => {
      setPrediction(r);
      qc.invalidateQueries({ queryKey: ['inference-log', modelId] });
    },
  });

  if (!me.data) return <p style={{ color: 'var(--muted)' }}>Sign in required.</p>;
  if (!detail.data) return <p style={{ color: 'var(--muted)' }}>Loading…</p>;

  const d = detail.data;

  return (
    <section>
      <div className="flex items-baseline justify-between mb-1">
        <h1 className="text-2xl font-medium">{d.name}</h1>
        <span className="text-xs mono" style={{ color: 'var(--muted)' }}>
          {d.algorithm}
        </span>
      </div>
      {d.description && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          {d.description}
        </p>
      )}
      <hr className="my-6" />

      <h2 className="text-sm uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
        Training runs
      </h2>
      {d.training_runs.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No training runs yet.
        </p>
      )}
      {d.training_runs.length > 0 && (
        <table className="w-full text-sm mb-8">
          <thead>
            <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <th className="font-normal text-xs pb-2">Status</th>
              <th className="font-normal text-xs pb-2">Profile</th>
              <th className="font-normal text-xs pb-2">As of</th>
              <th className="font-normal text-xs pb-2">Window</th>
              <th className="font-normal text-xs pb-2 tnum">Val RMSE</th>
              <th className="font-normal text-xs pb-2 tnum">Val IC</th>
              <th className="font-normal text-xs pb-2">Version</th>
            </tr>
          </thead>
          <tbody>
            {d.training_runs.map((r) => {
              const rawMetrics = r.metrics as Record<string, unknown> | undefined;
              const mm = (rawMetrics?.metrics as Record<string, unknown> | undefined) ?? rawMetrics ?? {};
              const vr = mm['val_rmse'];
              const ic = mm['val_ic'];
              const status = r.status;
              const statusColor =
                status === 'completed'
                  ? 'var(--success)'
                  : status === 'failed'
                  ? 'var(--destructive)'
                  : 'var(--warning)';
              return (
                <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="py-2 mono text-xs" style={{ color: statusColor }}>
                    {status}
                  </td>
                  <td className="py-2 mono text-xs">{r.compute_profile}</td>
                  <td className="py-2 mono text-xs">{r.as_of}</td>
                  <td className="py-2 mono text-xs">
                    {r.train_start} → {r.train_end}
                  </td>
                  <td className="py-2 mono text-xs tnum">
                    {typeof vr === 'number' ? vr.toFixed(6) : '—'}
                  </td>
                  <td className="py-2 mono text-xs tnum">
                    {typeof ic === 'number' ? ic.toFixed(4) : '—'}
                  </td>
                  <td className="py-2 mono text-xs">{r.model_version ?? '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <div className="mb-8">
        <button
          onClick={() => train.mutate([])}
          disabled={train.isPending}
          className="px-3 py-1.5 text-sm"
          style={{
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            borderRadius: 'var(--radius)',
          }}
        >
          {train.isPending ? 'Submitting…' : 'Submit new training run'}
        </button>
        {train.isSuccess && (
          <span className="ml-3 text-xs mono" style={{ color: 'var(--muted)' }}>
            queued: {train.data?.training_run_id}
          </span>
        )}
      </div>

      <h2 className="text-sm uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
        Inference
      </h2>
      <form
        className="flex gap-2 mb-4 items-end"
        onSubmit={(e) => {
          e.preventDefault();
          predict.mutate();
        }}
      >
        <label className="flex flex-col text-xs" style={{ color: 'var(--muted)' }}>
          Instrument
          <input
            value={instrument}
            onChange={(e) => setInstrument(e.target.value)}
            className="px-2 py-1 mono text-sm"
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              background: 'var(--surface-1)',
              color: 'var(--fg)',
            }}
          />
        </label>
        <label className="flex flex-col text-xs" style={{ color: 'var(--muted)' }}>
          As of
          <input
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
            className="px-2 py-1 mono text-sm"
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              background: 'var(--surface-1)',
              color: 'var(--fg)',
            }}
          />
        </label>
        <button
          type="submit"
          disabled={predict.isPending}
          className="px-3 py-1.5 text-sm"
          style={{
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            borderRadius: 'var(--radius)',
          }}
        >
          {predict.isPending ? 'Predicting…' : 'Predict'}
        </button>
      </form>
      {prediction && (
        <div
          className="border rounded p-4 mb-8 text-sm"
          style={{
            borderColor: 'var(--border)',
            background: 'var(--surface-2)',
            borderRadius: 'var(--radius)',
          }}
        >
          <dl className="grid grid-cols-4 gap-4">
            <div>
              <dt className="text-xs" style={{ color: 'var(--muted)' }}>
                Prediction
              </dt>
              <dd className="mono tnum">{prediction.prediction.toFixed(6)}</dd>
            </div>
            <div>
              <dt className="text-xs" style={{ color: 'var(--muted)' }}>
                Version
              </dt>
              <dd className="mono">{prediction.model_version}</dd>
            </div>
            <div>
              <dt className="text-xs" style={{ color: 'var(--muted)' }}>
                Latency
              </dt>
              <dd className="mono tnum">{prediction.latency_ms} ms</dd>
            </div>
            <div>
              <dt className="text-xs" style={{ color: 'var(--muted)' }}>
                Feature hash
              </dt>
              <dd className="mono text-xs">{prediction.feature_hash}</dd>
            </div>
          </dl>
        </div>
      )}

      <h2 className="text-sm uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
        Inference log
      </h2>
      {log.data && log.data.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No inferences yet.
        </p>
      )}
      {log.data && log.data.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <th className="font-normal text-xs pb-2">When</th>
              <th className="font-normal text-xs pb-2">Instrument</th>
              <th className="font-normal text-xs pb-2">As of</th>
              <th className="font-normal text-xs pb-2 tnum">Prediction</th>
              <th className="font-normal text-xs pb-2 tnum">Latency</th>
              <th className="font-normal text-xs pb-2">By</th>
            </tr>
          </thead>
          <tbody>
            {log.data.map((e) => (
              <tr key={e.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td className="py-1.5 mono text-xs tnum">
                  {new Date(e.requested_at).toLocaleString()}
                </td>
                <td className="py-1.5 mono">{e.instrument}</td>
                <td className="py-1.5 mono text-xs">{e.as_of_date}</td>
                <td className="py-1.5 mono tnum">{e.prediction.toFixed(6)}</td>
                <td className="py-1.5 mono tnum">{e.latency_ms}ms</td>
                <td
                  className="py-1.5 text-xs mono"
                  style={{ color: 'var(--muted)' }}
                >
                  {e.requested_by ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
