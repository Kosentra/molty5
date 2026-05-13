
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("API_KEY")
    url = "https://cdn.clawroyale.ai/api/accounts/me"
    headers = {
        "X-Version": "1.6.2",
        "Authorization": f"mr-auth {api_key}"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test())
