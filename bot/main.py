"""
Molty Royale AI Agent — Ultra-Flexible Entry Point v2.2.
Debugs and scales all agents found in environment variables.
"""
import asyncio
import os
import sys
import re
from bot.heartbeat import Heartbeat
from bot.dashboard.server import start_dashboard
from bot.dashboard.state import dashboard_state
from bot.utils.telegram import tg_notifier
from bot.utils.logger import get_logger

log = get_logger(__name__)

DASHBOARD_PORT = int(os.getenv("PORT", os.getenv("DASHBOARD_PORT", "8080")))

async def run_all():
    """Main runner with absolute variable transparency."""
    # 1. Audit relevant environment variables
    all_keys = sorted(os.environ.keys())
    api_related = [k for k in all_keys if "API" in k or "AGENT" in k or "KEY" in k]
    log.info("🔍 ENVIRONMENT AUDIT: Found %d relevant keys (%s)", len(api_related), ", ".join(api_related[:10]) + ("..." if len(api_related) > 10 else ""))

    # 2. Start Services
    log.info("Starting web dashboard on port %d...", DASHBOARD_PORT)
    await start_dashboard(port=DASHBOARD_PORT)
    tg_notifier.start_all()
    await tg_notifier.send_message("🚀 <b>Multi-Agent System Booting...</b>")

    # 3. Single Agent Mode (Simplified)
    agent_configs = [{
        "key": os.getenv("API_KEY", ""),
        "name": os.getenv("AGENT_NAME", "Agent-1"),
        "id": "agent-1"
    }]
    log.info("🚀 Running in Single-Agent mode.")
    dashboard_state.bots_running = 1

    # 4. Start Heartbeats
    tasks = []
    for config in agent_configs:
        hb = Heartbeat(
            api_key=config["key"],
            agent_name=config["name"],
            dashboard_key=config["id"]
        )
        tasks.append(hb.run())

    if tasks:
        await asyncio.gather(*tasks)
    else:
        log.error("No agents found! Sleeping...")
        while True: await asyncio.sleep(3600)

def main():
    log.info("Molty Royale Command Center v2.2.0")
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_all())
    except Exception as e:
        log.error("FATAL: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
