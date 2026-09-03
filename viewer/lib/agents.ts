// Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.

import { repoUrl, type RepoRef } from "./github";

/**
 * The coding agents a visitor can hand the movie to, and the deep link each
 * one accepts. Every link opens the agent with the prompt already in its
 * composer and nothing running: the visitor reads it and presses Enter.
 *
 * Each `href` is the documented scheme, so a change here should cite the page:
 *   Cursor        cursor.com/docs/reference/deeplinks
 *   Codex         developers.openai.com/codex/app/commands#deep-links
 *   Claude Code   code.claude.com/docs/en/deep-links   (5,000-character cap on `q`)
 *   Claude        support.claude.com → "Open Claude Desktop with a link"
 *   Copilot app   docs.github.com → "Using deep links to open the GitHub Copilot app"
 *   VS Code       the Copilot Chat extension's `vscode://GitHub.Copilot-Chat/chat?prompt=`
 *   Warp          docs.warp.dev/terminal/more-features/uri-scheme (no prompt parameter,
 *                 so the prompt goes to the clipboard first)
 */
export type AgentId =
  | "cursor"
  | "codex"
  | "claude-code"
  | "claude"
  | "copilot"
  | "vscode"
  | "warp"
  | "copy";

export type AgentIcon = "cursor" | "openai" | "claude" | "copilot" | "warp" | "copy";

export interface Agent {
  id: AgentId;
  name: string;
  icon: AgentIcon;
  /** A word under the name in the menu, for the ones that need one. */
  hint?: string;
  /** The link to open, or null for the clipboard-only entry. */
  href: (prompt: string, repo: RepoRef) => string | null;
  /** Put the prompt on the clipboard before following the link. */
  copiesPrompt?: boolean;
}

const enc = encodeURIComponent;

export const AGENTS: readonly Agent[] = [
  {
    id: "cursor",
    name: "Cursor",
    icon: "cursor",
    href: (prompt) => `cursor://anysphere.cursor-deeplink/prompt?text=${enc(prompt)}`,
  },
  {
    id: "codex",
    name: "Codex",
    icon: "openai",
    href: (prompt, repo) => `codex://new?prompt=${enc(prompt)}&originUrl=${enc(repoUrl(repo))}`,
  },
  {
    id: "claude-code",
    name: "Claude Code",
    icon: "claude",
    hint: "in your terminal",
    href: (prompt, repo) =>
      `claude-cli://open?q=${enc(prompt)}&repo=${enc(`${repo.owner}/${repo.repo}`)}`,
  },
  {
    id: "claude",
    name: "Claude",
    icon: "claude",
    hint: "desktop app",
    href: (prompt) => `claude://code/new?q=${enc(prompt)}`,
  },
  {
    id: "copilot",
    name: "GitHub Copilot",
    icon: "copilot",
    hint: "desktop app",
    href: (prompt, repo) => {
      const app =
        `ghapp://session/new?repo=${enc(`${repo.owner}/${repo.repo}`)}` +
        `&branch=${enc(repo.branch)}&mode=interactive&prompt=${enc(prompt)}`;
      return `https://github.com/copilot/app/launch?open=${enc(app)}`;
    },
  },
  {
    id: "vscode",
    name: "VS Code",
    icon: "copilot",
    hint: "Copilot Chat",
    href: (prompt) => `vscode://GitHub.Copilot-Chat/chat?prompt=${enc(prompt)}`,
  },
  {
    id: "warp",
    name: "Warp",
    icon: "warp",
    hint: "copies the prompt first",
    copiesPrompt: true,
    href: () => "warp://action/new_agent_conversation",
  },
  {
    id: "copy",
    name: "Copy as prompt",
    icon: "copy",
    copiesPrompt: true,
    href: () => null,
  },
];

export const DEFAULT_AGENT: AgentId = "cursor";

export function agentById(id: string | null | undefined): Agent {
  return AGENTS.find((agent) => agent.id === id) ?? AGENTS[0];
}

/** True for a link the browser can open in a new tab, as opposed to an app scheme. */
export function isWebHref(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

/**
 * The prompt every agent receives: where the movie lives, what to read first,
 * and the one task. Under 1,000 characters so it fits every scheme's cap.
 */
export function contributionPrompt(repo: RepoRef): string {
  const url = repoUrl(repo);
  return [
    `Clone ${url} and check out the \`${repo.branch}\` branch. It is the screenplay of OpenSlop, ` +
      `an open-source movie that is rendered live from this branch.`,
    `Read AGENTS.md, then skills/writing-a-scene/SKILL.md and STYLE.md, then the episode files.`,
    `Add one new scene to the movie: either a new episode file or a scene at the end of an ` +
      `existing one. Match the look in STYLE.md, keep the prompt between 200 and 800 characters, ` +
      `end it with what we hear, and pick a seed.`,
    `Run the validator AGENTS.md names, then open a pull request against \`${repo.branch}\` ` +
      `with a one-paragraph description of the scene.`,
  ].join("\n\n");
}
