"""
AI Brain Module — LLM-driven strategic decision making via Groq.
v1.0: Real-time analysis with Llama-3-70B.
"""
import json
import httpx
from bot.config import GROQ_API_KEY, AI_MODEL, AGENT_NAME
from bot.utils.logger import get_logger

log = get_logger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

async def get_ai_decision(view: dict, agent_name: str = "Agent") -> dict | None:
    """
    Send game view to LLM and get a strategic decision.
    Returns: { "action": "...", "data": {...}, "reason": "...", "thought": "..." }
    """
    if not GROQ_API_KEY:
        log.warning("AI_BRAIN: GROQ_API_KEY missing")
        return None

    # 1. Simplify view for LLM to save tokens and improve focus
    summary = _prepare_view_summary(view)
    
    system_prompt = (
        f"You are the strategic brain of '{agent_name}', an AI agent playing Claw Royale (v1.6.3).\n"
        "Your goal: Maximize $Moltz collection and survival. Be aggressive against weak players.\n\n"
        "Game Rules:\n"
        "- Move (2-3 EP), Attack (2 EP), Use Item (1 EP), Rest (0 EP).\n"
        "- Range: Fist/Sword (0), Bow/Pistol (1), Sniper (2).\n"
        "- Weapons: katana > sniper > sword > pistol > dagger > bow > fist.\n"
        "- Terrain: 'water' or 'storm' costs 3 EP to move.\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"action": "move|attack|pickup|use_item|equip|rest", "data": {"regionId": "...", "targetId": "...", "itemId": "..."}, "reason": "concise explanation", "thought": "internal monologue"}\n'
    )

    user_prompt = f"Current Game State:\n{json.dumps(summary, indent=2)}\n\nWhat is your next move?"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                },
                timeout=5.0
            )
            
            if resp.status_code == 200:
                result = resp.json()
                content = result['choices'][0]['message']['content']
                decision = json.loads(content)
                log.info("AI Thought: %s", decision.get("thought", "None"))
                return decision
            else:
                log.warning("AI_BRAIN: API error %d: %s", resp.status_code, resp.text)
                return None
    except Exception as e:
        log.error("AI_BRAIN: Thinking failed: %s", e)
        return None

def _prepare_view_summary(view: dict) -> dict:
    """Extract relevant info for the LLM to minimize token usage."""
    self_data = view.get("self", {})
    region = view.get("currentRegion", {})
    
    # Weapons stats for LLM context
    equipped = self_data.get("equippedWeapon", {})
    
    summary = {
        "me": {
            "hp": self_data.get("hp"),
            "ep": self_data.get("ep"),
            "max_ep": self_data.get("maxEp", 10),
            "regionId": region.get("id"),
            "regionName": region.get("name"),
            "terrain": region.get("terrain"),
            "equipped": equipped.get("typeId", "fist"),
            "inventory": [i.get("typeId") for i in self_data.get("inventory", [])]
        },
        "nearby_items": [],
        "nearby_agents": [],
        "exits": []
    }
    
    # Limit items to top 5
    for item_wrap in view.get("visibleItems", [])[:5]:
        item = item_wrap.get("item", item_wrap)
        summary["nearby_items"].append({
            "typeId": item.get("typeId"),
            "regionId": item_wrap.get("regionId", region.get("id"))
        })
        
    # Limit agents to top 5
    for agent in view.get("visibleAgents", [])[:5]:
        if agent.get("id") == self_data.get("id"): continue
        summary["nearby_agents"].append({
            "name": agent.get("name"),
            "hp": agent.get("hp"),
            "isGuardian": agent.get("isGuardian"),
            "regionId": agent.get("regionId")
        })
        
    # Region connections
    for conn in region.get("connections", []) or view.get("connectedRegions", []):
        rid = conn if isinstance(conn, str) else conn.get("id")
        summary["exits"].append(rid)
        
    # Danger zones
    danger = [dz.get("id") if isinstance(dz, dict) else dz for dz in view.get("pendingDeathzones", [])]
    summary["danger_zones"] = danger
    
    return summary
