import { getMetrics } from "../../lib/api";

export default async function MetricsPage() {
  const metrics = await getMetrics();

  return (
    <>
      <section className="card">
        <h2>Operational Metrics</h2>
        <p className="muted">Lightweight aggregate visibility for the fraud-ops prototype.</p>
      </section>

      <section className="grid three">
        <div className="card">
          <p className="eyebrow">Total Cases</p>
          <p className="metric-value">{metrics.total_cases}</p>
        </div>
        <div className="card">
          <p className="eyebrow">Reviewed Cases</p>
          <p className="metric-value">{metrics.reviewed_cases}</p>
        </div>
        <div className="card">
          <p className="eyebrow">Pending Review</p>
          <p className="metric-value">{metrics.total_cases - metrics.reviewed_cases}</p>
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <h2>By Risk Bucket</h2>
          <div className="grid">
            {Object.entries(metrics.by_risk_bucket).map(([bucket, count]) => (
              <div key={bucket} className="detail-hero">
                <strong>{bucket}</strong>
                <span>{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h2>By Pipeline Decision</h2>
          <div className="grid">
            {Object.entries(metrics.by_decision).map(([decision, count]) => (
              <div key={decision} className="detail-hero">
                <strong>{decision}</strong>
                <span>{count}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
