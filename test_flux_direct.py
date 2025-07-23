"""
Direct FLUX API Test
Tests the FLUX1.DEPTH API directly using Gradio client to see raw response format
"""

import os
from pathlib import Path
from gradio_client import Client, handle_file

def test_flux_direct():
    """Test FLUX1.DEPTH API directly with Gradio client"""
    
    print("🎨 Testing FLUX1.DEPTH API directly...")
    
    # Check HuggingFace token
    hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
    if hf_token:
        print(f"🔑 Using HF Token: ***{hf_token[-10:]}")
    else:
        print("⚠️  WARNING: HUGGINGFACE_HUB_ACCESS_TOKEN not set - using anonymous quota")
    
    # Check for control image
    control_path = Path("data/generated_images/gestureCamera/render.png")
    if not control_path.exists():
        print(f"❌ Control image not found: {control_path}")
        print("   In Blender, click 'Render Camera' button first")
        return
    
    print(f"✅ Control image found: {control_path}")
    
    try:
        # Initialize Gradio client with token
        print("🔧 Initializing Gradio client...")
        client = Client("black-forest-labs/FLUX.1-Depth-dev", hf_token=hf_token)
        print("✅ Gradio client initialized")
        
        # Make the API call
        print("🚀 Making direct API call to FLUX1.DEPTH...")
        result = client.predict(
            control_image=handle_file(str(control_path)),
            prompt="A simple geometric robot sculpture with metallic surfaces",
            seed=42,
            randomize_seed=False,
            width=1024,
            height=1024,
            guidance_scale=10,
            num_inference_steps=28,
            api_name="/infer"
        )
        
        print("✅ API call completed!")
        print("\n" + "="*60)
        print("🔍 RAW RESULT ANALYSIS")
        print("="*60)
        
        # Detailed analysis of the result
        print(f"Result type: {type(result)}")
        print(f"Result repr: {repr(result)}")
        
        if hasattr(result, '__len__'):
            try:
                print(f"Result length: {len(result)}")
            except:
                print("Result length: Could not determine")
        
        if isinstance(result, (list, tuple)):
            print(f"Result is a sequence with {len(result)} items:")
            for i, item in enumerate(result):
                print(f"  Item {i}: {type(item)} = {repr(item)[:100]}...")
                
                # If it's a dict, show its keys
                if isinstance(item, dict):
                    print(f"    Dict keys: {list(item.keys())}")
                    for key, value in item.items():
                        print(f"      {key}: {type(value)} = {repr(value)[:50]}...")
                        
                # If it has common file attributes
                if hasattr(item, 'name'):
                    print(f"    Has .name attribute: {item.name}")
                if hasattr(item, 'path'):
                    print(f"    Has .path attribute: {item.path}")
        
        elif isinstance(result, dict):
            print("Result is a dictionary:")
            print(f"  Keys: {list(result.keys())}")
            for key, value in result.items():
                print(f"    {key}: {type(value)} = {repr(value)[:50]}...")
        
        elif isinstance(result, str):
            print(f"Result is a string: {result}")
            # Check if it's a file path
            if Path(result).exists():
                print(f"  ✅ String is a valid file path that exists")
            else:
                print(f"  ❌ String is not a valid file path")
        
        else:
            print(f"Result is something else: {str(result)[:200]}...")
            
            # Try common attributes
            attrs_to_check = ['name', 'path', 'filename', 'file', 'url']
            for attr in attrs_to_check:
                if hasattr(result, attr):
                    attr_value = getattr(result, attr)
                    print(f"  Has .{attr} attribute: {attr_value}")
        
        print("="*60)
        
        # Try to find any file paths in the result
        print("\n🔍 Looking for file paths in result...")
        if _find_file_paths_in_result(result):
            print("✅ Found potential file paths - API is working!")
        else:
            print("❌ No file paths found - need to investigate result structure")
            
    except Exception as e:
        print(f"❌ Error during direct API test: {e}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")

def _find_file_paths_in_result(obj, depth=0):
    """Recursively search for file paths in the result"""
    if depth > 3:  # Prevent infinite recursion
        return False
    
    found_paths = False
    
    try:
        # Check if it's a string that looks like a path
        if isinstance(obj, str):
            if Path(obj).exists():
                print(f"  ✅ Found existing file path: {obj}")
                found_paths = True
            elif obj.startswith(('/tmp/', 'C:', '/')) or '.' in obj:
                print(f"  🔍 Found potential path (doesn't exist): {obj}")
        
        # Check if it's a Path object
        elif isinstance(obj, Path):
            print(f"  ✅ Found Path object: {obj} (exists: {obj.exists()})")
            found_paths = True
        
        # Recursively check containers
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                if _find_file_paths_in_result(item, depth + 1):
                    found_paths = True
        
        elif isinstance(obj, dict):
            for key, value in obj.items():
                if _find_file_paths_in_result(value, depth + 1):
                    found_paths = True
        
        # Check for file-like attributes
        elif hasattr(obj, 'name') or hasattr(obj, 'path'):
            if hasattr(obj, 'name'):
                name_val = getattr(obj, 'name')
                print(f"  🔍 Found .name attribute: {name_val}")
                if isinstance(name_val, str) and Path(name_val).exists():
                    print(f"    ✅ .name is an existing file!")
                    found_paths = True
            
            if hasattr(obj, 'path'):
                path_val = getattr(obj, 'path')
                print(f"  🔍 Found .path attribute: {path_val}")
                if isinstance(path_val, str) and Path(path_val).exists():
                    print(f"    ✅ .path is an existing file!")
                    found_paths = True
    
    except Exception:
        pass  # Ignore errors in recursive search
    
    return found_paths

if __name__ == "__main__":
    print("="*60)
    print("DIRECT FLUX API TEST")
    print("="*60)
    test_flux_direct() 