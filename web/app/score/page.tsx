"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { GuardedPage } from "@/components/guarded-page";
import { ApiError, scoreCase } from "@/lib/api";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { ScoreRequestPayload } from "@/lib/types";

function buildDefaultPayload(): ScoreRequestPayload {
  const isoNow = new Date().toISOString();
  return {
    transaction_id: `tx-${Date.now()}`,
    transaction_timestamp: isoNow,
    sender_id: "sender-001",
    receiver_id: "receiver-001",
    amount: 145.5,
    transaction_location: "VN-HCM",
    transaction_type: "card_not_present",
    currency: "USD",
    channel: "web",
    raw_attributes: {
      device_id: "device-001",
      ip_country: "VN",
    },
  };
}

export default function ScorePage() {
  const router = useRouter();
  const { run } = useAuthedRequest();
  const [formState, setFormState] = useState<ScoreRequestPayload>(() => buildDefaultPayload());
  const [rawAttributesText, setRawAttributesText] = useState(() =>
    JSON.stringify(buildDefaultPayload().raw_attributes, null, 2),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  function updateField<K extends keyof ScoreRequestPayload>(field: K, value: ScoreRequestPayload[K]) {
    setFormState((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const rawAttributes = rawAttributesText.trim() ? JSON.parse(rawAttributesText) : undefined;
      const payload: ScoreRequestPayload = {
        ...formState,
        raw_attributes: rawAttributes,
      };
      const detail = await run((token) => scoreCase(token, payload));
      setSuccessMessage(`Case ${detail.transaction_id} created with ${detail.latest_output.decision} routing.`);
      router.push(`/cases/${encodeURIComponent(detail.transaction_id)}`);
    } catch (caughtError) {
      if (caughtError instanceof SyntaxError) {
        setError("Raw attributes must be valid JSON.");
      } else if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Unable to score transaction.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <GuardedPage
      title="Browser Score Intake"
      description="Submit canonical transaction payloads from the browser and land directly on the stored case detail."
    >
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Submit new transaction</h3>
            <p>Use the canonical backend field names so the payload mirrors the production scoring contract.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field-group">
            <label htmlFor="transaction_id">Transaction ID</label>
            <input
              id="transaction_id"
              className="text-input"
              value={formState.transaction_id}
              onChange={(event) => updateField("transaction_id", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="transaction_timestamp">Transaction Timestamp</label>
            <input
              id="transaction_timestamp"
              className="text-input"
              value={formState.transaction_timestamp}
              onChange={(event) => updateField("transaction_timestamp", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="sender_id">Sender ID</label>
            <input
              id="sender_id"
              className="text-input"
              value={formState.sender_id}
              onChange={(event) => updateField("sender_id", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="receiver_id">Receiver ID</label>
            <input
              id="receiver_id"
              className="text-input"
              value={formState.receiver_id}
              onChange={(event) => updateField("receiver_id", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="amount">Amount</label>
            <input
              id="amount"
              className="text-input"
              type="number"
              min="0"
              step="0.01"
              value={formState.amount}
              onChange={(event) => updateField("amount", Number(event.target.value))}
            />
          </div>
          <div className="field-group">
            <label htmlFor="transaction_location">Transaction Location</label>
            <input
              id="transaction_location"
              className="text-input"
              value={formState.transaction_location}
              onChange={(event) => updateField("transaction_location", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="transaction_type">Transaction Type</label>
            <input
              id="transaction_type"
              className="text-input"
              value={formState.transaction_type}
              onChange={(event) => updateField("transaction_type", event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor="currency">Currency</label>
            <input
              id="currency"
              className="text-input"
              value={formState.currency ?? ""}
              onChange={(event) => updateField("currency", event.target.value)}
            />
          </div>
          <div className="field-group full-width">
            <label htmlFor="channel">Channel</label>
            <input
              id="channel"
              className="text-input"
              value={formState.channel ?? ""}
              onChange={(event) => updateField("channel", event.target.value)}
            />
          </div>
          <div className="field-group full-width">
            <label htmlFor="raw_attributes">Raw Attributes JSON</label>
            <textarea
              id="raw_attributes"
              className="text-area"
              value={rawAttributesText}
              onChange={(event) => setRawAttributesText(event.target.value)}
            />
          </div>
          {error ? <div className="error-banner full-width">{error}</div> : null}
          {successMessage ? <div className="success-banner full-width">{successMessage}</div> : null}
          <div className="button-row">
            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? "Scoring..." : "Score Transaction"}
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                const freshPayload = buildDefaultPayload();
                setFormState(freshPayload);
                setRawAttributesText(JSON.stringify(freshPayload.raw_attributes, null, 2));
                setError(null);
                setSuccessMessage(null);
              }}
            >
              Reset Form
            </button>
          </div>
        </form>
      </section>
    </GuardedPage>
  );
}
