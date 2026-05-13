"""
Strategy brain — main decision engine with priority-based action selection.
v1.6.2: CLAW ROYALE EDITION
- Aggressive Execution: Execute anyone with HP < 40.
- Loot Reaping: Focus on killing players to steal their healing items.
- Ranged Harassment: Use Sniper range advantage (Range 2) to dominate.
- Low Threshold: Combat starts at HP > 35 (Down from 50).
- EP Conscious: Use Item (1 EP), Attack (2 EP), Move (2-3 EP).
"""
import random
from bot.utils.logger import get_logger
from bot.config import AGENT_NAME

log = get_logger(__name__)

# ── Weapon stats ─────────────────────────────────────────────────────
WEAPONS = {
    "fist": {"bonus": 0, "range": 0},
    "dagger": {"bonus": 10, "range": 0},
    "sword": {"bonus": 20, "range": 0},
    "katana": {"bonus": 35, "range": 0},
    "bow": {"bonus": 5, "range": 1},
    "pistol": {"bonus": 10, "range": 1},
    "sniper": {"bonus": 28, "range": 2},
}

WEAPON_PRIORITY = ["sniper", "katana", "sword", "pistol", "dagger", "bow", "fist"]

ITEM_PRIORITY = {
    "rewards": 300, "moltz": 300, "smoltz": 300,
    "reward1": 300, "reward2": 300, "reward3": 300,
    "gold": 300, "credits": 300, "balance": 300,
    "sniper": 290, "katana": 280, "sword": 95, "pistol": 90,
    "dagger": 80, "bow": 75,
    "medkit": 180, "bandage": 120, "emergency_food": 60, "energy_drink": 58,
    "binoculars": 65, "map": 52, "megaphone": 40,
}

RECOVERY_ITEMS = {"medkit": 50, "bandage": 30, "emergency_food": 20, "energy_drink": 0}

# ── REAPER Thresholds ────────────────────────────────────────────────
AGGRESSION_MIN_HP = 35  # VERY AGGRESSIVE
CRITICAL_HEAL_HP = 30
KITING_EP_RESERVE = 2

def get_weapon_bonus(equipped_weapon) -> int:
    if not equipped_weapon: return 0
    return WEAPONS.get(equipped_weapon.get("typeId", "").lower(), {}).get("bonus", 0)

def get_weapon_range(equipped_weapon) -> int:
    if not equipped_weapon: return 0
    return WEAPONS.get(equipped_weapon.get("typeId", "").lower(), {}).get("range", 0)

def _get_item_type(item: dict) -> str:
    if not item: return ""
    return (item.get("typeId") or item.get("type") or item.get("name") or "").lower()

def _get_item_category(item: dict) -> str:
    if not item: return ""
    return (item.get("category") or item.get("cat") or item.get("type") or "").lower()

# ── State Tracking ──────────────────────────────────────────────────
_used_facilities = set()
_survival_state = {"last_hp": 100}
_map_knowledge = {"revealed": False, "death_zones": set(), "safe_center": []}

def reset_game_state():
    global _used_facilities, _survival_state, _map_knowledge
    _used_facilities = set()
    _survival_state = {"last_hp": 100}
    _map_knowledge = {"revealed": False, "death_zones": set(), "safe_center": []}
    log.info("BLOOD REAPER brain reset for new game")

def learn_from_map(view: dict):
    global _map_knowledge
    _map_knowledge["revealed"] = True
    for r in view.get("visibleRegions", []):
        if isinstance(r, dict) and not r.get("isDeathZone"):
            _map_knowledge["safe_center"].append(r.get("id"))

def mark_facility_used(facility_id: str):
    if facility_id: _used_facilities.add(facility_id)

