"""
Deployment Diagnostic Tool
Validates the RunComfy deployment configuration and identifies issues.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables
os.environ["RUNCOMFY_API_TOKEN"] = "78356331-a9ec-49c2-a412-59140b32b9b3"
os.environ["RUNCOMFY_USER_ID"] = "0cb54d51-f01e-48e1-ae7b-28d1c21bc947"
os.environ["RUNCOMFY_DEPLOYMENT_ID"] = "dfcf38cd-0a09-4637-a067-5059dc9e444e"

async def test_minimal_request():
    """Test with the absolute minimum valid payload"""
    
    print("🧪 Testing Minimal Request")
    print("="*40)
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        # Test 1: Submit with only required node (try just one input)
        print(f"\n🧪 Test 1: Single node input (image only)")
        
        # Create minimal test image
        from PIL import Image
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img = Image.new('RGB', (64, 64), 'white')  # Tiny image
            img.save(tmp.name)
            test_image_path = tmp.name
        
        # Try with just the image input
        minimal_overrides = {
            "16": {  # INPUTIMAGE only
                "inputs": {
                    "image": client.encode_image_to_base64(test_image_path)
                }
            }
        }
        
        endpoint = f"/prod/v1/deployments/{client.deployment_id}/inference"
        payload = {"overrides": minimal_overrides}
        
        print(f"🔧 Sending minimal payload: {list(minimal_overrides.keys())}")
        
        response = await client._make_request(
            method="POST",
            endpoint=endpoint,
            json_data=payload
        )
        
        request_id = response["request_id"]
        print(f"✅ Minimal request accepted: {request_id}")
        
        # Check if it progresses
        for i in range(5):
            await asyncio.sleep(2)
            status = await client.get_request_status(request_id)
            print(f"   Check {i+1}: {status.status.value} (queue: {status.queue_position})")
            
            if status.status.value != "in_queue":
                print(f"   🎯 Status changed! This suggests the deployment is working.")
                break
        else:
            print(f"   ⚠️ Still in queue - trying next test...")
        
        # Cancel
        await client.cancel_request(request_id)
        
        # Test 2: Try with different node combinations
        print(f"\n🧪 Test 2: Different node combinations")
        
        test_cases = [
            {
                "name": "Text only (CLIP)",
                "nodes": {
                    "40": {"inputs": {"text": "test"}}
                }
            },
            {
                "name": "Text only (T5XXL)", 
                "nodes": {
                    "41": {"inputs": {"text": "test"}}
                }
            },
            {
                "name": "Seed only",
                "nodes": {
                    "42": {"inputs": {"noise_seed": 123}}
                }
            },
            {
                "name": "Steps only (FLUX)",
                "nodes": {
                    "44": {"inputs": {"num_inference_steps": 1}}
                }
            }
        ]
        
        for test_case in test_cases:
            print(f"\n   Testing: {test_case['name']}")
            
            try:
                response = await client._make_request(
                    method="POST",
                    endpoint=endpoint,
                    json_data={"overrides": test_case["nodes"]}
                )
                
                req_id = response["request_id"]
                print(f"   ✅ Accepted: {req_id}")
                
                # Quick status check
                await asyncio.sleep(1)
                status = await client.get_request_status(req_id)
                print(f"   Status: {status.status.value}")
                
                # Cancel immediately
                await client.cancel_request(req_id)
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Clean up
        os.unlink(test_image_path)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_deployment_info():
    """Try to get deployment information if available"""
    
    print(f"\n🔍 Checking Deployment Information")
    print("="*40)
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        # Try different endpoints that might give us deployment info
        test_endpoints = [
            f"/prod/v1/deployments/{client.deployment_id}",
            f"/prod/v1/deployments/{client.deployment_id}/info",
            f"/prod/v1/deployments/{client.deployment_id}/status",
            f"/prod/v1/deployments/{client.deployment_id}/workflow",
            f"/prod/v1/deployments",
            f"/prod/v1/users/{client.user_id}/deployments"
        ]
        
        for endpoint in test_endpoints:
            try:
                print(f"\n🔍 Trying: {endpoint}")
                response = await client._make_request(
                    method="GET",
                    endpoint=endpoint
                )
                print(f"✅ Success! Response keys: {list(response.keys()) if isinstance(response, dict) else type(response)}")
                
                # If we get deployment info, show it
                if isinstance(response, dict):
                    if "workflow" in response:
                        print(f"   Workflow found in response")
                    if "nodes" in response:
                        print(f"   Nodes found: {list(response['nodes'].keys()) if isinstance(response['nodes'], dict) else 'Unknown format'}")
                    if "status" in response:
                        print(f"   Deployment status: {response['status']}")
                    if "id" in response:
                        print(f"   Deployment ID: {response['id']}")
                
            except Exception as e:
                if "404" in str(e):
                    print(f"   404 Not Found")
                elif "403" in str(e):
                    print(f"   403 Forbidden")
                else:
                    print(f"   Error: {e}")
        
    except Exception as e:
        print(f"❌ Failed to check deployment info: {e}")

async def test_alternative_nodes():
    """Test if the node IDs might be wrong"""
    
    print(f"\n🧪 Testing Alternative Node IDs")
    print("="*40)
    
    # Maybe the node IDs are different - let's try common alternatives
    alternative_mappings = [
        # Original mapping
        {"16": "image", "40": "text", "41": "text", "42": "noise_seed", "43": "num_steps", "44": "num_inference_steps"},
        
        # Try string node IDs  
        {"input_image": "image", "flux_clip": "text", "flux_t5": "text", "noise_seed": "noise_seed", "steps_partpacker": "num_steps", "steps_flux": "num_inference_steps"},
        
        # Try sequential numbers
        {"1": "image", "2": "text", "3": "text", "4": "noise_seed", "5": "num_steps", "6": "num_inference_steps"},
        
        # Try different input field names
        {"16": "input_image", "40": "prompt", "41": "prompt", "42": "seed", "43": "steps", "44": "inference_steps"},
    ]
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        client = ServerlessRunComfyClient()
        
        # Create tiny test image
        from PIL import Image
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img = Image.new('RGB', (32, 32), 'red')
            img.save(tmp.name)
            test_image_path = tmp.name
        
        encoded_image = client.encode_image_to_base64(test_image_path)
        
        for i, mapping in enumerate(alternative_mappings):
            print(f"\n   🧪 Testing mapping {i+1}: {list(mapping.keys())}")
            
            # Build test overrides based on mapping
            overrides = {}
            for node_id, input_type in mapping.items():
                if input_type == "image":
                    overrides[node_id] = {"inputs": {"image": encoded_image}}
                elif input_type in ["input_image"]:
                    overrides[node_id] = {"inputs": {"input_image": encoded_image}}
                elif input_type in ["text", "prompt"]:
                    overrides[node_id] = {"inputs": {input_type: "test cube"}}
                elif input_type in ["noise_seed", "seed"]:
                    overrides[node_id] = {"inputs": {input_type: 123}}
                elif input_type in ["num_steps", "steps"]:
                    overrides[node_id] = {"inputs": {input_type: 1}}
                elif input_type in ["num_inference_steps", "inference_steps"]:
                    overrides[node_id] = {"inputs": {input_type: 1}}
            
            try:
                endpoint = f"/prod/v1/deployments/{client.deployment_id}/inference"
                response = await client._make_request(
                    method="POST",
                    endpoint=endpoint,
                    json_data={"overrides": overrides}
                )
                
                req_id = response["request_id"]
                print(f"   ✅ Accepted: {req_id}")
                
                # Quick check if it progresses
                await asyncio.sleep(3)
                status = await client.get_request_status(req_id)
                print(f"   Status: {status.status.value} (queue: {status.queue_position})")
                
                if status.status.value != "in_queue":
                    print(f"   🎉 PROGRESS! This mapping might be correct!")
                    print(f"   Working mapping: {mapping}")
                
                await client.cancel_request(req_id)
                
            except Exception as e:
                print(f"   ❌ Failed: {str(e)[:100]}...")
        
        os.unlink(test_image_path)
        
    except Exception as e:
        print(f"❌ Alternative node test failed: {e}")

async def main():
    """Main diagnostic function"""
    
    print("🔬 RUNCOMFY DEPLOYMENT DIAGNOSTIC")
    print("="*60)
    print("🎯 This will help identify why requests get stuck in queue")
    print()
    
    # Run all diagnostics
    await check_deployment_info()
    await test_minimal_request()
    await test_alternative_nodes()
    
    print(f"\n" + "="*60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*60)
    print("💡 Common issues and solutions:")
    print()
    print("1. 🚫 Deployment not active:")
    print("   - Check RunComfy dashboard for deployment status")
    print("   - Verify deployment is 'running' not 'stopped'")
    print()
    print("2. 🔧 Wrong node IDs:")
    print("   - Node IDs might have changed in the workflow")
    print("   - Download the latest workflow JSON from RunComfy")
    print("   - Check actual node IDs in the workflow")
    print()
    print("3. 📋 Missing required inputs:")
    print("   - Some nodes might be required that we're not setting")
    print("   - Check workflow for mandatory vs optional inputs")
    print()
    print("4. 🏗️ Workflow misconfiguration:")
    print("   - Deployment might not be properly built")
    print("   - Try redeploying the workflow on RunComfy")
    print()
    print("🎯 Next steps:")
    print("   1. Check RunComfy dashboard for deployment status")
    print("   2. Download the actual workflow JSON")
    print("   3. Verify node IDs match our mapping")
    print("   4. Test with RunComfy's web interface first")

if __name__ == "__main__":
    asyncio.run(main())
