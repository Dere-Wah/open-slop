---
name: viewer-design
description: How the OpenSlop viewer is built and styled — a Next.js page laid out as a GitHub repository, its design tokens, its component map, the one grid that serves desktop and phone, the curtain's container queries, and how the rundown scales to hundreds of episodes. Read before changing anything under viewer/.
---

# The viewer

`viewer/` is the page at openslop.live: it joins the LiveKit room, plays the
broadcast, and shows what is on air. It calls nothing but its own
`/api/livekit/token` route. GitHub is linked to, never fetched from; the only
GitHub bytes the page loads are avatar images, which come off a CDN.

## The look is a GitHub repository page

OpenSlop is a film that lives on a branch, and the page says so by looking
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

Every `<a>` keeps the colour of the text around it and underlines on hover,
as on GitHub; the rule lives in `@layer base` in `globals.css`, so it applies
without a class. No link turns blue, at rest or on hover: `.gh-link` sets no
colour, and no anchor carries `hover:text-accent`. A link that looks
like a button, tab, or chip opts out: `.gh-btn`, `.gh-topic`, and the
underline nav do so in `@layer components`, and a one-off chip (the
overlay badges, the PR chip in chat, avatar links) adds
`hover:no-underline`. Do not put element rules such as `a { … }` outside
a layer: an unlayered rule beats every layer, and both the components and
the utilities stop being able to override it.

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
| `app/ShowPage.tsx` | The whole page from props. The grid, the mobile panel switch, the footer. From `lg` the right column is one `side` area holding an `<aside>` with chat above About; under `lg` the aside is `display: contents` so both take the single `panel` slot one at a time. |
| `components/RepoHeader.tsx` | Owner / repo, `Public`, branch @ sha, the buttons (an icon-only link to the launch post on X from `SITE.announcement`, the screenplay, the call to action, Star, the agent button), the underline nav. "Write the next scene" is the page's one call to action, the only primary button, and it opens the story branch's `CONTRIBUTING.md` (`contributingUrl`), the three-step guide — never the README. A connection pill sits at the nav's right end only while the page is not connected; there is no global bar above it. |
| `components/Player.tsx` | Video and audio elements, the progress line, mute and fullscreen, and the overlay slot. |
| `components/Overlay.tsx` | The "On air" chip (a red dot and the two words), a viewer count beside it (an eye and a number, `1.3k` past a thousand), the "Running on Reactor" chip top-right, and the stall ribbon, drawn over the picture while live. |
| `components/Curtain.tsx` | The pre-show that covers the player whenever nothing is on air: while `loading` its ring fills with the buffer and counts the seconds still to build; while `intermission` it fills with the pause and counts down to the next screening. |
| `components/NowPlaying.tsx` | The bar under the player, shaped like GitHub's latest-commit row: author, episode and scene, commit, and at the right end a green **Edit scene** button (`EditButton`, primary) that opens GitHub's editor on the lines on air (`editUrl` with the cursor's `line_start`/`line_end`, falling back to the rundown scene's `lines`). Carries the loading, downtime, warming, and off-air lines too. No countdown — a ticking clock read as a deadline. |
| `components/Rundown.tsx` | The episode table with its scenes, filter, paging, and jump-to-now-playing. Every episode row has a grey **Edit** (the whole file) and every scene row one beside the author's name that lands on the scene's prose lines; the scene on air gets the green one. Exports `EditButton`. Its last line is when the next screening starts, as a wall-clock time ("at about 19:24"; "no earlier than" while a scene holds). |
| `opengraph-image.tsx`, `twitter-image.tsx` | The social card, built once with `next/og`: owner and repo top left, the title, the description, and a row of facts, in Inter fetched from Google Fonts at build (falls back to the renderer's sans). No avatar. `lib/site.ts` holds the URL, repo, title, and description the card and the `<head>` metadata share. |
| `components/AgentButton.tsx` | The split button at the end of the header row, hidden under `md`: the left half opens the remembered agent with the contribution prompt pre-filled, the right half opens a custom menu (`.gh-menu`) of the others. Picking one runs it and stores it in `localStorage` under `openslop.agent`. The agents, their documented deep-link schemes, and the prompt live in `lib/agents.ts`; a new agent is one entry there with a cited scheme. Brand marks are in `components/BrandIcons.tsx`. |
| `components/About.tsx` | The sidebar: a "Write the next scene" box first (the three steps in one line each, the agent hint, a button to `CONTRIBUTING.md`), then description, links, topics, licences, the screening, sponsors (Reactor, linking to reactor.inc), contributors. |
| `components/Chat.tsx` | The room chat, first in the sidebar. Fixed height from its `className`, scrolls inside, follows new messages only when the reader is at the bottom; a header toggle collapses it to one row (remembered in localStorage). No name field: the first send opens a small dialog asking for one, which then persists; "change" under the box reopens it. A link to one of this repository's pull requests renders as a chip (`#41` with the pull-request icon) through `pullRefOf`; every other URL stays plain text. |
| `components/Avatar.tsx` | A GitHub avatar for a `@login` (or a profile URL), a lettered disc for anyone else. |
| `lib/github.ts` | Everything derived from `story_url`: `owner/repo/branch`, every link out, avatar and profile URLs, and `pullRefOf`, which recognises a link to this repository's pull requests and nothing else. |
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
- Chat never linkifies. The one exception is a pull request on this
  repository, rebuilt from the parsed number as a canonical URL; a link to
  any other host or repository is left as text, so the room cannot become a
  link board.
- The viewer count is the room's own participant list minus the `streamer`,
  counted on join and on every join or leave event; nothing is polled.

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
