import assert from "node:assert/strict";
import test from "node:test";

import { analyzeCaseWithGemini, buildCaseListQuery } from "../lib/api.ts";

test("buildCaseListQuery omits empty fields", () => {
  const query = buildCaseListQuery({
    risk_bucket: "critical",
    decision: "",
    review_status: "pending",
    page: 2,
    page_size: 10,
  });

  assert.equal(query, "?risk_bucket=critical&review_status=pending&page=2&page_size=10");
});

test("analyzeCaseWithGemini posts to the gemini-analysis endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  let calledUrl = "";
  let calledMethod = "";
  let calledAuth = "";

  process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
  globalThis.fetch = async (input: string | URL | Request, init?: RequestInit) => {
    calledUrl = String(input);
    calledMethod = init?.method ?? "GET";
    calledAuth = new Headers(init?.headers).get("Authorization") ?? "";
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await analyzeCaseWithGemini("token-123", "tx-001");
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBaseUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
    }
  }

  assert.equal(calledUrl, "http://localhost:8000/cases/tx-001/gemini-analysis");
  assert.equal(calledMethod, "POST");
  assert.equal(calledAuth, "Bearer token-123");
});
