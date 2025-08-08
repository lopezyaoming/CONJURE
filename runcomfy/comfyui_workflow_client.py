"""
ComfyUI Workflow Client for CONJURE

Simplified workflow execution client focused on generate_flux_mesh workflow.
Handles workflow submission, monitoring, and result retrieval.
"""
import asyncio
import base64
import json
import os
import time
import uuid
import websockets
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

import httpx

# Import the progress tracker
try:
    from .workflow_progress_tracker import progress_tracker, WorkflowProgress
except ImportError:
    from workflow_progress_tracker import progress_tracker, WorkflowProgress


class ExecutionStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PromptExecution:
    prompt_id: str
    status: str
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    outputs: Optional[Dict] = None


@dataclass
class GeneratedResult:
    filename: str
    subfolder: str
    type: str
    url: str
    local_path: Optional[str] = None


class ComfyUIWorkflowClient:
    """Client for executing workflows on ComfyUI instances via RunComfy"""
    
    def __init__(self, output_dir: str = "data/generated_models"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Timeouts and intervals (adjusted for 3D generation)
        self.execution_timeout = int(os.getenv("COMFYUI_EXECUTION_TIMEOUT", "3600"))  # 1 hour for 3D generation
        self.poll_interval = int(os.getenv("COMFYUI_POLL_INTERVAL", "5"))  # 5 seconds
        self.max_retries = int(os.getenv("COMFYUI_MAX_RETRIES", "3"))
        
        print(f"🎨 ComfyUI Workflow Client initialized")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Execution timeout: {self.execution_timeout}s")
    
    def prepare_flux_mesh_workflow(self, workflow_data: Dict, image_base64: str, prompt: str) -> Dict[str, Any]:
        """
        Prepare generate_flux_mesh workflow with image and prompt
        
        Args:
            workflow_data: The workflow JSON data
            image_base64: Base64 encoded image
            prompt: Text prompt for generation
            
        Returns:
            Modified workflow ready for execution
        """
        print(f"🔧 Preparing generate_flux_mesh workflow")
        print(f"   Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        print(f"   Image size: {len(image_base64)} characters")
        
        # Deep copy workflow to avoid modifying original
        workflow = json.loads(json.dumps(workflow_data))
        
        # TODO: Update this based on the actual workflow structure
        # For now, return the workflow as-is for testing
        print("⚠️ Workflow preparation not yet implemented - using workflow as-is")
        
        return workflow
    
    async def submit_workflow(self, comfyui_url: str, workflow: Dict[str, Any]) -> Tuple[str, str]:
        """
        Submit workflow to ComfyUI instance
        
        Args:
            comfyui_url: Base URL of ComfyUI instance
            workflow: Prepared workflow data
            
        Returns:
            Tuple of (prompt_id, client_id) for tracking execution
        """
        print(f"\n📤 [SUBMIT DEBUG] Submitting workflow to {comfyui_url}")
        
        try:
            # Generate unique client ID (prompt ID will come from ComfyUI)
            client_id = f"conjure_{uuid.uuid4().hex[:8]}"
            
            # Prepare prompt submission payload
            payload = {
                "prompt": workflow,
                "client_id": client_id
            }
            
            print(f"   Client ID: {client_id}")
            print(f"   Workflow nodes: {len(workflow)}")
            
            # Submit to ComfyUI /prompt endpoint
            print(f"   📡 [SUBMIT DEBUG] Sending POST request to /prompt...")
            async with httpx.AsyncClient(timeout=30.0) as client_http:
                response = await client_http.post(
                    f"{comfyui_url}/prompt",
                    json=payload
                )
                
                print(f"   📶 [SUBMIT DEBUG] Response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    prompt_id = result.get("prompt_id")
                    queue_number = result.get("number", "unknown")
                    node_errors = result.get("node_errors", {})
                    
                    print(f"   📄 [SUBMIT DEBUG] Response: {result}")
                    
                    if node_errors:
                        print(f"   ⚠️ [SUBMIT DEBUG] Node errors found: {node_errors}")
                    
                    if prompt_id:
                        print(f"   ✅ [SUBMIT DEBUG] Workflow submitted successfully!")
                        print(f"      Prompt ID: {prompt_id}")
                        print(f"      Queue position: {queue_number}")
                        return prompt_id, client_id
                    else:
                        error_msg = f"No prompt_id in response: {result}"
                        print(f"   ❌ [SUBMIT DEBUG] {error_msg}")
                        raise RuntimeError(error_msg)
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    print(f"   ❌ [SUBMIT DEBUG] Submit failed: {error_msg}")
                    raise RuntimeError(error_msg)
                    
        except Exception as e:
            print(f"   ❌ [SUBMIT DEBUG] Error submitting workflow: {e}")
            raise
    
    async def wait_for_completion_websocket(self, comfyui_url: str, prompt_id: str, client_id: str) -> PromptExecution:
        """
        Wait for workflow completion using WebSocket monitoring with detailed debug messages
        
        Args:
            comfyui_url: Base URL of ComfyUI instance
            prompt_id: Prompt ID to monitor
            client_id: Client ID for WebSocket connection
            
        Returns:
            PromptExecution with completion status
        """
        print(f"\n🔌 [WEBSOCKET DEBUG] Starting WebSocket monitoring for: {prompt_id}")
        print(f"   ComfyUI URL: {comfyui_url}")
        print(f"   Client ID: {client_id}")
        print(f"   Timeout: {self.execution_timeout}s")
        
        # Convert HTTP URL to WebSocket URL
        ws_url = comfyui_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/ws?clientId={client_id}"
        
        print(f"   WebSocket URL: {ws_url}")
        
        start_time = time.time()
        last_debug_time = 0
        execution_completed = False
        execution_result = None
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print(f"   ✅ [WEBSOCKET DEBUG] Connected to WebSocket!")
                
                while not execution_completed:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        elapsed = time.time() - start_time
                        
                        # Print detailed message info
                        msg_type = data.get("type", "unknown")
                        print(f"   📨 [WEBSOCKET DEBUG] Message: {msg_type}")
                        
                        if msg_type == "status":
                            status_data = data.get("data", {})
                            print(f"      Status: {json.dumps(status_data, indent=2)}")
                            
                        elif msg_type == "progress":
                            progress_data = data.get("data", {})
                            node = progress_data.get("node", "unknown")
                            value = progress_data.get("value", 0)
                            max_val = progress_data.get("max", 100)
                            print(f"      Progress: Node {node} - {value}/{max_val} ({(value/max_val*100):.1f}%)")
                            
                            # Update progress tracker
                            progress_tracker.update_node_progress(prompt_id, str(node), "progress", progress_data=progress_data)
                            
                        elif msg_type == "executing":
                            node_id = data.get("data", {}).get("node", "unknown")
                            print(f"      Executing: Node {node_id}")
                            
                            # Update progress tracker
                            progress_tracker.update_node_progress(prompt_id, str(node_id), "executing")
                            
                        elif msg_type == "executed":
                            node_id = data.get("data", {}).get("node", "unknown")
                            print(f"      Executed: Node {node_id}")
                            
                            # Update progress tracker
                            progress_tracker.update_node_progress(prompt_id, str(node_id), "executed")
                            
                        elif msg_type == "execution_start":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            if exec_prompt_id == prompt_id:
                                print(f"   🚀 [WEBSOCKET DEBUG] Our workflow started executing!")
                            else:
                                print(f"      Other workflow started: {exec_prompt_id}")
                                
                        elif msg_type == "execution_success":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            if exec_prompt_id == prompt_id:
                                print(f"   ✅ [WEBSOCKET DEBUG] Our workflow completed successfully!")
                                execution_completed = True
                                execution_result = PromptExecution(
                                    prompt_id=prompt_id,
                                    status=ExecutionStatus.COMPLETED.value,
                                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                )
                            else:
                                print(f"      Other workflow completed: {exec_prompt_id}")
                                
                        elif msg_type == "execution_error":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            if exec_prompt_id == prompt_id:
                                error_details = data.get("data", {})
                                print(f"   ❌ [WEBSOCKET DEBUG] Our workflow failed!")
                                print(f"      Error: {json.dumps(error_details, indent=2)}")
                                execution_completed = True
                                execution_result = PromptExecution(
                                    prompt_id=prompt_id,
                                    status=ExecutionStatus.FAILED.value,
                                    error_message=str(error_details),
                                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                )
                            else:
                                print(f"      Other workflow failed: {exec_prompt_id}")
                        
                        elif msg_type == "execution_cached":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            cached_nodes = data.get("data", {}).get("nodes", [])
                            if exec_prompt_id == prompt_id:
                                print(f"   💾 [WEBSOCKET DEBUG] Some nodes cached: {cached_nodes}")
                            
                        else:
                            # Log any other message types for debugging
                            print(f"      Unknown message: {json.dumps(data, indent=2)}")
                        
                        # Regular debug updates every 10 seconds
                        if elapsed - last_debug_time >= 10:
                            print(f"\n   ⏰ [WEBSOCKET DEBUG] Status update ({elapsed:.0f}s elapsed)")
                            print(f"      Still monitoring for prompt: {prompt_id}")
                            print(f"      Last message type: {msg_type}")
                            last_debug_time = elapsed
                            
                    except asyncio.TimeoutError:
                        # No message received in 1 second, continue monitoring
                        elapsed = time.time() - start_time
                        
                        # Regular debug updates every 10 seconds even without messages
                        if elapsed - last_debug_time >= 10:
                            print(f"\n   ⏰ [WEBSOCKET DEBUG] Heartbeat ({elapsed:.0f}s elapsed)")
                            print(f"      Waiting for messages from prompt: {prompt_id}")
                            print(f"      WebSocket connection: Active")
                            last_debug_time = elapsed
                        
                        # Check overall timeout
                        if elapsed > self.execution_timeout:
                            print(f"   ⏰ [WEBSOCKET DEBUG] Overall timeout reached ({self.execution_timeout}s)")
                            execution_completed = True
                            execution_result = PromptExecution(
                                prompt_id=prompt_id,
                                status=ExecutionStatus.FAILED.value,
                                error_message=f"Execution timeout after {self.execution_timeout}s",
                                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                            )
                        continue
                
                # If we completed successfully, try to get the full results from history
                if execution_result and execution_result.status == ExecutionStatus.COMPLETED.value:
                    print(f"   📋 [WEBSOCKET DEBUG] Fetching final results from history...")
                    try:
                        history = await self.get_execution_history(comfyui_url, prompt_id)
                        if history:
                            execution_result.outputs = history.get("outputs", {})
                            print(f"   ✅ [WEBSOCKET DEBUG] Got outputs: {list(execution_result.outputs.keys())}")
                        else:
                            print(f"   ⚠️ [WEBSOCKET DEBUG] No history found for prompt")
                    except Exception as e:
                        print(f"   ⚠️ [WEBSOCKET DEBUG] Could not fetch history: {e}")
                
                return execution_result or PromptExecution(
                    prompt_id=prompt_id,
                    status=ExecutionStatus.FAILED.value,
                    error_message="WebSocket monitoring ended without completion",
                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                )
                        
        except Exception as e:
            print(f"   ❌ [WEBSOCKET DEBUG] WebSocket error: {e}")
            print(f"   🔄 [WEBSOCKET DEBUG] Falling back to polling method...")
            return PromptExecution(
                prompt_id=prompt_id,
                status=ExecutionStatus.FAILED.value,
                error_message=f"WebSocket error: {e}",
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
            )
    
    async def get_execution_history(self, comfyui_url: str, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution history and results for a completed prompt
        
        Args:
            comfyui_url: Base URL of ComfyUI instance
            prompt_id: Prompt ID to get history for
            
        Returns:
            History data with outputs if available
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{comfyui_url}/history/{prompt_id}")
                
                if response.status_code == 200:
                    history = response.json()
                    return history.get(prompt_id, {})
                else:
                    print(f"⚠️ History request failed: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"⚠️ Error getting execution history: {e}")
            return None
    
    async def wait_for_completion_polling(self, comfyui_url: str, prompt_id: str) -> PromptExecution:
        """
        Fallback: Wait for completion using HTTP polling
        
        Args:
            comfyui_url: Base URL of ComfyUI instance
            prompt_id: Prompt ID to monitor
            
        Returns:
            PromptExecution with completion status
        """
        print(f"\n🔄 [POLLING DEBUG] Using HTTP polling fallback for prompt: {prompt_id}")
        print(f"   Timeout: {self.execution_timeout}s")
        print(f"   Poll interval: {self.poll_interval}s")
        
        start_time = time.time()
        last_debug_time = 0
        
        while True:
            try:
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > self.execution_timeout:
                    print(f"   ⏰ [POLLING DEBUG] Timeout reached ({self.execution_timeout}s)")
                    return PromptExecution(
                        prompt_id=prompt_id,
                        status=ExecutionStatus.FAILED.value,
                        error_message=f"Polling timeout after {self.execution_timeout}s",
                        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    )
                
                # Query execution status
                print(f"   📡 [POLLING DEBUG] Checking status via HTTP...")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{comfyui_url}/history/{prompt_id}")
                    
                    if response.status_code == 200:
                        history = response.json()
                        
                        if prompt_id in history:
                            prompt_history = history[prompt_id]
                            status_data = prompt_history.get("status", {})
                            status_str = status_data.get("status_str", "unknown")
                            
                            print(f"   📊 [POLLING DEBUG] Status: {status_str}")
                            
                            if status_str == "success":
                                print(f"   ✅ [POLLING DEBUG] Workflow completed (via polling)")
                                return PromptExecution(
                                    prompt_id=prompt_id,
                                    status=ExecutionStatus.COMPLETED.value,
                                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    outputs=prompt_history.get("outputs", {})
                                )
                            elif status_str == "error":
                                print(f"   ❌ [POLLING DEBUG] Workflow failed (via polling)")
                                return PromptExecution(
                                    prompt_id=prompt_id,
                                    status=ExecutionStatus.FAILED.value,
                                    error_message="Execution failed (see ComfyUI logs)",
                                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                )
                            else:
                                print(f"   ⏳ [POLLING DEBUG] Still executing... ({status_str})")
                        else:
                            print(f"   ⏳ [POLLING DEBUG] Prompt not in history yet")
                    else:
                        print(f"   ⚠️ [POLLING DEBUG] History request failed: {response.status_code}")
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
                # Progress update every 30 seconds for polling
                if elapsed - last_debug_time >= 30:
                    print(f"\n   ⏰ [POLLING DEBUG] Progress update ({elapsed:.0f}s elapsed)")
                    print(f"      Still polling for prompt: {prompt_id}")
                    last_debug_time = elapsed
                
            except Exception as e:
                print(f"   ⚠️ [POLLING DEBUG] Polling error: {e}")
                await asyncio.sleep(self.poll_interval * 2)  # Wait longer on error
    
    async def execute_workflow(
        self, 
        comfyui_url: str, 
        workflow: Dict[str, Any], 
        use_websocket: bool = True,
        workflow_name: str = "generate_flux_mesh"
    ) -> PromptExecution:
        """
        Execute workflow on ComfyUI instance
        
        Args:
            comfyui_url: Base URL of ComfyUI instance
            workflow: Prepared workflow data
            use_websocket: Whether to use WebSocket monitoring (fallback to polling)
            workflow_name: Name of the workflow for progress tracking
            
        Returns:
            PromptExecution with results
        """
        print(f"🚀 Executing workflow: {workflow_name} on {comfyui_url}")
        
        try:
            # Submit workflow
            prompt_id, client_id = await self.submit_workflow(comfyui_url, workflow)
            
            # Start progress tracking
            workflow_progress = progress_tracker.start_workflow_tracking(workflow_name, prompt_id, client_id)
            print(f"📊 [PROGRESS] Started tracking workflow: {workflow_name}")
            
            # Monitor execution
            if use_websocket:
                try:
                    result = await self.wait_for_completion_websocket(comfyui_url, prompt_id, client_id)
                except Exception as e:
                    print(f"⚠️ WebSocket monitoring failed: {e}")
                    print("🔄 Falling back to HTTP polling...")
                    result = await self.wait_for_completion_polling(comfyui_url, prompt_id)
            else:
                result = await self.wait_for_completion_polling(comfyui_url, prompt_id)
            
            # Handle completion in progress tracker
            if result.status == ExecutionStatus.COMPLETED:
                progress_tracker.handle_workflow_completion(prompt_id, success=True)
                print(f"📊 [PROGRESS] Workflow completed successfully: {workflow_name}")
            else:
                progress_tracker.handle_workflow_completion(prompt_id, success=False, error_message=result.error_message)
                print(f"📊 [PROGRESS] Workflow failed: {result.error_message}")
            
            return result
                
        except Exception as e:
            print(f"❌ Workflow execution failed: {e}")
            # Try to handle failure in progress tracker if we have a prompt_id
            try:
                if 'prompt_id' in locals():
                    progress_tracker.handle_workflow_completion(prompt_id, success=False, error_message=str(e))
            except:
                pass  # Don't fail on progress tracking errors
            
            return PromptExecution(
                prompt_id="",
                client_id="",
                status=ExecutionStatus.FAILED,
                error_message=str(e),
                outputs={}
            )
