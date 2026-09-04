---
name: story-ci-and-approval
description: How OpenSlop lets anyone merge into the film with no maintainer — the story branch's three workflows, the security invariants that make pull_request_target safe, the tamper-proof vote anchor, the quorum and cooling-off algorithm, account-age and block rules, auto-merge re-arming, the post-merge tip check, and the rulesets that hold it together. Read before touching .github/workflows on the story branch or the repository's settings.
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
nor the checker. The ref is a commit sha on this branch; moving it is a
maintainer commit on `story` (admins bypass the ruleset for exactly this), made
**after** the `story-tools/` change has landed here.

## The three workflows

| Workflow | Trigger | Posts |
| --- | --- | --- |
| `story-validate` | `pull_request_target` on `story`; `push` to `story` | commit status `story/validate`; sticky comment with the report; on a failing pull request, a review of one-click `suggestion` fixes from `story-tools/doctor.py`; on push, an issue when the tip does not validate |
| `story-quorum` | `issue_comment` (created/edited/deleted); `pull_request_target` opened/reopened/synchronize; cron every 5 minutes (the review event cannot be used from forks; see below) | commit status `story/quorum`; sticky tally comment; keeps auto-merge armed |
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
5. **The fork checkout is opted in, and pinned.** `actions/checkout` v4.4+
   refuses a fork's head under `pull_request_target` unless the step sets
   `allow-unsafe-pr-checkout: true`, because most workflows execute what they
   fetch. `story-validate` sets it on the `story-pr` step and nowhere else,
   and the reason it is safe is invariant 1: nothing in `story-pr` is ever
   run, imported, or installed. Every `actions/checkout` use is pinned to a
   full commit sha (with the version in a trailing comment); a floating `@v4`
   is what silently changed under us and failed every story PR for a night,
   with the bot then telling contributors "found 0 problem(s)". Move the pin
   deliberately, and re-read this list when you do.

The report step distinguishes "the validator ran and found problems"
(`story/validate` = `failure`, the list of problems) from "a step before it
failed" (`story/validate` = `error`, a comment saying the check itself broke
and a maintainer will look). A contributor must never be blamed for our
workflow failing.

**The tally comment's screenshot strip** (how to click Approve) is
`assets/how-to-approve.png` on this branch, embedded by URL:
`raw.githubusercontent.com/<owner>/<repo>/code/assets/how-to-approve.png`. The
story branch holds no binaries. Renaming or moving it breaks the image in every
open pull request's tally on the next refresh, so change the workflow and the
file together.

**Validator output in comments.** The validator prints `::error file=…::msg`
annotations under `GITHUB_ACTIONS` so problems show inline on the diff. Both
`story-validate` comment steps run that text through `asMarkdown()`, which
turns each annotation into a list item and drops the count line, so a reader
never sees the `::error` syntax.

**The doctor's review.** When the validator exits 1, a `continue-on-error`
step runs `story-tools/doctor.py` over the same `story-pr` tree (data only,
same invariants; the doctor is part of the pinned checkout) and writes
`doctor.json`. The comment step then:

1. deletes every review comment by `github-actions[bot]` that carries
   `<!-- open-slop:doctor -->`, so the previous push's suggestions do not sit
   beside the new ones;
2. posts one review (`event: COMMENT`, `commit_id` = the head sha) with one
   inline comment per suggestion: `path`, `line` = the range's last line, `side:
   RIGHT`, plus `start_line`/`start_side` for a multi-line range, and a body of
   the doctor's sentence followed by a ```` ```suggestion ```` block (an empty
   block deletes the lines; the fence grows past any backtick run in the
   prose). A comment may sit on a line outside the diff;
3. if that call fails (a 422 on a line GitHub will not take), falls back to
   printing the same suggestions in full in the sticky comment, so the author
   still gets them;
4. adds a section to the sticky comment: how many suggestions are waiting in
   **Files changed**, the notes for what only the author can fix (renames,
   prompts under the floor), and what the validator would still say after every
   suggestion is taken.

A committed suggestion is authored by the person who clicked, with the bot as
`Co-authored-by`; `projector/story.py` drops `[bot]` co-authors so the credit
stays with the writer. Committing one is a push like any other: the quorum
tally and the cooldown clock reset.

## The vote (`story-quorum`)

Constants at the top of the script: `QUORUM`, `COOLING_OFF_MINUTES`,
`MIN_ACCOUNT_AGE_DAYS`. **They live only there.** The story branch's README and
skills describe the mechanism and tell readers to look at the bot's tally
comment for the current values, so tuning them is a one-line change with no
docs to chase. Do not copy the values into prose anywhere.

