"""
Main controller (.exe entry point)
This is the main entry point for the CONJURE application.
It orchestrates the various components like the hand tracker, Blender,
and eventually the AI agent and GUI.
"""
# --- Add project root to sys.path ---
# This is necessary to ensure that local modules like 'comfyui' can be found
# when this script is run as the main entry point.
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -----------------------------------

# --- DEBUGGING: Print Python environment details ---
print("--- Python Environment ---")
print(f"Executable: {sys.executable}")
print("System Path:")
for p in sys.path:
    print(f"  - {p}")
print("--------------------------\n")
# -----------------------------------

import time
import atexit
import json
import uuid
from pathlib import Path
import shutil
import threading
import requests
from launcher.subprocess_manager import SubprocessManager
from launcher.state_manager import StateManager
from comfyui.api_wrapper import load_workflow, run_workflow, modify_workflow_paths
import launcher.config as config
from launcher.backend_agent import BackendAgent
# PHASE 1 SIMPLIFICATION: Removed conversational agent
# from conversational_agent import ConversationalAgent
from launcher.instruction_manager import InstructionManager
from launcher.voice_processor import VoiceProcessor

def select_generation_mode():
    """
    Prompt user to select generation mode: local, cloud, or debug.
    Returns the selected mode and updates config.
    """
    print("\n" + "="*60)
    print("🚀 CONJURE - Generation Mode Selection")
    print("="*60)
    print("Please choose your generation mode:")
    print()
    print("1. HUGGINGFACE - Use HuggingFace models (current implementation)")
    print("   • FLUX.1-dev and FLUX.1-Depth-dev")
    print("   • PartPacker for 3D generation")
    print("   • Requires: HUGGINGFACE_HUB_ACCESS_TOKEN")
    print()
    print("2. SERVERLESS - Use runComfy Serverless API (INSTANT, recommended)")
    print("   • ⚡ Instant generation (no server startup delays)")
    print("   • 💰 Pay only for execution time")
    print("   • 🚀 Auto-scaling, enterprise-grade infrastructure")
    print("   • 🎯 Unified FLUX + 3D mesh generation")
    print("   • Requires: runComfy API token and deployment")
    print()
    print("3. CLOUD      - Use runComfy legacy servers (slower startup)")
    print("   • Legacy server-based ComfyUI workflows")
    print("   • 30-90 second server startup delays")
    print("   • Manual server lifecycle management")
    print("   • Requires: runComfy account and credits")
    print()
    print("4. DEBUG      - Automated testing mode (serverless + speech input)")
    print("   • Tests all backend agent functions sequentially")
    print("   • spawn_primitive → generate_flux_mesh → segment_selection → fuse_mesh") 
    print("   • Uses runComfy serverless API for mesh generation")
    print("   • Conversational agent enabled - speak to update prompts contextually")
    print("   • Recursive segmentation loop for comprehensive testing")
    print()
    print("="*60)
    
    while True:
        try:
            choice = input("Enter your choice (1-4, or HUGGINGFACE/SERVERLESS/CLOUD/DEBUG): ").strip()
            
            if choice == "1" or choice.lower() == "huggingface":
                selected_mode = "local"  # Keep internal mode as "local" for backward compatibility
                print(f"✅ Selected: HUGGINGFACE mode (HuggingFace models)")
                break
            elif choice == "2" or choice.lower() == "serverless":
                selected_mode = "serverless"
                print(f"✅ Selected: SERVERLESS mode (runComfy Serverless API)")
                print("⚡ SERVERLESS: Instant generation with auto-scaling!")
                break
            elif choice == "3" or choice.lower() == "cloud":
                selected_mode = "cloud_legacy"
                print(f"✅ Selected: CLOUD LEGACY mode (runComfy servers)")
                print("⚠️  NOTE: Legacy server mode has longer startup times")
                break
            elif choice == "4" or choice.lower() == "debug":
                selected_mode = "debug"
                print(f"✅ Selected: DEBUG mode (automated testing)")
                print("🔬 DEBUG: Will test all backend agent functions automatically using serverless")
                break
            else:
                print("❌ Invalid choice. Please enter '1' for HUGGINGFACE, '2' for SERVERLESS, '3' for CLOUD, or '4' for DEBUG.")
                continue
                
        except KeyboardInterrupt:
            print("\n🛑 Setup cancelled by user")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error reading input: {e}")
            continue
    
    # Update the config module at runtime
    config.GENERATION_MODE = selected_mode
    
    print(f"🔧 Generation mode set to: {selected_mode.upper()}")
    print("="*60 + "\n")
    
    return selected_mode

