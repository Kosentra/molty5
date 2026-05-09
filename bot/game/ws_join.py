"""
WebSocket Join Engine — v1.6.1 unified /ws/join socket.

Per skill.md Core Rule 1 (v1.6.1):
  Open wss://cdn.moltyroyale.com/ws/join → read 'welcome' frame →
  send 'hello' frame → same socket becomes gameplay socket automatically.
  Do NOT re-dial to /ws/agent for new games.

Flow:
  1. Connect to /ws/join with X-API-Key
  2. Receive 'welcome' frame → check decision field
  3. Send 'hello' { type: "hello", entryType: "free" | "paid" }
  4. Receive join state messages (queued, assigned, waiting)
  5. Receive gameplay messages (agent_view, turn_advanced, etc.)
  6. Return when game_ended received

For RESUME (already in game): use websocket_engine.py → /ws/agent directly.
"""
import json
import asyncio
import websockets
from bot.config import WS_JOIN_URL, SKILL_VERSION
from bot.credentials import get_api_key
from bot.game.action_sender import ActionSender, COOLDOWN_ACTIONS
from bot.strategy.brain import decide_action, reset_game_state, learn_from_map
from bot.dashboard.state import dashboard_state
from bot.utils.rate_limiter import ws_limiter
from bot.utils.logger import get_logger

log = get_logger(__name__)


