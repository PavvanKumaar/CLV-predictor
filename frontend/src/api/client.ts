// src/api/client.ts

/**
 * Centralized API client for CLV Predictor frontend.
 * The base URL can be configured via the environment variable VITE_API_BASE_URL.
 * In development it defaults to http://127.0.0.1:8001.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001';

/** Request payload shape matching the FastAPI FeatureRequest model */
export interface FeatureRequest {
  recency: number;
  frequency: number;
  T: number;
  avg_order_value: number;
  monetary_std: number;
  purchase_velocity: number;
  interpurchase_time_mean: number;
  interpurchase_time_std: number;
  category_diversity: number;
  category_missing: number;
  tenure_bucket: 'new' | 'established' | 'loyal';
  last_order_recency_ratio: number;
  is_cold_start: boolean;
}

/** Response shape returned by /predict */
export interface PredictResponse {
  prob_purchase: number;
  expected_transactions: number;
  expected_value_per_txn: number;
  predicted_clv_90d: number;
  segment: string;
  is_cold_start: boolean;
  model_version: string;
  note: string;
}

/** Generic helper to handle HTTP errors */
async function handleResponse(response: Response) {
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const message = err.detail || response.statusText || 'API request failed';
    throw new Error(message);
  }
  return response.json();
}

/** POST /predict */
export async function predict(payload: FeatureRequest): Promise<PredictResponse> {
  const resp = await fetch(`${API_BASE_URL}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(resp);
}

/** GET /health */
export async function healthCheck(): Promise<{ status: string; model_version?: string }> {
  const resp = await fetch(`${API_BASE_URL}/health`);
  return handleResponse(resp);
}
