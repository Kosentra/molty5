"""
Telegram notifier utility for Molty Royale AI Agent.
Sends asynchronous messages to the configured bot/chat.
"""
import httpx
from bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, AGENT_NAME
from bot.utils.logger import get_logger

log = get_logger(__name__)

import asyncio
from typing import List

class TelegramNotifier:
    """Simple async Telegram bot client with background log forwarding."""

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._log_queue = asyncio.Queue()
        self._forwarder_task = None

    def start_log_forwarder(self):
        """Start background task to forward logs from queue."""
        if self.enabled and self._forwarder_task is None:
            self._forwarder_task = asyncio.create_task(self._log_loop())
            log.info("Telegram log forwarder started.")

    async def _log_loop(self):
        """Batch and send logs to Telegram to avoid rate limits."""
        batch: List[str] = []
        last_send = asyncio.get_event_loop().time()
        
        while True:
            try:
                # Wait for log with timeout to allow batching
                try:
                    msg = await asyncio.wait_for(self._log_queue.get(), timeout=2.0)
                    batch.append(msg)
                except asyncio.TimeoutError:
                    pass

                now = asyncio.get_event_loop().time()
                # Send batch if it's large enough or enough time has passed
                if batch and (len(batch) >= 5 or now - last_send >= 5.0):
                    text = "\n".join(batch)
                    await self.send_message(text)
                    batch = []
                    last_send = now
                    # Small delay to prevent hitting TG burst limits
                    await asyncio.sleep(1.0)

            except Exception as e:
                log.error("Telegram forwarder error: %s", e)
                await asyncio.sleep(5.0)

    def enqueue_log(self, message: str):
        """Thread-safe way to add logs to the queue (for logging handler)."""
        if not self.enabled:
            return
        try:
            # Check if loop is running
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._log_queue.put_nowait, message)
        except RuntimeError:
            pass # No loop running

    async def send_message(self, text: str, parse_mode: str = "HTML"):
        """Send an async message to the configured chat."""
        if not self.enabled:
            return

        payload = {
            "chat_id": self.chat_id,
            "text": f"<b>[{AGENT_NAME or 'MoltyAgent'}]</b>\n{text}",
            "parse_mode": parse_mode
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
                if resp.status_code == 429: # Rate limited
                    wait = resp.json().get("parameters", {}).get("retry_after", 30)
                    log.warning("Telegram rate limited. Waiting %ds", wait)
                    await asyncio.sleep(wait)
                elif resp.status_code != 200:
                    log.warning("Telegram send failed: %s", resp.text)
        except Exception as e:
            log.error("Telegram error: %s", e)

# Singleton instance
tg_notifier = TelegramNotifier()
