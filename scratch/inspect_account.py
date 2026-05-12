import asyncio
import os
import json
from dotenv import load_dotenv
from bot.api_client import MoltyAPI

async def inspect_account():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    api = MoltyAPI(api_key)
    try:
        me = await api.get_accounts_me()
        print(json.dumps(me, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(inspect_account())
