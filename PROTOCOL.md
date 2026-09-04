# The wire

Everything a viewer of OpenSlop knows arrives through one LiveKit room. This
document is the contract for what travels in it: the film's tracks, the
projector's cursor and rundown, and the chat. Anyone who can join the room (see
[INTEGRATION.md](./INTEGRATION.md) for how) can build their own presentation
from these alone; the viewer in `viewer/` uses nothing else and never calls
GitHub for what is on screen.

Code owns the shapes: `viewer/lib/types.ts` (the TypeScript types the viewer
reads), `projector/broadcast.py` (what the projector writes), and
`projector/publisher.py` (the show's chat lines). When they and this file
disagree, the code is right and this file has a bug; fix it in the same change.

## Participants

| Identity | Who | Publishes |
| --- | --- | --- |
| `streamer` | The projector. One per room. | The two media tracks, `show.state`, room metadata, and chat lines as `author: "show"`. |
| `v-<12 hex>` | A viewer on openslop.live. | Chat only. |
| `infinite-<12 hex>` | A viewer on The Infinite. | Chat only, when their token asked for it. |

Identity is assigned by the token servers and cannot be chosen by a client, so
it is the one thing a reader may trust. Honour `show.state` and `author:
"show"` only from `streamer`; decide where a chat line was typed by the prefix.

## Media

Two tracks, published by `streamer` and left up for the projector's whole life:

| Track name | Kind | LiveKit source | Content |
| --- | --- | --- | --- |
| `main_video` | video | `CAMERA` | The film, 16:9, at the model's resolution and frame rate. Black while nothing is on air. |
| `main_audio` | audio | `MICROPHONE` | The film's sound, s16 PCM. Silence while nothing is on air. |

They are separate publications; subscribe to either.

## `show.state`: the cursor (projector → everyone)

Data topic `show.state`, published by `streamer` once a second, reliable
delivery, one JSON object in UTF-8. Every packet carries:

| Field | Type | Meaning |
| --- | --- | --- |
| `v` | `1` | Protocol version. |
| `topic` | `"state"` | Always. |
| `status` | string | One of the five below. |
| `now` | epoch ms | The projector's clock when it sent the packet. Every other time in the packet is on this clock; convert to yours with `skew = Date.now() - now`. |
| `stalled` | boolean | Frames are not arriving as fast as they play. Always `true` while not `live`. |

A packet is a full snapshot, never a delta: draw from the latest one and forget
the rest. If none has arrived for about six seconds the projector is gone;
treat the room as off air rather than keep the last card up.

### Statuses

```
warming ──▶ loading ──▶ live ──▶ intermission ──▶ loading ──▶ live …
                          │
                          └──▶ downtime ──▶ loading ──▶ live
```

| `status` | Meaning | Extra fields |
| --- | --- | --- |
| `warming` | The projector is up but the model has not answered yet, or the story branch cannot be read. | `detail` (string, optional): why, in a sentence. |
| `loading` | The curtain. The model is building the opening of a screening and nothing plays until enough film is buffered. | `screening`, `sha`, `episode_title` (the first episode), `buffered_seconds`, `target_seconds`, `film_seconds`, `scene_total`, `restart` (boolean: this screening was on air and is starting over). |
| `live` | On air. | The scene fields below. |
| `intermission` | The loop point: a screening ended and the stream is held before the next one. The buffer fields describe the screening about to start. | `ended_screening`, `resumes_at` (epoch ms: when the next screening's first frame is due), `hold_seconds` (the whole pause), plus `screening`, `sha`, `episode_title`, `buffered_seconds`, `target_seconds`, `film_seconds`, `scene_total` for the next one. |
| `downtime` | The model session was lost. The screening restarts from the top, through `loading`. | `detail`. |

### The scene fields, while `live`

| Field | Type | Meaning |
| --- | --- | --- |
| `screening` | int | The screening number, counting up since the projector started. Joins with `Rundown.screening`. |
| `sha` | string | The story branch commit this screening was snapshotted at. |
| `next_sha` | string, optional | The commit the *next* screening is already snapshotted at, when known. |
| `episode_index` | int | 0-based, into `Rundown.episodes`. |
| `episodes_total` | int | |
| `episode_title` | string | The episode's `# Title`, or its file name when it has none. |
| `episode_file` | string | The file on the story branch, e.g. `0040-the-keeper.md`. |
| `scene_number` | int | 1-based within the episode. |
| `scene_count` | int | Scenes in this episode. |
| `global_index` | int | 1-based across the screening. |
| `global_total` | int | Scenes in the screening. |
| `author` | string | Who wrote the scene: `@login` when known, else the commit's name. |
| `author_url` | string or null | Their GitHub profile. |
| `commit` | string | The short sha that last touched the scene's prose. |
| `commit_url` | string or null | That commit on GitHub. |
| `line_start`, `line_end` | int | The scene's prose lines in `episode_file` at `sha`, 1-based inclusive, without the `---` fences and the header. Absent or 0 from an older projector. |
| `ends_at` | epoch ms | When the screening's last frame is out. |
| `next_start_at` | epoch ms | `ends_at` plus the intermission: when the next screening starts. |
| `progress` | 0..1 | How far through the screening, by seconds. |

A countdown reads `next_start_at` (or `resumes_at` during the intermission),
corrected by the skew from `now`.

## Room metadata: the rundown (projector → everyone)

LiveKit delivers the room's metadata string on join and on every change. It is
the programme for one screening: every episode and scene with its credit and
links, no prompt bodies. The projector writes it when a screening's first clip
starts, or at snapshot time while nothing is on air so the curtain can show
what is coming. Join it to the cursor on `screening`; a cursor and a rundown
with different `screening` values describe different programmes, so wait.

```json
{
  "v": 1,
  "screening": 12,
  "sha": "d5b84a2…",
  "story_url": "https://github.com/Dere-Wah/open-slop/tree/story",
  "total_seconds": 85.4,
  "truncated": false,
  "episodes": [
    {
      "i": 0,
      "file": "0010-the-lighthouse.md",
      "title": "The lighthouse",
      "seconds": 27.5,
      "scenes": [
        {
          "n": 1,
          "seconds": 9.417,
          "author": "@mira",
          "author_url": "https://github.com/mira",
          "commit": "8a1f0c3",
          "commit_url": "https://github.com/Dere-Wah/open-slop/commit/8a1f0c3…",
          "lines": [7, 9],
          "contributors": [{ "name": "@mira", "url": "https://github.com/mira" }]
        }
      ]
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `v` | Protocol version, `1`. |
| `screening`, `sha` | As in the cursor. |
| `story_url` | The story branch on GitHub. |
| `total_seconds` | The whole screening. |
| `episodes[].i` | 0-based; `title` is null when the file has no `# Title`. |
| `episodes[].scenes[]` | In play order. `n` is 1-based within the episode; `seconds` is the snapped clip length the model will actually produce. `lines` is the prose range at `sha`, the same as the cursor's `line_start`/`line_end`. |
| `scenes[].contributors` | Everyone `git blame` and `Co-authored-by` credit for the scene's lines, `author` first. Bots are left out. |
| `truncated` | `true` when the tail was cut to fit LiveKit's metadata cap. |

LiveKit caps metadata size. When a rundown does not fit, the projector drops
the per-scene `contributors` lists first, then cuts episodes from the tail and
sets `truncated: true`. Say so rather than presenting the list as complete.

## `show.chat`: the chat (everyone ↔ everyone)

Data topic `show.chat`, reliable delivery, one JSON object in UTF-8. Anyone
with a data-publish grant may send; LiveKit does not echo a packet to its
sender, so append your own line locally.

```json
{
  "v": 1,
  "source": "open-slop",
  "author": "@mira",
  "text": "the lighthouse shot is gorgeous",
  "user_id": "usr_8f3a",
  "user_url": "https://example.tv/u/mira"
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `author` | yes | Display name, up to 32 characters, shown as typed. openslop.live viewers write `@handle`. |
| `text` | yes | Up to 500 characters of plain text. The viewer renders only this repository's pull-request links as anything other than text. |
| `v` | no | Protocol version, `1`. Absent means 1. |
| `source` | no | Where the line was typed: `"open-slop"` or `"infinite"`. Absent means `"open-slop"`. A convenience tag, not proof (see below). |
| `user_id` | no | The sending site's stable id for the author, opaque. The viewer ignores it. |
| `user_url` | no | A profile link on the sending site. Reserved; not rendered. |

Unknown fields are ignored, so a sender may add one without breaking any
reader.

**The show's own lines.** `streamer` sends announcements (a screening going on
air, a capacity note, an error) as `author: "show"`. A viewer shows those as
the repository's bot; the same author from any other identity is a viewer
who typed the word, and the viewer quotes it to say so.

**Trust.** Anyone can write any `author` and any `source`. What a reader may
rely on is the sender's LiveKit identity, read off `participant.identity` in
the data handler: `streamer` for the show, `v-` for openslop.live, `infinite-`
for The Infinite. The viewer badges a line as the theatre's on that prefix
alone.

There is no rate limit in the room. Apply one at your own edge before
publishing.

## Changing the protocol

- Add, do not rename or remove. A new field is optional and readers ignore
  what they do not know; a field that changes meaning or type bumps `v`, and
  the writer keeps sending the old shape until every reader has moved.
- The three sites that write to the wire are `projector/broadcast.py`,
  `projector/publisher.py`, and `viewer/app/ShowApp.tsx` (`sendChat`). A change
  to any of them updates `viewer/lib/types.ts` and this file in the same
  change, and INTEGRATION.md if a partner is affected.
