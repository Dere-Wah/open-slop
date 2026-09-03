"use client";

import { formatDuration } from "@/lib/format";
import type { Rundown as RundownData, RundownEpisode, ShowState } from "@/lib/types";

/**
 * The ordered episode list, read entirely off LiveKit room metadata — no call
 * to GitHub. Each episode expands to its scenes; the scene on air is
 * highlighted. Every episode links to its file and every scene to its commit,
 * so this panel is also the credits: who wrote what, assembled from git.
 */
export function Rundown({
  rundown,
  state,
}: {
  rundown: RundownData | null;
  state: ShowState | null;
}) {
  if (!rundown) {
    return (
      <aside className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <h2 className="text-sm font-medium">Rundown</h2>
        <p className="mt-2 text-xs text-zinc-600">loading the screenplay…</p>
      </aside>
    );
  }

  const onAir = state?.screening === rundown.screening;
  const currentEpisode = onAir ? state?.episode_index : undefined;
  const currentScene = onAir ? state?.scene_number : undefined;
  const blobBase = rundown.story_url.replace("/tree/", "/blob/");

  return (
    <aside className="flex min-h-0 flex-col rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="border-b border-zinc-800 px-4 py-3">
        <h2 className="text-sm font-medium">Rundown &amp; credits</h2>
        <p className="mt-0.5 text-xs text-zinc-500">
          {rundown.episodes.length} episode
          {rundown.episodes.length === 1 ? "" : "s"} ·{" "}
          {formatDuration(rundown.total_seconds)} · every scene links to its commit
        </p>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {rundown.episodes.map((episode) => (
          <EpisodeRow
            key={episode.file}
            episode={episode}
            blobBase={blobBase}
            isCurrent={currentEpisode === episode.i}
            currentScene={currentEpisode === episode.i ? currentScene : undefined}
          />
        ))}
      </div>
    </aside>
  );
}

function EpisodeRow({
  episode,
  blobBase,
  isCurrent,
  currentScene,
}: {
  episode: RundownEpisode;
  blobBase: string;
  isCurrent: boolean;
  currentScene?: number;
}) {
  const authors = distinctAuthors(episode);
  return (
    <details open={isCurrent} className="rounded-lg px-2 py-1">
      <summary className="cursor-pointer list-none">
        <span className="flex items-baseline justify-between gap-2">
          <span className="flex items-baseline gap-2 truncate">
            <span
              className={`font-mono text-xs ${isCurrent ? "text-brand" : "text-zinc-500"}`}
            >
              {String(episode.i + 1).padStart(2, "0")}
            </span>
            <span
              className={`truncate text-sm ${isCurrent ? "text-zinc-100" : "text-zinc-300"}`}
            >
              {episode.title || episode.file}
            </span>
          </span>
          <span className="shrink-0 font-mono text-[11px] text-zinc-600">
            {formatDuration(episode.seconds)}
          </span>
        </span>
        {authors.length > 0 && (
          <span className="mt-0.5 block truncate pl-6 font-mono text-[11px] text-zinc-600">
            by {authors.join(", ")}
          </span>
        )}
      </summary>
      <ol className="mt-1 space-y-1 pl-6">
        {episode.scenes.map((scene) => {
          const extra = Math.max(0, scene.contributors.length - 1);
          const active = currentScene === scene.n;
          return (
            <li
              key={scene.n}
              className={`flex items-baseline justify-between gap-2 rounded px-2 py-0.5 text-xs ${
                active ? "bg-brand/10" : ""
              }`}
            >
              <span className="flex items-baseline gap-2 truncate">
                <span className="font-mono text-zinc-600">{scene.n}.</span>
                {scene.author_url ? (
                  <a
                    href={scene.author_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-zinc-300 hover:text-brand"
                  >
                    {scene.author}
                  </a>
                ) : (
                  <span className="text-zinc-400">{scene.author}</span>
                )}
                {extra > 0 && <span className="text-zinc-600">+{extra}</span>}
              </span>
              <span className="flex shrink-0 items-baseline gap-2 font-mono text-[11px] text-zinc-600">
                <span>{formatDuration(scene.seconds)}</span>
                {scene.commit &&
                  (scene.commit_url ? (
                    <a
                      href={scene.commit_url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-zinc-300"
                    >
                      {scene.commit}
                    </a>
                  ) : (
                    <span>{scene.commit}</span>
                  ))}
              </span>
            </li>
          );
        })}
      </ol>
      <a
        href={`${blobBase}/${episode.file}`}
        target="_blank"
        rel="noreferrer"
        className="mt-1 block pl-6 font-mono text-[11px] text-zinc-600 hover:text-zinc-400"
      >
        {episode.file} ↗
      </a>
    </details>
  );
}

function distinctAuthors(episode: RundownEpisode): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const scene of episode.scenes) {
    for (const person of scene.contributors.length ? scene.contributors : [{ name: scene.author }]) {
      if (person.name && !seen.has(person.name)) {
        seen.add(person.name);
        names.push(person.name);
      }
    }
  }
  return names;
}
