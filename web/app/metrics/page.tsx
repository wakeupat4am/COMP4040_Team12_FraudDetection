"use client";

import { useEffect, useState } from "react";
import { ActivityIcon, ClockIcon, GaugeIcon, InboxIcon, ListChecksIcon, TimerIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getMetricsSummary, getMonitoringSummary } from "@/lib/api";
import { formatDateTime, formatScore, titleCase } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { MetricsSummaryResponse, MonitoringSummaryResponse } from "@/lib/types";

function SummaryCard({
  icon: Icon,
  label,
  value,
  description,
}: {
  icon: typeof ActivityIcon;
  label: string;
  value: string | number;
  description?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-4 py-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-2 font-heading text-3xl font-medium tracking-tight">{value}</p>
          {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        <div className="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function DistributionCard({ title, values, suffix = "" }: { title: string; values: Record<string, number>; suffix?: string }) {
  const entries = Object.entries(values);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No values reported.</p>
        ) : (
          entries.map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-3 rounded-2xl border bg-muted/30 px-3 py-2">
              <span className="text-sm text-muted-foreground">{titleCase(key)}</span>
              <Badge variant="secondary">
                {Number.isInteger(value) ? value : value.toFixed(1)}
                {suffix}
              </Badge>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function MetricsSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

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
          setError(
            caughtError instanceof ApiError
              ? caughtError.message
              : caughtError instanceof Error
                ? caughtError.message
                : "Unable to load metrics.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [run]);

  return (
    <GuardedPage
      title="Metrics"
      description="Monitor queue health, case distribution, and backend scoring telemetry."
    >
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Unable to load metrics</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {loading ? <MetricsSkeleton /> : null}

      {!loading && (!metrics || !monitoring) ? (
        <EmptyState title="Metrics unavailable" description="The backend did not return a metrics payload for this session." />
      ) : null}

      {metrics && monitoring ? (
        <div className="grid gap-4">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <SummaryCard icon={InboxIcon} label="Total cases" value={metrics.total_cases} />
            <SummaryCard icon={GaugeIcon} label="Average fraud score" value={formatScore(metrics.average_final_risk_score)} />
            <SummaryCard icon={ListChecksIcon} label="Pending review" value={metrics.pending_review_cases} />
            <SummaryCard icon={ActivityIcon} label="Monitoring events" value={monitoring.total_events} />
            <SummaryCard icon={TimerIcon} label="Average latency" value={`${monitoring.average_latency_ms.toFixed(1)} ms`} />
            <SummaryCard
              icon={ClockIcon}
              label="Latest event"
              value={monitoring.latest_event_at ? formatDateTime(monitoring.latest_event_at) : "None"}
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <DistributionCard title="Risk buckets" values={metrics.risk_bucket_counts} />
            <DistributionCard title="Decision counts" values={metrics.decision_counts} />
            <DistributionCard title="Review status" values={metrics.review_status_counts} />
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <DistributionCard title="Event types" values={monitoring.event_type_counts} />
            <DistributionCard title="Latency by event type" values={monitoring.average_latency_by_event_type} suffix=" ms" />
          </section>
        </div>
      ) : null}
    </GuardedPage>
  );
}
