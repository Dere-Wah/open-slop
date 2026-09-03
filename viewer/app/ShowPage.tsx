"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { RemoteTrack } from "livekit-client";

import { RepoHeader, type Connection } from "./components/RepoHeader";
import { Player } from "./components/Player";
import { Overlay } from "./components/Overlay";
import { Curtain } from "./components/Curtain";
import { NowPlaying } from "./components/NowPlaying";
import { Rundown } from "./components/Rundown";
import { About } from "./components/About";
import { Chat, type ChatEntry } from "./components/Chat";
import { CommentIcon, InfoIcon, ListIcon } from "./components/Icons";
import { repoOf, repoUrl } from "@/lib/github";
import type { Rundown as RundownData, RundownScene, ShowState } from "@/lib/types";

/**
 * The whole page, given everything the room delivered. Pure presentation:
 * ShowApp owns the LiveKit room and hands the result here, and the dev-only
 * preview route hands fixtures here, so every state of the page — live,
 * loading, off air, a two-hundred-episode film — can be looked at without a
 * projector running.
 *
 * It is laid out as a GitHub repository page — the `owner / repo` header
 * with its underline nav, then a two-column body: the
 * player, the now-playing bar, and the rundown on the left; About and the
 * chat on the right. Under `lg` the columns collapse into one and the three
 * panels sit behind a segmented control below the player, so the film stays
 * on screen while a phone flips between the rundown, the chat, and the
 * about. One grid with named areas does both layouts, so every panel is
 * mounted exactly once and keeps its state across a resize.
 */

type Panel = "rundown" | "chat" | "about";

export function ShowPage({
  connection,
  showState,
  rundown,
  currentScene,
  endsAtLocal,
  offAir,
  videoTrack,
  audioTrack,
  chat,
  onSendChat,
}: {
  connection: Connection;
  showState: ShowState | null;
  rundown: RundownData | null;
  currentScene: RundownScene | null;
  endsAtLocal: number | null;
  offAir: boolean;
  videoTrack: RemoteTrack | null;
  audioTrack: RemoteTrack | null;
  chat: ChatEntry[];
  onSendChat: (author: string, text: string) => boolean;
}) {
  const [panel, setPanel] = useState<Panel>("rundown");
  const onAir = !offAir && showState?.status === "live";
  const repo = useMemo(() => repoOf(rundown?.story_url), [rundown?.story_url]);

  const tabs: { id: Panel; label: string; icon: ReactNode; count?: number }[] = [
    { id: "rundown", label: "Rundown", icon: <ListIcon />, count: rundown?.episodes.length },
    { id: "chat", label: "Chat", icon: <CommentIcon />, count: chat.length || undefined },
    { id: "about", label: "About", icon: <InfoIcon /> },
  ];

  return (
    <div className="flex min-h-dvh flex-col">
      <RepoHeader repo={repo} sha={showState?.sha} onAir={onAir} connection={connection} />

      <main className="mx-auto grid w-full max-w-[1440px] flex-1 gap-4 px-4 py-4 [grid-template-areas:'player'_'bar'_'tabs'_'panel'] sm:px-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:grid-rows-[auto_auto_1fr] lg:gap-x-6 lg:[grid-template-areas:'player_about'_'bar_about'_'rundown_chat'] xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 [grid-area:player]">
          <Player
            videoTrack={videoTrack}
            audioTrack={audioTrack}
            connection={connection}
            progress={onAir ? showState?.progress : undefined}
            overlay={
              onAir ? (
                <Overlay state={showState} />
              ) : connection === "live" ? (
                <Curtain state={showState} rundown={rundown} offAir={offAir} />
              ) : null
            }
          />
        </div>

        <div className="min-w-0 [grid-area:bar]">
          <NowPlaying
            state={offAir ? null : showState}
            scene={currentScene}
            offAir={offAir}
          />
        </div>

        {/* Under lg the three panels share one slot; this picks which. */}
        <nav
          className="gh-underline-nav -mb-2 flex gap-1 border-b border-line [grid-area:tabs] lg:hidden"
          aria-label="Panels"
          role="tablist"
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setPanel(tab.id)}
              aria-selected={panel === tab.id}
              role="tab"
              className="h-10"
            >
              {tab.icon}
              {tab.label}
              {typeof tab.count === "number" && <span className="gh-counter">{tab.count}</span>}
            </button>
          ))}
        </nav>

        <div className={`min-w-0 [grid-area:panel] lg:[grid-area:rundown] ${panel === "rundown" ? "" : "hidden lg:block"}`}>
          <Rundown
            rundown={rundown}
            state={showState}
            repo={repo}
            nextScreeningAt={onAir ? endsAtLocal : null}
          />
        </div>

        <div
          className={`min-w-0 [grid-area:panel] lg:[grid-area:chat] lg:sticky lg:top-4 lg:self-start ${
            panel === "chat" ? "" : "hidden lg:block"
          }`}
        >
          <Chat
            entries={chat}
            onSend={onSendChat}
            connected={connection === "live"}
            repo={repo}
            className="h-[min(60dvh,440px)] lg:h-[560px]"
          />
        </div>

        <div className={`min-w-0 [grid-area:panel] lg:[grid-area:about] ${panel === "about" ? "" : "hidden lg:block"}`}>
          <About repo={repo} rundown={rundown} state={showState} />
        </div>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2 px-4 py-6 text-xs text-fg-muted sm:px-6">
          <span>Open Slop · an open-source film. Screenplay CC BY-SA 4.0, code Apache-2.0.</span>
          <span className="flex flex-wrap gap-4">
            <a href={repoUrl(repo)} target="_blank" rel="noreferrer" className="hover:text-accent">
              GitHub
            </a>
            <a href="https://reactor.inc" target="_blank" rel="noreferrer" className="hover:text-accent">
              Rendered on Reactor
            </a>
            <a href="https://livekit.io" target="_blank" rel="noreferrer" className="hover:text-accent">
              Streamed with LiveKit
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}
