"use client";

import { safeHttpUrl } from "@/lib/safeUrl";

const FALLBACK_STORY_URL = "https://github.com/Dere-Wah/open-slop";

/**
 * The channel header: the brand, the connection state, the story sha on air,
 * and the two links out to GitHub. The screenplay itself is only ever read on
 * GitHub — the viewer shows what is playing and points there for the text.
 *
 * "Write the next scene" goes to the README of whichever branch the projector
 * says it is playing: the story URL arrives as `.../tree/<branch>`, and the
 * README lives at `.../blob/<branch>/README.md`.
 */
function contributeUrlOf(storyUrl: string | null): string {
  if (!storyUrl) return FALLBACK_STORY_URL;
  if (!storyUrl.includes("/tree/")) return storyUrl;
  return `${storyUrl.replace("/tree/", "/blob/")}/README.md`;
}
export function Header({
  status,
  sha,
  storyUrl,
}: {
  status: "connecting" | "live" | "offline";
  sha?: string;
  storyUrl?: string;
}) {
  const badge = {
    connecting: { label: "connecting", className: "bg-zinc-800 text-zinc-400" },
    live: { label: "live", className: "bg-active/20 text-active" },
    offline: {
      label: "offline — retrying",
      className: "bg-zinc-800 text-zinc-500",
    },
  }[status];

  const safeStoryUrl = safeHttpUrl(storyUrl);
  const contributeUrl = contributeUrlOf(safeStoryUrl);

  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">
          Open Slop
          {sha && (
            <span className="ml-2 font-mono text-xs font-normal text-zinc-500">
              @ {sha}
            </span>
          )}
        </h1>
        <p className="text-xs text-zinc-500">
          A film that never stops playing, that anyone can write.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <a
          href={safeStoryUrl ?? FALLBACK_STORY_URL}
          target="_blank"
          rel="noreferrer"
          className="rounded-md border border-zinc-800 px-3 py-1.5 font-mono text-xs text-zinc-300 hover:border-zinc-600"
        >
          read the screenplay
        </a>
        <a
          href={contributeUrl}
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-brand px-3 py-1.5 font-mono text-xs font-medium text-brand-fg hover:opacity-90"
        >
          write the next scene
        </a>
        <span
          className={`rounded-full px-3 py-1 font-mono text-xs ${badge.className}`}
        >
          {badge.label}
        </span>
      </div>
    </header>
  );
}
