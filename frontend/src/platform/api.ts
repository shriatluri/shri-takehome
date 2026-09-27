const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// The signed-in employee, set by the identity provider. Stands in for the
// bearer token a real client would attach.
let demoUserId: number | null = null;

export function setDemoUser(id: number | null) {
  demoUserId = id;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (demoUserId !== null) {
    headers.set("X-Demo-User", String(demoUserId));
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string): Promise<T> {
  return request<T>(path, { method: "POST" });
}

export type Employee = {
  id: number;
  name: string;
  team: string;
  level: string;
};

export type Case = {
  id: number;
  status: string;
  risk_score: number;
  assigned_to_name: string | null;
  customer_id: number;
  customer_name: string;
  country: string;
  ssn: string;
  account_status: string;
};

export type AuditEntry = {
  id: number;
  timestamp: string;
  employee_name: string | null;
  action: string;
  record_type: string;
  record_id: string | null;
  hash: string;
};
