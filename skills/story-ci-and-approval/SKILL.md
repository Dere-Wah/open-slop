---
name: story-ci-and-approval
description: How Open Slop lets anyone merge into the film with no maintainer — the story branch's three workflows, the security invariants that make pull_request_target safe, the tamper-proof vote anchor, the quorum and cooling-off algorithm, account-age and block rules, auto-merge re-arming, the post-merge tip check, and the rulesets that hold it together. Read before touching .github/workflows on the story branch or the repository's settings.
---

# Story CI and the audience vote

The story branch merges pull requests with **no human with write access in the
loop**. Three workflows on the story branch do it, all of them thin shims that
run code from this branch. This guide is the design and its invariants.

## Why the workflows live on the story branch but the logic lives here

`pull_request_target` and `issue_comment` run the workflow file **from the
default branch**, not from the pull request. So the workflow files sit on
`story` (the default branch), where the allowlist keeps pull requests off them,
and they check `story-tools/` out **from this branch at a pinned ref** to do
the actual judging. A story contributor can therefore neither edit the check
nor the checker. `GITHUB_SETUP.todo.md` tracks moving that ref from the branch
name to a commit sha once the repository is public.

## The three workflows

| Workflow | Trigger | Posts |
| --- | --- | --- |
| `story-validate` | `pull_request_target` on `story`; `push` to `story` | commit status `story/validate`; sticky comment with the report; on push, an issue when the tip does not validate |
| `story-quorum` | `issue_comment` (created/edited/deleted); `pull_request_target` opened/reopened/synchronize; hourly cron | commit status `story/quorum`; sticky tally comment; keeps auto-merge armed |
| `story-welcome` | `pull_request_target` opened | one greeting comment with the rules |

Both statuses are **required checks** in the `story` ruleset, with GitHub
Actions as their only accepted source, so nobody can hand-post a green one.

## Security invariants (`story-validate`)

1. **Never execute anything from the pull request.** The PR head is checked
   out as data into `story-pr/` and read as text. No `pip install`, no build,
   no script from it. The validator has no dependencies for exactly this
   reason.
2. **Never interpolate untrusted values with `${{ }}`** into a shell line or an
   inline script. Filenames and the validator's report flow through files
   (`changed.tsv`, `report.txt`) and environment variables. Tabs and newlines in
   a filename are replaced before the TSV is written.
3. **Sticky comments are the bot's own.** Marker comments are found with
   `user.login === "github-actions[bot]"`, so a contributor who pastes the
   marker does not hand the bot a comment to overwrite.
4. **`persist-credentials: false`** on every checkout; the token is never left
   on disk next to PR data.

## The vote (`story-quorum`)

Constants at the top of the script: `QUORUM = 3`, `COOLING_OFF_HOURS = 6`,
`MIN_ACCOUNT_AGE_DAYS = 30`.

**The anchor.** A vote counts only if cast after the head was pushed. The push
time is **not** read from the commit — committer dates are attacker-controlled,
and a backdated amend would carry old approvals onto new content. It is the
`created_at` of the earliest `story/validate` or `story/quorum` status the bot
posted on the head sha: GitHub timestamps that server-side when the push
triggered a run. Votes in the seconds between push and first status are lost,
which is the safe direction. With no status yet (first run on a new head) the
anchor is *now*, so nothing pre-push counts. This is why `story-quorum` also
runs on `synchronize`: it plants the anchor on every new head immediately.

**The tally.** Walk every comment on the pull request:

- Skip bots and the author. Skip anything created before the anchor.
- `/approve` sets the voter's vote to yes; `/unapprove` to no. The latest wins.
- A voter counts only if their account is a `User` at least
  `MIN_ACCOUNT_AGE_DAYS` old (`users.getByUsername`, cached per run). Voters
  who fail this are listed in the tally so the missing vote is explained.
- `/block` from an `OWNER`/`MEMBER`/`COLLABORATOR` blocks; `/unblock` from one
  lifts it. The latest wins. A block is **not** subject to the anchor; it
  survives pushes.

**The status.** `failure` "blocked by a maintainer"; `success` when
`count ≥ QUORUM` and `now ≥ anchor + COOLING_OFF_HOURS`; otherwise `pending`
with the count and the hours left. Cooling-off counts from the anchor, so a
placeholder opened early and filled in late waits the full window after its
real push.

**Auto-merge.** GitHub drops auto-merge when someone without write access
pushes — which is every contributor here. So `armAutoMerge()` runs on every
evaluation unless blocked: it enables squash auto-merge if `pr.auto_merge` is
unset, and if GitHub answers that the pull request is already in a clean state
(both checks green), it merges by hand with `pulls.merge(squash)`, which is
what auto-merge would have done. Squash is load-bearing: one contribution is
one commit, and per-scene credit reads the squash commit's author and its
`Co-authored-by` trailers.

**Robustness.** The hourly sweep evaluates every open pull request in its own
`try/catch`, so one 404 does not abort the rest. `concurrency` serialises runs
per pull request.

## The post-merge tip check

Two pull requests that each validate can merge into a film that does not — one
deletes `0030`, the other adds `0040` with `continue: true` that now continues
from something else. The ruleset does not use strict (up-to-date) status
checks, because that would force every open pull request to rebase after every
merge, which no-write-access contributors cannot do quickly. Instead
`story-validate`'s `branch-tip` job runs on every push to `story`, validates the
whole film, and opens (or updates, then closes) a bot issue when it fails. The
projector meanwhile airs its last good snapshot and shows a notice. This is a
deliberate trade: rare, visible, self-healing breakage over a rebase treadmill.

## Rulesets (done once, tracked in `GITHUB_SETUP.todo.md`)

- **`story`** (default): pull request required with **0** required approvals;
  required checks `story/validate` and `story/quorum` sourced from GitHub
  Actions; non-strict; block force-push and deletion; **squash-only** merge;
  "Allow auto-merge" on at the repository level.
- **`code`**: pull request required, at least one review, `code-ci` required,
  restricted push, block force-push.
- Actions settings: workflows need `contents: write`, `statuses: write`,
  `pull-requests: write`, `issues: write` (each file declares the minimum it
  uses); "Allow GitHub Actions to create and approve pull requests" is **off**
  (the bot never opens or approves one); fork pull requests to the default
  branch require no approval to run (they are data-only).

## Testing a change to these workflows

There is no local runner that reproduces `pull_request_target`. What works:

1. Parse every workflow with a YAML loader and `node --check` each inline
   script wrapped in an async function (the repository's verification does
   exactly this; `actionlint` when available adds expression checks).
2. Push the change to a scratch repository with the same two-branch layout,
   open a pull request from a **fork** account, and walk the path: report
   comment appears; `/approve` from a fresh account is listed as too new;
   three eligible approvals go `pending — cooling off`; a push resets the tally
   and the clock; `/block` flips the status to failure; a merge fires only after
   the window.
3. When the validator changes, move the pinned ref in `story-validate.yml` on
   the story branch **after** this branch's change has landed, not before.
