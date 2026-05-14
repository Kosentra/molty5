import httpx
import asyncio

API_KEY = "mr_live_6j03kxXGtvyhcGCWGpyzwTHWYJvjEcW-"

async def test_version(v):
    async with httpx.AsyncClient(base_url="https://cdn.clawroyale.ai/api") as client:
        headers = {
            "X-Version": v,
            "Authorization": f"mr-auth {API_KEY}"
        }
        resp = await client.get("/accounts/me", headers=headers)
        return resp.status_code, resp.text

async def main():
    for v in ["1.6.1", "1.6.2", "1.6.3", "1.6.4", "1.6.5"]:
        status, text = await test_version(v)
        print(f"Version {v} -> Status: {status}")
        if status == 426:
            print(f"   Mismatch detected!")
        elif status == 200:
            print(f"   Working!")
        else:
            print(f"   Body: {text[:100]}")

if __name__ == "__main__":
    asyncio.run(main())
