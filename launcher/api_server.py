"""
CONJURE FastAPI Server
Central API server for coordinating all CONJURE components.
Replaces direct function calls with HTTP API endpoints.
"""
# --- Add project root to sys.path ---
# This is necessary to ensure that local modules can be found
# when this script is run as a subprocess or entry point.
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -----------------------------------

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uvicorn
import asyncio
import os
import tempfile
import shutil
import json
import hashlib
import time
from pathlib import Path
# Gradio client will be handled by generation services

# Import existing managers (DO NOT MODIFY THESE)
from state_manager import StateManager
from instruction_manager import InstructionManager
from backend_agent import BackendAgent
import launcher.config as config
from generation_services import get_generation_service

# Import progress tracker
try:
    from runcomfy.workflow_progress_tracker import progress_tracker
except ImportError:
    progress_tracker = None

app = FastAPI(
    title="CONJURE API Server",
    description="Internal API server for CONJURE 3D modeling system",
    version="1.0.0"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (to be initialized on startup)
state_manager: Optional[StateManager] = None
instruction_manager: Optional[InstructionManager] = None
backend_agent: Optional[BackendAgent] = None

# Pydantic models for request/response validation
class ConversationRequest(BaseModel):
    conversation_history: str
    include_image: bool = True

class InstructionRequest(BaseModel):
    instruction: Dict[str, Any]

class StateUpdateRequest(BaseModel):
    updates: Dict[str, Any]

class StateSetRequest(BaseModel):
    value: Any

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# New models for FLUX and PartPacker APIs
class FluxRequest(BaseModel):
    prompt: str
    seed: int = 0
    randomize_seed: bool = True
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 3.5
    num_inference_steps: int = 28

class FluxDepthRequest(BaseModel):
    control_image_path: str  # Path to the GestureCamera render
    prompt: str
    seed: int = 0
    randomize_seed: bool = True
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 10
    num_inference_steps: int = 28

class PartPackerRequest(BaseModel):
    image_path: str  # Path to FLUX result image
    num_steps: int = 50
    cfg_scale: float = 7
    grid_res: int = 384
    seed: int = 0
    simplify_mesh: bool = False
    target_num_faces: int = 100000

class MeshImportRequest(BaseModel):
    mesh_path: str
    min_volume_threshold: float = 0.001  # Minimum volume before culling

# Startup/shutdown handlers
@app.on_event("startup")
async def startup_event():
    global state_manager, instruction_manager, backend_agent
    state_manager = StateManager()
    instruction_manager = InstructionManager(state_manager)
    backend_agent = BackendAgent(instruction_manager=instruction_manager)
    print("✅ CONJURE API Server initialized")

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 CONJURE API Server shutting down")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CONJURE API Server"}

# System shutdown endpoint
@app.post("/shutdown")
async def shutdown_system():
    """Trigger shutdown of the entire CONJURE system"""
    try:
        print("🛑 API Server: Received shutdown request from UI")
        
        # Import here to avoid circular imports
        import signal
        import os
        import threading
        
        def delayed_shutdown():
            """Shutdown the system after a brief delay"""
            import time
            time.sleep(1)  # Give time for API response to be sent
            print("🛑 API Server: Initiating system shutdown...")
            
            # Send SIGTERM to the main process
            try:
                # Get the parent process ID (main CONJURE process)
                parent_pid = os.getppid()
                if parent_pid != 1:  # Not init process
                    os.kill(parent_pid, signal.SIGTERM)
                    print(f"✅ Sent shutdown signal to main process (PID: {parent_pid})")
                else:
                    # Fallback: kill current process
                    os.kill(os.getpid(), signal.SIGTERM)
            except Exception as e:
                print(f"⚠️ Error sending shutdown signal: {e}")
                # Fallback: force exit
                os._exit(0)
        
        # Start shutdown in background thread to allow API response to complete
        shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
        shutdown_thread.start()
        
        return {"status": "success", "message": "CONJURE system shutdown initiated"}
        
    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
        return {"status": "error", "message": f"Shutdown failed: {str(e)}"}

# Progress tracking endpoints
@app.get("/workflow/progress/{prompt_id}")
async def get_workflow_progress(prompt_id: str):
    """Get current progress for a workflow execution."""
    if not progress_tracker:
        raise HTTPException(status_code=501, detail="Progress tracking not available")
    
    progress_summary = progress_tracker.get_workflow_summary(prompt_id)
    if not progress_summary:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "success": True,
        "data": progress_summary
    }

