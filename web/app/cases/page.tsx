import Link from "next/link";

import { getCases, getHealth } from "../../lib/api";
import { RiskPill } from "../../components/risk-pill";
import { StatusPill } from "../../components/status-pill";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function CasesPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const page = Number(params.page ?? "1");
  const pageSize = Number(params.page_size ?? "10");
  const selectedRiskBucket = typeof params.risk_bucket === "string" ? params.risk_bucket : "";
  const selectedDatasetFamily = typeof params.dataset_family === "string" ? params.dataset_family : "";
  const selectedStatus = typeof params.status === "string" ? params.status : "";
  const selectedDecision = typeof params.decision === "string" ? params.decision : "";

  const [health, queue] = await Promise.all([
    getHealth(),
    getCases({
      page,
      page_size: pageSize,
      risk_bucket: selectedRiskBucket || undefined,
      dataset_family: selectedDatasetFamily || undefined,
      status: selectedStatus || undefined,
      decision: selectedDecision || undefined,
    }),
  ]);

  const hasPreviousPage = page > 1;
  const hasNextPage = page * pageSize < queue.total;

  return (
    <>
      <section className="card">
        <div className="detail-hero">
          <div>
            <h2>Case Queue</h2>
            <p className="muted">
              Backend health: <strong>{health.status}</strong>. Use filters to test queue shaping before
              wiring auth.
            </p>
          </div>
          <div className="button-row">
            <a className="button secondary" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
              Open API Docs
            </a>
          </div>
        </div>
      </section>

      <section className="card">
        <form className="controls">
          <div className="field">
            <label htmlFor="risk_bucket">Risk bucket</label>
            <select id="risk_bucket" name="risk_bucket" defaultValue={selectedRiskBucket}>
              <option value="">All</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="dataset_family">Dataset family</label>
            <select id="dataset_family" name="dataset_family" defaultValue={selectedDatasetFamily}>
              <option value="">All</option>
              <option value="ssfd">ssfd</option>
              <option value="paysim">paysim</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="status">Status</label>
            <select id="status" name="status" defaultValue={selectedStatus}>
              <option value="">All</option>
              <option value="scored">scored</option>
              <option value="reviewed">reviewed</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="decision">Pipeline decision</label>
            <select id="decision" name="decision" defaultValue={selectedDecision}>
              <option value="">All</option>
              <option value="allow">allow</option>
              <option value="review">review</option>
              <option value="block">block</option>
            </select>
          </div>
          <input type="hidden" name="page" value="1" />
          <input type="hidden" name="page_size" value={pageSize} />
          <div className="button-row">
            <button className="button" type="submit">
              Apply Filters
            </button>
            <Link className="button secondary" href="/cases">
              Reset
            </Link>
          </div>
        </form>
      </section>

      <section className="card">
        {queue.items.length === 0 ? (
          <div className="empty">No cases found. Seed sample data and refresh the queue.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Family</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Pipeline</th>
                  <th>Status</th>
                  <th>Analyst</th>
                  <th>Scored</th>
                </tr>
              </thead>
              <tbody>
                {queue.items.map((item) => (
                  <tr key={item.event_id}>
                    <td>
                      <Link href={`/cases/${item.event_id}`}>
                        <strong>{item.event_id}</strong>
                      </Link>
                    </td>
                    <td>{item.dataset_family}</td>
                    <td>
                      <RiskPill bucket={item.risk_bucket} />
                    </td>
                    <td>{item.final_risk_score.toFixed(3)}</td>
                    <td>{item.decision}</td>
                    <td>
                      <StatusPill status={item.status} />
                    </td>
                    <td>{item.current_analyst_decision ?? "pending"}</td>
                    <td>{new Date(item.scored_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="pagination">
          <p className="muted">
            Showing page {queue.page} with page size {queue.page_size}. Total cases: {queue.total}.
          </p>
          <div className="button-row">
            {hasPreviousPage ? (
              <Link
                className="button secondary"
                href={`/cases?page=${page - 1}&page_size=${pageSize}&risk_bucket=${selectedRiskBucket}&dataset_family=${selectedDatasetFamily}&status=${selectedStatus}&decision=${selectedDecision}`}
              >
                Previous
              </Link>
            ) : null}
            {hasNextPage ? (
              <Link
                className="button"
                href={`/cases?page=${page + 1}&page_size=${pageSize}&risk_bucket=${selectedRiskBucket}&dataset_family=${selectedDatasetFamily}&status=${selectedStatus}&decision=${selectedDecision}`}
              >
                Next
              </Link>
            ) : null}
          </div>
        </div>
      </section>
    </>
  );
}
