import base64
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import HTTPException, UploadFile
from loguru import logger

from .models import JobStatus
from .utils import FileManager
from .runcomfy_orchestrator import RunComfyOrchestrator
from .comfyui_workflow_client import ComfyUIWorkflowClient
import asyncio

class ComfyUIService:
    """Service for interacting with ComfyUI API - supports both local and RunComfy cloud modes."""

    def __init__(self, file_manager: FileManager, workflow_path: str):
        self.file_manager = file_manager
        self.workflow_path = workflow_path
        
        # Determine operation mode
        self.mode = os.getenv("COMFYUI_MODE", "cloud").lower()  # "local" or "cloud"
        
        if self.mode == "cloud":
            # RunComfy cloud mode
            logger.info("🌩️ ComfyUI Service initialized in CLOUD mode (RunComfy)")
            self.runcomfy_orchestrator = RunComfyOrchestrator(workflow_path)
        else:
            # Local ComfyUI mode (existing functionality)
            logger.info("🏠 ComfyUI Service initialized in LOCAL mode")
            self.comfyui_url = os.getenv("COMFYUI_URL", "http://localhost:8188")
            self.api_key = os.getenv("COMFYUI_API_KEY", "")
            self.image_node_id = "1271"  # Updated for base64 image node
            self.prompt_node_id = "1223"  # Updated for direct text input
            self.comfyui_workflow_client = ComfyUIWorkflowClient(output_dir="data/output/user2imgs")

    def load_workflow(self) -> Dict[str, Any]:
        """Load the ComfyUI workflow from the specified path."""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Workflow file not found at {self.workflow_path}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from {self.workflow_path}")
            raise

    async def check_connection(self):
        """Check if the ComfyUI server is running."""
        if self.mode == "cloud":
            # Check RunComfy health
            logger.info("🌩️ Checking RunComfy cloud connection...")
            try:
                health = await self.runcomfy_orchestrator.health_check()
                if health["status"] == "healthy":
                    logger.info("✅ RunComfy cloud connection successful.")
                    return health
                else:
                    logger.error(f"❌ RunComfy cloud health check failed: {health}")
                    raise HTTPException(status_code=503, detail=f"RunComfy cloud unavailable: {health.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to RunComfy cloud: {e}")
                raise HTTPException(status_code=503, detail=f"Cannot connect to RunComfy cloud: {str(e)}")
        else:
            # Local ComfyUI connection check
            logger.info(f"🏠 Checking local ComfyUI connection at {self.comfyui_url}...")
            try:
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.comfyui_url}/object_info", headers=headers, timeout=5)
                response.raise_for_status()
                logger.info("✅ Local ComfyUI connection successful.")
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"❌ Failed to connect to local ComfyUI at {self.comfyui_url}. Error: {e}")
                raise HTTPException(status_code=503, detail=f"Cannot connect to local ComfyUI server at {self.comfyui_url}")

    async def queue_job(self, job_id: str, image: UploadFile, prompt: str) -> Dict[str, Any]:
        """Queue a new job in ComfyUI (local or cloud mode)."""
        logger.info(f"🚀 Queueing job {job_id} in {self.mode.upper()} mode")
        logger.info(f"   Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        logger.info(f"   Image: {image.filename}")
        
        if self.mode == "cloud":
            # RunComfy cloud execution - Read image data first, then start job asynchronously
            try:
                logger.info("🌩️ Starting job via RunComfy cloud...")
                print(f"\n🚀 [JOB START DEBUG] Starting RunComfy job: {job_id}")
                
                # Read image data immediately while file handle is still open
                try:
                    print(f"📥 [JOB START DEBUG] Reading image data before background task...")
                    image_content = await image.read()
                    print(f"✅ [JOB START DEBUG] Read {len(image_content)} bytes from {image.filename}")
                    
                    # Reset file pointer in case it's needed elsewhere
                    if hasattr(image.file, 'seek'):
                        try:
                            image.file.seek(0)
                        except:
                            pass  # File might be closed already
                    
                except Exception as read_error:
                    logger.error(f"❌ Failed to read image data: {read_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to read image data: {str(read_error)}")
                
                # Start the job execution in the background with pre-read data
                asyncio.create_task(self._execute_cloud_job_async(
                    job_id, 
                    image_content, 
                    image.filename, 
                    image.content_type, 
                    prompt
                ))
                
                # Return immediately with "queued" status
                return {
                    "status": "queued",
                    "job_id": job_id,
                    "comfyui_prompt_id": None,  # Will be set once execution starts
                    "server_id": None,  # Will be set once machine is ready
                    "message": f"Job queued for RunComfy cloud execution"
                }
                
            except HTTPException:
                # Re-raise HTTP exceptions
                raise
            except Exception as e:
                logger.error(f"❌ RunComfy cloud job start failed: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to start cloud job: {str(e)}")
        else:
            # Local ComfyUI execution (existing functionality)
            try:
                # Load workflow JSON
                workflow_path = Path(self.workflow_path)
                if not workflow_path.exists():
                    raise HTTPException(status_code=500, detail="Workflow file not found")
                
                with open(workflow_path, 'r') as f:
                    workflow_data = json.load(f)
                
                # Execute workflow using ComfyUI client
                execution, saved_images = await self.comfyui_workflow_client.execute_workflow(
                    self.comfyui_url,
                    workflow_data,
                    image,
                    prompt,
                    job_id
                )
                
                # Convert to frontend-expected format
                generated_images = {}
                for variant_name, image_info in saved_images.items():
                    generated_images[variant_name] = image_info.url
                
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "comfyui_prompt_id": execution.prompt_id,
                    "message": "Job executed successfully via local ComfyUI",
                    "generated_images": generated_images
                }
                
            except Exception as e:
                logger.error(f"❌ Local ComfyUI execution failed: {e}")
                raise e
    
    async def _execute_cloud_job_async(self, job_id: str, image_data: bytes, filename: str, content_type: str, prompt: str):
        """Execute RunComfy job in the background with pre-read image data"""
        try:
            print(f"\n🎬 [BACKGROUND JOB DEBUG] Starting background execution for job: {job_id}")
            print(f"   Image file: {filename}")
            print(f"   Image content type: {content_type}")
            print(f"   Image data size: {len(image_data)} bytes")
            
            # Create a new file-like object for the orchestrator
            try:
                print(f"📥 [BACKGROUND JOB DEBUG] Creating file object from pre-read data...")
                
                from io import BytesIO
                
                # Create a new UploadFile-like object
                class MockUploadFile:
                    def __init__(self, content, filename, content_type):
                        self.file = BytesIO(content)
                        self.filename = filename
                        self.content_type = content_type
                    
                    async def read(self):
                        return self.file.read()
                    
                    def read_sync(self):
                        return self.file.read()
                
                mock_image = MockUploadFile(image_data, filename, content_type)
                print(f"✅ [BACKGROUND JOB DEBUG] Created mock image file successfully")
                
            except Exception as file_error:
                print(f"❌ [BACKGROUND JOB DEBUG] Failed to create image object: {file_error}")
                raise HTTPException(status_code=500, detail=f"Failed to create image object: {file_error}")
            
            # Execute the full workflow
            job = await self.runcomfy_orchestrator.execute_job(job_id, mock_image, prompt)
            
            print(f"✅ [BACKGROUND JOB DEBUG] Job {job_id} completed successfully!")
            print(f"   Status: {job.status}")
            print(f"   Generated images: {len(job.generated_images) if job.generated_images else 0}")
            
        except Exception as e:
            logger.error(f"❌ Background job {job_id} failed: {e}")
            print(f"❌ [BACKGROUND JOB DEBUG] Job {job_id} failed: {e}")
            print(f"❌ [BACKGROUND JOB DEBUG] Error details: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"❌ [BACKGROUND JOB DEBUG] Traceback:")
            traceback.print_exc()
            # The orchestrator will handle job status updates
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status (cloud mode specific)"""
        if self.mode == "cloud":
            job = await self.runcomfy_orchestrator.get_job_status(job_id)
            if job:
                # Convert job dataclass to dict
                return {
                    "job_id": job.job_id,
                    "status": job.status,
                    "prompt": job.prompt,
                    "server_id": job.server_id,
                    "comfyui_url": job.comfyui_url,
                    "prompt_id": job.prompt_id,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "error_message": job.error_message,
                    "generated_images": job.generated_images,
                    "machine_cost_estimate": job.machine_cost_estimate
                }
            else:
                raise HTTPException(status_code=404, detail="Job not found")
        else:
            # Local mode uses existing route logic
            raise HTTPException(status_code=501, detail="Use /jobs/{job_id}/status endpoint for local mode")
