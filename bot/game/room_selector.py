"""
Room selector — forced to FREE only as per user request.
"""
from bot.utils.logger import get_logger

log = get_logger(__name__)

def select_room(me_data: dict, rooms_data: list = None) -> str:
    """
    Determine which room type to join.
    FORCED TO FREE ONLY.
    """
    log.info("Room mode: FORCED FREE ONLY (Security Policy)")
    return "free"
