#!/usr/bin/env python3
"""
Test Local ComfyUI Integration

This script tests the new LOCAL mode (option 5) for CONJURE that uses 
a locally running ComfyUI server with the generate_flux_mesh_LOCAL.json workflow.

Prerequisites:
1. ComfyUI server running on localhost:8188
2. generate_flux_mesh_LOCAL.json workflow in comfyui/workflows/
3. Required models and nodes installed in ComfyUI

Test Flow:
1. Create test input data (userPrompt.txt + render.png)
2. Initialize local ComfyUI service
3. Test connection to ComfyUI server
4. Execute unified workflow generation
5. Verify outputs (flux.png + partpacker_result_0.glb)
"""

import os
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import CONJURE modules
try:
    from launcher.local_comfyui_service import LocalComfyUIService
    from launcher.generation_services import get_generation_service
    print("✅ Successfully imported CONJURE modules")
except ImportError as e:
    print(f"❌ Failed to import CONJURE modules: {e}")
    sys.exit(1)


def create_test_data():
    """Create test input data for the workflow"""
    print("📝 Creating test input data...")
    
    # Create userPrompt.txt
    prompt_path = Path("data/generated_text/userPrompt.txt")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    
    test_prompt = "A sleek modern wireless headset with matte black finish, professional product photography, studio lighting"
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(test_prompt)
    print(f"✅ Created test prompt: {test_prompt}")
    
    # Create dummy render.png (you can replace this with an actual render)
    render_path = Path("data/generated_images/gestureCamera/render.png")
    render_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not render_path.exists():
        # Create a simple test image using PIL if available
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (512, 512), color='white')
            draw = ImageDraw.Draw(img)
            draw.rectangle([100, 100, 400, 400], fill='gray', outline='black', width=3)
            draw.text((200, 250), "TEST", fill='black')
            img.save(render_path)
            print(f"✅ Created test render image: {render_path}")
        except ImportError:
            print("⚠️ PIL not available - please provide a render.png manually")
            return False
    else:
        print(f"✅ Using existing render image: {render_path}")
    
    return True


def test_comfyui_connection():
    """Test connection to local ComfyUI server"""
    print("\n🔌 Testing ComfyUI server connection...")
    
    service = LocalComfyUIService()
    if service.check_comfyui_connection():
        print("✅ ComfyUI server is accessible")
        return True
    else:
        print("❌ ComfyUI server not accessible")
        print("   Make sure ComfyUI is running on localhost:8188")
        return False


def test_workflow_loading():
    """Test loading the local ComfyUI workflow"""
    print("\n📋 Testing workflow loading...")
    
    service = LocalComfyUIService()
    try:
        workflow = service.load_workflow()
        print(f"✅ Successfully loaded workflow with {len(workflow)} nodes")
        
        # Check for required nodes
        required_nodes = ["15", "22", "26"]  # Image input, GLB export, string input
        missing_nodes = [node for node in required_nodes if node not in workflow]
        
        if missing_nodes:
            print(f"⚠️ Missing required nodes: {missing_nodes}")
            return False
        else:
            print("✅ All required nodes found in workflow")
            return True
            
    except Exception as e:
        print(f"❌ Failed to load workflow: {e}")
        return False


def test_generation_service():
    """Test the generation service initialization"""
    print("\n🔧 Testing generation service...")
    
    try:
        service = get_generation_service("local_comfyui")
        print("✅ Successfully created local ComfyUI service")
        
        if service.is_available():
            print("✅ Service reports as available")
            return True
        else:
            print("❌ Service reports as not available")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create generation service: {e}")
        return False


def test_complete_generation():
    """Test complete FLUX + 3D mesh generation"""
    print("\n🚀 Testing complete generation workflow...")
    
    try:
        service = LocalComfyUIService()
        
        print("🎨 Starting unified FLUX + 3D mesh generation...")
        start_time = time.time()
        
        result = service.generate_flux_mesh()
        
        elapsed = time.time() - start_time
        print(f"⏱️ Generation completed in {elapsed:.1f} seconds")
        
        if result["success"]:
            print("✅ Generation completed successfully!")
            
            # Verify outputs
            flux_path = result.get("flux_image")
            mesh_path = result.get("mesh_model")
            
            if flux_path and Path(flux_path).exists():
                size = Path(flux_path).stat().st_size
                print(f"✅ FLUX image created: {flux_path} ({size} bytes)")
            else:
                print(f"❌ FLUX image not found: {flux_path}")
                
            if mesh_path and Path(mesh_path).exists():
                size = Path(mesh_path).stat().st_size
                print(f"✅ 3D mesh created: {mesh_path} ({size} bytes)")
            else:
                print(f"❌ 3D mesh not found: {mesh_path}")
            
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ Generation failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        return False


def main():
    """Run all tests"""
    print("🧪 LOCAL ComfyUI Integration Test")
    print("=" * 50)
    
    tests = [
        ("Create Test Data", create_test_data),
        ("ComfyUI Connection", test_comfyui_connection),
        ("Workflow Loading", test_workflow_loading),
        ("Generation Service", test_generation_service),
        ("Complete Generation", test_complete_generation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ PASSED: {test_name}")
                passed += 1
            else:
                print(f"❌ FAILED: {test_name}")
                failed += 1
        except Exception as e:
            print(f"❌ ERROR in {test_name}: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print("🧪 TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {passed}/{passed + failed} ({passed/(passed + failed)*100:.1f}%)" if (passed + failed) > 0 else "No tests run")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Local ComfyUI integration is working correctly.")
        print("\nNext steps:")
        print("1. Launch CONJURE with: python launcher/main.py")
        print("2. Select option 5 (LOCAL) when prompted")
        print("3. Use gestures in Blender to trigger generation")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Check the errors above.")
        print("\nTroubleshooting:")
        print("1. Ensure ComfyUI is running on localhost:8188")
        print("2. Check that generate_flux_mesh_LOCAL.json exists")
        print("3. Verify required ComfyUI nodes are installed")


if __name__ == "__main__":
    main()
