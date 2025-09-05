"""
Test script for RunComfy Serverless API integration.
Tests the complete serverless workflow with CONJURE.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Set environment variables for testing
os.environ["RUNCOMFY_API_TOKEN"] = "78356331-a9ec-49c2-a412-59140b32b9b3"
os.environ["RUNCOMFY_USER_ID"] = "0cb54d51-f01e-48e1-ae7b-28d1c21bc947"
os.environ["RUNCOMFY_DEPLOYMENT_ID"] = "dfcf38cd-0a09-4637-a067-5059dc9e444e"

async def test_serverless_client():
    """Test the serverless client directly"""
    print("🧪 Testing ServerlessRunComfyClient...")
    
    try:
        from runcomfy.serverless_client import ServerlessRunComfyClient
        
        client = ServerlessRunComfyClient()
        print(f"✅ Client initialized: {client.is_available()}")
        
        # Test availability
        if not client.is_available():
            print("❌ Client not available - check API token and deployment ID")
            return False
        
        print("✅ ServerlessRunComfyClient test passed!")
        return True
        
    except Exception as e:
        print(f"❌ ServerlessRunComfyClient test failed: {e}")
        return False

def test_serverless_service():
    """Test the serverless service"""
    print("🧪 Testing ServerlessRunComfyService...")
    
    try:
        from runcomfy.serverless_service import ServerlessRunComfyService
        
        service = ServerlessRunComfyService()
        print(f"✅ Service initialized: {service.is_available()}")
        
        if not service.is_available():
            print("❌ Service not available - check configuration")
            return False
        
        print("✅ ServerlessRunComfyService test passed!")
        return True
        
    except Exception as e:
        print(f"❌ ServerlessRunComfyService test failed: {e}")
        return False

def test_generation_services():
    """Test the generation services factory"""
    print("🧪 Testing generation services factory...")
    
    try:
        from launcher.generation_services import get_generation_service
        
        # Test serverless service
        serverless_service = get_generation_service("serverless")
        print(f"✅ Serverless service: {type(serverless_service).__name__}")
        print(f"   Available: {serverless_service.is_available()}")
        
        # Test that cloud now points to serverless
        cloud_service = get_generation_service("cloud")
        print(f"✅ Cloud service (should be serverless): {type(cloud_service).__name__}")
        print(f"   Available: {cloud_service.is_available()}")
        
        # Test legacy cloud
        legacy_service = get_generation_service("cloud_legacy")
        print(f"✅ Legacy cloud service: {type(legacy_service).__name__}")
        
        print("✅ Generation services factory test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Generation services test failed: {e}")
        return False

def test_conjure_data_setup():
    """Test CONJURE data file setup"""
    print("🧪 Testing CONJURE data setup...")
    
    try:
        # Create test data directories
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Create userPrompt.txt
        prompt_dir = data_dir / "generated_text"
        prompt_dir.mkdir(exist_ok=True)
        prompt_file = prompt_dir / "userPrompt.txt"
        prompt_file.write_text("high quality 3D model, detailed sci-fi spaceship, clean geometry")
        
        # Create placeholder render.png
        render_dir = data_dir / "generated_images" / "gestureCamera"
        render_dir.mkdir(parents=True, exist_ok=True)
        render_file = render_dir / "render.png"
        
        if not render_file.exists():
            # Create a simple test image
            try:
                from PIL import Image
                test_image = Image.new('RGB', (1024, 1024), 'white')
                test_image.save(render_file)
                print(f"✅ Created test render.png: {render_file}")
            except ImportError:
                print("⚠️ PIL not available, skipping render.png creation")
        
        print("✅ CONJURE data setup test passed!")
        return True
        
    except Exception as e:
        print(f"❌ CONJURE data setup test failed: {e}")
        return False

async def test_full_workflow():
    """Test the complete serverless workflow (WARNING: This will make actual API calls!)"""
    print("🧪 Testing complete serverless workflow...")
    print("⚠️  WARNING: This will make actual API calls to RunComfy and incur costs!")
    
    response = input("Do you want to proceed with the full workflow test? (y/N): ").strip().lower()
    if response != 'y':
        print("🛑 Full workflow test skipped by user")
        return True
    
    try:
        from runcomfy.serverless_service import ServerlessRunComfyService
        
        service = ServerlessRunComfyService()
        
        if not service.is_available():
            print("❌ Service not available for full test")
            return False
        
        print("🚀 Starting full FLUX + 3D mesh generation...")
        
        # Execute unified generation (this will read from CONJURE data)
        result = service.generate_flux_mesh_unified(
            steps_flux=10,  # Reduced steps for faster testing
            steps_partpacker=25  # Reduced steps for faster testing
        )
        
        if result["success"]:
            print("✅ Full workflow test PASSED!")
            print(f"   FLUX image: {result.get('flux_image_path', 'N/A')}")
            print(f"   3D mesh: {result.get('mesh_model_path', 'N/A')}")
            print(f"   Request ID: {result.get('request_id', 'N/A')}")
            return True
        else:
            print(f"❌ Full workflow test FAILED: {result.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        print(f"❌ Full workflow test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Running RunComfy Serverless Integration Tests")
    print("="*60)
    
    tests = [
        ("Serverless Client", test_serverless_client()),
        ("Serverless Service", test_serverless_service()),
        ("Generation Services", test_generation_services()),
        ("CONJURE Data Setup", test_conjure_data_setup()),
        ("Full Workflow", test_full_workflow())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"\n📋 Running test: {test_name}")
        print("-" * 40)
        
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
            
        results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
    
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print("-" * 40)
    print(f"   {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Serverless integration is ready!")
    else:
        print("⚠️  Some tests failed. Check configuration and try again.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
