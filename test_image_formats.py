"""
Test different image input formats to find what works
"""

import os
import sys
import asyncio
import httpx
import base64
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables
DEPLOYMENT_ID = "dfcf38cd-0a09-4637-a067-5059dc9e444e"
API_TOKEN = "78356331-a9ec-49c2-a412-59140b32b9b3"
BASE_URL = "https://api.runcomfy.net"

async def test_image_format(test_name: str, image_value: str, description: str):
    """Test specific image format"""
    
    print(f"\n🧪 {test_name}")
    print(f"   Format: {description}")
    print(f"   Value length: {len(str(image_value))} chars")
    
    # Test with minimal working nodes
    overrides = {
        "16": {"inputs": {"image": image_value}},
        "40": {"inputs": {"value": "test prompt"}}
    }
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/inference"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    payload = {"overrides": overrides}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url=url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                request_id = result.get('request_id')
                print(f"   ✅ SUCCESS: {request_id}")
                
                # Check status multiple times to see if it progresses
                for i in range(5):
                    await asyncio.sleep(3)
                    status = await check_status(request_id)
                    print(f"   Check {i+1}: {status}")
                    
                    if status and status != "in_queue":
                        print(f"   🎉 PROGRESS! Status changed to: {status}")
                        await cancel_request(request_id)
                        return True
                
                print(f"   ⚠️ Still in queue after 15 seconds")
                await cancel_request(request_id)
                return "queue_stuck"
                
            else:
                print(f"   ❌ FAILED: {response.status_code}")
                print(f"   Error: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"   ❌ EXCEPTION: {str(e)[:100]}...")
        return False

async def check_status(request_id: str):
    """Check request status"""
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url=url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('status')
            else:
                return f"error_{response.status_code}"
                
    except Exception:
        return "exception"

async def cancel_request(request_id: str):
    """Cancel request"""
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url=url, headers=headers)
    except:
        pass

async def main():
    """Test different image input formats"""
    
    print("🔬 IMAGE FORMAT TESTING")
    print("="*50)
    print("🎯 Testing different ways to provide image input")
    print("   Based on your RunComfy endpoint vs documentation")
    print()
    
    # Create test images of different sizes
    test_image_small = Path("test_small.png")
    test_image_large = Path("test_large.png")
    
    # Small image (64x64)
    if not test_image_small.exists():
        from PIL import Image
        img = Image.new('RGB', (64, 64), 'red')
        img.save(test_image_small)
    
    # Large image (1024x1024) 
    if not test_image_large.exists():
        from PIL import Image
        img = Image.new('RGB', (1024, 1024), 'blue')
        img.save(test_image_large)
    
    # Test cases
    test_cases = []
    
    # 1. Filename string (from your endpoint)
    test_cases.append({
        "name": "Test 1: Filename String",
        "value": "ComfyUI_00001_.png",
        "description": "Simple filename (from your endpoint example)"
    })
    
    # 2. Small Base64 data URI
    with open(test_image_small, 'rb') as f:
        small_data = f.read()
    small_b64 = base64.b64encode(small_data).decode('utf-8')
    small_uri = f"data:image/png;base64,{small_b64}"
    
    test_cases.append({
        "name": "Test 2: Small Base64 Data URI",
        "value": small_uri,
        "description": f"64x64 image as Base64 ({len(small_b64)} chars)"
    })
    
    # 3. Large Base64 data URI (what we were using)
    with open(test_image_large, 'rb') as f:
        large_data = f.read()
    large_b64 = base64.b64encode(large_data).decode('utf-8')
    large_uri = f"data:image/png;base64,{large_b64}"
    
    test_cases.append({
        "name": "Test 3: Large Base64 Data URI",
        "value": large_uri,
        "description": f"1024x1024 image as Base64 ({len(large_b64)} chars)"
    })
    
    # 4. Public URL (if we had one)
    test_cases.append({
        "name": "Test 4: Public URL",
        "value": "https://picsum.photos/512/512",
        "description": "Public URL to random image"
    })
    
    # Run tests
    results = []
    
    print(f"⏰ Note: Setting minimum instances to 1 should help with queue processing")
    print()
    
    for test_case in test_cases:
        result = await test_image_format(
            test_case["name"],
            test_case["value"], 
            test_case["description"]
        )
        results.append((test_case["name"], result))
        
        await asyncio.sleep(2)  # Delay between tests
    
    # Summary
    print(f"\n" + "="*50)
    print("📊 IMAGE FORMAT TEST RESULTS")
    print("="*50)
    
    working_formats = []
    stuck_formats = []
    failed_formats = []
    
    for test_name, result in results:
        if result is True:
            print(f"✅ WORKING: {test_name}")
            working_formats.append(test_name)
        elif result == "queue_stuck":
            print(f"🔄 QUEUE STUCK: {test_name}")
            stuck_formats.append(test_name)
        else:
            print(f"❌ FAILED: {test_name}")
            failed_formats.append(test_name)
    
    print(f"\n🎯 CONCLUSIONS:")
    
    if working_formats:
        print(f"✅ WORKING FORMATS:")
        for fmt in working_formats:
            print(f"   - {fmt}")
        print(f"   → Use this format in production!")
    
    if stuck_formats:
        print(f"🔄 FORMATS THAT GET STUCK IN QUEUE:")
        for fmt in stuck_formats:
            print(f"   - {fmt}")
        print(f"   → These formats are accepted but don't process")
    
    if failed_formats:
        print(f"❌ FORMATS THAT FAIL:")
        for fmt in failed_formats:
            print(f"   - {fmt}")
        print(f"   → These formats are rejected by the API")
    
    # Clean up
    for img in [test_image_small, test_image_large]:
        if img.exists():
            img.unlink()

if __name__ == "__main__":
    asyncio.run(main())
