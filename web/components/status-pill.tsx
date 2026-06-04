import { titleCase } from "@/lib/formatters";

const toneByValue: Record<string, string> = {
  block: "pill-danger",
  critical: "pill-danger",
  fraud: "pill-danger",
  review: "pill-warning",
  high: "pill-warning",
  reviewed: "pill-info",
  allow: "pill-success",
  low: "pill-success",
  legitimate: "pill-success",
  pending: "pill-neutral",
  medium: "pill-info",
};

export function StatusPill({ value }: { value: string }) {
  const toneClass = toneByValue[value] ?? "pill-neutral";
  return <span className={`status-pill ${toneClass}`}>{titleCase(value)}</span>;
}
