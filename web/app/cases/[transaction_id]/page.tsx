"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { JsonCard } from "@/components/json-card";
import { StatusPill } from "@/components/status-pill";
import { ApiError, analyzeCaseWithGemini, getCaseDetail, rescoreCase, submitDecision, submitFeedback } from "@/lib/api";
import { formatDateTime, formatScore, titleCase } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { CaseDetailResponse, ConfirmedLabelValue, DecisionValue } from "@/lib/types";

const DEFAULT_DECISION_NOTE = "Needs manual verification.";

function scorePercent(value: number): string {
  const bounded = Math.max(0, Math.min(1, value));
  return `${Math.round(bounded * 100)}%`;
}

function renderList(items: string[], emptyLabel: string) {
  if (items.length === 0) {
    return <p className="muted-copy">{emptyLabel}</p>;
  }

  return (
    <ul className="bullet-list compact-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

export default function CaseDetailPage() {
  const params = useParams<{ transaction_id: string }>();
  const transactionId = Array.isArray(params.transaction_id) ? params.transaction_id[0] : params.transaction_id;
  const { run } = useAuthedRequest();
  const [detail, setDetail] = useState<CaseDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"decision" | "rescore" | "feedback" | "gemini" | null>(null);
  const [decision, setDecision] = useState<DecisionValue>("review");
  const [decisionNote, setDecisionNote] = useState(DEFAULT_DECISION_NOTE);
  const [feedbackLabel, setFeedbackLabel] = useState<ConfirmedLabelValue>("fraud");
  const [feedbackTime, setFeedbackTime] = useState(new Date().toISOString().slice(0, 16));
  const [feedbackNote, setFeedbackNote] = useState("Confirmed after manual review.");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function loadDetail() {
    setLoading(true);
    setError(null);
    try {
      const response = await run((token) => getCaseDetail(token, transactionId));
      setDetail(response);
      setDecision(response.latest_analyst_decision ?? "review");
      setDecisionNote(response.latest_note ?? DEFAULT_DECISION_NOTE);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Unable to load case detail.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDetail();
  }, [transactionId]);

  async function handleDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("decision");
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await run((token) =>
        submitDecision(token, transactionId, {
          analyst_decision: decision,
          note: decisionNote,
        }),
      );
      setDetail(response);
      setSuccessMessage("Analyst decision recorded.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to submit decision.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRescore() {
    setBusyAction("rescore");
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await run((token) => rescoreCase(token, transactionId));
      setDetail(response);
      setDecision(response.latest_analyst_decision ?? "review");
      setDecisionNote(response.latest_note ?? DEFAULT_DECISION_NOTE);
      setSuccessMessage("Case rescored using the current pipeline.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to rescore case.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleGeminiAnalysis() {
    setBusyAction("gemini");
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await run((token) => analyzeCaseWithGemini(token, transactionId));
      setDetail(response);
      setSuccessMessage("Gemini advisory analysis generated.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to analyze case with Gemini.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("feedback");
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await run((token) =>
        submitFeedback(token, transactionId, {
          confirmed_label: feedbackLabel,
          feedback_timestamp: feedbackTime ? new Date(feedbackTime).toISOString() : undefined,
          note: feedbackNote,
        }),
      );
      setDetail(response);
      setSuccessMessage("Confirmed outcome feedback recorded.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to submit feedback.");
    } finally {
      setBusyAction(null);
    }
  }

  const modelScores = detail
    ? [
        ["LightGBM", detail.latest_output.model_scores_overview.LightGBM],
        ["AdaBoost", detail.latest_output.model_scores_overview.AdaBoost],
        ["Event GNN", detail.latest_output.model_scores_overview.Event_GNN],
      ] as const
    : [];
  const stateEntries = detail ? Object.entries(detail.latest_output.required_state_status) : [];
  const geminiAnalysis = detail?.latest_gemini_analysis ?? null;

  return (
    <GuardedPage
      title={`Case Detail: ${transactionId}`}
      description="Review a stored fraud case, inspect aligned scoring output, and take analyst actions without leaving the browser."
    >
      {error ? <div className="error-banner">{error}</div> : null}
      {successMessage ? <div className="success-banner">{successMessage}</div> : null}
      {loading ? (
        <section className="panel">
          <p>Loading case detail...</p>
        </section>
      ) : null}
      {!loading && !detail ? (
        <EmptyState title="Case not found" description="This transaction could not be loaded from the workflow store." />
      ) : null}

      {detail ? (
        <>
          <section className="case-command-bar panel">
            <div className="case-command-main">
              <span className="eyebrow">Transaction</span>
              <h3>{transactionId}</h3>
              <p>Last scored {formatDateTime(detail.last_scored_at)} with {detail.latest_output.pipeline_profile}.</p>
            </div>
            <div className="case-command-actions">
              <div className="case-status-strip">
                <div>
                  <span className="eyebrow">Model Decision</span>
                  <StatusPill value={detail.latest_output.decision} />
                </div>
                <div>
                  <span className="eyebrow">Review Status</span>
                  <StatusPill value={detail.review_status} />
                </div>
              </div>
              <div className="button-row">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleRescore}
                  disabled={busyAction === "rescore"}
                >
                  {busyAction === "rescore" ? "Rescoring..." : "Rescore Case"}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={handleGeminiAnalysis}
                  disabled={busyAction === "gemini"}
                >
                  {busyAction === "gemini" ? "Analyzing..." : "Analyze with Gemini"}
                </button>
              </div>
            </div>
          </section>

          <section className="risk-dashboard">
            <section className="score-hero panel">
              <span className="eyebrow">Fraud Score</span>
              <strong>{formatScore(detail.latest_output.fraud_score)}</strong>
              <div className="score-rail" aria-label="Fraud score visual indicator">
                <span style={{ width: scorePercent(detail.latest_output.fraud_score) }} />
              </div>
              <div className="score-hero-meta">
                <span>Threshold {formatScore(detail.latest_output.threshold)}</span>
                <span>Risk bucket: {titleCase(detail.risk_bucket)}</span>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header compact-panel-header">
                <div>
                  <h3>Model signals</h3>
                  <p>{detail.latest_output.explanation_summary.reason}</p>
                </div>
              </div>
              <div className="model-score-list">
                {modelScores.map(([label, score]) => (
                  <div key={label} className="model-score-row">
                    <div>
                      <strong>{label}</strong>
                      <span>{formatScore(score)}</span>
                    </div>
                    <div className="model-score-bar" aria-label={`${label} score ${formatScore(score)}`}>
                      <span style={{ width: scorePercent(score) }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header compact-panel-header">
                <div>
                  <h3>Explanation</h3>
                  <p>Signals used to route the current case.</p>
                </div>
              </div>
              <div className="signal-grid">
                <div className="signal-item">
                  <span className="eyebrow">Main Source</span>
                  <strong>{titleCase(detail.latest_output.explanation_summary.main_risk_source)}</strong>
                </div>
                <div className="signal-item">
                  <span className="eyebrow">Tabular Signal</span>
                  <StatusPill value={detail.latest_output.explanation_summary.tabular_signal} />
                </div>
                <div className="signal-item">
                  <span className="eyebrow">Graph Signal</span>
                  <StatusPill value={detail.latest_output.explanation_summary.graph_signal} />
                </div>
              </div>
              <div className="state-strip">
                {stateEntries.map(([key, available]) => (
                  <span key={key} className={available ? "state-chip state-chip-ok" : "state-chip state-chip-muted"}>
                    {titleCase(key)}: {available ? "Available" : "Limited"}
                  </span>
                ))}
              </div>
            </section>
          </section>

          <section className="review-workspace">
            <section className="gemini-panel panel">
              <div className="panel-header">
                <div>
                  <h3>Gemini advisory</h3>
                  <p>AI recommendation based on the current score snapshot. Analyst decision remains the official action.</p>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleGeminiAnalysis}
                  disabled={busyAction === "gemini"}
                >
                  {busyAction === "gemini" ? "Analyzing..." : geminiAnalysis ? "Refresh Gemini" : "Analyze"}
                </button>
              </div>
              {geminiAnalysis ? (
                <>
                  <div className="gemini-summary-card">
                    <div className="case-status-strip">
                      <div>
                        <span className="eyebrow">Recommendation</span>
                        <StatusPill value={geminiAnalysis.recommended_decision} />
                      </div>
                      <div>
                        <span className="eyebrow">Confidence</span>
                        <StatusPill value={geminiAnalysis.confidence} />
                      </div>
                    </div>
                    <p>{geminiAnalysis.summary}</p>
                    <div className="advisory-meta">
                      <span>{geminiAnalysis.model}</span>
                      <span>{formatDateTime(geminiAnalysis.analyzed_at)}</span>
                      <span>Score run {geminiAnalysis.source_score_run_id}</span>
                    </div>
                  </div>
                  <div className="advisory-list-grid">
                    <div>
                      <h4>Key factors</h4>
                      {renderList(geminiAnalysis.key_factors, "No key factors returned.")}
                    </div>
                    <div>
                      <h4>Risk flags</h4>
                      {renderList(geminiAnalysis.risk_flags, "No risk flags returned.")}
                    </div>
                    <div>
                      <h4>Follow-up</h4>
                      {renderList(geminiAnalysis.follow_up_actions, "No follow-up actions returned.")}
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState
                  title="No Gemini analysis yet"
                  description="Run Gemini analysis manually to add an advisory recommendation for this case."
                />
              )}
            </section>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Official analyst decision</h3>
                  <p>Record the decision that becomes part of the review workflow.</p>
                </div>
              </div>
              <form className="form-grid" onSubmit={handleDecision}>
                <div className="field-group full-width">
                  <label htmlFor="analyst_decision">Decision</label>
                  <select
                    id="analyst_decision"
                    className="select-input"
                    value={decision}
                    onChange={(event) => setDecision(event.target.value as DecisionValue)}
                  >
                    <option value="allow">Allow</option>
                    <option value="review">Review</option>
                    <option value="block">Block</option>
                  </select>
                </div>
                <div className="field-group full-width">
                  <label htmlFor="decision_note">Note</label>
                  <textarea
                    id="decision_note"
                    className="text-area"
                    value={decisionNote}
                    onChange={(event) => setDecisionNote(event.target.value)}
                  />
                </div>
                <div className="button-row">
                  <button type="submit" className="primary-button" disabled={busyAction === "decision"}>
                    {busyAction === "decision" ? "Submitting..." : "Submit Decision"}
                  </button>
                </div>
              </form>
            </section>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Confirmed feedback</h3>
                <p>Record the observed final outcome separately from analyst review history.</p>
              </div>
            </div>
            <form className="form-grid" onSubmit={handleFeedback}>
              <div className="field-group">
                <label htmlFor="feedback_label">Confirmed Label</label>
                <select
                  id="feedback_label"
                  className="select-input"
                  value={feedbackLabel}
                  onChange={(event) => setFeedbackLabel(event.target.value as ConfirmedLabelValue)}
                >
                  <option value="fraud">Fraud</option>
                  <option value="legitimate">Legitimate</option>
                </select>
              </div>
              <div className="field-group">
                <label htmlFor="feedback_timestamp">Feedback Timestamp</label>
                <input
                  id="feedback_timestamp"
                  className="text-input"
                  type="datetime-local"
                  value={feedbackTime}
                  onChange={(event) => setFeedbackTime(event.target.value)}
                />
              </div>
              <div className="field-group full-width">
                <label htmlFor="feedback_note">Feedback Note</label>
                <textarea
                  id="feedback_note"
                  className="text-area"
                  value={feedbackNote}
                  onChange={(event) => setFeedbackNote(event.target.value)}
                />
              </div>
              <div className="button-row">
                <button type="submit" className="secondary-button" disabled={busyAction === "feedback"}>
                  {busyAction === "feedback" ? "Saving..." : "Submit Feedback"}
                </button>
              </div>
            </form>
          </section>

          <section className="evidence-grid">
            <JsonCard title="Original Request Payload" value={detail.original_request_payload} />
            <JsonCard title="Explanation Payload" value={detail.explanation_payload} />
            <JsonCard title="Routing Metadata" value={detail.routing_metadata} />
          </section>

          <section className="evidence-grid">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Review history</h3>
                  <p>Analyst workflow actions stored on the case.</p>
                </div>
              </div>
              {detail.review_history.length === 0 ? (
                <EmptyState title="No review history yet" description="Submit the first analyst decision to populate this timeline." />
              ) : (
                <div className="timeline">
                  {detail.review_history.map((entry, index) => (
                    <article key={`${entry.created_at}-${index}`} className="timeline-item">
                      <header>
                        <strong>{entry.analyst_username ?? "Unknown analyst"}</strong>
                        <StatusPill value={entry.analyst_decision} />
                      </header>
                      <p>{entry.note}</p>
                      <span>{formatDateTime(entry.created_at)}</span>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Feedback history</h3>
                  <p>Confirmed labels are stored separately from internal analyst notes.</p>
                </div>
              </div>
              {detail.feedback_history.length === 0 ? (
                <EmptyState title="No confirmed outcomes yet" description="Submit feedback once the real outcome is known." />
              ) : (
                <div className="timeline">
                  {detail.feedback_history.map((entry, index) => (
                    <article key={`${entry.feedback_timestamp}-${index}`} className="timeline-item">
                      <header>
                        <strong>{entry.reviewer_username ?? "Unknown reviewer"}</strong>
                        <StatusPill value={entry.confirmed_label} />
                      </header>
                      <p>{entry.note ?? "No feedback note provided."}</p>
                      <span>{formatDateTime(entry.feedback_timestamp)}</span>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3>Audit trail</h3>
                  <p>Score, rescore, review, feedback, and Gemini actions captured for this workflow.</p>
                </div>
              </div>
              {detail.audit_trail.length === 0 ? (
                <EmptyState title="No audit entries" description="Audit events will appear here after backend workflow actions." />
              ) : (
                <div className="timeline">
                  {detail.audit_trail.map((entry, index) => (
                    <article key={`${entry.created_at}-${index}`} className="timeline-item">
                      <header>
                        <strong>{entry.action}</strong>
                        <span>{entry.actor_username ?? "System"}</span>
                      </header>
                      <p>{formatDateTime(entry.created_at)}</p>
                      <pre className="json-block">{JSON.stringify(entry.details, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </section>
        </>
      ) : null}
    </GuardedPage>
  );
}
