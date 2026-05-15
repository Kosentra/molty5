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

    # 3. Dynamic Scaling Logic
    agent_configs = []
    
    # Kumpulkan semua index angka yang ditemukan di variabel mana pun
    indices = set()
    for k in all_keys:
        m = re.search(r"(\d+)$", k)
        if m:
            indices.add(m.group(1))
    
    # Pastikan Agent 1 selalu ada
    agent_configs.append({
        "key": os.getenv("API_KEY", ""),
        "name": os.getenv("AGENT_NAME", "Agent-1"),
        "id": "agent-1"
    })

    # Tambahkan agent lain berdasarkan index yang ditemukan
    for idx in sorted(list(indices)):
        if idx == "1": continue
        
        # Cari kombinasi apa pun: API_KEY_2, API_KEY2, AGENT_2_KEY, dll
        key_val = (os.getenv(f"API_KEY_{idx}") or 
                   os.getenv(f"API_KEY{idx}") or 
                   os.getenv(f"AGENT_{idx}_API_KEY") or
                   os.getenv(f"AGENT{idx}_API_KEY"))
                   
        name_val = (os.getenv(f"AGENT_NAME_{idx}") or 
                    os.getenv(f"AGENT_NAME{idx}") or 
                    os.getenv(f"AGENT_{idx}_NAME") or
                    os.getenv(f"AGENT{idx}_NAME"))

        if key_val or name_val:
            log.info("➕ Detected Agent Index [%s]: Name=%s", idx, name_val or "Auto")
            agent_configs.append({
                "key": key_val or "",
                "name": name_val or f"Agent-{idx}",
                "id": f"agent-{idx}"
            })

    log.info("🚀 Final Scaling: Running %d independent agents.", len(agent_configs))
    dashboard_state.bots_running = len(agent_configs)

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
