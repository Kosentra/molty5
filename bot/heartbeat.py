"""
Heartbeat service — orchestrates the agent's lifecycle.
"""
import asyncio
import os
import json
from datetime import datetime

from bot.utils.logger import get_logger
from bot.api_client import MoltyAPI
from bot.state_router import (
    determine_state, NO_ACCOUNT, NO_IDENTITY, IN_GAME, READY_PAID, READY_FREE, ERROR
)
from bot.game.room_selector import select_room
from bot.game.ws_join import JoinEngine
from bot.memory.agent_memory import AgentMemory
from bot.dashboard.state import dashboard_state
from bot.setup.identity import ensure_identity

from bot.config import (
    ADVANCED_MODE, ROOM_MODE, AUTO_WHITELIST,
    AUTO_SC_WALLET, ENABLE_MEMORY, AUTO_IDENTITY,
)

log = get_logger(__name__)

class Heartbeat:
    def __init__(self, api_key: str, agent_name: str = "agent-1", dashboard_key: str = None):
        self.api_key = api_key
        self.api = MoltyAPI(api_key)
        self.running = True
        self._agent_key = dashboard_key or agent_name  # Key for dashboard state
        self._agent_name = agent_name
        self.memory = AgentMemory(agent_name)
        self.retry_count = 0

    async def run(self):
        log.info("═══════════════════════════════════════════")
        log.info("[agent-1] Config (First-Run Intake):")
        log.info("[agent-1]   ADVANCED_MODE   = %s", ADVANCED_MODE)
        log.info("[agent-1]   AUTO_SC_WALLET  = %s", AUTO_SC_WALLET)
        log.info("[agent-1]   AUTO_WHITELIST  = %s", AUTO_WHITELIST)
        log.info("[agent-1]   ENABLE_MEMORY   = %s", ENABLE_MEMORY)
        log.info("[agent-1]   AUTO_IDENTITY   = %s", AUTO_IDENTITY)
        log.info("[agent-1]   ROOM_MODE       = %s", ROOM_MODE)
        log.info("═══════════════════════════════════════════")
        log.info("  MOLTY ROYALE AI AGENT — STARTING")
        log.info("═══════════════════════════════════════════")

        if ENABLE_MEMORY:
            await self.memory.load()

        while self.running:
            try:
                await self._heartbeat_cycle()
                self.retry_count = 0  # Reset on success
                await asyncio.sleep(15)  # Healthy interval
            except Exception as e:
                self.retry_count += 1
                wait_time = min(120, 10 * self.retry_count)
                log.error("Heartbeat error (#%d): %s. Retrying in %ds...", 
                          self.retry_count, str(e), wait_time)
                await asyncio.sleep(wait_time)

    async def _heartbeat_cycle(self):
        # 1. Get status
        me = await self.api.get_accounts_me()
        
        # Determine agent key for dashboard
        if not self._agent_key:
            readiness = me.get("readiness", {})
            self._agent_key = readiness.get("walletAddress") or me.get("id") or self._agent_name

        # 2. Determine state
        state, ctx = determine_state(me)
        log.info("[%s] State: %s", self._agent_key, state)

        # 3. Handle state
        if state == IN_GAME:
            await self._handle_in_game(ctx)
        elif state in (READY_FREE, READY_PAID):
            await self._handle_ready(me, state)
        elif state == NO_IDENTITY:
            await self._handle_no_identity()
        elif state == ERROR:
            log.error("[%s] API reported error state. Checking config...", self._agent_key)
            await asyncio.sleep(30)
        else:
            log.info("[%s] Waiting for account readiness (current=%s)...", self._agent_key, state)

    async def _handle_in_game(self, ctx: dict):
        log.info("[%s] 🎮 Rejoining active game: %s", self._agent_key, ctx["game_id"])
        # Same JoinEngine can rejoin
        engine = JoinEngine(entry_type=ctx["entry_type"], mode="offchain", api_key=self.api_key)
        engine.dashboard_key = self._agent_key
        engine.dashboard_name = self._agent_name
        await engine.run()

    async def _handle_ready(self, me_data: dict, state: str):
        # Decide room
        from bot.game.room_selector import select_room
        rooms = []
        try:
            rooms = await self.api.get_games_rooms()
        except:
            pass

        room_type = select_room(me_data, rooms)
        log.info("═══ JOINING GAME via /ws/join: type=%s ═══", room_type)

        # Feed dashboard
        dashboard_state.update_agent(self._agent_key, {
            "name": self._agent_name,
            "status": "joining",
            "room_name": f"{room_type} room",
        })

        # Set temp memory
        self.memory.set_temp_game("joining")
        await self.memory.save()

        # v1.6.1: Default to offchain for sMoltz usage (Path A)
        mode_to_use = "offchain" 
        log.info("Starting JoinEngine (entry=%s, mode=%s)...", room_type, mode_to_use)

        # Ensure Identity is registered BEFORE JoinEngine (v1.6.2 requirement)
        if not me_data.get("erc8004Id"):
            log.info("[%s] 🆔 Identity missing — attempting registration...", self._agent_key)
            # Use data dir for session
            d_dir = os.path.join(os.getcwd(), "session")
            await ensure_identity(self.api, d_dir)

        # Run unified join + gameplay engine
        engine = JoinEngine(entry_type=room_type, mode=mode_to_use, api_key=self.api_key)
        engine.dashboard_key = self._agent_key
        engine.dashboard_name = self._agent_name
        game_result = await engine.run()

        # Self-healing
        if engine.needs_identity_reset:
            log.info("[%s] 🛠️ Self-Healing: Resetting identity...", self._agent_key)
            d_dir = os.path.join(os.getcwd(), "session")
            await ensure_identity(self.api, d_dir)

    async def _handle_no_identity(self):
        log.info("[%s] 🆔 Missing ERC-8004 identity. Registering...", self._agent_key)
        d_dir = os.path.join(os.getcwd(), "session")
        await ensure_identity(self.api, d_dir)
