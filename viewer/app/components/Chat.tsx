"use client";

import { useEffect, useRef, useState } from "react";

export interface ChatEntry {
  id: number;
  author: string;
  text: string;
}

const NAME_KEY = "open-slop-name";
const NAME_MAX = 24;
const TEXT_MAX = 500;

/**
 * The room chat: viewers talking while they watch. It is only chat — the way
 * to change the film is a pull request on the story branch, not a message
 * here. A display name is required before sending; it persists in
 * localStorage.
 */
export function Chat({
  entries,
  onSend,
  connected,
}: {
  entries: ChatEntry[];
  onSend: (author: string, text: string) => boolean;
  connected: boolean;
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
    <aside className="flex min-h-0 w-full flex-1 flex-col rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="border-b border-zinc-800 px-4 py-3">
        <h2 className="text-sm font-medium">Chat</h2>
        <p className="mt-0.5 text-xs text-zinc-500">
          Talk while you watch. To change the film, open a pull request.
        </p>
      </div>
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4 text-sm"
      >
        {entries.length === 0 && (
          <p className="text-xs text-zinc-600">No messages yet — say hello.</p>
        )}
        {entries.map((entry) => (
          <p key={entry.id} className="leading-5">
            <span
              className={
                entry.author === "show"
                  ? "font-mono text-xs text-brand"
                  : "font-mono text-xs text-zinc-400"
              }
            >
              {entry.author}
            </span>{" "}
            <span className={entry.author === "show" ? "text-zinc-300" : ""}>
              {entry.text}
            </span>
          </p>
        ))}
      </div>
      <div className="space-y-2 border-t border-zinc-800 p-3">
        <input
          value={name}
          onChange={(event) => {
            const value = event.target.value.slice(0, NAME_MAX);
            setName(value);
            localStorage.setItem(NAME_KEY, value);
          }}
          placeholder="your name"
          className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs outline-none focus:border-zinc-600"
        />
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submit();
            }}
            placeholder={connected ? "say something…" : "connecting…"}
            disabled={!connected}
            className="flex-1 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-600 disabled:opacity-50"
          />
          <button
            onClick={submit}
            disabled={!connected || !draft.trim() || !name.trim()}
            className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </aside>
  );
}
