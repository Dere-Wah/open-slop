"use client";

import { useMemo, useRef, useState, type Ref } from "react";
import { Avatar } from "./Avatar";
import { ChevronRightIcon, ClockIcon, FileIcon, GitCommitIcon, ListIcon, SearchIcon } from "./Icons";
import { formatClock, formatDuration } from "@/lib/format";
import { blobUrl, type RepoRef } from "@/lib/github";
import { safeHttpUrl } from "@/lib/safeUrl";
import type { Rundown as RundownData, RundownEpisode, ShowState } from "@/lib/types";

/**
 * The film's table of contents, drawn like the file list on a GitHub
 * repository page: one row per episode, each expanding to its scenes, the
 * scene on air highlighted. Every episode links to its file and every scene
 * to its commit, so this is also the credits — who wrote what, assembled from
 * git, with GitHub avatars for the people who have one.
 *
 * It reads entirely off LiveKit room metadata; nothing here calls GitHub.
 *
 * Built to hold a long film. Rows render in pages of `PAGE` with a "show
 * more" footer, a filter narrows by title, file, or author, and the episode
 * on air is always within the rendered page, with a button that scrolls to
 * it — never on its own, so a reader is not yanked around when the scene
 * changes. A 200-episode film costs the page a few dozen rows, not
 * thousands. Room metadata has a size cap too: a very long film arrives with
 * its per-scene contributor lists stripped first and, past that, its tail
 * cut; the footer says so and points at the branch for the rest.
 *
 * The last line of the box is when the next screening starts — a wall-clock
 * time, given as "about" because a scene can hold between clips. It is the
 * one place the page says so: a ticking countdown read as a deadline.
 * `nextScreeningAt` is already in the viewer's own clock (ShowApp corrects the
 * projector's estimate for skew) and null while nothing is on air.
 */

const PAGE = 25;

