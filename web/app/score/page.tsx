"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCcwIcon, SendIcon } from "lucide-react";

import { GuardedPage } from "@/components/guarded-page";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

  function resetForm() {
    const freshPayload = buildDefaultPayload();
    setFormState(freshPayload);
    setRawAttributesText(JSON.stringify(freshPayload.raw_attributes, null, 2));
    setError(null);
    setSuccessMessage(null);
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
      title="Score Intake"
      description="Create a scored transaction case, then continue directly into analyst review."
    >
      <Card>
        <CardHeader>
          <CardTitle>New transaction payload</CardTitle>
          <CardDescription>Use canonical backend fields so the browser submission mirrors the scoring contract.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-5" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="transaction_id">Transaction ID</Label>
                <Input
                  id="transaction_id"
                  value={formState.transaction_id}
                  onChange={(event) => updateField("transaction_id", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="transaction_timestamp">Transaction timestamp</Label>
                <Input
                  id="transaction_timestamp"
                  value={formState.transaction_timestamp}
                  onChange={(event) => updateField("transaction_timestamp", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="sender_id">Sender ID</Label>
                <Input
                  id="sender_id"
                  value={formState.sender_id}
                  onChange={(event) => updateField("sender_id", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="receiver_id">Receiver ID</Label>
                <Input
                  id="receiver_id"
                  value={formState.receiver_id}
                  onChange={(event) => updateField("receiver_id", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="amount">Amount</Label>
                <Input
                  id="amount"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formState.amount}
                  onChange={(event) => updateField("amount", Number(event.target.value))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="transaction_location">Transaction location</Label>
                <Input
                  id="transaction_location"
                  value={formState.transaction_location}
                  onChange={(event) => updateField("transaction_location", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="transaction_type">Transaction type</Label>
                <Input
                  id="transaction_type"
                  value={formState.transaction_type}
                  onChange={(event) => updateField("transaction_type", event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={formState.currency ?? ""}
                  onChange={(event) => updateField("currency", event.target.value)}
                />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <Label htmlFor="channel">Channel</Label>
                <Input
                  id="channel"
                  value={formState.channel ?? ""}
                  onChange={(event) => updateField("channel", event.target.value)}
                />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <Label htmlFor="raw_attributes">Raw attributes JSON</Label>
                <Textarea
                  id="raw_attributes"
                  className="min-h-44 font-mono"
                  value={rawAttributesText}
                  onChange={(event) => setRawAttributesText(event.target.value)}
                />
              </div>
            </div>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Unable to score transaction</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {successMessage ? (
              <Alert className="border-primary/30 bg-primary/10">
                <AlertTitle>Score created</AlertTitle>
                <AlertDescription>{successMessage}</AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={submitting}>
                <SendIcon className="size-4" />
                {submitting ? "Scoring" : "Score transaction"}
              </Button>
              <Button type="button" variant="outline" onClick={resetForm} disabled={submitting}>
                <RotateCcwIcon className="size-4" />
                Reset form
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </GuardedPage>
  );
}
