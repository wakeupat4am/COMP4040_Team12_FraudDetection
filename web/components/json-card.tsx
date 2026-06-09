import { prettyJson } from "@/lib/formatters";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

export function JsonCard({ title, value }: { title: string; value: unknown }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-80 rounded-2xl border bg-muted/40">
          <pre className="min-w-0 overflow-x-auto p-4 font-mono text-xs leading-6 text-muted-foreground">
            {prettyJson(value)}
          </pre>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
