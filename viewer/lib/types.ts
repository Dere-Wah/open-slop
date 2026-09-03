// The two payloads the projector sends the viewer.
//
// `ShowState` is the live cursor on the `show.state` data topic, republished
// once a second. `Rundown` is the whole screening, written into LiveKit room
// metadata once per screening and delivered to a viewer on join. The viewer
// joins them on (screening, scene) — never by calling GitHub.

export interface ShowState {
  v: number;
  topic: "state";
  status: "warming" | "live";
  screening?: number;
  sha?: string;
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
}
