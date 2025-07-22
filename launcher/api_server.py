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
from pathlib import Path

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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info") 