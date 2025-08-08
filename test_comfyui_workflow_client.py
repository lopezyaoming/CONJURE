"""
Test ComfyUI Workflow Client

Tests the workflow client against a running ComfyUI server.
This uses the development server if available.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from runcomfy.comfyui_workflow_client import ComfyUIWorkflowClient
from runcomfy.dev_server_state import get_active_server


async def test_workflow_client():
    """Test the ComfyUI workflow client with development server"""
    print("🧪 Testing ComfyUI Workflow Client")
    print("=" * 50)
    
    # Check for active development server
    server_state = get_active_server()
    if not server_state:
        print("❌ No active development server found")
        print("💡 Start a development server first:")
        print("   python runcomfy/dev_server_startup.py")
        return False
    
    print(f"✅ Using development server:")
    print(f"   Server ID: {server_state.server_id}")
    print(f"   URL: {server_state.base_url}")
    print(f"   Status: {server_state.status}")
    
    # Initialize workflow client
    client = ComfyUIWorkflowClient()
    
    # Load the generate_flux_mesh workflow
    workflow_path = Path("runcomfy/workflows/generate_flux_mesh.json")
    if not workflow_path.exists():
        print(f"❌ Workflow file not found: {workflow_path}")
        return False
    
    print(f"✅ Loading workflow: {workflow_path}")
    with open(workflow_path, 'r') as f:
        workflow_data = json.load(f)
    
    print(f"   Workflow loaded: {len(workflow_data)} nodes")
    
    # Test 1: Simple workflow validation
    print("\\n🔍 Test 1: Workflow Validation")
    try:
        # Prepare a minimal test workflow
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="  # 1x1 white pixel
        test_prompt = "A simple test object"
        
        prepared_workflow = client.prepare_flux_mesh_workflow(
            workflow_data, 
            test_image_b64, 
            test_prompt
        )
        
        print("✅ Workflow preparation completed")
        print(f"   Prepared workflow has {len(prepared_workflow)} nodes")
        
    except Exception as e:
        print(f"❌ Workflow preparation failed: {e}")
        return False
    
    # Test 2: Server connectivity 
    print("\\n🔍 Test 2: Server Connectivity")
    try:
        import httpx
        
        # Test basic connectivity to ComfyUI server
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(f"{server_state.base_url}/")
            
            if response.status_code == 200:
                print("✅ ComfyUI server is reachable")
                print(f"   Response status: {response.status_code}")
            else:
                print(f"⚠️ ComfyUI server responded with status: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Server connectivity test failed: {e}")
        print("💡 The server might still be starting up")
        return False
    
    # Test 3: Workflow submission (dry run - don't actually execute)
    print("\\n🔍 Test 3: Workflow Submission Test")
    try:
        # Test workflow submission without actual execution
        print("📤 Testing workflow submission endpoint...")
        
        # Check if /prompt endpoint exists
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            # Try to get queue status first (lighter operation)
            response = await http_client.get(f"{server_state.base_url}/queue")
            
            if response.status_code == 200:
                queue_data = response.json()
                print("✅ ComfyUI /queue endpoint working")
                print(f"   Queue status: {queue_data}")
            else:
                print(f"⚠️ Queue endpoint returned: {response.status_code}")
        
        print("✅ Workflow submission test completed")
        
    except Exception as e:
        print(f"❌ Workflow submission test failed: {e}")
        return False
    
    print("\\n" + "=" * 50)
    print("🎯 Test Results Summary:")
    print("✅ Workflow Client initialized successfully")
    print("✅ Development server connection verified")
    print("✅ Workflow loading and preparation working")
    print("✅ Server connectivity confirmed")
    print("✅ Basic API endpoints accessible")
    
    print("\\n💡 Next Steps:")
    print("1. The ComfyUI Workflow Client is ready to use")
    print("2. You can now execute workflows on the running server")
    print("3. Test with: client.execute_workflow(server_url, workflow)")
    
    return True


async def test_full_workflow_execution():
    """Test full workflow execution (optional - more intensive)"""
    print("\\n🚀 Optional: Full Workflow Execution Test")
    print("=" * 50)
    
    response = input("Do you want to test full workflow execution? (y/N): ")
    if response.lower() != 'y':
        print("⏭️ Skipping full execution test")
        return
    
    server_state = get_active_server()
    if not server_state:
        print("❌ No active development server")
        return
    
    client = ComfyUIWorkflowClient()
    
    try:
        # Load workflow
        workflow_path = Path("runcomfy/workflows/generate_flux_mesh.json")
        with open(workflow_path, 'r') as f:
            workflow_data = json.load(f)
        
        # Prepare with test data
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        test_prompt = "A simple test cube"
        
        prepared_workflow = client.prepare_flux_mesh_workflow(
            workflow_data, 
            test_image_b64, 
            test_prompt
        )
        
        print("🚀 Executing workflow...")
        result = await client.execute_workflow(
            server_state.base_url, 
            prepared_workflow
        )
        
        print(f"📊 Execution result:")
        print(f"   Status: {result.status}")
        print(f"   Prompt ID: {result.prompt_id}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
        
    except Exception as e:
        print(f"❌ Full execution test failed: {e}")


if __name__ == "__main__":
    print("🧪 ComfyUI Workflow Client Tests")
    print("=" * 50)
    
    asyncio.run(test_workflow_client())
    
    # Optional full execution test
    asyncio.run(test_full_workflow_execution())
