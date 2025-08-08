"""
ComfyUI Workflow Client for direct execution on RunComfy machines
Handles workflow submission, monitoring, and result retrieval
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
from loguru import logger
from fastapi import HTTPException, UploadFile


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
class GeneratedImage:
    filename: str
    subfolder: str
    type: str
    url: str
    local_path: Optional[str] = None


class ComfyUIWorkflowClient:
    """Client for executing workflows on ComfyUI instances"""
    
    def __init__(self, output_dir: str = "data/output/user2imgs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Workflow configuration
        self.image_node_id = "1271"  # Base64 image input node
        self.prompt_node_id = "1223"  # Text prompt input node
        self.output_nodes = {
            "variant_1": "1254",  # OP1 output
            "variant_2": "1253",  # OP2 output 
            "variant_3": "1252",  # OP3 output
            "assembly": "1242"    # Assembly diagram output
        }
        
        # Timeouts and intervals
        self.execution_timeout = int(os.getenv("COMFYUI_EXECUTION_TIMEOUT", "2000"))  # 33 minutes for model loading
        self.poll_interval = int(os.getenv("COMFYUI_POLL_INTERVAL", "3"))  # 3 seconds
        self.max_retries = int(os.getenv("COMFYUI_MAX_RETRIES", "3"))
        
        logger.info(f"🎨 ComfyUI Workflow Client initialized")
        logger.info(f"   Output directory: {self.output_dir}")
        logger.info(f"   Execution timeout: {self.execution_timeout}s")
    
    def prepare_workflow(self, workflow_data: Dict, image: UploadFile, prompt: str) -> Dict[str, Any]:
        """Prepare workflow with image and prompt data"""
        logger.info(f"🔧 Preparing workflow with image and prompt")
        logger.info(f"   Image: {image.filename} ({image.content_type})")
        logger.info(f"   Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        
        # Deep copy workflow to avoid modifying original
        workflow = json.loads(json.dumps(workflow_data))
        
        # Convert image to base64
        try:
            # Handle both regular UploadFile and our MockUploadFile
            if hasattr(image, 'file') and hasattr(image.file, 'read'):
                # Regular UploadFile or file-like object
                image_content = image.file.read()
                if hasattr(image.file, 'seek'):
                    image.file.seek(0)  # Reset file pointer for potential reuse
            else:
                # Direct read method (MockUploadFile)
                image_content = image.read() if callable(image.read) else image.file.read()
            
            image_base64 = base64.b64encode(image_content).decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Failed to read image content: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read image content: {e}"
            )
        
        logger.info(f"📸 Image converted to base64 ({len(image_base64)} chars)")
        
        # Update image node
        if self.image_node_id in workflow:
            workflow[self.image_node_id]["inputs"]["base64_data"] = image_base64
            logger.info(f"✅ Updated image node {self.image_node_id}")
        else:
            logger.error(f"❌ Image node {self.image_node_id} not found in workflow")
            raise HTTPException(
                status_code=500,
                detail=f"Image node {self.image_node_id} not found in workflow"
            )
        
        # Update prompt node
        if self.prompt_node_id in workflow:
            workflow[self.prompt_node_id]["inputs"]["STRING"] = prompt
            logger.info(f"✅ Updated prompt node {self.prompt_node_id}")
        else:
            logger.error(f"❌ Prompt node {self.prompt_node_id} not found in workflow")
            raise HTTPException(
                status_code=500,
                detail=f"Prompt node {self.prompt_node_id} not found in workflow"
            )
        
        logger.info(f"🔧 Workflow prepared successfully")
        return workflow
    
    async def submit_workflow(self, comfyui_url: str, workflow: Dict[str, Any]) -> Tuple[str, str]:
        """Submit workflow to ComfyUI and return (prompt_id, client_id)"""
        client_id = str(uuid.uuid4())
        
        payload = {
            "prompt": workflow,
            "client_id": client_id
        }
        
        logger.info(f"📤 Submitting workflow to ComfyUI...")
        logger.info(f"   URL: {comfyui_url}/prompt")
        logger.info(f"   Client ID: {client_id}")
        logger.info(f"   Workflow nodes: {len(workflow)}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{comfyui_url}/prompt",
                    json=payload
                )
            
            logger.info(f"📨 ComfyUI response: {response.status_code}")
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"📨 Response data: {result}")
            
            if 'error' in result:
                error_details = result.get('node_errors', {})
                logger.error(f"❌ ComfyUI workflow error: {result['error']}")
                logger.error(f"❌ Node errors: {error_details}")
                raise HTTPException(
                    status_code=400,
                    detail=f"ComfyUI workflow error: {result['error']} - Details: {error_details}"
                )
            
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                logger.error(f"❌ No prompt_id in response: {result}")
                raise HTTPException(
                    status_code=500,
                    detail="ComfyUI did not return a prompt_id"
                )
            
            logger.info(f"✅ Workflow submitted successfully - Prompt ID: {prompt_id}")
            return prompt_id, client_id
            
        except httpx.RequestError as e:
            logger.error(f"❌ Failed to connect to ComfyUI: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to ComfyUI: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ ComfyUI API error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"ComfyUI API error: {e.response.text}"
            )
    
    async def get_queue_status(self, comfyui_url: str) -> Dict[str, Any]:
        """Get current queue status from ComfyUI"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{comfyui_url}/queue")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ Failed to get queue status: {e}")
            return {"queue_running": [], "queue_pending": []}
    
    async def get_execution_history(self, comfyui_url: str, prompt_id: str) -> Optional[Dict]:
        """Get execution history for a specific prompt"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{comfyui_url}/history/{prompt_id}")
            
            response.raise_for_status()
            history = response.json()
            
            return history.get(prompt_id)
            
        except Exception as e:
            logger.debug(f"Could not get history for {prompt_id}: {e}")
            return None
    
    async def wait_for_completion(self, comfyui_url: str, prompt_id: str) -> PromptExecution:
        """Wait for workflow execution to complete"""
        print(f"\n⏳ [EXECUTION DEBUG] Waiting for workflow completion: {prompt_id}")
        print(f"   ComfyUI URL: {comfyui_url}")
        print(f"   Timeout: {self.execution_timeout}s")
        print(f"   Poll interval: {self.poll_interval}s")
        
        logger.info(f"⏳ Waiting for workflow completion: {prompt_id}")
        start_time = time.time()
        last_status_report = 0
        
        while True:
            # Check queue status
            queue_status = await self.get_queue_status(comfyui_url)
            
            # Check if our prompt is still in queue
            running = queue_status.get("queue_running", [])
            pending = queue_status.get("queue_pending", [])
            
            in_queue = any(item[1] == prompt_id for item in running + pending)
            elapsed = time.time() - start_time
            
            # Regular status updates
            if elapsed - last_status_report >= 10:  # Every 10 seconds
                if in_queue:
                    running_count = len(running)
                    pending_count = len(pending)
                    in_running = any(item[1] == prompt_id for item in running)
                    
                    if in_running:
                        print(f"   ⚡ [EXECUTION DEBUG] Workflow RUNNING ({elapsed:.0f}s)")
                        print(f"      Queue: {running_count} running, {pending_count} pending")
                    else:
                        position = next((i for i, item in enumerate(pending) if item[1] == prompt_id), -1)
                        print(f"   ⏳ [EXECUTION DEBUG] Workflow QUEUED ({elapsed:.0f}s)")
                        print(f"      Position in queue: {position + 1}/{pending_count}")
                        print(f"      Running: {running_count}")
                else:
                    print(f"   🔍 [EXECUTION DEBUG] Checking completion ({elapsed:.0f}s)")
                
                last_status_report = elapsed
            
            if not in_queue:
                # Not in queue, check history
                print(f"   📋 [EXECUTION DEBUG] Not in queue, checking history...")
                history = await self.get_execution_history(comfyui_url, prompt_id)
                
                if history:
                    # Execution completed
                    status = history.get("status", {})
                    
                    if status.get("completed", False):
                        print(f"   ✅ [EXECUTION DEBUG] Workflow completed successfully!")
                        print(f"      Total time: {elapsed:.1f}s")
                        print(f"      Outputs available: {list(history.get('outputs', {}).keys())}")
                        
                        logger.info(f"✅ Workflow completed successfully: {prompt_id}")
                        return PromptExecution(
                            prompt_id=prompt_id,
                            status=ExecutionStatus.COMPLETED.value,
                            outputs=history.get("outputs", {})
                        )
                    elif "error" in status:
                        error_msg = status.get("error", "Unknown error")
                        print(f"   ❌ [EXECUTION DEBUG] Workflow failed: {error_msg}")
                        logger.error(f"❌ Workflow failed: {error_msg}")
                        return PromptExecution(
                            prompt_id=prompt_id,
                            status=ExecutionStatus.FAILED.value,
                            error_message=error_msg
                        )
                else:
                    print(f"   🔍 [EXECUTION DEBUG] No history yet, continuing to wait...")
            
            # Check timeout
            if elapsed > self.execution_timeout:
                print(f"   ⏰ [EXECUTION DEBUG] Timeout reached ({self.execution_timeout}s)")
                logger.error(f"⏰ Workflow execution timeout ({self.execution_timeout}s)")
                raise HTTPException(
                    status_code=408,
                    detail=f"Workflow execution timeout after {self.execution_timeout}s"
                )
            
            await asyncio.sleep(self.poll_interval)
    
    async def wait_for_completion_websocket(self, comfyui_url: str, prompt_id: str, client_id: str) -> PromptExecution:
        """Wait for workflow completion using WebSocket monitoring with debug messages every 10 seconds"""
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
                            
                        elif msg_type == "executed":
                            node_id = data.get("data", {}).get("node", "unknown")
                            print(f"      Executed: Node {node_id}")
                            
                        elif msg_type == "execution_start":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            if exec_prompt_id == prompt_id:
                                print(f"   🚀 [WEBSOCKET DEBUG] Our workflow started executing!")
                                
                        elif msg_type == "execution_success":
                            exec_prompt_id = data.get("data", {}).get("prompt_id", "")
                            if exec_prompt_id == prompt_id:
                                print(f"   ✅ [WEBSOCKET DEBUG] Our workflow completed successfully!")
                                execution_completed = True
                                execution_result = PromptExecution(
                                    prompt_id=prompt_id,
                                    status=ExecutionStatus.COMPLETED.value
                                )
                                
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
                                    error_message=str(error_details)
                                )
                        
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
                            raise HTTPException(
                                status_code=408,
                                detail=f"Workflow execution timeout after {self.execution_timeout}s"
                            )
                        continue
                        
                # If we completed via WebSocket, get the full results from history
                if execution_result and execution_result.status == ExecutionStatus.COMPLETED.value:
                    print(f"   📋 [WEBSOCKET DEBUG] Fetching final results from history...")
                    history = await self.get_execution_history(comfyui_url, prompt_id)
                    if history:
                        execution_result.outputs = history.get("outputs", {})
                        print(f"   ✅ [WEBSOCKET DEBUG] Got outputs: {list(execution_result.outputs.keys())}")
                
                return execution_result or PromptExecution(
                    prompt_id=prompt_id,
                    status=ExecutionStatus.FAILED.value,
                    error_message="WebSocket monitoring ended without completion"
                )
                
        except Exception as e:
            print(f"   ❌ [WEBSOCKET DEBUG] WebSocket error: {e}")
            print(f"   🔄 [WEBSOCKET DEBUG] Falling back to polling method...")
            # Fall back to regular polling if WebSocket fails
            return await self.wait_for_completion(comfyui_url, prompt_id)
    
    async def download_image(self, comfyui_url: str, filename: str, subfolder: str, folder_type: str) -> bytes:
        """Download a single generated image"""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        
        logger.debug(f"📥 Downloading image: {filename}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{comfyui_url}/view",
                    params=params
                )
            
            response.raise_for_status()
            logger.debug(f"✅ Downloaded {filename} ({len(response.content)} bytes)")
            return response.content
            
        except Exception as e:
            logger.error(f"❌ Failed to download {filename}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download image {filename}: {str(e)}"
            )
    
    async def save_generated_images(
        self, 
        comfyui_url: str, 
        outputs: Dict, 
        job_id: str
    ) -> Dict[str, GeneratedImage]:
        """Download and save all generated images"""
        print(f"\n💾 [IMAGE SAVE DEBUG] Starting image save for job: {job_id}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Available output nodes: {list(self.output_nodes.keys())}")
        print(f"   Outputs received: {list(outputs.keys())}")
        
        logger.info(f"💾 Saving generated images for job: {job_id}")
        
        saved_images = {}
        
        # Ensure we save to the user2imgs directory
        job_output_dir = self.output_dir
        job_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"   Saving to directory: {job_output_dir.absolute()}")
        
        for variant_name, node_id in self.output_nodes.items():
            print(f"\n🔍 [IMAGE SAVE DEBUG] Processing {variant_name} (node {node_id})")
            
            if node_id in outputs:
                node_outputs = outputs[node_id]
                images_data = node_outputs.get("images", [])
                
                print(f"   Found {len(images_data)} images for {variant_name}")
                
                if images_data:
                    # Take the first image for each variant
                    image_info = images_data[0]
                    filename = image_info["filename"]
                    subfolder = image_info.get("subfolder", "")
                    image_type = image_info.get("type", "output")
                    
                    print(f"   Downloading: {filename} (subfolder: {subfolder}, type: {image_type})")
                    logger.info(f"📥 Downloading {variant_name}: {filename}")
                    
                    # Download image
                    image_data = await self.download_image(
                        comfyui_url, filename, subfolder, image_type
                    )
                    
                    # Save with descriptive names in the main user2imgs directory
                    file_extension = Path(filename).suffix or ".png"
                    if variant_name == "variant_1":
                        local_filename = f"OP1{file_extension}"
                    elif variant_name == "variant_2":
                        local_filename = f"OP2{file_extension}"
                    elif variant_name == "variant_3":
                        local_filename = f"OP3{file_extension}"
                    elif variant_name == "assembly":
                        local_filename = f"Assembly Diagram{file_extension}"
                    else:
                        local_filename = f"{variant_name}{file_extension}"
                    
                    local_path = job_output_dir / local_filename
                    
                    print(f"   Saving as: {local_filename}")
                    print(f"   Full path: {local_path.absolute()}")
                    
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    
                    # Verify file was saved
                    if local_path.exists():
                        file_size = local_path.stat().st_size
                        print(f"   ✅ File saved successfully! Size: {file_size} bytes")
                    else:
                        print(f"   ❌ File save failed!")
                    
                    # Create web URL for frontend access
                    web_url = f"/output/user2imgs/{local_filename}"
                    
                    saved_images[variant_name] = GeneratedImage(
                        filename=filename,
                        subfolder=subfolder,
                        type=image_type,
                        url=web_url,
                        local_path=str(local_path)
                    )
                    
                    logger.info(f"✅ Saved {variant_name} -> {local_path}")
                else:
                    print(f"   ⚠️ No images found for {variant_name}")
                    logger.warning(f"⚠️ No images found for {variant_name} (node {node_id})")
            else:
                print(f"   ⚠️ Node {node_id} not found in outputs")
                logger.warning(f"⚠️ Node {node_id} not found in outputs for {variant_name}")
        
        print(f"\n💾 [IMAGE SAVE DEBUG] Summary:")
        print(f"   Total images saved: {len(saved_images)}")
        for name, img in saved_images.items():
            print(f"   - {name}: {img.local_path}")
        
        logger.info(f"💾 Saved {len(saved_images)} images for job {job_id}")
        return saved_images
    
    async def execute_workflow(
        self, 
        comfyui_url: str, 
        workflow: Dict[str, Any], 
        image: UploadFile, 
        prompt: str, 
        job_id: str
    ) -> Tuple[PromptExecution, Dict[str, GeneratedImage]]:
        """Execute complete workflow from submission to result retrieval"""
        logger.info(f"🎨 Starting workflow execution for job: {job_id}")
        
        # Prepare workflow with data
        prepared_workflow = self.prepare_workflow(workflow, image, prompt)
        
        # Submit workflow
        prompt_id, client_id = await self.submit_workflow(comfyui_url, prepared_workflow)
        
        # Wait for completion using WebSocket monitoring
        print(f"\n🔌 [WORKFLOW DEBUG] Switching to WebSocket monitoring for real-time updates...")
        print(f"   Using same client_id from submission: {client_id}")
        execution = await self.wait_for_completion_websocket(comfyui_url, prompt_id, client_id)
        
        if execution.status == ExecutionStatus.FAILED.value:
            logger.error(f"❌ Workflow execution failed: {execution.error_message}")
            raise HTTPException(
                status_code=500,
                detail=f"Workflow execution failed: {execution.error_message}"
            )
        
        # Download and save results
        saved_images = await self.save_generated_images(comfyui_url, execution.outputs, job_id)
        
        logger.info(f"🎨 Workflow execution completed successfully for job: {job_id}")
        return execution, saved_images
    
    async def monitor_with_websocket(self, comfyui_url: str, prompt_id: str, callback=None):
        """Monitor execution progress via WebSocket (optional real-time updates)"""
        ws_url = comfyui_url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())
        
        logger.info(f"🔌 Connecting to WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(f"{ws_url}?clientId={client_id}") as websocket:
                logger.info(f"🔌 WebSocket connected for prompt: {prompt_id}")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        if data.get("type") == "executing":
                            node_id = data.get("data", {}).get("node")
                            if callback:
                                await callback("executing", {"node_id": node_id})
                        
                        elif data.get("type") == "execution_cached":
                            if callback:
                                await callback("cached", data.get("data", {}))
                        
                        elif data.get("type") == "executed":
                            if callback:
                                await callback("executed", data.get("data", {}))
                        
                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON WebSocket message: {message}")
                        
        except Exception as e:
            logger.warning(f"⚠️ WebSocket monitoring failed: {e}")
            # WebSocket is optional, don't raise exception
