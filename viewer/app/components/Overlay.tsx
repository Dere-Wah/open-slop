"use client";

import { safeHttpUrl } from "@/lib/safeUrl";
import type { RundownScene, ShowState } from "@/lib/types";

/**
 * What is on air, drawn over the player. The now-playing card names the
 * episode, the scene, and the author, and links the commit. When the scene
 * has several authors it says so (`@alice +3`), reading the count off the
 * rundown. When the show is warming up, between scenes, or has lost the model
 * and is about to restart the screening, an intermission ribbon takes over.
 */
export function Overlay({
  state,
  scene,
}: {
  state: ShowState | null;
  scene: RundownScene | null;
}) {
  if (!state || state.status === "warming") {
    return (
      <Intermission
        line={state?.detail || "reading the story…"}
        sub={state?.sha ? `now at ${state.sha}` : undefined}
      />
    );
  }

  if (state.status === "downtime") {
    return (
      <Intermission
        line="we lost the projector — the screening restarts from the top"
        sub={state.detail || undefined}
      />
    );
  }

  const extra = scene ? Math.max(0, scene.contributors.length - 1) : 0;
  const author = state.author ?? "someone";
  const authorUrl = safeHttpUrl(state.author_url);
  const commitUrl = safeHttpUrl(state.commit_url);

  return (
    <>
      <div className="absolute left-3 top-3 max-w-[75%] rounded-lg bg-zinc-950/70 px-3 py-2 backdrop-blur">
        <div className="flex items-baseline gap-2">
          <span className="truncate text-sm font-medium text-zinc-100">
            {state.episode_title || state.episode_file || "untitled"}
          </span>
          <span className="shrink-0 font-mono text-xs text-zinc-400">
            scene {state.scene_number}/{state.scene_count}
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-2 font-mono text-xs text-zinc-400">
          {authorUrl ? (
            <a
              href={authorUrl}
              target="_blank"
              rel="noreferrer"
              className="text-brand hover:underline"
            >
              {author}
            </a>
          ) : (
            <span className="text-brand">{author}</span>
          )}
          {extra > 0 && <span className="text-zinc-500">+{extra}</span>}
          {state.commit &&
            (commitUrl ? (
              <a
                href={commitUrl}
                target="_blank"
                rel="noreferrer"
                className="text-zinc-500 hover:text-zinc-300"
              >
                {state.commit}
              </a>
            ) : (
              <span className="text-zinc-600">{state.commit}</span>
            ))}
        </div>
      </div>

      {state.stalled && (
        <Intermission line="holding for the next scene…" />
      )}
    </>
  );
}

function Intermission({ line, sub }: { line: string; sub?: string }) {
  return (
    <div className="absolute inset-x-0 top-3 flex flex-col items-center gap-1">
      <span className="rounded-full bg-zinc-950/80 px-3 py-1 font-mono text-xs text-zinc-300 backdrop-blur">
        {line}
      </span>
      {sub && <span className="font-mono text-[11px] text-zinc-500">{sub}</span>}
    </div>
  );
}
