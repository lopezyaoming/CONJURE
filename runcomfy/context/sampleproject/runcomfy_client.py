"""
RunComfy API Client for machine lifecycle management
Handles launching, monitoring, and stopping RunComfy machines
"""
import asyncio
import os
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import httpx
from loguru import logger
from fastapi import HTTPException


class MachineStatus(Enum):
    STARTING = "Starting"
    READY = "Ready"
    STOPPING = "Stopping"
    DELETING = "Deleting"
    ERROR = "Error"


class ServerType(Enum):
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra-large"
    LARGE_2X = "2x-large"
    TURBO_2XL = "2xl-turbo"


@dataclass
class MachineInfo:
    server_id: str
    user_id: str
    server_type: str
    current_status: str
    estimated_duration: int
    main_service_url: Optional[str] = None
    service_ready_at: Optional[str] = None
    estimated_stopping_at: Optional[str] = None


@dataclass
class WorkflowInfo:
    workflow_id: str
    name: str
    version_id: str
    created_at: str
    updated_at: str


class RunComfyAPIClient:
    """Client for RunComfy management API"""
    
    def __init__(self):
        # Configuration from environment
        self.base_url = os.getenv("RUNCOMFY_API_BASE_URL", "https://api.runcomfy.net")
        self.user_id = os.getenv("RUNCOMFY_USER_ID", "92b6028c-6a08-4571-a998-0f2d66493db1")
        self.api_token = os.getenv("RUNCOMFY_API_TOKEN", "f706b389-2346-4a03-a0ec-7aff43f8ddfd")
        
        # Defaults
        self.default_server_type = os.getenv("RUNCOMFY_DEFAULT_SERVER_TYPE", "medium")
        self.default_duration = int(os.getenv("RUNCOMFY_DEFAULT_DURATION", "3600"))  # 1 hour
        self.max_retries = int(os.getenv("RUNCOMFY_MAX_RETRIES", "3"))
        self.poll_interval = int(os.getenv("RUNCOMFY_POLL_INTERVAL", "5"))
        self.machine_timeout = int(os.getenv("RUNCOMFY_MACHINE_TIMEOUT", "600"))  # 10 minutes for cloud reliability
        
        # Validation
        if not self.api_token:
            logger.warning("⚠️ RUNCOMFY_API_TOKEN not set - RunComfy features will be unavailable")
        
        logger.info(f"🏗️ RunComfy API Client initialized")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   User ID: {self.user_id}")
        logger.info(f"   Default Server: {self.default_server_type}")
        logger.info(f"   Default Duration: {self.default_duration}s")
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers
    
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
                logger.debug(f"🌐 {method} {url} (attempt {attempt + 1}/{self.max_retries})")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json_data,
                        params=params
                    )
                
                logger.debug(f"📨 Response: {response.status_code}")
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"⏳ Rate limited, waiting {retry_after}s before retry")
                    await asyncio.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                logger.debug(f"✅ Request successful: {result}")
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"RunComfy API error: {e.response.text}"
                    )
            except httpx.RequestError as e:
                logger.error(f"❌ Request error: {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Failed to connect to RunComfy API: {str(e)}"
                    )
            
            # Exponential backoff
            wait_time = 2 ** attempt
            logger.info(f"⏳ Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
        
        raise HTTPException(status_code=503, detail="Max retries exceeded")
    
    async def list_workflows(self) -> List[WorkflowInfo]:
        """List all workflows for the user"""
        logger.info("📋 Listing user workflows...")
        
        endpoint = f"/prod/api/users/{self.user_id}/workflows"
        result = await self._make_request("GET", endpoint)
        
        workflows = []
        # result is a list directly, not a dict with "workflows"
        for workflow_data in result:
            workflows.append(WorkflowInfo(
                workflow_id=workflow_data["workflow_id"],
                name=workflow_data["workflow_name"],  # API uses "workflow_name"
                version_id=workflow_data["version_id"],
                created_at=workflow_data.get("created_at", ""),
                updated_at=workflow_data.get("updated_at", "")
            ))
        
        logger.info(f"📋 Found {len(workflows)} workflows")
        for wf in workflows:
            logger.info(f"   - {wf.name} (version: {wf.version_id})")
        
        return workflows
    
    async def find_workflow_version(self, workflow_name: str = "user2imgs") -> Optional[str]:
        """Find version_id for a specific workflow name"""
        logger.info(f"🔍 Looking for workflow: {workflow_name}")
        
        workflows = await self.list_workflows()
        
        for workflow in workflows:
            if workflow.name == workflow_name:
                logger.info(f"✅ Found workflow '{workflow_name}' with version_id: {workflow.version_id}")
                return workflow.version_id
        
        logger.warning(f"⚠️ Workflow '{workflow_name}' not found")
        return None
    
    async def launch_machine(
        self,
        version_id: str,
        server_type: Optional[str] = None,
        estimated_duration: Optional[int] = None
    ) -> str:
        """Launch a new machine with specified workflow"""
        server_type = server_type or self.default_server_type
        estimated_duration = estimated_duration or self.default_duration
        
        logger.info(f"🚀 Launching machine...")
        logger.info(f"   Workflow version: {version_id}")
        logger.info(f"   Server type: {server_type}")
        logger.info(f"   Duration: {estimated_duration}s")
        
        endpoint = f"/prod/api/users/{self.user_id}/servers"
        payload = {
            "workflow_version_id": version_id,  # API expects workflow_version_id
            "server_type": server_type,
            "estimated_duration": estimated_duration
        }
        
        result = await self._make_request("POST", endpoint, json_data=payload)
        server_id = result["server_id"]
        
        logger.info(f"🚀 Machine launch initiated - Server ID: {server_id}")
        return server_id
    
    async def get_machine_status(self, server_id: str) -> MachineInfo:
        """Get current status of a machine"""
        logger.debug(f"📊 Checking machine status: {server_id}")
        
        endpoint = f"/prod/api/users/{self.user_id}/servers/{server_id}"
        result = await self._make_request("GET", endpoint)
        
        machine_info = MachineInfo(
            server_id=result["server_id"],
            user_id=result["user_id"],
            server_type=result["server_type"],
            current_status=result["current_status"],
            estimated_duration=result["estimated_duration"],
            main_service_url=result.get("main_service_url"),
            service_ready_at=result.get("service_ready_at"),
            estimated_stopping_at=result.get("estimated_stopping_at")
        )
        
        logger.debug(f"📊 Machine {server_id}: {machine_info.current_status}")
        return machine_info
    
    async def wait_for_machine_ready(self, server_id: str, console_mode: bool = False) -> MachineInfo:
        """Poll machine status until it's ready or timeout"""
        logger.debug(f"⏳ Waiting for machine to be ready: {server_id}")
        start_time = time.time()
        last_status = None
        
        while True:
            machine_info = await self.get_machine_status(server_id)
            
            if machine_info.current_status == MachineStatus.READY.value:
                elapsed = time.time() - start_time
                if console_mode:
                    print(f"✅ Machine ready! ({elapsed:.1f}s)")
                else:
                    logger.info(f"✅ Machine ready! ({elapsed:.1f}s)")
                    logger.info(f"   ComfyUI URL: {machine_info.main_service_url}")
                return machine_info
            
            elif machine_info.current_status in [MachineStatus.DELETING.value, MachineStatus.ERROR.value]:
                error_msg = f"Machine failed with status: {machine_info.current_status}"
                if console_mode:
                    print(f"❌ {error_msg}")
                logger.error(f"❌ {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Machine failed to start: {machine_info.current_status}"
                )
            
            elapsed = time.time() - start_time
            if elapsed > self.machine_timeout:
                error_msg = f"Machine startup timeout ({self.machine_timeout}s)"
                if console_mode:
                    print(f"⏰ {error_msg}")
                logger.error(f"⏰ {error_msg}")
                raise HTTPException(
                    status_code=408,
                    detail=f"Machine startup timeout after {self.machine_timeout}s"
                )
            
            # Progress indicator (less verbose in console mode)
            if console_mode:
                # Show status changes and every 60 seconds in console
                if machine_info.current_status != last_status:
                    print(f"   Status: {machine_info.current_status}")
                    last_status = machine_info.current_status
                elif elapsed % 60 == 0:  # Every 60 seconds for console
                    print(f"   Still waiting... ({elapsed:.0f}s)")
            else:
                # Regular logging for backend
                if elapsed % 30 == 0:  # Every 30 seconds
                    logger.info(f"⏳ Still waiting... ({elapsed:.0f}s, status: {machine_info.current_status})")
            
            await asyncio.sleep(self.poll_interval)
    
    async def update_machine_duration(self, server_id: str, new_duration: int) -> MachineInfo:
        """Update the estimated running duration of a machine"""
        logger.info(f"⏱️ Updating machine duration: {server_id} -> {new_duration}s")
        
        endpoint = f"/prod/api/users/{self.user_id}/servers/{server_id}/update-estimated-duration"
        payload = {"update_estimated_duration": new_duration}
        
        result = await self._make_request("POST", endpoint, json_data=payload)
        
        machine_info = MachineInfo(
            server_id=result["server_id"],
            user_id=result["user_id"],
            server_type=result["server_type"],
            current_status=result["current_status"],
            estimated_duration=result["estimated_duration"],
            main_service_url=result.get("main_service_url"),
            service_ready_at=result.get("service_ready_at"),
            estimated_stopping_at=result.get("estimated_stopping_at")
        )
        
        logger.info(f"✅ Machine duration updated to {machine_info.estimated_duration}s")
        return machine_info
    
    async def stop_machine(self, server_id: str) -> MachineInfo:
        """Stop a running machine"""
        logger.info(f"🛑 Stopping machine: {server_id}")
        
        endpoint = f"/prod/api/users/{self.user_id}/servers/{server_id}"
        result = await self._make_request("DELETE", endpoint)
        
        machine_info = MachineInfo(
            server_id=result["server_id"],
            user_id=result["user_id"],
            server_type=result["server_type"],
            current_status=result["current_status"],
            estimated_duration=result["estimated_duration"],
            main_service_url=result.get("main_service_url"),
            service_ready_at=result.get("service_ready_at"),
            estimated_stopping_at=result.get("estimated_stopping_at")
        )
        
        logger.info(f"🛑 Machine stop initiated - Status: {machine_info.current_status}")
        return machine_info
    
    async def list_running_machines(self) -> List[MachineInfo]:
        """List all running machines for the user"""
        logger.info("📋 Listing running machines...")
        
        endpoint = f"/prod/api/users/{self.user_id}/servers"
        result = await self._make_request("GET", endpoint)
        
        machines = []
        # Handle both list and dict responses from API
        if isinstance(result, list):
            machine_list = result
        else:
            machine_list = result.get("servers", [])
            
        for machine_data in machine_list:
            machines.append(MachineInfo(
                server_id=machine_data["server_id"],
                user_id=machine_data["user_id"],
                server_type=machine_data["server_type"],
                current_status=machine_data["current_status"],
                estimated_duration=machine_data["estimated_duration"],
                main_service_url=machine_data.get("main_service_url"),
                service_ready_at=machine_data.get("service_ready_at"),
                estimated_stopping_at=machine_data.get("estimated_stopping_at")
            ))
        
        logger.info(f"📋 Found {len(machines)} running machines")
        for machine in machines:
            logger.info(f"   - {machine.server_id}: {machine.current_status} ({machine.server_type})")
        
        return machines
    
    async def get_or_create_ready_machine(self, workflow_name: str = "user2imgs") -> MachineInfo:
        """Get an existing ready machine or create a new one"""
        logger.info(f"🔍 Looking for ready machine with workflow: {workflow_name}")
        
        # Check for existing ready machines
        machines = await self.list_running_machines()
        ready_machines = [m for m in machines if m.current_status == MachineStatus.READY.value]
        
        if ready_machines:
            machine = ready_machines[0]
            logger.info(f"♻️ Reusing existing ready machine: {machine.server_id}")
            return machine
        
        # Need to launch a new machine
        logger.info("🚀 No ready machines found, launching new one...")
        
        # Get workflow version
        version_id = await self.find_workflow_version(workflow_name)
        if not version_id:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{workflow_name}' not found in RunComfy account"
            )
        
        # Launch and wait for ready
        server_id = await self.launch_machine(version_id)
        machine_info = await self.wait_for_machine_ready(server_id)
        
        return machine_info
