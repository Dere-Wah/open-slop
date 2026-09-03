"use client";

import { useEffect, useState } from "react";
import { formatClock, formatCountdown } from "@/lib/format";

/**
 * The strip under the player: how long until the film loops, and the wall-clock
 * time it will happen, so a viewer can plan to come back. `endsAt` is already
 * corrected into the viewer's own clock by ShowApp, so the countdown stays
 * honest across a clock skew. While the show is between scenes the estimate is
 * a floor, shown as "at least".
 */
export function Countdown({
  endsAt,
  stalled,
}: {
  endsAt: number | null;
  stalled: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  if (endsAt === null) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-xs text-zinc-500">
        the next screening is loading…
      </div>
    );
  }

  const remaining = endsAt - now;
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-xs text-zinc-400">
      <span>
        {stalled && <span className="text-zinc-500">at least </span>}
        restarts in{" "}
        <span className="text-zinc-200">{formatCountdown(remaining)}</span>
      </span>
      <span className="text-zinc-500">this screening ends {formatClock(endsAt)}</span>
    </div>
  );
}
