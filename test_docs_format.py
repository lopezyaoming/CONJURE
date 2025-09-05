"""
Test script that exactly matches the RunComfy documentation format
Based on the examples in newruncomfydocs.txt
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

async def test_docs_format():
    """Test using the exact format from RunComfy documentation"""
    
    print("🔍 Testing EXACT RunComfy Documentation Format")
    print("="*60)
    print("📋 Based on examples from newruncomfydocs.txt")
    print()
    
    # Create simple test image
    test_image_path = Path("test_image.png")
    if not test_image_path.exists():
        from PIL import Image
        img = Image.new('RGB', (512, 512), 'red')
        img.save(test_image_path)
        print(f"✅ Created test image: {test_image_path}")
    
    # Encode image exactly like the docs show
    with open(test_image_path, 'rb') as f:
        image_data = f.read()
    
    base64_data = base64.b64encode(image_data).decode('utf-8')
    data_uri = f"data:image/png;base64,{base64_data}"
    
    print(f"🖼️ Image encoded: {len(base64_data)} chars")
    
    # Test 1: Try with minimal overrides (like docs example)
    print(f"\n🧪 Test 1: Minimal overrides (following docs pattern)")
    
    # Use the EXACT format from docs
    overrides = {
        "16": {
            "inputs": {
                "image": data_uri
            }
        },
        "40": {
            "inputs": {
                "value": "red cube test"
            }
        }
    }
    
    # Make request exactly like the docs
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/inference"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    payload = {
        "overrides": overrides
    }
    
    print(f"🚀 Making request to: {url}")
    print(f"🔧 Headers: {headers}")
    print(f"📦 Payload overrides keys: {list(overrides.keys())}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url=url,
                headers=headers,
                json=payload
            )
            
            print(f"📡 Response status: {response.status_code}")
            print(f"📄 Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ SUCCESS! Request submitted:")
                print(f"   Request ID: {result.get('request_id')}")
                print(f"   Status URL: {result.get('status_url')}")
                
                # Try to check status
                request_id = result.get('request_id')
                if request_id:
                    await test_status_check(request_id)
                
                return True
                
            else:
                print(f"❌ Request failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                
                # Try different authorization formats
                await test_auth_formats(url, payload)
                
                return False
                
    except Exception as e:
        print(f"❌ Request exception: {e}")
        return False

async def test_status_check(request_id: str):
    """Test status checking with exact docs format"""
    
    print(f"\n🔍 Testing status check for: {request_id}")
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url=url, headers=headers)
            
            print(f"📡 Status response: {response.status_code}")
            
            if response.status_code == 200:
                status_data = response.json()
                print(f"✅ Status check successful:")
                print(f"   Status: {status_data.get('status')}")
                print(f"   Queue position: {status_data.get('queue_position')}")
            else:
                print(f"❌ Status check failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Status check exception: {e}")

async def test_auth_formats(url: str, payload: dict):
    """Test different authorization header formats"""
    
    print(f"\n🧪 Testing different authorization formats...")
    
    auth_formats = [
        f"Bearer {API_TOKEN}",
        f"Token {API_TOKEN}",
        f"{API_TOKEN}",
        f"Bearer token={API_TOKEN}",
        f"token={API_TOKEN}",
    ]
    
    for i, auth_format in enumerate(auth_formats, 1):
        print(f"\n   Test {i}: Authorization: {auth_format[:20]}...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_format
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url=url,
                    headers=headers,
                    json=payload
                )
                
                print(f"      Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"      ✅ SUCCESS with format: {auth_format}")
                    result = response.json()
                    print(f"      Request ID: {result.get('request_id')}")
                    return True
                elif response.status_code != 403:
                    print(f"      🔍 Different error: {response.text[:100]}...")
                    
        except Exception as e:
            print(f"      ❌ Exception: {str(e)[:50]}...")
    
    return False

async def main():
    """Main test function"""
    
    print("🎯 This test uses the EXACT format from RunComfy documentation")
    print("   to identify any differences between docs and our implementation")
    print()
    
    success = await test_docs_format()
    
    print(f"\n" + "="*60)
    
    if success:
        print("🎉 SUCCESS! Documentation format works correctly!")
        print("   The issue may be in our node mapping or other details.")
    else:
        print("❌ Documentation format also fails!")
        print("   This suggests an authentication or API endpoint issue.")
        print()
        print("🔍 Possible issues:")
        print("   1. API token might be expired or invalid")
        print("   2. Deployment might be in wrong state")
        print("   3. API endpoint might have changed")
        print("   4. Account/billing issues")
    
    # Clean up
    test_image_path = Path("test_image.png")
    if test_image_path.exists():
        test_image_path.unlink()

if __name__ == "__main__":
    asyncio.run(main())
