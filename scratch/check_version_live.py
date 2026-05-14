import httpx
import asyncio

async def test_version(v):
    async with httpx.AsyncClient(base_url="https://cdn.clawroyale.ai/api") as client:
        headers = {"X-Version": v}
        resp = await client.get("/accounts/me", headers=headers)
        return resp.status_code

async def main():
    results = {}
    for v in ["1.6.1", "1.6.2", "1.6.3", "1.6.4", "1.6.5"]:
        status = await test_version(v)
        results[v] = status
        print(f"Version {v}: {status}")
    
    # Check if any didn't return 426
    working = [v for v, s in results.items() if s != 426]
    if working:
        print(f"Working versions: {working}")
    else:
        print("All versions returned 426 or error.")

if __name__ == "__main__":
    asyncio.run(main())
