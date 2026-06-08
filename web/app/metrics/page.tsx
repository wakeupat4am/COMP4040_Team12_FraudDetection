"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { ApiError, getMetricsSummary, getMonitoringSummary } from "@/lib/api";
import { formatDateTime, formatScore, titleCase } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { MetricsSummaryResponse, MonitoringSummaryResponse } from "@/lib/types";

export default function MetricsPage() {
  const { run } = useAuthedRequest();
  const [metrics, setMetrics] = useState<MetricsSummaryResponse | null>(null);
  const [monitoring, setMonitoring] = useState<MonitoringSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadMetrics() {
      setLoading(true);
      setError(null);
      try {
        const [metricsResponse, monitoringResponse] = await Promise.all([
          run((token) => getMetricsSummary(token)),
          run((token) => getMonitoringSummary(token)),
        ]);
        if (!cancelled) {
          setMetrics(metricsResponse);
          setMonitoring(monitoringResponse);
        }
      } catch (caughtError) {
        if (!cancelled) {
          if (caughtError instanceof ApiError) {
            setError(caughtError.message);
          } else {
            setError(caughtError instanceof Error ? caughtError.message : "Unable to load metrics.");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [run]);

  return (
    <GuardedPage
      title="Metrics"
      description="View queue state and backend telemetry from the same signed-in dashboard."
    >
      {error ? <div className="error-banner">{error}</div> : null}
      {loading ? <section className="panel"><p>Loading metrics...</p></section> : null}
      {!loading && (!metrics || !monitoring) ? (
        <EmptyState title="Metrics unavailable" description="The backend did not return a metrics payload for this session." />
      ) : null}

      {metrics && monitoring ? (
        <>
          <section className="metric-grid">
            <div className="metric-card">
              <span className="eyebrow">Total Cases</span>
              <strong>{metrics.total_cases}</strong>
            </div>
            <div className="metric-card">
              <span className="eyebrow">Average Fraud Score</span>
              <strong>{formatScore(metrics.average_final_risk_score)}</strong>
            </div>
            <div className="metric-card">
              <span className="eyebrow">Pending Review</span>
              <strong>{metrics.pending_review_cases}</strong>
            </div>
          </section>

          <section className="split-grid">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Case distribution</h3>
                  <p>Queue state aggregated from the workflow database.</p>
                </div>
              </div>
              <div className="metric-grid">
                <div className="metric-card">
                  <span className="eyebrow">Risk Buckets</span>
                  <ul className="bullet-list">
                    {Object.entries(metrics.risk_bucket_counts).map(([key, value]) => (
                      <li key={key}>
                        {titleCase(key)}: {value}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="metric-card">
                  <span className="eyebrow">Decision Counts</span>
                  <ul className="bullet-list">
                    {Object.entries(metrics.decision_counts).map(([key, value]) => (
                      <li key={key}>
                        {titleCase(key)}: {value}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="metric-card">
                  <span className="eyebrow">Review Status</span>
                  <ul className="bullet-list">
                    {Object.entries(metrics.review_status_counts).map(([key, value]) => (
                      <li key={key}>
                        {titleCase(key)}: {value}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Monitoring summary</h3>
                  <p>Score and rescore telemetry recorded by the backend during Milestone 4.</p>
                </div>
              </div>
              <div className="metric-grid">
                <div className="metric-card">
                  <span className="eyebrow">Total Events</span>
                  <strong>{monitoring.total_events}</strong>
                </div>
                <div className="metric-card">
                  <span className="eyebrow">Average Latency</span>
                  <strong>{monitoring.average_latency_ms.toFixed(1)} ms</strong>
                </div>
                <div className="metric-card">
                  <span className="eyebrow">Latest Event</span>
                  <strong style={{ fontSize: "1.1rem" }}>{formatDateTime(monitoring.latest_event_at)}</strong>
                </div>
              </div>
              <div className="split-grid" style={{ marginTop: "18px" }}>
                <div className="metric-card">
                  <span className="eyebrow">Event Types</span>
                  <ul className="bullet-list">
                    {Object.entries(monitoring.event_type_counts).map(([key, value]) => (
                      <li key={key}>
                        {titleCase(key)}: {value}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="metric-card">
                  <span className="eyebrow">Latency by Event Type</span>
                  <ul className="bullet-list">
                    {Object.entries(monitoring.average_latency_by_event_type).map(([key, value]) => (
                      <li key={key}>
                        {titleCase(key)}: {value.toFixed(1)} ms
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          </section>
        </>
      ) : null}
    </GuardedPage>
  );
}
