"""
Generation Services Interface

This module provides abstract interfaces for different generation backends:
- LocalGenerationService (HuggingFace mode): Uses HuggingFace models (FLUX, PartPacker)
- LocalComfyUIService: Uses local ComfyUI server on localhost:8188
- CloudGenerationService: Uses runComfy cloud services (to be implemented)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import os
import asyncio
from gradio_client import Client, handle_file
import shutil

class GenerationService(ABC):
    """Abstract base class for generation services."""
    
    @abstractmethod
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using FLUX.1-dev."""
        pass
    
    @abstractmethod
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image using FLUX.1-Depth-dev."""
        pass
    
    @abstractmethod
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model from 2D image."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this generation service is available."""
        pass

class LocalGenerationService(GenerationService):
    """HuggingFace generation service using HuggingFace models (formerly called LocalGenerationService)."""
    
    def __init__(self):
        self.hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
        if not self.hf_token:
            print("⚠️  WARNING: HUGGINGFACE_HUB_ACCESS_TOKEN not set - using anonymous quota")
    
    def is_available(self) -> bool:
        """Check if HuggingFace token is available."""
        return self.hf_token is not None
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using FLUX.1-dev."""
        print(f"🎨 [HUGGINGFACE] Generating FLUX image: {prompt[:100]}...")
        
        # Set defaults
        width = kwargs.get('width', 1024)
        height = kwargs.get('height', 1024)
        randomize_seed = kwargs.get('randomize_seed', True)
        num_inference_steps = kwargs.get('num_inference_steps', 28)
        
        # Initialize client
        client = Client("black-forest-labs/FLUX.1-dev", hf_token=self.hf_token)
        
        result = client.predict(
            prompt=prompt,
            seed=seed,
            randomize_seed=randomize_seed,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            api_name="/infer"
        )
        
        # Process result
        output_dir = Path("data/generated_images/flux_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if isinstance(result, tuple) and len(result) >= 1:
            image_data = result[0]
            seed_used = result[1] if len(result) > 1 else seed
        else:
            image_data = result
            seed_used = seed
        
        # Extract and save image
        image_path = None
        if hasattr(image_data, 'path'):
            image_path = image_data.path
        elif isinstance(image_data, dict) and 'path' in image_data:
            image_path = image_data['path']
        elif isinstance(image_data, str):
            image_path = image_data
        
        if image_path and Path(image_path).exists():
            dest_path = output_dir / f"flux_result_{seed_used}.png"
            shutil.copy(image_path, dest_path)
            return {
                "success": True,
                "image_path": str(dest_path),
                "seed_used": seed_used
            }
        else:
            raise Exception("Could not extract image path from FLUX result")
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image using FLUX.1-Depth-dev."""
        print(f"🎨 [HUGGINGFACE] Generating FLUX Depth image: {prompt[:100]}...")
        
        # Verify control image exists
        if not Path(control_image_path).exists():
            raise FileNotFoundError(f"Control image not found: {control_image_path}")
        
        # Set defaults
        width = kwargs.get('width', 1024)
        height = kwargs.get('height', 1024)
        randomize_seed = kwargs.get('randomize_seed', False)
        guidance_scale = kwargs.get('guidance_scale', 10)
        num_inference_steps = kwargs.get('num_inference_steps', 28)
        
        # Initialize client
        client = Client("black-forest-labs/FLUX.1-Depth-dev", hf_token=self.hf_token)
        
        result = client.predict(
            control_image=handle_file(control_image_path),
            prompt=prompt,
            seed=seed,
            randomize_seed=randomize_seed,
            width=width,
            height=height,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            api_name="/infer"
        )
        
        # Process result - FLUX returns (file_path_string, seed_int)
        if isinstance(result, tuple) and len(result) >= 2:
            temp_file_path, seed_used = result[0], result[1]
            
            if isinstance(temp_file_path, str) and Path(temp_file_path).exists():
                # Create output directory and destination path
                output_dir = Path("data/generated_images/flux")
                output_dir.mkdir(parents=True, exist_ok=True)
                dest_path = output_dir / "flux.png"
                
                # Handle file conversion if needed
                if temp_file_path.lower().endswith('.webp'):
                    from PIL import Image
                    with Image.open(temp_file_path) as img:
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        img.save(dest_path, 'PNG')
                else:
                    shutil.copy(temp_file_path, dest_path)
                
                return {
                    "success": True,
                    "image_path": str(dest_path),
                    "seed_used": seed_used
                }
            else:
                raise Exception(f"Temporary file not accessible: {temp_file_path}")
        else:
            raise Exception(f"Unexpected result format: {type(result)}")
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model using PartPacker."""
        print(f"🏗️ [HUGGINGFACE] Generating 3D model from: {image_path}")
        
        # Verify input image exists
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
        
        # Set defaults
        num_steps = kwargs.get('num_steps', 50)
        cfg_scale = kwargs.get('cfg_scale', 7)
        grid_res = kwargs.get('grid_res', 384)
        simplify_mesh = kwargs.get('simplify_mesh', False)
        target_num_faces = kwargs.get('target_num_faces', 100000)
        
        # Initialize client
        client = Client("nvidia/PartPacker", hf_token=self.hf_token)
        
        result = client.predict(
            input_image=handle_file(image_path),
            num_steps=num_steps,
            cfg_scale=cfg_scale,
            grid_res=grid_res,
            seed=seed,
            simplify_mesh=simplify_mesh,
            target_num_faces=target_num_faces,
            api_name="/process_3d"
        )
        
        if result:
            # Create output directory
            output_dir = Path("data/generated_models/partpacker_results")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy result to our directory
            dest_path = output_dir / f"partpacker_result_{seed}.glb"
            shutil.copy(result, dest_path)
            
            return {
                "success": True,
                "model_path": str(dest_path),
                "seed_used": seed
            }
        else:
            raise Exception("No model file returned from PartPacker API")

class CloudGenerationService(GenerationService):
    """Cloud generation service using runComfy."""
    
    def __init__(self):
        self.runcomfy_credentials_path = Path("runcomfy/credentials.txt")
        print("☁️  CloudGenerationService: Using RunComfy orchestrator")


class ServerlessGenerationService(GenerationService):
    """Serverless generation service using RunComfy Serverless API."""
    
    def __init__(self):
        try:
            from runcomfy.serverless_service import ServerlessRunComfyService
            self.service = ServerlessRunComfyService()
            print("⚡ ServerlessGenerationService: Using RunComfy Serverless API")
        except ImportError as e:
            print(f"❌ Failed to import ServerlessRunComfyService: {e}")
            self.service = None
    
    def is_available(self) -> bool:
        """Check if serverless service is available."""
        return self.service is not None and self.service.is_available()
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using FLUX.1-dev via serverless API."""
        if not self.service:
            raise Exception("ServerlessRunComfyService not available")
        
        return self.service.generate_flux_image(prompt, seed, **kwargs)
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image using serverless API."""
        if not self.service:
            raise Exception("ServerlessRunComfyService not available")
        
        return self.service.generate_flux_depth_image(control_image_path, prompt, seed, **kwargs)
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model using serverless API."""
        if not self.service:
            raise Exception("ServerlessRunComfyService not available")
        
        return self.service.generate_3d_model(image_path, seed, **kwargs)
    
    def generate_flux_mesh_unified(self, **kwargs) -> Dict[str, Any]:
        """Execute unified FLUX + 3D mesh generation (serverless-specific method)."""
        if not self.service:
            raise Exception("ServerlessRunComfyService not available")
        
        return self.service.generate_flux_mesh_unified(**kwargs)


