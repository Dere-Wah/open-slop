"use client";

import { useEffect, useRef, useState } from "react";
import { Avatar } from "./Avatar";
import { CommentIcon } from "./Icons";
import type { RepoRef } from "@/lib/github";

export interface ChatEntry {
  id: number;
  author: string;
  text: string;
}

const NAME_KEY = "open-slop-name";
const NAME_MAX = 24;
const TEXT_MAX = 500;

/**
 * The room chat: viewers talking while they watch, laid out like a GitHub
 * conversation — an avatar disc, a bold name, the line. It is only chat; the
 * way to change the film is a pull request on the story branch, not a message
 * here, and the header says so. Messages signed by the show carry a `bot`
 * label the way GitHub marks its apps. A display name is required before
 * sending; it persists in localStorage.
 */
export function Chat({
  entries,
  onSend,
  connected,
  repo,
  className = "",
}: {
  entries: ChatEntry[];
  onSend: (author: string, text: string) => boolean;
  connected: boolean;
  repo: RepoRef;
  className?: string;
}) {
  const [name, setName] = useState("");
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setName(localStorage.getItem(NAME_KEY) ?? "");
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [entries]);

  function submit() {
    const text = draft.trim().slice(0, TEXT_MAX);
    const author = name.trim().slice(0, NAME_MAX);
    if (!text || !author) return;
    if (onSend(author, text)) setDraft("");
  }

  return (
    <section className={`gh-box flex min-h-0 flex-col overflow-hidden ${className}`} id="chat">
      <header className="gh-box-header justify-between">
        <div className="flex items-center gap-2">
          <CommentIcon className="text-fg-muted" />
          <h2 className="font-semibold">Chat</h2>
          {entries.length > 0 && <span className="gh-counter">{entries.length}</span>}
        </div>
        <span className="hidden text-xs text-fg-muted sm:inline">to add a scene, open a PR</span>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {entries.length === 0 && (
          <p className="py-6 text-center text-sm text-fg-muted">No messages yet — say hello.</p>
        )}
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => {
            const isShow = entry.author === "show";
            return (
              <li key={entry.id} className="flex items-start gap-2 text-sm leading-5">
                <Avatar name={isShow ? `@${repo.owner}` : entry.author} size={20} className="mt-0.5" />
                <p className="min-w-0 break-words">
                  <span className={`font-semibold ${isShow ? "text-accent" : "text-fg"}`}>
                    {isShow ? repo.repo : entry.author}
                  </span>
                  {isShow && <span className="gh-label ml-1.5 h-4 px-1.5 text-[10px]">bot</span>}{" "}
                  <span className="text-fg">{entry.text}</span>
                </p>
              </li>
            );
          })}
        </ul>
      </div>

      <form
        className="flex flex-col gap-2 border-t border-line bg-canvas-subtle p-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(event) => {
              const value = event.target.value.slice(0, NAME_MAX);
              setName(value);
              localStorage.setItem(NAME_KEY, value);
            }}
            placeholder="Your name"
            aria-label="Your name"
            className="gh-input w-32 shrink-0"
          />
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={connected ? "Say something…" : "Connecting…"}
            aria-label="Message"
            disabled={!connected}
            className="gh-input min-w-0 flex-1"
          />
          <button
            type="submit"
            disabled={!connected || !draft.trim() || !name.trim()}
            className="gh-btn gh-btn-primary shrink-0 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
