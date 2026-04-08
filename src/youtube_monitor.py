import asyncio
import logging
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CHANNEL_HANDLE = "@airevolutionx"
CHANNEL_URL = "https://www.youtube.com/@airevolutionx"
STATE_FILE = Path("youtube_state.json")
RSS_NS = "http://www.w3.org/2005/Atom"


async def _resolve_channel_id() -> str | None:
    """Fetch channel page and extract channel ID from HTML."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0)"
        }) as client:
            resp = await client.get(CHANNEL_URL, follow_redirects=True)
            match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
            if match:
                return match.group(1)
            # Fallback: externalId
            match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        logger.error(f"Failed to resolve channel ID: {e}")
    return None


async def fetch_latest_video(channel_id: str) -> dict | None:
    """Fetch latest video from YouTube RSS feed."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

        root = ET.fromstring(resp.text)
        ns = {"atom": RSS_NS, "yt": "http://www.youtube.com/xml/schemas/2015"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        video_id = entry.findtext("yt:videoId", namespaces=ns)
        title = entry.findtext("atom:title", namespaces=ns)
        link_el = entry.find("atom:link", ns)
        link = link_el.attrib.get("href") if link_el is not None else f"https://youtu.be/{video_id}"
        published = entry.findtext("atom:published", namespaces=ns, default="")

        return {
            "video_id": video_id,
            "title": title,
            "url": link,
            "published": published[:10] if published else ""
        }
    except Exception as e:
        logger.error(f"Failed to fetch YouTube RSS: {e}")
        return None


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


class YouTubeMonitor:
    """Monitors YouTube channels for new videos and sends Telegram notifications."""

    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self._task: asyncio.Task | None = None
        self._channel_id: str | None = None
        self._check_interval = 3600  # 1 Stunde
        self._state = _load_state()

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("YouTube monitor started")

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _monitor_loop(self):
        # Resolve channel ID once on startup
        await asyncio.sleep(15)
        self._channel_id = await _resolve_channel_id()
        if self._channel_id:
            logger.info(f"YouTube: resolved {CHANNEL_HANDLE} → {self._channel_id}")
        else:
            logger.warning(f"YouTube: could not resolve channel ID for {CHANNEL_HANDLE}")

        while True:
            try:
                await self._check_and_notify()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"YouTube monitor error: {e}")
            await asyncio.sleep(self._check_interval)

    async def _check_and_notify(self):
        if not self._channel_id:
            self._channel_id = await _resolve_channel_id()
            if not self._channel_id:
                return

        video = await fetch_latest_video(self._channel_id)
        if not video:
            return

        last_seen = self._state.get(CHANNEL_HANDLE)

        if last_seen != video["video_id"]:
            self._state[CHANNEL_HANDLE] = video["video_id"]
            _save_state(self._state)

            # Don't notify on very first check (initialization)
            if last_seen is not None:
                msg = (
                    f"🎥 *Neues Video auf {CHANNEL_HANDLE}!*\n\n"
                    f"📺 *{video['title']}*\n"
                    f"📅 {video['published']}\n\n"
                    f"🔗 {video['url']}"
                )
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=msg,
                    parse_mode="Markdown"
                )
                logger.info(f"New video notified: {video['title']}")
            else:
                logger.info(f"YouTube init: latest video = {video['title']}")

    async def get_status(self) -> dict:
        """Get current status for heartbeat."""
        if not self._channel_id:
            return {"channel": CHANNEL_HANDLE, "status": "Channel ID nicht aufgelöst", "latest": None}

        video = await fetch_latest_video(self._channel_id)
        return {
            "channel": CHANNEL_HANDLE,
            "channel_id": self._channel_id,
            "status": "aktiv",
            "latest": video
        }
