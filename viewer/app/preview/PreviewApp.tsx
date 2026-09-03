"use client";

import { useMemo, useState } from "react";
import { ShowPage } from "../ShowPage";
import type { ChatEntry } from "../components/Chat";
import type { Rundown, RundownEpisode, RundownScene, ShowState } from "@/lib/types";

/** Fixtures shaped exactly like the projector's two payloads. */

const STORY_URL = "https://github.com/Dere-Wah/open-slop/tree/story";
const NAMES = ["@Dere-Wah", "@torvalds", "@gaearon", "Ada Lovelace", "@octocat", "@defunkt", "Someone"];
const WORDS = [
  "The Arrival", "What the Keeper Saw", "The Signal", "Low Tide", "A Letter Never Sent",
  "The Long Corridor", "Night Market", "Salt", "The Cartographer's Daughter", "Interference",
  "Blue Hour", "The Understudy", "Static", "The Weight of a Name", "Ferry at Dawn",
];

function scene(n: number, seed: number): RundownScene {
  const author = NAMES[seed % NAMES.length];
  const login = author.startsWith("@") ? author.slice(1) : null;
  const co = NAMES[(seed * 7 + 3) % NAMES.length];
  const coLogin = co.startsWith("@") ? co.slice(1) : null;
  const sha = (0x100000 + seed * 2654435761) .toString(16).slice(0, 7);
  return {
    n,
    seconds: [8, 10.125, 12.25][seed % 3],
    author,
    author_url: login ? `https://github.com/${login}` : null,
    commit: sha,
    commit_url: `https://github.com/Dere-Wah/open-slop/commit/${sha}`,
    contributors:
      seed % 4 === 0
        ? [
            { name: author, url: login ? `https://github.com/${login}` : null },
            { name: co, url: coLogin ? `https://github.com/${coLogin}` : null },
          ]
        : [{ name: author, url: login ? `https://github.com/${login}` : null }],
  };
}

function film(count: number): Rundown {
  const episodes: RundownEpisode[] = [];
  for (let i = 0; i < count; i++) {
    const scenes = Array.from({ length: 2 + (i % 3) }, (_, k) => scene(k + 1, i * 5 + k));
    const title = `${WORDS[i % WORDS.length]}${i >= WORDS.length ? ` ${Math.floor(i / WORDS.length) + 1}` : ""}`;
    episodes.push({
      i,
      file: `${String((i + 1) * 10).padStart(4, "0")}-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`,
      title,
      seconds: scenes.reduce((sum, s) => sum + s.seconds, 0),
      scenes,
    });
  }
  return {
    v: 1,
    screening: 12,
    sha: "d5b84a2",
    story_url: STORY_URL,
    total_seconds: episodes.reduce((sum, e) => sum + e.seconds, 0),
    episodes,
    truncated: count > 150,
  };
}

const CHATTER = [
  ["@mira", "the lighthouse shot is gorgeous"],
  ["@kb", "who wrote scene 2?? that eye"],
  ["@tomasz", "seed 481517 again please, that one was perfect"],
  ["@ren", "https://github.com/Dere-Wah/open-slop/pull/41 is up, needs one more approve"],
  ["@ada", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
  ["@mira", "ok the keeper's face in scene 3 is going to haunt me"],
] as const;

function chatter(count: number): ChatEntry[] {
  const entries: ChatEntry[] = [
    { id: 1, author: "show", text: "Screening nº 12 is on air: 3 episodes, 1m 25s. Story at d5b84a2." },
  ];
  for (let i = 0; entries.length < count; i++) {
    const [author, text] = CHATTER[i % CHATTER.length];
    entries.push({ id: entries.length + 1, author, text: i < CHATTER.length ? text : `${text} (${i})` });
  }
  return entries;
}

export function PreviewApp({
  state,
  episodes,
  chatCount = 3,
}: {
  state: string;
  episodes: number;
  chatCount?: number;
}) {
  const rundown = useMemo(() => film(episodes), [episodes]);
  const [chat, setChat] = useState<ChatEntry[]>(() => chatter(chatCount));

  const current = rundown.episodes[Math.min(1, rundown.episodes.length - 1)];
  const currentScene = current.scenes[Math.min(1, current.scenes.length - 1)];
  const now = Date.now();

  const showState: ShowState | null = (() => {
    switch (state) {
      case "loading":
        return {
          v: 1, topic: "state", status: "loading", screening: 12, sha: "d5b84a2",
          episode_title: rundown.episodes[0].title ?? undefined,
          buffered_seconds: 12.25, target_seconds: 30, film_seconds: rundown.total_seconds,
          scene_total: rundown.episodes.reduce((n, e) => n + e.scenes.length, 0), restart: false, now,
        };
      case "intermission":
        return {
          v: 1, topic: "state", status: "intermission", ended_screening: 12, screening: 13,
          sha: "a1b2c3d", episode_title: rundown.episodes[0].title ?? undefined,
          resumes_at: now + 14_000, hold_seconds: 20, buffered_seconds: 30, target_seconds: 30,
          film_seconds: rundown.total_seconds,
          scene_total: rundown.episodes.reduce((n, e) => n + e.scenes.length, 0), now,
        };
      case "downtime":
        return { v: 1, topic: "state", status: "downtime", screening: 12, sha: "d5b84a2", now };
      case "warming":
        return { v: 1, topic: "state", status: "warming", detail: "reading the story…", now };
      case "offair":
        return null;
      default:
        return {
          v: 1, topic: "state", status: "live", screening: 12, sha: "d5b84a2", next_sha: "a1b2c3d",
          episode_index: current.i, episodes_total: rundown.episodes.length,
          episode_title: current.title ?? undefined, episode_file: current.file,
          scene_number: currentScene.n, scene_count: current.scenes.length,
          author: currentScene.author, author_url: currentScene.author_url,
          commit: currentScene.commit, commit_url: currentScene.commit_url,
          now, ends_at: now + 4 * 60_000 + 12_000, next_start_at: now + 4 * 60_000 + 32_000,
          stalled: false, progress: 0.37,
        };
    }
  })();

  return (
    <ShowPage
      connection="live"
      showState={showState}
      rundown={state === "warming" ? null : rundown}
      currentScene={state === "live" ? currentScene : null}
      endsAtLocal={showState?.next_start_at ?? showState?.ends_at ?? showState?.resumes_at ?? null}
      offAir={state === "offair"}
      videoTrack={null}
      audioTrack={null}
      chat={chat}
      viewers={chatCount > 3 ? 1284 : 37}
      onSendChat={(author, text) => {
        setChat((prev) => [...prev, { id: prev.length + 1, author, text }]);
        return true;
      }}
    />
  );
}
