/**
 * The Infinite (theinfinite.tv) shows the screening inside a virtual movie
 * theatre and shares the room chat. Everything about that partnership the
 * viewer or the token endpoint needs is here, so a second partner is a second
 * entry rather than a search.
 *
 * The trust anchor is the LiveKit identity prefix: `/api/infinite/token`
 * mints identities that start with it and nothing else does, so a chat line
 * from such a participant is theirs no matter what the packet claims. The
 * `source` tag inside the packet is a convenience for readers (theirs and
 * ours), never proof. See INTEGRATION.md for the protocol.
 */
export const INFINITE = {
  name: "The Infinite",
  url: "https://theinfinite.tv",
  favicon: "https://theinfinite.tv/favicon.svg",
  identityPrefix: "infinite-",
  source: "infinite",
} as const;

/** Where a chat line was typed, read off the sender's identity, never the packet. */
export type ChatSource = "open-slop" | "infinite";

/** The `source` tag this viewer writes into every packet it sends. */
export const OWN_SOURCE: ChatSource = "open-slop";

export function sourceOfIdentity(identity: string | undefined): ChatSource {
  return identity?.startsWith(INFINITE.identityPrefix) ? INFINITE.source : OWN_SOURCE;
}

/** Fifteen minutes: the partner reconnects, and a leaked token dies young. */
export const PARTNER_TOKEN_TTL_S = 15 * 60;

const DEFAULT_ORIGINS = ["https://theinfinite.tv", "https://www.theinfinite.tv", "http://localhost:5187"];

/**
 * Origins `/api/infinite/token` answers. `INFINITE_ALLOWED_ORIGINS` (comma
 * separated) replaces the default list when set, so a staging host can be
 * added without a deploy of code.
 */
export function partnerOrigins(): string[] {
  const configured = process.env.INFINITE_ALLOWED_ORIGINS;
  if (!configured) return DEFAULT_ORIGINS;
  return configured
    .split(",")
    .map((origin) => origin.trim().replace(/\/+$/, ""))
    .filter(Boolean);
}

export function isPartnerOrigin(origin: string): boolean {
  return partnerOrigins().includes(origin.replace(/\/+$/, ""));
}
