"""
Quick script to verify our node mappings against the documented workflow.
Based on the serverlessruncomfyinfo.txt file.
"""

import json

def analyze_node_mapping():
    """Analyze our current node mapping for potential issues"""
    
    print("🔍 NODE MAPPING ANALYSIS")
    print("="*40)
    
    # Our current mapping (from serverless_client.py)
    our_mapping = {
        "16": {"input_type": "image", "field": "image", "description": "INPUTIMAGE - render.png"},
        "40": {"input_type": "text", "field": "text", "description": "FLUXCLIP - Text prompt (CLIP)"},
        "41": {"input_type": "text", "field": "text", "description": "FLUXT5XXL - Text prompt (T5XXL)"},
        "42": {"input_type": "integer", "field": "noise_seed", "description": "NOISESEED - Random seed"},
        "43": {"input_type": "integer", "field": "num_steps", "description": "STEPSPARTPACKER - PartPacker steps"},
        "44": {"input_type": "integer", "field": "num_inference_steps", "description": "STEPSFLUX - FLUX steps"}
    }
    
    # Expected outputs
    expected_outputs = {
        "24": "EXPORT IMAGE - FLUX-generated image",
        "33": "EXPORTGLB - 3D mesh via PartPacker"
    }
    
    print("📋 Current Input Mapping:")
    for node_id, info in our_mapping.items():
        print(f"   Node #{node_id}: {info['description']}")
        print(f"      Input field: '{info['field']}' ({info['input_type']})")
    
    print(f"\n📤 Expected Outputs:")
    for node_id, desc in expected_outputs.items():
        print(f"   Node #{node_id}: {desc}")
    
    print(f"\n🔧 Potential Issues:")
    
    # Issue 1: Input field names
    print(f"\n1. 🎯 Input Field Names:")
    print(f"   Our fields: {[info['field'] for info in our_mapping.values()]}")
    print(f"   Common alternatives:")
    print(f"   - Image: 'image', 'input', 'input_image', 'source_image'")
    print(f"   - Text: 'text', 'prompt', 'input_text', 'conditioning'")
    print(f"   - Seed: 'noise_seed', 'seed', 'random_seed'")
    print(f"   - Steps: 'num_steps', 'steps', 'inference_steps'")
    
    # Issue 2: Node ID format
    print(f"\n2. 🔢 Node ID Format:")
    print(f"   We use: Strings like '16', '40', '41'")
    print(f"   Alternatives: Integers, descriptive names")
    
    # Issue 3: Required vs Optional
    print(f"\n3. ❗ Required vs Optional Inputs:")
    print(f"   We send all 6 inputs every time")
    print(f"   Some might be optional or have different requirements")
    
    # Issue 4: Input validation
    print(f"\n4. ✅ Input Validation:")
    print(f"   - Image: Must be valid Base64 data URI")
    print(f"   - Text: Both CLIP and T5XXL get same prompt")
    print(f"   - Steps: Very low (1) might be invalid")
    print(f"   - Seed: Standard integer")
    
    return our_mapping

def create_test_payloads():
    """Create different test payloads to try"""
    
    print(f"\n🧪 SUGGESTED TEST PAYLOADS")
    print("="*40)
    
    # Test 1: Only required inputs (guess)
    test1 = {
        "name": "Essential Only",
        "payload": {
            "16": {"inputs": {"image": "[BASE64_IMAGE]"}},
            "40": {"inputs": {"text": "simple cube"}},
            "41": {"inputs": {"text": "simple cube"}}
        }
    }
    
    # Test 2: Different field names
    test2 = {
        "name": "Alternative Field Names",
        "payload": {
            "16": {"inputs": {"input_image": "[BASE64_IMAGE]"}},
            "40": {"inputs": {"prompt": "simple cube"}},
            "41": {"inputs": {"prompt": "simple cube"}},
            "42": {"inputs": {"seed": 123}},
            "43": {"inputs": {"steps": 20}},
            "44": {"inputs": {"inference_steps": 10}}
        }
    }
    
    # Test 3: Higher step counts
    test3 = {
        "name": "Realistic Steps",
        "payload": {
            "16": {"inputs": {"image": "[BASE64_IMAGE]"}},
            "40": {"inputs": {"text": "simple cube"}},
            "41": {"inputs": {"text": "simple cube"}},
            "42": {"inputs": {"noise_seed": 123}},
            "43": {"inputs": {"num_steps": 20}},
            "44": {"inputs": {"num_inference_steps": 10}}
        }
    }
    
    tests = [test1, test2, test3]
    
    for i, test in enumerate(tests, 1):
        print(f"\n🧪 Test {i}: {test['name']}")
        print("   Payload structure:")
        for node_id, node_data in test['payload'].items():
            inputs = node_data['inputs']
            for field, value in inputs.items():
                if field == 'image':
                    print(f"      Node {node_id}.{field}: [Base64 image data]")
                else:
                    print(f"      Node {node_id}.{field}: {value}")
    
    return tests

def generate_diagnostic_script():
    """Generate a simplified test script"""
    
    script_content = '''"""
Quick node mapping test - copy/paste this into diagnose_deployment.py if needed
"""

async def test_specific_mapping():
    """Test our exact node mapping with better debugging"""
    
    # Your exact mapping from serverlessruncomfyinfo.txt
    test_overrides = {
        "16": {"inputs": {"image": "[REPLACE_WITH_BASE64]"}},      # INPUTIMAGE
        "40": {"inputs": {"text": "red cube"}},                    # FLUXCLIP  
        "41": {"inputs": {"text": "red cube"}},                    # FLUXT5XXL
        "42": {"inputs": {"noise_seed": 42}},                      # NOISESEED
        "43": {"inputs": {"num_steps": 20}},                       # STEPSPARTPACKER (higher value)
        "44": {"inputs": {"num_inference_steps": 10}}              # STEPSFLUX (higher value)
    }
    
    print("Testing exact node mapping from your workflow...")
    # Add this to your diagnostic script
'''
    
    print(f"\n💾 DIAGNOSTIC SCRIPT SNIPPET")
    print("="*40)
    print(script_content)

if __name__ == "__main__":
    analyze_node_mapping()
    create_test_payloads()
    generate_diagnostic_script()
    
    print(f"\n🎯 NEXT STEPS:")
    print("="*40)
    print("1. Run: python diagnose_deployment.py")
    print("2. Check RunComfy dashboard for deployment status")
    print("3. Download actual workflow JSON from RunComfy")
    print("4. Compare node IDs with our mapping")
    print("5. Test with higher step values (20+ instead of 1)")
    print("6. Verify the deployment is active and not paused")
