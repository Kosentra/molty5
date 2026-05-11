
import httpx
import asyncio

token = "88b80fc0-1307-447c-8eef-f25c57e09133"
url = "https://backboard.railway.com/graphql/v2"

query = """
query {
  projects {
    edges {
      node {
        id
        name
      }
    }
  }
}
"""

async def list_projects():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"query": query},
            headers={"Authorization": f"Bearer {token}"}
        )
        print(resp.text)

if __name__ == "__main__":
    asyncio.run(list_projects())
