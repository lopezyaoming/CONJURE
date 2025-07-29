"""
FLUX Pipeline Debug Test
Tests each component of the FLUX pipeline to identify where issues occur
"""

import os
import time
import httpx
import json
from pathlib import Path

def check_environment():
    """Check if required environment variables are set"""
    print("🔍 Checking environment setup...")
    
    # Check Hugging Face token
    hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
    if hf_token:
        print(f"✅ HUGGINGFACE_HUB_ACCESS_TOKEN: {'*' * 20}{hf_token[-10:]}")
    else:
        print("❌ HUGGINGFACE_HUB_ACCESS_TOKEN not set!")
        print("   Set it with: export HUGGINGFACE_HUB_ACCESS_TOKEN='your_token'")
        return False
    
    # Check API server
    try:
        response = httpx.get("http://127.0.0.1:8000/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ API Server: Running on port 8000")
        else:
            print(f"❌ API Server: Unhealthy ({response.status_code})")
            return False
    except Exception as e:
        print(f"❌ API Server: Not accessible ({e})")
        print("   Make sure to run: python launcher/main.py")
        return False
    
    return True

def check_control_image():
    """Check if GestureCamera render exists"""
    print("\n🖼️ Checking control image...")
    
    control_path = Path("data/generated_images/gestureCamera/render.png")
    if control_path.exists():
        print(f"✅ Control image found: {control_path}")
        return str(control_path)
    else:
        print(f"❌ Control image not found: {control_path}")
        print("   In Blender, click 'Render Camera' button first")
        return None

def test_flux_depth_api(control_image_path):
    """Test FLUX1.DEPTH API directly"""
    print("\n🎨 Testing FLUX1.DEPTH API...")
    
    request_data = {
        "control_image_path": control_image_path,
        "prompt": "A simple geometric robot sculpture with metallic surfaces",
        "seed": 42,
        "randomize_seed": False,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 10,
        "num_inference_steps": 28
    }
    
    print(f"📝 Request: {request_data['prompt']}")
    print(f"🎲 Seed: {request_data['seed']}")
    
    try:
        print("🌐 Making request to FLUX1.DEPTH API...")
        with httpx.Client(timeout=300.0) as client:
            response = client.post("http://127.0.0.1:8000/flux/depth", json=request_data)
            
        print(f"📶 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ FLUX1.DEPTH API successful!")
                print(f"   Generated image: {result['data']['image_path']}")
                return result['data']['image_path']
            else:
                print(f"❌ FLUX1.DEPTH API failed: {result['message']}")
        else:
            print(f"❌ HTTP Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        
    return None

def test_partpacker_api(image_path):
    """Test PartPacker API directly"""
    print("\n🏗️ Testing PartPacker API...")
    
    request_data = {
        "image_path": image_path,
        "num_steps": 20,  # Reduced for faster testing
        "cfg_scale": 7,
        "grid_res": 256,  # Reduced for faster testing
        "seed": 42,
        "simplify_mesh": False,
        "target_num_faces": 50000
    }
    
    print(f"🖼️ Input image: {image_path}")
    print(f"⚙️ Settings: {request_data['num_steps']} steps, {request_data['grid_res']} grid")
    
    try:
        print("🌐 Making request to PartPacker API...")
        with httpx.Client(timeout=600.0) as client:
            response = client.post("http://127.0.0.1:8000/partpacker/generate_3d", json=request_data)
            
        print(f"📶 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ PartPacker API successful!")
                print(f"   Generated model: {result['data']['model_path']}")
                return result['data']['model_path']
            else:
                print(f"❌ PartPacker API failed: {result['message']}")
        else:
            print(f"❌ HTTP Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        
    return None

def test_mesh_import_api(model_path):
    """Test mesh import API"""
    print("\n📦 Testing Mesh Import API...")
    
    request_data = {
        "mesh_path": model_path,
        "min_volume_threshold": 0.001
    }
    
    print(f"📁 Model path: {model_path}")
    
    try:
        print("🌐 Making request to Mesh Import API...")
        with httpx.Client(timeout=60.0) as client:
            response = client.post("http://127.0.0.1:8000/blender/import_mesh", json=request_data)
            
        print(f"📶 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ Mesh Import API successful!")
                return True
            else:
                print(f"❌ Mesh Import API failed: {result['message']}")
        else:
            print(f"❌ HTTP Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        
    return False

def trigger_flux_pipeline():
    """Trigger the complete FLUX pipeline through state.json"""
    print("\n🚀 Testing complete FLUX pipeline via state.json...")
    
    state_file = Path("data/input/state.json")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Read current state
    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state_data = {}
    
    # DISABLED: Set FLUX pipeline request (was overriding user prompts)
    # state_data.update({
    #     "flux_pipeline_request": "new", 
    #     "flux_prompt": "A futuristic robotic sculpture with smooth curves and metallic surfaces",
    #     "flux_seed": 42,
    #     "min_volume_threshold": 0.001
    # })
    
    with open(state_file, 'w') as f:
        json.dump(state_data, f, indent=2)
    
    print("❌ FLUX pipeline test DISABLED to prevent overriding user prompts")
    print("   User prompts should now work correctly")
    
    # Wait and check for status updates
    for i in range(30):  # Wait up to 30 seconds for the request to be picked up
        time.sleep(1)
        try:
            with open(state_file, 'r') as f:
                current_state = json.load(f)
            
            if current_state.get("flux_pipeline_request") != "new":
                print("✅ Pipeline request was picked up by the launcher!")
                break
            elif i % 5 == 0:
                print(f"⏳ Waiting for launcher to pick up request... ({i}s)")
                
        except Exception:
            pass
    else:
        print("❌ Pipeline request was not picked up after 30 seconds")
        print("   Check if the main launcher is running and processing requests")

def main():
    """Run the complete debug test"""
    print("="*60)
    print("FLUX PIPELINE DEBUG TEST")
    print("="*60)
    
    # Step 1: Check environment
    if not check_environment():
        print("\n❌ Environment setup failed - cannot proceed")
        return
    
    # Step 2: Check control image
    control_image = check_control_image()
    if not control_image:
        print("\n❌ Control image missing - cannot proceed")
        print("   Solution: In Blender, click the 'Render Camera' button in CONJURE panel")
        return
    
    print(f"\n🎯 Testing pipeline components individually...")
    
    # Step 3: Test FLUX API
    flux_image = test_flux_depth_api(control_image)
    if not flux_image:
        print("\n❌ FLUX1.DEPTH API failed - cannot proceed to PartPacker")
        return
    
    # Step 4: Test PartPacker API  
    model_path = test_partpacker_api(flux_image)
    if not model_path:
        print("\n❌ PartPacker API failed - cannot proceed to mesh import")
        return
    
    # Step 5: Test Mesh Import API
    if test_mesh_import_api(model_path):
        print("\n✅ All pipeline components working individually!")
    else:
        print("\n❌ Mesh import failed")
        return
    
    # Step 6: Test complete pipeline via state.json
    print("\n" + "="*40)
    print("TESTING COMPLETE PIPELINE")
    print("="*40)
    trigger_flux_pipeline()
    
    print("\n" + "="*60)
    print("✅ DEBUG TEST COMPLETED")
    print("   Check the main launcher console for detailed debug logs")
    print("="*60)

if __name__ == "__main__":
    main() 