class ConjureApp:
    def __init__(self, generation_mode="local"):
        print("Initializing CONJURE...")
        
        # 🧹 CLEAN SESSION: Reset transcript and prompt files
        print("🧹 Starting fresh session - cleaning transcript and prompt files...")
        from session_cleaner import clean_session
        clean_session()
        
        # Store generation mode
        self.generation_mode = generation_mode
        config.GENERATION_MODE = generation_mode  # Ensure config is updated
        
        # Debug mode handling
        self.is_debug_mode = (generation_mode == "debug")
        if self.is_debug_mode:
            # Set to serverless mode for actual operations (faster than legacy cloud)
            config.GENERATION_MODE = "serverless"
            print(f"🔧 Running in DEBUG mode (using SERVERLESS backend via runComfy)")
        else:
            print(f"🔧 Running in {generation_mode.upper()} mode")
        
        self.state_manager = StateManager()
        
        # 🧹 STARTUP CLEANUP: Clear any leftover requests from previous runs
        self.state_manager.reset_to_clean_state()
        
        # 🔧 Store generation mode in state file for API server access
        actual_mode = "serverless" if self.is_debug_mode else generation_mode
        self.state_manager.set_state("generation_mode", actual_mode)
        print(f"🔧 Generation mode stored in state file: {actual_mode}")
        
        self.subprocess_manager = SubprocessManager()
        self.instruction_manager = InstructionManager(self.state_manager)
        self.backend_agent = BackendAgent(instruction_manager=self.instruction_manager)
        
        # PHASE 2: Initialize voice processor for continuous prompt updates
        self.voice_processor = VoiceProcessor(backend_agent=self.backend_agent)
        
        # PHASE 1 SIMPLIFICATION: Removed conversational agent initialization
        # self.conversational_agent = ConversationalAgent(backend_agent=None)
        self.project_root = Path(__file__).parent.parent.resolve()
        
        # 🚦 Initialization tracking
        self.startup_time = time.time()
        self.initialization_complete = False
        self.startup_grace_period = 10  # seconds
        
        # 🎬 Demo automation timers
        self.demo_start_time = None
        self.last_mesh_import_time = None
        self.demo_flux_triggered = False
        self.last_flux_trigger_time = None
        self.segment_selection_forced = False
        
        # 📝 User prompt monitoring
        self.last_user_prompt = None
        self.user_prompt_path = self.project_root / "data" / "generated_text" / "userPrompt.txt"
        
        atexit.register(self.stop)
        
        print("CONJURE Agents are initialized.")

    def start(self):
        """Starts all the necessary components of the application."""
        print("CONJURE application starting...")
        self.state_manager.set_state("app_status", "running")

        # Start API server first
        self.subprocess_manager.start_api_server()
        print("Waiting for API server to initialize...")
        time.sleep(3)

        self.subprocess_manager.start_hand_tracker()
        self.state_manager.set_state("hand_tracker_status", "running")
        
        print("Waiting for hand tracker to initialize...")
        time.sleep(3)

        self.subprocess_manager.start_blender()
        self.state_manager.set_state("blender_status", "running")

        print("\nCONJURE is now running. Close the Blender window or press Ctrl+C here to exit.")

        # PHASE 1 SIMPLIFICATION: Removed conversational agent startup
        # self.agent_thread = threading.Thread(target=self.conversational_agent.start, daemon=True)
        # self.agent_thread.start()
        if self.is_debug_mode:
            print("🔬 DEBUG MODE: Simplified workflow without conversational agent")
        else:
            print("✅ CONJURE simplified workflow ready (no conversational agent)")
        
        # DISABLED: PyQt overlay UI (replaced with Blender viewport display)
        # self.start_ui_system()
        
        # 🚦 Mark initialization as complete
        self.initialization_complete = True
        print("✅ CONJURE initialization complete - ready to process requests")
        
        # 🔄 PHASE 2: Start voice processor for continuous prompt updates
        self.voice_processor.start()
        
        # 🔬 DEBUG MODE: Start automated testing
        if self.is_debug_mode:
            print("🔬 Initializing debug test mode...")
            self._ensure_runcomfy_dev_server()
            self.debug_test = DebugTestMode(self)
            # Wait a bit for systems to fully initialize
            threading.Timer(15.0, self.debug_test.start_debug_mode).start()
            print("🔬 Debug test mode will start in 15 seconds...")

    def _ensure_runcomfy_dev_server(self):
        """Ensure runComfy dev server is running for debug mode"""
        try:
            print("☁️ Checking runComfy dev server status...")
            
            # Try to import and check dev server state
            from runcomfy.dev_server_state import DevServerStateManager
            
            dev_manager = DevServerStateManager()
            server_state = dev_manager.load_server_state()
            
            if server_state and server_state.status == "running":
                print(f"✅ runComfy dev server is running (Server ID: {server_state.server_id})")
                return
            
            print("⚠️ runComfy dev server not running. Starting dev server...")
            print("🔬 DEBUG: You may need to manually start the runComfy dev server:")
            print("   python runcomfy/dev_server_startup.py")
            print("   Then restart debug mode")
            
        except ImportError:
            print("❌ runComfy components not available - cannot use cloud mode")
        except Exception as e:
            print(f"❌ Error checking runComfy dev server: {e}")

    def start_ui_system(self):
        """Start the CONJURE UI overlay as a separate process (simplest approach)"""
        print("🖥️  Starting CONJURE UI overlay...")
        
        try:
            import subprocess
            import platform
            
            # Path to the UI script (launch Phase 3 streamlined UI)
            ui_script = self.project_root / "Agent" / "conjure_ui.py"
            python_exe = sys.executable
            
            # Launch UI as completely separate process
            if platform.system() == "Windows":
                # On Windows, create detached process that won't interfere
                self.ui_process = subprocess.Popen(
                    [python_exe, str(ui_script)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # On other systems





                

                
                self.ui_process = subprocess.Popen(
                    [python_exe, str(ui_script)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            print("✅ CONJURE UI overlay launched as separate process")
            



        except Exception as e:
            print(f"⚠️  UI system error: {e}")
            import traceback
            traceback.print_exc()

    def check_for_requests(self):
        """Checks the state file for requests from Blender and triggers workflows."""
        # 🚦 STARTUP PROTECTION: Don't process requests during startup grace period
        if not self.initialization_complete:
            return
            
        time_since_startup = time.time() - self.startup_time
        if time_since_startup < self.startup_grace_period:
            if int(time_since_startup) % 2 == 0:  # Print every 2 seconds
                remaining = self.startup_grace_period - time_since_startup
                print(f"⏳ Startup grace period: {remaining:.1f}s remaining before processing requests")
            return
        
        # 🔄 PHASE 2: Continuous 30-second generation loop
        if self.demo_start_time is None:
            self.demo_start_time = time.time()
            print("🔄 PHASE 2: Started continuous generation loop (30s cycles)")
        
        state_data = self.state_manager.get_state()
        if not state_data:
            return

        # 🔄 PHASE 2: Continuous 30s cycles for generate_flux_mesh
        time_since_demo_start = time.time() - self.demo_start_time
        
        # Trigger generate_flux_mesh every 30 seconds
        should_trigger_flux = False
        if not self.demo_flux_triggered and time_since_demo_start >= 30:
            # First trigger after 30s
            should_trigger_flux = True
            print("🔄 PHASE 2: Initial 30 seconds elapsed - Starting generation loop!")
        elif self.last_flux_trigger_time and time.time() - self.last_flux_trigger_time >= 30:
            # Subsequent triggers every 30s after last one
            should_trigger_flux = True
            print("🔄 PHASE 2: 30 seconds since last generation - Continuing loop!")
        
        if should_trigger_flux:
            self._force_generate_flux_mesh()
            self.demo_flux_triggered = True
            self.last_flux_trigger_time = time.time()
        
        # After mesh import: immediate segment_selection
        if self.last_mesh_import_time is not None:
            time_since_import = time.time() - self.last_mesh_import_time
            print(f"🎬 DEBUG: Checking mesh import trigger - {time_since_import:.1f}s since import")
            if time_since_import >= 2:  # Just 2 seconds for immediate transition
                print("🎬 HARDCORE DEMO: Mesh imported - FORCING segment_selection!")
                self._force_segment_selection()
                self.last_mesh_import_time = None  # Reset to avoid repeated triggers
        
        # Recursive cycle: Every 30s in segment mode, generate new mesh
        if hasattr(self, '_last_segment_time') and self._last_segment_time is not None:
            time_since_segment = time.time() - self._last_segment_time
            if time_since_segment >= 30:
                print("🎬 HARDCORE DEMO: 30s in segment mode - RECURSIVE generate_flux_mesh!")
                self._force_generate_flux_mesh()
                self._last_segment_time = None  # Reset

        # 📝 Monitor userPrompt.txt for updates
        self._monitor_user_prompt_updates()
        # 🎬 BACKUP: Check for completed mesh files if API import failed
        self._check_for_completed_meshes()
        
        # 🎬 NUCLEAR OPTION: If 60s since flux trigger and no segment selection yet, FORCE IT
        if (self.last_flux_trigger_time is not None and 
            not self.segment_selection_forced and 
            time.time() - self.last_flux_trigger_time >= 60):
            print("🎬 NUCLEAR OPTION: 60s since flux trigger - FORCING SEGMENT SELECTION NO MATTER WHAT!")
            self._force_segment_selection()
            self.segment_selection_forced = True

        command = state_data.get("command")
        generation_mode = state_data.get("generation_mode", "standard")

        # Only show debug info when there are actual requests
        has_requests = (
            state_data.get("flux_pipeline_request") == "new" or
            state_data.get("generation_request") == "new" or
            state_data.get("selection_request") or
            command
        )
        
        if has_requests:
            print("🔍 DEBUG: Active requests detected!")
            print(f"   📋 Available commands: {list(state_data.keys())}")
            
            # 🎯 ENHANCED DEBUGGING: Backend Agent State Monitoring
            self._monitor_backend_agent_activity(state_data)
        
        # Check for FLUX pipeline request first (highest priority)
        flux_request = state_data.get("flux_pipeline_request")
        
        # DEBUG: Track flux_pipeline_request changes
        if not hasattr(self, '_last_flux_request'):
            self._last_flux_request = None
        
        if flux_request != self._last_flux_request:
            print(f"🔄 MAIN LOOP: flux_pipeline_request changed: '{self._last_flux_request}' → '{flux_request}'")
            self._last_flux_request = flux_request
        
        if flux_request == "new":
            print("🚀 DEBUG: FLUX pipeline request detected!")
            self.handle_flux_pipeline_request(state_data)
            self.state_manager.clear_specific_requests(["flux_pipeline_request"])
        
        # This part of the logic is now handled by the new agent system.
        # The old agent was triggered by Blender UI, the new one is voice-driven.
        # We'll keep the generation/selection logic as it's triggered by Blender/gestures.
        # if command == "agent_user_message":
        #     print(f"\nUser message received: {state_data.get('text')}")
        #     # First, clear the user message command so it doesn't get 
        # processed again.
        #     self.state_manager.clear_command()
        #     # Now, get the agent's response. The agent may issue a new command
        #     # to Blender by updating the state file itself.
        #     self.agent.get_response(state_data.get('text'))
        elif state_data.get("generation_request") == "new":
            print("🎨 DEBUG: Generation request detected!")
            self.handle_generation_request()
            self.state_manager.clear_specific_requests(["generation_request"])
        elif state_data.get("selection_request"):
            print("🎯 DEBUG: Selection request detected!")
            self.handle_selection_request(state_data, generation_mode)
            self.state_manager.clear_specific_requests(["selection_request", "selection_status"])

    def _monitor_user_prompt_updates(self):
        """📝 Monitor userPrompt.txt for updates and display in console"""
        try:
            if self.user_prompt_path.exists():
                with open(self.user_prompt_path, 'r', encoding='utf-8') as f:
                    current_prompt = f.read().strip()
                
                # Check if prompt has changed
                if current_prompt != self.last_user_prompt and current_prompt:
                    print("\n" + "🎨" + "="*80)
                    print("🎨 USER PROMPT UPDATED!")
                    print("🎨" + "="*80)
                    print(f"📝 NEW PROMPT: {current_prompt}")
                    print("🎨" + "="*80 + "\n")
                    
                    self.last_user_prompt = current_prompt
        except Exception as e:
            # Silently handle errors to avoid spam
            pass

    def _check_for_completed_meshes(self):
        """🎬 BACKUP: Check for newly generated mesh files and trigger import if needed"""
        try:
            mesh_dir = self.project_root / "data" / "generated_models" / "partpacker_results"
            if mesh_dir.exists():
                # Look for the most recent partpacker_result_0.glb file
                mesh_file = mesh_dir / "partpacker_result_0.glb"
                if mesh_file.exists():
                    # Check if this is a new file (modified in last 2 minutes)
                    import time
                    file_age = time.time() - mesh_file.stat().st_mtime
                    
                    if file_age < 120 and not hasattr(self, '_processed_backup_mesh'):  # 2 minutes
                        print("🎬 BACKUP DETECTION: Found fresh mesh file, triggering import and segment selection!")
                        
                        # Mark as processed to avoid repeated triggers
                        self._processed_backup_mesh = True
                        
                        # Directly call import API
                        try:
                            import httpx
                            with httpx.Client(timeout=30.0) as client:
                                response = client.post(
                                    "http://127.0.0.1:8000/blender/import_mesh",
                                    json={
                                        "mesh_path": str(mesh_file),
                                        "min_volume_threshold": 0.01
                                    }
                                )
                                if response.status_code == 200:
                                    print("✅ BACKUP: Mesh import API call successful!")
                                    print("🎬 FORCING SEGMENT SELECTION IN 3 SECONDS...")
                                    # Trigger segment selection immediately
                                    time.sleep(3)  # Give import time to complete
                                    self._force_segment_selection()
                                    print("🎬 BACKUP: SEGMENT SELECTION FORCED!")
                                    # Track this as successful import for main automation
                                    self.last_mesh_import_time = time.time()
                                else:
                                    print(f"❌ BACKUP: Import API failed with {response.status_code}")
                                    # FUCK IT - FORCE SEGMENT SELECTION ANYWAY
                                    print("🎬 FUCK IT - FORCING SEGMENT SELECTION ANYWAY!")
                                    self._force_segment_selection()
                        except Exception as e:
                            print(f"❌ BACKUP: Import failed: {e}")
        except Exception as e:
            # Silently handle errors
            pass

    def _force_generate_flux_mesh(self):
        """🔄 PHASE 2: Trigger generate_flux_mesh with current user prompt"""
        try:
            # Read prompt from user_prompt.txt
            prompt_path = self.project_root / "data" / "generated_text" / "userPrompt.txt"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                print(f"📄 Using prompt from userPrompt.txt: {prompt[:100]}...")
            else:
                # Fallback prompt
                prompt = "A detailed futuristic robot head with metallic surfaces, studio lighting, high definition, professional photography"
                print("⚠️  userPrompt.txt not found, using fallback prompt")
            
            # Create instruction and execute it
            instruction = {
                "tool_name": "generate_flux_mesh",
                "parameters": {
                    "prompt": prompt,
                    "seed": 1337,
                    "min_volume_threshold": 0.01
                }
            }
            
            print("🔄 PHASE 2: Executing generate_flux_mesh instruction...")
            self.instruction_manager.execute_instruction(instruction)
            
        except Exception as e:
            print(f"❌ PHASE 2: Error triggering generate_flux_mesh: {e}")
    
    def _force_segment_selection(self):
        """🎬 DEMO AUTOMATION: Force segment_selection mode"""
        try:
            instruction = {
                "tool_name": "segment_selection",
                "parameters": {}
            }
            
            print("🎬 DEMO: Executing segment_selection instruction...")
            self.instruction_manager.execute_instruction(instruction)
            
            # Track when segment selection starts for recursive timing
            self._last_segment_time = time.time()
            self.segment_selection_forced = True  # Mark that we've achieved segment selection
            print("🎬 HARDCORE DEMO: Segment selection started - next mesh generation in 30s")
            
        except Exception as e:
            print(f"❌ DEMO AUTOMATION: Error forcing segment_selection: {e}")

    def check_for_shutdown_signal(self):
        """Check for shutdown signal file from UI overlay"""
        try:
            shutdown_file = self.project_root / "shutdown_signal.txt"
            
            # Add occasional debug info (every 30 checks)
            if not hasattr(self, '_shutdown_check_count'):
                self._shutdown_check_count = 0
            self._shutdown_check_count += 1
            
            if self._shutdown_check_count % 10 == 0:  # More frequent debugging
                print(f"🔍 DEBUG: Checking for shutdown signal at: {shutdown_file}")
            
            if shutdown_file.exists():
                print("🛑 Shutdown signal detected from UI overlay")
                
                # Read the signal file for details
                try:
                    with open(shutdown_file, 'r') as f:
                        signal_content = f.read()
                    print(f"📄 Shutdown signal content: {signal_content.strip()}")
                except:
                    pass
                
                # Remove the signal file
                try:
                    shutdown_file.unlink()
                    print("🗑️  Shutdown signal file removed")
                except:
                    pass
                
                # Trigger graceful shutdown
                print("🛑 Initiating graceful CONJURE shutdown...")
                self.state_manager.set_state("app_status", "shutting_down")
                
        except Exception as e:
            # Occasionally print errors for debugging
            if hasattr(self, '_shutdown_check_count') and self._shutdown_check_count % 60 == 0:
                print(f"⚠️ DEBUG: Shutdown signal check error: {e}")

    def _monitor_backend_agent_activity(self, state_data):
        """Monitor and report backend agent activity and outputs."""
        print("\n" + "-"*60)
        print("🧠 MAIN.PY: BACKEND AGENT ACTIVITY MONITOR")
        print("-"*60)
        
        # Check for backend agent generated files
        try:
            # Check for vision description
            vision_path = self.project_root / "screen_description.txt"
            if vision_path.exists():
                with open(vision_path, 'r', encoding='utf-8') as f:
                    vision_content = f.read()
                print(f"👁️ Current Vision: {vision_content[:150]}...")
            
            # Check for generated FLUX prompt  
            prompt_path = self.project_root / "data" / "generated_text" / "userPrompt.txt"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_content = f.read()
                print(f"🎨 Current FLUX Prompt: {prompt_content[:150]}...")
                
            # Analyze state for backend agent commands
            backend_commands = []
            for key, value in state_data.items():
                if key in ["command", "generation_request", "selection_request", "flux_pipeline_request"]:
                    if value and value != "null":
                        backend_commands.append(f"{key}: {value}")
            
            if backend_commands:
                print(f"⚙️ Active Backend Commands: {', '.join(backend_commands)}")
            else:
                print("💤 No active backend commands")
                
        except Exception as e:
            print(f"⚠️ Error monitoring backend agent activity: {e}")
            
        print("-"*60)
        print("🔚 END BACKEND AGENT ACTIVITY MONITOR")
        print("-"*60 + "\n")

    def handle_generation_request(self):
        """Handles the request to generate initial concept options."""
        print("--- Detected Generation Request ---")
        
        source_render_path = self.project_root / "data" / "generated_images" / "gestureCamera" / "render.png"
        comfyui_input_path = config.COMFYUI_ROOT_PATH / "input" / "render.png"
        
        try:
            print(f"Copying {source_render_path} to {comfyui_input_path}...")
            shutil.copy(source_render_path, comfyui_input_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy render.png to ComfyUI input: {e}")
            return

        workflow_path = self.project_root / "comfyui" / "workflows" / "promptMaker.json"
        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print("ERROR: Could not load promptMaker workflow.")
            return

        output_dir_abs = self.project_root / "data" / "generated_images" / "imageOPTIONS"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
        modifications = {
            "139": {"output_path": str(output_dir_abs)},
            "142": {"output_path": str(output_dir_abs)},
            "143": {"output_path": str(output_dir_abs)},
        }
        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print("--- promptMaker.json workflow completed successfully. ---")
        else:
            print("--- ERROR: promptMaker.json workflow failed. ---")

        self.reset_state_file({"generation_request": "done"})

    def handle_selection_request(self, state_data, mode):
        """Handles the request to process a selected option and generate a 3D model."""
        option_index = state_data["selection_request"]
        print(f"--- Detected Selection Request for Option {option_index} (Mode: {mode.upper()}) ---")

        try:
            source_option_path = self.project_root / "data" / "generated_images" / "imageOPTIONS" / f"OP{option_index}.png"
            dest_selected_path = config.COMFYUI_ROOT_PATH / "input" / "selectedOption.png"
            print(f"Copying {source_option_path} to {dest_selected_path}...")
            shutil.copy(source_option_path, dest_selected_path)

            mv_render_dir = self.project_root / "data" / "generated_images" / "multiviewRender"
            for view_file in os.listdir(mv_render_dir):
                source_path = mv_render_dir / view_file
                dest_path = config.COMFYUI_ROOT_PATH / "input" / view_file
                print(f"Copying {source_path} to {dest_path}...")
                shutil.copy(source_path, dest_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy input files to ComfyUI: {e}")
            self.reset_state_file({"selection_status": "failed"})
            return
            
        # --- 2. Load and Modify mv2mv Workflow ---
        if mode == 'turbo':
            workflow_name = f"mv2mv{option_index}turbo.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "turbo"
        else: # standard
            workflow_name = f"mv2mv{option_index}.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "standard"

        workflow_path = workflow_dir / workflow_name
        
        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print(f"ERROR: Could not load {workflow_path}.")
            self.reset_state_file({"selection_status": "failed"})
            return

        prompt_path_abs = self.project_root / "data" / "generated_text" / "userPrompt.txt"
        output_dir_abs = self.project_root / "data" / "generated_images" / "mvResults"
        output_dir_abs.mkdir(parents=True, exist_ok=True)
        
        print(f"Cleaning output directory: {output_dir_abs}")
        for f in output_dir_abs.glob('*.*'):
            try:
                if f.is_file():
                    f.unlink()
            except OSError as e:
                print(f"Error deleting file {f}: {e}")

        if mode == 'turbo':
            modifications = {
                "120": {"file_path": str(prompt_path_abs)}, 
                "165": {"output_path": str(output_dir_abs), "filename_prefix": "mv_1"},
                "187": {"output_path": str(output_dir_abs), "filename_prefix": "mv_3"},
                "164": {"output_path": str(output_dir_abs), "filename_prefix": "mv_4"},
            }
        else:
            modifications = {
                "120": {"file_path": str(prompt_path_abs)},
                "124": {"output_path": str(output_dir_abs)},
            }

        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            self.handle_3d_generation(mode)
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            self.reset_state_file({"selection_status": "failed"})

    def handle_3d_generation(self, mode):
        print(f"--- Detected 3D Generation Request (Mode: {mode.upper()}) ---")

        print("Copying latest mvResults to ComfyUI input...")
        mv_results_dir = self.project_root / "data" / "generated_images" / "mvResults"
        try:
            for view_file in os.listdir(mv_results_dir):
                source_path = mv_results_dir / view_file
                dest_path = config.COMFYUI_ROOT_PATH / "input" / view_file
                print(f"  -> Copying {source_path} to {dest_path}")
                shutil.copy(source_path, dest_path)
        except (IOError, FileNotFoundError) as e:
            print(f"ERROR: Could not copy mvResult files to ComfyUI: {e}")
            self.reset_state_file({"3d_generation_request": "failed"})
            return
            
        if mode == 'turbo':
            workflow_name = "mv23Dturbo.json"
            workflow_dir = self.project_root / "comfyui" / "workflows" / "turbo"
        else:
            workflow_name = "mv23D.json"
            workflow_dir = self.project_root / "comfyui" / "workflows"

        workflow_path = workflow_dir / workflow_name
        if not workflow_path.exists():
            print(f"--- ERROR: Workflow file not found at {workflow_path} ---")
            self.reset_state_file({"3d_generation_request": "failed"})
            return

        workflow = load_workflow(str(workflow_path))
        if not workflow:
            print(f"--- ERROR: Could not load workflow from {workflow_path} ---")
            self.reset_state_file({"3d_generation_request": "failed"})
            return

        modifications = {
            "13": {"filename_prefix": "CONJURE/copyMesh"}
        }
        workflow = modify_workflow_paths(workflow, modifications)

        client_id = f"conjure_launcher_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)
        if success:
            print(f"--- {workflow_name} workflow completed successfully. ---")
            
            try:
                output_dir = config.COMFYUI_CONJURE_OUTPUT_PATH
                output_dir.mkdir(parents=True, exist_ok=True)

                list_of_files = list(output_dir.glob('*.glb'))
                if not list_of_files:
                    raise FileNotFoundError("No .glb files found in the ComfyUI CONJURE output directory.")
                
                latest_file = max(list_of_files, key=lambda p: p.stat().st_mtime)
                print(f"Found latest generated model: {latest_file}")

                destination_dir = self.project_root / "data" / "generated_models"
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination_path = destination_dir / "genMesh.glb"

                shutil.copy(latest_file, destination_path)
                print(f"Copied model to {destination_path}")

            except Exception as e:
                print(f"ERROR: Could not copy generated model: {e}")
                self.reset_state_file({"3d_generation_request": "failed"})
                return

            self.reset_state_file({"import_request": "new"})
        else:
            print(f"--- ERROR: {workflow_name} workflow failed. ---")
            self.reset_state_file({"3d_generation_request": "failed"})

    def handle_flux_pipeline_request(self, state_data):
        """
        Handle the complete FLUX1.DEPTH -> PartPacker -> Import pipeline
        """
        prompt = state_data.get("flux_prompt", "")
        seed = state_data.get("flux_seed", 0)
        min_volume_threshold = state_data.get("min_volume_threshold", 0.001)
        
        print("🚀 --- Starting FLUX Pipeline ---")
        print(f"📝 Prompt: {prompt}")
        print(f"🎲 Seed: {seed}")
        print(f"🔍 Min volume threshold: {min_volume_threshold}")
        
        try:
            # Step 1: Generate FLUX1.DEPTH image
            print("🎨 Step 1: Generating FLUX1.DEPTH image...")
            print("📡 DEBUG: About to call FLUX1.DEPTH API...")
            flux_result = self.call_flux_depth_api(prompt, seed)
            if not flux_result:
                print("❌ FLUX1.DEPTH generation failed")
                self.reset_state_file({"flux_pipeline_status": "failed"})
                return
            
            flux_image_path = flux_result["image_path"]
            print(f"✅ FLUX1.DEPTH completed: {flux_image_path}")
            
            # Step 2: Generate 3D model with PartPacker
            print("🏗️ Step 2: Generating 3D model with PartPacker...")
            print("📡 DEBUG: About to call PartPacker API...")
            partpacker_result = self.call_partpacker_api(flux_image_path, seed)
            if not partpacker_result:
                print("❌ PartPacker generation failed")
                self.reset_state_file({"flux_pipeline_status": "failed"})
                return
            
            model_path = partpacker_result["model_path"]
            print(f"✅ PartPacker completed: {model_path}")
            
            # Step 3: Import mesh into Blender
            print("📦 Step 3: Importing mesh into Blender...")
            print("📡 DEBUG: About to call mesh import API...")
            import_result = self.call_mesh_import_api(model_path, min_volume_threshold)
            if not import_result:
                print("❌ Mesh import failed")
                self.reset_state_file({"flux_pipeline_status": "failed"})
                return
            
            print("✅ Mesh import completed")
            
            # 🎬 DEMO AUTOMATION: Record mesh import time for segment selection trigger
            self.last_mesh_import_time = time.time()
            print("🎬 DEMO AUTOMATION: Mesh import completed - segment selection will trigger in 2s")
            print(f"🎬 DEMO AUTOMATION: Current time: {time.time()}, Import time: {self.last_mesh_import_time}")
            
            print("🎉 --- FLUX Pipeline Completed Successfully ---")
            self.reset_state_file({"flux_pipeline_status": "completed"})
            
        except Exception as e:
            print(f"❌ Error in FLUX pipeline: {e}")
            import traceback
            print(f"🔍 Full error traceback:\n{traceback.format_exc()}")
            self.reset_state_file({"flux_pipeline_status": "failed"})
    
    def call_flux_depth_api(self, prompt, seed):
        """Call the FLUX1.DEPTH API via our FastAPI server"""
        print("📡 DEBUG: FLUX1.DEPTH API call starting...")
        try:
            import httpx
            
            # Path to the GestureCamera render
            render_path = self.project_root / "data" / "generated_images" / "gestureCamera" / "render.png"
            print(f"🖼️ DEBUG: Using control image: {render_path}")
            
            if not render_path.exists():
                print(f"❌ GestureCamera render not found: {render_path}")
                return None
            
            # Prepare request data
            request_data = {
                "control_image_path": str(render_path),
                "prompt": prompt,
                "seed": seed,
                "randomize_seed": False,  # Use fixed seed
                "width": 1024,
                "height": 1024,
                "guidance_scale": 10,
                "num_inference_steps": 28
            }
            
            print(f"📝 DEBUG: Request data prepared: {request_data}")
            
            # Call our FastAPI server
            print("🌐 DEBUG: Making HTTP request to FastAPI server...")
            with httpx.Client(timeout=300.0) as client:  # 5-minute timeout for generation
                response = client.post("http://127.0.0.1:8000/flux/depth", json=request_data)
                print(f"📶 DEBUG: HTTP response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"📄 DEBUG: Response data: {result}")
                    if result["success"]:
                        print("✅ DEBUG: FLUX1.DEPTH API call successful!")
                        # The image is now saved as data/generated_images/flux/flux.png
                        return {
                            "image_path": str(self.project_root / "data" / "generated_images" / "flux" / "flux.png"),
                            "seed_used": result["data"]["seed_used"]
                        }
                    else:
                        print(f"❌ FLUX1.DEPTH API error: {result['message']}")
                        return None
                else:
                    print(f"❌ HTTP error {response.status_code}: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error calling FLUX1.DEPTH API: {e}")
            import traceback
            print(f"🔍 Full traceback:\n{traceback.format_exc()}")
            return None
    
    def call_partpacker_api(self, image_path, seed):
        """Call the PartPacker API via our FastAPI server"""
        print("📡 DEBUG: PartPacker API call starting...")
        try:
            import httpx
            
            print(f"🖼️ DEBUG: Using input image: {image_path}")
            
            # Prepare request data
            request_data = {
                "image_path": image_path,
                "num_steps": 50,
                "cfg_scale": 7,
                "grid_res": 384,
                "seed": seed,
                "simplify_mesh": False,
                "target_num_faces": 100000
            }
            
            print(f"📝 DEBUG: Request data prepared: {request_data}")
            
            # Call our FastAPI server
            print("🌐 DEBUG: Making HTTP request to FastAPI server...")
            with httpx.Client(timeout=600.0) as client:  # 10-minute timeout for 3D generation
                response = client.post("http://127.0.0.1:8000/partpacker/generate_3d", json=request_data)
                print(f"📶 DEBUG: HTTP response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"📄 DEBUG: Response data: {result}")
                    if result["success"]:
                        print("✅ DEBUG: PartPacker API call successful!")
                        return result["data"]
                    else:
                        print(f"❌ PartPacker API error: {result['message']}")
                        return None
                else:
                    print(f"❌ HTTP error {response.status_code}: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error calling PartPacker API: {e}")
            import traceback
            print(f"🔍 Full traceback:\n{traceback.format_exc()}")
            return None
    
    def call_mesh_import_api(self, mesh_path, min_volume_threshold):
        """Call the mesh import API via our FastAPI server"""
        print("📡 DEBUG: Mesh import API call starting...")
        try:
            import httpx
            
            print(f"📦 DEBUG: Using mesh file: {mesh_path}")
            
            # Prepare request data
            request_data = {
                "mesh_path": mesh_path,
                "min_volume_threshold": min_volume_threshold
            }
            
            print(f"📝 DEBUG: Request data prepared: {request_data}")
            
            # Call our FastAPI server
            print("🌐 DEBUG: Making HTTP request to FastAPI server...")
            with httpx.Client(timeout=60.0) as client:  # 1-minute timeout for import
                response = client.post("http://127.0.0.1:8000/blender/import_mesh", json=request_data)
                print(f"📶 DEBUG: HTTP response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"📄 DEBUG: Response data: {result}")
                    if result["success"]:
                        print("✅ DEBUG: Mesh import API call successful!")
                        return result["data"]
                    else:
                        print(f"❌ Mesh import API error: {result['message']}")
                        return None
                else:
                    print(f"❌ HTTP error {response.status_code}: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error calling mesh import API: {e}")
            import traceback
            print(f"🔍 Full traceback:\n{traceback.format_exc()}")
            return None

    def reset_state_file(self, data_to_update: dict):
        """
        Updates the state file with the given data, preserving existing keys.
        """
        self.state_manager.update_state(data_to_update)
        print("State file has been updated.")

    def run(self):
        """Main application loop."""
        self.start()
        
        # Add a debug counter to avoid spam
        debug_counter = 0
        grace_period_announced = False
        
        try:
            print("🔄 Main application loop started - checking for requests every second")
            while self.state_manager.get_state().get("app_status") == "running":
                # Handle grace period messaging
                time_since_startup = time.time() - self.startup_time
                if not self.initialization_complete or time_since_startup < self.startup_grace_period:
                    if not grace_period_announced:
                        print(f"⏳ Startup grace period active - {self.startup_grace_period}s delay before processing requests")
                        grace_period_announced = True
                    # Show remaining time every 2 seconds during grace period
                    if int(time_since_startup) % 2 == 0:
                        remaining = max(0, self.startup_grace_period - time_since_startup)
                        if remaining > 0:
                            print(f"⏳ Grace period: {remaining:.1f}s remaining...")
                        elif not hasattr(self, '_grace_complete_announced'):
                            print("✅ Startup grace period complete - now monitoring for requests")
                            self._grace_complete_announced = True
                else:
                    # Normal operation - periodic heartbeat (every 30 seconds)
                    if debug_counter % 30 == 0:
                        print("💓 Main loop heartbeat - application running normally")
                
                self.check_for_requests()
                
                # DISABLED: UI shutdown signal check (overlay UI disabled)
                # self.check_for_shutdown_signal()
                
                time.sleep(1)
                debug_counter += 1
                
        except KeyboardInterrupt:
            print("\n⚠️ Keyboard interrupt received - shutting down CONJURE...")
        except Exception as e:
            print(f"\n❌ Unexpected error in main loop: {e}")
            import traceback
            print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        finally:
            self.stop()

    def stop(self):
        """Stops all components and cleans up resources."""
        print("\n🛑 CONJURE is shutting down...")
        
        # 🔬 DEBUG MODE: Stop debug testing
        if self.is_debug_mode and hasattr(self, 'debug_test'):
            print("🔬 Stopping debug test mode...")
            self.debug_test.stop_debug_mode()
        
        # 🧹 SHUTDOWN CLEANUP: Clear all pending requests to prevent issues on next startup
        print("🧹 Cleaning up state before shutdown...")
        self.state_manager.clear_all_requests()
        
        # Stop all subprocesses
        if hasattr(self, 'subprocess_manager'):
            print("🔌 Stopping all subprocesses...")
            self.subprocess_manager.stop_all()
        
        # 🔄 PHASE 2: Stop voice processor
        if hasattr(self, 'voice_processor'):
            print("🎤 Stopping voice processor...")
            self.voice_processor.stop()
        
        # PHASE 1 SIMPLIFICATION: No conversational agent to stop
        # if hasattr(self, 'conversational_agent'):
        #     print("🎤 Stopping conversational agent...")
        #     self.conversational_agent.stop()
        
        # Stop UI system (if it was started)
        if hasattr(self, 'ui_process') and self.ui_process:
            print("🖥️  Stopping UI overlay process...")
            try:
                self.ui_process.terminate()
                self.ui_process.wait(timeout=5)
                print("✅ UI overlay process stopped")
            except Exception as e:
                print(f"⚠️  Error stopping UI overlay: {e}")
                try:
                    self.ui_process.kill()
                except:
                    pass
        else:
            print("ℹ️  UI overlay was not running (disabled)")
        
        print("✅ CONJURE shutdown complete")


class DebugTestMode:
    """
    Automated debug testing mode that cycles through all backend agent functions.
    Tests the complete workflow: spawn_primitive → generate_flux_mesh → segment_selection → fuse_mesh
    """
    
    def __init__(self, conjure_app):
        self.app = conjure_app
        self.step_delay = 15  # seconds between steps
        self.segment_selection_duration = 10  # seconds to stay in segment selection
        self.current_cycle = 0
        self.max_cycles = 3  # Maximum number of recursive cycles
        
        # Test sequence steps
        self.test_sequence = [
            ("spawn_primitive", self.test_spawn_primitive),
            ("generate_flux_mesh", self.test_generate_flux_mesh),
            ("segment_selection", self.test_segment_selection),
            ("fuse_mesh", self.test_fuse_mesh),
        ]
        self.current_step = 0
        self.debug_running = False
        
    def start_debug_mode(self):
        """Start the automated debug testing sequence"""
        print("\n" + "🔬" + "="*70)
        print("🔬 STARTING DEBUG TEST MODE")
        print("🔬" + "="*70)
        print("📋 Test Sequence:")
        print("   1. spawn_primitive (Sphere)")
        print("   2. generate_flux_mesh (from user_prompt.txt)")
        print("   3. segment_selection (10s interactive mode)")
        print("   4. fuse_mesh (combine segments)")
        print("   5. [RECURSIVE] - Repeat from segment_selection")
        print(f"🔄 Will run {self.max_cycles} complete cycles")
        print("🔬" + "="*70 + "\n")
        
        self.debug_running = True
        # Start the debug sequence in a separate thread
        debug_thread = threading.Thread(target=self._run_debug_sequence, daemon=True)
        debug_thread.start()
        
    def _run_debug_sequence(self):
        """Run the complete debug test sequence"""
        try:
            while self.debug_running and self.current_cycle < self.max_cycles:
                self.current_cycle += 1
                print(f"\n🔬 === DEBUG CYCLE {self.current_cycle}/{self.max_cycles} ===")
                
                for step_name, step_function in self.test_sequence:
                    if not self.debug_running:
                        break
                        
                    print(f"\n🔬 Step {self.current_step + 1}: {step_name}")
                    print("⏳ Executing...")
                    
                    try:
                        step_function()
                        print(f"✅ {step_name} completed successfully")
                    except Exception as e:
                        print(f"❌ {step_name} failed: {e}")
                    
                    self.current_step = (self.current_step + 1) % len(self.test_sequence)
                    
                    # Wait before next step
                    if self.debug_running:
                        print(f"⏱️  Waiting {self.step_delay}s before next step...")
                        time.sleep(self.step_delay)
                
                if self.current_cycle < self.max_cycles:
                    print(f"\n🔄 Cycle {self.current_cycle} complete. Starting recursive cycle...")
                    time.sleep(5)
            
            print(f"\n🔬 === DEBUG TESTING COMPLETE ===")
            print(f"✅ Completed {self.current_cycle} cycles successfully")
            print("🔬 Debug mode finished. Regular operation continues...\n")
            
        except Exception as e:
            print(f"❌ Debug sequence error: {e}")
            import traceback
            print(f"🔍 Debug traceback:\n{traceback.format_exc()}")
        finally:
            self.debug_running = False
    
    def test_spawn_primitive(self):
        """Test spawn_primitive with Sphere"""
        print("🔮 Testing spawn_primitive: Creating Sphere...")
        
        instruction = {
            "tool_name": "spawn_primitive",
            "parameters": {"primitive_type": "Sphere"}
        }
        
        # Send via API
        import requests
        response = requests.post("http://127.0.0.1:8000/execute_instruction",
                               json={"instruction": instruction},
                               timeout=30)
        
        if response.status_code == 200:
            print("✅ spawn_primitive API call successful")
        else:
            raise Exception(f"spawn_primitive API call failed: {response.status_code}")
    
    def test_generate_flux_mesh(self):
        """Test generate_flux_mesh using user_prompt.txt"""
        print("🎨 Testing generate_flux_mesh: Using user_prompt.txt...")
        
        # Read prompt from user_prompt.txt
        prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()
            print(f"📄 Using prompt: {prompt[:100]}...")
        else:
            # Fallback prompt
            prompt = "A detailed futuristic robot head with metallic surfaces, studio lighting, high definition, professional photography"
            print("⚠️  user_prompt.txt not found, using fallback prompt")
        
        instruction = {
            "tool_name": "generate_flux_mesh",
            "parameters": {
                "prompt": prompt,
                "seed": 1337 + self.current_cycle,  # Different seed each cycle
                "min_volume_threshold": 0.01
            }
        }
        
        # Send via API
        import requests
        response = requests.post("http://127.0.0.1:8000/execute_instruction",
                               json={"instruction": instruction},
                               timeout=120)  # Longer timeout for generation
        
        if response.status_code == 200:
            print("✅ generate_flux_mesh API call successful")
            print("⏳ Waiting for mesh generation and import to complete...")
            # Wait extra time for the full pipeline
            time.sleep(30)
        else:
            raise Exception(f"generate_flux_mesh API call failed: {response.status_code}")
    
    def test_segment_selection(self):
        """Test segment_selection mode"""
        print("👆 Testing segment_selection: Entering interactive selection mode...")
        
        instruction = {
            "tool_name": "segment_selection",
            "parameters": {}
        }
        
        # Send via API
        import requests
        response = requests.post("http://127.0.0.1:8000/execute_instruction",
                               json={"instruction": instruction},
                               timeout=30)
        
        if response.status_code == 200:
            print("✅ segment_selection API call successful")
            print(f"⏱️  Staying in segment selection mode for {self.segment_selection_duration}s...")
            print("👆 Point at mesh segments with your finger during this time!")
            time.sleep(self.segment_selection_duration)
        else:
            raise Exception(f"segment_selection API call failed: {response.status_code}")
    
    def test_fuse_mesh(self):
        """Test fuse_mesh operation"""
        print("🔗 Testing fuse_mesh: Combining all segments...")
        
        instruction = {
            "tool_name": "fuse_mesh",
            "parameters": {}
        }
        
        # Send via API
        import requests
        response = requests.post("http://127.0.0.1:8000/execute_instruction",
                               json={"instruction": instruction},
                               timeout=30)
        
        if response.status_code == 200:
            print("✅ fuse_mesh API call successful")
        else:
            raise Exception(f"fuse_mesh API call failed: {response.status_code}")
    
    def stop_debug_mode(self):
        """Stop the debug testing sequence"""
        print("🛑 Stopping debug test mode...")
        self.debug_running = False


if __name__ == "__main__":
    # First, let user select generation mode
    selected_mode = select_generation_mode()
    
    # Initialize app with selected mode
    app = ConjureApp(generation_mode=selected_mode)
    app.run() 