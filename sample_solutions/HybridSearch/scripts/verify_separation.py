import asyncio
import httpx
import json
import os

# Configuration
API_URL = "http://localhost:8004"  # Ingestion service
RETRIEVAL_URL = "http://localhost:8002"  # Retrieval service

async def verify_separation():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("1. Clearing all indexes...")
        response = await client.delete(f"{API_URL}/api/v1/documents/clear-all")
        if response.status_code != 200:
            print(f"Failed to clear indexes: {response.text}")
            return
        print("Indexes cleared.")

        print("\n2. Uploading Document (California Drivers License)...")
        # Create a dummy PDF file
        with open("drivers_license.txt", "w") as f:
            f.write("The California Drivers License Handbook covers rules of the road, traffic signs, and safe driving practices.")
        
        files = {'file': ('drivers_license.txt', open('drivers_license.txt', 'rb'), 'text/plain')}
        response = await client.post(f"{API_URL}/api/v1/documents/upload", files=files)
        if response.status_code != 202:
            print(f"Failed to upload document: {response.text}")
            return
        doc_id = response.json()['document_id']
        print(f"Document uploaded: {doc_id}")
        
        # Wait for processing
        print("Waiting for document processing...")
        await asyncio.sleep(5)

        print("\n3. Uploading Product Catalog (Shoes)...")
        # Create a dummy CSV file
        with open("products.csv", "w") as f:
            f.write("id,name,description,category,price\n")
            f.write("1,Running Shoes,High performance running shoes for athletes.,Footwear,99.99\n")
            f.write("2,Hiking Boots,Durable boots for rough terrain.,Footwear,129.99\n")
        
        files = {'file': ('products.csv', open('products.csv', 'rb'), 'text/csv')}
        response = await client.post(f"{API_URL}/api/v1/products/upload", files=files)
        if response.status_code != 202:
            print(f"Failed to upload products: {response.text}")
            return
        job_data = response.json()
        job_id = job_data['job_id']
        print(f"Product upload job started: {job_id}")
        
        # Confirm mapping
        mapping = {
            "name": "Product Catalog",
            "id_field": "id",
            "name_field": "name",
            "description_field": "description",
            "category_field": "category",
            "price_field": "price"
        }
        
        response = await client.post(
            f"{API_URL}/api/v1/products/confirm",
            data={
                "job_id": job_id,
                "field_mapping": json.dumps(mapping)
            }
        )
        if response.status_code != 202:
            print(f"Failed to confirm mapping: {response.text}")
            return
        print("Product mapping confirmed.")
        
        # Wait for processing
        print("Waiting for product processing...")
        await asyncio.sleep(5)
        
        # Reload indexes
        print("\n4. Reloading indexes...")
        await client.post(f"{RETRIEVAL_URL}/api/v1/reload")
        
        print("\n5. Verifying Document Search (Query: 'shoes')...")
        # Should NOT find products
        response = await client.post(
            f"{RETRIEVAL_URL}/api/v1/retrieve/hybrid",
            json={
                "query": "shoes",
                "top_k_candidates": 10,
                "top_k_fusion": 5,
                "top_k_final": 5
            }
        )
        results = response.json()['results']
        print(f"Found {len(results)} results.")
        for res in results:
            print(f" - {res.get('text', '')[:50]}... (Source: {res.get('metadata', {}).get('filename', 'Unknown')})")
            if "Running Shoes" in res.get('text', ''):
                print("FAILURE: Product found in document search!")
                return

        print("\n6. Verifying Product Search (Query: 'license')...")
        # Should NOT find documents
        response = await client.post(
            f"{RETRIEVAL_URL}/api/v1/search/products",
            json={
                "query_text": "license",
                "top_k": 5
            }
        )
        results = response.json()['results']
        print(f"Found {len(results)} results.")
        for res in results:
             print(f" - {res.get('name', '')}: {res.get('description', '')[:50]}...")
             if "California Drivers License" in res.get('description', ''):
                 print("FAILURE: Document found in product search!")
                 return

        print("\nSUCCESS: Contexts are properly separated!")

        # Cleanup
        os.remove("drivers_license.txt")
        os.remove("products.csv")

if __name__ == "__main__":
    asyncio.run(verify_separation())
