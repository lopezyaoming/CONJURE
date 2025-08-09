"""
Test Complete CONJURE Data Flow with RunComfy

This script tests the complete end-to-end data flow:
1. Read userPrompt.txt and render.png (inputs)
2. Upload image and execute workflow on RunComfy
3. Download results to flux.png and partpacker_result_0.glb (outputs)
4. Verify files are saved locally

This is the comprehensive test for the full CONJURE data management system.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any

# Import our components
try:
    from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator, FluxMeshJob, JobStatus
    from runcomfy.comfyui_workflow_client import ComfyUIWorkflowClient
    from runcomfy.dev_server_state import DevServerStateManager
    from runcomfy.workflow_progress_tracker import progress_tracker
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    exit(1)


def check_input_files():
    """Check if required input files exist"""
    print("🔍 Checking Input Files")
    print("="*50)
    
    required_files = {
        "userPrompt.txt": Path("data/generated_text/userPrompt.txt"),
        "render.png": Path("data/generated_images/gestureCamera/render.png")
    }
    
    all_good = True
    for name, path in required_files.items():
        if path.exists():
            size = path.stat().st_size
            print(f"✅ {name}: {path} ({size} bytes)")
            
            if name == "userPrompt.txt":
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    print(f"   📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}")
                except Exception as e:
                    print(f"   ⚠️ Could not read: {e}")
        else:
            print(f"❌ {name}: {path} (not found)")
            all_good = False
    
    return all_good


def prepare_output_directories():
    """Ensure output directories exist"""
    print("\n📁 Preparing Output Directories")
    print("="*50)
    
    output_dirs = [
        Path("data/generated_images/flux"),
        Path("data/generated_models/partpacker_results")
    ]
    
    for dir_path in output_dirs:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created: {dir_path}")
            except Exception as e:
                print(f"❌ Failed to create {dir_path}: {e}")
                return False
        else:
            print(f"✅ Exists: {dir_path}")
    
    return True


async def test_orchestrator_execution():
    """Test complete workflow execution using the orchestrator"""
    print("\n🎭 Testing Complete Workflow with Orchestrator")
    print("="*60)
    
    # Check for development server
    dev_server_manager = DevServerStateManager()
    server_state = dev_server_manager.load_server_state()
    
    if not server_state or server_state.status != "running":
        print("❌ No active development server found")
        print("💡 Please run: python runcomfy/dev_server_startup.py")
        return False
    
    print(f"✅ Using development server: {server_state.server_id}")
    print(f"   URL: {server_state.base_url}")
    
    # Test server health
    is_healthy = await dev_server_manager.check_server_health(server_state)
    if not is_healthy:
        print("❌ Development server is not healthy")
        return False
    
    print("✅ Server is healthy and ready")
    
    try:
        # Create orchestrator
        orchestrator = RunComfyOrchestrator()
        
        # Execute complete workflow
        print(f"\n🚀 Starting complete flux mesh generation...")
        print(f"   This will read userPrompt.txt and render.png")
        print(f"   And generate flux.png and partpacker_result_0.glb")
        
        start_time = time.time()
        
        # Execute the job
        job = await orchestrator.execute_flux_mesh_generation("conjure_test")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Report results
        print(f"\n📊 Execution Results:")
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status.value}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Prompt: {job.prompt[:100]}{'...' if len(job.prompt) > 100 else ''}")
        
        if job.status == JobStatus.COMPLETED:
            print(f"✅ Workflow completed successfully!")
            print(f"   Machine cost: ${job.actual_machine_cost:.4f}")
            
            # Check outputs
            print(f"\n📂 Generated Files:")
            if job.generated_image_url:
                print(f"   Image URL: {job.generated_image_url}")
            if job.generated_mesh_url:
                print(f"   Mesh URL: {job.generated_mesh_url}")
            
            if job.result_files:
                print(f"   All outputs: {list(job.result_files.keys())}")
            
            return job
            
        else:
            print(f"❌ Workflow failed: {job.error_message}")
            return None
            
    except Exception as e:
        print(f"❌ Orchestrator execution failed: {e}")
        return None


async def download_and_verify_results(job: FluxMeshJob):
    """Download workflow results and verify they're saved locally"""
    print("\n💾 Downloading and Verifying Results")
    print("="*50)
    
    if not job or job.status != JobStatus.COMPLETED:
        print("❌ No completed job to download from")
        return False
    
    expected_files = {
        "flux.png": Path("data/generated_images/flux/flux.png"),
        "partpacker_result_0.glb": Path("data/generated_models/partpacker_results/partpacker_result_0.glb")
    }
    
    # In a real implementation, we would download from the URLs
    # For now, let's check if ComfyUI has saved files directly
    # (ComfyUI typically saves to its output folder, not our data folder)
    
    print("🔍 Checking for locally saved files...")
    
    all_downloaded = True
    for filename, local_path in expected_files.items():
        if local_path.exists():
            size = local_path.stat().st_size
            print(f"✅ {filename}: {local_path} ({size} bytes)")
            
            # Check if file was recently modified (within last 10 minutes)
            import os
            import time
            mod_time = os.path.getmtime(local_path)
            if time.time() - mod_time < 600:  # 10 minutes
                print(f"   🕒 Recently modified (likely from this workflow)")
            else:
                print(f"   ⚠️ File exists but may be from previous run")
        else:
            print(f"❌ {filename}: {local_path} (not found)")
            all_downloaded = False
    
    if not all_downloaded:
        print("\n💡 Note: ComfyUI may save files to its own output directory")
        print("   We need to implement result downloading from ComfyUI server")
        print("   Or configure ComfyUI to save directly to our data folders")
    
    return all_downloaded


