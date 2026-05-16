import Link from "next/link";

import { DecisionForm } from "../../../components/decision-form";
import { RescoreButton } from "../../../components/rescore-button";
import { RiskPill } from "../../../components/risk-pill";
import { StatusPill } from "../../../components/status-pill";
import { getCaseDetail } from "../../../lib/api";

export default async function CaseDetailPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  const detail = await getCaseDetail(eventId);

  return (
    <>
      <section className="card">
        <div className="detail-hero">
          <div>
            <p className="eyebrow">Case Detail</p>
            <h2>{detail.event_id}</h2>
            <p className="muted">
              Family {detail.dataset_family} via {detail.routing_metadata.selected_ensemble}
            </p>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/cases">
              Back to Queue
            </Link>
            <RescoreButton eventId={detail.event_id} />
          </div>
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <p className="eyebrow">Final Score</p>
          <p className="score">{detail.final_risk_score.toFixed(3)}</p>
          <div className="button-row">
            <RiskPill bucket={detail.risk_bucket} />
            <StatusPill status={detail.status} />
          </div>
          <p className="muted">
            Pipeline decision: <strong>{detail.decision}</strong>
          </p>
          <p className="muted">Scored at {new Date(detail.scored_at).toLocaleString()}</p>
        </div>

        <div className="card">
          <h2>Model Comparison</h2>
          <div className="grid three">
            <div>
              <p className="eyebrow">Event GNN</p>
              <p className="metric-value">{detail.model_scores.event_gnn.toFixed(3)}</p>
            </div>
            <div>
              <p className="eyebrow">AdaBoost</p>
              <p className="metric-value">{detail.model_scores.adaboost.toFixed(3)}</p>
            </div>
            <div>
              <p className="eyebrow">LightGBM</p>
              <p className="metric-value">{detail.model_scores.lightgbm.toFixed(3)}</p>
            </div>
          </div>
        </div>
      </section>

      {!detail.required_state_status.history_available || !detail.required_state_status.graph_context_available ? (
        <section className="warning">
          <strong>State availability warning.</strong> {detail.explanation_stub.state_availability.history_summary}{" "}
          {detail.explanation_stub.state_availability.graph_summary}
        </section>
      ) : null}

      <section className="grid two">
        <div className="card">
          <h2>Top Contributors</h2>
          <ul className="list">
            {detail.explanation_stub.top_contributors.map((item) => (
              <li key={item.feature}>
                <strong>{item.feature}</strong>: {item.summary} ({item.magnitude.toFixed(3)})
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Evidence Panels</h2>
          <div className="grid">
            {detail.explanation_stub.evidence_panels.map((panel) => (
              <div key={panel.panel} className="card">
                <h3>{panel.title}</h3>
                <ul className="list">
                  {panel.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <DecisionForm
        eventId={detail.event_id}
        currentDecision={detail.current_analyst_decision}
        currentNote={detail.analyst_note}
      />
    </>
  );
}
