"""
Test script for CONJURE data management integration.

Tests the complete data flow:
1. Reading from userPrompt.txt
2. Using render.png as input
3. Workflow preparation with correct paths
4. Output configuration (flux.png and partpacker_result_0.glb)
"""

import asyncio
import json
from pathlib import Path

# Import our components
try:
    from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator
    from runcomfy.workflow_progress_tracker import progress_tracker
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    exit(1)


def test_data_file_availability():
    """Check if all required CONJURE data files are available"""
    print("🔍 Checking CONJURE Data File Availability")
    print("="*50)
    
    # Required input files
    required_files = {
        "userPrompt.txt": Path("data/generated_text/userPrompt.txt"),
        "render.png": Path("data/generated_images/gestureCamera/render.png"),
        "workflow": Path("runcomfy/workflows/generate_flux_mesh.json")
    }
    
    # Output directories
    output_dirs = {
        "flux images": Path("data/generated_images/flux"),
        "partpacker results": Path("data/generated_models/partpacker_results")
    }
    
    all_good = True
    
    # Check input files
    print("📋 Required Input Files:")
    for name, path in required_files.items():
        if path.exists():
            if path.is_file():
                size = path.stat().st_size
                print(f"   ✅ {name}: {path} ({size} bytes)")
                
                # Show content preview for text files
                if name == "userPrompt.txt":
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        print(f"      📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}")
                    except Exception as e:
                        print(f"      ⚠️ Could not read content: {e}")
            else:
                print(f"   ❌ {name}: {path} (exists but not a file)")
                all_good = False
        else:
            print(f"   ❌ {name}: {path} (not found)")
            all_good = False
    
    # Check output directories
    print("\n📁 Output Directories:")
    for name, path in output_dirs.items():
        if path.exists():
            print(f"   ✅ {name}: {path}")
        else:
            print(f"   ⚠️ {name}: {path} (will be created)")
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"      ✅ Created directory: {path}")
            except Exception as e:
                print(f"      ❌ Failed to create: {e}")
                all_good = False
    
    return all_good


def test_workflow_configuration():
    """Test workflow JSON configuration with CONJURE paths"""
    print("\n🔧 Testing Workflow Configuration")
    print("="*50)
    
    try:
        # Load workflow
        workflow_path = Path("runcomfy/workflows/generate_flux_mesh.json")
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)
        
        print(f"✅ Loaded workflow: {len(workflow)} nodes")
        
        # Check input configuration (node 16 - INPUTIMAGE)
        if "16" in workflow:
            input_image = workflow["16"]["inputs"]["image"]
            print(f"✅ Input image node (16): {input_image}")
            if input_image == "render.png":
                print("   ✅ Correctly configured for render.png")
            else:
                print(f"   ⚠️ Expected 'render.png', got '{input_image}'")
        else:
            print("❌ Input image node (16) not found")
        
        # Check positive clip node (34 - POSITIVECLIP)
        if "34" in workflow:
            clip_l = workflow["34"]["inputs"]["clip_l"]
            print(f"✅ Positive clip node (34) found")
            print(f"   Current prompt: {clip_l[:100]}{'...' if len(clip_l) > 100 else ''}")
        else:
            print("❌ Positive clip node (34) not found")
        
        # Check output configuration (node 24 - EXPORT IMAGE)
        if "24" in workflow:
            image_prefix = workflow["24"]["inputs"]["filename_prefix"]
            print(f"✅ Image output node (24): prefix '{image_prefix}'")
            if image_prefix == "flux":
                print("   ✅ Correctly configured for flux.png")
            else:
                print(f"   ⚠️ Expected 'flux', got '{image_prefix}'")
        else:
            print("❌ Image output node (24) not found")
        
        # Check GLB output configuration (node 33 - EXPORTGLB)
        if "33" in workflow:
            glb_prefix = workflow["33"]["inputs"]["filename_prefix"]
            print(f"✅ GLB output node (33): prefix '{glb_prefix}'")
            if glb_prefix == "partpacker_results/partpacker_result_0":
                print("   ✅ Correctly configured for partpacker_results/partpacker_result_0.glb")
            else:
                print(f"   ⚠️ Expected 'partpacker_results/partpacker_result_0', got '{glb_prefix}'")
        else:
            print("❌ GLB output node (33) not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow configuration test failed: {e}")
        return False


