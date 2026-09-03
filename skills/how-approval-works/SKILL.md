---
name: how-approval-works
description: How an Open Slop story pull request gets merged — the audience vote by /approve comment, who may vote, the quorum and the six-hour cooling-off counted from the last push, why a push resets the vote, the /block veto and model moderation, and how on-screen credit is assigned per scene.
---

# How approval works

There is no maintainer who approves the story. The audience does. This guide is
the whole rule.

## The vote is a comment

GitHub's built-in "required approvals" only counts people with write access to
the repository, and Open Slop gives write access to no one. So the vote does not
use GitHub reviews. It uses **comments**:

- To approve a pull request, comment **`/approve`** on it. `/unapprove`
  withdraws. Your latest comment of the two is your vote.
- A bot counts the distinct people who have `/approve`d — not counting the pull
  request's author, not counting bots, and not counting accounts younger than
  **30 days** (the tally names them separately so nobody wonders where a vote
  went).
- When the count reaches the **quorum of three**, and **six hours** have passed
  since the pull request's last push, the bot marks it approved and GitHub
  merges it automatically.

You will see a running tally comment from the bot: `2/3 approvals`. When it hits
`3/3` and the clock has run, the merge happens on its own. No human presses a
button. The bot re-checks on every comment, on every push, and once an hour, so
a pull request that goes quiet still merges when its six hours are up.

## Why the cooling-off window

A pull request cannot merge the instant three friends show up. Six hours must
pass after its **latest push** first, so the room has a chance to see what will
actually merge. This is the main defence against a scene being rushed through by
a small group before anyone else notices — and because the clock starts at the
last push rather than at opening, a placeholder opened early and filled in late
still waits its six hours.

## Approvals are for the words that are there

If the scene changes after people have approved — you push a new commit to the
pull request — the approvals reset and the six hours restart. People approve the
exact words in front of them, not a promise. Get your edits in before you gather
votes.

How the reset is anchored matters, so it is written down: the bot does **not**
trust the commit's own timestamp (anyone can set that). It reads the time
GitHub itself recorded the first check running on the new head. A vote counts
only if it was cast after that moment. Nothing in a commit can move it.

## The safety valves

This is a public film that strangers watch, so two backstops sit behind the
vote:

- **`/block`** — a project maintainer can veto a pull request that is harmful
  or off-limits. A block stops the merge regardless of the vote, survives new
  pushes, and lifts only with `/unblock` from a maintainer.
- **Model moderation** — the video model moderates every prompt it is given, so
  a prompt that slips through still will not render into the broadcast.

And one behind the merge: after every merge the whole branch is validated again.
Two pull requests that were each fine alone can combine into a film that is not
(one deletes the episode the other continues from). When that happens the bot
opens an issue, and the projector keeps airing the last good film until a fix is
voted in.

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
  link. `Co-authored-by:` trailers on the merge commit are credited too, so a
  pull request several people pushed to credits all of them.

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
4. At three approvals, six hours after your last push, with no `/block`, the
   pull request merges itself.
5. The projector snapshots the branch about a minute of film before each
   screening starts. Your scene is on air from the first screening snapshotted
   after the merge, with your name on it. The viewer's countdown shows which
   story version the next screening will play.
