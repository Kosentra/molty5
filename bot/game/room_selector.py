"""
Room selector — forced to FREE only as per user request.
"""
from bot.utils.logger import get_logger

log = get_logger(__name__)

def select_room(me_data: dict, rooms_data: list = None) -> str:
    """
    Determine which room type to join based on ROOM_MODE.
    auto: joins paid if balance >= 500, else free.
    free: always free.
    paid: always paid.
    """
    from bot.config import ROOM_MODE
    
    mode = ROOM_MODE.lower()
    balance = me_data.get("balance", 0)
    
    if mode == "paid":
        log.info("Room mode: FORCED PAID ONLY")
        return "paid"
    
    if mode == "free":
        log.info("Room mode: FORCED FREE ONLY")
        return "free"
        
    # Auto mode logic
    if balance >= 500:
        log.info("Room mode: AUTO (Balance %d >= 500) -> Choosing PAID", balance)
        return "paid"
    else:
        log.info("Room mode: AUTO (Balance %d < 500) -> Choosing FREE", balance)
        return "free"
