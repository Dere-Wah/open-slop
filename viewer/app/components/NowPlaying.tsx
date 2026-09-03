"use client";

import type { ReactNode } from "react";
import { Avatar } from "./Avatar";
import { GitCommitIcon } from "./Icons";
import { safeHttpUrl } from "@/lib/safeUrl";
import type { RundownScene, ShowState } from "@/lib/types";

/**
 * The bar under the player, shaped like the latest-commit row atop a GitHub
 * file list: who wrote the scene on air, which episode and scene it is, and
 * the commit it came from. When the next screening starts is the rundown's
 * footer, not this bar's — a ticking countdown here read as a deadline.
 *
 * While the curtain is down the same bar says what is being waited for — the
 * buffer filling, the projector reconnecting, or nothing at all.
 */
export function NowPlaying({
  state,
  scene,
  offAir,
}: {
  state: ShowState | null;
  scene: RundownScene | null;
  offAir: boolean;
}) {
  if (offAir || !state) {
    return (
      <Bar tone="muted">
        <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-fg-subtle" />
        <span className="text-fg-muted">
          <strong className="font-semibold text-fg">Off air.</strong> Nobody is projecting right
          now; the screenplay is still open on GitHub.
        </span>
      </Bar>
    );
  }

  if (state.status === "downtime") {
    return (
      <Bar tone="attention">
        <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-attention" />
        <span className="text-fg-muted">
          <strong className="font-semibold text-fg">Reconnecting the projector.</strong> This
          screening restarts from the top when it is back.
        </span>
      </Bar>
    );
  }

  if (state.status === "loading") {
    const buffered = state.buffered_seconds ?? 0;
    const target = state.target_seconds ?? 0;
    const left = Math.max(0, Math.ceil(target - buffered));
    const ratio = target > 0 ? Math.min(1, buffered / target) : 0;
    return (
      <Bar tone="accent">
        <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-accent" />
        <span className="min-w-0 flex-1 text-fg-muted">
          <strong className="font-semibold text-fg">
            {state.restart ? "Starting over." : "Preparing screening"}
            {!state.restart && typeof state.screening === "number" && <> nº {state.screening}.</>}
          </strong>{" "}
          The opening is being built —{" "}
          <span className="text-fg">{left}s</span> of movie still to go.
        </span>
        <span className="gh-progress hidden w-40 sm:block" aria-hidden="true">
          <span className="bg-accent" style={{ width: `${ratio * 100}%` }} />
        </span>
      </Bar>
    );
  }

  if (state.status !== "live") {
    return (
      <Bar tone="muted">
        <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-fg-subtle" />
        <span className="text-fg-muted">
          <strong className="font-semibold text-fg">Warming up.</strong>{" "}
          {state.detail || "Reading the story…"}
        </span>
      </Bar>
    );
  }

  const author = state.author ?? "someone";
  const authorUrl = safeHttpUrl(state.author_url);
  const commitUrl = safeHttpUrl(state.commit_url);
  const extra = scene ? Math.max(0, scene.contributors.length - 1) : 0;

  return (
    <Bar tone="default">
      <Avatar name={author} url={state.author_url} size={20} />
      <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        {authorUrl ? (
          <a href={authorUrl} target="_blank" rel="noreferrer" className="font-semibold text-fg hover:underline">
            {author}
          </a>
        ) : (
          <span className="font-semibold text-fg">{author}</span>
        )}
        {extra > 0 && (
          <span className="text-fg-muted" title="other people who wrote lines of this scene">
            +{extra}
          </span>
        )}
        <span className="truncate text-fg">
          {state.episode_title || state.episode_file || "untitled"}
          <span className="text-fg-muted">
            {" "}
            · scene {state.scene_number}/{state.scene_count}
          </span>
        </span>
        {state.commit && (
          <span className="inline-flex items-center gap-1 font-mono text-xs text-fg-muted">
            <GitCommitIcon size={14} />
            {commitUrl ? (
              <a href={commitUrl} target="_blank" rel="noreferrer" className="hover:text-accent hover:underline">
                {state.commit}
              </a>
            ) : (
              state.commit
            )}
          </span>
        )}
      </div>
    </Bar>
  );
}

function Bar({
  tone,
  children,
}: {
  tone: "default" | "muted" | "accent" | "attention";
  children: ReactNode;
}) {
  const border = {
    default: "border-line",
    muted: "border-line",
    accent: "border-accent-muted",
    attention: "border-attention/40",
  }[tone];
  return (
    <div
      className={`flex min-h-11 items-center gap-3 rounded-[6px] border ${border} bg-canvas-subtle px-3 py-2 text-sm`}
    >
      {children}
    </div>
  );
}