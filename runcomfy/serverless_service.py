"""
RunComfy Serverless Generation Service
Implements the GenerationService interface using RunComfy's Serverless API.
Replaces server-based generation with instant serverless workflow execution.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional

from runcomfy.serverless_client import ServerlessRunComfyClient, RequestStatus


class ServerlessRunComfyService:
    """
    Serverless generation service using RunComfy Serverless API.
    Provides unified FLUX + 3D mesh generation through pre-deployed workflows.
    """
    
    def __init__(self):
        self.client = ServerlessRunComfyClient()
        
        # Configuration
        self.default_steps_flux = int(os.getenv("RUNCOMFY_DEFAULT_STEPS_FLUX", "20"))
        self.default_steps_partpacker = int(os.getenv("RUNCOMFY_DEFAULT_STEPS_PARTPACKER", "50"))
        self.enable_cost_tracking = os.getenv("RUNCOMFY_COST_TRACKING", "true").lower() == "true"
        
        # Output directories
        self.flux_output_dir = Path("data/generated_images/flux")
        self.mesh_output_dir = Path("data/generated_models/partpacker_results")
        
        print(f"☁️ ServerlessRunComfyService initialized")
        print(f"   Default FLUX steps: {self.default_steps_flux}")
        print(f"   Default PartPacker steps: {self.default_steps_partpacker}")
        print(f"   Cost tracking: {self.enable_cost_tracking}")
    
    def is_available(self) -> bool:
        """Check if serverless service is available."""
        return self.client.is_available()
    
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
    
    def _ensure_conjure_data_available(self) -> tuple[str, str]:
        """
        Ensure CONJURE data files are available for generation.
        
        Returns:
            Tuple of (prompt, render_image_path)
        """
        # Read prompt from userPrompt.txt
        prompt_file = Path("data/generated_text/userPrompt.txt")
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                print(f"✅ Loaded prompt from userPrompt.txt: {prompt[:100]}...")
            except Exception as e:
                print(f"⚠️ Failed to read userPrompt.txt: {e}")
                prompt = "high quality 3D model, detailed, clean geometry"
        else:
            print(f"⚠️ userPrompt.txt not found, using default prompt")
            prompt = "high quality 3D model, detailed, clean geometry"
        
        # Check for render.png from GestureCamera
        render_path = Path("data/generated_images/gestureCamera/render.png")
        if not render_path.exists():
            print(f"⚠️ render.png not found at {render_path}, creating placeholder")
            render_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create a simple 1024x1024 white image as placeholder
            try:
                from PIL import Image
                placeholder = Image.new('RGB', (1024, 1024), 'white')
                placeholder.save(render_path)
                print(f"✅ Created placeholder render.png: {render_path}")
            except ImportError:
                print(f"❌ PIL not available, cannot create placeholder image")
                raise FileNotFoundError(f"render.png not found and cannot create placeholder: {render_path}")
        
        return prompt, str(render_path)
    
    async def _execute_unified_generation(
        self,
        prompt: str,
        render_image_path: str,
        seed: Optional[int] = None,
        steps_flux: Optional[int] = None,
        steps_partpacker: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute unified FLUX + 3D mesh generation workflow.
        
        Args:
            prompt: Text prompt for generation
            render_image_path: Path to input render image
            seed: Random seed for generation
            steps_flux: FLUX inference steps
            steps_partpacker: PartPacker steps
            
        Returns:
            Generation result with local file paths
        """
        # Use defaults if not specified
        steps_flux = steps_flux or self.default_steps_flux
        steps_partpacker = steps_partpacker or self.default_steps_partpacker
        
        print(f"🚀 Executing unified FLUX + 3D generation via Serverless API")
        print(f"   Prompt: {prompt[:100]}...")
        print(f"   Input image: {render_image_path}")
        print(f"   FLUX steps: {steps_flux}")
        print(f"   PartPacker steps: {steps_partpacker}")
        
        try:
            # Submit request to serverless workflow
            request = await self.client.submit_request(
                prompt=prompt,
                render_image_path=render_image_path,
                seed=seed,
                steps_flux=steps_flux,
                steps_partpacker=steps_partpacker
            )
            
            # Wait for completion with progress monitoring
            completed_request = await self.client.wait_for_completion(request.request_id)
            
            if completed_request.status in [RequestStatus.COMPLETED, RequestStatus.SUCCEEDED]:
                print(f"✅ Generation completed successfully!")
                
                # Download outputs to CONJURE directories
                print(f"📥 Downloading outputs to local directories...")
                
                # Download FLUX image to flux directory
                self.flux_output_dir.mkdir(parents=True, exist_ok=True)
                downloaded_files = await self.client.download_outputs(
                    completed_request, 
                    self.flux_output_dir
                )
                
                # Move mesh file to proper directory if needed
                if "mesh_model" in downloaded_files:
                    mesh_source = Path(downloaded_files["mesh_model"])
                    self.mesh_output_dir.mkdir(parents=True, exist_ok=True)
                    mesh_dest = self.mesh_output_dir / "partpacker_result_0.glb"
                    
                    if mesh_source != mesh_dest:
                        import shutil
                        shutil.move(str(mesh_source), str(mesh_dest))
                        downloaded_files["mesh_model"] = str(mesh_dest)
                        print(f"📦 Moved mesh to: {mesh_dest}")
                
                return {
                    "success": True,
                    "request_id": completed_request.request_id,
                    "flux_image_path": downloaded_files.get("flux_image"),
                    "mesh_model_path": downloaded_files.get("mesh_model"),
                    "seed_used": seed,
                    "steps_flux": steps_flux,
                    "steps_partpacker": steps_partpacker,
                    "generation_mode": "serverless"
                }
                
            else:
                error_msg = completed_request.error_message or f"Generation failed with status: {completed_request.status.value}"
                print(f"❌ Generation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "request_id": completed_request.request_id,
                    "status": completed_request.status.value
                }
                
        except Exception as e:
            print(f"❌ Serverless generation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """
        Generate image using FLUX.1-dev via serverless workflow.
        Note: This executes the full FLUX+3D pipeline but only returns image results.
        """
        print(f"🎨 [SERVERLESS] Generating FLUX image: {prompt[:100]}...")
        
        try:
            # Get CONJURE data
            actual_prompt, render_image_path = self._ensure_conjure_data_available()
            
            # Use provided prompt if different from userPrompt.txt
            if prompt != actual_prompt:
                print(f"🔄 Using provided prompt instead of userPrompt.txt")
                actual_prompt = prompt
            
            # Extract parameters
            steps_flux = kwargs.get('num_inference_steps', self.default_steps_flux)
            
            # Execute unified generation
            async def run_generation():
                return await self._execute_unified_generation(
                    prompt=actual_prompt,
                    render_image_path=render_image_path,
                    seed=seed if seed > 0 else None,
                    steps_flux=steps_flux
                )
            
            result = self._run_async(run_generation())
            
            if result["success"]:
                flux_path = result.get("flux_image_path")
                if flux_path and Path(flux_path).exists():
                    return {
                        "success": True,
                        "image_path": flux_path,
                        "seed_used": result.get("seed_used", seed),
                        "generation_mode": "serverless"
                    }
                else:
                    raise Exception("FLUX image not generated or not found")
            else:
                raise Exception(result.get("error", "Unknown error"))
                
        except Exception as e:
            print(f"❌ Serverless FLUX generation failed: {e}")
            raise e
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """
        Generate depth-controlled image using serverless workflow.
        For serverless, we use the control image as the render input.
        """
        print(f"🎨 [SERVERLESS] Generating FLUX Depth image: {prompt[:100]}...")
        
        try:
            # For serverless, we use the control image directly as render input
            if not Path(control_image_path).exists():
                raise FileNotFoundError(f"Control image not found: {control_image_path}")
            
            # Extract parameters
            steps_flux = kwargs.get('num_inference_steps', self.default_steps_flux)
            
            # Execute unified generation with control image as input
            async def run_generation():
                return await self._execute_unified_generation(
                    prompt=prompt,
                    render_image_path=control_image_path,
                    seed=seed if seed > 0 else None,
                    steps_flux=steps_flux
                )
            
            result = self._run_async(run_generation())
            
            if result["success"]:
                flux_path = result.get("flux_image_path")
                if flux_path and Path(flux_path).exists():
                    return {
                        "success": True,
                        "image_path": flux_path,
                        "seed_used": result.get("seed_used", seed),
                        "generation_mode": "serverless"
                    }
                else:
                    raise Exception("FLUX depth image not generated or not found")
            else:
                raise Exception(result.get("error", "Unknown error"))
                
        except Exception as e:
            print(f"❌ Serverless FLUX Depth generation failed: {e}")
            raise e
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """
        Generate 3D model using serverless workflow.
        Note: This executes the full FLUX+3D pipeline but only returns mesh results.
        """
        print(f"🏗️ [SERVERLESS] Generating 3D model from: {image_path}")
        
        try:
            if not Path(image_path).exists():
                raise FileNotFoundError(f"Input image not found: {image_path}")
            
            # Extract parameters
            steps_partpacker = kwargs.get('num_steps', self.default_steps_partpacker)
            prompt = kwargs.get('prompt', 'high quality 3D model, detailed, clean geometry')
            
            # Execute unified generation
            async def run_generation():
                return await self._execute_unified_generation(
                    prompt=prompt,
                    render_image_path=image_path,
                    seed=seed if seed > 0 else None,
                    steps_partpacker=steps_partpacker
                )
            
            result = self._run_async(run_generation())
            
            if result["success"]:
                mesh_path = result.get("mesh_model_path")
                if mesh_path and Path(mesh_path).exists():
                    return {
                        "success": True,
                        "model_path": mesh_path,
                        "seed_used": result.get("seed_used", seed),
                        "generation_mode": "serverless"
                    }
                else:
                    raise Exception("3D model not generated or not found")
            else:
                raise Exception(result.get("error", "Unknown error"))
                
        except Exception as e:
            print(f"❌ Serverless 3D generation failed: {e}")
            raise e
    
    def generate_flux_mesh_unified(
        self,
        prompt: Optional[str] = None,
        render_image_path: Optional[str] = None,
        seed: Optional[int] = None,
        steps_flux: Optional[int] = None,
        steps_partpacker: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete CONJURE FLUX + 3D mesh generation pipeline.
        This is the primary method for serverless generation.
        
        Args:
            prompt: Text prompt (uses userPrompt.txt if None)
            render_image_path: Input image path (uses GestureCamera render.png if None)
            seed: Random seed for generation
            steps_flux: FLUX inference steps
            steps_partpacker: PartPacker steps
            
        Returns:
            Complete generation result with both FLUX image and 3D mesh
        """
        print(f"🚀 [SERVERLESS] Executing unified FLUX + 3D mesh generation")
        
        try:
            # Get CONJURE data if not provided
            if not prompt or not render_image_path:
                auto_prompt, auto_render_path = self._ensure_conjure_data_available()
                prompt = prompt or auto_prompt
                render_image_path = render_image_path or auto_render_path
            
            # Execute unified generation
            async def run_generation():
                return await self._execute_unified_generation(
                    prompt=prompt,
                    render_image_path=render_image_path,
                    seed=seed,
                    steps_flux=steps_flux,
                    steps_partpacker=steps_partpacker
                )
            
            result = self._run_async(run_generation())
            
            if result["success"]:
                print(f"✅ [SERVERLESS] Unified generation completed successfully!")
                print(f"   FLUX image: {result.get('flux_image_path', 'N/A')}")
                print(f"   3D mesh: {result.get('mesh_model_path', 'N/A')}")
                return result
            else:
                print(f"❌ [SERVERLESS] Unified generation failed: {result.get('error', 'Unknown error')}")
                return result
                
        except Exception as e:
            print(f"❌ [SERVERLESS] Unified generation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "generation_mode": "serverless"
            }
