"use client";

import { useEffect, useState } from "react";
import { formatClock, formatCountdown } from "@/lib/format";
import type { ShowStatus } from "@/lib/types";

/**
 * The strip under the player: how long until the film loops, and the wall-clock
 * time it will happen, so a viewer can plan to come back. `endsAt` is already
 * corrected into the viewer's own clock by ShowApp, so the countdown stays
 * honest across a clock skew. While the show is between scenes the estimate is
 * a floor, shown as "at least". When the next screening has already been
 * snapshotted at a different story sha, the strip says which sha comes up.
 */
export function Countdown({
  endsAt,
  stalled,
  status,
  sha,
  nextSha,
}: {
  endsAt: number | null;
  stalled: boolean;
  status?: ShowStatus;
  sha?: string;
  nextSha?: string;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  if (status === "downtime") {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-xs text-zinc-500">
        the projector is reconnecting — this screening restarts from the top when it is back
      </div>
    );
  }

  if (endsAt === null || status !== "live") {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-xs text-zinc-500">
        the next screening is loading…
      </div>
    );
  }

  const remaining = endsAt - now;
  const storyChanges = !!nextSha && !!sha && nextSha !== sha;
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-xs text-zinc-400">
      <span>
        {stalled && <span className="text-zinc-500">at least </span>}
        restarts in{" "}
        <span className="text-zinc-200">{formatCountdown(remaining)}</span>
        {storyChanges && (
          <span className="text-zinc-500">
            {" "}
            with the story at <span className="text-zinc-300">{nextSha}</span>
          </span>
        )}
      </span>
      <span className="text-zinc-500">this screening ends {formatClock(endsAt)}</span>
    </div>
  );
}
