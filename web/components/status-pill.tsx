import { CaseStatus } from "../lib/types";

export function StatusPill({ status }: { status: CaseStatus }) {
  return <span className={`pill ${status === "reviewed" ? "reviewed" : "medium"}`}>{status}</span>;
}
