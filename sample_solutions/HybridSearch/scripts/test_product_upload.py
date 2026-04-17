import asyncio
import httpx
import json
import os

# Configuration
API_URL = "http://localhost:8004"  # Ingestion service

async def verify_upload_fix():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("1. Clearing product catalog...")
        response = await client.delete(f"{API_URL}/api/v1/products/clear")
        if response.status_code != 200:
            print(f"Failed to clear products: {response.text}")
            return
        print("Products cleared.")

        print("\n2. Uploading Product Catalog (should auto-process)...")
        # Create a dummy CSV file with standard headers
        with open("test_products.csv", "w") as f:
            f.write("id,name,description,category,price,rating,review_count,image_url,brand\n")
            f.write("1,Test Product,A test product.,Test Category,10.00,4.5,10,http://example.com/image.jpg,Test Brand\n")
        
        files = {'file': ('test_products.csv', open('test_products.csv', 'rb'), 'text/csv')}
        response = await client.post(f"{API_URL}/api/v1/products/upload", files=files)
        
        if response.status_code != 202:
            print(f"Failed to upload products: {response.text}")
            return
            
        data = response.json()
        job_id = data['job_id']
        status = data['status']
        requires_confirmation = data['requires_confirmation']
        
        print(f"Upload response status: {status}")
        print(f"Requires confirmation: {requires_confirmation}")
        
        if requires_confirmation:
            print("FAILURE: Upload still requires confirmation for standard headers!")
            return
            
        if status != "processing":
            print(f"FAILURE: Status should be 'processing', got '{status}'")
            return

        print(f"Job started: {job_id}")
        
        # Poll for completion
        print("Waiting for processing...")
        for _ in range(10):
            await asyncio.sleep(1)
            response = await client.get(f"{API_URL}/api/v1/products/status/{job_id}")
            job_status = response.json()
            print(f"Job status: {job_status['status']} ({job_status['products_processed']}/{job_status['products_total']})")
            
            if job_status['status'] == 'complete':
                print("SUCCESS: Product upload auto-processed successfully!")
                break
            if job_status['status'] == 'error':
                print(f"FAILURE: Job failed with error: {job_status['errors']}")
                break
        else:
            print("FAILURE: Timeout waiting for processing")

        # Cleanup
        os.remove("test_products.csv")

if __name__ == "__main__":
    asyncio.run(verify_upload_fix())
