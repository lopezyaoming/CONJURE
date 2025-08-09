"""
RunComfy Orchestrator for CONJURE - High-level coordination of flux mesh generation workflow.
Manages the complete lifecycle: machine management → workflow execution → result handling.
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

# Import our components
try:
    from .runcomfy_client import RunComfyAPIClient, MachineInfo, MachineStatus
    from .comfyui_workflow_client import ComfyUIWorkflowClient, PromptExecution, ExecutionStatus
    from .dev_server_state import DevServerStateManager, DevServerState
    from .workflow_progress_tracker import progress_tracker
except ImportError:
    from runcomfy_client import RunComfyAPIClient, MachineInfo, MachineStatus
    from comfyui_workflow_client import ComfyUIWorkflowClient, PromptExecution, ExecutionStatus
    from dev_server_state import DevServerStateManager, DevServerState
    from workflow_progress_tracker import progress_tracker


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FluxMeshJob:
    """Represents a complete flux mesh generation job"""
    job_id: str
    status: JobStatus
    prompt: str
    input_image_path: Optional[str] = None
    
    # Machine details
    server_id: Optional[str] = None
    comfyui_url: Optional[str] = None
    
    # Workflow execution
    prompt_id: Optional[str] = None
    client_id: Optional[str] = None
    
    # Timing
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Results
    generated_image_url: Optional[str] = None
    generated_mesh_url: Optional[str] = None
    result_files: Optional[Dict[str, str]] = None
    
    # Error handling
    error_message: Optional[str] = None
    
    # Cost tracking
    machine_cost_estimate: Optional[float] = None
    actual_machine_cost: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "prompt": self.prompt,
            "input_image_path": self.input_image_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "generated_image_url": self.generated_image_url,
            "generated_mesh_url": self.generated_mesh_url,
            "result_files": self.result_files,
            "error_message": self.error_message,
            "machine_cost_estimate": self.machine_cost_estimate,
            "actual_machine_cost": self.actual_machine_cost,
            "progress_summary": progress_tracker.get_workflow_summary(self.prompt_id) if self.prompt_id else None
        }


class RunComfyOrchestrator:
    """
    High-level orchestrator for CONJURE's flux mesh generation workflow.
    
    Coordinates between:
    - Development server management (for fast iteration)
    - RunComfy API client (machine lifecycle)
    - ComfyUI workflow client (workflow execution)
    - Progress tracking (real-time updates)
    """
    
    def __init__(self, workflow_path: str = "runcomfy/workflows/generate_flux_mesh.json"):
        self.workflow_path = Path(workflow_path)
        
        # Core components
        self.runcomfy_client = RunComfyAPIClient()
        self.comfyui_client = ComfyUIWorkflowClient()
        self.dev_server_manager = DevServerStateManager()
        
        # Job tracking
        self.active_jobs: Dict[str, FluxMeshJob] = {}
        self.machine_pool: Dict[str, MachineInfo] = {}
        
        # Configuration
        self.prefer_dev_server = True  # Prefer development server for faster iteration
        self.auto_shutdown = os.getenv("CONJURE_AUTO_SHUTDOWN", "false").lower() == "true"
        self.machine_reuse = os.getenv("CONJURE_MACHINE_REUSE", "true").lower() == "true"
        self.idle_timeout = int(os.getenv("CONJURE_IDLE_TIMEOUT", "600"))  # 10 minutes
        
        # Cost estimation (RunComfy pricing)
        self.cost_per_hour = {
            "medium": 0.50,
            "large": 1.00,
            "extra-large": 2.00,
            "2x-large": 4.00,
            "2xl-turbo": 6.00
        }
        
        print(f"🎭 CONJURE RunComfy Orchestrator initialized")
        print(f"   Workflow: {self.workflow_path}")
        print(f"   Dev server preference: {self.prefer_dev_server}")
        print(f"   Auto shutdown: {self.auto_shutdown}")
        print(f"   Machine reuse: {self.machine_reuse}")
    
    def load_workflow(self) -> Dict[str, Any]:
        """Load the generate_flux_mesh workflow"""
        try:
            if not self.workflow_path.exists():
                raise FileNotFoundError(f"Workflow file not found: {self.workflow_path}")
                
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            
            print(f"📄 Loaded flux mesh workflow with {len(workflow)} nodes")
            return workflow
            
        except Exception as e:
            print(f"❌ Failed to load workflow: {e}")
            raise
    
    def prepare_workflow_inputs(self, workflow: Dict[str, Any], use_conjure_data: bool = True) -> Dict[str, Any]:
        """
        Prepare workflow with CONJURE data inputs and outputs.
        
        Args:
            workflow: Base workflow JSON
            use_conjure_data: If True, read from CONJURE data files, otherwise use existing values
            
        Returns:
            Modified workflow with inputs injected and outputs configured
        """
        # Create a copy to avoid modifying the original
        prepared_workflow = json.loads(json.dumps(workflow))
        
        if use_conjure_data:
            # Read prompt from userPrompt.txt
            user_prompt_path = Path("data/generated_text/userPrompt.txt")
            if user_prompt_path.exists():
                try:
                    with open(user_prompt_path, 'r', encoding='utf-8') as f:
                        prompt = f.read().strip()
                    
                    # Update text prompts (node 34 - POSITIVECLIP)
                    if "34" in prepared_workflow:
                        prepared_workflow["34"]["inputs"]["clip_l"] = prompt
                        prepared_workflow["34"]["inputs"]["t5xxl"] = prompt
                    
                    print(f"✅ Loaded prompt from userPrompt.txt: {prompt[:100]}...")
                    
                except Exception as e:
                    print(f"⚠️ Failed to read userPrompt.txt: {e}")
                    print("   Using default prompt from workflow")
            else:
                print(f"⚠️ userPrompt.txt not found: {user_prompt_path}")
                print("   Using default prompt from workflow")
            
            # Verify input image exists (render.png)
            input_image_path = Path("data/generated_images/gestureCamera/render.png")
            if input_image_path.exists():
                # Update input image (node 16 - INPUTIMAGE) - already set to "render.png" in workflow
                print(f"✅ Input image found: {input_image_path}")
            else:
                print(f"⚠️ Input image not found: {input_image_path}")
                print("   Workflow will use placeholder image")
        
        # Configure output paths (already set in workflow JSON):
        # - Node 24 (EXPORT IMAGE): "flux" -> saves as flux.png
        # - Node 33 (EXPORTGLB): "partpacker_results/partpacker_result_0" -> saves as partpacker_result_0.glb
        
        print(f"✅ Workflow prepared with CONJURE data management")
        print(f"   Input image: render.png (from gestureCamera/)")
        print(f"   Input prompt: from userPrompt.txt")
        print(f"   Output image: flux.png")
        print(f"   Output mesh: partpacker_results/partpacker_result_0.glb")
        
        return prepared_workflow
    
    def estimate_cost(self, machine_type: str, estimated_duration_seconds: int = 300) -> float:
        """
        Estimate cost for flux mesh generation.
        
        Args:
            machine_type: Type of machine (medium, large, etc.)
            estimated_duration_seconds: Estimated execution time
            
        Returns:
            Estimated cost in USD
        """
        hourly_rate = self.cost_per_hour.get(machine_type, 1.0)
        hours = estimated_duration_seconds / 3600
        cost = hourly_rate * hours
        return round(cost, 4)
    
    async def get_or_create_machine(self) -> Union[DevServerState, MachineInfo]:
        """
        Get a ComfyUI server for workflow execution.
        
        Priority:
        1. Use existing development server if available and healthy
        2. Reuse pooled machine if available
        3. Launch new machine via RunComfy API
        
        Returns:
            Server information (DevServerState or MachineInfo)
        """
        print(f"🏭 Getting ComfyUI server for flux mesh generation...")
        
        # 1. Check for development server first (fastest option)
        if self.prefer_dev_server:
            dev_server = self.dev_server_manager.load_server_state()
            if dev_server and dev_server.status == "running":
                # Verify server health
                if await self.dev_server_manager.check_server_health(dev_server):
                    print(f"🚀 Using development server: {dev_server.server_id}")
                    return dev_server
                else:
                    print(f"⚠️ Development server unhealthy, falling back to RunComfy API")
        
        # 2. Check for pooled machines (if machine reuse enabled)
        if self.machine_reuse:
            for server_id, machine in self.machine_pool.items():
                if machine.current_status == MachineStatus.READY.value:
                    print(f"♻️ Reusing pooled machine: {server_id}")
                    return machine
        
        # 3. Launch new machine via RunComfy API
        print(f"🚀 Launching new RunComfy machine...")
        machine_info = await self.runcomfy_client.get_or_create_ready_machine("generate_flux_mesh")
        
        # Add to machine pool for potential reuse
        self.machine_pool[machine_info.server_id] = machine_info
        
        print(f"✅ New machine ready: {machine_info.server_id}")
        print(f"   URL: {machine_info.base_url}")
        print(f"   Type: {machine_info.server_type}")
        
        return machine_info
    
    async def create_job(self, job_name: str = "flux_mesh_generation") -> FluxMeshJob:
        """
        Create a new flux mesh generation job using CONJURE data.
        
        Args:
            job_name: Name identifier for the job
            
        Returns:
            Created job with initial status
        """
        job_id = str(uuid.uuid4())
        
        # Read prompt from userPrompt.txt for job creation
        prompt = "Default flux mesh generation"
        user_prompt_path = Path("data/generated_text/userPrompt.txt")
        if user_prompt_path.exists():
            try:
                with open(user_prompt_path, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
            except Exception as e:
                print(f"⚠️ Failed to read userPrompt.txt: {e}")
        
        job = FluxMeshJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            prompt=prompt,
            input_image_path="data/generated_images/gestureCamera/render.png",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.active_jobs[job_id] = job
        
        print(f"📝 Created CONJURE job {job_id}: {job_name}")
        print(f"   Prompt: {prompt[:100]}...")
        print(f"   Input image: render.png")
        return job
    
    async def execute_job(self, job: FluxMeshJob) -> FluxMeshJob:
        """
        Execute a complete flux mesh generation job.
        
        Args:
            job: Job to execute
            
        Returns:
            Updated job with results or error information
        """
        print(f"\n🚀 Executing flux mesh job: {job.job_id}")
        print(f"   Prompt: {job.prompt[:100]}...")
        
        try:
            # Update job status
            job.status = JobStatus.STARTING
            job.started_at = datetime.now(timezone.utc).isoformat()
            
            # 1. Get or create machine
            server_info = await self.get_or_create_machine()
            
            if isinstance(server_info, DevServerState):
                job.server_id = server_info.server_id
                job.comfyui_url = server_info.base_url
                machine_type = server_info.server_type
            else:  # MachineInfo
                job.server_id = server_info.server_id
                job.comfyui_url = server_info.base_url
                machine_type = server_info.server_type
            
            # Estimate cost
            job.machine_cost_estimate = self.estimate_cost(machine_type)
            
            # 2. Load and prepare workflow with CONJURE data
            workflow = self.load_workflow()
            prepared_workflow = self.prepare_workflow_inputs(workflow, use_conjure_data=True)
            
            # 3. Execute workflow with progress tracking
            job.status = JobStatus.RUNNING
            print(f"🎯 Starting workflow execution...")
            
            execution_result = await self.comfyui_client.execute_workflow(
                comfyui_url=job.comfyui_url,
                workflow=prepared_workflow,
                workflow_name="generate_flux_mesh"
            )
            
            # Store execution details
            job.prompt_id = execution_result.prompt_id
            job.client_id = execution_result.client_id
            
            # 4. Handle results
            if execution_result.status == ExecutionStatus.COMPLETED.value:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                
                # Extract result URLs from outputs
                job.result_files = execution_result.outputs
                
                print(f"✅ Workflow completed successfully!")
                print(f"   Available outputs: {list(execution_result.outputs.keys()) if execution_result.outputs else 'None'}")
                
                # Download results to local CONJURE data folders
                print(f"💾 Downloading results to local data folders...")
                downloaded_files = await self.comfyui_client.download_results(job.comfyui_url, execution_result)
                
                # Update job with local file paths
                if "Generated Image" in downloaded_files:
                    job.generated_image_url = downloaded_files["Generated Image"]
                
                if "Generated Mesh" in downloaded_files:
                    job.generated_mesh_url = downloaded_files["Generated Mesh"]
                
                print(f"✅ Job completed with local files!")
                if job.generated_image_url:
                    print(f"   📸 Image: {job.generated_image_url}")
                if job.generated_mesh_url:
                    print(f"   🗿 Mesh: {job.generated_mesh_url}")
                
            else:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.error_message = execution_result.error_message
                
                print(f"❌ Job failed: {job.error_message}")
            
            # Calculate actual cost based on execution time
            if job.started_at and job.completed_at:
                start_time = datetime.fromisoformat(job.started_at.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(job.completed_at.replace('Z', '+00:00'))
                duration_seconds = (end_time - start_time).total_seconds()
                job.actual_machine_cost = self.estimate_cost(machine_type, int(duration_seconds))
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.error_message = str(e)
            print(f"❌ Job execution failed: {e}")
        
        print(f"🏁 Job {job.job_id} finished with status: {job.status.value}")
        return job
    
    async def execute_flux_mesh_generation(self, job_name: str = "conjure_flux_mesh") -> FluxMeshJob:
        """
        High-level method to generate a flux mesh using CONJURE data.
        
        Args:
            job_name: Name identifier for the job
            
        Returns:
            Completed job with results or error information
        """
        # Create and execute job using CONJURE data files
        job = await self.create_job(job_name)
        job = await self.execute_job(job)
        
        return job
    
    def get_job_status(self, job_id: str) -> Optional[FluxMeshJob]:
        """Get current status of a job"""
        return self.active_jobs.get(job_id)
    
    def get_all_jobs(self) -> List[FluxMeshJob]:
        """Get all jobs"""
        return list(self.active_jobs.values())
    
    def get_active_jobs(self) -> List[FluxMeshJob]:
        """Get currently running jobs"""
        return [job for job in self.active_jobs.values() 
                if job.status in [JobStatus.PENDING, JobStatus.STARTING, JobStatus.RUNNING]]
    
    async def cleanup_job(self, job_id: str) -> bool:
        """Clean up a completed job"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            
            # Clean up progress tracking
            if job.prompt_id:
                progress_tracker.cleanup_completed_workflows(max_age_hours=1)
            
            # Remove from active jobs
            del self.active_jobs[job_id]
            
            print(f"🧹 Cleaned up job: {job_id}")
            return True
        
        return False
    
    async def shutdown_idle_machines(self):
        """Shutdown machines that have been idle for too long"""
        if not self.auto_shutdown:
            return
        
        current_time = time.time()
        to_remove = []
        
        for server_id, machine in self.machine_pool.items():
            # Check if machine is idle
            if machine.current_status == MachineStatus.READY.value:
                idle_time = current_time - machine.last_used_time if hasattr(machine, 'last_used_time') else 0
                
                if idle_time > self.idle_timeout:
                    print(f"🛑 Shutting down idle machine: {server_id}")
                    try:
                        await self.runcomfy_client.stop_machine(server_id)
                        to_remove.append(server_id)
                    except Exception as e:
                        print(f"⚠️ Failed to shutdown machine {server_id}: {e}")
        
        # Remove from pool
        for server_id in to_remove:
            del self.machine_pool[server_id]
    
    async def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for all jobs"""
        total_estimated = sum(job.machine_cost_estimate or 0 for job in self.active_jobs.values())
        total_actual = sum(job.actual_machine_cost or 0 for job in self.active_jobs.values())
        
        return {
            "total_jobs": len(self.active_jobs),
            "active_jobs": len(self.get_active_jobs()),
            "total_estimated_cost": round(total_estimated, 4),
            "total_actual_cost": round(total_actual, 4),
            "active_machines": len(self.machine_pool),
            "cost_per_hour_rates": self.cost_per_hour
        }
