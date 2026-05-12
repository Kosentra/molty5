"""
Telegram notifier utility for Molty Royale AI Agent.
Sends asynchronous messages to the configured bot/chat.
"""
import httpx
from bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, AGENT_NAME
from bot.utils.logger import get_logger

log = get_logger(__name__)

class TelegramNotifier:
    """Simple async Telegram bot client."""

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"

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
                if resp.status_code != 200:
                    log.warning("Telegram send failed: %s", resp.text)
        except Exception as e:
            log.error("Telegram error: %s", e)

# Singleton instance
tg_notifier = TelegramNotifier()
