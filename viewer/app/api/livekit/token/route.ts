import { NextRequest, NextResponse } from "next/server";
import { AccessToken } from "livekit-server-sdk";

/**
 * `/api/livekit/token?name=<display name>` — a viewer's way into the show's
 * room.
 *
 * Mints a short-lived LiveKit token: subscribe plus data-channel publish
 * (chat), never media publish — the streamer is the room's only media
 * publisher. The viewer's identity is a random `v-` prefixed id minted
 * here, so a visitor can never claim the streamer's identity. The LiveKit
 * secret stays server-side; the browser receives only the room URL, the
 * room name, and the scoped JWT.
 */

// Config is read per request: the room can move without a rebuild.
export const dynamic = "force-dynamic";

const NAME_MAX = 32;

export async function GET(request: NextRequest): Promise<NextResponse> {
  const url = process.env.LIVEKIT_URL;
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const room = process.env.LIVEKIT_ROOM || "open-slop";
  if (!url || !apiKey || !apiSecret) {
    console.error(
      "/api/livekit/token: LIVEKIT_URL / _API_KEY / _API_SECRET not set",
    );
    return NextResponse.json(
      { error: "The show is not available right now." },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }

  const name = (request.nextUrl.searchParams.get("name") ?? "viewer")
    .replace(/[^\w -]/g, "")
    .slice(0, NAME_MAX);
  const token = new AccessToken(apiKey, apiSecret, {
    identity: `v-${crypto.randomUUID().slice(0, 12)}`,
    name,
    ttl: "1h",
  });
  token.addGrant({
    roomJoin: true,
    room,
    canPublish: false,
    canPublishData: true,
    canSubscribe: true,
  });

  return NextResponse.json(
    { url, room, token: await token.toJwt() },
    { headers: { "cache-control": "no-store" } },
  );
}
