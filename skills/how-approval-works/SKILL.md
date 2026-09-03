---
name: how-approval-works
description: How an OpenSlop story pull request gets merged — the audience vote by GitHub approving review, who may vote, the short wait counted from the last push, why a push resets the vote, the /block veto and model moderation, and how on-screen credit is assigned per scene.
---

# How approval works

Nobody approves the story. The audience does. This guide is the whole rule.

The exact numbers — how many approvals, how long the wait, how old an account
must be — live in one place: the workflow that counts the vote. **The bot's
comment on your pull request always shows the current values.** This guide
describes the mechanism and does not repeat the numbers, so it never goes stale.

## The vote is a GitHub review

You approve a story pull request the way you approve any pull request:
**Files changed → Review changes → Approve → Submit review**.

GitHub's built-in "required approvals" only counts people with write access,
and OpenSlop gives write access to no one — so GitHub shows your approval with
a grey check mark and does not count it itself. A bot does:

- It counts the distinct people whose latest review on the current commit is
  **Approve** — not the author, not bots, and not accounts newer than the
  minimum age (the tally names them separately so nobody wonders where a vote
  went). Comments are not votes; `/approve` in a comment does nothing.
- To withdraw, submit a **Request changes** review. Your latest review wins.
- When the count reaches the quorum and the wait since the last push has
  passed, the bot marks the pull request approved and GitHub merges it.

The bot keeps one tally comment up to date: `1/3 approvals`, then how long
until it merges. Nobody presses a button. It re-checks on every comment, on
every push, and on a sweep every few minutes — so an approval appears in the
tally within a few minutes, or at once if anyone comments — and a pull request
that goes quiet still merges once its wait is up.

## Why there is a wait

The wait after the **last push** gives the room a moment to see what will
actually merge before it does. Because it counts from the last push and not from
opening, a placeholder opened early and filled in late still waits. The bot does
not trust the commit's own timestamp for this (anyone can set that); it reads
the time GitHub recorded the first check running on the new head.

## Approvals are for the words that are there

An approval is for the exact commit it was given on — GitHub records which one,
and nothing in a commit can change that. Push a new commit and every approval
falls away and the wait restarts. Finish editing, then gather votes.

## The safety valves

- **`/block`** — a maintainer can veto a harmful pull request. A block stops the
  merge regardless of the vote, survives pushes, and lifts only with `/unblock`.
- **Model moderation** — the video model moderates every prompt, so a prompt
  that slips through still does not render.
- **The branch is re-checked after every merge.** Two pull requests fine on
  their own can combine into a broken film (one deletes the episode the other
  depends on). The bot opens an issue; the projector keeps airing the last good
  film until a fix is voted in.

## How you get credited

Credit is per scene, read from git. Nobody maintains a credits list.

- The name on screen is the author of the most recent commit that touched that
  scene's prompt lines (`git blame` on exactly those lines).
- Everyone who shaped the scene is listed as a contributor, newest first.
- Your GitHub handle appears when your commit carries it, which a normal GitHub
  merge does. `Co-authored-by:` trailers are credited too.

In one line: **on-screen credit means you wrote those words.** Rewrite a scene
and the screen names you; the history is one click away.

## The whole path

1. Add or edit an episode file; open a pull request.
2. The format check comments what it found, where your episode lands, and the
   film's new runtime.
3. People approve it with a review. The tally comment shows what is still needed.
4. Quorum reached, wait over, no `/block`: it merges itself.
5. The projector snapshots the branch shortly before each screening. Your scene
   airs from the first screening snapshotted after the merge. The viewer's
   countdown shows which story version plays next.
