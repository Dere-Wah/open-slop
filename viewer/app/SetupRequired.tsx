import { FilmIcon } from "./components/Icons";

export function SetupRequired() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <div className="gh-box w-full max-w-lg">
        <div className="gh-box-header">
          <FilmIcon className="text-fg-muted" />
          <h1 className="font-semibold">OpenSlop — almost there</h1>
        </div>
        <div className="space-y-3 p-4 text-sm text-fg-muted">
          <p>
            The viewer needs your LiveKit project credentials so it can mint room tokens. Copy{" "}
            <code className="rounded bg-canvas-overlay px-1 py-0.5 font-mono text-xs text-fg">
              .env.example
            </code>{" "}
            to{" "}
            <code className="rounded bg-canvas-overlay px-1 py-0.5 font-mono text-xs text-fg">
              .env.local
            </code>{" "}
            and set:
          </p>
          <ul className="list-disc pl-5 font-mono text-xs text-fg">
            <li>LIVEKIT_URL</li>
            <li>LIVEKIT_API_KEY</li>
            <li>LIVEKIT_API_SECRET</li>
            <li>LIVEKIT_ROOM (must match the projector&apos;s)</li>
          </ul>
          <p>
            Then restart{" "}
            <code className="rounded bg-canvas-overlay px-1 py-0.5 font-mono text-xs text-fg">
              pnpm dev
            </code>
            . The projector half of this project (the{" "}
            <code className="rounded bg-canvas-overlay px-1 py-0.5 font-mono text-xs text-fg">
              projector/
            </code>{" "}
            folder on the code branch) uses the same LiveKit project and broadcasts the movie this
            page plays.
          </p>
        </div>
      </div>
    </main>
  );
}
