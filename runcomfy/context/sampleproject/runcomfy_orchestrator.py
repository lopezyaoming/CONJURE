"""
RunComfy Orchestrator - High-level coordination of RunComfy workflow execution
Manages the complete lifecycle: machine launch → workflow execution → cleanup
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from loguru import logger
from fastapi import HTTPException, UploadFile

from .runcomfy_client import RunComfyAPIClient, MachineInfo, MachineStatus
from .comfyui_workflow_client import ComfyUIWorkflowClient, PromptExecution, GeneratedImage
from .models import JobStatus


@dataclass
class RunComfyJob:
    job_id: str
    status: str
    prompt: str
    image_filename: str
    server_id: Optional[str] = None
    comfyui_url: Optional[str] = None
    prompt_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    generated_images: Optional[Dict[str, str]] = None
    machine_cost_estimate: Optional[float] = None


class RunComfyOrchestrator:
    """High-level orchestrator for RunComfy workflow execution"""
    
    def __init__(self, workflow_path: str = "backend/workflows/user2imgs.json"):
        self.workflow_path = workflow_path
        self.runcomfy_client = RunComfyAPIClient()
        self.comfyui_client = ComfyUIWorkflowClient()
        
        # Job tracking
        self.active_jobs: Dict[str, RunComfyJob] = {}
        self.machine_pool: Dict[str, MachineInfo] = {}
        
        # Configuration
        self.auto_shutdown = os.getenv("RUNCOMFY_AUTO_SHUTDOWN", "true").lower() == "true"
        self.machine_reuse = os.getenv("RUNCOMFY_MACHINE_REUSE", "true").lower() == "true"
        self.idle_timeout = int(os.getenv("RUNCOMFY_IDLE_TIMEOUT", "300"))  # 5 minutes
        self.cost_per_hour = {
            "medium": 0.50,
            "large": 1.00,
            "extra-large": 2.00,
            "2x-large": 4.00,
            "2xl-turbo": 6.00
        }
        
        logger.info(f"🎭 RunComfy Orchestrator initialized")
        logger.info(f"   Workflow: {self.workflow_path}")
        logger.info(f"   Auto shutdown: {self.auto_shutdown}")
        logger.info(f"   Machine reuse: {self.machine_reuse}")
        logger.info(f"   Idle timeout: {self.idle_timeout}s")
    
    def load_workflow(self) -> Dict[str, Any]:
        """Load the user2imgs workflow"""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            logger.info(f"📄 Loaded workflow with {len(workflow)} nodes")
            return workflow
        except Exception as e:
            logger.error(f"❌ Failed to load workflow: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to load workflow: {str(e)}")
    
    def estimate_cost(self, machine_info: MachineInfo, duration_seconds: int) -> float:
        """Estimate cost for machine usage"""
        hourly_rate = self.cost_per_hour.get(machine_info.server_type, 1.0)
        hours = duration_seconds / 3600
        cost = hourly_rate * hours
        return round(cost, 4)
    
    async def get_or_create_machine(self, workflow_name: str = "user2imgs") -> MachineInfo:
        """Get an existing ready machine or create a new one"""
        logger.info(f"🏭 Getting machine for workflow: {workflow_name}")
        
        if self.machine_reuse:
            # Check if we have a ready machine in our pool
            for server_id, machine in self.machine_pool.items():
                if machine.current_status == MachineStatus.READY.value:
                    logger.info(f"♻️ Reusing pooled machine: {server_id}")
                    return machine
        
        # Get or create machine through RunComfy API
        machine_info = await self.runcomfy_client.get_or_create_ready_machine(workflow_name)
        
        # Add to our pool
        self.machine_pool[machine_info.server_id] = machine_info
        
        logger.info(f"🏭 Machine ready: {machine_info.server_id}")
        logger.info(f"   Type: {machine_info.server_type}")
        logger.info(f"   URL: {machine_info.main_service_url}")
        
        return machine_info
    
    async def cleanup_machine(self, server_id: str, force: bool = False):
        """Clean up machine based on configuration"""
        if server_id not in self.machine_pool:
            logger.warning(f"⚠️ Machine {server_id} not in pool")
            return
        
        machine = self.machine_pool[server_id]
        
        if force or self.auto_shutdown:
            logger.info(f"🛑 Stopping machine: {server_id}")
            try:
                await self.runcomfy_client.stop_machine(server_id)
                del self.machine_pool[server_id]
                logger.info(f"✅ Machine {server_id} stopped and removed from pool")
            except Exception as e:
                logger.error(f"❌ Failed to stop machine {server_id}: {e}")
        else:
            logger.info(f"🔄 Keeping machine {server_id} in pool for reuse")
    
    async def execute_job(
        self, 
        job_id: str, 
        image: UploadFile, 
        prompt: str,
        workflow_name: str = "user2imgs"
    ) -> RunComfyJob:
        """Execute a complete RunComfy job from start to finish"""
        logger.info(f"🚀 Starting RunComfy job execution: {job_id}")
        logger.info(f"   Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        logger.info(f"   Image: {image.filename}")
        
        # Create job record
        job = RunComfyJob(
            job_id=job_id,
            status=JobStatus.QUEUED,
            prompt=prompt,
            image_filename=image.filename,
            created_at=datetime.now().isoformat()
        )
        self.active_jobs[job_id] = job
        
        start_time = time.time()
        
        try:
            # Step 1: Get or create machine
            print(f"\n🚀 [WORKFLOW DEBUG] Job {job_id} - STEP 1: Getting/Creating Machine")
            logger.info(f"🏭 [Job {job_id}] Getting machine...")
            job.status = "launching_machine"
            machine_info = await self.get_or_create_machine(workflow_name)
            
            job.server_id = machine_info.server_id
            job.comfyui_url = machine_info.main_service_url
            print(f"✅ [WORKFLOW DEBUG] Job {job_id} - Machine ready: {machine_info.server_id}")
            print(f"   ComfyUI URL: {machine_info.main_service_url}")
            
            # Step 2: Load workflow
            print(f"\n📄 [WORKFLOW DEBUG] Job {job_id} - STEP 2: Loading Workflow")
            logger.info(f"📄 [Job {job_id}] Loading workflow...")
            job.status = "loading_workflow"
            workflow = self.load_workflow()
            print(f"✅ [WORKFLOW DEBUG] Job {job_id} - Workflow loaded with {len(workflow)} nodes")
            
            # Step 3: Execute workflow
            print(f"\n🎨 [WORKFLOW DEBUG] Job {job_id} - STEP 3: Executing Workflow")
            print(f"   Uploading image: {image.filename}")
            print(f"   Using prompt: {prompt}")
            logger.info(f"🎨 [Job {job_id}] Executing workflow...")
            job.status = "executing_workflow"
            job.started_at = datetime.now().isoformat()
            
            execution, generated_images = await self.comfyui_client.execute_workflow(
                comfyui_url=machine_info.main_service_url,
                workflow=workflow,
                image=image,
                prompt=prompt,
                job_id=job_id
            )
            
            job.prompt_id = execution.prompt_id
            print(f"✅ [WORKFLOW DEBUG] Job {job_id} - Workflow execution complete!")
            print(f"   Prompt ID: {execution.prompt_id}")
            print(f"   Generated {len(generated_images)} images")
            
            # Step 4: Process results
            print(f"\n💾 [WORKFLOW DEBUG] Job {job_id} - STEP 4: Processing Results")
            logger.info(f"💾 [Job {job_id}] Processing results...")
            job.status = "processing_results"
            job.generated_images = {
                name: img.url for name, img in generated_images.items()
            }
            print(f"✅ [WORKFLOW DEBUG] Job {job_id} - Results processed")
            
            # Step 5: Calculate costs
            duration = time.time() - start_time
            job.machine_cost_estimate = self.estimate_cost(machine_info, duration)
            
            # Step 6: Mark as completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ [Job {job_id}] Completed successfully!")
            logger.info(f"   Duration: {duration:.1f}s")
            logger.info(f"   Cost estimate: ${job.machine_cost_estimate}")
            logger.info(f"   Generated images: {len(generated_images)}")
            
            # Step 7: Cleanup (background task)
            if not self.machine_reuse:
                asyncio.create_task(self.cleanup_machine(machine_info.server_id))
            
            return job
            
        except Exception as e:
            # Handle errors
            duration = time.time() - start_time
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now().isoformat()
            
            if job.server_id:
                job.machine_cost_estimate = self.estimate_cost(
                    self.machine_pool.get(job.server_id), duration
                ) if job.server_id in self.machine_pool else 0.0
            
            logger.error(f"❌ [Job {job_id}] Failed after {duration:.1f}s: {e}")
            
            # Cleanup on error
            if job.server_id and self.auto_shutdown:
                asyncio.create_task(self.cleanup_machine(job.server_id, force=True))
            
            raise e
    
    async def get_job_status(self, job_id: str) -> Optional[RunComfyJob]:
        """Get current status of a job"""
        return self.active_jobs.get(job_id)
    
    async def list_active_jobs(self) -> List[RunComfyJob]:
        """List all active jobs"""
        return list(self.active_jobs.values())
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        if job_id not in self.active_jobs:
            return False
        
        job = self.active_jobs[job_id]
        logger.info(f"❌ Cancelling job: {job_id}")
        
        job.status = "cancelled"
        job.completed_at = datetime.now().isoformat()
        
        # Cleanup machine if auto-shutdown enabled
        if job.server_id and self.auto_shutdown:
            asyncio.create_task(self.cleanup_machine(job.server_id, force=True))
        
        return True
    
    async def get_machine_status(self) -> Dict[str, Any]:
        """Get status of all machines in pool"""
        machine_statuses = {}
        
        for server_id, machine in self.machine_pool.items():
            try:
                # Refresh machine status
                updated_machine = await self.runcomfy_client.get_machine_status(server_id)
                self.machine_pool[server_id] = updated_machine
                
                machine_statuses[server_id] = {
                    "status": updated_machine.current_status,
                    "type": updated_machine.server_type,
                    "url": updated_machine.main_service_url,
                    "estimated_stopping_at": updated_machine.estimated_stopping_at,
                    "ready_at": updated_machine.service_ready_at
                }
            except Exception as e:
                logger.error(f"❌ Failed to get status for machine {server_id}: {e}")
                machine_statuses[server_id] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return machine_statuses
    
    async def cleanup_idle_machines(self):
        """Background task to cleanup idle machines"""
        if not self.auto_shutdown:
            return
        
        logger.info("🧹 Checking for idle machines to cleanup...")
        
        cutoff_time = datetime.now() - timedelta(seconds=self.idle_timeout)
        
        for job_id, job in list(self.active_jobs.items()):
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED] and 
                job.completed_at and 
                datetime.fromisoformat(job.completed_at) < cutoff_time):
                
                if job.server_id:
                    logger.info(f"🧹 Cleaning up idle machine for job {job_id}")
                    await self.cleanup_machine(job.server_id, force=True)
                
                # Remove old job record
                del self.active_jobs[job_id]
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics for monitoring"""
        metrics = {
            "active_jobs": len(self.active_jobs),
            "pooled_machines": len(self.machine_pool),
            "jobs_by_status": {},
            "machines_by_status": {},
            "total_estimated_cost": 0.0
        }
        
        # Job statistics
        for job in self.active_jobs.values():
            status = job.status
            metrics["jobs_by_status"][status] = metrics["jobs_by_status"].get(status, 0) + 1
            
            if job.machine_cost_estimate:
                metrics["total_estimated_cost"] += job.machine_cost_estimate
        
        # Machine statistics
        for machine in self.machine_pool.values():
            status = machine.current_status
            metrics["machines_by_status"][status] = metrics["machines_by_status"].get(status, 0) + 1
        
        metrics["total_estimated_cost"] = round(metrics["total_estimated_cost"], 4)
        
        return metrics
    
    def to_dict(self, job: RunComfyJob) -> Dict[str, Any]:
        """Convert job to dictionary for API responses"""
        return asdict(job)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the orchestrator"""
        try:
            # Check if we can connect to RunComfy API
            workflows = await self.runcomfy_client.list_workflows()
            
            health = {
                "status": "healthy",
                "runcomfy_api": "connected",
                "available_workflows": len(workflows),
                "active_jobs": len(self.active_jobs),
                "pooled_machines": len(self.machine_pool),
                "configuration": {
                    "auto_shutdown": self.auto_shutdown,
                    "machine_reuse": self.machine_reuse,
                    "idle_timeout": self.idle_timeout
                }
            }
            
            return health
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "runcomfy_api": "disconnected"
            }
