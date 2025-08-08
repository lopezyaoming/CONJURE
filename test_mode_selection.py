"""
Test script for mode selection functionality
"""

import httpx
import json
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_mode_endpoint():
    """Test the /mode endpoint to check current mode and service availability."""
    try:
        print("🔍 Testing mode endpoint...")
        response = httpx.get("http://127.0.0.1:8000/mode", timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Mode endpoint working!")
            print(f"📊 Current mode: {data['generation_mode'].upper()}")
            print(f"🔧 Available modes: {', '.join(data['available_modes'])}")
            print(f"🏠 Local available: {data['local_available']}")
            print(f"☁️ Cloud available: {data['cloud_available']}")
            
            print("\n📋 Service Details:")
            for service_name, service_info in data['services'].items():
                status = "✅ Available" if service_info['available'] else "❌ Not Available"
                print(f"   {service_name.upper()}: {status}")
                print(f"      Name: {service_info['name']}")
                print(f"      Description: {service_info['description']}")
                print(f"      Requirements: {service_info['requirements']}")
            
            return True
        else:
            print(f"❌ Mode endpoint error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing mode endpoint: {e}")
        print("   Make sure the API server is running: python launcher/main.py")
        return False

def test_config_mode():
    """Test that the config mode is properly set."""
    try:
        print("\n🔍 Testing config mode setting...")
        
        # Import after adding path
        import launcher.config as config
        
        mode = getattr(config, 'GENERATION_MODE', 'not_set')
        print(f"📊 Config mode: {mode}")
        
        if mode in ['local', 'cloud']:
            print("✅ Config mode is valid")
            return True
        else:
            print("❌ Config mode is invalid")
            return False
            
    except Exception as e:
        print(f"❌ Error testing config mode: {e}")
        return False

def test_generation_services():
    """Test that generation services can be imported and instantiated."""
    try:
        print("\n🔍 Testing generation services...")
        
        from launcher.generation_services import get_generation_service, LocalGenerationService, CloudGenerationService
        
        # Test local service
        local_service = get_generation_service("local")
        print(f"🏠 Local service: {type(local_service).__name__}")
        print(f"   Available: {local_service.is_available()}")
        
        # Test cloud service  
        cloud_service = get_generation_service("cloud")
        print(f"☁️ Cloud service: {type(cloud_service).__name__}")
        print(f"   Available: {cloud_service.is_available()}")
        
        print("✅ Generation services working!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing generation services: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing CONJURE Mode Selection Implementation")
    print("=" * 60)
    
    # Test 1: Config mode
    config_ok = test_config_mode()
    
    # Test 2: Generation services
    services_ok = test_generation_services()
    
    # Test 3: Mode endpoint (requires running server)
    endpoint_ok = test_mode_endpoint()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    print(f"   Config Mode: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"   Generation Services: {'✅ PASS' if services_ok else '❌ FAIL'}")
    print(f"   Mode Endpoint: {'✅ PASS' if endpoint_ok else '❌ FAIL'}")
    
    if config_ok and services_ok:
        print("\n🎉 Core mode selection functionality is working!")
        if not endpoint_ok:
            print("ℹ️  To test the API endpoint, run: python launcher/main.py")
        else:
            print("🌟 All tests passed! Mode selection is fully functional.")
    else:
        print("\n❌ Some core functionality is not working. Check the errors above.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
