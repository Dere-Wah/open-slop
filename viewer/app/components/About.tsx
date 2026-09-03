"use client";

import { useMemo } from "react";
import { Avatar } from "./Avatar";
import {
  BookIcon,
  FilmIcon,
  GitPullRequestIcon,
  LawIcon,
  LinkIcon,
  PeopleIcon,
  ReactorMark,
  TagIcon,
} from "./Icons";
import { formatDuration } from "@/lib/format";
import { commitsUrl, pullsUrl, readmeUrl, repoUrl, treeUrl, type RepoRef } from "@/lib/github";
import { safeHttpUrl } from "@/lib/safeUrl";
import type { Contributor, Rundown, ShowState } from "@/lib/types";

const SITE = "openslop.live";
const TOPICS = ["open-source", "film", "world-model", "livestream", "community", "reactor", "livekit"];

/**
 * The right-hand column, in the shape of a GitHub repository's About panel:
 * what this is in one paragraph, the site link, topics, the two licences,
 * then the parts a repository sidebar would list — the current screening in
 * the place of a release, and the contributors, with avatars, assembled from
 * the rundown. Everything links out to GitHub; nothing is fetched from it.
 */
export function About({
  repo,
  rundown,
  state,
}: {
  repo: RepoRef;
  rundown: Rundown | null;
  state: ShowState | null;
}) {
  const contributors = useMemo(() => distinctContributors(rundown), [rundown]);
  const sceneCount = rundown?.episodes.reduce((count, episode) => count + episode.scenes.length, 0) ?? 0;

  return (
    <div className="flex flex-col divide-y divide-line">
      <section className="pb-4">
        <h2 className="mb-2 text-base font-semibold">About</h2>
        <p className="text-sm text-fg">
          A film that never stops playing, that anyone can write. The screenplay is the{" "}
          <code className="rounded bg-canvas-overlay px-1 py-0.5 font-mono text-xs">{repo.branch}</code>{" "}
          branch of this repository; a projector reads it, renders every scene with a video model,
          and screens the result here around the clock. Open a pull request, get it approved by
          other viewers, and your scene plays in the next screening.
        </p>
        <ul className="mt-3 flex flex-col gap-2 text-sm">
          <li className="flex items-center gap-2">
            <LinkIcon className="shrink-0 text-fg-muted" />
            <a href={`https://${SITE}`} className="gh-link font-semibold">
              {SITE}
            </a>
          </li>
          <li className="flex items-center gap-2">
            <BookIcon className="shrink-0 text-fg-muted" />
            <a href={readmeUrl(repo)} target="_blank" rel="noreferrer" className="text-fg-muted hover:text-accent">
              README · how to write a scene
            </a>
          </li>
          <li className="flex items-center gap-2">
            <GitPullRequestIcon className="shrink-0 text-fg-muted" />
            <a href={pullsUrl(repo)} target="_blank" rel="noreferrer" className="text-fg-muted hover:text-accent">
              Pull requests · scenes waiting for votes
            </a>
          </li>
          <li className="flex items-center gap-2">
            <LawIcon className="shrink-0 text-fg-muted" />
            <a href={treeUrl(repo)} target="_blank" rel="noreferrer" className="text-fg-muted hover:text-accent">
              CC BY-SA 4.0 (the film)
            </a>
          </li>
          <li className="flex items-center gap-2">
            <LawIcon className="shrink-0 text-fg-muted" />
            <a
              href={`${repoUrl(repo)}/tree/code`}
              target="_blank"
              rel="noreferrer"
              className="text-fg-muted hover:text-accent"
            >
              Apache-2.0 (the projector and this page)
            </a>
          </li>
        </ul>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TOPICS.map((topic) => (
            <a
              key={topic}
              href={`https://github.com/topics/${topic}`}
              target="_blank"
              rel="noreferrer"
              className="gh-topic"
            >
              {topic}
            </a>
          ))}
        </div>
      </section>

      <section className="py-4">
        <h2 className="mb-2 flex items-center gap-2 text-base font-semibold">
          Screening
          {typeof state?.screening === "number" && (
            <span className="gh-counter">nº {state.screening}</span>
          )}
        </h2>
        {rundown ? (
          <div className="flex items-start gap-2 text-sm">
            <TagIcon className="mt-0.5 shrink-0 text-success" />
            <div className="min-w-0">
              <a
                href={commitsUrl(repo)}
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-fg hover:text-accent"
              >
                story at <span className="font-mono">{rundown.sha}</span>
              </a>
              <p className="text-xs text-fg-muted">
                {rundown.episodes.length} episode{rundown.episodes.length === 1 ? "" : "s"} · {sceneCount}{" "}
                scene{sceneCount === 1 ? "" : "s"} · {formatDuration(rundown.total_seconds)}
              </p>
              {state?.next_sha && state.next_sha !== rundown.sha && (
                <p className="mt-1 text-xs text-fg-muted">
                  next: <span className="font-mono text-fg">{state.next_sha}</span>
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <FilmIcon className="shrink-0" /> waiting for the projector
          </p>
        )}
      </section>

      <section className="py-4">
        <h2 className="mb-2 text-base font-semibold">Sponsors</h2>
        <a
          href="https://reactor.inc"
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-2.5 text-sm"
          title="Reactor — the video model behind every scene"
        >
          <ReactorMark size={32} className="shrink-0 rounded-full ring-1 ring-line" />
          <span>
            <span className="block font-semibold text-fg group-hover:text-accent group-hover:underline">
              Reactor
            </span>
            <span className="block text-xs text-fg-muted">renders every scene, live</span>
          </span>
        </a>
      </section>

      <section className="pt-4">
        <h2 className="mb-2 flex items-center gap-2 text-base font-semibold">
          Contributors
          {contributors.length > 0 && <span className="gh-counter">{contributors.length}</span>}
        </h2>
        {contributors.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <PeopleIcon className="shrink-0" /> the credits arrive with the screening
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {contributors.slice(0, 40).map((person) => {
              const url = safeHttpUrl(person.url);
              const avatar = <Avatar name={person.name} url={person.url} size={32} />;
              return (
                <li key={person.name}>
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer" title={person.name}>
                      {avatar}
                    </a>
                  ) : (
                    avatar
                  )}
                </li>
              );
            })}
            {contributors.length > 40 && (
              <li className="self-center text-xs text-fg-muted">+{contributors.length - 40}</li>
            )}
          </ul>
        )}
        <a
          href={`${repoUrl(repo)}/graphs/contributors`}
          target="_blank"
          rel="noreferrer"
          className="gh-link mt-3 inline-block text-xs"
        >
          Everyone who ever wrote a line
        </a>
      </section>
    </div>
  );
}

function distinctContributors(rundown: Rundown | null): Contributor[] {
  if (!rundown) return [];
  const seen = new Map<string, Contributor>();
  for (const episode of rundown.episodes) {
    for (const scene of episode.scenes) {
      const people = scene.contributors?.length
        ? scene.contributors
        : [{ name: scene.author, url: scene.author_url }];
      for (const person of people) {
        if (person.name && !seen.has(person.name)) seen.set(person.name, person);
      }
    }
  }
  return [...seen.values()];
}
