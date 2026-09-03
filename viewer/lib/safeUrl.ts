/**
 * Only ever render an `href` that is an http(s) URL. Everything the viewer
 * links to comes off the room — author profiles, commits, the story branch —
 * and while the streamer is the only participant allowed to write those
 * fields, a link is still the one place a bad value would become a click.
 */
export function safeHttpUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length === 0 || value.length > 2048) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}
