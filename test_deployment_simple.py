"""
Simple test to validate the RunComfy deployment itself
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables
os.environ["RUNCOMFY_API_TOKEN"] = "78356331-a9ec-49c2-a412-59140b32b9b3"
os.environ["RUNCOMFY_USER_ID"] = "0cb54d51-f01e-48e1-ae7b-28d1c21bc947"
os.environ["RUNCOMFY_DEPLOYMENT_ID"] = "dfcf38cd-0a09-4637-a067-5059dc9e444e"

async def test_deployment():
    """Test basic deployment connectivity"""
    
    print("🔍 Testing RunComfy Deployment")
    print("="*40)
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        print(f"✅ Client initialized")
        print(f"   Base URL: {client.base_url}")
        print(f"   User ID: {client.user_id}")
        print(f"   Deployment ID: {client.deployment_id}")
        print(f"   API Token: {client.api_token[:8]}...")
        
        # Test 1: Try to make a simple status call with fake request ID
        print(f"\n🧪 Test 1: Basic API connectivity")
        try:
            # This should fail gracefully but tell us if our auth works
            fake_request_id = "00000000-0000-0000-0000-000000000000"
            await client.get_request_status(fake_request_id)
        except Exception as e:
            print(f"   Expected error (fake ID): {type(e).__name__}: {str(e)}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print(f"   ❌ Authentication failed - check API token")
                return False
            elif "404" in str(e) or "not found" in str(e).lower():
                print(f"   ✅ Authentication works (404 expected for fake ID)")
            else:
                print(f"   ⚠️ Unexpected error: {e}")
        
        # Test 2: Try minimal inference request
        print(f"\n🧪 Test 2: Minimal inference request")
        try:
            # Create minimal test data
            test_prompt = "simple cube"
            
            # Create tiny test image (1x1 pixel white)
            from PIL import Image
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img = Image.new('RGB', (1, 1), 'white')
                img.save(tmp.name)
                test_image_path = tmp.name
            
            print(f"   Prompt: {test_prompt}")
            print(f"   Image: {test_image_path} (1x1 white pixel)")
            
            # Submit with minimal steps
            request = await client.submit_request(
                prompt=test_prompt,
                render_image_path=test_image_path,
                seed=42,
                steps_flux=1,  # Minimal steps
                steps_partpacker=1  # Minimal steps
            )
            
            print(f"   ✅ Request submitted: {request.request_id}")
            print(f"   Status: {request.status}")
            
            # Check status a few times
            for i in range(3):
                await asyncio.sleep(2)
                status = await client.get_request_status(request.request_id)
                print(f"   Check {i+1}: {status.status.value} (queue: {status.queue_position})")
                
                if status.status.value not in ["in_queue"]:
                    break
            
            # Cancel the request to avoid charges
            try:
                await client.cancel_request(request.request_id)
                print(f"   ✅ Request cancelled to avoid charges")
            except:
                print(f"   ⚠️ Could not cancel request")
            
            # Clean up temp file
            os.unlink(test_image_path)
            
        except Exception as e:
            print(f"   ❌ Failed to submit request: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"\n🎉 Deployment test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_deployment())
    if success:
        print(f"\n✅ Deployment appears to be working correctly!")
    else:
        print(f"\n❌ Deployment has issues that need to be resolved.")