**The vote is a GitHub review, counted by us.** Anyone can submit an *Approve*
review on a public repository; GitHub shows it with a grey check and does not
count it toward its native required-reviews rule (write access only). The
ruleset therefore requires **0** native approvals and the bot's `story/quorum`
status is the gate. The bot reads `pulls.listReviews`.

**Why the bot cannot run on the review event.** `pull_request_review` from a
fork runs with a **read-only** `GITHUB_TOKEN` (and from the fork's copy of the
workflow file), and every contributor here is a fork. So the workflow does not
listen to it at all. The tally is refreshed by `issue_comment` (any comment),
`pull_request_target` (pushes) and a `*/5` cron. An approval is therefore
visible within ~5 minutes or on the next comment. Do not "fix" this by adding
the review event — it cannot post a status.

**What counts as a vote.** A review's `commit_id` must equal the pull request's
current head. GitHub records it server-side, so a push after approvals were
gathered drops them all, and nothing a contributor writes can carry an old
approval onto new content. This replaces any timestamp anchoring for votes.

**The tally.** Walk every review on the pull request, in submission order:

- Skip bots and the author. Skip reviews whose `commit_id` is not the head.
- `APPROVED` sets the reviewer's vote to yes; `CHANGES_REQUESTED` or
  `DISMISSED` to no. The latest wins. `COMMENTED` reviews are ignored.
- A voter counts only if their account is a `User` at least
  `MIN_ACCOUNT_AGE_DAYS` old (`users.getByUsername`, cached per run). Voters
  who fail this are listed in the tally so the missing vote is explained.
- `/block` from an `OWNER`/`MEMBER`/`COLLABORATOR` **comment** blocks;
  `/unblock` from one lifts it. The latest wins. A block survives pushes.
  Comments are otherwise not votes.

**The wait anchor.** The wait after the last push is **not** read from the
commit — committer dates are attacker-controlled. It is the `created_at` of the
earliest `story/validate` or `story/quorum` status the bot posted on the head
sha: GitHub timestamps that server-side when the push triggered a run. With no
status yet (first run on a new head) the anchor is *now*. This is why
`story-quorum` runs on `synchronize`: it plants the anchor on every new head.

**The status.** `failure` "blocked by a maintainer"; `success` when
`count ≥ QUORUM` and `now ≥ anchor + COOLING_OFF_MINUTES`; otherwise `pending`
with the count and the minutes left. The wait counts from the anchor, so a
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

**Robustness.** The five-minute sweep evaluates every open pull request in its own
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

## Rulesets (applied; the operator's record is `GITHUB_SETUP.todo.md`)

- **`story`** (default): pull request required with **0** required approvals;
  required checks `story/validate` and `story/quorum` sourced from GitHub
  Actions; non-strict; linear history; block force-push and deletion;
  **squash-only** merge; "Allow auto-merge" on at the repository level.
- **`code`**: pull request required, one review, the `code-ci` jobs
  `story-tools` and `viewer` required, block force-push and deletion.
- **Repository admins bypass both rulesets.** A solo maintainer otherwise
  cannot move the validator pin or edit `skills/` on `story`, nor merge into
  `code` (nobody can review their own pull request). Narrow this when there is
  a second maintainer.
- The repository must be **public**: on a private Free-plan repository GitHub
  disables rulesets, branch protection, and auto-merge, and the whole gate
  silently degrades to "nothing is enforced".
- Actions settings: workflows need `contents: write`, `statuses: write`,
  `pull-requests: write`, `issues: write` (each file declares the minimum it
  uses); "Allow GitHub Actions to create and approve pull requests" is **off**
  (the bot never opens or approves one). Fork pull-request approval is set to
  the least restrictive option GitHub offers, "first-time contributors who are
  new to GitHub": a brand-new account's first pull request waits for a
  maintainer to click *Approve and run*; everyone else runs immediately. The
  workflows treat the pull request as data only, so this is safe.

## Testing a change to these workflows

There is no local runner that reproduces `pull_request_target`. What works:

1. Parse every workflow with a YAML loader and `node --check` each inline
   script wrapped in an async function (the repository's verification does
   exactly this; `actionlint` when available adds expression checks).
2. Push the change to a scratch repository with the same two-branch layout,
   open a pull request from a **fork** account, and walk the path: report
   comment appears; an approving review from a fresh account is listed as too new;
   three eligible approvals go `pending — cooling off`; a push resets the tally
   and the clock; `/block` flips the status to failure; a merge fires only after
   the window.
3. When the validator changes, move the pinned ref in `story-validate.yml` on
   the story branch **after** this branch's change has landed, not before.
