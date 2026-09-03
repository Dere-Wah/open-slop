---
name: how-approval-works
description: How an Open Slop story pull request gets merged — the audience vote by /approve comment, the quorum and cooling-off window, stale-vote reset, the /block veto and model moderation, and how on-screen credit is assigned per scene.
---

# How approval works

There is no maintainer who approves the story. The audience does. This guide is
the whole rule.

## The vote is a comment

GitHub's built-in "required approvals" only counts people with write access to
the repository, and Open Slop gives write access to no one. So the vote does not
use GitHub reviews. It uses **comments**:

- To approve a pull request, comment **`/approve`** on it.
- A bot counts the distinct people who have `/approve`d — not counting the pull
  request's author, and not counting bots.
- When the count reaches the **quorum of three**, and the pull request has been
  open past a short **cooling-off window**, the bot marks it approved and GitHub
  merges it automatically.

You will see a running tally comment from the bot: `2/3 approvals`. When it hits
`3/3`, the merge happens on its own. No human presses a button.

## Why the cooling-off window

A brand-new pull request cannot merge the instant three friends show up. It must
be open for a set time first, so the room has a chance to see it. This is the
main defence against a scene being rushed through by a small group before anyone
else notices.

## Approvals are for the words that are there

If the scene changes after people have approved — you push a new commit to the
pull request — the approvals reset. People approve the exact words in front of
them, not a promise. Get your edits in before you gather votes.

## The safety valves

This is a public film that strangers watch, so two backstops sit behind the
vote:

- **`/block`** — a project maintainer can veto a pull request that is harmful
  or off-limits. A block stops the merge regardless of the vote.
- **Model moderation** — the video model moderates every prompt it is given, so
  a prompt that slips through still will not render into the broadcast.

Keep contributions to something a stranger can enjoy. The vote is the main gate;
these are the floor.

## How you get credited

Credit is per scene, and it comes straight from git — nobody maintains a credits
list by hand.

- The name on screen for a scene is **the author of the most recent commit that
  touched that scene's prompt lines**. That is read with `git blame` on exactly
  those lines.
- Everyone who has shaped the scene is kept as its contributors, newest first,
  and shown in the rundown. A scene four people refined lists four names.
- Your GitHub handle appears when your commit carries it (it does, for a normal
  GitHub merge), linking your profile; otherwise your git name shows without a
  link.

The rule in one line: **on-screen credit means you wrote those words**, not that
you had the idea. Rewrite someone's scene and the screen names you — and the
full history is one click away on the commit link. For a film written together,
that is the fair and legible rule, so it is written down here rather than left
to be discovered.

## The whole path, start to finish

1. Add or edit one episode file; open a pull request.
2. The format checker runs and comments what it found (and where your episode
   lands, and the film's new runtime).
3. People watch and `/approve`.
4. At three approvals, past the cooling-off window, with no `/block`, the pull
   request merges itself.
5. At the next screening, the projector re-reads the branch and your scene is on
   air, with your name on it.
