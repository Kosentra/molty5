"""
Strategy brain — main decision engine with priority-based action selection.
v1.6.2: Aggressive Predator v2.1
- Strategic Guardian Hunting (120 sMoltz per kill)
- Kill Stealing (Executing low-HP enemies)
- Smart Storage (Drop-and-Replace logic)
- High Ground Advantage (Hills prioritize vision)
- Kiting (Maintaining range advantage)
- Resting (Strategic EP banking)
"""
import random
from bot.utils.logger import get_logger
from bot.config import AGENT_NAME

log = get_logger(__name__)

# ── Weapon stats from combat-items.md ─────────────────────────────────
WEAPONS = {
    "fist": {"bonus": 0, "range": 0},
    "dagger": {"bonus": 10, "range": 0},
    "sword": {"bonus": 20, "range": 0},
    "katana": {"bonus": 35, "range": 0},
    "bow": {"bonus": 5, "range": 1},
    "pistol": {"bonus": 10, "range": 1},
    "sniper": {"bonus": 28, "range": 2},
}

WEAPON_PRIORITY = ["katana", "sniper", "sword", "pistol", "dagger", "bow", "fist"]

# ── Item priority for pickup ──────────────────────────────────────────
ITEM_PRIORITY = {
    "rewards": 300, "moltz": 300, "smoltz": 300,
    "reward1": 300, "reward2": 300, "reward3": 300,
    "gold": 300, "credits": 300, "balance": 300,
    "katana": 250, "sniper": 240, "sword": 90, "pistol": 85,
    "dagger": 80, "bow": 75,
    "medkit": 180, "bandage": 120, "emergency_food": 60, "energy_drink": 58,
    "binoculars": 55, "map": 52, "megaphone": 40,
}

RECOVERY_ITEMS = {"medkit": 50, "bandage": 30, "emergency_food": 20, "energy_drink": 0}

# ── Survival & Aggression Thresholds ──────────────────────────────────
SAFETY_MARGIN_HP = 20
AGGRESSION_MIN_HP = 50
CRITICAL_HEAL_HP = 35
KITING_EP_RESERVE = 4

def get_weapon_bonus(equipped_weapon) -> int:
    if not equipped_weapon: return 0
    return WEAPONS.get(equipped_weapon.get("typeId", "").lower(), {}).get("bonus", 0)

def get_weapon_range(equipped_weapon) -> int:
    if not equipped_weapon: return 0
    return WEAPONS.get(equipped_weapon.get("typeId", "").lower(), {}).get("range", 0)

def _get_item_type(item: dict) -> str:
    return (item.get("typeId") or item.get("type") or item.get("name") or "").lower()

def _get_item_category(item: dict) -> str:
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
    log.info("Strategy brain reset for new game")

def learn_from_map(view: dict):
    """Process map data to reveal safe regions and death zones."""
    global _map_knowledge
    _map_knowledge["revealed"] = True
    # Logic to extract safe regions from visibleRegions in view
    for r in view.get("visibleRegions", []):
        if isinstance(r, dict) and not r.get("isDeathZone"):
            _map_knowledge["safe_center"].append(r.get("id"))

def mark_facility_used(facility_id: str):
    """Call this when interaction is successful."""
    if facility_id:
        _used_facilities.add(facility_id)

