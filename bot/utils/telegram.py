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
        self._polling_task = None

    def start_all(self):
        """Start both log forwarding and command polling."""
        self.start_log_forwarder()
        self.start_polling()

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

    def start_polling(self):
        """Start background task to listen for commands."""
        if self.enabled and self._polling_task is None:
            self._polling_task = asyncio.create_task(self._poll_loop())
            log.info("Telegram command listener started.")

    async def _poll_loop(self):
        """Long poll for incoming messages from Telegram."""
        offset = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                try:
                    url = f"{self.base_url}/getUpdates"
                    params = {"offset": offset, "timeout": 20}
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        updates = resp.json().get("result", [])
                        for update in updates:
                            offset = update["update_id"] + 1
                            if "message" in update:
                                await self._handle_command(update["message"])
                    elif resp.status_code == 401:
                        log.error("Telegram Token invalid! Stopping listener.")
                        break
                    await asyncio.sleep(1) # Grace period
                except Exception as e:
                    log.debug("Telegram polling retry: %s", e)
                    await asyncio.sleep(5)

    async def _handle_command(self, msg: dict):
        """Parse and respond to user commands."""
        raw_text = msg.get("text", "")
        if not raw_text.startswith("/"):
            return
            
        text = raw_text.lower().split("@")[0] # Remove bot handle if present
        chat_id = msg.get("chat", {}).get("id")
        
        # Security: Only respond to the authorized chat ID
        if str(chat_id) != str(self.chat_id):
            log.warning("Unauthorized command from chat_id %s", chat_id)
            return

        from bot.dashboard.state import dashboard_state
        
        if text.startswith("/start"):
            welcome = (
                "👋 <b>Halo Komandan!</b>\n"
                "Saya adalah Molty Predator Bot. Gunakan perintah berikut:\n\n"
                "/status - Cek kondisi HP, EP, dan Kills\n"
                "/logs - Lihat 10 log aktivitas terakhir\n"
                "/dashboard - Link akses dashboard web\n"
                "/ping - Cek apakah bot merespon"
            )
            await self.send_message(welcome)
            
        elif text.startswith("/status"):
            snap = dashboard_state.get_snapshot()
            agents = snap.get("agents", {})
            if not agents:
                await self.send_message("❌ Belum ada agent yang terdeteksi aktif.")
                return
            
            summary = "<b>📊 Status Operasional:</b>\n\n"
            for aid, data in agents.items():
                status_emoji = "🎮" if data.get("status") == "playing" else "💤"
                summary += (f"{status_emoji} <b>{data.get('name')}</b>\n"
                            f"  ❤️ HP: {data.get('hp')}/{data.get('maxHp')}\n"
                            f"  ⚡ EP: {data.get('ep')}/{data.get('maxEp')}\n"
                            f"  🎯 Kills: {data.get('kills')}\n"
                            f"  📍 Region: {data.get('region')}\n"
                            f"  🕒 Bal: {data.get('smoltz', 0)} sMoltz\n"
                            f"  📝 Last: <i>{data.get('last_action')}</i>\n\n")
            await self.send_message(summary)

        elif text.startswith("/logs"):
            logs = list(dashboard_state.global_logs)[-10:]
            if not logs:
                await self.send_message("📭 Belum ada log aktivitas.")
                return
            
            text = "<b>📜 Log Aktivitas Terakhir:</b>\n<pre>"
            for l in logs:
                text += f"• {l['msg']}\n"
            text += "</pre>"
            await self.send_message(text)
            
        elif text.startswith("/dashboard"):
            await self.send_message("🌐 <b>Dashboard Web:</b>\nhttps://molty5-production-8e42.up.railway.app/")
            
        elif text.startswith("/ping"):
            await self.send_message("🏓 <b>Pong!</b> Bot aktif dan mendengarkan.")

# Singleton instance
tg_notifier = TelegramNotifier()
