"""The Open Slop projector. See ../README on the code branch for the picture.

Wiring, in dependency order:

  story branch (git) ──▶ StorySource ──▶ Screening (the queue's only writer)
              │ snapshots the film into a reel, then enqueues one scene at a
              │ time as the model's bounded queue has room — at its seed and
              │ length, chained where continue is true, tagged in metadata
              ▼
        ReactorLink ◀──▶ fast-h3 (clip queue; autoplay off until the curtain)
              │ 24 fps video + 48 kHz mono audio
              ▼
            Pacer ──▶ LiveKitPublisher ──▶ the show's room (viewers)
                              ▲
        Broadcast ────────────┘  show.state cursor at 1 Hz + room-metadata rundown

Everything is one asyncio process. The pacer and the publisher are created
after the first `state_update` (that is where the deployment's canvas size
comes from) and then live until shutdown, across any number of Reactor
reconnects — the room-side broadcast never restarts, it shows downtime while
the model is away and the screening that was on air restarts from the top.
The film itself, read from the story branch, keeps the projector fed: the
branch is snapshotted once per screening, a fixed pre-roll before it airs.
Every fresh session opens behind a curtain: nothing plays until about
`CURTAIN_SECONDS` of the opening is built, and the broadcast reports the
buffer filling as `loading` so the viewer can draw a pre-show instead of the
first clip stuttering out ahead of the builds.

Usage:
    cp .env.example .env      # keys, room, and the story repo
    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import warnings

from broadcast import Broadcast
from config import Config
from pacer import Pacer
from publisher import AudioFormat, LiveKitPublisher, VideoFormat
from reactor_link import MODEL_FPS, MODEL_SAMPLE_RATE, ReactorLink
from screening import Screening
from story import StorySource

logger = logging.getLogger("projector")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # WebRTC internals are chatty at INFO and alarming at their defaults.
    logging.getLogger("aiortc.codecs.vpx").setLevel(logging.ERROR)
    logging.getLogger("aiortc.codecs.h264").setLevel(logging.ERROR)
    logging.getLogger("aioice.ice").setLevel(logging.WARNING)
    warnings.filterwarnings("ignore", category=DeprecationWarning)


async def main() -> None:
    setup_logging()
    config = Config.load()

    link = ReactorLink(config)
    publisher = LiveKitPublisher(
        room_name=config.livekit_room,
        livekit_url=config.livekit_url,
        api_key=config.livekit_api_key,
        api_secret=config.livekit_api_secret,
    )
    story = StorySource(
        repo=config.story_repo,
        branch=config.story_branch,
        mirror_dir=config.story_mirror_dir,
        html_url=config.story_html_url,
    )
    broadcast = Broadcast(publisher)
    screening = Screening(link, story, broadcast)

    tasks = [
        asyncio.create_task(link.run(), name="reactor-link"),
        asyncio.create_task(screening.run(), name="screening"),
    ]

    try:
        # The room's video geometry comes from the deployment (state_update),
        # so the pacer starts only once the first session is up. From then on
        # it, the publisher, and the broadcaster survive every reconnect.
        await link.wait_first_state()
        width, height = link.canvas
        pacer = Pacer(
            publisher,
            VideoFormat(width=width, height=height, fps=MODEL_FPS),
            AudioFormat(sample_rate=MODEL_SAMPLE_RATE, channels=1),
        )
        link.attach_pacer(pacer)
        tasks.append(asyncio.create_task(pacer.run(), name="pacer"))
        tasks.append(asyncio.create_task(broadcast.run(), name="broadcast"))
        logger.info(
            "projecting %dx%d@%dfps into room %r from %s (%s)",
            width,
            height,
            MODEL_FPS,
            config.livekit_room,
            config.story_repo,
            config.story_branch,
        )

        # Run until a task dies (none should) or the process is interrupted.
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception() is not None:
                logger.error("task %s died: %s", task.get_name(), task.exception())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await publisher.stop()
        logger.info("shut down cleanly")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
