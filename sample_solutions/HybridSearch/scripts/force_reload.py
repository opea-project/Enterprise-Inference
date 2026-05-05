import httpx
import asyncio
import json

RETRIEVAL_URL = "http://localhost:8002"
GATEWAY_URL = "http://localhost:8000"

async def verify_reload():
    async with httpx.AsyncClient() as client:
        print(f"1. Triggering reload at {RETRIEVAL_URL}/api/v1/reload...")
        try:
            response = await client.post(f"{RETRIEVAL_URL}/api/v1/reload")
            if response.status_code == 200:
                print("Reload successful!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"Reload failed: {response.status_code} - {response.text}")
                return
        except Exception as e:
            print(f"Failed to connect to retrieval service: {e}")
            return

        print("\n2. Testing Product Search...")
        try:
            response = await client.post(
                f"{GATEWAY_URL}/api/v1/search",
                json={"query": "product", "limit": 5}
            )
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                print(f"Found {len(results)} products.")
                if results:
                    print("First product:", results[0]['name'])
                    print("SUCCESS: Products are searchable!")
                else:
                    print("FAILURE: No products found after reload.")
            else:
                print(f"Search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Failed to connect to gateway: {e}")

if __name__ == "__main__":
    asyncio.run(verify_reload())