@app.get("/workflow/progress")
async def get_all_active_workflows():
    """Get progress for all active workflows."""
    if not progress_tracker:
        raise HTTPException(status_code=501, detail="Progress tracking not available")
    
    active_workflows = []
    for prompt_id in progress_tracker.active_workflows:
        summary = progress_tracker.get_workflow_summary(prompt_id)
        if summary:
            active_workflows.append(summary)
    
    return {
        "success": True,
        "data": {
            "active_workflows": active_workflows,
            "total_count": len(active_workflows)
        }
    }

# Generation mode endpoint
@app.get("/mode")
async def get_mode():
    """Get current generation mode and service availability."""
    mode = get_generation_mode()
    
    # Check service availability
    local_service = get_generation_service("local")
    serverless_service = get_generation_service("serverless")
    cloud_legacy_service = get_generation_service("cloud_legacy")
    
    return {
        "generation_mode": mode,
        "available_modes": ["huggingface", "cloud", "serverless", "cloud_legacy"],
        "local_available": local_service.is_available(),
        "cloud_available": serverless_service.is_available(),  # Cloud now means serverless
        "serverless_available": serverless_service.is_available(),
        "cloud_legacy_available": cloud_legacy_service.is_available(),
        "services": {
            "huggingface": {
                "name": "HuggingFace Models", 
                "description": "FLUX.1-dev, FLUX.1-Depth-dev, PartPacker",
                "available": local_service.is_available(),
                "requirements": "HUGGINGFACE_HUB_ACCESS_TOKEN"
            },
            "cloud": {
                "name": "runComfy Serverless API",
                "description": "Instant serverless FLUX + 3D mesh generation",
                "available": serverless_service.is_available(),
                "requirements": "runComfy API token and deployment"
            },
            "serverless": {
                "name": "runComfy Serverless API",
                "description": "Instant serverless FLUX + 3D mesh generation",
                "available": serverless_service.is_available(),
                "requirements": "runComfy API token and deployment"
            },
            "cloud_legacy": {
                "name": "runComfy Server Management",
                "description": "Legacy server-based ComfyUI workflows",
                "available": cloud_legacy_service.is_available(),
                "requirements": "runComfy account and credits"
            }
        }
    }

# Conversation processing endpoint
@app.post("/process_conversation", response_model=APIResponse)
async def process_conversation(request: ConversationRequest):
    """
    Process conversation history through the backend agent.
    Replaces direct backend_agent.get_response() calls.
    """
    global backend_agent
    if not backend_agent:
        print("❌ API Error: Backend agent not initialized")
        raise HTTPException(status_code=500, detail="Backend agent not initialized")
    
    try:
        print(f"📨 API received conversation: {request.conversation_history[:100]}...")
        print(f"🔍 Full conversation length: {len(request.conversation_history)} chars")
        print(f"🖼️ Include image: {request.include_image}")
        
        # 🎬 HARDCORE DEMO: ALLOW backend agent for conversations to generate contextual prompts
        print("🎬 HARDCORE DEMO: Processing conversation through backend agent for contextual prompts")
        
        # Call the backend agent to process the conversation
        result = backend_agent.get_response(
            conversation_history=request.conversation_history,
            include_image=request.include_image
        )
        
        print(f"✅ Backend agent processed conversation successfully")
        print(f"📊 Result type: {type(result)}, Content preview: {str(result)[:200]}...")
        
        # 🎯 ENHANCED DEBUGGING: Detailed Backend Agent Response Analysis
        print("\n" + "="*80)
        print("🧠 BACKEND AGENT RESPONSE ANALYSIS")
        print("="*80)
        
        if result:
            print(f"📋 Response Type: {type(result)}")
            print(f"📄 Full Response: {result}")
            
            if isinstance(result, dict):
                print(f"🔧 Tool Name: {result.get('tool_name', 'None')}")
                print(f"⚙️ Parameters: {result.get('parameters', 'None')}")
                
                # Check if files were written by backend agent
                try:
                    # Check for vision summary
                    vision_path = Path(__file__).parent.parent / "screen_description.txt"
                    if vision_path.exists():
                        with open(vision_path, 'r', encoding='utf-8') as f:
                            vision_content = f.read()
                        print(f"👁️ Vision Summary: {vision_content[:200]}...")
                    
                    # Check for user prompt
                    prompt_path = Path(__file__).parent.parent / "data" / "generated_text" / "userPrompt.txt"
                    if prompt_path.exists():
                        with open(prompt_path, 'r', encoding='utf-8') as f:
                            prompt_content = f.read()
                        print(f"🎨 Generated FLUX Prompt: {prompt_content[:200]}...")
                        
                except Exception as e:
                    print(f"⚠️ Error reading backend agent output files: {e}")
            else:
                print(f"📝 Raw Result: {result}")
        else:
            print("❌ No result returned from backend agent")
            
        print("="*80)
        print("🔚 END BACKEND AGENT RESPONSE ANALYSIS")
        print("="*80 + "\n")
        
        # 🎬 HARDCORE DEMO: Always return success, ignore tool execution
        # Backend agent processes conversation and writes user prompts
        # But we're forcing the sequence in main.py instead of executing tools
        print("🎬 HARDCORE DEMO: Backend agent processed conversation - ignoring tool execution")
        
        return APIResponse(
            success=True,
            message="Conversation processed successfully (demo mode - backend agent analyzes but tools are forced)",
            data={"instruction": result} if result else None
        )
    except Exception as e:
        print(f"❌ Error processing conversation: {e}")
        import traceback
        print(f"🔍 Full error traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing conversation: {str(e)}")

