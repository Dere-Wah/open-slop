# Showing OpenSlop somewhere else

OpenSlop is one LiveKit room. The projector publishes the film into it and a
cursor beside it; every viewer, wherever the page lives, subscribes to the same
room. This document is the contract for a partner site that wants to show the
screening and share its chat. It is written for [The Infinite](https://theinfinite.tv),
the first, and it is additive: nothing here changes what the room already
carries.

## 1. Getting in

```
GET https://www.openslop.live/api/infinite/token
GET https://www.openslop.live/api/infinite/token?chat=1&name=<display name>
```

Call it from the browser. The endpoint answers only a request whose `Origin`
is `https://theinfinite.tv`, `https://www.theinfinite.tv`, or
`http://localhost:5187`; anything else, including no `Origin`, gets a 403. That
is a CORS fence for tidiness, not a secret: the room is public.

```json
{
  "url": "wss://<project>.livekit.cloud",
  "token": "<jwt>",
  "room": "open-slop",
  "identity": "infinite-7c1e3a9b02d4",
  "expires_at": "2026-09-04T19:09:42.073Z",
  "tracks": { "video": "main_video", "audio": "main_audio" },
  "chat": { "topic": "show.chat", "source": "infinite" }
}
```

- `url` and `token` go straight into `new Room().connect(url, token)`.
- The token lives **15 minutes** and grants `roomJoin` and `canSubscribe`;
  never media publish. Reconnect with a fresh one when LiveKit drops you.
- Its identity is random and starts with `infinite-`. Nothing else in the
  room can carry that prefix; it is how our viewer knows a chat line is yours
  (§3).
- `?chat=1` adds `canPublishData`, the one extra grant the chat protocol needs.
  Without it the token is subscribe-only. `chat` in the response is `null`
  then.
- `?name=` sets the participant's display name (letters, digits, `_`, `-`,
  space; 32 characters). Optional; the chat packet carries its own author.

## 2. What is in the room

**Room name:** `open-slop`. Everything that travels in it, field by field, is
[PROTOCOL.md](./PROTOCOL.md); this is the short version.

**One media publisher,** the participant with identity `streamer`. It publishes
two separate tracks:

| Track name | Kind | LiveKit source | Notes |
| --- | --- | --- | --- |
| `main_video` | video | `CAMERA` | The film, 16:9. Frame rate and resolution are the model's; read them off the track. |
| `main_audio` | audio | `MICROPHONE` | The film's sound, s16 PCM. Separate from the video, so you can route it to the screen's own speakers. |

Between scenes and when nothing is on air the video is black and the audio is
silence; the tracks stay published. The room has an empty-timeout of ten
minutes, so it exists whenever the projector is up.

**Two data topics** and the room metadata, all JSON:

| Channel | Who sends | What |
| --- | --- | --- |
| `show.state` | `streamer` only, once a second | The live cursor: status, what is playing, who wrote it, progress, when the next screening starts. Ignore it from any other identity. Enough to draw a now-playing card, a countdown, and a curtain. |
| room metadata | the server, on join and on change | The whole rundown for the current screening: episodes, scenes, credits, line ranges. Enough to draw a programme. |
| `show.chat` | anyone with `canPublishData` | The shared chat (§3). |

## 3. The chat

One topic, `show.chat`, reliable delivery, one JSON object per packet. The
full field table is in [PROTOCOL.md](./PROTOCOL.md#showchat-the-chat-everyone--everyone);
what matters for you:

```json
{ "v": 1, "source": "infinite", "author": "popcorn_pete", "text": "watching from the back row", "user_id": "usr_8f3a" }
```

- `author` (up to 32 characters) and `text` (up to 500) are required and shown
  as typed. Everything else is optional; unknown fields are ignored on both
  sides, so either of us can add one without breaking the other.
- Send `source: "infinite"`. Our packets carry `source: "open-slop"`; a packet
  without one is ours, from before the field.
- `user_id` is yours: your stable id for the author, opaque to us. Every
  participant receives the packet as sent, so it reaches your other viewers
  untouched.

### Telling the two chats apart

Two signals, and you should trust them in this order:

1. **The sender's LiveKit identity.** The token endpoints fix its shape:
   `infinite-…` was minted for you, `v-…` for a viewer on openslop.live,
   `streamer` is the projector. A viewer cannot choose its identity, so this
   cannot be spoofed. Read it off `participant.identity` in your
   `DataReceived` handler.
2. **The `source` tag** in the packet. A convenience for logging and display;
   anyone with a data grant can write anything there, so do not let it override
   the identity.

Our viewer badges a line as yours when the identity starts with `infinite-`,
draws your favicon after the name, and on click invites the reader to watch
from your theatre. It ignores `source` for that decision.

On your side, to show only your own users, drop packets whose identity does
not start with `infinite-`; to show both, tag ours (identity `v-…`) as coming
from openslop.live. Messages from `streamer` with `author: "show"` are the
projector's announcements (a screening starting); render or drop as you like.

### Sending

```js
room.localParticipant.publishData(
  new TextEncoder().encode(JSON.stringify({ v: 1, source: "infinite", author, text, user_id })),
  { reliable: true, topic: "show.chat" },
);
```

LiveKit does not echo a packet to its sender; append your own line locally.
Rate-limit at your edge: the room applies none.

## 4. What we ask

- Credit stays with the writers. The cursor and the rundown name the person
  who wrote each scene; if you show who is on screen, show that.
- Do not republish the tracks as your own media. Subscribe and play.
- Tell us before you change what you send on `show.chat`, and we will do the
  same; this file is the record.
