import asyncio
import httpx

KEYS = [
    "mr_live_6j03kxXGtvyhcGCWGpyzwTHWYJvjEcW-",
    "mr_live_IpoTaHiZKck6m48Il-bhd2gbrwp-GrlM"
]

API_URL = "https://cdn.moltyroyale.com/api"

async def check_key(api_key):
    print(f"Checking key: {api_key}")
    headers = {
        "X-API-Key": api_key,
        "X-Version": "1.6.1"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_URL}/accounts/me", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", resp.json())
                print(f"  Name: {data.get('name')}")
                print(f"  Wallet: {data.get('walletAddress')}")
                print(f"  Readiness: {data.get('readiness')}")
            else:
                print(f"  Error {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"  Error: {e}")

async def main():
    for key in KEYS:
        await check_key(key)
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
