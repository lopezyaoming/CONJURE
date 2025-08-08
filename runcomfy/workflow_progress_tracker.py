"""
Workflow Progress Tracker for RunComfy ComfyUI workflows.

This module provides detailed progress tracking for the generate_flux_mesh workflow,
mapping individual node executions to logical workflow stages and overall progress.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class WorkflowStage:
    """Represents a logical stage in the workflow"""
    stage_id: str
    name: str
    description: str
    nodes: List[str]
    weight: float  # Relative weight for progress calculation
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class NodeProgress:
    """Progress information for a specific node"""
    node_id: str
    node_title: str
    class_type: str
    status: str = "pending"  # pending, executing, executed, failed
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    progress_value: Optional[int] = None
    progress_max: Optional[int] = None


@dataclass
class WorkflowProgress:
    """Complete workflow progress information"""
    workflow_name: str
    prompt_id: str
    client_id: str
    overall_progress: float = 0.0
    current_stage: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed, cancelled
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    stages: List[WorkflowStage] = None
    nodes: Dict[str, NodeProgress] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.stages is None:
            self.stages = []
        if self.nodes is None:
            self.nodes = {}


class FluxMeshProgressTracker:
    """
    Progress tracker specifically designed for the generate_flux_mesh workflow.
    
    Maps ComfyUI node executions to logical workflow stages and provides
    real-time progress updates.
    """
    
    def __init__(self):
        self.workflow_stages = self._define_workflow_stages()
        self.node_to_stage = self._build_node_stage_mapping()
        self.active_workflows: Dict[str, WorkflowProgress] = {}
        
    def _define_workflow_stages(self) -> List[WorkflowStage]:
        """Define the logical stages of the flux mesh generation workflow"""
        return [
            WorkflowStage(
                stage_id="initialization",
                name="🚀 Initialization",
                description="Loading models and preparing environment",
                nodes=["4", "8", "10", "13", "30", "36"],  # CLIP, VAE, UNET, ControlNet, PartPacker, RemBG loaders
                weight=0.15
            ),
            WorkflowStage(
                stage_id="input_processing", 
                name="📥 Input Processing",
                description="Processing input image and generating depth map",
                nodes=["16", "25"],  # LoadImage, DepthAnything
                weight=0.10
            ),
            WorkflowStage(
                stage_id="text_encoding",
                name="📝 Text Encoding", 
                description="Encoding text prompts and conditioning",
                nodes=["19", "34"],  # Negative and Positive CLIP encoding
                weight=0.05
            ),
            WorkflowStage(
                stage_id="controlnet_setup",
                name="🎛️ ControlNet Setup",
                description="Applying depth-based control guidance",
                nodes=["14"],  # ApplyFluxControlNet
                weight=0.05
            ),
            WorkflowStage(
                stage_id="latent_generation",
                name="🎨 Latent Generation",
                description="Creating empty latent space",
                nodes=["6"],  # EmptyLatentImage
                weight=0.05
            ),
            WorkflowStage(
                stage_id="flux_sampling",
                name="⚡ FLUX Sampling",
                description="Generating image with FLUX diffusion model",
                nodes=["3"],  # XlabsSampler - Most computationally intensive
                weight=0.30
            ),
            WorkflowStage(
                stage_id="image_decoding",
                name="🖼️ Image Decoding",
                description="Decoding latent to image",
                nodes=["7"],  # VAEDecode
                weight=0.05
            ),
            WorkflowStage(
                stage_id="background_removal",
                name="✂️ Background Removal",
                description="Removing background for clean mesh generation",
                nodes=["37"],  # ImageRemoveBackground
                weight=0.05
            ),
            WorkflowStage(
                stage_id="mesh_generation",
                name="🗿 3D Mesh Generation",
                description="Converting image to 3D mesh with PartPacker",
                nodes=["32"],  # PartPacker_Sampler - Second most intensive
                weight=0.15
            ),
            WorkflowStage(
                stage_id="export",
                name="💾 Export Results", 
                description="Saving final image and mesh files",
                nodes=["24", "33"],  # SaveImage, SaveGLB
                weight=0.05
            )
        ]
    
    def _build_node_stage_mapping(self) -> Dict[str, str]:
        """Build mapping from node IDs to stage IDs"""
        mapping = {}
        for stage in self.workflow_stages:
            for node_id in stage.nodes:
                mapping[node_id] = stage.stage_id
        return mapping
    
    def start_workflow_tracking(self, workflow_name: str, prompt_id: str, client_id: str) -> WorkflowProgress:
        """Start tracking a new workflow execution"""
        progress = WorkflowProgress(
            workflow_name=workflow_name,
            prompt_id=prompt_id,
            client_id=client_id,
            start_time=datetime.now(timezone.utc).isoformat(),
            status="running",
            stages=[WorkflowStage(**asdict(stage)) for stage in self.workflow_stages],
            nodes={}
        )
        
        self.active_workflows[prompt_id] = progress
        return progress
    
    def update_node_progress(self, prompt_id: str, node_id: str, event_type: str, 
                           node_data: Optional[Dict] = None, progress_data: Optional[Dict] = None) -> Optional[WorkflowProgress]:
        """Update progress based on node execution events"""
        if prompt_id not in self.active_workflows:
            return None
            
        workflow = self.active_workflows[prompt_id]
        
        # Initialize node progress if not exists
        if node_id not in workflow.nodes:
            workflow.nodes[node_id] = NodeProgress(
                node_id=node_id,
                node_title=f"Node {node_id}",
                class_type="Unknown"
            )
        
        node_progress = workflow.nodes[node_id]
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Update node status based on event type
        if event_type == "executing":
            node_progress.status = "executing"
            node_progress.start_time = current_time
            
        elif event_type == "executed":
            node_progress.status = "executed" 
            node_progress.end_time = current_time
            
        elif event_type == "progress":
            if progress_data:
                node_progress.progress_value = progress_data.get("value", 0)
                node_progress.progress_max = progress_data.get("max", 100)
        
        # Update stage progress
        self._update_stage_progress(workflow, node_id, event_type)
        
        # Update overall progress
        self._calculate_overall_progress(workflow)
        
        return workflow
    
    def _update_stage_progress(self, workflow: WorkflowProgress, node_id: str, event_type: str):
        """Update stage progress based on node events"""
        stage_id = self.node_to_stage.get(node_id)
        if not stage_id:
            return
            
        # Find the stage
        stage = None
        for s in workflow.stages:
            if s.stage_id == stage_id:
                stage = s
                break
                
        if not stage:
            return
            
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Check if this is the first node in the stage to start
        if event_type == "executing" and stage.status == "pending":
            stage.status = "running"
            stage.start_time = current_time
            workflow.current_stage = stage.name
            
        # Check if all nodes in the stage are completed
        elif event_type == "executed":
            all_completed = True
            for stage_node_id in stage.nodes:
                node_status = workflow.nodes.get(stage_node_id, {}).status if stage_node_id in workflow.nodes else "pending"
                if node_status not in ["executed"]:
                    all_completed = False
                    break
                    
            if all_completed:
                stage.status = "completed"
                stage.end_time = current_time
                
                # Move to next stage
                self._advance_to_next_stage(workflow)
    
    def _advance_to_next_stage(self, workflow: WorkflowProgress):
        """Advance to the next pending stage"""
        for stage in workflow.stages:
            if stage.status == "pending":
                workflow.current_stage = f"📋 Preparing {stage.name}"
                break
        else:
            # All stages completed
            workflow.current_stage = "✅ Completed"
            workflow.status = "completed"
            workflow.end_time = datetime.now(timezone.utc).isoformat()
    
    def _calculate_overall_progress(self, workflow: WorkflowProgress):
        """Calculate overall workflow progress as percentage"""
        total_weight = sum(stage.weight for stage in workflow.stages)
        completed_weight = 0.0
        
        for stage in workflow.stages:
            if stage.status == "completed":
                completed_weight += stage.weight
            elif stage.status == "running":
                # Calculate partial stage progress
                completed_nodes = 0
                total_nodes = len(stage.nodes)
                
                for node_id in stage.nodes:
                    if node_id in workflow.nodes and workflow.nodes[node_id].status == "executed":
                        completed_nodes += 1
                        
                stage_progress = completed_nodes / total_nodes if total_nodes > 0 else 0
                completed_weight += stage.weight * stage_progress
        
        workflow.overall_progress = min((completed_weight / total_weight) * 100, 100.0)
    
    def handle_workflow_completion(self, prompt_id: str, success: bool = True, error_message: Optional[str] = None):
        """Handle workflow completion or failure"""
        if prompt_id not in self.active_workflows:
            return
            
        workflow = self.active_workflows[prompt_id]
        workflow.end_time = datetime.now(timezone.utc).isoformat()
        
        if success:
            workflow.status = "completed"
            workflow.overall_progress = 100.0
            workflow.current_stage = "✅ Completed Successfully"
            
            # Mark all stages as completed
            for stage in workflow.stages:
                if stage.status != "completed":
                    stage.status = "completed"
                    stage.end_time = workflow.end_time
        else:
            workflow.status = "failed"
            workflow.error_message = error_message
            workflow.current_stage = "❌ Failed"
    
    def get_workflow_progress(self, prompt_id: str) -> Optional[WorkflowProgress]:
        """Get current workflow progress"""
        return self.active_workflows.get(prompt_id)
    
    def get_workflow_summary(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of workflow progress suitable for UI display"""
        workflow = self.get_workflow_progress(prompt_id)
        if not workflow:
            return None
            
        return {
            "prompt_id": workflow.prompt_id,
            "workflow_name": workflow.workflow_name,
            "overall_progress": round(workflow.overall_progress, 1),
            "status": workflow.status,
            "current_stage": workflow.current_stage,
            "start_time": workflow.start_time,
            "end_time": workflow.end_time,
            "stages": [
                {
                    "name": stage.name,
                    "description": stage.description,
                    "status": stage.status,
                    "nodes_total": len(stage.nodes),
                    "nodes_completed": len([n for n in stage.nodes if n in workflow.nodes and workflow.nodes[n].status == "executed"])
                }
                for stage in workflow.stages
            ],
            "error_message": workflow.error_message
        }
    
    def cleanup_completed_workflows(self, max_age_hours: int = 24):
        """Clean up old completed workflows"""
        current_time = datetime.now(timezone.utc)
        to_remove = []
        
        for prompt_id, workflow in self.active_workflows.items():
            if workflow.status in ["completed", "failed"] and workflow.end_time:
                end_time = datetime.fromisoformat(workflow.end_time.replace('Z', '+00:00'))
                age_hours = (current_time - end_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    to_remove.append(prompt_id)
        
        for prompt_id in to_remove:
            del self.active_workflows[prompt_id]


# Global progress tracker instance
progress_tracker = FluxMeshProgressTracker()
