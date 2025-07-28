"""
Simple import test for CONJURE modules
Helps diagnose import issues without initializing complex objects
"""
import sys
import os

# Add paths
project_root = os.path.dirname(os.path.abspath(__file__))
launcher_dir = os.path.join(project_root, 'launcher')
sys.path.insert(0, project_root)
sys.path.insert(0, launcher_dir)

def test_imports():
    """Test importing CONJURE modules step by step."""
    print("🧪 Testing CONJURE Module Imports")
    print("=" * 50)
    
    # Test basic Python setup
    print(f"📁 Project root: {project_root}")
    print(f"📁 Launcher dir: {launcher_dir}")
    print(f"🐍 Python version: {sys.version}")
    print()
    
    # Test each module individually
    modules_to_test = [
        ("launcher.state_manager", "StateManager"),
        ("launcher.instruction_manager", "InstructionManager"), 
        ("launcher.backend_agent", "BackendAgent"),
        ("launcher.conversational_agent", "ConversationalAgent"),
        ("launcher.api_server", None),  # No specific class to test
        ("launcher.main", "ConjureApp"),
    ]
    
    successful_imports = []
    failed_imports = []
    
    for module_name, class_name in modules_to_test:
        try:
            print(f"🔍 Testing {module_name}...")
            
            # Try to import the module
            module = __import__(module_name, fromlist=[class_name] if class_name else [])
            print(f"   ✅ Module imported successfully")
            
            # Try to access the class if specified
            if class_name:
                cls = getattr(module, class_name)
                print(f"   ✅ Class {class_name} found")
            
            successful_imports.append(module_name)
            
        except ImportError as e:
            print(f"   ❌ Import error: {e}")
            failed_imports.append((module_name, str(e)))
        except AttributeError as e:
            print(f"   ❌ Attribute error: {e}")
            failed_imports.append((module_name, str(e)))
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            failed_imports.append((module_name, str(e)))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 IMPORT TEST SUMMARY")
    print("=" * 50)
    
    print(f"✅ Successful imports: {len(successful_imports)}")
    for module in successful_imports:
        print(f"   - {module}")
    
    if failed_imports:
        print(f"\n❌ Failed imports: {len(failed_imports)}")
        for module, error in failed_imports:
            print(f"   - {module}: {error}")
    else:
        print("\n🎉 All imports successful!")
    
    return len(failed_imports) == 0

def test_environment():
    """Test environment setup."""
    print("\n🌍 Environment Test")
    print("=" * 30)
    
    # Check file existence
    files_to_check = [
        "launcher/state_manager.py",
        "launcher/instruction_manager.py",
        "launcher/backend_agent.py", 
        "launcher/conversational_agent.py",
        "launcher/api_server.py",
        "launcher/main.py",
        "requirements.txt",
        "data/input/state.json"
    ]
    
    for file_path in files_to_check:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (missing)")
    
    # Check for key dependencies
    print("\n🔧 Key Dependencies")
    print("-" * 20)
    
    dependencies = [
        "elevenlabs",
        "openai", 
        "fastapi",
        "uvicorn",
        "httpx",
        "pyaudio",
        "mediapipe"
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} (not installed)")

def main():
    """Run all tests."""
    print("🔧 CONJURE Import Diagnostic Tool")
    print("=" * 50)
    
    # Test environment
    test_environment()
    
    # Test imports
    print("\n")
    success = test_imports()
    
    if success:
        print("\n🎯 Next steps:")
        print("✅ All imports working - you can now run debug_conversation.py")
        print("✅ Try: python debug_conversation.py")
    else:
        print("\n🔧 Troubleshooting:")
        print("1. Check that all files exist in the launcher/ directory")
        print("2. Install missing dependencies: pip install -r requirements.txt")
        print("3. Make sure you're running from the project root directory")
        print("4. Check for syntax errors in the failed modules")

if __name__ == "__main__":
    main() 