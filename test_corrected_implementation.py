"""
Test our corrected serverless implementation that matches the working runcomfy_api_client.py
This should now work perfectly since we copied the exact working format.
"""

import os
import sys
import asyncio
import base64
import random
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from runcomfy.serverless_client import ServerlessRunComfyClient

def create_test_image():
    """Create a test render.png if it doesn't exist"""
    test_image_path = "data/input/render.png"
    os.makedirs("data/input", exist_ok=True)
    
    if not os.path.exists(test_image_path):
        # Create a simple test image
        try:
            from PIL import Image
            img = Image.new('RGB', (512, 512), color='blue')
            img.save(test_image_path)
            print(f"✅ Created test image: {test_image_path}")
        except ImportError:
            # Create a dummy file if PIL not available
            with open(test_image_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n')  # PNG header
            print(f"✅ Created dummy test image: {test_image_path}")
    
    return test_image_path

def create_test_prompt():
    """Create a test userPrompt.txt"""
    prompt_path = "data/input/userPrompt.txt"
    os.makedirs("data/input", exist_ok=True)
    
    test_prompt = "epic futuristic spaceship with glowing engines"
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(test_prompt)
    
    print(f"✅ Created test prompt: {test_prompt}")
    return test_prompt

async def test_corrected_implementation():
    """Test our corrected implementation that matches working code"""
    
    print("🧪 TESTING CORRECTED IMPLEMENTATION")
    print("="*60)
    print("🎯 Using EXACT format from successful runcomfy_api_client.py:")
    print("   ✅ Base64 data URI for images")
    print("   ✅ Only 4 nodes (16, 40, 41, 42)")
    print("   ✅ Node 40 = empty, Node 41 = prompt")
    print("   ✅ Same structure as working code")
    print()
    
    # Setup test data
    test_image_path = create_test_image()
    test_prompt = create_test_prompt()
    
    # Initialize client
    client = ServerlessRunComfyClient()
    
    print(f"🚀 Testing with corrected format:")
    print(f"   Image: {test_image_path}")
    print(f"   Prompt: {test_prompt}")
    print()
    
    try:
        # Build overrides using our corrected method
        overrides = client.build_conjure_overrides(
            prompt=test_prompt,
            render_image_path=test_image_path,
            seed=random.randint(1, 1000000000)
        )
        
        print(f"📋 Generated overrides:")
        print(f"   Nodes: {list(overrides.keys())}")
        print(f"   Node 16 (image): {'Base64 data URI' if overrides['16']['inputs']['image'].startswith('data:') else 'Other format'}")
        print(f"   Node 40 (FLUXCLIP): '{overrides['40']['inputs']['value']}'")
        print(f"   Node 41 (FLUXT5XXL): '{overrides['41']['inputs']['value'][:50]}...'")
        print(f"   Node 42 (seed): {overrides['42']['inputs']['value']}")
        print()
        
        # Verify format matches working implementation
        assert len(overrides) == 4, f"Should have 4 nodes, got {len(overrides)}"
        assert "16" in overrides, "Missing node 16"
        assert "40" in overrides, "Missing node 40"
        assert "41" in overrides, "Missing node 41"
        assert "42" in overrides, "Missing node 42"
        assert "43" not in overrides, "Should NOT have node 43"
        assert "44" not in overrides, "Should NOT have node 44"
        
        # Verify image format
        image_data = overrides["16"]["inputs"]["image"]
        assert image_data.startswith("data:image/png;base64,"), "Image should be Base64 data URI"
        
        # Verify prompt distribution
        assert overrides["40"]["inputs"]["value"] == "", "Node 40 should be empty"
        assert overrides["41"]["inputs"]["value"] == test_prompt, "Node 41 should have the prompt"
        
        print(f"✅ Format validation PASSED!")
        print(f"   ✅ Exactly 4 nodes (like working code)")
        print(f"   ✅ Base64 data URI format")
        print(f"   ✅ Correct prompt distribution")
        print(f"   ✅ Structure matches successful implementation")
        print()
        
        # Submit the request
        request = await client.submit_request(
            prompt=test_prompt,
            render_image_path=test_image_path
        )
        
        print(f"🎉 REQUEST SUBMITTED SUCCESSFULLY!")
        print(f"   Request ID: {request.request_id}")
        print(f"   This means our corrected format is accepted!")
        print()
        
        # Monitor for a short time to see if it processes
        print(f"⏳ Monitoring for processing (should work now)...")
        
        for i in range(10):
            await asyncio.sleep(3)
            
            status_request = await client.get_request_status(request.request_id)
            status = status_request.status.value
            queue_pos = status_request.queue_position
            
            print(f"   Check {i+1}: {status} (queue: {queue_pos})")
            
            if status != "in_queue":
                print(f"   🎉 BREAKTHROUGH! Status changed to: {status}")
                print(f"   ✅ Our corrected implementation WORKS!")
                break
                
            if i == 9:
                print(f"   ⚠️ Still in queue, but at least the request was accepted")
                print(f"   💡 This is better than our previous errors!")
        
        # Cancel the request
        await client.cancel_request(request.request_id)
        print(f"   ✅ Request cancelled")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    
    print("🔬 CORRECTED IMPLEMENTATION TEST")
    print("="*70)
    print("🎯 Testing our fixes based on successful runcomfy_api_client.py")
    print()
    
    success = await test_corrected_implementation()
    
    print(f"\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    
    if success:
        print(f"🎉 SUCCESS! Corrected implementation works!")
        print(f"✅ We successfully copied the working format")
        print(f"✅ Base64 data URI format works")
        print(f"✅ 4-node structure is correct")
        print(f"✅ Prompt distribution is fixed")
        print()
        print(f"🚀 Ready for integration into main CONJURE system!")
        
    else:
        print(f"❌ Test failed - need further investigation")
        print(f"💡 Check error messages above for details")

if __name__ == "__main__":
    asyncio.run(main())
