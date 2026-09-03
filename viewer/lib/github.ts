// Everything the viewer knows about GitHub it derives from one string: the
// projector's `story_url`, `https://github.com/<owner>/<repo>/tree/<branch>`.
// From it come the repository name in the header, every link out, and the
// avatar of each contributor. The viewer never calls the GitHub API — an
// anonymous page would burn through the rate limit in minutes — it only links
// to github.com and loads avatar images, which are served from a CDN.

import { safeHttpUrl } from "./safeUrl";

export const FALLBACK_REPO: RepoRef = {
  owner: "Dere-Wah",
  repo: "open-slop",
  branch: "story",
};

export interface RepoRef {
  owner: string;
  repo: string;
  branch: string;
}

const SEGMENT = /^[A-Za-z0-9_.-]{1,100}$/;
const LOGIN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/;

/** Parse `.../<owner>/<repo>/tree/<branch>`; the fallback when it is not one. */
export function repoOf(storyUrl: unknown): RepoRef {
  const url = safeHttpUrl(storyUrl);
  if (!url) return FALLBACK_REPO;
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== "github.com") return FALLBACK_REPO;
    const [owner, repo, tree, ...rest] = parsed.pathname.split("/").filter(Boolean);
    const branch = rest.join("/");
    if (!owner || !repo || tree !== "tree" || !branch) return FALLBACK_REPO;
    if (!SEGMENT.test(owner) || !SEGMENT.test(repo)) return FALLBACK_REPO;
    return { owner, repo, branch: decodeURIComponent(branch) };
  } catch {
    return FALLBACK_REPO;
  }
}

export function repoUrl(ref: RepoRef): string {
  return `https://github.com/${ref.owner}/${ref.repo}`;
}

export function treeUrl(ref: RepoRef): string {
  return `${repoUrl(ref)}/tree/${encodeURIComponent(ref.branch)}`;
}

export function blobUrl(ref: RepoRef, path: string): string {
  return `${repoUrl(ref)}/blob/${encodeURIComponent(ref.branch)}/${encodeURIComponent(path)}`;
}

export function readmeUrl(ref: RepoRef): string {
  return blobUrl(ref, "README.md");
}

export function pullsUrl(ref: RepoRef): string {
  return `${repoUrl(ref)}/pulls`;
}

export function newPullUrl(ref: RepoRef): string {
  return `${repoUrl(ref)}/compare/${encodeURIComponent(ref.branch)}...${encodeURIComponent(ref.branch)}?expand=1`;
}

export function commitsUrl(ref: RepoRef): string {
  return `${repoUrl(ref)}/commits/${encodeURIComponent(ref.branch)}`;
}

/** `@octocat` → `octocat`; null for a display name that is not a login. */
export function loginOf(name: unknown): string | null {
  if (typeof name !== "string" || !name.startsWith("@")) return null;
  const login = name.slice(1);
  return LOGIN.test(login) ? login : null;
}

/** The avatar GitHub serves for a login, sized for a retina 2× of `size`. */
export function avatarUrl(login: string, size: number): string {
  return `https://github.com/${encodeURIComponent(login)}.png?size=${size * 2}`;
}

/** The login a `https://github.com/<login>` profile URL names, or null. */
export function loginFromUrl(url: unknown): string | null {
  const safe = safeHttpUrl(url);
  if (!safe) return null;
  try {
    const parsed = new URL(safe);
    if (parsed.hostname !== "github.com") return null;
    const [login, ...rest] = parsed.pathname.split("/").filter(Boolean);
    return login && rest.length === 0 && LOGIN.test(login) ? login : null;
  } catch {
    return null;
  }
}

export function profileUrl(login: string): string {
  return `https://github.com/${encodeURIComponent(login)}`;
}