# Instruction execution endpoint
@app.post("/execute_instruction", response_model=APIResponse)
async def execute_instruction(request: InstructionRequest):
    """
    Execute tool instructions through the instruction manager.
    Replaces direct instruction_manager.execute_instruction() calls.
    """
    global instruction_manager
    if not instruction_manager:
        raise HTTPException(status_code=500, detail="Instruction manager not initialized")
    
    try:
        tool_name = request.instruction.get("tool_name", "unknown")
        print(f"🔧 API received instruction: {tool_name}")
        
        # Add smart API-level deduplication matching InstructionManager logic
        if not hasattr(execute_instruction, '_processed_instructions'):
            execute_instruction._processed_instructions = {}
        
        if not hasattr(execute_instruction, '_heavy_operations'):
            execute_instruction._heavy_operations = {
                "generate_flux_mesh", "import_and_process_mesh", "spawn_primitive"
            }
            execute_instruction._interactive_operations = {
                "segment_selection", "fuse_mesh", "select_concept"
            }
        
        # Interactive operations are always allowed to repeat at API level
        if tool_name in execute_instruction._interactive_operations:
            print(f"🔄 API: Interactive command {tool_name} allowed to repeat")
        elif tool_name in execute_instruction._heavy_operations:
            # Apply strict deduplication for heavy operations
            instruction_str = json.dumps(request.instruction, sort_keys=True)
            instruction_hash = hashlib.md5(instruction_str.encode()).hexdigest()
            
            current_time = time.time()
            
            # Clean up old entries (older than 30 seconds)
            expired_hashes = [
                h for h, timestamp in execute_instruction._processed_instructions.items()
                if current_time - timestamp > 30
            ]
            for h in expired_hashes:
                del execute_instruction._processed_instructions[h]
            
            # Check for duplicates
            if instruction_hash in execute_instruction._processed_instructions:
                time_since = current_time - execute_instruction._processed_instructions[instruction_hash]
                print(f"🚫 API: Duplicate heavy operation {tool_name} blocked (executed {time_since:.1f}s ago)")
                return APIResponse(
                    success=True,
                    message=f"Heavy operation {tool_name} already processed recently",
                    data={"instruction": request.instruction, "duplicate_blocked": True}
                )
            
            # Mark as processed
            execute_instruction._processed_instructions[instruction_hash] = current_time
            print(f"✅ API: Heavy operation {tool_name} allowed")
        else:
            print(f"✅ API: Unknown operation {tool_name} allowed (no API-level deduplication)")
        
        # 🎬 HARDCORE DEMO: Don't execute tools - main.py forces the sequence
        print(f"🎬 HARDCORE DEMO: Ignoring tool execution '{tool_name}' - using forced sequence")
        
        return APIResponse(
            success=True,
            message=f"Tool '{tool_name}' ignored in demo mode - using forced sequence",
            data={"tool_name": tool_name, "demo_mode": True}
        )
    except Exception as e:
        print(f"❌ Error executing instruction: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing instruction: {str(e)}")

