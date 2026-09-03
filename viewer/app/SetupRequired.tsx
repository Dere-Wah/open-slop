export function SetupRequired() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-lg rounded-xl border border-zinc-800 bg-zinc-900/60 p-8">
        <h1 className="text-lg font-semibold">Open Slop — almost there</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-400">
          The viewer needs your LiveKit project credentials so it can mint room
          tokens. Copy{" "}
          <code className="font-mono text-zinc-200">.env.example</code> to{" "}
          <code className="font-mono text-zinc-200">.env.local</code> and set:
        </p>
        <ul className="mt-3 list-disc pl-5 font-mono text-sm text-zinc-300">
          <li>LIVEKIT_URL</li>
          <li>LIVEKIT_API_KEY</li>
          <li>LIVEKIT_API_SECRET</li>
          <li>LIVEKIT_ROOM (must match the projector&apos;s)</li>
        </ul>
        <p className="mt-3 text-sm leading-6 text-zinc-400">
          Then restart <code className="font-mono text-zinc-200">pnpm dev</code>
          . The projector half of this project (see the{" "}
          <code className="font-mono text-zinc-200">projector/</code> folder on
          the code branch) uses the same LiveKit project and broadcasts the film
          the page plays.
        </p>
      </div>
    </main>
  );
}
