"""
Test using the STANDARD FLUX workflow format from quickstart guide
to see if our deployment can handle standard node patterns
"""

import os
import sys
import asyncio
import httpx
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables
DEPLOYMENT_ID = "dfcf38cd-0a09-4637-a067-5059dc9e444e"
API_TOKEN = "78356331-a9ec-49c2-a412-59140b32b9b3"
BASE_URL = "https://api.runcomfy.net"

async def test_standard_flux_format():
    """Test using standard FLUX workflow format from quickstart"""
    
    print("🧪 Testing STANDARD FLUX Format")
    print("="*50)
    print("📋 Using STANDARD FLUX node structure from quickstart:")
    print("   Node 6: text prompt")
    print("   Node 25: noise_seed")
    print("   (This might not work but will show compatibility)")
    print()
    
    # Use STANDARD FLUX format from quickstart guide
    overrides = {
        "6": {
            "inputs": {
                "text": "epic futuristic spaceship with glowing engines"
            }
        },
        "25": {
            "inputs": {
                "noise_seed": 123456789
            }
        }
    }
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/inference"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    payload = {"overrides": overrides}
    
    print(f"🚀 Making request with STANDARD FLUX format:")
    print(f"   Nodes: {list(overrides.keys())}")
    print(f"   Format: From RunComfy quickstart guide")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url=url, headers=headers, json=payload)
            
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                request_id = result.get('request_id')
                print(f"✅ Request accepted: {request_id}")
                print(f"   This means deployment can handle different node formats")
                
                # Quick status check
                await asyncio.sleep(3)
                status_response = await client.get(
                    url=f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status",
                    headers={"Authorization": f"Bearer {API_TOKEN}"}
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get('status')
                    print(f"   Status: {status}")
                    
                    if status != "in_queue":
                        print(f"   🎉 DIFFERENT RESULT! Standard format affects processing")
                    else:
                        print(f"   ⚠️ Same issue - still stuck in queue")
                
                # Cancel
                await client.post(
                    url=f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel",
                    headers={"Authorization": f"Bearer {API_TOKEN}"}
                )
                
                return True
                
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                
                if "node" in response.text.lower() or "not found" in response.text.lower():
                    print(f"   ✅ This confirms: deployment expects specific node structure")
                    print(f"   💡 Your custom workflow has different node IDs than standard FLUX")
                
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_deployment_with_no_overrides():
    """Test deployment with NO overrides - use pure defaults"""
    
    print(f"\n🧪 Testing with NO OVERRIDES")
    print("="*50)
    print("📋 Testing with empty overrides - pure workflow defaults")
    print("   This will tell us if the deployment/workflow itself works")
    print()
    
    # Empty overrides - use workflow defaults
    payload = {"overrides": {}}
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/inference"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url=url, headers=headers, json=payload)
            
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                request_id = result.get('request_id')
                print(f"✅ Request accepted: {request_id}")
                print(f"   Testing if deployment processes with NO overrides...")
                
                # Monitor for a short time
                for i in range(10):
                    await asyncio.sleep(5)
                    
                    status_response = await client.get(
                        url=f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status",
                        headers={"Authorization": f"Bearer {API_TOKEN}"}
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get('status')
                        queue_pos = status_data.get('queue_position')
                        
                        print(f"   Check {i+1}: {status} (queue: {queue_pos})")
                        
                        if status != "in_queue":
                            print(f"   🎉 SUCCESS! Default workflow WORKS!")
                            print(f"   💡 Issue is with our overrides, not the deployment")
                            
                            # Cancel and return
                            await client.post(
                                url=f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel",
                                headers={"Authorization": f"Bearer {API_TOKEN}"}
                            )
                            return True
                
                print(f"   ⚠️ Still stuck in queue even with no overrides")
                print(f"   💡 This suggests deployment/workflow issue, not our code")
                
                # Cancel
                await client.post(
                    url=f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel",
                    headers={"Authorization": f"Bearer {API_TOKEN}"}
                )
                
                return False
                
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    """Main diagnostic function"""
    
    print("🔬 WORKFLOW FORMAT DIAGNOSIS")
    print("="*60)
    print("🎯 Testing different formats to identify the root issue")
    print()
    
    # Test 1: Standard FLUX format
    standard_result = await test_standard_flux_format()
    
    # Test 2: No overrides at all
    default_result = await test_deployment_with_no_overrides()
    
    print(f"\n" + "="*60)
    print("📊 DIAGNOSIS RESULTS")
    print("="*60)
    
    if default_result:
        print(f"🎉 BREAKTHROUGH! Default workflow WORKS!")
        print(f"✅ The deployment itself is functional")
        print(f"❌ The issue is with our specific overrides")
        print()
        print(f"💡 Next steps:")
        print(f"   1. Check the actual workflow JSON for correct node IDs")
        print(f"   2. Your workflow v2 might have different nodes than v1")
        print(f"   3. Download the workflow API JSON from deployment page")
        print(f"   4. Match our overrides to the actual node structure")
        
    elif standard_result and not default_result:
        print(f"🤔 MIXED RESULTS!")
        print(f"✅ Standard format accepted but doesn't process")
        print(f"❌ Default workflow also doesn't process")
        print(f"💡 Suggests deployment/GPU/resource issue")
        
    else:
        print(f"❌ DEPLOYMENT ISSUE!")
        print(f"❌ Neither our format nor defaults work")
        print(f"💡 Possible issues:")
        print(f"   1. Deployment needs to be restarted")
        print(f"   2. GPU tier (H200) has issues")
        print(f"   3. Workflow v2 has problems")
        print(f"   4. Account/billing limitations")
        print()
        print(f"🔧 Suggested actions:")
        print(f"   1. Try restarting the deployment")
        print(f"   2. Switch to a different GPU tier (A6000)")
        print(f"   3. Deploy a fresh standard RunComfy/FLUX workflow")
        print(f"   4. Check account billing/limits")

if __name__ == "__main__":
    asyncio.run(main())
