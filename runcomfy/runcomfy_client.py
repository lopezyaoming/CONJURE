"""
RunComfy API Client for machine lifecycle management
Handles launching, monitoring, and stopping RunComfy machines

Adapted from sample project with CONJURE-specific enhancements
"""
import asyncio
import os
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import httpx
from pathlib import Path


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
        # Configuration from environment (set by dev_server_startup.py)
        self.base_url = os.getenv("RUNCOMFY_API_BASE_URL", "https://api.runcomfy.net")
        self.user_id = os.getenv("RUNCOMFY_USER_ID", "")
        self.api_token = os.getenv("RUNCOMFY_API_TOKEN", "")
        
        # Defaults
        self.default_server_type = os.getenv("RUNCOMFY_DEFAULT_SERVER_TYPE", "medium")
        self.default_duration = int(os.getenv("RUNCOMFY_DEFAULT_DURATION", "3600"))  # 1 hour
        self.max_retries = int(os.getenv("RUNCOMFY_MAX_RETRIES", "3"))
        self.poll_interval = int(os.getenv("RUNCOMFY_POLL_INTERVAL", "5"))
        self.machine_timeout = int(os.getenv("RUNCOMFY_MACHINE_TIMEOUT", "1800"))  # 30 minutes
        
        # Validation
        if not self.api_token:
            print("⚠️ RUNCOMFY_API_TOKEN not set - RunComfy features will be unavailable")
        if not self.user_id:
            print("⚠️ RUNCOMFY_USER_ID not set - RunComfy features will be unavailable")
        
        print(f"🏗️ RunComfy API Client initialized")
        print(f"   Base URL: {self.base_url}")
        print(f"   User ID: {self.user_id}")
        print(f"   Default Server: {self.default_server_type}")
        print(f"   Default Duration: {self.default_duration}s")
    
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
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json_data,
                        params=params
                    )
                    
                    if response.status_code == 200:
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
    
    async def launch_machine(
        self, 
        server_type: str = None,
        estimated_duration: int = None,
        workflow_version_id: str = None
    ) -> MachineInfo:
        """
        Launch a new RunComfy machine
        
        Args:
            server_type: Type of server to launch
            estimated_duration: Estimated duration in seconds
            workflow_version_id: Workflow version to use
            
        Returns:
            MachineInfo object with server details
        """
        server_type = server_type or self.default_server_type
        estimated_duration = estimated_duration or self.default_duration
        
        if not workflow_version_id:
            raise ValueError("workflow_version_id is required for launching machines")
        
        payload = {
            "workflow_version_id": workflow_version_id,  # API expects workflow_version_id
            "server_type": server_type,
            "estimated_duration": estimated_duration
        }
        
        print(f"🚀 Launching machine: {server_type} for {estimated_duration}s")
        print(f"   Workflow version: {workflow_version_id}")
        
        try:
            response = await self._make_request(
                method="POST",
                endpoint=f"/prod/api/users/{self.user_id}/servers",  # Correct endpoint
                json_data=payload
            )
            
            print(f"🔍 DEBUG: API Response: {response}")
            
            machine_info = MachineInfo(
                server_id=response["server_id"],  # API returns server_id
                user_id=response["user_id"],
                server_type=response["server_type"],
                current_status=response["current_status"],
                estimated_duration=response["estimated_duration"]
            )
            
            print(f"✅ Machine launch initiated: {machine_info.server_id}")
            return machine_info
            
        except Exception as e:
            print(f"❌ Failed to launch machine: {e}")
            raise
    
    async def get_machine_status(self, server_id: str) -> MachineInfo:
        """Get current status of a machine"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/prod/api/users/{self.user_id}/servers/{server_id}"  # Correct endpoint
            )
            
            return MachineInfo(
                server_id=response["server_id"],
                user_id=response["user_id"],
                server_type=response["server_type"],
                current_status=response["current_status"],
                estimated_duration=response["estimated_duration"],
                main_service_url=response.get("main_service_url"),
                service_ready_at=response.get("service_ready_at"),
                estimated_stopping_at=response.get("estimated_stopping_at")
            )
            
        except Exception as e:
            print(f"❌ Failed to get machine status: {e}")
            raise
    
    async def wait_for_machine_ready(
        self, 
        server_id: str, 
        timeout: int = None
    ) -> Optional[MachineInfo]:
        """
        Wait for machine to be ready
        
        Args:
            server_id: Server ID to wait for
            timeout: Timeout in seconds
            
        Returns:
            MachineInfo when ready, None if timeout
        """
        timeout = timeout or self.machine_timeout
        start_time = time.time()
        
        print(f"⏳ Waiting for machine {server_id} to be ready (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            try:
                machine_info = await self.get_machine_status(server_id)
                
                print(f"   Status: {machine_info.current_status}")
                
                if machine_info.current_status == MachineStatus.READY.value:
                    print(f"✅ Machine {server_id} is ready!")
                    return machine_info
                elif machine_info.current_status == MachineStatus.ERROR.value:
                    print(f"❌ Machine {server_id} failed to start")
                    return None
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"⚠️ Error checking machine status: {e}")
                await asyncio.sleep(self.poll_interval)
        
        print(f"⏰ Timeout waiting for machine {server_id} to be ready")
        return None
    
    async def stop_machine(self, server_id: str) -> bool:
        """
        Stop a running machine
        
        Args:
            server_id: Server ID to stop
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"🛑 Stopping machine: {server_id}")
            
            response = await self._make_request(
                method="DELETE",  # DELETE method for stopping
                endpoint=f"/prod/api/users/{self.user_id}/servers/{server_id}"  # Correct endpoint
            )
            
            print(f"✅ Machine stop initiated: {server_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to stop machine: {e}")
            return False
    
    async def list_machines(self) -> List[MachineInfo]:
        """List all machines for the user"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/prod/api/users/{self.user_id}/servers"  # Correct endpoint
            )
            
            machines = []
            # Response is a list directly
            for machine_data in response:
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
            
            return machines
            
        except Exception as e:
            print(f"❌ Failed to list machines: {e}")
            return []
    
    async def get_workflows(self) -> List[WorkflowInfo]:
        """Get available workflows for the user"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/prod/api/users/{self.user_id}/workflows"  # Correct endpoint
            )
            
            workflows = []
            # Response is a list directly
            for workflow_data in response:
                workflows.append(WorkflowInfo(
                    workflow_id=workflow_data["workflow_id"],
                    name=workflow_data["workflow_name"],  # API uses workflow_name
                    version_id=workflow_data["version_id"],
                    created_at=workflow_data.get("created_at", ""),
                    updated_at=workflow_data.get("updated_at", "")
                ))
            
            return workflows
            
        except Exception as e:
            print(f"❌ Failed to get workflows: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if RunComfy client is properly configured"""
        return bool(self.api_token and self.user_id)
