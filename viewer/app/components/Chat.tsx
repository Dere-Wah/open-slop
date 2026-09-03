"use client";

import { useEffect, useRef, useState } from "react";
import { Avatar } from "./Avatar";
import { ChevronRightIcon, CommentIcon } from "./Icons";
import type { RepoRef } from "@/lib/github";

export interface ChatEntry {
  id: number;
  author: string;
  text: string;
}

const NAME_KEY = "open-slop-name";
const HIDDEN_KEY = "open-slop-chat-hidden";
const NAME_MAX = 24;
const TEXT_MAX = 500;
// How close to the bottom (px) the reader must be for a new message to pull
// the list down. Further up, they are reading history; leave them there.
const FOLLOW_SLACK = 48;

/**
 * The room chat: viewers talking while they watch, laid out like a GitHub
 * conversation — an avatar disc, a bold name, the line. It is only chat; the
 * way to change the film is a pull request on the story branch, not a message
 * here, and the header says so. Messages signed by the show carry a `bot`
 * label the way GitHub marks its apps. A display name is required before
 * sending; it persists in localStorage, as does the hide toggle.
 *
 * The list has a fixed height from `className` and scrolls inside it, so a
 * busy room never grows the page. A new message scrolls the list to the
 * bottom only when the reader is already there; ShowApp caps what is kept.
 * Hidden, the box collapses to its header with a count, so the chat is one
 * click away without taking the sidebar.
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
  const [hidden, setHidden] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const atBottomRef = useRef(true);

  useEffect(() => {
    setName(localStorage.getItem(NAME_KEY) ?? "");
    setHidden(localStorage.getItem(HIDDEN_KEY) === "1");
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (element && atBottomRef.current) element.scrollTop = element.scrollHeight;
  }, [entries, hidden]);

  function toggleHidden() {
    setHidden((value) => {
      localStorage.setItem(HIDDEN_KEY, value ? "0" : "1");
      return !value;
    });
  }

  function onScroll() {
    const element = scrollRef.current;
    if (!element) return;
    atBottomRef.current =
      element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_SLACK;
  }

  function submit() {
    const text = draft.trim().slice(0, TEXT_MAX);
    const author = name.trim().slice(0, NAME_MAX);
    if (!text || !author) return;
    if (onSend(author, text)) setDraft("");
  }

  return (
    <section
      className={`gh-box flex min-h-0 flex-col overflow-hidden ${hidden ? "" : className}`}
      id="chat"
    >
      <header className={`gh-box-header justify-between ${hidden ? "rounded-b-[6px] border-b-0" : ""}`}>
        <button
          type="button"
          onClick={toggleHidden}
          aria-expanded={!hidden}
          aria-controls="chat-body"
          className="-ml-1 flex items-center gap-2 rounded px-1 text-fg hover:text-accent"
          title={hidden ? "Show the chat" : "Hide the chat"}
        >
          <ChevronRightIcon
            size={14}
            className={`text-fg-muted transition-transform ${hidden ? "" : "rotate-90"}`}
          />
          <CommentIcon className="text-fg-muted" />
          <h2 className="font-semibold">Chat</h2>
          {entries.length > 0 && <span className="gh-counter">{entries.length}</span>}
        </button>
        <span className="hidden text-xs text-fg-muted sm:inline">
          {hidden ? "hidden" : "to add a scene, open a PR"}
        </span>
      </header>

      {!hidden && (
        <div ref={scrollRef} onScroll={onScroll} id="chat-body" className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
          {entries.length === 0 && (
            <p className="py-6 text-center text-sm text-fg-muted">No messages yet — say hello.</p>
          )}
          <ul className="flex flex-col gap-2">
            {entries.map((entry) => {
              const isShow = entry.author === "show";
              return (
                <li key={entry.id} className="flex items-start gap-2 text-sm leading-5">
                  <Avatar name={isShow ? `@${repo.owner}` : entry.author} size={20} className="mt-0.5" />
                  <p className="min-w-0 [overflow-wrap:anywhere]">
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
      )}

      {!hidden && (
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
      )}
    </section>
  );
}