def decide_action(view: dict, can_act: bool) -> dict | None:
    self_data = view.get("self", {})
    my_id = self_data.get("id")
    hp = self_data.get("hp", 0)
    ep = self_data.get("ep", 0)
    inventory = self_data.get("inventory", [])
    equipped = self_data.get("equippedWeapon")
    max_ep = self_data.get("maxEp", 10)
    alive_count = view.get("aliveCount", 50)
    
    region = view.get("currentRegion", {})
    region_id = region.get("id", "")
    connections = region.get("connections", []) or view.get("connectedRegions", [])
    visible_items_raw = view.get("visibleItems", [])
    visible_agents = view.get("visibleAgents", [])
    
    visible_items = []
    for entry in visible_items_raw:
        item = entry.get("item") if "item" in entry else entry
        if isinstance(item, dict):
            item["regionId"] = entry.get("regionId", region_id)
            visible_items.append(item)

    danger_ids = {dz.get("id") for dz in view.get("pendingDeathzones", []) if isinstance(dz, dict)}
    for r in view.get("visibleRegions", []):
        if isinstance(r, dict) and r.get("isDeathZone"):
            danger_ids.add(r.get("id"))

    move_ep_cost = 2
    if region.get("terrain") == "water" or region.get("weather") == "storm":
        move_ep_cost = 3

    # Targets
    enemies = [a for a in visible_agents if a.get("isAlive") and a.get("id") != my_id and not a.get("isGuardian")]
    guardians = [a for a in visible_agents if a.get("isAlive") and a.get("isGuardian")]

    # ── Priority 1: Emergency Escape (Death Zone) ─────────────────
    if region.get("isDeathZone") or region_id in danger_ids:
        safe_target = _find_safe_region(connections, danger_ids)
        if safe_target and ep >= move_ep_cost:
            return {"action": "move", "data": {"regionId": safe_target}, "reason": "ESCAPE: DANGER ZONE!"}

    # ── Priority 2: REAPER EXECUTION (Target HP < 40) ──────────────
    # Kill them to take their loot (Reap Heal)
    all_targets = guardians + enemies
    if all_targets and ep >= 2:
        weak = [t for t in all_targets if t.get("hp", 100) < 40]
        if weak:
            target = min(weak, key=lambda t: t.get("hp", 100))
            if _is_in_range(target, region_id, get_weapon_range(equipped), connections):
                if can_act:
                    return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                            "reason": f"REAPER: Executing {target.get('name')} (HP={target.get('hp')}) to steal their loot!"}

    # ── Phase Detection ─────────────────────────────────────────
    # Mode: BLOOD REAPER (Aggressive)
    is_predator_mode = alive_count < 30 or _get_item_type(equipped) in ["katana", "sniper", "sword"] or hp > 80

    # ── Priority 3: HUNTING ───────────────────────────────────────
    if all_targets and ep >= 2:
        # ACTIVE HUNT (Aggressive HP threshold)
        if (is_predator_mode or hp > 40) and hp >= AGGRESSION_MIN_HP:
            # Focus on player enemies to get their gear
            hunt_targets = enemies if enemies else guardians
            target = min(hunt_targets, key=lambda t: t.get("hp", 100))
            if _is_in_range(target, region_id, get_weapon_range(equipped), connections):
                if can_act:
                    return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                            "reason": f"BLOODLUST: Hunting {target.get('name')} for rewards!"}

    # ── Priority 4: FREE ACTIONS (Pickup/Equip) ───────────────────
    pickup = _check_pickup(visible_items, inventory, region_id, equipped)
    if pickup: return pickup

    equip = _check_smart_equip(inventory, equipped, all_targets, region_id, connections)
    if equip: return equip

    # ── COOLDOWN BLOCK ──────────────────────────────────────────
    if not can_act: return None

    # ── Priority 5: REAPER MAINTENANCE ────────────────────────────
    if hp < 75 and ep >= 1:
        heal = _find_healing_item(inventory, hp < 30)
        if heal: return {"action": "use_item", "data": {"itemId": heal["id"]}, "reason": f"MAINTENANCE: HP={hp}"}
    
    if ep <= 2 and ep >= 1:
        drink = next((i for i in inventory if _get_item_type(i) == "energy_drink"), None)
        if drink: return {"action": "use_item", "data": {"itemId": drink["id"]}, "reason": "STAMINA: EP low"}

    # ── Priority 6: STRATEGIC MOVEMENT (Hunt for Loot) ────────────
    if ep >= move_ep_cost:
        move_target = _choose_move_target(connections, danger_ids, visible_items, region_id, hp < 40)
        if move_target:
            return {"action": "move", "data": {"regionId": move_target}, 
                    "reason": f"STALKING: To {move_target[:8]} for potential kills/loot"}

    # ── Priority 7: BANKING (Rest) ────────────────────────────────
    if ep < max_ep:
        return {"action": "rest", "data": {}, "reason": f"BANKING: EP={ep}/{max_ep}"}

    return None

