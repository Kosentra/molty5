
import asyncio
import httpx
from bot.config import API_BASE

async def check_version():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_BASE}/version")
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_version())
