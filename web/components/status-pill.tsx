import { titleCase } from "@/lib/formatters";
import { Badge } from "@/components/ui/badge";

const toneByValue: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  allow: "default",
  legitimate: "default",
  low: "default",
  block: "destructive",
  critical: "destructive",
  fraud: "destructive",
  high: "destructive",
  medium: "secondary",
  pending: "outline",
  review: "secondary",
  reviewed: "outline",
};

export function StatusPill({ value }: { value: string }) {
  return <Badge variant={toneByValue[value] ?? "outline"}>{titleCase(value)}</Badge>;
}
