"""
Focused test script for RunComfy Serverless workflow.
ONLY tests the workflow: sends a prompt and saves GLB/IMG to correct locations.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables (from serverlessruncomfyinfo.txt)
os.environ["RUNCOMFY_API_TOKEN"] = "78356331-a9ec-49c2-a412-59140b32b9b3"
os.environ["RUNCOMFY_USER_ID"] = "0cb54d51-f01e-48e1-ae7b-28d1c21bc947"
os.environ["RUNCOMFY_DEPLOYMENT_ID"] = "dfcf38cd-0a09-4637-a067-5059dc9e444e"

async def test_serverless_workflow():
    """Test the complete serverless workflow with actual API calls."""
    
    print("🚀 Testing RunComfy Serverless Workflow - FIXED VERSION")
    print("="*50)
    print("🔧 FIXES APPLIED:")
    print("   ✅ Corrected input field names (nodes 40-44 use 'value')")
    print("   ✅ Using workflow default steps (FLUX: 20, PartPacker: 50)")
    print("   ✅ Updated based on actual workflow JSON")
    print("="*50)
    
    # Enable detailed debug logging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # 1. Setup test data
    print("📁 Setting up test data...")
    
    # Create directories
    data_dir = Path("data")
    prompt_dir = data_dir / "generated_text"
    render_dir = data_dir / "generated_images" / "gestureCamera"
    flux_dir = data_dir / "generated_images" / "flux"
    mesh_dir = data_dir / "generated_models" / "partpacker_results"
    
    for dir_path in [prompt_dir, render_dir, flux_dir, mesh_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create test prompt
    test_prompt = "futuristic sci-fi spaceship with glowing engines, detailed 3D model, clean geometry, cyberpunk style"
    prompt_file = prompt_dir / "userPrompt.txt"
    prompt_file.write_text(test_prompt)
    print(f"✅ Created prompt: {test_prompt}")
    
    # Create test render image
    render_file = render_dir / "render.png"
    if not render_file.exists():
        try:
            from PIL import Image, ImageDraw
            # Create a simple test image with some content
            img = Image.new('RGB', (1024, 1024), 'black')
            draw = ImageDraw.Draw(img)
            
            # Draw a simple spaceship shape
            draw.rectangle([400, 300, 600, 500], fill='gray', outline='white', width=3)
            draw.polygon([(500, 300), (450, 200), (550, 200)], fill='lightgray', outline='white')
            draw.ellipse([470, 350, 530, 400], fill='blue', outline='cyan', width=2)
            
            img.save(render_file)
            print(f"✅ Created test render.png")
        except ImportError:
            # Fallback: create a simple white image
            from PIL import Image
            img = Image.new('RGB', (1024, 1024), 'white')
            img.save(render_file)
            print(f"✅ Created simple test render.png")
    
    # 2. Initialize serverless client
    print("\n🔧 Initializing serverless client...")
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        
        if not client.is_available():
            print("❌ Serverless client not available")
            return False
        
        print("✅ Serverless client ready")
        
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # 3. Submit workflow request
    print("\n🚀 Submitting workflow request...")
    print(f"📝 Prompt: {test_prompt}")
    print(f"🖼️ Input image: {render_file}")
    
    try:
        # Add debug info before submission
        print(f"🔧 Debug Info:")
        print(f"   API Token: {os.environ.get('RUNCOMFY_API_TOKEN', 'NOT SET')[:8]}...")
        print(f"   User ID: {os.environ.get('RUNCOMFY_USER_ID', 'NOT SET')}")
        print(f"   Deployment ID: {os.environ.get('RUNCOMFY_DEPLOYMENT_ID', 'NOT SET')}")
        print(f"   Image file exists: {render_file.exists()}")
        print(f"   Image file size: {render_file.stat().st_size if render_file.exists() else 'N/A'} bytes")
        
        # Submit request with reduced steps for faster testing
        print(f"🚀 Calling client.submit_request with FIXED parameters:")
        print(f"   prompt: {test_prompt[:50]}...")
        print(f"   render_image_path: {render_file}")
        print(f"   seed: 12345")
        print(f"   steps_flux: 20 (workflow default)")
        print(f"   steps_partpacker: 50 (workflow default)")
        print(f"🔧 Using CORRECTED input field names:")
        print(f"   - Nodes 40/41: 'value' instead of 'text'")
        print(f"   - Nodes 42/43/44: 'value' instead of specific field names")
        
        request = await client.submit_request(
            prompt=test_prompt,
            render_image_path=str(render_file),
            seed=12345,
            steps_flux=20,  # Fixed: using workflow defaults
            steps_partpacker=50  # Fixed: using workflow defaults
        )
        
        print(f"✅ Request submitted: {request.request_id}")
        print(f"🔍 Full request object:")
        print(f"   ID: {request.request_id}")
        print(f"   Deployment: {request.deployment_id}")
        print(f"   Status: {request.status}")
        print(f"   Queue position: {request.queue_position}")
        print(f"   Created at: {request.created_at}")
        
    except Exception as e:
        print(f"❌ Failed to submit request: {e}")
        print(f"🔍 Exception type: {type(e).__name__}")
        print(f"🔍 Exception details: {str(e)}")
        import traceback
        print(f"🔍 Full traceback:")
        traceback.print_exc()
        return False
    
    # 4. Wait for completion
    print("\n⏳ Waiting for generation to complete...")
    
    try:
        print(f"🔧 Starting wait_for_completion with:")
        print(f"   Request ID: {request.request_id}")
        print(f"   Timeout: 1800 seconds (30 minutes)")
        
        # Use longer timeout since the workflow should now work properly
        production_timeout = 1800  # 30 minutes for complete generation
        print(f"⏰ Using production timeout: {production_timeout} seconds (workflow should work now!)")
        
        completed_request = await client.wait_for_completion(
            request.request_id,
            timeout=production_timeout
        )
        
        print(f"🔍 Final request status:")
        print(f"   Status: {completed_request.status}")
        print(f"   Queue position: {completed_request.queue_position}")
        print(f"   Error message: {completed_request.error_message}")
        print(f"   Outputs: {completed_request.outputs}")
        print(f"   Created at: {completed_request.created_at}")
        print(f"   Finished at: {completed_request.finished_at}")
        
        if completed_request.status.value not in ["completed", "succeeded"]:
            print(f"❌ Generation failed: {completed_request.status.value}")
            if completed_request.error_message:
                print(f"   Error: {completed_request.error_message}")
            
            # Check if it's still in queue after timeout
            if completed_request.status.value == "in_queue":
                print(f"⚠️ Request still in queue after {production_timeout} seconds")
                print(f"   This is unexpected since we fixed the input field names!")
                print(f"   Possible remaining issues:")
                print(f"   1. Deployment is heavily overloaded")
                print(f"   2. There might be another configuration issue")
                
                # Try to get more info about the deployment
                print(f"\n🔍 Let's check the deployment status...")
                try:
                    status_response = await client.get_request_status(request.request_id)
                    print(f"   Raw status response: {status_response}")
                except Exception as status_e:
                    print(f"   Failed to get status: {status_e}")
            
            return False
        
        print("✅ Generation completed successfully!")
        
    except asyncio.TimeoutError:
        print(f"⏰ Request timed out after {production_timeout} seconds")
        print(f"   Request ID: {request.request_id}")
        print(f"   The fix may not have resolved all issues, or generation is very slow")
        return False
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        print(f"🔍 Exception type: {type(e).__name__}")
        print(f"🔍 Exception details: {str(e)}")
        import traceback
        print(f"🔍 Full traceback:")
        traceback.print_exc()
        return False
    
    # 5. Download results to correct CONJURE locations
    print("\n📥 Downloading results...")
    
    try:
        # Download to temporary location first
        temp_dir = Path("temp_downloads")
        downloaded_files = await client.download_outputs(completed_request, temp_dir)
        
        # Move files to correct CONJURE locations
        final_files = {}
        
        # Move FLUX image
        if "flux_image" in downloaded_files:
            temp_flux = Path(downloaded_files["flux_image"])
            final_flux = flux_dir / "flux.png"
            
            if temp_flux.exists():
                import shutil
                shutil.move(str(temp_flux), str(final_flux))
                final_files["flux_image"] = str(final_flux)
                print(f"✅ FLUX image saved: {final_flux}")
            else:
                print(f"⚠️ FLUX image not found at {temp_flux}")
        
        # Move 3D mesh
        if "mesh_model" in downloaded_files:
            temp_mesh = Path(downloaded_files["mesh_model"])
            final_mesh = mesh_dir / "partpacker_result_0.glb"
            
            if temp_mesh.exists():
                import shutil
                shutil.move(str(temp_mesh), str(final_mesh))
                final_files["mesh_model"] = str(final_mesh)
                print(f"✅ 3D mesh saved: {final_mesh}")
            else:
                print(f"⚠️ 3D mesh not found at {temp_mesh}")
        
        # Clean up temp directory
        try:
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except:
            pass
        
    except Exception as e:
        print(f"❌ Failed to download results: {e}")
        return False
    
    # 6. Verify results
    print("\n🔍 Verifying results...")
    
    success = True
    
    expected_flux = flux_dir / "flux.png"
    expected_mesh = mesh_dir / "partpacker_result_0.glb"
    
    if expected_flux.exists():
        size = expected_flux.stat().st_size
        print(f"✅ FLUX image verified: {expected_flux} ({size:,} bytes)")
    else:
        print(f"❌ FLUX image missing: {expected_flux}")
        success = False
    
    if expected_mesh.exists():
        size = expected_mesh.stat().st_size
        print(f"✅ 3D mesh verified: {expected_mesh} ({size:,} bytes)")
    else:
        print(f"❌ 3D mesh missing: {expected_mesh}")
        success = False
    
    # 7. Summary
    print("\n" + "="*50)
    print("📊 WORKFLOW TEST SUMMARY")
    print("="*50)
    
    if success:
        print("🎉 WORKFLOW TEST PASSED!")
        print(f"   ✅ Generated FLUX image: {expected_flux}")
        print(f"   ✅ Generated 3D mesh: {expected_mesh}")
        print(f"   🎯 Request ID: {completed_request.request_id}")
        print(f"   ⏱️ Files saved to correct CONJURE directories")
        print()
        print("🚀 SERVERLESS WORKFLOW IS NOW WORKING!")
        print("   🔧 Input field fix was successful!")
        print("   🚀 CONJURE can now use serverless mode for instant generation!")
        print()
        print("📋 What was fixed:")
        print("   - Nodes 40/41: 'text' → 'value' (PrimitiveStringMultiline)")
        print("   - Node 42: 'noise_seed' → 'value' (PrimitiveInt)")
        print("   - Node 43: 'num_steps' → 'value' (PrimitiveInt)")
        print("   - Node 44: 'num_inference_steps' → 'value' (PrimitiveInt)")
    else:
        print("❌ WORKFLOW TEST FAILED!")
        print("   Some files were not generated or saved correctly.")
        print("   Check the error messages above for details.")
        print("   The input field fix may need further refinement.")
    
    return success

async def main():
    """Main test function"""
    
    print("⚠️  WARNING: This test will make actual API calls to RunComfy")
    print("💰 This will incur charges on your RunComfy account")
    print("⏱️  Estimated time: 2-5 minutes (should work now!)")
    print("🎯 Estimated cost: ~$0.10-0.50 (depending on server tier)")
    print()
    print("🔧 TESTING FIXED WORKFLOW:")
    print("   ✅ Corrected input field names based on actual workflow JSON")
    print("   ✅ Using proper default steps (FLUX: 20, PartPacker: 50)")
    print("   ✅ This should move from 'in_queue' to 'in_progress' now!")
    print()
    
    response = input("Do you want to proceed with the workflow test? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("🛑 Test cancelled by user")
        return
    
    print("\n🔥 Starting workflow test...")
    
    success = await test_serverless_workflow()
    
    if success:
        print("\n🎉 SUCCESS! Serverless workflow is ready for production use!")
    else:
        print("\n💥 FAILED! Check configuration and try again.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
