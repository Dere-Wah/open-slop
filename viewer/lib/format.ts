// Small display helpers shared across the viewer.

/** "15m 04s" from a second count. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

/** "4:12" from a millisecond remaining count; "0:00" once it passes. */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

/** "16:38" wall-clock time from an epoch-ms instant, in the viewer's zone. */
export function formatClock(epochMs: number): string {
  return new Date(epochMs).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** The short commit, defensively trimmed. */
export function shortCommit(commit: string | undefined | null): string {
  return (commit ?? "").slice(0, 7);
}