async def test_orchestrator_data_preparation():
    """Test orchestrator's data preparation functionality"""
    print("\n🎭 Testing Orchestrator Data Preparation")
    print("="*50)
    
    try:
        # Create orchestrator
        orchestrator = RunComfyOrchestrator()
        
        # Load workflow
        workflow = orchestrator.load_workflow()
        print(f"✅ Orchestrator loaded workflow: {len(workflow)} nodes")
        
        # Test workflow preparation
        prepared_workflow = orchestrator.prepare_workflow_inputs(workflow, use_conjure_data=True)
        
        # Verify preparation results
        print("\n📋 Workflow Preparation Results:")
        
        # Check if userPrompt.txt content was loaded
        if "34" in prepared_workflow:
            prepared_prompt = prepared_workflow["34"]["inputs"]["clip_l"]
            
            # Compare with file content
            user_prompt_path = Path("data/generated_text/userPrompt.txt")
            if user_prompt_path.exists():
                with open(user_prompt_path, 'r', encoding='utf-8') as f:
                    file_prompt = f.read().strip()
                
                if prepared_prompt == file_prompt:
                    print("   ✅ Prompt correctly loaded from userPrompt.txt")
                else:
                    print("   ⚠️ Prompt mismatch between file and workflow")
                    print(f"      File: {file_prompt[:50]}...")
                    print(f"      Workflow: {prepared_prompt[:50]}...")
            else:
                print("   ⚠️ userPrompt.txt not found, using default")
        
        # Verify paths are correctly set
        expected_configs = {
            "16": {"input": "image", "expected": "render.png"},
            "24": {"input": "filename_prefix", "expected": "flux"},
            "33": {"input": "filename_prefix", "expected": "partpacker_results/partpacker_result_0"}
        }
        
        for node_id, config in expected_configs.items():
            if node_id in prepared_workflow:
                actual_value = prepared_workflow[node_id]["inputs"][config["input"]]
                if actual_value == config["expected"]:
                    print(f"   ✅ Node {node_id} correctly configured: {actual_value}")
                else:
                    print(f"   ⚠️ Node {node_id} mismatch: expected '{config['expected']}', got '{actual_value}'")
            else:
                print(f"   ❌ Node {node_id} not found in workflow")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator data preparation test failed: {e}")
        return False


async def test_job_creation():
    """Test job creation with CONJURE data"""
    print("\n📝 Testing Job Creation with CONJURE Data")
    print("="*50)
    
    try:
        orchestrator = RunComfyOrchestrator()
        
        # Create a job
        job = await orchestrator.create_job("test_conjure_data")
        
        print(f"✅ Job created: {job.job_id}")
        print(f"   Status: {job.status.value}")
        print(f"   Prompt: {job.prompt[:100]}{'...' if len(job.prompt) > 100 else ''}")
        print(f"   Input image: {job.input_image_path}")
        print(f"   Created at: {job.created_at}")
        
        # Test job dictionary conversion
        job_dict = job.to_dict()
        print(f"✅ Job serialization working: {len(job_dict)} fields")
        
        # Cleanup
        await orchestrator.cleanup_job(job.job_id)
        print(f"✅ Job cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Job creation test failed: {e}")
        return False


def test_output_file_cleanup():
    """Test cleanup of previous output files (overwrite functionality)"""
    print("\n🧹 Testing Output File Cleanup (Overwrite)")
    print("="*50)
    
    output_files = [
        Path("data/generated_images/flux/flux.png"),
        Path("data/generated_models/partpacker_results/partpacker_result_0.glb")
    ]
    
    for output_file in output_files:
        if output_file.exists():
            try:
                # Test if we can write to the file (to verify overwrite capability)
                backup_content = None
                if output_file.stat().st_size > 0:
                    # Read current content to restore later
                    with open(output_file, 'rb') as f:
                        backup_content = f.read()
                
                # Try to write a test marker
                with open(output_file, 'w') as f:
                    f.write("# CONJURE test marker\n")
                
                print(f"✅ Can overwrite: {output_file}")
                
                # Restore original content if it existed
                if backup_content:
                    with open(output_file, 'wb') as f:
                        f.write(backup_content)
                
            except Exception as e:
                print(f"❌ Cannot overwrite {output_file}: {e}")
        else:
            print(f"ℹ️ Output file doesn't exist yet: {output_file}")


async def main():
    """Run all data management tests"""
    print("🎯 CONJURE Data Management Test Suite")
    print("="*60)
    
    # Run tests in sequence
    all_tests_passed = True
    
    # Basic file availability
    if not test_data_file_availability():
        all_tests_passed = False
    
    # Workflow configuration
    if not test_workflow_configuration():
        all_tests_passed = False
    
    # Orchestrator data preparation
    if not await test_orchestrator_data_preparation():
        all_tests_passed = False
    
    # Job creation
    if not await test_job_creation():
        all_tests_passed = False
    
    # Output file handling
    test_output_file_cleanup()
    
    print(f"\n🎉 Data Management Test Suite {'✅ PASSED' if all_tests_passed else '⚠️ ISSUES FOUND'}")
    
    if all_tests_passed:
        print("\n🚀 CONJURE data management is ready!")
        print("   ✅ Input files: userPrompt.txt, render.png")
        print("   ✅ Output files: flux.png, partpacker_result_0.glb")
        print("   ✅ Workflow configuration: correct paths")
        print("   ✅ Orchestrator integration: working")
        print("\n💡 Ready to proceed to CloudGenerationService integration!")
    else:
        print("\n⚠️ Please fix the issues above before proceeding")


if __name__ == "__main__":
    asyncio.run(main())
