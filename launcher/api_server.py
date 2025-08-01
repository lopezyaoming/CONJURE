"""
CONJURE FastAPI Server
Central API server for coordinating all CONJURE components.
Replaces direct function calls with HTTP API endpoints.
"""
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
from gradio_client import Client, handle_file

# Import existing managers (DO NOT MODIFY THESE)
from state_manager import StateManager
from instruction_manager import InstructionManager
from backend_agent import BackendAgent

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
        
        # Call existing backend agent method (NO CHANGES to backend_agent.py)
        result = backend_agent.get_response(request.conversation_history)
        
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
        
        return APIResponse(
            success=True,
            message="Conversation processed successfully",
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
        
        # Add API-level deduplication to prevent duplicate calls to the same instruction
        instruction_str = json.dumps(request.instruction, sort_keys=True)
        instruction_hash = hashlib.md5(instruction_str.encode()).hexdigest()
        
        if not hasattr(execute_instruction, '_processed_instructions'):
            execute_instruction._processed_instructions = {}
        
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
            print(f"🚫 API: Duplicate instruction {tool_name} blocked (executed {time_since:.1f}s ago)")
            return APIResponse(
                success=True,
                message=f"Instruction {tool_name} already processed recently",
                data={"instruction": request.instruction, "duplicate_blocked": True}
            )
        
        # Mark as processed
        execute_instruction._processed_instructions[instruction_hash] = current_time
        
        # Call existing instruction manager method (NO CHANGES to instruction_manager.py)
        instruction_manager.execute_instruction(request.instruction)
        
        print(f"✅ Instruction executed successfully: {tool_name}")
        
        return APIResponse(
            success=True,
            message="Instruction executed successfully",
            data={"instruction": request.instruction}
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

@app.post("/flux/generate", response_model=APIResponse)
async def generate_flux_image(request: FluxRequest):
    """Generate image using FLUX.1-dev API."""
    try:
        print(f"🎨 Generating FLUX image with prompt: {request.prompt[:100]}...")
        
        # Initialize client with token
        client = Client("black-forest-labs/FLUX.1-dev", hf_token=HF_TOKEN)
        result = client.predict(
            prompt=request.prompt,
            seed=request.seed,
            randomize_seed=request.randomize_seed,
            width=request.width,
            height=request.height,
            num_inference_steps=request.num_inference_steps,
            api_name="/infer"
        )
        
        # Handle result (similar to depth implementation)
        output_dir = Path("data/generated_images/flux_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process result to get image path
        if isinstance(result, tuple) and len(result) >= 1:
            image_data = result[0]
            seed_used = result[1] if len(result) > 1 else request.seed
        else:
            image_data = result
            seed_used = request.seed
        
        # Extract image path and save
        image_path = None
        if hasattr(image_data, 'path'):
            image_path = image_data.path
        elif isinstance(image_data, dict) and 'path' in image_data:
            image_path = image_data['path']
        elif isinstance(image_data, str):
            image_path = image_data
        
        if image_path and Path(image_path).exists():
            dest_path = output_dir / f"flux_result_{seed_used}.png"
            shutil.copy(image_path, dest_path)
            
            print(f"✅ FLUX image generated successfully: {dest_path}")
            return APIResponse(
                success=True,
                message="FLUX image generated successfully",
                data={
                    "image_path": str(dest_path),
                    "seed_used": seed_used
                }
            )
        else:
            raise Exception("Could not extract image path from FLUX result")
            
    except Exception as e:
        print(f"❌ Error generating FLUX image: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating FLUX image: {str(e)}")

@app.post("/flux/depth", response_model=APIResponse)
async def generate_flux_depth_image(request: FluxDepthRequest):
    """Generate depth-controlled image using FLUX.1-Depth-dev API."""
    try:
        print(f"🎨 FLUX DEPTH API: Request received")
        print(f"   📝 Prompt: {request.prompt[:100]}...")
        print(f"   🖼️ Control image: {request.control_image_path}")
        print(f"   🎲 Seed: {request.seed}")
        print(f"   🔑 Using HF Token: {'Yes' if HF_TOKEN else 'No (Anonymous)'}")
        
        # Verify control image exists
        if not Path(request.control_image_path).exists():
            error_msg = f"Control image not found: {request.control_image_path}"
            print(f"❌ FLUX DEPTH API: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        print(f"✅ FLUX DEPTH API: Control image verified, starting generation...")
        
        # Initialize client with token
        client = Client("black-forest-labs/FLUX.1-Depth-dev", hf_token=HF_TOKEN)
        print(f"🔧 FLUX DEPTH API: Gradio client initialized, calling predict...")
        
        result = client.predict(
            control_image=handle_file(request.control_image_path),
            prompt=request.prompt,
            seed=request.seed,
            randomize_seed=request.randomize_seed,
            width=request.width,
            height=request.height,
            guidance_scale=request.guidance_scale,
            num_inference_steps=request.num_inference_steps,
            api_name="/infer"
        )
        
        print(f"🎨 FLUX DEPTH API: Generation completed, processing result...")
        
        # CRITICAL DEBUG: Always show raw result first, even if parsing fails
        try:
            print(f"🔍 DEBUG: Raw result type: {type(result)}")
            print(f"🔍 DEBUG: Raw result length: {len(result) if hasattr(result, '__len__') else 'N/A'}")
            print(f"🔍 DEBUG: Raw result content: {str(result)[:500]}...")  # Truncate for readability
        except Exception as debug_e:
            print(f"🔍 DEBUG: Could not display result - {debug_e}")
            print(f"🔍 DEBUG: Result repr: {repr(result)}")

        # Handle the FLUX result format: (file_path_string, seed_int)
        try:
            if isinstance(result, tuple) and len(result) >= 2:
                # FLUX returns: (file_path_string, seed_int)
                temp_file_path, seed_used = result[0], result[1]
                print(f"🔍 DEBUG: Tuple format - temp_file_path: {temp_file_path}")
                print(f"🔍 DEBUG: Tuple format - seed_used: {seed_used}")
                
                # Verify the temporary file exists
                if isinstance(temp_file_path, str) and Path(temp_file_path).exists():
                    print(f"✅ Temporary file verified: {temp_file_path}")
                    
                    # Create our target directory and file path
                    output_dir = Path("data/generated_images/flux")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = output_dir / "flux.png"
                    
                    # Copy and convert the file
                    try:
                        if temp_file_path.lower().endswith('.webp'):
                            # Convert webp to png using PIL
                            from PIL import Image
                            print(f"🔄 Converting .webp to .png...")
                            with Image.open(temp_file_path) as img:
                                # Convert to RGB if needed (webp might have transparency)
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(dest_path, 'PNG')
                            print(f"✅ Converted and saved: {dest_path}")
                        else:
                            # Direct copy for other formats
                            shutil.copy(temp_file_path, dest_path)
                            print(f"✅ Copied: {dest_path}")
                            
                        print(f"✅ FLUX DEPTH API: Image saved successfully to {dest_path}")
                        return APIResponse(
                            success=True,
                            message="FLUX Depth image generated successfully",
                            data={
                                "image_path": str(dest_path),
                                "seed_used": seed_used
                            }
                        )
                    except Exception as save_e:
                        print(f"❌ Error saving file: {save_e}")
                        raise Exception(f"Could not save image: {save_e}")
                else:
                    print(f"❌ Temporary file not found or invalid: {temp_file_path}")
                    raise Exception(f"Temporary file not accessible: {temp_file_path}")
            else:
                print(f"❌ Unexpected result format: {type(result)} with length {len(result) if hasattr(result, '__len__') else 'unknown'}")
                raise Exception(f"Unexpected result format: {type(result)}")
                
        except Exception as parse_e:
            print(f"❌ DEBUG: Exception during result parsing: {parse_e}")
            import traceback
            print(f"🔍 Full parsing traceback:\n{traceback.format_exc()}")
            raise Exception(f"Could not process FLUX result: {parse_e}")
            
    except Exception as e:
        print(f"❌ FLUX DEPTH API ERROR: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating FLUX Depth image: {str(e)}")

@app.post("/partpacker/generate_3d", response_model=APIResponse)
async def generate_3d_with_partpacker(request: PartPackerRequest):
    """Generate 3D model using PartPacker API."""
    try:
        print(f"🏗️ PARTPACKER API: Request received")
        print(f"   🖼️ Input image: {request.image_path}")
        print(f"   🎲 Seed: {request.seed}")
        print(f"   ⚙️ Steps: {request.num_steps}, CFG: {request.cfg_scale}, Grid: {request.grid_res}")
        print(f"   🔑 Using HF Token: {'Yes' if HF_TOKEN else 'No (Anonymous)'}")
        
        # Verify input image exists
        if not Path(request.image_path).exists():
            error_msg = f"Input image not found: {request.image_path}"
            print(f"❌ PARTPACKER API: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        print(f"✅ PARTPACKER API: Input image verified, starting 3D generation...")
        
        # Initialize client with token
        client = Client("nvidia/PartPacker", hf_token=HF_TOKEN)
        result = client.predict(
            input_image=handle_file(request.image_path),
            num_steps=request.num_steps,
            cfg_scale=request.cfg_scale,
            grid_res=request.grid_res,
            seed=request.seed,
            simplify_mesh=request.simplify_mesh,
            target_num_faces=request.target_num_faces,
            api_name="/process_3d"
        )
        
        print(f"🏗️ PARTPACKER API: Generation completed, processing result...")
        
        # Result should be a file path to the generated 3D model
        if result:
            # Create output directory
            output_dir = Path("data/generated_models/partpacker_results")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy the result to our data directory
            dest_path = output_dir / f"partpacker_result_{request.seed}.glb"
            shutil.copy(result, dest_path)
            
            print(f"✅ PARTPACKER API: 3D model saved successfully to {dest_path}")
            return APIResponse(
                success=True,
                message="3D model generated successfully with PartPacker",
                data={
                    "model_path": str(dest_path),
                    "seed_used": request.seed
                }
            )
        else:
            error_msg = "No model file returned from PartPacker API"
            print(f"❌ PARTPACKER API: {error_msg}")
            raise Exception(error_msg)
            
    except Exception as e:
        print(f"❌ PARTPACKER API ERROR: {e}")
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

@app.post("/blender/import_mesh", response_model=APIResponse)
async def import_mesh(request: MeshImportRequest):
    """Import and process mesh from PartPacker results."""
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