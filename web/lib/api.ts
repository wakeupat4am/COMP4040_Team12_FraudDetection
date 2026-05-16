import { CaseDetail, MetricsSummary, QueueResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch(buildUrl("/health"), { cache: "no-store" });
  return parseResponse(response);
}

export async function getCases(params: Record<string, string | number | undefined>): Promise<QueueResponse> {
  const response = await fetch(buildUrl("/cases", params), { cache: "no-store" });
  return parseResponse(response);
}

export async function getCaseDetail(eventId: string): Promise<CaseDetail> {
  const response = await fetch(buildUrl(`/cases/${eventId}`), { cache: "no-store" });
  return parseResponse(response);
}

export async function getMetrics(): Promise<MetricsSummary> {
  const response = await fetch(buildUrl("/metrics/summary"), { cache: "no-store" });
  return parseResponse(response);
}

export async function submitDecision(payload: {
  event_id: string;
  analyst_decision: "allow" | "review" | "block";
  note: string;
}) {
  const response = await fetch(buildUrl(`/cases/${payload.event_id}/decision`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function rescoreCase(eventId: string) {
  const response = await fetch(buildUrl(`/score/rescore/${eventId}`), {
    method: "POST",
  });
  return parseResponse(response);
}
