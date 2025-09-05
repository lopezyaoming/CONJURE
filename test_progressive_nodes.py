"""
Progressive node testing - add one node at a time to find the problematic one
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

async def test_node_combination(test_name: str, overrides: dict):
    """Test a specific node combination"""
    
    print(f"\n🧪 {test_name}")
    print(f"   Nodes: {list(overrides.keys())}")
    
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
                
                # Quick status check
                await check_status(request_id)
                
                # Cancel to avoid charges
                await cancel_request(request_id)
                
                return True
            else:
                print(f"   ❌ FAILED: {response.status_code}")
                print(f"   Error: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"   ❌ EXCEPTION: {str(e)[:100]}...")
        return False

async def check_status(request_id: str):
    """Quick status check"""
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url=url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                queue_pos = data.get('queue_position')
                print(f"   📊 Status: {status} (queue: {queue_pos})")
            else:
                print(f"   ❌ Status check failed: {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Status exception: {str(e)[:50]}...")

async def cancel_request(request_id: str):
    """Cancel request to avoid charges"""
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url=url, headers=headers)
            print(f"   🛑 Cancelled")
    except:
        pass  # Don't worry if cancel fails

async def main():
    """Progressive testing to find the problematic node"""
    
    print("🔬 PROGRESSIVE NODE TESTING")
    print("="*50)
    print("🎯 Adding one node at a time to identify the issue")
    print()
    
    # Create test image
    test_image_path = Path("test_image.png")
    if not test_image_path.exists():
        from PIL import Image
        img = Image.new('RGB', (512, 512), 'red')
        img.save(test_image_path)
    
    # Encode image
    with open(test_image_path, 'rb') as f:
        image_data = f.read()
    base64_data = base64.b64encode(image_data).decode('utf-8')
    data_uri = f"data:image/png;base64,{base64_data}"
    
    # Progressive tests
    test_cases = [
        {
            "name": "Test 1: Just Image (Node 16) - KNOWN WORKING",
            "overrides": {
                "16": {"inputs": {"image": data_uri}}
            }
        },
        {
            "name": "Test 2: Image + FLUXCLIP (Nodes 16, 40) - KNOWN WORKING", 
            "overrides": {
                "16": {"inputs": {"image": data_uri}},
                "40": {"inputs": {"value": "test prompt"}}
            }
        },
        {
            "name": "Test 3: + FLUXT5XXL (Nodes 16, 40, 41)",
            "overrides": {
                "16": {"inputs": {"image": data_uri}},
                "40": {"inputs": {"value": "test prompt"}},
                "41": {"inputs": {"value": "test prompt"}}
            }
        },
        {
            "name": "Test 4: + NOISESEED (Nodes 16, 40, 41, 42)",
            "overrides": {
                "16": {"inputs": {"image": data_uri}},
                "40": {"inputs": {"value": "test prompt"}},
                "41": {"inputs": {"value": "test prompt"}},
                "42": {"inputs": {"value": 12345}}
            }
        },
        {
            "name": "Test 5: + STEPSPARTPACKER (Nodes 16, 40, 41, 42, 43)",
            "overrides": {
                "16": {"inputs": {"image": data_uri}},
                "40": {"inputs": {"value": "test prompt"}},
                "41": {"inputs": {"value": "test prompt"}},
                "42": {"inputs": {"value": 12345}},
                "43": {"inputs": {"value": 50}}
            }
        },
        {
            "name": "Test 6: + STEPSFLUX (ALL NODES - Complete Override)",
            "overrides": {
                "16": {"inputs": {"image": data_uri}},
                "40": {"inputs": {"value": "test prompt"}},
                "41": {"inputs": {"value": "test prompt"}},
                "42": {"inputs": {"value": 12345}},
                "43": {"inputs": {"value": 50}},
                "44": {"inputs": {"value": 20}}
            }
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        success = await test_node_combination(
            test_case["name"], 
            test_case["overrides"]
        )
        results.append((test_case["name"], success))
        
        if not success:
            print(f"\n🚨 FOUND THE ISSUE!")
            print(f"   Problem node combination: {list(test_case['overrides'].keys())}")
            break
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Summary
    print(f"\n" + "="*50)
    print("📊 PROGRESSIVE TEST RESULTS")
    print("="*50)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    # Find the problematic node
    last_working = None
    first_failing = None
    
    for i, (test_name, success) in enumerate(results):
        if success:
            last_working = i
        else:
            first_failing = i
            break
    
    if first_failing is not None and last_working is not None:
        print(f"\n🎯 DIAGNOSIS:")
        print(f"   ✅ Last working: {results[last_working][0]}")
        print(f"   ❌ First failing: {results[first_failing][0]}")
        
        # Identify the problematic node
        working_nodes = set(test_cases[last_working]["overrides"].keys())
        failing_nodes = set(test_cases[first_failing]["overrides"].keys())
        new_node = failing_nodes - working_nodes
        
        if new_node:
            problem_node = list(new_node)[0]
            print(f"   🚨 PROBLEM NODE: {problem_node}")
            
            # Suggest fixes based on node type
            node_names = {
                "41": "FLUXT5XXL (T5XXL text encoder)",
                "42": "NOISESEED (Random seed)",
                "43": "STEPSPARTPACKER (PartPacker steps)",
                "44": "STEPSFLUX (FLUX inference steps)"
            }
            
            if problem_node in node_names:
                print(f"   📋 Node type: {node_names[problem_node]}")
                
                if problem_node == "41":
                    print(f"   💡 Possible fixes for node 41:")
                    print(f"      - Try 'text' instead of 'value'")
                    print(f"      - Try 't5xxl' instead of 'value'")
                    print(f"      - Node might not be needed if 40 works")
                
    else:
        print(f"\n✅ ALL TESTS PASSED!")
        print(f"   The complete node combination works correctly.")
        print(f"   The issue must be elsewhere in the original code.")
    
    # Clean up
    if test_image_path.exists():
        test_image_path.unlink()

if __name__ == "__main__":
    asyncio.run(main())