def _is_in_range(target, my_region, w_range, connections) -> bool:
    tr = target.get("regionId", my_region)
    if tr == my_region: return True
    if w_range >= 1 and connections:
        adj = {c if isinstance(c, str) else c.get("id") for c in connections}
        return tr in adj
    return False

def _check_pickup(items, inventory, region_id, equipped) -> dict | None:
    local = [i for i in items if i.get("regionId") == region_id]
    if not local: return None
    local.sort(key=lambda i: ITEM_PRIORITY.get(_get_item_type(i), 0), reverse=True)
    best = local[0]
    score = ITEM_PRIORITY.get(_get_item_type(best), 0)
    if score <= 0: return None
    if len(inventory) < 10:
        return {"action": "pickup", "data": {"itemId": best["id"]}, "reason": f"PICKUP: {_get_item_type(best)}"}
    inv_scores = [(i, ITEM_PRIORITY.get(_get_item_type(i), 0) + (1000 if _get_item_category(i) == "currency" else 0)) for i in inventory]
    inv_scores.sort(key=lambda x: x[1])
    worst_inv, worst_score = inv_scores[0]
    if score > worst_score + 20:
        return {"action": "drop", "data": {"itemId": worst_inv["id"]}, "reason": f"SMART STORAGE: Drop {_get_item_type(worst_inv)} for {_get_item_type(best)}"}
    return None

def _check_smart_equip(inventory, equipped, targets, my_region, connections) -> dict | None:
    current_bonus = get_weapon_bonus(equipped)
    all_weapons = [i for i in inventory if _get_item_category(i) == "weapon"]
    if not all_weapons: return None
    all_weapons.sort(key=lambda w: WEAPONS.get(_get_item_type(w), {}).get("bonus", 0), reverse=True)
    best_in_inv = all_weapons[0]
    best_bonus = WEAPONS.get(_get_item_type(best_in_inv), {}).get("bonus", 0)
    if best_bonus > current_bonus:
        return {"action": "equip", "data": {"itemId": best_in_inv["id"]}, "reason": "EQUIP: Stronger weapon"}
    return None

def _find_safe_region(connections, danger_ids) -> str | None:
    for c in connections:
        rid = c if isinstance(c, str) else c.get("id")
        if rid not in danger_ids: return rid
    return None

def _find_healing_item(inventory, critical) -> dict | None:
    heals = [i for i in inventory if _get_item_type(i) in RECOVERY_ITEMS and RECOVERY_ITEMS[_get_item_type(i)] > 0]
    if not heals: return None
    heals.sort(key=lambda i: RECOVERY_ITEMS[_get_item_type(i)], reverse=critical)
    return heals[0]

def _choose_move_target(connections, danger_ids, items, my_region, desperate=False) -> str | None:
    if desperate:
        for item in items:
            t = _get_item_type(item)
            if t in RECOVERY_ITEMS and RECOVERY_ITEMS[t] > 0:
                rid = item.get("regionId")
                if rid and rid != my_region and rid not in danger_ids: return rid
    for item in items:
        rid = item.get("regionId")
        if rid and rid != my_region and rid not in danger_ids: return rid
    safe = []
    for c in connections:
        rid = c if isinstance(c, str) else c.get("id")
        if rid not in danger_ids:
            terrain = c.get("terrain", "plains") if isinstance(c, dict) else "plains"
            score = 10 if terrain in ["hills", "plains"] else 1
            safe.append((rid, score))
    if safe:
        safe.sort(key=lambda x: x[1], reverse=True)
        return safe[0][0]
    return None