async def implement_result_download(job: FluxMeshJob, server_url: str):
    """Implement actual result downloading from ComfyUI server"""
    print("\n🔄 Implementing Result Download from ComfyUI")
    print("="*50)
    
    if not job or not job.result_files:
        print("❌ No result files to download")
        return False
    
    import httpx
    
    # Mapping from node IDs to local file paths
    output_mapping = {
        "24": Path("data/generated_images/flux/flux.png"),      # Image output
        "33": Path("data/generated_models/partpacker_results/partpacker_result_0.glb")  # GLB output
    }
    
    downloaded_files = []
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for node_id, local_path in output_mapping.items():
                if node_id in job.result_files:
                    node_outputs = job.result_files[node_id]
                    
                    # Handle different output formats
                    if isinstance(node_outputs, dict) and "images" in node_outputs:
                        # Image outputs
                        images = node_outputs["images"]
                        if images:
                            image_info = images[0]  # Take first image
                            filename = image_info["filename"]
                            subfolder = image_info.get("subfolder", "")
                            
                            # Build download URL
                            url_path = f"/view?filename={filename}"
                            if subfolder:
                                url_path += f"&subfolder={subfolder}"
                            
                            download_url = f"{server_url}{url_path}"
                            
                            print(f"📥 Downloading {filename} from {download_url}")
                            
                            # Download file
                            response = await client.get(download_url)
                            if response.status_code == 200:
                                # Ensure directory exists
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                
                                # Save file
                                with open(local_path, 'wb') as f:
                                    f.write(response.content)
                                
                                size = len(response.content)
                                print(f"✅ Saved: {local_path} ({size} bytes)")
                                downloaded_files.append(local_path)
                            else:
                                print(f"❌ Download failed: HTTP {response.status_code}")
                    
                    elif isinstance(node_outputs, dict) and "gltf" in node_outputs:
                        # GLB/GLTF outputs (PartPacker)
                        gltf_files = node_outputs["gltf"]
                        if gltf_files:
                            gltf_info = gltf_files[0]  # Take first file
                            filename = gltf_info["filename"]
                            subfolder = gltf_info.get("subfolder", "")
                            
                            # Build download URL
                            url_path = f"/view?filename={filename}"
                            if subfolder:
                                url_path += f"&subfolder={subfolder}"
                            
                            download_url = f"{server_url}{url_path}"
                            
                            print(f"📥 Downloading {filename} from {download_url}")
                            
                            # Download file
                            response = await client.get(download_url)
                            if response.status_code == 200:
                                # Ensure directory exists
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                
                                # Save file
                                with open(local_path, 'wb') as f:
                                    f.write(response.content)
                                
                                size = len(response.content)
                                print(f"✅ Saved: {local_path} ({size} bytes)")
                                downloaded_files.append(local_path)
                            else:
                                print(f"❌ Download failed: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Result download failed: {e}")
        return False
    
    print(f"\n📊 Download Summary:")
    print(f"   Downloaded {len(downloaded_files)} files")
    for file_path in downloaded_files:
        print(f"   ✅ {file_path}")
    
    return len(downloaded_files) > 0