# State management endpoints
@app.get("/state", response_model=APIResponse)
async def get_state():
    """Get current application state."""
    global state_manager
    if not state_manager:
        raise HTTPException(status_code=500, detail="State manager not initialized")
    
    try:
        state = state_manager.get_state()
        print(f"📊 API retrieved state (keys: {list(state.keys()) if state else 'empty'})")
        return APIResponse(success=True, message="State retrieved", data=state)
    except Exception as e:
        print(f"❌ Error getting state: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting state: {str(e)}")

@app.post("/state/update", response_model=APIResponse)
async def update_state(request: StateUpdateRequest):
    """Update application state."""
    global state_manager
    if not state_manager:
        raise HTTPException(status_code=500, detail="State manager not initialized")
    
    try:
        print(f"📊 API updating state with keys: {list(request.updates.keys())}")
        state_manager.update_state(request.updates)
        return APIResponse(success=True, message="State updated successfully")
    except Exception as e:
        print(f"❌ Error updating state: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating state: {str(e)}")

@app.post("/state/set/{key}", response_model=APIResponse)
async def set_state_value(key: str, request: StateSetRequest):
    """Set a specific state value."""
    global state_manager
    if not state_manager:
        raise HTTPException(status_code=500, detail="State manager not initialized")
    
    try:
        print(f"📊 API setting state key '{key}' to: {request.value}")
        state_manager.set_state(key, request.value)
        return APIResponse(success=True, message=f"State key '{key}' set successfully")
    except Exception as e:
        print(f"❌ Error setting state: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting state: {str(e)}")

# New FLUX and PartPacker API endpoints
# Add this near the top imports
import os

# Get HuggingFace token at module level
HF_TOKEN = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
if not HF_TOKEN:
    print("⚠️  WARNING: HUGGINGFACE_HUB_ACCESS_TOKEN not set - API calls will use anonymous quota")

def get_generation_mode():
    """Get the current generation mode from state file."""
    try:
        from state_manager import StateManager
        state_manager = StateManager()
        state = state_manager.get_state()
        mode = state.get('generation_mode', 'local')
        print(f"🔍 API SERVER: Retrieved generation mode from state: {mode}")
        return mode
    except Exception as e:
        print(f"⚠️ API SERVER: Error reading generation mode from state, defaulting to local: {e}")
        return 'local'



@app.post("/flux/generate", response_model=APIResponse)
async def generate_flux_image(request: FluxRequest):
    """Generate image using FLUX.1-dev API."""
    try:
        # Get appropriate generation service based on current mode
        mode = get_generation_mode()
        generation_service = get_generation_service(mode)
        
        print(f"🎨 [{mode.upper()}] Generating FLUX image with prompt: {request.prompt[:100]}...")
        
        # Use generation service
        result = generation_service.generate_flux_image(
            prompt=request.prompt,
            seed=request.seed,
            randomize_seed=request.randomize_seed,
            width=request.width,
            height=request.height,
            num_inference_steps=request.num_inference_steps
        )
        
        if result["success"]:
            print(f"✅ [{mode.upper()}] FLUX image generated successfully: {result['image_path']}")
            return APIResponse(
                success=True,
                message=f"FLUX image generated successfully using {mode.upper()} mode",
                data={
                    "image_path": result["image_path"],
                    "seed_used": result["seed_used"],
                    "generation_mode": mode
                }
            )
        else:
            raise Exception("Generation service returned failure")
            
    except Exception as e:
        print(f"❌ Error generating FLUX image: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating FLUX image: {str(e)}")

@app.post("/flux/depth", response_model=APIResponse)
async def generate_flux_depth_image(request: FluxDepthRequest):
    """Generate depth-controlled image using FLUX.1-Depth-dev API."""
    try:
        # Get appropriate generation service based on current mode
        mode = get_generation_mode()
        generation_service = get_generation_service(mode)
        
        print(f"🎨 [{mode.upper()}] FLUX DEPTH API: Request received")
        print(f"   📝 Prompt: {request.prompt[:100]}...")
        print(f"   🖼️ Control image: {request.control_image_path}")
        print(f"   🎲 Seed: {request.seed}")
        
        # Use generation service
        result = generation_service.generate_flux_depth_image(
            control_image_path=request.control_image_path,
            prompt=request.prompt,
            seed=request.seed,
            randomize_seed=request.randomize_seed,
            width=request.width,
            height=request.height,
            guidance_scale=request.guidance_scale,
            num_inference_steps=request.num_inference_steps
        )
        
        if result["success"]:
            print(f"✅ [{mode.upper()}] FLUX Depth image generated successfully: {result['image_path']}")
            return APIResponse(
                success=True,
                message=f"FLUX Depth image generated successfully using {mode.upper()} mode",
                data={
                    "image_path": result["image_path"],
                    "seed_used": result["seed_used"],
                    "generation_mode": mode
                }
            )
        else:
            raise Exception("Generation service returned failure")
            
    except Exception as e:
        print(f"❌ [{get_generation_mode().upper()}] FLUX DEPTH API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating FLUX Depth image: {str(e)}")

