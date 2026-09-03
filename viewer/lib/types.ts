// The two payloads the projector sends the viewer.
//
// `ShowState` is the live cursor on the `show.state` data topic, republished
// once a second. `Rundown` is the whole screening, written into LiveKit room
// metadata when the screening's first clip starts and delivered to a viewer on
// join. The viewer joins them on (screening, scene) — never by calling GitHub.
//
// Both come off the wire from the room's streamer participant only; the viewer
// ignores a `show.state` packet from anyone else.

// `warming`: the projector is up but the model has not answered, or the story
// cannot be read. `loading`: the curtain — the model is building the opening
// and nothing plays until enough film is buffered. `downtime`: the model was
// lost; the screening restarts from the top (through `loading`). `live`: on air.
export type ShowStatus = "warming" | "loading" | "downtime" | "live";

export interface ShowState {
  v: number;
  topic: "state";
  status: ShowStatus;
  detail?: string; // why nothing is on air, while not live
  screening?: number;
  sha?: string;
  next_sha?: string; // what the next screening was snapshotted at, when known
  // While `loading`:
  buffered_seconds?: number; // film built and waiting behind the curtain
  target_seconds?: number; // what must be built before the first frame
  film_seconds?: number; // the whole screening's length
  scene_total?: number;
  restart?: boolean; // this screening was on air and is starting over
  episode_index?: number;
  episodes_total?: number;
  episode_title?: string;
  episode_file?: string;
  scene_number?: number;
  scene_count?: number;
  global_index?: number;
  global_total?: number;
  author?: string;
  author_url?: string | null;
  commit?: string;
  commit_url?: string | null;
  now: number; // server epoch ms, for clock-skew correction
  ends_at?: number; // server epoch ms when this screening ends (the loop point)
  stalled?: boolean;
  progress?: number; // 0..1 across the screening
}

export interface Contributor {
  name: string; // already "@login" or a display name
  url: string | null;
}

export interface RundownScene {
  n: number; // 1-based within the episode
  seconds: number;
  author: string;
  author_url: string | null;
  commit: string;
  commit_url: string | null;
  contributors: Contributor[];
}

export interface RundownEpisode {
  i: number; // 0-based
  file: string;
  title: string | null;
  seconds: number;
  scenes: RundownScene[];
}

export interface Rundown {
  v: number;
  screening: number;
  sha: string;
  story_url: string;
  total_seconds: number;
  episodes: RundownEpisode[];
  truncated?: boolean; // the tail was cut to fit room metadata
}
