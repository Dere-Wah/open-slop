import { NextRequest, NextResponse } from "next/server";
import { AccessToken } from "livekit-server-sdk";
import { INFINITE, PARTNER_TOKEN_TTL_S, isPartnerOrigin } from "@/lib/partners";

/**
 * `GET /api/infinite/token` — The Infinite's way into the show's room.
 *
 * theinfinite.tv places the screening in a virtual theatre and needs a
 * viewer token from a browser on their origin. This mints one: subscribe to
 * the streamer's tracks, no media publish, a short life (they reconnect), and
 * a random `infinite-` identity, which is what the viewer trusts to badge a
 * chat line as coming from there — a token from `/api/livekit/token` can
 * never carry that prefix. `?chat=1` adds the data-channel publish grant the
 * chat protocol needs (see INTEGRATION.md); without it the token is
 * subscribe-only, as their default request asks.
 *
 * The response is CORS-scoped to their origins (plus localhost for their
 * tests), and a request without an allowed `Origin` is refused outright. That
 * is a browser fence, not authentication: anyone can read the room. The
 * LiveKit secret stays server-side.
 */

export const dynamic = "force-dynamic";

const NAME_MAX = 32;

function cors(origin: string): HeadersInit {
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "600",
    vary: "origin",
    "cache-control": "no-store",
  };
}

function refused(origin: string | null): NextResponse {
  return NextResponse.json(
    { error: "This endpoint serves theinfinite.tv only.", origin },
    { status: 403, headers: { "cache-control": "no-store", vary: "origin" } },
  );
}

export async function OPTIONS(request: NextRequest): Promise<NextResponse> {
  const origin = request.headers.get("origin");
  if (!origin || !isPartnerOrigin(origin)) return refused(origin);
  return new NextResponse(null, { status: 204, headers: cors(origin) });
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const origin = request.headers.get("origin");
  if (!origin || !isPartnerOrigin(origin)) return refused(origin);

  const url = process.env.LIVEKIT_URL;
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const room = process.env.LIVEKIT_ROOM || "open-slop";
  if (!url || !apiKey || !apiSecret) {
    console.error("/api/infinite/token: LIVEKIT_URL / _API_KEY / _API_SECRET not set");
    return NextResponse.json(
      { error: "The show is not available right now." },
      { status: 503, headers: cors(origin) },
    );
  }

  const params = request.nextUrl.searchParams;
  const name = (params.get("name") ?? "")
    .replace(/[^\w -]/g, "")
    .slice(0, NAME_MAX);
  const chat = params.get("chat") === "1";
  const identity = `${INFINITE.identityPrefix}${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;

  const token = new AccessToken(apiKey, apiSecret, {
    identity,
    name: name || undefined,
    ttl: PARTNER_TOKEN_TTL_S,
  });
  token.addGrant({
    roomJoin: true,
    room,
    canPublish: false,
    canPublishData: chat,
    canSubscribe: true,
  });

  return NextResponse.json(
    {
      url,
      token: await token.toJwt(),
      room,
      identity,
      expires_at: new Date(Date.now() + PARTNER_TOKEN_TTL_S * 1000).toISOString(),
      tracks: { video: "main_video", audio: "main_audio" },
      chat: chat ? { topic: "show.chat", source: INFINITE.source } : null,
    },
    { headers: cors(origin) },
  );
}
