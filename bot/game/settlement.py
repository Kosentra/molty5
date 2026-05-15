"""
Game settlement — Phase 3: process game end, update memory, prepare for next game.
"""
from bot.memory.agent_memory import AgentMemory
from bot.utils.telegram import tg_notifier
from bot.utils.logger import get_logger


log = get_logger(__name__)


async def settle_game(game_result: dict, entry_type: str, memory: AgentMemory):
    """
    Process game end:
    1. Extract final stats
    2. Update memory (overall history + lessons)
    3. Clear temp memory
    """
    result = game_result.get("result", game_result)
    is_winner = result.get("isWinner", False)
    final_rank = result.get("finalRank", 0)
    kills = result.get("kills", 0)
    # Robust reward extraction (handles varying server casing/field names)
    rewards = result.get("rewards", {})
    if not isinstance(rewards, dict):
        rewards = {}
        
    # Check multiple possible keys for sMoltz and Moltz
    smoltz_earned = (
        rewards.get("sMoltz") or rewards.get("smoltz") or 
        rewards.get("balance") or result.get("smoltz") or 
        result.get("sMoltz") or 0
    )
    moltz_earned = (
        rewards.get("moltz") or rewards.get("Moltz") or 
        result.get("moltz") or result.get("Moltz") or 0
    )

    log.info("═══ GAME SETTLEMENT ═══")
    log.info("  Winner: %s | Rank: %d | Kills: %d", "YES" if is_winner else "No", final_rank, kills)
    log.info("  Rewards: %d sMoltz, %d Moltz", smoltz_earned, moltz_earned)

    # Update memory
    memory.record_game_end(
        is_winner=is_winner,
        final_rank=final_rank,
        kills=kills,
        smoltz_earned=smoltz_earned,
    )

    # Add lessons based on game outcome
    if is_winner:
        memory.add_lesson(f"Won with {kills} kills at rank {final_rank}")
    elif final_rank <= 3:
        memory.add_lesson(f"Top 3 finish (rank {final_rank}) with {kills} kills")
    elif kills == 0:
        memory.add_lesson("Zero kills — need more aggressive guardian/monster targeting")

    # Clear temp for next game
    memory.clear_temp()
    await memory.save()

    # Telegram Report
    from bot.dashboard.state import dashboard_state
    status_icon = "🏆" if is_winner else "💀"
    msg = (
        f"{status_icon} <b>Game Over ({entry_type})</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🚩 Rank: <b>{final_rank}</b>\n"
        f"⚔️ Kills: <b>{kills}</b>\n"
        f"💰 Earned: <b>{smoltz_earned}</b> sMoltz\n"
        f"✨ Total: <b>{dashboard_state.total_smoltz}</b>"
    )
    await tg_notifier.send_message(msg)


    log.info("Settlement complete. Ready for next game.")