class CloudGenerationService_Legacy(GenerationService):
    """Legacy cloud generation service using runComfy servers."""
    
    def __init__(self):
        self.runcomfy_credentials_path = Path("runcomfy/credentials.txt")
        print("☁️  CloudGenerationService_Legacy: Using RunComfy orchestrator")
    
    def is_available(self) -> bool:
        """Check if runComfy credentials are available."""
        try:
            if not self.runcomfy_credentials_path.exists():
                print(f"❌ RunComfy credentials not found: {self.runcomfy_credentials_path}")
                return False
            
            # Try to import runComfy components
            from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator
            from runcomfy.dev_server_state import DevServerStateManager
            
            # Check if dev server is running
            dev_manager = DevServerStateManager()
            server_state = dev_manager.load_server_state()
            
            if not server_state or server_state.status != "running":
                print("❌ RunComfy dev server not running")
                return False
            
            return True
            
        except ImportError as e:
            print(f"❌ RunComfy components not available: {e}")
            return False
        except Exception as e:
            print(f"❌ RunComfy availability check failed: {e}")
            return False
    
    def _run_async(self, coro):
        """Helper to run async function in sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create a new one
            return asyncio.run(coro)
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using runComfy FLUX workflow."""
        print(f"☁️ [CLOUD] Generating FLUX image: {prompt[:100]}...")
        
        # Save prompt to userPrompt.txt for workflow
        prompt_file = Path("data/generated_text/userPrompt.txt")
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt, encoding='utf-8')
        
        # Ensure render.png exists (use a placeholder if needed)
        render_path = Path("data/generated_images/gestureCamera/render.png")
        if not render_path.exists():
            print("⚠️ render.png not found, creating placeholder")
            render_path.parent.mkdir(parents=True, exist_ok=True)
            # Create a simple 1024x1024 white image as placeholder
            from PIL import Image
            placeholder = Image.new('RGB', (1024, 1024), 'white')
            placeholder.save(render_path)
        
        try:
            from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator
            
            async def run_generation():
                orchestrator = RunComfyOrchestrator()
                job = await orchestrator.execute_flux_mesh_generation(f"flux_gen_{seed}")
                return job
            
            job = self._run_async(run_generation())
            
            if job.status.value == "completed":
                return {
                    "success": True,
                    "image_path": str(job.generated_image_url) if job.generated_image_url else "data/generated_images/flux/flux.png",
                    "seed_used": seed,
                    "cost": job.actual_machine_cost or job.machine_cost_estimate or 0.0
                }
            else:
                raise Exception(f"RunComfy generation failed: {job.error_message}")
                
        except Exception as e:
            print(f"❌ Cloud FLUX generation failed: {e}")
            raise e
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image using runComfy FLUX workflow."""
        print(f"☁️ [CLOUD] Generating FLUX Depth image: {prompt[:100]}...")
        
        # For now, copy the control image to render.png and use the regular FLUX workflow
        # TODO: Implement a specific depth workflow when available
        render_path = Path("data/generated_images/gestureCamera/render.png")
        render_path.parent.mkdir(parents=True, exist_ok=True)
        
        if Path(control_image_path).exists():
            # Check if source and destination are the same file to avoid SameFileError
            if not Path(control_image_path).samefile(render_path):
                shutil.copy(control_image_path, render_path)
            else:
                print(f"🔄 Source and destination are the same file, skipping copy: {control_image_path}")
        else:
            raise FileNotFoundError(f"Control image not found: {control_image_path}")
        
        # Use the regular FLUX generation workflow
        return self.generate_flux_image(prompt, seed, **kwargs)
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model using runComfy workflow."""
        print(f"☁️ [CLOUD] Generating 3D model from: {image_path}")
        
        # Copy the input image to render.png for the workflow
        render_path = Path("data/generated_images/gestureCamera/render.png")
        render_path.parent.mkdir(parents=True, exist_ok=True)
        
        if Path(image_path).exists():
            # Check if source and destination are the same file to avoid SameFileError
            if not Path(image_path).samefile(render_path):
                shutil.copy(image_path, render_path)
            else:
                print(f"🔄 Source and destination are the same file, skipping copy: {image_path}")
        else:
            raise FileNotFoundError(f"Input image not found: {image_path}")
        
        # Set a default prompt for 3D generation
        prompt_file = Path("data/generated_text/userPrompt.txt")
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        default_prompt = kwargs.get('prompt', 'high quality 3D model, detailed, clean geometry')
        prompt_file.write_text(default_prompt, encoding='utf-8')
        
        try:
            from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator
            
            async def run_generation():
                orchestrator = RunComfyOrchestrator()
                job = await orchestrator.execute_flux_mesh_generation(f"3d_gen_{seed}")
                return job
            
            job = self._run_async(run_generation())
            
            if job.status.value == "completed":
                return {
                    "success": True,
                    "model_path": str(job.generated_mesh_url) if job.generated_mesh_url else "data/generated_models/partpacker_results/partpacker_result_0.glb",
                    "seed_used": seed,
                    "cost": job.actual_machine_cost or job.machine_cost_estimate or 0.0
                }
            else:
                raise Exception(f"RunComfy 3D generation failed: {job.error_message}")
                
        except Exception as e:
            print(f"❌ Cloud 3D generation failed: {e}")
            raise e

def get_generation_service(mode: str = "local") -> GenerationService:
    """Factory function to get the appropriate generation service."""
    if mode == "local":
        return LocalGenerationService()
    elif mode == "cloud":
        # Cloud now defaults to serverless for better performance
        return ServerlessGenerationService()
    elif mode == "serverless":
        return ServerlessGenerationService()
    elif mode == "cloud_legacy":
        # Legacy server-based cloud service
        return CloudGenerationService_Legacy()
    elif mode == "local_comfyui":
        # Local ComfyUI server service
        from launcher.local_comfyui_service import LocalComfyUIService
        return LocalComfyUIService()
    else:
        raise ValueError(f"Unknown generation mode: {mode}. Use 'local', 'cloud', 'serverless', 'cloud_legacy', or 'local_comfyui'.")
