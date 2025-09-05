"""
RunComfy Serverless API Client
Direct interface to RunComfy's new serverless workflow API endpoints.
Replaces server management with instant workflow execution.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import httpx


class RequestStatus(Enum):
    """Request execution status"""
    IN_QUEUE = "in_queue"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class ServerlessRequest:
    """Represents a serverless workflow request"""
    request_id: str
    deployment_id: str
    status: RequestStatus
    queue_position: Optional[int] = None
    outputs: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None
    cost_estimate: Optional[float] = None


class ServerlessRunComfyClient:
    """
    Client for RunComfy Serverless API
    Handles workflow execution without server management.
    """
    
    def __init__(self):
        # Configuration from environment or serverlessruncomfyinfo.txt
        self.base_url = "https://api.runcomfy.net"
        self.api_token = os.getenv("RUNCOMFY_API_TOKEN", "78356331-a9ec-49c2-a412-59140b32b9b3")
        self.user_id = os.getenv("RUNCOMFY_USER_ID", "0cb54d51-f01e-48e1-ae7b-28d1c21bc947")
        self.deployment_id = os.getenv("RUNCOMFY_DEPLOYMENT_ID", "dfcf38cd-0a09-4637-a067-5059dc9e444e")
        
        # Request settings
        self.max_retries = int(os.getenv("RUNCOMFY_MAX_RETRIES", "3"))
        self.poll_interval = int(os.getenv("RUNCOMFY_POLL_INTERVAL", "2"))  # 2 seconds for serverless
        self.request_timeout = int(os.getenv("RUNCOMFY_REQUEST_TIMEOUT", "1800"))  # 30 minutes
        
        print(f"🚀 RunComfy Serverless Client initialized")
        print(f"   Base URL: {self.base_url}")
        print(f"   User ID: {self.user_id}")
        print(f"   Deployment ID: {self.deployment_id}")
        print(f"   API Token: {self.api_token[:8]}...")
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling and retries"""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json_data,
                        params=params
                    )
                    
                    if response.status_code in [200, 202]:
                        return response.json()
                    elif response.status_code == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        print(f"⏳ Rate limited, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                        print(f"❌ API request failed: {error_msg}")
                        if attempt == self.max_retries - 1:
                            raise httpx.HTTPStatusError(error_msg, request=response.request, response=response)
                        
            except httpx.TimeoutException:
                print(f"⏳ Request timeout, retry {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                print(f"❌ Request error: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise RuntimeError(f"Failed to complete request after {self.max_retries} attempts")
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image file to Base64 data URI"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Determine MIME type based on file extension
            path = Path(image_path)
            if path.suffix.lower() in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif path.suffix.lower() == '.png':
                mime_type = 'image/png'
            elif path.suffix.lower() == '.webp':
                mime_type = 'image/webp'
            else:
                mime_type = 'image/png'  # Default
            
            # Encode to Base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            data_uri = f"data:{mime_type};base64,{base64_data}"
            
            print(f"✅ Encoded image {image_path} to Base64 ({len(base64_data)} chars)")
            return data_uri
            
        except Exception as e:
            print(f"❌ Failed to encode image {image_path}: {e}")
            raise
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 data URI - PROVEN TO WORK!"""
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded_string}"

    def build_conjure_overrides(
        self,
        prompt: str,
        render_image_path: str,
        seed: Optional[int] = None,
        steps_flux: int = 20,
        steps_partpacker: int = 50
    ) -> Dict[str, Any]:
        """
        Build overrides for CONJURE workflow - FIXED TO MATCH WORKING IMPLEMENTATION
        
        WORKING Node mapping (from successful runcomfy_api_client.py):
        #16: INPUTIMAGE - Input: Base64 data URI (CONFIRMED WORKING!)
        #40: FLUXCLIP - Input: Empty string "" (NOT the prompt!)
        #41: FLUXT5XXL - Input: Actual user prompt
        #42: NOISESEED - Input: Random seed integer
        
        NOTE: Nodes 43, 44 are NOT used in working implementation!
        """
        
        # Generate seed if not provided
        if seed is None:
            import random
            seed = random.randint(1, 1000000000)
        
        # CRITICAL FIX: Use Base64 data URI format (PROVEN TO WORK!)
        image_base64 = self.encode_image_to_base64(render_image_path)
        print(f"🔧 Using Base64 data URI format (CONFIRMED WORKING!)")
        print(f"   ✅ This format works in successful implementation")
        
        # EXACT format from working runcomfy_api_client.py
        overrides = {
            "16": {  # INPUTIMAGE - LoadImage node
                "inputs": {
                    "image": image_base64  # Base64 data URI (WORKING!)
                }
            },
            "40": {  # FLUXCLIP - PrimitiveStringMultiline (EMPTY!)
                "inputs": {
                    "value": ""  # Empty string in working code!
                }
            },
            "41": {  # FLUXT5XXL - PrimitiveStringMultiline (ACTUAL PROMPT!)
                "inputs": {
                    "value": prompt  # Real prompt goes here
                }
            },
            "42": {  # NOISESEED - PrimitiveInt
                "inputs": {
                    "value": seed  # Random seed
                }
            }
            # CRITICAL: NO nodes 43, 44 in working implementation!
        }
        
        print(f"🔧 Built CONJURE overrides (WORKING FORMAT):")
        print(f"   Node 16: Base64 image data")
        print(f"   Node 40: Empty string (as per working code)")
        print(f"   Node 41: User prompt - {prompt[:100]}...")
        print(f"   Node 42: Seed - {seed}")
        print(f"   Nodes 43,44: SKIPPED (not in working implementation)")
        
        return overrides
    
    async def submit_request(
        self,
        prompt: str,
        render_image_path: str,
        seed: Optional[int] = None,
        steps_flux: int = 20,
        steps_partpacker: int = 50
    ) -> ServerlessRequest:
        """
        Submit inference request to serverless workflow
        
        Args:
            prompt: Text prompt for FLUX generation
            render_image_path: Path to render.png from GestureCamera
            seed: Random seed for generation
            steps_flux: Number of FLUX inference steps
            steps_partpacker: Number of PartPacker steps
            
        Returns:
            ServerlessRequest object with tracking information
        """
        print(f"🚀 Submitting serverless request...")
        print(f"   Deployment: {self.deployment_id}")
        print(f"   Prompt: {prompt[:100]}...")
        print(f"   Image: {render_image_path}")
        
        # Build overrides for CONJURE workflow
        overrides = self.build_conjure_overrides(
            prompt=prompt,
            render_image_path=render_image_path,
            seed=seed,
            steps_flux=steps_flux,
            steps_partpacker=steps_partpacker
        )
        
        # Submit request
        endpoint = f"/prod/v1/deployments/{self.deployment_id}/inference"
        payload = {"overrides": overrides}
        
        print(f"🔧 Submitting to endpoint: {endpoint}")
        print(f"🔧 Payload keys: {list(payload.keys())}")
        print(f"🔧 Override nodes: {list(overrides.keys())}")
        
        try:
            response = await self._make_request(
                method="POST",
                endpoint=endpoint,
                json_data=payload
            )
            
            print(f"🔍 Raw submit response: {response}")
            
            request_id = response["request_id"]
            
            serverless_request = ServerlessRequest(
                request_id=request_id,
                deployment_id=self.deployment_id,
                status=RequestStatus.IN_QUEUE
            )
            
            print(f"✅ Request submitted successfully: {request_id}")
            print(f"   Status URL: {response.get('status_url', 'N/A')}")
            print(f"   Result URL: {response.get('result_url', 'N/A')}")
            
            return serverless_request
            
        except Exception as e:
            print(f"❌ Failed to submit request: {e}")
            raise
    
    async def get_request_status(self, request_id: str) -> ServerlessRequest:
        """Get current status of a request"""
        endpoint = f"/prod/v1/deployments/{self.deployment_id}/requests/{request_id}/status"
        
        try:
            response = await self._make_request(
                method="GET",
                endpoint=endpoint
            )
            
            # Debug logging
            print(f"🔍 Raw status response: {response}")
            
            status_str = response.get("status", "unknown")
            try:
                status = RequestStatus(status_str)
            except ValueError:
                print(f"⚠️ Unknown status: {status_str}")
                status = RequestStatus.IN_QUEUE
            
            return ServerlessRequest(
                request_id=request_id,
                deployment_id=self.deployment_id,
                status=status,
                queue_position=response.get("queue_position"),
                created_at=response.get("created_at"),
                finished_at=response.get("finished_at")
            )
            
        except Exception as e:
            print(f"❌ Failed to get request status: {e}")
            raise
    
    async def get_request_result(self, request_id: str) -> ServerlessRequest:
        """Get final result of a completed request"""
        endpoint = f"/prod/v1/deployments/{self.deployment_id}/requests/{request_id}/result"
        
        try:
            response = await self._make_request(
                method="GET",
                endpoint=endpoint
            )
            
            status_str = response.get("status", "unknown")
            try:
                status = RequestStatus(status_str)
            except ValueError:
                print(f"⚠️ Unknown status: {status_str}")
                status = RequestStatus.FAILED
            
            return ServerlessRequest(
                request_id=request_id,
                deployment_id=self.deployment_id,
                status=status,
                outputs=response.get("outputs"),
                error_message=response.get("error"),
                created_at=response.get("created_at"),
                finished_at=response.get("finished_at")
            )
            
        except Exception as e:
            print(f"❌ Failed to get request result: {e}")
            raise
    
    async def wait_for_completion(
        self, 
        request_id: str, 
        timeout: int = None
    ) -> ServerlessRequest:
        """
        Wait for request to complete with progress monitoring
        
        Args:
            request_id: Request ID to monitor
            timeout: Timeout in seconds
            
        Returns:
            Final ServerlessRequest with results or error
        """
        timeout = timeout or self.request_timeout
        start_time = time.time()
        
        print(f"⏳ Waiting for request {request_id} to complete (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            try:
                # Check status
                request = await self.get_request_status(request_id)
                
                if request.status in [RequestStatus.IN_QUEUE]:
                    position = request.queue_position or "unknown"
                    print(f"   📋 In queue (position: {position})")
                elif request.status == RequestStatus.IN_PROGRESS:
                    print(f"   🔄 Processing...")
                elif request.status in [RequestStatus.COMPLETED, RequestStatus.SUCCEEDED]:
                    print(f"   ✅ Completed! Getting results...")
                    return await self.get_request_result(request_id)
                elif request.status in [RequestStatus.FAILED, RequestStatus.CANCELED]:
                    print(f"   ❌ Request {request.status.value}")
                    return await self.get_request_result(request_id)
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"⚠️ Error checking request status: {e}")
                await asyncio.sleep(self.poll_interval)
        
        print(f"⏰ Timeout waiting for request {request_id} to complete")
        raise TimeoutError(f"Request {request_id} did not complete within {timeout} seconds")
    
    async def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a queued or running request
        
        Args:
            request_id: Request ID to cancel
            
        Returns:
            True if cancellation was accepted, False otherwise
        """
        endpoint = f"/prod/v1/deployments/{self.deployment_id}/requests/{request_id}/cancel"
        
        try:
            print(f"🛑 Cancelling request: {request_id}")
            
            response = await self._make_request(
                method="POST",
                endpoint=endpoint
            )
            
            status = response.get("status", "unknown")
            if status == "cancellation_requested":
                print(f"✅ Cancellation requested for {request_id}")
                return True
            else:
                print(f"⚠️ Cancellation not possible: {status}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to cancel request: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if serverless client is properly configured"""
        return bool(self.api_token and self.deployment_id and self.user_id)
    
    async def download_outputs(self, request: ServerlessRequest, output_dir: Path) -> Dict[str, str]:
        """
        Download output files from completed request
        
        Args:
            request: Completed ServerlessRequest with outputs
            output_dir: Directory to save downloaded files
            
        Returns:
            Dictionary mapping output types to local file paths
        """
        if not request.outputs:
            print("⚠️ No outputs available to download")
            return {}
        
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded_files = {}
        
        try:
            # Based on serverlessruncomfyinfo.txt:
            # #33: EXPORTGLB: **Output**: 3D mesh (via PartPacker)
            # #24: EXPORT IMAGE: **Output**: FLUX-generated image
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Download FLUX image (node 24)
                if "24" in request.outputs:
                    image_outputs = request.outputs["24"]
                    if "images" in image_outputs and image_outputs["images"]:
                        image_info = image_outputs["images"][0]
                        image_url = image_info["url"]
                        
                        print(f"📥 Downloading FLUX image from {image_url}")
                        response = await client.get(image_url)
                        response.raise_for_status()
                        
                        flux_path = output_dir / "flux.png"
                        with open(flux_path, 'wb') as f:
                            f.write(response.content)
                        
                        downloaded_files["flux_image"] = str(flux_path)
                        print(f"✅ Downloaded FLUX image: {flux_path}")
                
                # Download 3D mesh (node 33)
                if "33" in request.outputs:
                    mesh_outputs = request.outputs["33"]
                    if "files" in mesh_outputs and mesh_outputs["files"]:
                        mesh_info = mesh_outputs["files"][0]
                        mesh_url = mesh_info["url"]
                        
                        print(f"📥 Downloading 3D mesh from {mesh_url}")
                        response = await client.get(mesh_url)
                        response.raise_for_status()
                        
                        mesh_path = output_dir / "partpacker_result_0.glb"
                        with open(mesh_path, 'wb') as f:
                            f.write(response.content)
                        
                        downloaded_files["mesh_model"] = str(mesh_path)
                        print(f"✅ Downloaded 3D mesh: {mesh_path}")
        
        except Exception as e:
            print(f"❌ Error downloading outputs: {e}")
            raise
        
        return downloaded_files
