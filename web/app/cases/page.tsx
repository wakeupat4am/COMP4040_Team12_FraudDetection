"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { StatusPill } from "@/components/status-pill";
import { ApiError, listCases } from "@/lib/api";
import { formatDateTime, formatScore } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { CaseListFilters, CaseListResponse } from "@/lib/types";

const DEFAULT_FILTERS: CaseListFilters = {
  page: 1,
  page_size: 10,
  risk_bucket: "",
  decision: "",
  review_status: "",
  created_from: "",
  created_to: "",
};

export default function CasesPage() {
  const { run } = useAuthedRequest();
  const [filters, setFilters] = useState<CaseListFilters>(DEFAULT_FILTERS);
  const [activeFilters, setActiveFilters] = useState<CaseListFilters>(DEFAULT_FILTERS);
  const [data, setData] = useState<CaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCases() {
      setLoading(true);
      setError(null);
      try {
        const response = await run((token) => listCases(token, activeFilters));
        if (!cancelled) {
          setData(response);
        }
      } catch (caughtError) {
        if (!cancelled) {
          if (caughtError instanceof ApiError) {
            setError(caughtError.message);
          } else {
            setError(caughtError instanceof Error ? caughtError.message : "Unable to load cases.");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCases();
    return () => {
      cancelled = true;
    };
  }, [activeFilters, run]);

  function updateFilter(key: keyof CaseListFilters, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveFilters({ ...filters, page: 1 });
  }

  function changePage(nextPage: number) {
    setFilters((current) => ({ ...current, page: nextPage }));
    setActiveFilters((current) => ({ ...current, page: nextPage }));
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <GuardedPage
      title="Analyst Case Queue"
      description="Filter the case backlog by routing outcome, review state, and time window before drilling into a single transaction."
    >
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Queue filters</h3>
            <p>Keep the queue lightweight here and pull full case detail only when you open an individual transaction.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={applyFilters}>
          <div className="field-group">
            <label htmlFor="risk_bucket">Risk Bucket</label>
            <select
              id="risk_bucket"
              className="select-input"
              value={String(filters.risk_bucket ?? "")}
              onChange={(event) => updateFilter("risk_bucket", event.target.value)}
            >
              <option value="">All</option>
              <option value="low">Low</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="decision">Decision</label>
            <select
              id="decision"
              className="select-input"
              value={String(filters.decision ?? "")}
              onChange={(event) => updateFilter("decision", event.target.value)}
            >
              <option value="">All</option>
              <option value="allow">Allow</option>
              <option value="review">Review</option>
              <option value="block">Block</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="review_status">Review Status</label>
            <select
              id="review_status"
              className="select-input"
              value={String(filters.review_status ?? "")}
              onChange={(event) => updateFilter("review_status", event.target.value)}
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="reviewed">Reviewed</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="page_size">Page Size</label>
            <select
              id="page_size"
              className="select-input"
              value={String(filters.page_size ?? 10)}
              onChange={(event) => updateFilter("page_size", Number(event.target.value))}
            >
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="50">50</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="created_from">Created From</label>
            <input
              id="created_from"
              className="text-input"
              type="datetime-local"
              value={String(filters.created_from ?? "")}
              onChange={(event) => updateFilter("created_from", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="created_to">Created To</label>
            <input
              id="created_to"
              className="text-input"
              type="datetime-local"
              value={String(filters.created_to ?? "")}
              onChange={(event) => updateFilter("created_to", event.target.value)}
            />
          </div>
          <div className="button-row">
            <button type="submit" className="primary-button">
              Apply Filters
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setFilters(DEFAULT_FILTERS);
                setActiveFilters(DEFAULT_FILTERS);
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="toolbar">
          <div>
            <h3>Queue results</h3>
            <p>{data ? `${data.total} case(s) matched the current filters.` : "Loading queue state."}</p>
          </div>
          <div className="button-row">
            <button
              type="button"
              className="ghost-button"
              disabled={loading || (data?.page ?? 1) <= 1}
              onClick={() => changePage((data?.page ?? 1) - 1)}
            >
              Previous
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={loading || (data?.page ?? 1) >= totalPages}
              onClick={() => changePage((data?.page ?? 1) + 1)}
            >
              Next
            </button>
          </div>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}
        {loading ? <p>Loading cases...</p> : null}
        {!loading && data && data.items.length === 0 ? (
          <EmptyState
            title="No cases matched these filters"
            description="Try a wider date range or reset the decision and review-status filters."
          />
        ) : null}

        {!loading && data && data.items.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Fraud Score</th>
                  <th>Risk Bucket</th>
                  <th>Decision</th>
                  <th>Review Status</th>
                  <th>Last Scored</th>
                  <th>Latest Note</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.transaction_id}>
                    <td>
                      <Link className="table-link" href={`/cases/${encodeURIComponent(item.transaction_id)}`}>
                        {item.transaction_id}
                      </Link>
                    </td>
                    <td>{formatScore(item.final_risk_score)}</td>
                    <td>
                      <StatusPill value={item.risk_bucket} />
                    </td>
                    <td>
                      <StatusPill value={item.decision} />
                    </td>
                    <td>
                      <StatusPill value={item.review_status} />
                    </td>
                    <td>{formatDateTime(item.last_scored_at)}</td>
                    <td>{item.latest_note ?? "No analyst note yet."}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </GuardedPage>
  );
}
