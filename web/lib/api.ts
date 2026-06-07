import type {
  AnalystDecisionPayload,
  CaseDetailResponse,
  CaseListFilters,
  CaseListResponse,
  FeedbackPayload,
  LoginResponse,
  MetricsSummaryResponse,
  MonitoringSummaryResponse,
  ScoreRequestPayload,
} from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

export function buildCaseListQuery(filters: CaseListFilters): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  try {
    detail = await response.json();
  } catch {
    detail = await response.text();
  }

  const message =
    typeof detail === "string"
      ? detail
      : typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : undefined;
  return new ApiError(response.status, detail, message);
}

async function request<TResponse>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<TResponse> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (init.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as TResponse;
}

export function loginRequest(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function scoreCase(token: string, payload: ScoreRequestPayload): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>("/score", {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function listCases(token: string, filters: CaseListFilters): Promise<CaseListResponse> {
  return request<CaseListResponse>(`/cases${buildCaseListQuery(filters)}`, { token });
}

export function getCaseDetail(token: string, transactionId: string): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(transactionId)}`, { token });
}

export function submitDecision(
  token: string,
  transactionId: string,
  payload: AnalystDecisionPayload,
): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(transactionId)}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function rescoreCase(token: string, transactionId: string): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(transactionId)}/rescore`, {
    method: "POST",
    token,
  });
}

export function submitFeedback(
  token: string,
  transactionId: string,
  payload: FeedbackPayload,
): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(transactionId)}/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function analyzeCaseWithGemini(token: string, transactionId: string): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(transactionId)}/gemini-analysis`, {
    method: "POST",
    token,
  });
}

export function getMetricsSummary(token: string): Promise<MetricsSummaryResponse> {
  return request<MetricsSummaryResponse>("/metrics/summary", { token });
}

export function getMonitoringSummary(token: string): Promise<MonitoringSummaryResponse> {
  return request<MonitoringSummaryResponse>("/monitoring/summary", { token });
}
