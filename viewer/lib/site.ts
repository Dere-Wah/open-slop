// Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.

/**
 * What the page says about itself before a room is joined: the public URL
 * and the repository, for the <head> metadata and the social card. Once
 * connected, the live values come from the projector's rundown instead.
 */
export const SITE = {
  url: "https://openslop.live",
  owner: "Dere-Wah",
  repo: "open-slop",
  branch: "story",
  title: "OpenSlop | The First Ever Open Source Movie",
  description:
    "A movie written by its audience, screened around the clock. The screenplay is a branch on GitHub: add a scene in a pull request, get it approved, and it is on air in the next screening.",
} as const;