class JoinEngine:
    """
    Unified join + gameplay engine via /ws/join (v1.6.1).
    One socket handles matchmaking queue AND full gameplay.
    """

    def __init__(self, entry_type: str = "free", mode: str = "offchain"):
        self.entry_type = entry_type   # "free" | "paid"
        self.mode = mode               # "offchain" | "onchain"
        self.action_sender = ActionSender()
        self.ws = None
        self.game_result = None
        self.last_view = None
        self._ping_task = None
        self._running = False
        self._map_just_used = False
        self._joined = False           # True once assigned to a game
        # Dashboard
        self.dashboard_key = "agent-1"
        self.dashboard_name = "Agent"
        self.game_id = ""
        self.agent_id = ""

    async def run(self) -> dict:
        """
        Main entry point. Connects to /ws/join and runs until game_ended.
        Returns game result dict.
        """
        api_key = get_api_key()
        headers = {
            "X-API-Key": api_key,
            "X-Version": SKILL_VERSION,
        }

        self._running = True
        retry_count = 0
        max_retries = 5

        while self._running and retry_count < max_retries:
            try:
                log.info("Connecting /ws/join (entryType=%s mode=%s)...",
                         self.entry_type, self.mode)
                async with websockets.connect(
                    WS_JOIN_URL,
                    additional_headers=headers,
                    ping_interval=None,
                    max_size=2 ** 20,
                ) as ws:
                    self.ws = ws
                    retry_count = 0
                    log.info("✅ /ws/join connected")

                    # Start ping keepalive
                    self._ping_task = asyncio.create_task(self._ping_loop())

                    # Message processing loop
                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            if not isinstance(msg, dict):
                                continue
                            msg_type = msg.get("type", "unknown")
                            log.debug("WS recv: type=%s", msg_type)
                            result = await self._handle_message(msg)
                            if result is not None:
                                self._running = False
                                return result
                        except json.JSONDecodeError:
                            log.warning("Non-JSON WS message: %s", raw_msg[:100])

            except websockets.exceptions.ConnectionClosed as e:
                retry_count += 1
                log.warning("WS closed: code=%s reason=%s (retry %d/%d)",
                            e.code, e.reason, retry_count, max_retries)
                if self._ping_task:
                    self._ping_task.cancel()
                await asyncio.sleep(min(2 ** retry_count, 30))

            except Exception as e:
                retry_count += 1
                log.error("WS error: %s (retry %d/%d)", e, retry_count, max_retries)
                if self._ping_task:
                    self._ping_task.cancel()
                await asyncio.sleep(min(2 ** retry_count, 30))

        return self.game_result or {"status": "disconnected"}

    async def _handle_message(self, msg: dict) -> dict | None:
        """Handle a single WebSocket message. Returns game result or None."""
        msg_type = msg.get("type", "")

        # ── welcome frame: entry point of join state machine ─────────
        if msg_type == "welcome":
            decision = msg.get("decision", "ASK_ENTRY_TYPE")
            log.info("Welcome: decision=%s", decision)

            if decision == "BLOCKED":
                log.error("❌ Join BLOCKED (code 4001) — identity or whitelist missing")
                dashboard_state.add_log("❌ Join BLOCKED — identity registration needed", "error")
                self._running = False
                return {"status": "blocked", "reason": "READINESS_BLOCKED"}

            if decision == "ALREADY_IN_GAME":
                log.info("Already in game — server will route socket to gameplay")
                # Server will send agent_view automatically, no hello needed

            else:
                # ASK_ENTRY_TYPE / FREE_ONLY / PAID_ONLY
                # Honour server's decision for entry type
                actual_entry = self.entry_type
                if decision == "FREE_ONLY":
                    actual_entry = "free"
                    if self.entry_type == "paid":
                        log.warning("Server says FREE_ONLY — falling back to free")
                elif decision == "PAID_ONLY":
                    actual_entry = "paid"

                hello = {"type": "hello", "entryType": actual_entry}
                if actual_entry == "paid" and self.mode == "onchain":
                    hello["mode"] = "onchain"
                await self._send(hello)
                log.info("Sent hello: entryType=%s", actual_entry)

        # ── join state machine messages ───────────────────────────────
        elif msg_type == "queued":
            log.info("⏳ Queued — waiting for room assignment...")
            dashboard_state.add_log("Queued — waiting for room...", "info")

        elif msg_type == "assigned":
            self.game_id = msg.get("gameId", "")
            self.agent_id = msg.get("agentId", "")
            self._joined = True
            log.info("✅ Assigned: game=%s agent=%s", self.game_id[:12], self.agent_id[:12])
            dashboard_state.add_log(
                f"✅ Joined {self.entry_type} game: {self.game_id[:12]}", "info",
                self.dashboard_key,
            )
            # Socket automatically becomes gameplay socket — no re-dial!

        # ── gameplay messages (identical to websocket_engine.py) ─────

        elif msg_type == "agent_view":
            view = msg.get("view") or msg.get("data") or {}
            if isinstance(view, dict) and view:
                self.last_view = view
                reason = msg.get("reason", "initial")
                alive = view.get("self", {}).get("isAlive", "?")
                hp = view.get("self", {}).get("hp", "?")
                ep = view.get("self", {}).get("ep", "?")
                log.info("agent_view (reason=%s) alive=%s HP=%s EP=%s", reason, alive, hp, ep)
                await self._on_agent_view(view)

        elif msg_type == "action_result":
            self.action_sender.can_act = msg.get("canAct", self.action_sender.can_act)
            self.action_sender.cooldown_remaining_ms = msg.get("cooldownRemainingMs", 0)
            success = msg.get("success", False)
            if success:
                data = msg.get("data", {})
                action_msg = data.get("message", "") if isinstance(data, dict) else str(data)
                log.info("Action OK: %s (canAct=%s)", action_msg, msg.get("canAct"))
                if isinstance(data, dict) and "map" in str(action_msg).lower():
                    self._map_just_used = True
            else:
                err = msg.get("error", {})
                log.warning("Action FAILED: %s — %s",
                            err.get("code", "") if isinstance(err, dict) else str(err),
                            err.get("message", "") if isinstance(err, dict) else "")

        elif msg_type == "can_act_changed":
            self.action_sender.can_act = msg.get("canAct", True)
            self.action_sender.cooldown_remaining_ms = msg.get("cooldownRemainingMs", 0)
            log.info("can_act_changed: canAct=%s", msg.get("canAct"))
            if self.last_view and msg.get("canAct"):
                await self._on_agent_view(self.last_view)

        elif msg_type == "turn_advanced":
            turn_num = msg.get("turn", "?")
            view = msg.get("view")
            if not view and isinstance(msg.get("data"), dict):
                view = msg["data"].get("view")
                turn_num = msg["data"].get("turn", turn_num)
            log.info("Turn %s — processing view...", turn_num)
            if view and isinstance(view, dict):
                self.last_view = view
                await self._on_agent_view(view)
            elif self.last_view:
                await self._on_agent_view(self.last_view)

        elif msg_type == "game_ended":
            log.info("═══ GAME ENDED ═══")
            reset_game_state()
            self.game_result = msg
            return msg

        elif msg_type == "waiting":
            log.info("Game is waiting for players to fill room...")

        elif msg_type == "pong":
            pass

        elif msg_type == "error":
            err_msg = msg.get("message", msg.get("data", {}).get("message", str(msg)))
            log.error("Server error: %s", err_msg)

        else:
            log.info("Unknown WS message: type=%s keys=%s", msg_type, list(msg.keys()))

        return None

    async def _on_agent_view(self, view: dict):
        """Process agent view → decide action → send."""
        if not isinstance(view, dict):
            return

        self_data = view.get("self", {})
        if not isinstance(self_data, dict):
            return

        alive_count = view.get("aliveCount", "?")

        if not self_data.get("isAlive", True):
            log.info("☠️ Agent DEAD — Alive remaining: %s. Waiting for game_ended...", alive_count)
            dashboard_state.update_agent(self.dashboard_key, {
                "status": "dead", "hp": 0, "ep": 0, "alive_count": alive_count,
                "last_action": "☠️ DEAD — waiting for game to end",
            })
            return

        hp = self_data.get("hp", "?")
        ep = self_data.get("ep", "?")
        region = view.get("currentRegion", {})
        region_name = region.get("name", "?") if isinstance(region, dict) else "?"
        log.info("Status: HP=%s EP=%s Region=%s | Alive: %s", hp, ep, region_name, alive_count)

        dashboard_state.update_agent(self.dashboard_key, {
            "name": self.dashboard_name,
            "hp": hp, "ep": ep,
            "status": "playing",
            "maxHp": self_data.get("maxHp", 100),
            "maxEp": self_data.get("maxEp", 10),
            "atk": self_data.get("atk", 0),
            "def": self_data.get("def", 0),
            "kills": self_data.get("kills", 0),
            "region": region_name,
            "alive_count": alive_count,
            "room_type": self.entry_type,
        })
        dashboard_state.add_log(
            f"HP={hp} EP={ep} Region={region_name} | Alive: {alive_count}",
            "info", self.dashboard_key,
        )

        # Map learning after Map item used
        if self._map_just_used:
            self._map_just_used = False
            learn_from_map(view)
            log.info("🗺️ Map knowledge updated")

        # Run strategy brain
        can_act = self.action_sender.can_send_cooldown_action()
        decision = decide_action(view, can_act)

        if decision is None:
            return

        action_type = decision["action"]
        action_data = decision.get("data", {})
        reason = decision.get("reason", "")

        if action_type in COOLDOWN_ACTIONS and not can_act:
            log.debug("Cooldown active — skipping %s", action_type)
            return

        payload = self.action_sender.build_action(action_type, action_data, reason, action_type)
        await self._send(payload)
        log.info("→ %s | %s", action_type.upper(), reason)
        dashboard_state.update_agent(self.dashboard_key, {
            "last_action": f"{action_type}: {reason[:60]}",
        })

    async def _send(self, payload: dict):
        """Send message through WebSocket with rate limiting."""
        if self.ws is None:
            return
        await ws_limiter.acquire()
        await self.ws.send(json.dumps(payload))

    async def _ping_loop(self):
        """Send ping every 15s to keep connection alive."""
        try:
            while self._running:
                await asyncio.sleep(15)
                if self.ws:
                    await self._send({"type": "ping"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug("Ping loop error: %s", e)
