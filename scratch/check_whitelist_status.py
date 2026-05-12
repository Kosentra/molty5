import asyncio
import os
from dotenv import load_dotenv
from bot.api_client import MoltyAPI

async def check_whitelist():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("[!] No API_KEY found in .env")
        return

    api = MoltyAPI(api_key)
    try:
        me = await api.get_accounts_me()
        print(f"--- Account Status for {me.get('name', 'Unknown')} ---")
        print(f"Agent ID: {me.get('agentId')}")
        print(f"Wallet Address: {me.get('wallet_address')}")
        print(f"Moltz Balance: {me.get('moltz')}")
        print(f"sMoltz Balance: {me.get('balance')}")
        
        if me.get('wallet_address'):
            print("[OK] Wallet is REGISTERED/ASSOCIATED")
        else:
            print("[WARN] No wallet associated yet.")
            
        try:
            ident = await api.get_identity()
            if ident:
                print(f"[OK] Identity REGISTERED (ERC-8004): Agent #{ident.get('agentId')}")
            else:
                print("[WARN] No identity registered (ERC-8004).")
        except Exception:
            print("[WARN] Could not fetch identity status.")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(check_whitelist())
