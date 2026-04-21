import { api } from './api';

export interface Model {
  id: string;
  name: string;
  description: string | null;
  algorithm: string;
  owner_email: string | null;
  created_at: string;
  updated_at: string;
  production_version: string | null;
  last_run_status: string | null;
  last_run_at: string | null;
}

export interface TrainingRun {
  id: string;
  model_id: string;
  mlflow_run_id: string | null;
  status: string;
  compute_profile: string;
  as_of: string;
  train_start: string;
  train_end: string;
  instruments: string[];
  hyperparameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  artefact_uri: string | null;
  model_version: string | null;
  started_at: string;
  completed_at: string | null;
  submitted_by: string | null;
  error: string | null;
}

export interface ModelVersion {
  id: string;
  model_id: string;
  training_run_id: string;
  version: string;
  stage: string;
  mlflow_model_version: string | null;
  created_at: string;
  promoted_at: string | null;
  metrics: Record<string, unknown>;
}

export interface ModelDetail extends Model {
  training_runs: TrainingRun[];
  versions: ModelVersion[];
}

export interface InferenceLogEntry {
  id: string;
  model_id: string;
  model_version: string;
  instrument: string;
  as_of_date: string;
  prediction: number;
  latency_ms: number;
  requested_by: string | null;
  requested_at: string;
}

export interface TrainingSubmission {
  model_id: string;
  compute_profile: 'local-cpu' | 'local-gpu' | 'cloud-cpu' | 'cloud-gpu';
  as_of: string;
  train_start: string;
  train_end: string;
  instruments: string[];
  hyperparameters: Record<string, unknown>;
}

export interface PredictResult {
  instrument: string;
  as_of: string;
  prediction: number;
  model_version: string;
  feature_hash: string;
  latency_ms: number;
  inference_id: string;
}

export const models = {
  list: () => api.get<Model[]>('/api/models'),
  get: (id: string) => api.get<ModelDetail>(`/api/models/${id}`),
  submitTraining: (sub: TrainingSubmission) =>
    api.post<{ training_run_id: string; status: string }>('/api/training/submit', sub),
  predict: (modelName: string, instrument: string, asOf: string) =>
    api.post<PredictResult>(`/api/serving/${modelName}/predict`, {
      instrument,
      as_of: asOf,
    }),
  inferenceLog: (id: string, limit = 50) =>
    api.get<InferenceLogEntry[]>(`/api/models/${id}/inference-log?limit=${limit}`),
};
