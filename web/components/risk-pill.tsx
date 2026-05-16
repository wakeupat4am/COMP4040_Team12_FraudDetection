import { RiskBucket } from "../lib/types";

export function RiskPill({ bucket }: { bucket: RiskBucket }) {
  return <span className={`pill ${bucket}`}>{bucket}</span>;
}
