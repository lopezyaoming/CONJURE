"""
Generation Services Interface

This module provides abstract interfaces for different generation backends:
- LocalGenerationService: Uses HuggingFace models (FLUX, PartPacker)
- CloudGenerationService: Uses runComfy cloud services (to be implemented)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import os
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
    """Local generation service using HuggingFace models."""
    
    def __init__(self):
        self.hf_token = os.getenv("HUGGINGFACE_HUB_ACCESS_TOKEN")
        if not self.hf_token:
            print("⚠️  WARNING: HUGGINGFACE_HUB_ACCESS_TOKEN not set - using anonymous quota")
    
    def is_available(self) -> bool:
        """Check if HuggingFace token is available."""
        return self.hf_token is not None
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using FLUX.1-dev."""
        print(f"🎨 [LOCAL] Generating FLUX image: {prompt[:100]}...")
        
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
        print(f"🎨 [LOCAL] Generating FLUX Depth image: {prompt[:100]}...")
        
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
        print(f"🏗️ [LOCAL] Generating 3D model from: {image_path}")
        
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
    """Cloud generation service using runComfy (to be implemented)."""
    
    def __init__(self):
        # TODO: Initialize runComfy credentials and settings
        self.runcomfy_api_key = os.getenv("RUNCOMFY_API_KEY")
        self.runcomfy_base_url = os.getenv("RUNCOMFY_BASE_URL", "https://api.runcomfy.com")
        print("⚠️  CloudGenerationService: Implementation in progress")
    
    def is_available(self) -> bool:
        """Check if runComfy credentials are available."""
        # TODO: Check runComfy API availability
        return False  # Not implemented yet
    
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate image using runComfy FLUX workflow."""
        # TODO: Implement runComfy FLUX generation
        raise NotImplementedError("Cloud FLUX generation not yet implemented")
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image using runComfy FLUX.1-Depth workflow."""
        # TODO: Implement runComfy FLUX.1-Depth generation
        raise NotImplementedError("Cloud FLUX Depth generation not yet implemented")
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model using runComfy 3D workflow."""
        # TODO: Implement runComfy 3D generation
        raise NotImplementedError("Cloud 3D generation not yet implemented")

def get_generation_service(mode: str = "local") -> GenerationService:
    """Factory function to get the appropriate generation service."""
    if mode == "local":
        return LocalGenerationService()
    elif mode == "cloud":
        return CloudGenerationService()
    else:
        raise ValueError(f"Unknown generation mode: {mode}. Use 'local' or 'cloud'.")