@app.post("/partpacker/generate_3d", response_model=APIResponse)
async def generate_3d_with_partpacker(request: PartPackerRequest):
    """Generate 3D model using PartPacker API."""
    try:
        # Get appropriate generation service based on current mode
        mode = get_generation_mode()
        generation_service = get_generation_service(mode)
        
        print(f"🏗️ [{mode.upper()}] PARTPACKER API: Request received")
        print(f"   🖼️ Input image: {request.image_path}")
        print(f"   🎲 Seed: {request.seed}")
        print(f"   ⚙️ Steps: {request.num_steps}, CFG: {request.cfg_scale}, Grid: {request.grid_res}")
        
        # Use generation service
        result = generation_service.generate_3d_model(
            image_path=request.image_path,
            seed=request.seed,
            num_steps=request.num_steps,
            cfg_scale=request.cfg_scale,
            grid_res=request.grid_res,
            simplify_mesh=request.simplify_mesh,
            target_num_faces=request.target_num_faces
        )
        
        if result["success"]:
            print(f"✅ [{mode.upper()}] PARTPACKER API: 3D model saved successfully to {result['model_path']}")
            return APIResponse(
                success=True,
                message=f"3D model generated successfully using {mode.upper()} mode",
                data={
                    "model_path": result["model_path"],
                    "seed_used": result["seed_used"],
                    "generation_mode": mode
                }
            )
        else:
            raise Exception("Generation service returned failure")
            
    except Exception as e:
        print(f"❌ [{get_generation_mode().upper()}] PARTPACKER API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating 3D model: {str(e)}")

@app.post("/blender/render_gesture_camera", response_model=APIResponse)
async def render_gesture_camera():
    """Trigger Blender to render GestureCamera for FLUX.1-Depth input."""
    try:
        print(f"📸 Triggering GestureCamera render for FLUX.1-Depth...")
        
        # Set state to trigger Blender operator
        global state_manager
        if not state_manager:
            raise HTTPException(status_code=500, detail="State manager not initialized")
        
        state_manager.set_state("command", "render_gesture_camera")
        
        # Wait a moment for Blender to process
        await asyncio.sleep(0.5)
        
        # Check if render file exists
        render_path = Path("data/generated_images/gestureCamera/render.png")
        if render_path.exists():
            print(f"✅ GestureCamera render completed: {render_path}")
            return APIResponse(
                success=True,
                message="GestureCamera render completed",
                data={"render_path": str(render_path)}
            )
        else:
            raise Exception("Render file not found after triggering render")
            
    except Exception as e:
        print(f"❌ Error rendering GestureCamera: {e}")
        raise HTTPException(status_code=500, detail=f"Error rendering GestureCamera: {str(e)}")

