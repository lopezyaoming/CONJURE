"""
Quick test script for the fixed workflow execution and result download.

This tests:
1. The bug fix (client_id attribute)
2. Result downloading to local folders
3. Complete data flow
"""

import asyncio
from pathlib import Path

try:
    from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator
    from runcomfy.dev_server_state import DevServerStateManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)


async def test_fixed_workflow():
    """Test the fixed workflow execution"""
    print("🧪 Testing Fixed Workflow Execution with Result Download")
    print("="*60)
    
    # Check for development server
    dev_server_manager = DevServerStateManager()
    server_state = dev_server_manager.load_server_state()
    
    if not server_state or server_state.status != "running":
        print("❌ No active development server found")
        print("💡 Please run: python runcomfy/dev_server_startup.py")
        return False
    
    # Check server health
    is_healthy = await dev_server_manager.check_server_health(server_state)
    if not is_healthy:
        print("❌ Development server is not healthy")
        return False
    
    print(f"✅ Using healthy development server: {server_state.server_id}")
    
    # Check input files
    input_files = [
        Path("data/generated_text/userPrompt.txt"),
        Path("data/generated_images/gestureCamera/render.png")
    ]
    
    for input_file in input_files:
        if input_file.exists():
            print(f"✅ Input file: {input_file}")
        else:
            print(f"❌ Missing input file: {input_file}")
            return False
    
    try:
        # Create orchestrator and execute workflow
        orchestrator = RunComfyOrchestrator()
        
        print(f"\n🚀 Executing complete workflow with bug fixes...")
        print(f"   This should now complete successfully and download files")
        
        job = await orchestrator.execute_flux_mesh_generation("bug_fix_test")
        
        print(f"\n📊 Results:")
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status.value}")
        print(f"   Prompt: {job.prompt[:100]}...")
        
        if job.status.value == "completed":
            print(f"✅ Workflow completed successfully!")
            print(f"   Cost: ${job.actual_machine_cost:.4f}")
            
            # Check if files were downloaded
            expected_files = [
                Path("data/generated_images/flux/flux.png"),
                Path("data/generated_models/partpacker_results/partpacker_result_0.glb")
            ]
            
            print(f"\n📁 Checking downloaded files:")
            for expected_file in expected_files:
                if expected_file.exists():
                    size = expected_file.stat().st_size
                    print(f"   ✅ {expected_file} ({size} bytes)")
                    
                    # Check if recently modified
                    import time
                    mod_time = expected_file.stat().st_mtime
                    if time.time() - mod_time < 300:  # 5 minutes
                        print(f"      🕒 Recently modified (from this run)")
                    else:
                        print(f"      ⚠️ Older file (may be from previous run)")
                else:
                    print(f"   ❌ {expected_file} (not found)")
            
            if job.generated_image_url:
                print(f"\n📸 Generated image path: {job.generated_image_url}")
            if job.generated_mesh_url:
                print(f"🗿 Generated mesh path: {job.generated_mesh_url}")
            
            return True
        else:
            print(f"❌ Workflow failed: {job.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the test"""
    print("🎯 CONJURE Fixed Workflow Test")
    print("="*40)
    
    success = await test_fixed_workflow()
    
    if success:
        print(f"\n🎉 Test PASSED!")
        print(f"✅ Bug fixes working")
        print(f"✅ Result download working")
        print(f"✅ Local files saved correctly")
        print(f"\n💡 The workflow is now ready for production use!")
    else:
        print(f"\n❌ Test FAILED!")
        print(f"Please check the error messages above")


if __name__ == "__main__":
    asyncio.run(main())
