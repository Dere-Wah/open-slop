"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Avatar } from "./Avatar";
import { ChevronRightIcon, CommentIcon, GitPullRequestIcon } from "./Icons";
import { pullRefOf, type RepoRef } from "@/lib/github";

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
 * way to change the movie is a pull request on the story branch, not a message
 * here, and the header says so. Messages signed by the show carry a `bot`
 * label the way GitHub marks its apps.
 *
 * A link to one of this repository's pull requests renders as a chip — the
 * pull-request icon and `#41` — so "can someone review this?" reads at a
 * glance. Only this repository's pull requests get that; any other URL stays
 * plain text, so the chat cannot be turned into a link board.
 *
 * Nobody types a name to read. The first time someone sends, a small dialog
 * asks what to call them, the message goes out under that name, and the name
 * persists in localStorage; "change" under the box reopens the dialog.
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
  // The message waiting for a name, when the dialog is open.
  const [pending, setPending] = useState<string | null>(null);
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

  function send(author: string, text: string) {
    if (onSend(author, text)) setDraft("");
  }

  function submit() {
    const text = draft.trim().slice(0, TEXT_MAX);
    if (!text) return;
    const author = name.trim();
    if (author) send(author, text);
    else setPending(text);
  }

  function chooseName(chosen: string) {
    const author = chosen.trim().slice(0, NAME_MAX);
    if (!author) return;
    localStorage.setItem(NAME_KEY, author);
    setName(author);
    if (pending) send(author, pending);
    setPending(null);
  }

  return (
    <section
      className={`gh-box flex min-h-0 flex-col overflow-hidden ${hidden ? "" : className}`}
      id="chat"
    >
      <header
        className={`gh-box-header justify-between ${hidden ? "rounded-b-[6px] border-b-0" : ""}`}
      >
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
        <div
          ref={scrollRef}
          onScroll={onScroll}
          id="chat-body"
          className="min-h-0 flex-1 overflow-y-auto px-3 py-2"
        >
          {entries.length === 0 && (
            <p className="py-6 text-center text-sm text-fg-muted">No messages yet — say hello.</p>
          )}
          <ul className="flex flex-col gap-2">
            {entries.map((entry) => {
              const isShow = entry.author === "show";
              return (
                <li key={entry.id} className="flex items-start gap-2 text-sm leading-5">
                  <Avatar name={isShow ? `@${repo.owner}` : entry.author} size={20} />
                  <p className="min-w-0 [overflow-wrap:anywhere]">
                    <span className={`font-semibold ${isShow ? "text-accent" : "text-fg"}`}>
                      {isShow ? repo.repo : entry.author}
                    </span>
                    {isShow && <span className="gh-label ml-1.5 h-4 px-1.5 text-[10px]">bot</span>}{" "}
                    <span className="text-fg">{renderText(entry.text, repo)}</span>
                  </p>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {!hidden && (
        <form
          className="flex flex-col gap-1.5 border-t border-line bg-canvas-subtle p-3"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <div className="flex gap-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={connected ? "Say something…" : "Connecting…"}
              aria-label="Message"
              disabled={!connected}
              maxLength={TEXT_MAX}
              className="gh-input min-w-0 flex-1"
            />
            <button
              type="submit"
              disabled={!connected || !draft.trim()}
              className="gh-btn gh-btn-primary shrink-0 disabled:opacity-50"
            >
              Send
            </button>
          </div>
          {name && (
            <p className="text-xs text-fg-muted">
              Chatting as <span className="font-semibold text-fg">{name}</span>
              {" · "}
              <button type="button" onClick={() => setPending("")} className="gh-link">
                change
              </button>
            </p>
          )}
        </form>
      )}

      {pending !== null && (
        <NameDialog
          initial={name}
          onCancel={() => setPending(null)}
          onChoose={chooseName}
        />
      )}
    </section>
  );
}

/**
 * The message text with this repository's pull-request links drawn as chips.
 * Everything else is left exactly as typed.
 */
function renderText(text: string, repo: RepoRef): ReactNode {
  const parts: ReactNode[] = [];
  const pattern = /https?:\/\/\S+/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    // "…/pull/7?" — the question mark belongs to the sentence, not the link.
    const token = match[0].replace(/[).,;:!?'"\]]+$/, "");
    const pull = pullRefOf(token, repo);
    if (!pull) continue;
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(
      <a
        key={`${match.index}`}
        href={pull.url}
        target="_blank"
        rel="noreferrer"
        title={`Pull request #${pull.number} on ${repo.owner}/${repo.repo}`}
        className="mx-0.5 inline-flex items-center gap-1 rounded-full border border-line bg-canvas-overlay px-2 py-0.5 align-[-3px] font-mono text-xs text-fg hover:border-accent hover:no-underline"
      >
        <GitPullRequestIcon size={12} className="text-success" />#{pull.number}
      </a>,
    );
    last = match.index + token.length;
  }
  if (parts.length === 0) return text;
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Ask what to call this viewer. Enter confirms, Escape or the backdrop cancels. */
function NameDialog({
  initial,
  onCancel,
  onChoose,
}: {
  initial: string;
  onCancel: () => void;
  onChoose: (name: string) => void;
}) {
  const [value, setValue] = useState(initial);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Focus and select the previous name once, when the dialog opens. This
  // effect must not depend on anything that changes while the user types:
  // the parent re-renders on every chat packet and hands down a fresh
  // `onCancel`, and re-running `select()` then would grab the whole field
  // under the caret on every keystroke.
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") cancelRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="name-dialog-title"
        className="gh-box w-full max-w-sm overflow-hidden shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          onChoose(value);
        }}
      >
        <header className="gh-box-header">
          <CommentIcon className="text-fg-muted" />
          <h2 id="name-dialog-title" className="font-semibold">
            What should we call you?
          </h2>
        </header>
        <div className="flex flex-col gap-3 p-4">
          <p className="text-sm text-fg-muted">
            Shown next to your messages. Use your GitHub handle with an @ to get your avatar.
          </p>
          <input
            ref={inputRef}
            value={value}
            onChange={(event) => setValue(event.target.value.slice(0, NAME_MAX))}
            placeholder="@octocat"
            aria-label="Your name"
            maxLength={NAME_MAX}
            className="gh-input"
          />
        </div>
        <footer className="flex justify-end gap-2 border-t border-line bg-canvas-subtle px-4 py-3">
          <button type="button" onClick={onCancel} className="gh-btn">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!value.trim()}
            className="gh-btn gh-btn-primary disabled:opacity-50"
          >
            Continue
          </button>
        </footer>
      </form>
    </div>
  );
}