export function Rundown({
  rundown,
  state,
  repo,
  nextScreeningAt = null,
  compact = false,
}: {
  rundown: RundownData | null;
  state: ShowState | null;
  repo: RepoRef;
  nextScreeningAt?: number | null;
  compact?: boolean;
}) {
  const [filter, setFilter] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const currentRef = useRef<HTMLLIElement | null>(null);

  const onAir = !!rundown && state?.status === "live" && state.screening === rundown.screening;
  const currentEpisode = onAir ? state?.episode_index : undefined;
  const currentScene = onAir ? state?.scene_number : undefined;

  const episodes = rundown?.episodes ?? [];
  const query = filter.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!query) return episodes;
    return episodes.filter((episode) => {
      if ((episode.title ?? "").toLowerCase().includes(query)) return true;
      if (episode.file.toLowerCase().includes(query)) return true;
      return episode.scenes.some(
        (scene) =>
          scene.author.toLowerCase().includes(query) ||
          scene.contributors.some((person) => person.name.toLowerCase().includes(query)),
      );
    });
  }, [episodes, query]);

  // The episode on air must be within the rendered page, and in view.
  const currentPosition =
    currentEpisode === undefined ? -1 : filtered.findIndex((episode) => episode.i === currentEpisode);
  const visible = Math.max(shown, currentPosition + 1);
  const rows = filtered.slice(0, visible);

  function toggle(file: string, isCurrent: boolean) {
    setOpen((prev) => ({ ...prev, [file]: !(prev[file] ?? isCurrent) }));
  }

  return (
    <section className="gh-box overflow-hidden" id="rundown">
      <header className="gh-box-header flex-wrap justify-between gap-y-2">
        <div className="flex items-center gap-2">
          <ListIcon className="text-fg-muted" />
          <h2 className="font-semibold">Rundown &amp; credits</h2>
          {rundown && (
            <span className="text-fg-muted">
              {episodes.length} episode{episodes.length === 1 ? "" : "s"} ·{" "}
              {formatDuration(rundown.total_seconds)}
            </span>
          )}
        </div>
        <div className="flex w-full items-center gap-2 sm:w-auto">
          {currentPosition >= 0 && (
            <button
              type="button"
              onClick={() => currentRef.current?.scrollIntoView({ block: "center", behavior: "smooth" })}
              className="gh-btn h-7 shrink-0 px-2.5 text-xs"
              title="scroll to the episode on air"
            >
              <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-success" />
              Now playing · {String((currentEpisode ?? 0) + 1).padStart(2, "0")}
            </button>
          )}
          {episodes.length > 6 && (
          <label className="relative block w-full sm:w-56">
            <SearchIcon
              size={14}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle"
            />
            <input
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value);
                setShown(PAGE);
              }}
              placeholder="Find an episode or author"
              className="gh-input h-7 pl-8 text-xs"
              aria-label="Filter episodes"
            />
          </label>
          )}
        </div>
      </header>

      {!rundown ? (
        <p className="px-4 py-6 text-center text-sm text-fg-muted">Loading the screenplay…</p>
      ) : rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-fg-muted">
          Nothing matches <span className="font-mono text-fg">{filter}</span>.
        </p>
      ) : (
        <ol className={compact ? "max-h-[60vh] overflow-y-auto" : ""}>
          {rows.map((episode) => {
            const isCurrent = currentEpisode === episode.i;
            return (
              <EpisodeRow
                key={episode.file}
                ref={isCurrent ? currentRef : null}
                episode={episode}
                repo={repo}
                isCurrent={isCurrent}
                currentScene={isCurrent ? currentScene : undefined}
                expanded={open[episode.file] ?? isCurrent}
                onToggle={() => toggle(episode.file, isCurrent)}
              />
            );
          })}
        </ol>
      )}

      {rundown && (rows.length < filtered.length || rundown.truncated) && (
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line bg-canvas-subtle px-4 py-2 text-xs text-fg-muted">
          {rows.length < filtered.length ? (
            <button
              type="button"
              onClick={() => setShown((value) => value + PAGE)}
              className="gh-link font-medium"
            >
              Show {Math.min(PAGE, filtered.length - rows.length)} more of {filtered.length}
            </button>
          ) : (
            <span />
          )}
          {rundown.truncated && (
            <span>
              The movie is longer than fits here —{" "}
              <a
                href={safeHttpUrl(rundown.story_url) ?? "#"}
                target="_blank"
                rel="noreferrer"
                className="gh-link"
              >
                the rest is on the branch
              </a>
              .
            </span>
          )}
        </footer>
      )}

      {rundown && nextScreeningAt !== null && (
        <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 border-t border-line px-4 py-2.5 text-xs text-fg-muted">
          <ClockIcon size={14} className="shrink-0" />
          <span>
            The next screening starts {state?.stalled ? "no earlier than" : "at"} about{" "}
            <span className="font-semibold text-fg">{formatClock(nextScreeningAt)}</span>
            {state?.next_sha && state.next_sha !== rundown.sha && (
              <>
                , with the story at{" "}
                <span className="font-mono text-fg">{state.next_sha}</span>
              </>
            )}
            .
          </span>
        </p>
      )}
    </section>
  );
}

