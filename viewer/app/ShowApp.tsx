"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConnectionState, RemoteTrack, Room, RoomEvent } from "livekit-client";

import { ShowPage } from "./ShowPage";
import type { ChatEntry } from "./components/Chat";
import type { Rundown as RundownData, RundownScene, ShowState } from "@/lib/types";

/**
 * The viewer: joins the show's LiveKit room (subscribe-only for media), plays
 * the broadcast, and shows what is on air.
 *
 * Three inputs arrive from the room, each on the transport that fits it:
 *  - media tracks (the film itself);
 *  - a `show.state` data packet once a second — the live cursor and countdown;
 *  - room metadata, delivered on join and on change — the whole rundown.
 *
 * It never calls GitHub. The rundown links out to it; that is all.
 *
 * Trust is by participant identity. Every viewer holds a data-publish grant
 * (that is how chat works), so a `show.state` packet is honoured only when it
 * comes from the streamer, and a chat message may only sign as the show when
 * it does too. Room metadata is written through the server API, which no
 * viewer token can reach, so it needs no such check.
 *
 * The LiveKit client resumes transient drops on its own; when it gives up,
 * this component re-fetches a token and rejoins in a loop.
 *
 * Whenever nothing is on air the player is covered by the curtain — the
 * pre-show drawn on this side — rather than showing the black frames the
 * stream carries meanwhile. "Nothing on air" is read off the cursor's status,
 * and off its silence: a cursor arrives every second, so one that has not
 * arrived for `STATE_STALE_MS` means the projector is gone, and the last
 * packet it sent must not keep a stale "live" card up.
 *
 * Everything visual is ShowPage's; this component only owns the room.
 */

const CHAT_TOPIC = "show.chat";
const STATE_TOPIC = "show.state";
const STREAMER_IDENTITY = "streamer";
const SHOW_AUTHOR = "show";
const RECONNECT_DELAY_MS = 3_000;
const CHAT_LIMIT = 200;
const STATE_STALE_MS = 6_000;

type Status = "connecting" | "live" | "offline";

function safeParse<T>(bytes: Uint8Array): T | null {
  try {
    return JSON.parse(new TextDecoder().decode(bytes)) as T;
  } catch {
    return null;
  }
}

function parseMetadata(metadata: string | undefined): RundownData | null {
  if (!metadata) return null;
  try {
    const parsed = JSON.parse(metadata) as Partial<RundownData>;
    if (
      !parsed ||
      typeof parsed.screening !== "number" ||
      typeof parsed.story_url !== "string" ||
      !Array.isArray(parsed.episodes)
    ) {
      return null;
    }
    return parsed as RundownData;
  } catch {
    return null;
  }
}

