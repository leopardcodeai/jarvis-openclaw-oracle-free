import asyncio
import logging
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from .config import settings

logger = logging.getLogger(__name__)

CHANNEL_HANDLE = "@airevolutionx"
CHANNEL_URL = "https://www.youtube.com/@airevolutionx"
STATE_FILE = Path("youtube_state.json")
RSS_NS = "http://www.w3.org/2005/Atom"


async def resolve_channel_id(handle_or_url: str) -> str | None:
    """Resolve a YouTube channel handle or URL to a channel ID.
    Tries multiple methods in order:
    1. Free Piped API (no key required)
    2. yt.lemnoslife.com noKey API
    3. Direct YouTube page scrape with browser headers
    """
    # Normalise: extract handle from URL if needed
    handle = handle_or_url.strip()
    for prefix in ["https://www.youtube.com/", "https://youtube.com/", "http://"]:
        handle = handle.replace(prefix, "")
    handle = handle.split("?")[0].rstrip("/")
    if not handle.startswith("@"):
        # Already a channel ID?
        if re.match(r'^UC[a-zA-Z0-9_-]{22}$', handle):
            return handle
        handle = "@" + handle

    channel_url = f"https://www.youtube.com/{handle}"

    headers_browser = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        # Method 1: Piped API (open-source YouTube frontend)
        try:
            piped = await client.get(
                f"https://pipedapi.kavin.rocks/channel/{handle.lstrip('@')}"
            )
            if piped.status_code == 200:
                data = piped.json()
                cid = data.get("id", "")
                if re.match(r'^UC[a-zA-Z0-9_-]{22}$', cid):
                    logger.info(f"Resolved via Piped: {handle} → {cid}")
                    return cid
        except Exception:
            pass

        # Method 2: yt.lemnoslife.com noKey API
        try:
            lemon = await client.get(
                "https://yt.lemnoslife.com/noKey/channels",
                params={"handle": handle}
            )
            if lemon.status_code == 200:
                items = lemon.json().get("items", [])
                if items:
                    cid = items[0].get("id", "")
                    if re.match(r'^UC[a-zA-Z0-9_-]{22}$', cid):
                        logger.info(f"Resolved via lemnoslife: {handle} → {cid}")
                        return cid
        except Exception:
            pass

        # Method 3: YouTube page scrape with browser headers
        try:
            resp = await client.get(channel_url, headers=headers_browser)
            for pattern in [
                r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
                r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
                r'channel/(UC[a-zA-Z0-9_-]{22})',
                r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
            ]:
                m = re.search(pattern, resp.text)
                if m:
                    logger.info(f"Resolved via scrape: {handle} → {m.group(1)}")
                    return m.group(1)
        except Exception as e:
            logger.error(f"Scrape failed for {handle}: {e}")

    logger.warning(f"Could not resolve channel ID for {handle}")
    return None


async def _resolve_channel_id() -> str | None:
    """Resolve the default monitored channel."""
    return await resolve_channel_id(CHANNEL_URL)


async def fetch_recent_videos(channel_id: str, max_results: int = 15) -> list[dict]:
    """Fetch recent videos from YouTube RSS feed (up to max_results)."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

        root = ET.fromstring(resp.text)
        ns = {"atom": RSS_NS, "yt": "http://www.youtube.com/xml/schemas/2015"}
        videos = []
        for entry in root.findall("atom:entry", ns)[:max_results]:
            video_id = entry.findtext("yt:videoId", namespaces=ns)
            title = entry.findtext("atom:title", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.attrib.get("href") if link_el is not None else f"https://youtu.be/{video_id}"
            published = entry.findtext("atom:published", namespaces=ns, default="")
            videos.append({
                "video_id": video_id,
                "title": title,
                "url": link,
                "published": published[:10] if published else ""
            })
        return videos
    except Exception as e:
        logger.error(f"Failed to fetch YouTube RSS: {e}")
        return []


async def fetch_latest_video(channel_id: str) -> dict | None:
    """Fetch latest video (convenience wrapper)."""
    videos = await fetch_recent_videos(channel_id, max_results=1)
    return videos[0] if videos else None


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
        self._heartbeat_seen_ids: set[str] = set()  # video_ids already shown in heartbeat

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("YouTube monitor started")

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _monitor_loop(self):
        # Use hardcoded channel ID from config if available, otherwise scrape
        await asyncio.sleep(15)
        if settings.youtube_channel_id:
            self._channel_id = settings.youtube_channel_id
            logger.info(f"YouTube: using configured channel ID {self._channel_id}")
        else:
            self._channel_id = await _resolve_channel_id()
            if self._channel_id:
                logger.info(f"YouTube: resolved {CHANNEL_HANDLE} → {self._channel_id}")
            else:
                logger.warning(f"YouTube: could not resolve channel ID for {CHANNEL_HANDLE} – set YOUTUBE_CHANNEL_ID in .env")

        # Pre-seed heartbeat seen IDs with current videos so first /heartbeat
        # doesn't flood with all 15 RSS entries
        if self._channel_id:
            videos = await fetch_recent_videos(self._channel_id)
            for v in videos:
                self._heartbeat_seen_ids.add(v["video_id"])
            logger.info(f"YouTube: pre-seeded {len(self._heartbeat_seen_ids)} video IDs for heartbeat")

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

        videos = await fetch_recent_videos(self._channel_id)
        if not videos:
            return

        # State stores a set of known video IDs
        known = self._state.get(CHANNEL_HANDLE + "_known", [])
        known_set = set(known)
        is_init = not known_set

        new_videos = [v for v in videos if v["video_id"] not in known_set]

        if new_videos:
            # Update known set with all current video IDs
            all_ids = [v["video_id"] for v in videos]
            self._state[CHANNEL_HANDLE + "_known"] = all_ids
            # Keep legacy key for compatibility
            self._state[CHANNEL_HANDLE] = videos[0]["video_id"]
            _save_state(self._state)

            if not is_init:
                for video in reversed(new_videos):  # oldest first
                    msg = (
                        f"🎥 *Neues Video auf {CHANNEL_HANDLE}!*\n\n"
                        f"📺 *{video['title']}*\n"
                        f"📅 {video['published']}\n\n"
                        f"🔗 {video['url']}"
                    )
                    await self.bot.send_message(
                        chat_id=self.chat_id, text=msg, parse_mode="Markdown"
                    )
                    logger.info(f"New video notified: {video['title']}")
            else:
                logger.info(f"YouTube init: {len(videos)} videos known, latest = {videos[0]['title']}")

    async def get_status(self) -> dict:
        """Get current status for heartbeat.
        Returns all videos not yet shown in a heartbeat. Marks them as shown.
        """
        if not self._channel_id:
            return {"channel": CHANNEL_HANDLE, "status": "Channel ID nicht aufgelöst", "new_videos": []}

        videos = await fetch_recent_videos(self._channel_id)
        if not videos:
            return {"channel": CHANNEL_HANDLE, "channel_id": self._channel_id,
                    "status": "aktiv", "new_videos": [], "already_seen": True}

        new_videos = [v for v in videos if v["video_id"] not in self._heartbeat_seen_ids]

        # Mark all current videos as seen for future heartbeats
        for v in videos:
            self._heartbeat_seen_ids.add(v["video_id"])

        return {
            "channel": CHANNEL_HANDLE,
            "channel_id": self._channel_id,
            "status": "aktiv",
            "new_videos": new_videos,
            "already_seen": len(new_videos) == 0,
        }