def decide_action(view: dict, can_act: bool) -> dict | None:
    self_data = view.get("self", {})
    my_id = self_data.get("id")
    hp = self_data.get("hp", 0)
    ep = self_data.get("ep", 0)
    inventory = self_data.get("inventory", [])
    equipped = self_data.get("equippedWeapon")
    max_ep = self_data.get("maxEp", 10)
    
    region = view.get("currentRegion", {})
    region_id = region.get("id", "")
    connections = region.get("connections", []) or view.get("connectedRegions", [])
    visible_items_raw = view.get("visibleItems", [])
    visible_agents = view.get("visibleAgents", [])
    
    # Unwrap items
    visible_items = []
    for entry in visible_items_raw:
        item = entry.get("item") if "item" in entry else entry
        if isinstance(item, dict):
            item["regionId"] = entry.get("regionId", region_id)
            visible_items.append(item)

    # Danger Zones
    danger_ids = {dz.get("id") for dz in view.get("pendingDeathzones", []) if isinstance(dz, dict)}
    for r in view.get("visibleRegions", []):
        if isinstance(r, dict) and r.get("isDeathZone"):
            danger_ids.add(r.get("id"))

    # Movement cost
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

    # ── Priority 2: KILL STEALING (Low HP Targets) ────────────────
    all_targets = guardians + enemies
    if all_targets and ep >= 2:
        weak = [t for t in all_targets if t.get("hp", 100) < 30]
        if weak:
            target = min(weak, key=lambda t: t.get("hp", 100))
            if _is_in_range(target, region_id, get_weapon_range(equipped), connections):
                return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                        "reason": f"PREDATOR: Executing weak {target.get('name')} (HP={target.get('hp')})"}

    # ── Priority 3: FREE ACTIONS (Pickup/Equip) ───────────────────
    pickup = _check_pickup(visible_items, inventory, region_id, equipped)
    if pickup: return pickup

    equip = _check_smart_equip(inventory, equipped, all_targets, region_id, connections)
    if equip: return equip

    if not can_act: return None

    # ── Priority 4: GUARDIAN FARMING (sMoltz Focus) ───────────────
    if guardians and ep >= 2 and hp >= AGGRESSION_MIN_HP:
        target = min(guardians, key=lambda t: t.get("hp", 100))
        if _is_in_range(target, region_id, get_weapon_range(equipped), connections):
            return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                    "reason": f"FARMER: Hunting Guardian (HP={target.get('hp')})"}

    # ── Priority 5: RANGED REAPING (Kiting) ───────────────────────
    if enemies and ep >= 2:
        target = min(enemies, key=lambda t: t.get("hp", 100))
        w_range = get_weapon_range(equipped)
        enemy_range = get_weapon_range(target.get("equippedWeapon"))
        if _is_in_range(target, region_id, w_range, connections):
            if w_range > enemy_range and target.get("regionId") != region_id:
                return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                        "reason": f"REAPER: Kiting enemy from range {w_range}"}

    # ── Priority 6: BRAWLING ──────────────────────────────────────
    if enemies and ep >= 2 and hp >= 70:
        target = min(enemies, key=lambda t: t.get("hp", 100))
        if target.get("regionId") == region_id:
             return {"action": "attack", "data": {"targetId": target["id"], "targetType": "agent"},
                     "reason": f"BRAWLER: Engaging player nearby (HP={target.get('hp')})"}

    # ── Priority 7: MAINTENANCE ───────────────────────────────────
    if hp < 75:
        heal = _find_healing_item(inventory, hp < 35)
        if heal: return {"action": "use_item", "data": {"itemId": heal["id"]}, "reason": f"HEAL: HP={hp}"}
    
    if ep <= 2:
        drink = next((i for i in inventory if _get_item_type(i) == "energy_drink"), None)
        if drink: return {"action": "use_item", "data": {"itemId": drink["id"]}, "reason": "STAMINA: EP low"}

    # ── Priority 8: STRATEGIC MOVEMENT ────────────────────────────
    if ep >= move_ep_cost:
        move_target = _choose_move_target(connections, danger_ids, visible_items, region_id)
        if move_target:
            return {"action": "move", "data": {"regionId": move_target}, "reason": f"EXPLORE: To {move_target[:8]}"}

    # ── Priority 9: BANKING (Rest) ────────────────────────────────
    if ep < max_ep:
        return {"action": "rest", "data": {}, "reason": f"REST: Banking EP ({ep}/{max_ep})"}

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
    
    # Smart Storage Drop
    inv_scores = []
    for i in inventory:
        s = ITEM_PRIORITY.get(_get_item_type(i), 0)
        if _get_item_category(i) == "currency": s += 1000
        inv_scores.append((i, s))
    inv_scores.sort(key=lambda x: x[1])
    worst_inv, worst_score = inv_scores[0]
    
    if score > worst_score + 20:
        return {"action": "drop", "data": {"itemId": worst_inv["id"]}, 
                "reason": f"SMART STORAGE: Drop {_get_item_type(worst_inv)} for {_get_item_type(best)}"}
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

def _choose_move_target(connections, danger_ids, items, my_region) -> str | None:
    # 1. Toward items
    for item in items:
        rid = item.get("regionId")
        if rid and rid != my_region and rid not in danger_ids:
            return rid
    # 2. Random safe
    safe = [c if isinstance(c, str) else c.get("id") for c in connections if (c if isinstance(c, str) else c.get("id")) not in danger_ids]
    return random.choice(safe) if safe else None

def _use_utility_item(inventory, hp, ep, alive_count) -> dict | None:
    map_item = next((i for i in inventory if _get_item_type(i) == "map"), None)
    if map_item: return {"action": "use_item", "data": {"itemId": map_item["id"]}, "reason": "UTIL: Reveal Map"}
    return None
