"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  BrainIcon,
  CheckCircle2Icon,
  HistoryIcon,
  RefreshCwIcon,
  SaveIcon,
  ShieldAlertIcon,
  SlidersHorizontalIcon,
} from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { JsonCard } from "@/components/json-card";
import { StatusPill } from "@/components/status-pill";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, analyzeCaseWithGemini, getCaseDetail, rescoreCase, submitDecision, submitFeedback } from "@/lib/api";
import { formatDateTime, formatScore, titleCase } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { CaseDetailResponse, ConfirmedLabelValue, DecisionValue } from "@/lib/types";

const DEFAULT_DECISION_NOTE = "Needs manual verification.";

function scorePercent(value: number): string {
  const bounded = Math.max(0, Math.min(1, value));
  return `${Math.round(bounded * 100)}%`;
}

function SignalList({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <Card size="sm" className="bg-muted/30">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        ) : (
          <ul className="grid gap-2 text-sm text-muted-foreground">
            {items.map((item, index) => (
              <li key={`${item}-${index}`} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function LoadingDetail() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-36 w-full" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-56 w-full lg:col-span-2" />
      </div>
    </div>
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
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : caughtError instanceof Error
            ? caughtError.message
            : "Unable to load case detail.",
      );
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
    ? ([
        ["LightGBM", detail.latest_output.model_scores_overview.LightGBM],
        ["AdaBoost", detail.latest_output.model_scores_overview.AdaBoost],
        ["Event GNN", detail.latest_output.model_scores_overview.Event_GNN],
      ] as const)
    : [];
  const stateEntries = detail ? Object.entries(detail.latest_output.required_state_status) : [];
  const geminiAnalysis = detail?.latest_gemini_analysis ?? null;

  return (
    <GuardedPage
      title="Case Detail"
      description="Inspect risk evidence, request AI advisory support, and record the official analyst outcome."
    >
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Case workflow error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {successMessage ? (
        <Alert className="border-primary/30 bg-primary/10">
          <CheckCircle2Icon className="size-4" />
          <AlertTitle>Saved</AlertTitle>
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      ) : null}

      {loading ? <LoadingDetail /> : null}

      {!loading && !detail ? (
        <EmptyState title="Case not found" description="This transaction could not be loaded from the workflow store." />
      ) : null}

      {detail ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">Transaction</Badge>
                    <span className="break-all font-mono text-sm text-muted-foreground">{transactionId}</span>
                  </div>
                  <CardTitle className="text-2xl">Risk score {formatScore(detail.latest_output.fraud_score)}</CardTitle>
                  <CardDescription>
                    Last scored {formatDateTime(detail.last_scored_at)} with {detail.latest_output.pipeline_profile}.
                  </CardDescription>
                </div>
                <div className="grid gap-3 sm:grid-cols-[auto_auto] lg:justify-items-end">
                  <div className="flex flex-wrap gap-2">
                    <StatusPill value={detail.latest_output.decision} />
                    <StatusPill value={detail.review_status} />
                    <StatusPill value={detail.risk_bucket} />
                  </div>
                  <div className="flex flex-wrap gap-2 sm:col-span-2 lg:justify-end">
                    <Button type="button" variant="outline" onClick={handleRescore} disabled={busyAction === "rescore"}>
                      <RefreshCwIcon className="size-4" />
                      {busyAction === "rescore" ? "Rescoring" : "Rescore"}
                    </Button>
                    <Button type="button" onClick={handleGeminiAnalysis} disabled={busyAction === "gemini"}>
                      <BrainIcon className="size-4" />
                      {busyAction === "gemini" ? "Analyzing" : geminiAnalysis ? "Refresh advisory" : "Analyze"}
                    </Button>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-2xl border bg-muted/30 p-4">
                  <p className="text-xs text-muted-foreground">Threshold</p>
                  <p className="mt-1 text-lg font-medium">{formatScore(detail.latest_output.threshold)}</p>
                </div>
                <div className="rounded-2xl border bg-muted/30 p-4">
                  <p className="text-xs text-muted-foreground">Model decision</p>
                  <div className="mt-2">
                    <StatusPill value={detail.latest_output.decision} />
                  </div>
                </div>
                <div className="rounded-2xl border bg-muted/30 p-4">
                  <p className="text-xs text-muted-foreground">Latest analyst decision</p>
                  <div className="mt-2">
                    <StatusPill value={detail.latest_analyst_decision ?? "pending"} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="overview" className="gap-4">
            <TabsList variant="line" className="w-full justify-start overflow-x-auto">
              <TabsTrigger value="overview">
                <ShieldAlertIcon className="size-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="advisory">
                <BrainIcon className="size-4" />
                Advisory
              </TabsTrigger>
              <TabsTrigger value="decision">
                <SaveIcon className="size-4" />
                Decision
              </TabsTrigger>
              <TabsTrigger value="evidence">
                <SlidersHorizontalIcon className="size-4" />
                Evidence
              </TabsTrigger>
              <TabsTrigger value="history">
                <HistoryIcon className="size-4" />
                History
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="grid gap-4">
              <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr_1fr]">
                <Card>
                  <CardHeader>
                    <CardTitle>Fraud score</CardTitle>
                    <CardDescription>Current model output</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-5">
                    <div className="font-heading text-6xl font-medium tracking-tight">
                      {formatScore(detail.latest_output.fraud_score)}
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: scorePercent(detail.latest_output.fraud_score) }} />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {titleCase(detail.risk_bucket)} risk with a {formatScore(detail.latest_output.threshold)} threshold.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Model signals</CardTitle>
                    <CardDescription>{detail.latest_output.explanation_summary.reason}</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    {modelScores.map(([label, score]) => (
                      <div key={label} className="grid gap-2">
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="font-medium">{label}</span>
                          <span className="text-muted-foreground">{formatScore(score)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-primary" style={{ width: scorePercent(score) }} />
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Explanation</CardTitle>
                    <CardDescription>Signals used to route this case</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3">
                    <div className="rounded-2xl border bg-muted/30 p-3">
                      <p className="text-xs text-muted-foreground">Main source</p>
                      <p className="mt-1 font-medium">{titleCase(detail.latest_output.explanation_summary.main_risk_source)}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <StatusPill value={detail.latest_output.explanation_summary.tabular_signal} />
                      <StatusPill value={detail.latest_output.explanation_summary.graph_signal} />
                    </div>
                    <Separator />
                    <div className="flex flex-wrap gap-2">
                      {stateEntries.map(([key, available]) => (
                        <Badge key={key} variant={available ? "secondary" : "outline"}>
                          {titleCase(key)}: {available ? "Available" : "Limited"}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="advisory" className="grid gap-4">
              <Card>
                <CardHeader>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <CardTitle>Gemini advisory</CardTitle>
                      <CardDescription>Advisory support only. The analyst decision remains the official action.</CardDescription>
                    </div>
                    <Button type="button" variant="outline" onClick={handleGeminiAnalysis} disabled={busyAction === "gemini"}>
                      <BrainIcon className="size-4" />
                      {busyAction === "gemini" ? "Analyzing" : geminiAnalysis ? "Refresh analysis" : "Analyze"}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {geminiAnalysis ? (
                    <div className="grid gap-4">
                      <div className="rounded-2xl border bg-muted/30 p-4">
                        <div className="mb-3 flex flex-wrap gap-2">
                          <StatusPill value={geminiAnalysis.recommended_decision} />
                          <StatusPill value={geminiAnalysis.confidence} />
                        </div>
                        <p className="text-sm leading-6">{geminiAnalysis.summary}</p>
                        <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>{geminiAnalysis.model}</span>
                          <span>{formatDateTime(geminiAnalysis.analyzed_at)}</span>
                          <span>Score run {geminiAnalysis.source_score_run_id}</span>
                        </div>
                      </div>
                      <div className="grid gap-4 lg:grid-cols-3">
                        <SignalList title="Key factors" items={geminiAnalysis.key_factors} emptyLabel="No key factors returned." />
                        <SignalList title="Risk flags" items={geminiAnalysis.risk_flags} emptyLabel="No risk flags returned." />
                        <SignalList title="Follow-up" items={geminiAnalysis.follow_up_actions} emptyLabel="No follow-up actions returned." />
                      </div>
                    </div>
                  ) : (
                    <EmptyState
                      title="No Gemini analysis yet"
                      description="Run Gemini analysis manually to add an advisory recommendation for this case."
                    />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="decision" className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Official analyst decision</CardTitle>
                  <CardDescription>Record the decision that becomes part of the review workflow.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form className="grid gap-4" onSubmit={handleDecision}>
                    <div className="grid gap-2">
                      <Label htmlFor="analyst_decision">Decision</Label>
                      <Select value={decision} onValueChange={(value) => setDecision((value ?? "review") as DecisionValue)}>
                        <SelectTrigger id="analyst_decision" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="allow">Allow</SelectItem>
                          <SelectItem value="review">Review</SelectItem>
                          <SelectItem value="block">Block</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="decision_note">Decision note</Label>
                      <Textarea
                        id="decision_note"
                        className="min-h-32"
                        value={decisionNote}
                        onChange={(event) => setDecisionNote(event.target.value)}
                      />
                    </div>
                    <Button type="submit" className="w-fit" disabled={busyAction === "decision"}>
                      <SaveIcon className="size-4" />
                      {busyAction === "decision" ? "Submitting" : "Submit decision"}
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Confirmed feedback</CardTitle>
                  <CardDescription>Store the observed final outcome separately from analyst notes.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form className="grid gap-4" onSubmit={handleFeedback}>
                    <div className="grid gap-2">
                      <Label htmlFor="feedback_label">Confirmed label</Label>
                      <Select
                        value={feedbackLabel}
                        onValueChange={(value) => setFeedbackLabel((value ?? "fraud") as ConfirmedLabelValue)}
                      >
                        <SelectTrigger id="feedback_label" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="fraud">Fraud</SelectItem>
                          <SelectItem value="legitimate">Legitimate</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="feedback_timestamp">Feedback timestamp</Label>
                      <Input
                        id="feedback_timestamp"
                        type="datetime-local"
                        value={feedbackTime}
                        onChange={(event) => setFeedbackTime(event.target.value)}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="feedback_note">Feedback note</Label>
                      <Textarea
                        id="feedback_note"
                        className="min-h-28"
                        value={feedbackNote}
                        onChange={(event) => setFeedbackNote(event.target.value)}
                      />
                    </div>
                    <Button type="submit" variant="outline" className="w-fit" disabled={busyAction === "feedback"}>
                      <SaveIcon className="size-4" />
                      {busyAction === "feedback" ? "Saving" : "Submit feedback"}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="evidence" className="grid gap-4 lg:grid-cols-3">
              <JsonCard title="Original request payload" value={detail.original_request_payload} />
              <JsonCard title="Explanation payload" value={detail.explanation_payload} />
              <JsonCard title="Routing metadata" value={detail.routing_metadata} />
            </TabsContent>

            <TabsContent value="history" className="grid gap-4 xl:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>Review history</CardTitle>
                  <CardDescription>Analyst workflow actions stored on the case.</CardDescription>
                </CardHeader>
                <CardContent>
                  {detail.review_history.length === 0 ? (
                    <EmptyState title="No review history yet" description="Submit the first analyst decision to populate this timeline." />
                  ) : (
                    <ScrollArea className="max-h-96">
                      <div className="grid gap-3 pr-3">
                        {detail.review_history.map((entry, index) => (
                          <article key={`${entry.created_at}-${index}`} className="rounded-2xl border bg-muted/30 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <strong className="text-sm">{entry.analyst_username ?? "Unknown analyst"}</strong>
                              <StatusPill value={entry.analyst_decision} />
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{entry.note}</p>
                            <p className="mt-2 text-xs text-muted-foreground">{formatDateTime(entry.created_at)}</p>
                          </article>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Feedback history</CardTitle>
                  <CardDescription>Confirmed labels are stored separately from internal analyst notes.</CardDescription>
                </CardHeader>
                <CardContent>
                  {detail.feedback_history.length === 0 ? (
                    <EmptyState title="No confirmed outcomes yet" description="Submit feedback once the real outcome is known." />
                  ) : (
                    <ScrollArea className="max-h-96">
                      <div className="grid gap-3 pr-3">
                        {detail.feedback_history.map((entry, index) => (
                          <article key={`${entry.feedback_timestamp}-${index}`} className="rounded-2xl border bg-muted/30 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <strong className="text-sm">{entry.reviewer_username ?? "Unknown reviewer"}</strong>
                              <StatusPill value={entry.confirmed_label} />
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{entry.note ?? "No feedback note provided."}</p>
                            <p className="mt-2 text-xs text-muted-foreground">{formatDateTime(entry.feedback_timestamp)}</p>
                          </article>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Audit trail</CardTitle>
                  <CardDescription>Score, rescore, review, feedback, and Gemini events.</CardDescription>
                </CardHeader>
                <CardContent>
                  {detail.audit_trail.length === 0 ? (
                    <EmptyState title="No audit entries" description="Audit events will appear here after backend workflow actions." />
                  ) : (
                    <ScrollArea className="max-h-96">
                      <div className="grid gap-3 pr-3">
                        {detail.audit_trail.map((entry, index) => (
                          <article key={`${entry.created_at}-${index}`} className="rounded-2xl border bg-muted/30 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <strong className="text-sm">{entry.action}</strong>
                              <span className="text-xs text-muted-foreground">{entry.actor_username ?? "System"}</span>
                            </div>
                            <p className="mt-2 text-xs text-muted-foreground">{formatDateTime(entry.created_at)}</p>
                            <pre className="mt-3 overflow-x-auto rounded-2xl bg-background p-3 font-mono text-xs text-muted-foreground">
                              {JSON.stringify(entry.details, null, 2)}
                            </pre>
                          </article>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </GuardedPage>
  );
}