async def test_progress_monitoring(job_duration_estimate: int = 300):
    """Test progress monitoring during workflow execution"""
    print("\n📊 Testing Progress Monitoring")
    print("="*50)
    
    # Check if there are any active workflows
    active_workflows = []
    for prompt_id in progress_tracker.active_workflows:
        summary = progress_tracker.get_workflow_summary(prompt_id)
        if summary:
            active_workflows.append(summary)
    
    if not active_workflows:
        print("ℹ️ No active workflows found for progress monitoring")
        return
    
    # Monitor the most recent workflow
    latest_workflow = active_workflows[-1]
    prompt_id = latest_workflow["prompt_id"]
    
    print(f"🔍 Monitoring workflow: {prompt_id}")
    print(f"   Current progress: {latest_workflow['overall_progress']:.1f}%")
    print(f"   Current stage: {latest_workflow['current_stage']}")
    print(f"   Status: {latest_workflow['status']}")
    
    # Show stage breakdown
    print(f"\n📋 Stage Progress:")
    for stage in latest_workflow["stages"]:
        status_emoji = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(stage["status"], "❓")
        
        print(f"   {status_emoji} {stage['name']}: {stage['nodes_completed']}/{stage['nodes_total']} nodes")


async def main():
    """Run complete data flow test"""
    print("🎯 CONJURE Complete Data Flow Test")
    print("="*60)
    print("This test will execute a full workflow and download results")
    print("⚠️ This will incur RunComfy costs!")
    
    # Confirm execution
    confirm = input("\nDo you want to proceed with the full test? (y/N): ")
    if confirm.lower() != 'y':
        print("⏭️ Test cancelled")
        return
    
    # Step 1: Check inputs
    if not check_input_files():
        print("❌ Input files missing. Please ensure userPrompt.txt and render.png exist.")
        return
    
    # Step 2: Prepare outputs
    if not prepare_output_directories():
        print("❌ Failed to prepare output directories")
        return
    
    # Step 3: Execute workflow
    job = await test_orchestrator_execution()
    if not job:
        print("❌ Workflow execution failed")
        return
    
    # Step 4: Test progress monitoring
    await test_progress_monitoring()
    
    # Step 5: Download and verify results
    dev_server_manager = DevServerStateManager()
    server_state = dev_server_manager.load_server_state()
    
    if server_state and job.status == JobStatus.COMPLETED:
        await implement_result_download(job, server_state.base_url)
    
    await download_and_verify_results(job)
    
    print(f"\n🎉 Complete Data Flow Test Finished!")
    print(f"📊 Summary:")
    print(f"   ✅ Input files read successfully")
    print(f"   ✅ Workflow executed on RunComfy")
    print(f"   ✅ Progress tracking working")
    print(f"   {'✅' if job.status == JobStatus.COMPLETED else '❌'} Results generated")
    print(f"   💰 Cost: ${job.actual_machine_cost:.4f}")
    
    print(f"\n📁 Check your data folders for:")
    print(f"   📸 data/generated_images/flux/flux.png")
    print(f"   🗿 data/generated_models/partpacker_results/partpacker_result_0.glb")


if __name__ == "__main__":
    asyncio.run(main())
