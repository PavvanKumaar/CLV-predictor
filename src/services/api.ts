```typescript
const API_BASE_URL = "/api";

export interface Customer {
  customer_id: string;
}

export interface PurchasePrediction {
  customer_id: string;
  model_version: string;
  snapshot_id: string;
  prob_purchase: number;
  is_cold_start: boolean;
}

export interface CLVPrediction {
  customer_id: string;
  model_version: string;
  snapshot_id: string;
  prob_purchase: number;
  expected_transactions: number;
  expected_value_per_txn: number;
  predicted_clv_90d: number;
  segment: string;
  is_cold_start: boolean;
  predicted_at?: string | null;
}

export interface CLVSummary {
  model_version: string | null;
  count: number;
  total_predicted_clv: number;
  average_predicted_clv: number;
  average_purchase_probability: number;
  average_expected_transactions: number;
  cold_start_count: number;
  cold_start_share: number;
  segments: Record<string, number>;
  message?: string;
  note?: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}): ${path}`
    );
  }

  return response.json() as Promise<T>;
}

export function getCustomers(limit = 50, offset = 0) {
  return getJSON<Customer[]>(
    `/customers?limit=${limit}&offset=${offset}`
  );
}

export function getPurchasePredictions(limit = 50, offset = 0) {
  return getJSON<PurchasePrediction[]>(
    `/stage1/predictions?limit=${limit}&offset=${offset}`
  );
}

export function getCLVPredictions(limit = 50, offset = 0) {
  return getJSON<CLVPrediction[]>(
    `/clv/predictions?limit=${limit}&offset=${offset}`
  );
}

export function getCLVSummary() {
  return getJSON<CLVSummary>("/clv/summary");
}

export function getModelStatus() {
  return getJSON<Record<string, unknown>>("/model/status");
}
```