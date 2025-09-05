"""
Test with ONLY the nodes shown in the deployment webpage example
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

async def test_minimal_nodes():
    """Test with ONLY the nodes shown in deployment webpage"""
    
    print("🎯 Testing MINIMAL Required Nodes")
    print("="*50)
    print("📋 Using ONLY the nodes from deployment webpage:")
    print("   Node 16: INPUTIMAGE")
    print("   Node 40: FLUXCLIP") 
    print("   Node 41: FLUXT5XXL")
    print("   (Skipping nodes 42, 43, 44 - seed/steps)")
    print()
    
    # Use EXACTLY what the deployment webpage shows
    overrides = {
        "16": {
            "inputs": {
                "image": "ComfyUI_00001_.png"
            }
        },
        "40": {
            "inputs": {
                "value": "epic futuristic spaceship with glowing engines"
            }
        },
        "41": {
            "inputs": {
                "value": "epic futuristic spaceship with glowing engines"
            }
        }
    }
    
    url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/inference"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    payload = {"overrides": overrides}
    
    print(f"🚀 Making request with MINIMAL nodes:")
    print(f"   Nodes: {list(overrides.keys())}")
    print(f"   Format: Exactly from deployment webpage")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url=url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                request_id = result.get('request_id')
                print(f"✅ Request submitted: {request_id}")
                print()
                
                # Monitor for progress
                print(f"⏳ Monitoring (this should work with minimal nodes)...")
                
                for i in range(20):  # Check for 2 minutes
                    await asyncio.sleep(6)
                    
                    # Check status
                    status_url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/status"
                    status_response = await client.get(url=status_url, headers={"Authorization": f"Bearer {API_TOKEN}"})
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get('status')
                        queue_pos = status_data.get('queue_position')
                        
                        print(f"   Check {i+1:2d}: {status:<12} (queue: {queue_pos})")
                        
                        if status == "in_progress":
                            print(f"   🎉 SUCCESS! Request is now PROCESSING!")
                            print(f"   ✅ Minimal nodes approach WORKS!")
                            
                            # Continue monitoring for completion
                            for j in range(10):
                                await asyncio.sleep(10)
                                status_response = await client.get(url=status_url, headers={"Authorization": f"Bearer {API_TOKEN}"})
                                
                                if status_response.status_code == 200:
                                    status_data = status_response.json()
                                    status = status_data.get('status')
                                    print(f"   Progress {j+1}: {status}")
                                    
                                    if status in ["completed", "succeeded"]:
                                        print(f"   🏆 COMPLETED! Generation successful!")
                                        return True
                                    elif status == "failed":
                                        print(f"   ❌ Generation failed")
                                        return False
                            
                            # Cancel to avoid long charges
                            cancel_url = f"{BASE_URL}/prod/v1/deployments/{DEPLOYMENT_ID}/requests/{request_id}/cancel"
                            await client.post(url=cancel_url, headers={"Authorization": f"Bearer {API_TOKEN}"})
                            print(f"   🛑 Cancelled to avoid charges")
                            return True
                            
                        elif status in ["completed", "succeeded"]:
                            print(f"   🏆 COMPLETED! Very fast generation!")
                            return True
                        elif status == "failed":
                            print(f"   ❌ Generation failed")
                            return False
                    else:
                        print(f"   ❌ Status check failed: {status_response.status_code}")
                
                print(f"   ⚠️ Still in queue after 2 minutes")
                return False
                
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    
    print("🔬 MINIMAL NODES TEST")
    print("="*60)
    print("🎯 Testing with ONLY the nodes from deployment webpage")
    print("   This should tell us if extra nodes are causing the issue")
    print()
    
    success = await test_minimal_nodes()
    
    print(f"\n" + "="*60)
    
    if success:
        print(f"🎉 SUCCESS! Minimal nodes approach WORKS!")
        print(f"✅ The issue was sending too many nodes!")
        print(f"🔧 Solution: Use only nodes 16, 40, 41 (skip seed/steps)")
        print()
        print(f"📋 Working configuration:")
        print(f"   - Node 16: image filename")
        print(f"   - Node 40: prompt (FLUXCLIP)")
        print(f"   - Node 41: prompt (FLUXT5XXL)")
        print(f"   - Skip nodes 42,43,44 (use workflow defaults)")
    else:
        print(f"❌ Still not working with minimal nodes")
        print(f"💡 Possible remaining issues:")
        print(f"   1. H200 GPU tier might be having issues")
        print(f"   2. Workflow v2 might be different from our JSON")
        print(f"   3. Account/billing limitations")
        print(f"   4. Deployment might need to be restarted")

if __name__ == "__main__":
    asyncio.run(main())
