"""
Heartbeat loop — main orchestration per heartbeat.md.
State machine: setup → join → play → settle → repeat.
Respects First-Run Intake config flags for Railway/Docker deployment.
"""
import asyncio
import random
from bot.api_client import MoltyAPI, APIError
from bot.dashboard.state import dashboard_state
from bot.state_router import determine_state, NO_ACCOUNT, NO_IDENTITY, IN_GAME, READY_PAID, READY_FREE
from bot.setup.account_setup import ensure_account_ready
from bot.setup.wallet_setup import ensure_molty_wallet
from bot.setup.whitelist import ensure_whitelist
from bot.setup.identity import ensure_identity
from bot.game.room_selector import select_room
from bot.game.free_join import join_free_game
from bot.game.paid_join import join_paid_game
from bot.game.websocket_engine import WebSocketEngine
from bot.game.settlement import settle_game
from bot.memory.agent_memory import AgentMemory
from bot.credentials import load_credentials, get_api_key
from bot.config import (
    ADVANCED_MODE, ROOM_MODE, AUTO_WHITELIST,
    AUTO_SC_WALLET, ENABLE_MEMORY, AUTO_IDENTITY,
)
from bot.utils.logger import get_logger

log = get_logger(__name__)


class Heartbeat:
    """Main heartbeat loop — runs forever, manages the full agent lifecycle."""

    def __init__(self, api_key: str = None, agent_name: str = "Agent", dashboard_key: str = "agent-1"):
        self.api_key = api_key
        self.api: MoltyAPI | None = None
        self.memory = AgentMemory()
        self.running = True
        self._agent_key = dashboard_key
        self._agent_name = agent_name

    async def run(self):
        """Entry point — runs the heartbeat loop indefinitely."""
        # Stagger start to avoid rate limits (0-10s)
        delay = random.uniform(0, 10)
        log.info("[%s] Staggering start (delay=%.1fs)...", self._agent_key, delay)
        await asyncio.sleep(delay)

        log.info("═══════════════════════════════════════════")
        log.info("  MOLTY ROYALE AI AGENT — STARTING")
        log.info("═══════════════════════════════════════════")

        # Log active config (answers to setup.md First-Run Intake)
        log.info("[%s] Config (First-Run Intake):", self._agent_key)
        log.info("[%s]   ADVANCED_MODE   = %s", self._agent_key, ADVANCED_MODE)
        log.info("[%s]   AUTO_SC_WALLET  = %s", self._agent_key, AUTO_SC_WALLET)
        log.info("[%s]   AUTO_WHITELIST  = %s", self._agent_key, AUTO_WHITELIST)
        log.info("[%s]   ENABLE_MEMORY   = %s", self._agent_key, ENABLE_MEMORY)
        log.info("[%s]   AUTO_IDENTITY   = %s", self._agent_key, AUTO_IDENTITY)
        log.info("[%s]   ROOM_MODE       = %s", self._agent_key, ROOM_MODE)

        if not self.api_key:
            # Phase 0: First-run intake + account setup (retry until success)
            creds = None
            while self.running and not creds:
                try:
                    # data_dir mapping: "agent-1" -> "dev-agent", "agent-2" -> "dev-agent-2"
                    d_dir = self._agent_key.replace("agent", "dev-agent") if self._agent_key != "agent-1" else "dev-agent"
                    creds = await ensure_account_ready(data_dir=d_dir)
                    self.api_key = creds.get("api_key", "") or get_api_key(data_dir=d_dir)
                    if not self.api_key:
                        log.error("[%s] No API key available. Retrying in 60s...", self._agent_key)
                        await asyncio.sleep(60)
                except Exception as e:
                    log.error("[%s] Account setup error: %s. Retrying in 60s...", self._agent_key, e)
                    await asyncio.sleep(60)
        else:
            creds = {"api_key": self.api_key, "agent_name": self._agent_name}

        if not self.running:
            return

        self.api = MoltyAPI(self.api_key)

        # Feed dashboard
        dashboard_state.bots_running = 1
        dashboard_state.add_log("Bot started", "info")

        # Load memory (if enabled)
        if ENABLE_MEMORY:
            await self.memory.load()
            if creds.get("agent_name"):
                self.memory.set_agent_name(creds["agent_name"])
        else:
            log.info("Memory system disabled (ENABLE_MEMORY=false)")

        # Main loop — NEVER exits, NEVER crashes
        consecutive_errors = 0
        while self.running:
            try:
                await self._heartbeat_cycle()
                consecutive_errors = 0  # Reset on success
            except KeyboardInterrupt:
                log.info("Shutdown requested")
                self.running = False
            except Exception as e:
                consecutive_errors += 1
                # Escalating backoff: 10s → 30s → 60s → 120s
                wait = min(10 * (2 ** min(consecutive_errors - 1, 4)), 120)
                log.error("Heartbeat error (#%d): %s. Retrying in %ds...",
                          consecutive_errors, e, wait)
                await asyncio.sleep(wait)

        if self.api:
            await self.api.close()
        log.info("Agent stopped.")

    async def _heartbeat_cycle(self):
        """Single heartbeat cycle: check state → route → act."""
        # Step 1: GET /accounts/me
        try:
            me = await self.api.get_accounts_me()
        except APIError as e:
            if e.status == 401:
                log.error("Invalid API key. Re-run setup.")
                self.running = False
                return
            raise

        # Step 2: Determine state
        state, ctx = determine_state(me)
        log.info("[%s] State: %s", self._agent_key, state)

        # Feed dashboard with account info — use CONSISTENT key
        self._agent_key = str(me.get("agentId", me.get("id", "agent-1")))
        self._agent_name = me.get("agentName", me.get("name", "Agent"))
        
        balance = me.get("balance", 0)
        moltz = me.get("moltz", 0)
        cross = me.get("cross", 0)
        
        # Per-agent dashboard update
        dashboard_state.update_agent(self._agent_key, {
            "name": self._agent_name,
            "status": "playing" if state == IN_GAME else "idle",
            "smoltz": balance,
            "moltz": moltz,
            "cross": cross,
            "whitelisted": state != NO_IDENTITY,
        })

        # Aggregate total update (approximate since it's per-heartbeat)
        # In a real multi-agent, we'd sum these, but for now we just 
        # ensure the individual agent views are correct.
        dashboard_state.total_smoltz = sum(a.get("smoltz", 0) for a in dashboard_state.agents.values())
        dashboard_state.total_moltz = sum(a.get("moltz", 0) for a in dashboard_state.agents.values())
        dashboard_state.total_cross = sum(a.get("cross", 0) for a in dashboard_state.agents.values())

        # Step 3: Route based on state
        d_dir = self._agent_key.replace("agent", "dev-agent") if self._agent_key != "agent-1" else "dev-agent"
        
        if state == NO_IDENTITY:
            await self._handle_no_identity(me, d_dir)
            return

        if state == IN_GAME:
            await self._handle_in_game(ctx)
            return

        if state in (READY_FREE, READY_PAID):
            await self._handle_ready(me, state)
            return

    async def _handle_no_identity(self, me: dict, d_dir: str):
        """Setup pipeline: wallet → whitelist → identity. Respects config flags."""
        from bot.credentials import load_credentials
        from bot.setup.whitelist import ensure_whitelist
        from bot.setup.identity import ensure_identity

        creds = load_credentials(d_dir) or {}
        owner_eoa = creds.get("owner_eoa", "")

        log.info("[%s] 🆔 Handling NO_IDENTITY — Starting setup pipeline...", self._agent_key)

        # 1. Ensure Wallets (Agent + SC Wallet)
        if AUTO_SC_WALLET:
            await ensure_molty_wallet(self.api, owner_eoa, d_dir)

        # 2. Ensure Whitelist
        if AUTO_WHITELIST:
            wl_ok = await ensure_whitelist(self.api, d_dir)
            if not wl_ok:
                log.info(
                    "⏳ Whitelist pending — Owner EOA may need CROSS for gas. "
                    "Fund Owner EOA: %s then bot will retry in 2 minutes.", owner_eoa
                )
                await asyncio.sleep(120)
                return
        else:
            log.info("[%s] Whitelist auto-approval skipped (AUTO_WHITELIST=false).", self._agent_key)

        # Q9: ERC-8004 Identity
        if AUTO_IDENTITY:
            id_ok = await ensure_identity(self.api, d_dir)
            if not id_ok:
                log.info("[%s] Identity registration pending. Will retry in 30s.", self._agent_key)
                await asyncio.sleep(30)
                return
        else:
            log.info("[%s] Identity auto-registration skipped (AUTO_IDENTITY=false)", self._agent_key)

        log.info("[%s] ✅ Full setup complete!", self._agent_key)

    async def _handle_ready(self, me: dict, state: str):
        """Join a game using v1.6.1 unified /ws/join socket.
        Per skill.md Core Rule 1: one socket handles both join + gameplay.
        """
        from bot.game.ws_join import JoinEngine

        # Fetch current rooms to check for paid availability
        rooms = []
        try:
            rooms = await self.api.get_rooms()
        except:
            pass

        room_type = select_room(me, rooms)
        log.info("═══ JOINING GAME via /ws/join: type=%s ═══", room_type)

        # Feed dashboard
        dashboard_state.update_agent(self._agent_key, {
            "name": self._agent_name,
            "status": "joining",
            "room_name": f"{room_type} room",
        })
        dashboard_state.add_log(f"Joining {room_type} room via /ws/join...", "info",
                                self._agent_key)

        # Set temp memory
        self.memory.set_temp_game("joining")
        await self.memory.save()

        # v1.6.1: Paid rooms MUST be onchain
        mode_to_use = "onchain" if room_type == "paid" else "offchain"
        log.info("Starting JoinEngine (entry=%s, mode=%s)...", room_type, mode_to_use)

        # Run unified join + gameplay engine (v1.6.1)
        engine = JoinEngine(entry_type=room_type, mode=mode_to_use, api_key=self.api_key)
        engine.dashboard_key = self._agent_key
        engine.dashboard_name = self._agent_name
        game_result = await engine.run()

        # Self-healing: if 1013 error detected, reset identity for next attempt
        if engine.needs_identity_reset:
            log.info("[%s] 🛠️ Self-Healing: Resetting identity to clear 1013 error...", self._agent_key)
            try:
                await self.api.delete_identity()
                from bot.setup.identity import ensure_identity
                d_dir = self._agent_key.replace("agent", "dev-agent") if self._agent_key != "agent-1" else "dev-agent"
                await ensure_identity(self.api, d_dir)
            except Exception as e:
                log.error("[%s] Identity reset failed: %s", self._agent_key, e)

        # Settle game result
        await settle_game(game_result, room_type, self.memory)
        log.info("Game complete. Starting next cycle in 5s...")
        await asyncio.sleep(5)

    async def _handle_in_game(self, ctx: dict):
        """Resume or start playing an active game.
        Per game-loop.md: always connect WS, even when dead.
        Dead agents wait for game_ended inside the WS engine.
        """
        game_id = ctx["game_id"]
        agent_id = ctx["agent_id"]
        entry_type = ctx.get("entry_type", "free")

        if not ctx.get("is_alive", True):
            log.info("Agent is dead in game %s. Waiting for game to finish on server...", game_id)
            await asyncio.sleep(60)
            return

        await self._play_game(game_id, agent_id, entry_type)

    async def _play_game(self, game_id: str, agent_id: str, entry_type: str):
        """Run the WebSocket gameplay engine."""
        log.info("═══ PLAYING GAME: %s (type=%s) ═══", game_id, entry_type)

        # Feed dashboard — use SAME key as heartbeat so no duplicate card
        dashboard_state.update_agent(self._agent_key, {
            "status": "playing",
            "room_id": game_id,
            "room_name": entry_type + " room",
        })
        dashboard_state.add_log(f"Joined {entry_type} game: {game_id[:12]}", "info", self._agent_key)

        # Set temp memory for this game
        self.memory.set_temp_game(game_id)
        await self.memory.save()

        # Run WebSocket engine — pass agent_key + name for dashboard
        engine = WebSocketEngine(game_id, agent_id)
        engine.dashboard_key = self._agent_key
        engine.dashboard_name = self._agent_name
        game_result = await engine.run()

        # Settle
        await settle_game(game_result, entry_type, self.memory)

        log.info("Game complete. Starting next cycle in 5s...")
        await asyncio.sleep(5)
