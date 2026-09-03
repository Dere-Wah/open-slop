---
name: viewer-design
description: How the Open Slop viewer is built and styled — a Next.js page laid out as a GitHub repository, its design tokens, its component map, the one grid that serves desktop and phone, the curtain's container queries, and how the rundown scales to hundreds of episodes. Read before changing anything under viewer/.
---

# The viewer

`viewer/` is the page at openslop.live: it joins the LiveKit room, plays the
broadcast, and shows what is on air. It calls nothing but its own
`/api/livekit/token` route. GitHub is linked to, never fetched from; the only
GitHub bytes the page loads are avatar images, which come off a CDN.

## The look is a GitHub repository page

Open Slop is a film that lives on a branch, and the page says so by looking
like the branch's home: the `owner / repo` title with its `Public` label and
action buttons, an underline nav, then a two-column body
with the content on the left and an About panel on the right. A visitor
arriving from github.com should feel they never left.

That is a look, not a dependency. There is no component library; the palette,
type stack, and radii are plain CSS variables in `app/globals.css`, exposed
to Tailwind through `@theme`, and the recurring pieces (`.gh-btn`,
`.gh-box`, `.gh-label`, `.gh-counter`, `.gh-input`, `.gh-topic`,
`.gh-underline-nav`, `.gh-avatar`, `.gh-progress`) are one class each in
`@layer components`, so a utility on the same element still wins.

| Token group | Classes | Use |
| --- | --- | --- |
| Canvas | `bg-canvas`, `bg-canvas-inset`, `bg-canvas-subtle`, `bg-canvas-overlay` | page, box headers, code chips |
| Foreground | `text-fg`, `text-fg-muted`, `text-fg-subtle`, `text-fg-on-emphasis` | body, secondary, tertiary, on a filled button |
| Lines | `border-line`, `border-line-muted` | box borders, row separators |
| Signals | `accent` (blue), `success` (green), `attention` (amber), `danger` (red), `done` (purple) | links and the buffer; on air; reconnecting; the live dot; unused so far |
| Type | `font-sans`, `font-mono` | the system stacks GitHub uses; mono for shas, files, durations |

Do not add a colour that is not a token. Do not reach for a UI package; the
page needs a dozen glyphs and they are inline in `components/Icons.tsx`, drawn
on the Octicons grid.

## Component map

| File | Owns |
| --- | --- |
| `app/ShowApp.tsx` | The room: token fetch, join and rejoin, media tracks, `show.state` and `show.chat` packets, room metadata, clock-skew correction, the stale-cursor rule. No markup beyond `<ShowPage>`. |
| `app/ShowPage.tsx` | The whole page from props. The grid, the mobile panel switch, the footer. |
| `components/RepoHeader.tsx` | Owner / repo, `Public`, branch @ sha, the three buttons, the underline nav. A connection pill sits at the nav's right end only while the page is not connected; there is no global bar above it. |
| `components/Player.tsx` | Video and audio elements, the progress line, mute and fullscreen, and the overlay slot. |
| `components/Overlay.tsx` | The "On air" chip (a red dot and the two words, nothing else) and the intermission ribbon, drawn over the picture while live. |
| `components/Curtain.tsx` | The pre-show that covers the player whenever nothing is on air. |
| `components/NowPlaying.tsx` | The bar under the player, shaped like GitHub's latest-commit row: author, episode and scene, commit. Carries the loading, downtime, warming, and off-air lines too. No countdown — a ticking clock read as a deadline. |
| `components/Rundown.tsx` | The episode table with its scenes, filter, paging, and jump-to-now-playing. Its last line is when the next screening starts, as a wall-clock time ("at about 19:24"; "no earlier than" while a scene holds). |
| `components/About.tsx` | The sidebar: description, links, topics, licences, the screening, sponsors (Reactor, linking to reactor.inc), contributors. |
| `components/Chat.tsx` | The room chat. |
| `components/Avatar.tsx` | A GitHub avatar for a `@login` (or a profile URL), a lettered disc for anyone else. |
| `lib/github.ts` | Everything derived from `story_url`: `owner/repo/branch`, every link out, avatar and profile URLs. |
| `lib/safeUrl.ts` | The only way an `href` is rendered from wire data. |
| `app/preview/` | A fixture-driven copy of the page for design work; development only. |

## One grid, two layouts

`ShowPage` renders every panel exactly once inside a single grid with named
areas. Under `lg` the areas stack in one column (`player`, `bar`, `tabs`,
`rundown`, `chat`, `about`) and a segmented control in the `tabs` area picks
which of the last three is shown; the other two get `hidden lg:block`. At `lg`
and up the areas become

```
player   about
bar      about
rundown  chat
```

with the chat sticky in its cell. Because the panels are never unmounted or
duplicated, chat drafts, the rundown's filter, and the video element survive
a resize and a rotation. Keep it that way: do not render a panel twice for
two breakpoints.

## The curtain must fit any player

The player is 16:9 and full width, so on a 320px phone the curtain has 180px
of height; on a wall it has 700. `.curtain` sets `container-type: size` and
the `.curtain-*` rules in `globals.css` size the title, ring, and padding off
the box height (`cqh`) and drop sections from the bottom up as the box gets
shorter — programme, then buffer readout, then tagline, then kicker. Nothing
inside the curtain may use a viewport unit or a fixed pixel height. When you
add something to it, give it a `.curtain-*` class and a `@container`
threshold below which it disappears, and check `/preview?state=loading` at
390px wide.

## The rundown must hold a long film

Room metadata carries the whole screening, and a film can grow to hundreds of
episodes. `Rundown.tsx` renders `PAGE` (25) rows and a "show more" footer; the
filter narrows by title, file, or author; the episode on air is always inside
the rendered slice and a "Now playing" button scrolls to it. Scenes render
only for expanded episodes, and only the episode on air starts expanded. When
the projector says `truncated`, the footer says so and links to the branch.
Check `/preview?state=live&episodes=120` after any change here.

## Trust rules the markup must keep

- A `show.state` packet counts only from the `streamer` participant; a chat
  message may sign as the show only from it. Both checks live in `ShowApp`.
- Every `href` built from wire data goes through `safeHttpUrl` or a
  `lib/github.ts` builder over a parsed `RepoRef`. Never interpolate a wire
  string into a URL.
- Avatars are loaded only for logins that match GitHub's login grammar,
  with `referrerPolicy="no-referrer"`.

## Working on it

```sh
cd viewer && pnpm install
pnpm dev                                   # http://localhost:3000
open http://localhost:3000/preview?state=loading&episodes=120
pnpm build                                 # what CI and Vercel run
```

`/preview` takes `state=live|loading|downtime|warming|offair` and
`episodes=<n>`; it is `notFound()` in a production build. Look at 390px and
1440px wide before calling a change done.
