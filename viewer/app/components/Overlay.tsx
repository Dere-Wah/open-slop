"use client";

import { ReactorMark } from "./Icons";
import type { ShowState } from "@/lib/types";

/**
 * The little that is drawn over the picture while the film plays: an
 * "On air" chip top-left, a "Running on Reactor" chip top-right (the model
 * rendering the picture, linking to reactor.inc), and an intermission ribbon
 * when the show is holding between scenes. Both chips are the same small,
 * translucent shape, so the badge reads as a broadcaster's bug rather than
 * an advert. What is playing, who wrote it, and its commit sit under the player
 * in the now-playing bar, where they are readable and clickable without
 * covering the frame. Everything else — loading, warming,
 * downtime, off air — is the curtain's, which replaces this overlay whenever
 * nothing is on air.
 */
export function Overlay({ state }: { state: ShowState | null }) {
  if (!state || state.status !== "live") return null;

  return (
    <>
      <div className="pointer-events-none absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-black/60 px-2.5 py-1.5 text-xs font-semibold text-fg backdrop-blur">
        <span className="live-dot inline-block h-2 w-2 rounded-full bg-danger" />
        On air
      </div>

      <a
        href="https://reactor.inc"
        target="_blank"
        rel="noreferrer"
        className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-black/60 py-1.5 pl-1.5 pr-2.5 text-xs font-medium text-fg-muted backdrop-blur transition-colors hover:text-fg"
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
