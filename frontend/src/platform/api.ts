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
    // FastAPI puts the reason in `detail`; showing it is the difference between
    // "403" and "the person who recommended cannot also approve".
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    throw new ApiError(response.status, detail ?? `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  if (body === undefined) {
    return request<T>(path, { method: "POST" });
  }
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
  assigned_to: number | null;
  assigned_to_name: string | null;
  customer_id: number;
  customer_name: string;
  country: string;
  ssn: string;
  account_status: string;
};

export type RiskReason = { reason: string; points: number };

export type CaseDetail = Case & {
  risk_reasons: RiskReason[];
  policy_snapshot: Record<string, { value: string; version: number }>;
  recommended_by: number | null;
  recommended_by_name: string | null;
  recommendation: string | null;
  approved_by: number | null;
  approved_by_name: string | null;
  decision_reason: string | null;
  created_at: string;
  decided_at: string | null;
  dob: string;
  address: string;
  document_expiry: string | null;
  document_quality: string | null;
  idv_status: string;
  idv_reason: string | null;
  sanctions_match_name: string | null;
  sanctions_program: string | null;
};

export type Reviewer = { id: number; name: string; level: string };

export type AuditEntry = {
  id: number;
  timestamp: string;
  employee_id: number | null;
  employee_name: string | null;
  action: string;
  record_type: string;
  record_id: string | null;
  details: Record<string, unknown>;
  prev_hash: string | null;
  hash: string;
};

export type AuditFacets = { actions: string[]; record_types: string[] };

export type AuditVerification = {
  intact: boolean;
  broken_at: number | null;
  checked: number;
};

export type PolicyRule = {
  id: number;
  rule_name: string;
  value: string;
  version: number;
  valid_from: string;
  valid_to: string | null;
  changed_by: number | null;
  changed_by_name: string | null;
};
