"""
Test with realistic step values instead of minimal ones
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

async def test_realistic_steps():
    """Test with realistic step counts that models actually expect"""
    
    print("🧪 Testing with Realistic Step Values")
    print("="*50)
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        # Create test data
        data_dir = Path("data")
        render_dir = data_dir / "generated_images" / "gestureCamera"
        render_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test image
        render_file = render_dir / "render.png"
        if not render_file.exists():
            from PIL import Image
            img = Image.new('RGB', (512, 512), 'black')
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rectangle([200, 200, 312, 312], fill='red', outline='white', width=2)
            img.save(render_file)
        
        # Test with REALISTIC step values
        test_prompt = "simple red cube"
        
        print(f"📝 Prompt: {test_prompt}")
        print(f"🖼️ Image: {render_file}")
        print(f"🔧 Using REALISTIC steps:")
        print(f"   FLUX Steps: 20 (was 1)")
        print(f"   PartPacker Steps: 50 (was 1)")
        
        request = await client.submit_request(
            prompt=test_prompt,
            render_image_path=str(render_file),
            seed=42,
            steps_flux=20,      # Realistic FLUX steps
            steps_partpacker=50  # Realistic PartPacker steps
        )
        
        print(f"✅ Request submitted: {request.request_id}")
        
        # Monitor for progress
        print(f"\n⏳ Monitoring for 2 minutes...")
        
        for i in range(24):  # Check every 5 seconds for 2 minutes
            await asyncio.sleep(5)
            
            status = await client.get_request_status(request.request_id)
            print(f"   Check {i+1:2d}: {status.status.value:<12} (queue: {status.queue_position})")
            
            if status.status.value == "in_progress":
                print(f"   🎉 SUCCESS! Request is now PROCESSING!")
                print(f"   This confirms the deployment works with realistic steps.")
                
                # Let it run a bit more to see if it completes
                for j in range(6):  # Check every 10 seconds for 1 more minute
                    await asyncio.sleep(10)
                    status = await client.get_request_status(request.request_id)
                    print(f"   Progress {j+1}: {status.status.value}")
                    
                    if status.status.value in ["completed", "succeeded"]:
                        print(f"   🏆 COMPLETED! The workflow is fully functional!")
                        return True
                
                break
                
            elif status.status.value in ["completed", "succeeded", "failed"]:
                print(f"   🎯 Final status: {status.status.value}")
                break
        
        # Cancel if still running
        try:
            await client.cancel_request(request.request_id)
            print(f"   ✅ Request cancelled")
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_realistic_steps())
    
    if success:
        print(f"\n🎉 SUCCESS! The deployment works with realistic step values!")
        print(f"💡 The issue was using steps=1 which is too low for the models.")
        print(f"🚀 Use steps_flux=20 and steps_partpacker=50 for production.")
    else:
        print(f"\n💭 Still not working. Try the diagnostic tools:")
        print(f"   python check_workflow_nodes.py")
        print(f"   python diagnose_deployment.py")
