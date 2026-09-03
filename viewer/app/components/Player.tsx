"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import type { RemoteTrack } from "livekit-client";
import { MuteIcon, ScreenFullIcon, UnmuteIcon } from "./Icons";

/**
 * The broadcast surface: attaches the room's video and audio tracks to media
 * elements, renders an overlay on top (the now-playing chip, or the curtain),
 * and a whole-film progress line along the bottom. Video autoplays muted
 * (every browser allows that); sound and fullscreen are one tap away, in a
 * control row that only appears when the stream is actually there.
 */
export function Player({
  videoTrack,
  audioTrack,
  connection,
  overlay,
  progress,
}: {
  videoTrack: RemoteTrack | null;
  audioTrack: RemoteTrack | null;
  connection: "connecting" | "live" | "offline";
  overlay?: ReactNode;
  progress?: number;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
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

  function fullscreen() {
    const frame = frameRef.current;
    if (!frame) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void frame.requestFullscreen?.();
  }

  return (
    <section
      ref={frameRef}
      className="group relative w-full overflow-hidden rounded-[6px] border border-line bg-black"
    >
      <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-contain" />
      <audio ref={audioRef} autoPlay />

      {!videoTrack && !overlay && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="font-mono text-sm text-fg-subtle">
            {connection === "live" ? "waiting for the projector…" : "connecting to the show…"}
          </p>
        </div>
      )}

      {typeof progress === "number" && (
        <div className="absolute inset-x-0 bottom-0 h-[3px] bg-white/10">
          <div
            className="h-full bg-accent transition-[width] duration-1000 ease-linear"
            style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
          />
        </div>
      )}

      {videoTrack && (
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5">
          {audioTrack && (
            <button
              type="button"
              onClick={() => setMuted((value) => !value)}
              className="flex h-8 items-center gap-1.5 rounded-md bg-black/60 px-2.5 text-xs font-medium text-fg backdrop-blur hover:bg-black/80"
              aria-label={muted ? "Unmute" : "Mute"}
            >
              {muted ? <UnmuteIcon /> : <MuteIcon />}
              <span className="hidden sm:inline">{muted ? "Unmute" : "Mute"}</span>
            </button>
          )}
          <button
            type="button"
            onClick={fullscreen}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-black/60 text-fg backdrop-blur hover:bg-black/80"
            aria-label="Fullscreen"
          >
            <ScreenFullIcon />
          </button>
        </div>
      )}

      {/* Last, so a full-cover overlay (the curtain) sits above the controls. */}
      {overlay}
    </section>
  );
}