export function ShowApp() {
  const [status, setStatus] = useState<Status>("connecting");
  const [videoTrack, setVideoTrack] = useState<RemoteTrack | null>(null);
  const [audioTrack, setAudioTrack] = useState<RemoteTrack | null>(null);
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [showState, setShowState] = useState<ShowState | null>(null);
  const [rundown, setRundown] = useState<RundownData | null>(null);
  const [endsAtLocal, setEndsAtLocal] = useState<number | null>(null);
  const [stateSeenAt, setStateSeenAt] = useState<number | null>(null);
  const [tick, setTick] = useState(() => Date.now());
  const roomRef = useRef<Room | null>(null);
  const nextId = useRef(0);

  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1_000);
    return () => clearInterval(id);
  }, []);

  const appendChat = useCallback((author: string, text: string) => {
    nextId.current += 1;
    const entry: ChatEntry = { id: nextId.current, author, text };
    setChat((prev) => [...prev.slice(-CHAT_LIMIT), entry]);
  }, []);

  const applyState = useCallback((state: ShowState) => {
    setShowState(state);
    setStateSeenAt(Date.now());
    // Correct the server's end time into the viewer's own clock, so the
    // countdown is right even when the two clocks disagree.
    if (state.status === "live" && typeof state.ends_at === "number") {
      const skew = Date.now() - state.now;
      setEndsAtLocal(state.ends_at + skew);
    } else {
      setEndsAtLocal(null);
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let room: Room | null = null;

    async function join(): Promise<void> {
      while (!disposed) {
        try {
          const response = await fetch("/api/livekit/token", { cache: "no-store" });
          if (!response.ok) throw new Error(`token: ${response.status}`);
          const { url, token } = (await response.json()) as {
            url: string;
            token: string;
          };

          room = new Room({ adaptiveStream: true });
          roomRef.current = room;
          room.on(RoomEvent.TrackSubscribed, (track) => {
            if (track.kind === "video") setVideoTrack(track);
            if (track.kind === "audio") setAudioTrack(track);
          });
          room.on(RoomEvent.TrackUnsubscribed, (track) => {
            if (track.kind === "video") setVideoTrack(null);
            if (track.kind === "audio") setAudioTrack(null);
          });
          room.on(RoomEvent.RoomMetadataChanged, (metadata) => {
            const parsed = parseMetadata(metadata);
            if (parsed) setRundown(parsed);
          });
          room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
            const fromStreamer = participant?.identity === STREAMER_IDENTITY;
            if (topic === CHAT_TOPIC) {
              const message = safeParse<{ author?: string; text?: string }>(payload);
              if (!message) return;
              let author = String(message.author ?? "").slice(0, 32);
              const text = String(message.text ?? "").slice(0, 500);
              // Only the streamer speaks as the show; a viewer who signs as
              // "show" is shown as a viewer with that name, not as the show.
              if (author === SHOW_AUTHOR && !fromStreamer) author = `"${SHOW_AUTHOR}"`;
              if (author && text) appendChat(author, text);
            } else if (topic === STATE_TOPIC) {
              if (!fromStreamer) return;
              const state = safeParse<ShowState>(payload);
              if (state && typeof state.now === "number") applyState(state);
            }
          });
          room.on(RoomEvent.ConnectionStateChanged, (state) => {
            if (state === ConnectionState.Connected) setStatus("live");
          });
          room.on(RoomEvent.Disconnected, () => {
            setStatus("offline");
            setVideoTrack(null);
            setAudioTrack(null);
            if (!disposed) setTimeout(() => void join(), RECONNECT_DELAY_MS);
          });

          await room.connect(url, token);
          setStatus("live");
          // Room metadata is delivered with the join, so the rundown is
          // available immediately without any request.
          const initial = parseMetadata(room.metadata);
          if (initial) setRundown(initial);
          return;
        } catch (error) {
          console.error("room join failed:", error);
          setStatus("offline");
          await new Promise((resolve) => setTimeout(resolve, RECONNECT_DELAY_MS));
        }
      }
    }

    void join();
    return () => {
      disposed = true;
      roomRef.current = null;
      void room?.disconnect();
    };
  }, [appendChat, applyState]);

  const sendChat = useCallback(
    (author: string, text: string) => {
      const room = roomRef.current;
      if (!room || room.state !== ConnectionState.Connected) return false;
      const packet = new TextEncoder().encode(JSON.stringify({ author, text }));
      room.localParticipant
        .publishData(packet, { reliable: true, topic: CHAT_TOPIC })
        .catch((error) => console.error("chat send failed:", error));
      appendChat(author, text);
      return true;
    },
    [appendChat],
  );

  const currentScene = useMemo<RundownScene | null>(() => {
    if (!rundown || !showState || showState.screening !== rundown.screening) return null;
    const episode = rundown.episodes[showState.episode_index ?? -1];
    if (!episode) return null;
    return episode.scenes.find((scene) => scene.n === showState.scene_number) ?? null;
  }, [rundown, showState]);

  // The projector speaks once a second; silence means it is gone, whatever
  // its last packet said. Until it speaks at all, the room is off air too.
  const offAir =
    status === "live" && (stateSeenAt === null || tick - stateSeenAt > STATE_STALE_MS);

  return (
    <ShowPage
      connection={status}
      showState={showState}
      rundown={rundown}
      currentScene={currentScene}
      endsAtLocal={endsAtLocal}
      offAir={offAir}
      videoTrack={videoTrack}
      audioTrack={audioTrack}
      chat={chat}
      onSendChat={sendChat}
    />
  );
}
