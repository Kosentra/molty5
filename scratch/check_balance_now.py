import asyncio
import os
from bot.api_client import MoltyAPI
from bot.credentials import get_api_key

async def check_balance():
    api_key = get_api_key()
    if not api_key:
        print("API Key not found.")
        return

    api = MoltyAPI(api_key)
    try:
        me = await api.get_accounts_me()
        name = me.get("name", "Unknown")
        balance = me.get("balance", 0)
        print(f"Agent Name: {name}")
        print(f"sMoltz Balance: {balance}")
        
        # Check current games
        current_games = me.get("currentGames", [])
        if current_games:
            print(f"Currently in {len(current_games)} game(s).")
        else:
            print("Not currently in any game.")
            
    except Exception as e:
        print(f"Error fetching account info: {e}")

if __name__ == "__main__":
    asyncio.run(check_balance())
