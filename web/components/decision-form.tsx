"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { submitDecision } from "../lib/api";
import { Decision } from "../lib/types";

export function DecisionForm(props: {
  eventId: string;
  currentDecision: Decision | null;
  currentNote: string | null;
}) {
  const router = useRouter();
  const [decision, setDecision] = useState<Decision>(props.currentDecision ?? "review");
  const [note, setNote] = useState(props.currentNote ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <div className="card">
      <h2>Analyst Review</h2>
      <p className="muted">Record a decision and note against the persisted case.</p>
      <div className="field">
        <label htmlFor="analyst-decision">Decision</label>
        <select
          id="analyst-decision"
          value={decision}
          onChange={(event) => setDecision(event.target.value as Decision)}
        >
          <option value="allow">allow</option>
          <option value="review">review</option>
          <option value="block">block</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="analyst-note">Note</label>
        <textarea
          id="analyst-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Summarize why this case should be allowed, reviewed, or blocked."
        />
      </div>
      <div className="button-row">
        <button
          className="button"
          disabled={isPending || note.trim().length === 0}
          onClick={() => {
            setMessage(null);
            startTransition(async () => {
              try {
                await submitDecision({
                  event_id: props.eventId,
                  analyst_decision: decision,
                  note: note.trim(),
                });
                setMessage("Decision saved.");
                router.refresh();
              } catch (error) {
                setMessage(error instanceof Error ? error.message : "Failed to save decision.");
              }
            });
          }}
        >
          {isPending ? "Saving..." : "Save Decision"}
        </button>
      </div>
      {message ? <p className="muted">{message}</p> : null}
    </div>
  );
}
