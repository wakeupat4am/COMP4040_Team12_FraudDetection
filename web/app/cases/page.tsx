"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, FilterIcon, RotateCcwIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { GuardedPage } from "@/components/guarded-page";
import { StatusPill } from "@/components/status-pill";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, listCases } from "@/lib/api";
import { formatDateTime, formatScore } from "@/lib/formatters";
import { useAuthedRequest } from "@/hooks/use-authed-request";
import type { CaseListFilters, CaseListResponse } from "@/lib/types";

const DEFAULT_FILTERS: CaseListFilters = {
  page: 1,
  page_size: 10,
  risk_bucket: "",
  decision: "",
  review_status: "",
  created_from: "",
  created_to: "",
};

const riskOptions = [
  { value: "all", label: "All risks" },
  { value: "low", label: "Low" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const decisionOptions = [
  { value: "all", label: "All decisions" },
  { value: "allow", label: "Allow" },
  { value: "review", label: "Review" },
  { value: "block", label: "Block" },
];

const reviewOptions = [
  { value: "all", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "reviewed", label: "Reviewed" },
];

function normalizeSelect(value: string): string {
  return value === "all" ? "" : value;
}

function QueueTableSkeleton() {
  return (
    <div className="grid gap-2">
      {Array.from({ length: 6 }).map((_, index) => (
        <Skeleton key={index} className="h-11 w-full" />
      ))}
    </div>
  );
}

export default function CasesPage() {
  const { run } = useAuthedRequest();
  const [filters, setFilters] = useState<CaseListFilters>(DEFAULT_FILTERS);
  const [activeFilters, setActiveFilters] = useState<CaseListFilters>(DEFAULT_FILTERS);
  const [data, setData] = useState<CaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCases() {
      setLoading(true);
      setError(null);
      try {
        const response = await run((token) => listCases(token, activeFilters));
        if (!cancelled) {
          setData(response);
        }
      } catch (caughtError) {
        if (!cancelled) {
          setError(
            caughtError instanceof ApiError
              ? caughtError.message
              : caughtError instanceof Error
                ? caughtError.message
                : "Unable to load cases.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadCases();
    return () => {
      cancelled = true;
    };
  }, [activeFilters, run]);

  function updateFilter(key: keyof CaseListFilters, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveFilters({ ...filters, page: 1 });
  }

  function resetFilters() {
    setFilters(DEFAULT_FILTERS);
    setActiveFilters(DEFAULT_FILTERS);
  }

  function changePage(nextPage: number) {
    setFilters((current) => ({ ...current, page: nextPage }));
    setActiveFilters((current) => ({ ...current, page: nextPage }));
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const currentPage = data?.page ?? activeFilters.page ?? 1;

  return (
    <GuardedPage
      title="Case Queue"
      description="Start here: filter the backlog, identify risky transactions, and open a case for analyst action."
    >
      <Card>
        <CardHeader>
          <CardTitle>Queue filters</CardTitle>
          <CardDescription>Use narrow filters for triage, then open a transaction for full evidence and actions.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" onSubmit={applyFilters}>
            <div className="grid gap-2">
              <Label htmlFor="risk_bucket">Risk bucket</Label>
              <Select
                value={String(filters.risk_bucket || "all")}
                onValueChange={(value) => updateFilter("risk_bucket", normalizeSelect(value ?? "all"))}
              >
                <SelectTrigger id="risk_bucket" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {riskOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="decision">Decision</Label>
              <Select
                value={String(filters.decision || "all")}
                onValueChange={(value) => updateFilter("decision", normalizeSelect(value ?? "all"))}
              >
                <SelectTrigger id="decision" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {decisionOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="review_status">Review status</Label>
              <Select
                value={String(filters.review_status || "all")}
                onValueChange={(value) => updateFilter("review_status", normalizeSelect(value ?? "all"))}
              >
                <SelectTrigger id="review_status" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {reviewOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="page_size">Page size</Label>
              <Select
                value={String(filters.page_size ?? 10)}
                onValueChange={(value) => updateFilter("page_size", Number(value ?? 10))}
              >
                <SelectTrigger id="page_size" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[10, 25, 50].map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size} rows
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2 md:col-span-1 xl:col-span-2">
              <Label htmlFor="created_from">Created from</Label>
              <Input
                id="created_from"
                type="datetime-local"
                value={String(filters.created_from ?? "")}
                onChange={(event) => updateFilter("created_from", event.target.value)}
              />
            </div>

            <div className="grid gap-2 md:col-span-1 xl:col-span-2">
              <Label htmlFor="created_to">Created to</Label>
              <Input
                id="created_to"
                type="datetime-local"
                value={String(filters.created_to ?? "")}
                onChange={(event) => updateFilter("created_to", event.target.value)}
              />
            </div>

            <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4">
              <Button type="submit" disabled={loading}>
                <FilterIcon className="size-4" />
                Apply filters
              </Button>
              <Button type="button" variant="outline" onClick={resetFilters} disabled={loading}>
                <RotateCcwIcon className="size-4" />
                Reset
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <CardTitle>Queue results</CardTitle>
              <CardDescription>
                {data ? `${data.total} case${data.total === 1 ? "" : "s"} matched the current filters.` : "Loading queue state."}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={loading || currentPage <= 1}
                onClick={() => changePage(currentPage - 1)}
              >
                <ArrowLeftIcon className="size-4" />
                Previous
              </Button>
              <span className="min-w-20 text-center text-sm text-muted-foreground">
                {currentPage} / {totalPages}
              </span>
              <Button
                type="button"
                variant="outline"
                disabled={loading || currentPage >= totalPages}
                onClick={() => changePage(currentPage + 1)}
              >
                Next
                <ArrowRightIcon className="size-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to load queue</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {loading ? <QueueTableSkeleton /> : null}

          {!loading && data && data.items.length === 0 ? (
            <EmptyState
              title="No cases matched these filters"
              description="Try a wider date range or reset the decision and review-status filters."
            />
          ) : null}

          {!loading && data && data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead>Review</TableHead>
                  <TableHead>Last scored</TableHead>
                  <TableHead className="min-w-64">Latest note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((item) => (
                  <TableRow key={item.transaction_id}>
                    <TableCell className="font-mono text-xs">
                      <Link
                        className="font-medium text-primary underline-offset-4 hover:underline"
                        href={`/cases/${encodeURIComponent(item.transaction_id)}`}
                      >
                        {item.transaction_id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-medium">{formatScore(item.final_risk_score)}</TableCell>
                    <TableCell>
                      <StatusPill value={item.risk_bucket} />
                    </TableCell>
                    <TableCell>
                      <StatusPill value={item.decision} />
                    </TableCell>
                    <TableCell>
                      <StatusPill value={item.review_status} />
                    </TableCell>
                    <TableCell>{formatDateTime(item.last_scored_at)}</TableCell>
                    <TableCell className="max-w-80 whitespace-normal text-muted-foreground">
                      {item.latest_note ?? "No analyst note yet."}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </GuardedPage>
  );
}