function EpisodeRow({
  ref,
  episode,
  repo,
  isCurrent,
  currentScene,
  expanded,
  onToggle,
}: {
  ref: Ref<HTMLLIElement> | null;
  episode: RundownEpisode;
  repo: RepoRef;
  isCurrent: boolean;
  currentScene?: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const authors = distinctAuthors(episode);
  const lastCommit = episode.scenes[episode.scenes.length - 1]?.commit;
  return (
    <li
      ref={ref}
      className={`border-t border-line-muted first:border-t-0 ${isCurrent ? "bg-accent-subtle" : ""}`}
    >
      <div className="flex items-center gap-3 px-3 py-2 hover:bg-canvas-subtle sm:px-4">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <ChevronRightIcon
            size={14}
            className={`shrink-0 text-fg-subtle transition-transform ${expanded ? "rotate-90" : ""}`}
          />
          <span className="w-7 shrink-0 font-mono text-xs text-fg-muted">
            {String(episode.i + 1).padStart(2, "0")}
          </span>
          <span
            className={`truncate text-sm ${isCurrent ? "font-semibold text-fg" : "text-fg"}`}
          >
            {episode.title || episode.file}
          </span>
          {isCurrent && (
            <span className="gh-counter shrink-0 bg-success-subtle text-success">on air</span>
          )}
        </button>
        <span className="hidden shrink-0 items-center -space-x-1.5 sm:flex" title={authors.join(", ")}>
          {authors.slice(0, 4).map((name) => (
            <Avatar key={name} name={name} size={20} />
          ))}
          {authors.length > 4 && (
            <span className="gh-avatar inline-flex h-5 items-center justify-center bg-canvas-overlay px-1 text-[10px] text-fg-muted">
              +{authors.length - 4}
            </span>
          )}
        </span>
        <span className="hidden w-24 shrink-0 items-center justify-end gap-1 font-mono text-xs text-fg-muted md:flex">
          {lastCommit && <GitCommitIcon size={14} className="text-fg-subtle" />}
          {lastCommit}
        </span>
        <span className="w-14 shrink-0 text-right font-mono text-xs text-fg-muted">
          {formatDuration(episode.seconds)}
        </span>
      </div>

      {expanded && (
        <ol className="border-t border-line-muted bg-canvas-inset/40 py-1">
          {episode.scenes.map((scene) => {
            const active = currentScene === scene.n;
            const authorUrl = safeHttpUrl(scene.author_url);
            const commitUrl = safeHttpUrl(scene.commit_url);
            const extra = Math.max(0, (scene.contributors?.length ?? 0) - 1);
            return (
              <li
                key={scene.n}
                className={`flex items-center gap-3 py-1.5 pl-[3.25rem] pr-3 text-sm sm:pl-[3.75rem] sm:pr-4 ${
                  active ? "border-l-2 border-accent bg-accent-subtle" : "border-l-2 border-transparent"
                }`}
              >
                <span className="w-7 shrink-0 font-mono text-xs text-fg-subtle">{scene.n}</span>
                <Avatar name={scene.author} url={scene.author_url} size={16} />
                <span className="flex min-w-0 flex-1 items-baseline gap-1.5">
                  {authorUrl ? (
                    <a
                      href={authorUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate text-fg hover:text-accent"
                    >
                      {scene.author}
                    </a>
                  ) : (
                    <span className="truncate text-fg">{scene.author}</span>
                  )}
                  {extra > 0 && (
                    <span className="text-xs text-fg-muted" title="others who wrote lines of this scene">
                      +{extra}
                    </span>
                  )}
                  {active && <span className="text-xs text-success">· playing</span>}
                </span>
                <span className="hidden w-24 shrink-0 items-center justify-end gap-1 font-mono text-xs text-fg-muted md:flex">
                  {scene.commit &&
                    (commitUrl ? (
                      <a
                        href={commitUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:text-accent"
                      >
                        {scene.commit}
                      </a>
                    ) : (
                      scene.commit
                    ))}
                </span>
                <span className="w-14 shrink-0 text-right font-mono text-xs text-fg-muted">
                  {formatDuration(scene.seconds)}
                </span>
              </li>
            );
          })}
          <li className="flex items-center gap-2 py-1.5 pl-[3.25rem] pr-3 text-xs sm:pl-[3.75rem] sm:pr-4">
            <FileIcon size={14} className="text-fg-subtle" />
            <a
              href={blobUrl(repo, episode.file)}
              target="_blank"
              rel="noreferrer"
              className="gh-link font-mono"
            >
              {episode.file}
            </a>
          </li>
        </ol>
      )}
    </li>
  );
}

function distinctAuthors(episode: RundownEpisode): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const scene of episode.scenes) {
    const contributors = scene.contributors ?? [];
    for (const person of contributors.length ? contributors : [{ name: scene.author }]) {
      if (person.name && !seen.has(person.name)) {
        seen.add(person.name);
        names.push(person.name);
      }
    }
  }
  return names;
}