@app.post("/serverless/flux_mesh_unified", response_model=APIResponse)
async def generate_flux_mesh_unified():
    """Execute unified FLUX + 3D mesh generation using serverless API."""
    try:
        print(f"🚀 SERVERLESS UNIFIED API: Request received")
        
        # Get serverless generation service
        generation_service = get_generation_service("serverless")
        
        if not generation_service.is_available():
            raise HTTPException(status_code=503, detail="Serverless service not available")
        
        print(f"⚡ SERVERLESS UNIFIED: Starting unified FLUX + 3D generation...")
        
        # Execute unified generation (reads from CONJURE data automatically)
        result = generation_service.generate_flux_mesh_unified()
        
        if result["success"]:
            print(f"✅ SERVERLESS UNIFIED: Generation completed successfully!")
            print(f"   FLUX image: {result.get('flux_image_path', 'N/A')}")
            print(f"   3D mesh: {result.get('mesh_model_path', 'N/A')}")
            
            # Trigger mesh import if we have a mesh result
            mesh_path = result.get('mesh_model_path')
            if mesh_path and Path(mesh_path).exists():
                global state_manager
                if state_manager:
                    state_manager.update_state({
                        "command": "import_and_process_mesh",
                        "mesh_path": mesh_path,
                        "min_volume_threshold": 0.001
                    })
                    print(f"✅ SERVERLESS UNIFIED: Triggered mesh import for {mesh_path}")
            
            return APIResponse(
                success=True,
                message="Serverless unified generation completed successfully",
                data=result
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ SERVERLESS UNIFIED: Generation failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Serverless generation failed: {error_msg}")
            
    except Exception as e:
        print(f"❌ SERVERLESS UNIFIED API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in serverless generation: {str(e)}")

@app.post("/local_comfyui/flux_mesh_unified", response_model=APIResponse)
async def generate_flux_mesh_local_comfyui():
    """Execute unified FLUX + 3D mesh generation using local ComfyUI server."""
    try:
        print(f"🖥️ LOCAL COMFYUI UNIFIED API: Request received")
        
        # Get local ComfyUI generation service
        generation_service = get_generation_service("local_comfyui")
        
        print(f"🔧 LOCAL COMFYUI UNIFIED: Starting unified FLUX + 3D generation...")
        
        # Execute unified generation (reads from CONJURE data automatically)
        result = generation_service.generate_flux_mesh()
        
        if result["success"]:
            print(f"✅ LOCAL COMFYUI UNIFIED: Generation completed successfully!")
            print(f"   FLUX image: {result.get('flux_image', 'N/A')}")
            print(f"   3D mesh: {result.get('mesh_model', 'N/A')}")
            
            # Trigger mesh import if we have a mesh result
            mesh_path = result.get('mesh_model')
            if mesh_path and Path(mesh_path).exists():
                global state_manager
                if state_manager:
                    state_manager.update_state({
                        "command": "import_and_process_mesh",
                        "mesh_path": mesh_path,
                        "min_volume_threshold": 0.001
                    })
                    print(f"✅ LOCAL COMFYUI UNIFIED: Triggered mesh import for {mesh_path}")
            
            return APIResponse(
                success=True,
                message="Local ComfyUI unified generation completed successfully",
                data={
                    "flux_image_path": result.get('flux_image'),
                    "mesh_model_path": result.get('mesh_model'),
                    "prompt_id": result.get('prompt_id')
                }
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ LOCAL COMFYUI UNIFIED: Generation failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Local ComfyUI generation failed: {error_msg}")
            
    except Exception as e:
        print(f"❌ LOCAL COMFYUI UNIFIED API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in local ComfyUI generation: {str(e)}")

@app.post("/blender/import_mesh", response_model=APIResponse)
async def import_mesh(request: MeshImportRequest):
    """Import and process mesh from generation results (PartPacker local or RunComfy cloud).
    - HuggingFace mode: Handles pre-segmented meshes from PartPacker
    - Cloud mode: Automatically separates single mesh from RunComfy into loose parts"""
    try:
        print(f"📦 MESH IMPORT API: Request received")
        print(f"   📁 Mesh path: {request.mesh_path}")
        print(f"   🔍 Min volume threshold: {request.min_volume_threshold}")
        
        # Verify mesh file exists
        if not Path(request.mesh_path).exists():
            error_msg = f"Mesh file not found: {request.mesh_path}"
            print(f"❌ MESH IMPORT API: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        print(f"✅ MESH IMPORT API: Mesh file verified, sending command to Blender...")
        
        # Set state to trigger Blender import operator
        global state_manager
        if not state_manager:
            raise HTTPException(status_code=500, detail="State manager not initialized")
        
        state_manager.update_state({
            "command": "import_and_process_mesh",
            "mesh_path": request.mesh_path,
            "min_volume_threshold": request.min_volume_threshold
        })
        
        print(f"✅ MESH IMPORT API: Command sent to Blender successfully")
        return APIResponse(
            success=True,
            message="Mesh import command sent to Blender",
            data={
                "mesh_path": request.mesh_path,
                "min_volume_threshold": request.min_volume_threshold
            }
        )
        
    except Exception as e:
        print(f"❌ MESH IMPORT API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error importing mesh: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info") 