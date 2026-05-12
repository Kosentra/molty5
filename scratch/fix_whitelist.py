import asyncio
import os
from dotenv import load_dotenv
from bot.api_client import MoltyAPI, APIError

async def fix_whitelist():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    owner_eoa = os.getenv("OWNER_EOA")
    
    if not api_key or not owner_eoa:
        print("[!] API_KEY or OWNER_EOA missing in .env")
        return

    api = MoltyAPI(api_key)
    try:
        # 1. Associate EOA with account
        print(f"[*] Associating wallet {owner_eoa} with account...")
        try:
            res = await api.put_wallet(owner_eoa)
            print(f"[OK] Wallet associated: {res}")
        except APIError as e:
            print(f"[INFO] Association: {e.message}")

        # 2. Check SC Wallet
        me = await api.get_accounts_me()
        if not me.get("sc_wallet_address"):
            print("[*] Creating SC Wallet (MoltyRoyale Wallet)...")
            try:
                res = await api.create_wallet(owner_eoa)
                print(f"[OK] SC Wallet created: {res}")
            except APIError as e:
                print(f"[INFO] SC Wallet: {e.message}")
        else:
            print(f"[OK] SC Wallet already exists: {me.get('sc_wallet_address')}")

        # 3. Request Whitelist
        print("[*] Requesting whitelist...")
        try:
            res = await api.whitelist_request(owner_eoa)
            print(f"[OK] Whitelist request submitted: {res}")
        except APIError as e:
            print(f"[INFO] Whitelist request: {e.message}")

        # 4. Check Identity
        print("[*] Checking Identity...")
        try:
            ident = await api.get_identity()
            if not ident:
                print("[!] No Identity found. You may need to run 'python bot/setup/identity.py' to anchor NFT.")
            else:
                print(f"[OK] Identity found: {ident}")
        except:
            print("[WARN] Could not fetch identity.")

        print("\n--- Final Status ---")
        me = await api.get_accounts_me()
        print(f"Wallet: {me.get('wallet_address')}")
        print(f"SC Wallet: {me.get('sc_wallet_address')}")
        print(f"Whitelisted: {me.get('readiness', {}).get('whitelistApproved')}")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(fix_whitelist())
