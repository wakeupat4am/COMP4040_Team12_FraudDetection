import { InboxIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card className="border-dashed bg-card/60">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-10 text-center">
        <div className="flex size-10 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <InboxIcon className="size-5" />
        </div>
        <div className="space-y-1">
          <h3 className="font-heading text-base font-medium">{title}</h3>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
