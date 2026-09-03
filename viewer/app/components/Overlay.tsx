"use client";

import { EyeIcon, ReactorMark } from "./Icons";
import type { ShowState } from "@/lib/types";

/**
 * The little that is drawn over the picture while the film plays: an
 * "On air" chip top-left with how many are watching beside it (from the
 * room's own participant list), a "Running on Reactor" chip top-right (the model
 * rendering the picture, linking to reactor.inc), and an intermission ribbon
 * when the show is holding between scenes. Both chips are the same small,
 * translucent shape, so the badge reads as a broadcaster's bug rather than
 * an advert. What is playing, who wrote it, and its commit sit under the player
 * in the now-playing bar, where they are readable and clickable without
 * covering the frame. Everything else — loading, warming,
 * downtime, off air — is the curtain's, which replaces this overlay whenever
 * nothing is on air.
 */
export function Overlay({ state, viewers }: { state: ShowState | null; viewers: number | null }) {
  if (!state || state.status !== "live") return null;

  return (
    <>
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-1.5">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-black/60 px-2.5 py-1.5 text-xs font-semibold text-fg backdrop-blur">
          <span className="live-dot inline-block h-2 w-2 rounded-full bg-danger" />
          On air
        </span>
        {viewers !== null && viewers > 0 && (
          <span
            className="inline-flex items-center gap-1 rounded-md bg-black/60 px-2 py-1.5 text-xs font-medium text-fg-muted backdrop-blur"
            title={`${viewers} watching now`}
          >
            <EyeIcon size={14} />
            <span className="tabular-nums text-fg">{formatViewers(viewers)}</span>
          </span>
        )}
      </div>

      <a
        href="https://reactor.inc"
        target="_blank"
        rel="noreferrer"
        className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-black/60 py-1.5 pl-1.5 pr-2.5 text-xs font-medium text-fg-muted backdrop-blur transition-colors hover:text-fg hover:no-underline"
        title="The video model behind every scene"
      >
        <ReactorMark size={16} className="shrink-0" />
        <span>
          Running on <span className="font-semibold text-fg">Reactor</span>
        </span>
      </a>

      {state.stalled && (
        <div className="pointer-events-none absolute inset-x-0 top-3 flex justify-center">
          <span className="rounded-full bg-black/70 px-3 py-1 font-mono text-xs text-fg-muted backdrop-blur">
            holding for the next scene…
          </span>
        </div>
      )}
    </>
  );
}

/** 37 → "37", 1284 → "1.3k": a viewer count is a feel, not a ledger. */
function formatViewers(count: number): string {
  if (count < 1000) return String(count);
  const thousands = count / 1000;
  return `${thousands < 10 ? thousands.toFixed(1).replace(/\.0$/, "") : Math.round(thousands)}k`;
}
