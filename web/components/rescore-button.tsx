"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { rescoreCase } from "../lib/api";

export function RescoreButton({ eventId }: { eventId: string }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <div className="button-row">
      <button
        className="button secondary"
        disabled={isPending}
        onClick={() => {
          setMessage(null);
          startTransition(async () => {
            try {
              await rescoreCase(eventId);
              setMessage("Case rescored.");
              router.refresh();
            } catch (error) {
              setMessage(error instanceof Error ? error.message : "Failed to rescore case.");
            }
          });
        }}
      >
        {isPending ? "Rescoring..." : "Rescore Case"}
      </button>
      {message ? <p className="muted">{message}</p> : null}
    </div>
  );
}
