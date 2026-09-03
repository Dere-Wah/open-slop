"use client";

import type { ReactNode } from "react";
import { AgentButton } from "./AgentButton";
import {
  BookIcon,
  GitBranchIcon,
  GitPullRequestIcon,
  MarkGithubIcon,
  PlayIcon,
  RepoIcon,
  StarIcon,
} from "./Icons";
import {
  commitsUrl,
  contributingUrl,
  pullsUrl,
  repoUrl,
  treeUrl,
  type RepoRef,
} from "@/lib/github";

export type Connection = "connecting" | "live" | "offline";

function ConnectionPill({ connection }: { connection: Connection }) {
  const spec = {
    connecting: { label: "connecting to the room", dot: "bg-fg-subtle" },
    live: { label: "connected", dot: "bg-success" },
    offline: { label: "offline · retrying", dot: "bg-danger" },
  }[connection];
  return (
    <span className="gh-label gap-1.5 px-2.5" title="your connection to the broadcast">
      <span className={`inline-block h-2 w-2 rounded-full ${spec.dot}`} />
      {spec.label}
    </span>
  );
}

/**
 * The top of the page, laid out the way GitHub lays out a repository: the
 * `owner / repo` title row with its `Public` label and action buttons, then
 * the underline nav. The nav's first tab is this page (the screening); the
 * rest link out to the parts of the repository a viewer might want next — the
 * screenplay itself, the open pull requests where scenes are voted in, and
 * the commit log that is the film's credits in full. While the page is not
 * connected to the room, a pill at the nav's right end says so.
 */
export function RepoHeader({
  repo,
  sha,
  onAir,
  connection,
}: {
  repo: RepoRef;
  sha?: string;
  onAir: boolean;
  connection: Connection;
}) {
  return (
    <div className="border-b border-line bg-canvas-inset">
      <div className="mx-auto max-w-[1440px] px-4 pt-5 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <RepoIcon className="shrink-0 text-fg-muted" />
            <h1 className="flex min-w-0 flex-wrap items-center gap-x-1 text-xl leading-7">
              <a
                href={`https://github.com/${repo.owner}`}
                target="_blank"
                rel="noreferrer"
                className="gh-link truncate"
              >
                {repo.owner}
              </a>
              <span className="text-fg-muted">/</span>
              <a
                href={repoUrl(repo)}
                target="_blank"
                rel="noreferrer"
                className="gh-link truncate font-semibold"
              >
                {repo.repo}
              </a>
            </h1>
            <span className="gh-label ml-1">Public</span>
            {sha && (
              <span
                className="hidden items-center gap-1 font-mono text-xs text-fg-muted md:inline-flex"
                title={onAir ? "the commit on air" : "the commit being prepared"}
              >
                <GitBranchIcon size={14} />
                {repo.branch}
                <span className="text-fg-subtle">@</span>
                {sha}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a href={treeUrl(repo)} target="_blank" rel="noreferrer" className="gh-btn">
              <BookIcon className="text-fg-muted" />
              <span className="hidden sm:inline">Read the screenplay</span>
              <span className="sm:hidden">Screenplay</span>
            </a>
            <a
              href={contributingUrl(repo)}
              target="_blank"
              rel="noreferrer"
              className="gh-btn gh-btn-primary"
              title="Add or edit a scene in three steps"
            >
              <GitPullRequestIcon />
              <span className="hidden sm:inline">Write the next scene</span>
              <span className="sm:hidden">Write a scene</span>
            </a>
            <a
              href={repoUrl(repo)}
              target="_blank"
              rel="noreferrer"
              className="gh-btn"
              title="Star the repository on GitHub"
            >
              <StarIcon className="text-fg-muted" />
              <span>Star</span>
            </a>
            <AgentButton repo={repo} />
          </div>
        </div>

        <nav className="gh-underline-nav -mb-px mt-2 flex gap-2 overflow-x-auto" aria-label="Repository">
          <a href="/" aria-current="page">
            <PlayIcon className="text-fg-muted" />
            Screening
            <span
              className={`gh-counter ${onAir ? "bg-success-subtle text-success" : ""}`}
              title={onAir ? "on air" : "off air"}
            >
              {onAir ? "on air" : "off air"}
            </span>
          </a>
          <NavLink href={treeUrl(repo)} icon={<BookIcon className="text-fg-muted" />}>
            Screenplay
          </NavLink>
          <NavLink href={pullsUrl(repo)} icon={<GitPullRequestIcon className="text-fg-muted" />}>
            Pull requests
          </NavLink>
          <NavLink href={commitsUrl(repo)} icon={<GitBranchIcon className="text-fg-muted" />}>
            Commits
          </NavLink>
          <NavLink href={repoUrl(repo)} icon={<MarkGithubIcon className="text-fg-muted" />}>
            GitHub
          </NavLink>
          {connection !== "live" && (
            <span className="ml-auto flex items-center pl-2">
              <ConnectionPill connection={connection} />
            </span>
          )}
        </nav>
      </div>
    </div>
  );
}

function NavLink({ href, icon, children }: { href: string; icon: ReactNode; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-fg-muted">
      {icon}
      {children}
      <span aria-hidden="true" className="text-fg-subtle">
        ↗
      </span>
    </a>
  );
}
