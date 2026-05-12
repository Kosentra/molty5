import asyncio
import json
from bot.api_client import MoltyAPI

API_KEY = "mr_live_6j03kxXGtvyhcGCWGpyzwTHWYJvjEcW-"

async def debug_me():
    api = MoltyAPI(API_KEY)
    try:
        me = await api.get_accounts_me()
        print("--- /accounts/me RESPONSE ---")
        print(json.dumps(me, indent=2))
        print("----------------------------")
        
        readiness = me.get("readiness", {})
        print(f"erc8004Id: {readiness.get('erc8004Id')}")
        print(f"whitelistApproved: {readiness.get('whitelistApproved')}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(debug_me())
