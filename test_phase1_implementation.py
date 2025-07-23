"""
Test script for Phase 1 VIBE Modeling implementation
Tests FLUX1.DEPTH + PartPacker integration and Blender mesh processing
"""

import os
import time
import httpx
import json
from pathlib import Path

# Set environment variables (you'll need to set these)
# os.environ["HUGGINGFACE_HUB_ACCESS_TOKEN"] = "your_token_here"

def test_api_server_health():
    """Test if the FastAPI server is running"""
    print("🔍 Testing API server health...")
    try:
        response = httpx.get("http://127.0.0.1:8000/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ API server is healthy")
            return True
        else:
            print(f"❌ API server unhealthy: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API server: {e}")
        return False

def test_flux_generation():
    """Test FLUX.1-dev image generation"""
    print("\n🎨 Testing FLUX.1-dev generation...")
    
    request_data = {
        "prompt": "A simple geometric cube sculpture on a white background",
        "seed": 42,
        "randomize_seed": False,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 3.5,
        "num_inference_steps": 28
    }
    
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post("http://127.0.0.1:8000/flux/generate", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print(f"✅ FLUX generation successful: {result['data']['image_path']}")
                    return result['data']['image_path']
                else:
                    print(f"❌ FLUX generation failed: {result['message']}")
                    return None
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error testing FLUX generation: {e}")
        return None

def test_flux_depth_generation():
    """Test FLUX.1-Depth generation (requires a control image)"""
    print("\n🎨 Testing FLUX.1-Depth generation...")
    
    # Create a dummy control image for testing
    control_image_path = Path("data/generated_images/gestureCamera/render.png")
    control_image_path.parent.mkdir(parents=True, exist_ok=True)
    
    # For testing, create a simple image or use existing one
    if not control_image_path.exists():
        print(f"⚠️ Control image not found: {control_image_path}")
        print("   Run Blender with CONJURE and use 'Render Camera' button first")
        return None
    
    request_data = {
        "control_image_path": str(control_image_path),
        "prompt": "A futuristic robotic sculpture with metallic surfaces",
        "seed": 42,
        "randomize_seed": False,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 10,
        "num_inference_steps": 28
    }
    
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post("http://127.0.0.1:8000/flux/depth", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print(f"✅ FLUX Depth generation successful: {result['data']['image_path']}")
                    return result['data']['image_path']
                else:
                    print(f"❌ FLUX Depth generation failed: {result['message']}")
                    return None
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error testing FLUX Depth generation: {e}")
        return None

def test_partpacker_generation(image_path):
    """Test PartPacker 3D generation"""
    print("\n🏗️ Testing PartPacker 3D generation...")
    
    if not image_path or not Path(image_path).exists():
        print(f"❌ Input image not found: {image_path}")
        return None
    
    request_data = {
        "image_path": image_path,
        "num_steps": 20,  # Reduced for faster testing
        "cfg_scale": 7,
        "grid_res": 256,  # Reduced for faster testing
        "seed": 42,
        "simplify_mesh": False,
        "target_num_faces": 50000  # Reduced for faster testing
    }
    
    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post("http://127.0.0.1:8000/partpacker/generate_3d", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print(f"✅ PartPacker generation successful: {result['data']['model_path']}")
                    return result['data']['model_path']
                else:
                    print(f"❌ PartPacker generation failed: {result['message']}")
                    return None
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error testing PartPacker generation: {e}")
        return None

def test_mesh_import(model_path):
    """Test mesh import via API"""
    print("\n📦 Testing mesh import...")
    
    if not model_path or not Path(model_path).exists():
        print(f"❌ Model file not found: {model_path}")
        return None
    
    request_data = {
        "mesh_path": model_path,
        "min_volume_threshold": 0.001
    }
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post("http://127.0.0.1:8000/blender/import_mesh", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print(f"✅ Mesh import command sent successfully")
                    return True
                else:
                    print(f"❌ Mesh import failed: {result['message']}")
                    return False
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing mesh import: {e}")
        return False

def test_instruction_manager():
    """Test new instruction manager tools"""
    print("\n🔧 Testing instruction manager tools...")
    
    # Test spawn_primitive
    instruction_data = {
        "instruction": {
            "tool_name": "spawn_primitive",
            "parameters": {
                "primitive_type": "Sphere"
            }
        }
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post("http://127.0.0.1:8000/execute_instruction", json=instruction_data)
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print("✅ spawn_primitive instruction executed successfully")
                else:
                    print(f"❌ spawn_primitive instruction failed: {result['message']}")
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing instruction manager: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting Phase 1 Implementation Tests")
    print("=" * 50)
    
    # Check environment variables
    if not os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN"):
        print("⚠️ WARNING: HUGGINGFACE_HUB_ACCESS_TOKEN not set")
        print("   Some tests may fail without proper authentication")
    
    # Test API server
    if not test_api_server_health():
        print("❌ Cannot proceed without API server")
        return
    
    # Test instruction manager
    test_instruction_manager()
    
    # Test FLUX generation
    flux_image = test_flux_generation()
    
    # Test FLUX Depth generation (if control image exists)
    flux_depth_image = test_flux_depth_generation()
    
    # Test PartPacker (if we have an image)
    test_image = flux_depth_image or flux_image
    if test_image:
        model_path = test_partpacker_generation(test_image)
        
        # Test mesh import (if we have a model)
        if model_path:
            test_mesh_import(model_path)
    
    print("\n" + "=" * 50)
    print("✅ Phase 1 tests completed!")
    print("\nNext steps:")
    print("1. Run Blender with CONJURE addon loaded")
    print("2. Use 'Test FLUX Pipeline' button in the UI")
    print("3. Try the fuse_mesh and segment_selection tools")

if __name__ == "__main__":
    main() 