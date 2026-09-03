// Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.

"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { AgentMark } from "./BrandIcons";
import { CheckIcon, TriangleDownIcon } from "./Icons";
import {
  AGENTS,
  DEFAULT_AGENT,
  agentById,
  contributionPrompt,
  isWebHref,
  type Agent,
  type AgentId,
} from "@/lib/agents";
import type { RepoRef } from "@/lib/github";

const AGENT_KEY = "openslop.agent";

/**
 * "Open in <agent>", the way GitHub and Linear draw it: a split button whose
 * left half runs the remembered agent and whose right half opens a menu of
 * the others. Picking one runs it and makes it the default, kept in
 * localStorage. Every entry hands the agent the same prompt (see
 * `contributionPrompt`), pre-filled and not sent, so the visitor reads it
 * before anything runs. Hidden under `md`: the links open desktop apps.
 */
export function AgentButton({ repo }: { repo: RepoRef }) {
  const [choice, setChoice] = useState<AgentId>(DEFAULT_AGENT);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    setChoice(agentById(localStorage.getItem(AGENT_KEY)).id);
  }, []);

  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  const prompt = contributionPrompt(repo);
  const current = agentById(choice);

  /** Remember the agent and put the prompt on the clipboard when it needs it. */
  const run = useCallback(
    (agent: Agent, event: MouseEvent) => {
      localStorage.setItem(AGENT_KEY, agent.id);
      setChoice(agent.id);
      setOpen(false);
      if (agent.copiesPrompt) {
        void navigator.clipboard?.writeText(prompt).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        });
      }
      if (agent.href(prompt, repo) === null) event.preventDefault();
    },
    [prompt, repo],
  );

  return (
    <div ref={root} className="relative hidden md:block">
      <div className="flex">
        <AgentLink
          agent={current}
          prompt={prompt}
          repo={repo}
          onRun={run}
          className="gh-btn rounded-r-none px-2.5"
          title={current.href(prompt, repo) ? `Open in ${current.name}` : current.name}
          aria-label={current.href(prompt, repo) ? `Open in ${current.name}` : current.name}
        >
          {copied ? (
            <CheckIcon className="text-success" />
          ) : (
            <AgentMark icon={current.icon} size={16} />
          )}
        </AgentLink>
        <button
          type="button"
          className="gh-btn -ml-px rounded-l-none px-1.5"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={menuId}
          title="Choose an agent"
          onClick={() => setOpen((value) => !value)}
        >
          <TriangleDownIcon />
        </button>
      </div>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="gh-menu absolute right-0 top-full z-30 mt-1 w-64"
        >
          <div className="gh-menu-heading">Hand this movie to an agent</div>
          <p className="px-3 pb-2 text-xs text-fg-muted">
            Opens the app with the prompt ready. Nothing runs until you press Enter.
          </p>
          <div className="gh-menu-divider" />
          {AGENTS.map((agent) => (
            <AgentLink
              key={agent.id}
              agent={agent}
              prompt={prompt}
              repo={repo}
              onRun={run}
              role="menuitem"
              className="gh-menu-item"
            >
              <AgentMark icon={agent.icon} size={16} className="shrink-0 text-fg-muted" />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{agent.name}</span>
                {agent.hint && (
                  <span className="block truncate text-xs text-fg-muted">{agent.hint}</span>
                )}
              </span>
              {agent.id === choice && <CheckIcon className="shrink-0 text-fg-muted" />}
            </AgentLink>
          ))}
        </div>
      )}
    </div>
  );
}

interface AgentLinkProps {
  agent: Agent;
  prompt: string;
  repo: RepoRef;
  onRun: (agent: Agent, event: MouseEvent) => void;
  className: string;
  role?: string;
  title?: string;
  "aria-label"?: string;
  children: ReactNode;
}

/**
 * One agent as a link the browser follows itself, so an app scheme opens the
 * app the same way any other link would. The clipboard-only entry is a
 * button.
 */
function AgentLink({ agent, prompt, repo, onRun, className, children, ...rest }: AgentLinkProps) {
  const href = agent.href(prompt, repo);
  if (href === null) {
    return (
      <button type="button" className={className} onClick={(event) => onRun(agent, event)} {...rest}>
        {children}
      </button>
    );
  }
  return (
    <a
      href={href}
      className={`${className} hover:no-underline`}
      onClick={(event) => onRun(agent, event)}
      {...(isWebHref(href) ? { target: "_blank", rel: "noreferrer" } : {})}
      {...rest}
    >
      {children}
    </a>
  );
}
