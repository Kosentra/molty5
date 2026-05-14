import httpx
import asyncio

async def main():
    async with httpx.AsyncClient(base_url="https://cdn.clawroyale.ai/api") as client:
        # Try a versioned request with a known wrong version
        headers = {"X-Version": "1.0.0"}
        resp = await client.get("/accounts/me", headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Headers: {resp.headers}")
        print(f"Body: {resp.text}")
        
        # Check /version again
        v_resp = await client.get("/version")
        print(f"Version Endpoint Status: {v_resp.status_code}")
        print(f"Version Endpoint Body: {v_resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
