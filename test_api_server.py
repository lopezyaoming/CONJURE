#!/usr/bin/env python3
"""
Test script for CONJURE API server.
This tests the API endpoints to ensure they're working correctly.
"""

import requests
import time
import subprocess
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_api_health():
    """Test the health endpoint."""
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_conversation_endpoint():
    """Test the conversation processing endpoint."""
    try:
        payload = {
            "conversation_history": "Test conversation from API test script",
            "include_image": True
        }
        
        response = requests.post(
            "http://127.0.0.1:8000/process_conversation",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Conversation endpoint passed")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Conversation endpoint failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Conversation endpoint error: {e}")
        return False

def test_state_endpoint():
    """Test the state retrieval endpoint."""
    try:
        response = requests.get("http://127.0.0.1:8000/state", timeout=5)
        if response.status_code == 200:
            print("✅ State endpoint passed")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ State endpoint failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ State endpoint error: {e}")
        return False

def main():
    print("=== CONJURE API Server Test ===")
    print("Testing API endpoints...")
    print()
    
    # Test health endpoint first
    if not test_api_health():
        print("\n❌ API server appears to be down. Please start it first:")
        print("   python launcher/api_server.py")
        return False
    
    print()
    
    # Test other endpoints
    health_ok = test_api_health()
    conversation_ok = test_conversation_endpoint()
    state_ok = test_state_endpoint()
    
    print("\n=== Test Summary ===")
    print(f"Health endpoint: {'✅' if health_ok else '❌'}")
    print(f"Conversation endpoint: {'✅' if conversation_ok else '❌'}")
    print(f"State endpoint: {'✅' if state_ok else '❌'}")
    
    if all([health_ok, conversation_ok, state_ok]):
        print("\n🎉 All tests passed! API server is working correctly.")
        return True
    else:
        print("\n⚠️ Some tests failed. Check the API server logs for details.")
        return False

if __name__ == "__main__":
    main() 