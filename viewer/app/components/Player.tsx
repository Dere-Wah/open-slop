"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import type { RemoteTrack } from "livekit-client";

/**
 * The broadcast surface: attaches the room's video and audio tracks to media
 * elements, renders an overlay on top (now-playing, intermission), and a
 * whole-film progress bar along the bottom. Video autoplays muted (every
 * browser allows that); sound is one tap away.
 */
export function Player({
  videoTrack,
  audioTrack,
  status,
  overlay,
  progress,
}: {
  videoTrack: RemoteTrack | null;
  audioTrack: RemoteTrack | null;
  status: "connecting" | "live" | "offline";
  overlay?: ReactNode;
  progress?: number;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    const element = videoRef.current;
    if (!videoTrack || !element) return;
    videoTrack.attach(element);
    return () => {
      videoTrack.detach(element);
    };
  }, [videoTrack]);

  useEffect(() => {
    const element = audioRef.current;
    if (!audioTrack || !element) return;
    audioTrack.attach(element);
    element.muted = muted;
    return () => {
      audioTrack.detach(element);
    };
  }, [audioTrack, muted]);

  return (
    <section className="relative w-full shrink-0 overflow-hidden rounded-xl border border-zinc-800 bg-black">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="aspect-video w-full object-contain"
      />
      <audio ref={audioRef} autoPlay />

      {!videoTrack && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="font-mono text-sm text-zinc-600">
            {status === "live"
              ? "waiting for the projector…"
              : "connecting to the show…"}
          </p>
        </div>
      )}

      {overlay}

      {typeof progress === "number" && (
        <div className="absolute inset-x-0 bottom-0 h-1 bg-white/10">
          <div
            className="h-full bg-brand transition-[width] duration-1000 ease-linear"
            style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
          />
        </div>
      )}

      {videoTrack && audioTrack && (
        <button
          onClick={() => setMuted((value) => !value)}
          className="absolute bottom-3 right-3 rounded-md bg-zinc-900/80 px-3 py-1.5 font-mono text-xs text-zinc-200 hover:bg-zinc-800"
        >
          {muted ? "unmute" : "mute"}
        </button>
      )}
    </section>
  );
}
