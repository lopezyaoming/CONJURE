"""
Enhanced serverless workflow test with comprehensive debugging
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

async def test_with_token(api_token: str, token_name: str):
    """Test workflow with specific API token"""
    
    print(f"\n🔑 Testing with {token_name}")
    print("="*50)
    
    # Set environment variables
    os.environ["RUNCOMFY_API_TOKEN"] = api_token
    os.environ["RUNCOMFY_USER_ID"] = "0cb54d51-f01e-48e1-ae7b-28d1c21bc947"
    os.environ["RUNCOMFY_DEPLOYMENT_ID"] = "dfcf38cd-0a09-4637-a067-5059dc9e444e"
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        print(f"✅ Client initialized with {token_name}")
        print(f"   API Token: {api_token[:8]}...")
        
        # Create test data
        data_dir = Path("data")
        prompt_dir = data_dir / "generated_text"
        render_dir = data_dir / "generated_images" / "gestureCamera"
        
        prompt_dir.mkdir(parents=True, exist_ok=True)
        render_dir.mkdir(parents=True, exist_ok=True)
        
        # Simple test prompt
        test_prompt = "red cube, simple geometry"
        prompt_file = prompt_dir / "userPrompt.txt"
        prompt_file.write_text(test_prompt)
        
        # Create simple test image
        render_file = render_dir / "render.png"
        if not render_file.exists():
            from PIL import Image
            # Create a simple 512x512 image with a colored square
            img = Image.new('RGB', (512, 512), 'black')
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rectangle([200, 200, 312, 312], fill='red', outline='white', width=2)
            img.save(render_file)
        
        print(f"📁 Test data ready:")
        print(f"   Prompt: {test_prompt}")
        print(f"   Image: {render_file} ({render_file.stat().st_size} bytes)")
        
        # Submit request with very reduced steps for quick testing
        print(f"\n🚀 Submitting test request...")
        
        request = await client.submit_request(
            prompt=test_prompt,
            render_image_path=str(render_file),
            seed=123,
            steps_flux=1,  # Minimal for quick test
            steps_partpacker=1  # Minimal for quick test
        )
        
        print(f"✅ Request submitted: {request.request_id}")
        
        # Monitor for a short time
        print(f"\n⏳ Monitoring for 60 seconds...")
        
        for i in range(20):  # Check every 3 seconds for 1 minute
            await asyncio.sleep(3)
            
            try:
                status = await client.get_request_status(request.request_id)
                print(f"   Check {i+1:2d}: {status.status.value:<12} (queue: {status.queue_position})")
                
                if status.status.value in ["completed", "succeeded", "failed"]:
                    print(f"   🎯 Request finished with status: {status.status.value}")
                    if status.error_message:
                        print(f"   Error: {status.error_message}")
                    return True
                    
                if status.status.value == "in_progress":
                    print(f"   🔥 Request is now running! This is good progress.")
                    
            except Exception as e:
                print(f"   ❌ Status check failed: {e}")
                break
        
        # Cancel request to avoid unnecessary charges
        try:
            await client.cancel_request(request.request_id)
            print(f"   ✅ Request cancelled")
        except Exception as e:
            print(f"   ⚠️ Could not cancel: {e}")
        
        return False
        
    except Exception as e:
        print(f"❌ Test failed with {token_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    
    print("🧪 ENHANCED SERVERLESS WORKFLOW TEST")
    print("="*60)
    print("💡 This test will:")
    print("   1. Try both API tokens")
    print("   2. Use minimal steps to reduce costs")
    print("   3. Cancel requests after 60 seconds")
    print("   4. Provide detailed debugging")
    print()
    
    # Test tokens
    tokens = [
        ("78356331-a9ec-49c2-a412-59140b32b9b3", "API Token 1"),
        ("85d58c0c-a147-4097-b9ed-2b1fcdc1e160", "API Token 2")
    ]
    
    for token, name in tokens:
        success = await test_with_token(token, name)
        if success:
            print(f"\n🎉 SUCCESS with {name}!")
            break
        else:
            print(f"\n❌ {name} did not complete in time")
    
    print(f"\n" + "="*60)
    print(f"📊 Test completed")
    print(f"💡 If requests stayed 'in_queue', the deployment might be:")
    print(f"   - Overloaded or busy")
    print(f"   - Misconfigured")
    print(f"   - Requiring different node inputs")
    print(f"   - Not properly deployed")

if __name__ == "__main__":
    asyncio.run(main())
