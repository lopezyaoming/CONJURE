"""
Local ComfyUI Service for CONJURE

This service connects directly to a locally running ComfyUI instance on localhost:8188
and executes the generate_flux_mesh_LOCAL.json workflow using the same data flow
as other generation modes.

Data Flow:
- Input: userPrompt.txt + render.png (from gestureCamera)
- Output: flux.png + partpacker_result_0.glb
"""

import asyncio
import json
import os
import shutil
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from launcher.generation_services import GenerationService
import launcher.config as config


class LocalComfyUIService(GenerationService):
    """Service for generating meshes using local ComfyUI server"""
    
    def __init__(self):
        super().__init__()
        self.comfyui_url = "http://127.0.0.1:8188"
        self.workflow_path = Path("comfyui/workflows/generate_flux_mesh_LOCAL.json")
        
        # Ensure output directories exist
        self.flux_output_dir = Path("data/generated_images/flux")
        self.mesh_output_dir = Path("data/generated_models/partpacker_results")
        self.flux_output_dir.mkdir(parents=True, exist_ok=True)
        self.mesh_output_dir.mkdir(parents=True, exist_ok=True)
        
        print("🖥️ Local ComfyUI Service initialized")
        print(f"   ComfyUI URL: {self.comfyui_url}")
        print(f"   Workflow: {self.workflow_path}")
    
    def check_comfyui_connection(self) -> bool:
        """Check if ComfyUI server is running and accessible"""
        try:
            response = urllib.request.urlopen(f"{self.comfyui_url}/object_info", timeout=5)
            if response.status == 200:
                print("✅ ComfyUI server connection verified")
                return True
            else:
                print(f"⚠️ ComfyUI server responded with status: {response.status}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to ComfyUI server: {e}")
            print("   Make sure ComfyUI is running on localhost:8188")
            return False
    
    def load_workflow(self) -> Dict[str, Any]:
        """Load the local ComfyUI workflow JSON"""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            print(f"✅ Loaded workflow: {self.workflow_path}")
            return workflow
        except FileNotFoundError:
            raise Exception(f"Workflow file not found: {self.workflow_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in workflow file: {e}")
    
    def prepare_workflow_inputs(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare workflow with CONJURE data inputs"""
        print("🔧 Preparing workflow with CONJURE data...")
        
        # Create a copy to avoid modifying the original
        prepared_workflow = json.loads(json.dumps(workflow))
        
        # 1. Read prompt from userPrompt.txt
        user_prompt_path = Path("data/generated_text/userPrompt.txt")
        if user_prompt_path.exists():
            try:
                with open(user_prompt_path, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                
                # Update prompt node (node 26 - STRING INPUT)
                if "26" in prepared_workflow:
                    prepared_workflow["26"]["inputs"]["value"] = prompt
                    print(f"✅ Updated prompt: {prompt[:100]}...")
                else:
                    print("⚠️ Prompt node 26 not found in workflow")
                    
            except Exception as e:
                print(f"⚠️ Failed to read userPrompt.txt: {e}")
        else:
            print(f"⚠️ userPrompt.txt not found: {user_prompt_path}")
        
        # 2. Verify input image exists and copy to ComfyUI input directory
        input_image_path = Path("data/generated_images/gestureCamera/render.png")
        if input_image_path.exists():
            # ComfyUI expects images in its input directory
            # We'll copy the render.png to ComfyUI's input folder
            try:
                # Try to find ComfyUI input directory - multiple common paths
                comfyui_input_paths = [
                    Path("C:/ComfyUI/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/input"),
                    Path("C:/ComfyUI/input"),
                    Path("../ComfyUI/input"),
                    Path("./ComfyUI/input"),
                    Path("input"),
                    # Also try config path from launcher config
                    Path(f"{config.COMFYUI_ROOT_PATH}/input") if hasattr(config, 'COMFYUI_ROOT_PATH') else Path(".")
                ]
                
                comfyui_input_dir = None
                for path in comfyui_input_paths:
                    if path.exists() and path.is_dir():
                        comfyui_input_dir = path
                        print(f"✅ Found ComfyUI input directory: {comfyui_input_dir}")
                        break
                
                if not comfyui_input_dir:
                    print("⚠️ Could not find ComfyUI input directory - creating local input folder")
                    comfyui_input_dir = Path("input")
                    comfyui_input_dir.mkdir(exist_ok=True)
                
                # Copy the render image
                dest_path = comfyui_input_dir / "render.png"
                shutil.copy2(input_image_path, dest_path)
                print(f"✅ Copied input image to ComfyUI: {dest_path}")
                
                # Update workflow to use the copied image (node 15 - IMAGE INPUT)
                if "15" in prepared_workflow:
                    prepared_workflow["15"]["inputs"]["image"] = "render.png"
                    print("✅ Updated workflow to use render.png")
                else:
                    print("⚠️ Image input node 15 not found in workflow")
                    
            except Exception as e:
                print(f"⚠️ Failed to copy input image: {e}")
                print("   Workflow will use existing image reference")
        else:
            print(f"⚠️ Input image not found: {input_image_path}")
        
        # 3. Set random seeds for generation
        import random
        seed = random.randint(1, 2147483647)
        
        # Update seeds in workflow
        seed_nodes = ["4", "21"]  # KSampler seed, PartPacker seed
        for node_id in seed_nodes:
            if node_id in prepared_workflow:
                if "seed" in prepared_workflow[node_id]["inputs"]:
                    prepared_workflow[node_id]["inputs"]["seed"] = seed
                    print(f"✅ Set seed for node {node_id}: {seed}")
        
        print("🔧 Workflow preparation complete")
        return prepared_workflow
    
    def queue_prompt(self, workflow: Dict[str, Any]) -> Optional[str]:
        """Queue a workflow prompt on the ComfyUI server"""
        client_id = f"conjure_local_{uuid.uuid4()}"
        
        try:
            # Prepare the data for the POST request
            data = {
                "prompt": workflow,
                "client_id": client_id
            }
            json_data = json.dumps(data).encode('utf-8')

            # Send the request to the ComfyUI server
            url = f"{self.comfyui_url}/prompt"
            req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
            
            print(f"📤 Queueing prompt on {url}...")
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                
                if "prompt_id" in result:
                    prompt_id = result['prompt_id']
                    print(f"✅ Successfully queued prompt with ID: {prompt_id}")
                    return prompt_id
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"❌ Error queueing prompt: {error_msg}")
                    return None

        except Exception as e:
            print(f"❌ ERROR: Could not queue prompt on ComfyUI server: {e}")
            return None
    
    def get_history(self, prompt_id: str) -> Optional[Dict]:
        """Get execution history for a prompt ID"""
        try:
            url = f"{self.comfyui_url}/history/{prompt_id}"
            with urllib.request.urlopen(url) as response:
                history = json.loads(response.read())
                return history.get(prompt_id)
        except Exception as e:
            print(f"❌ ERROR: Could not retrieve history for prompt {prompt_id}: {e}")
            return None
    
    def wait_for_completion(self, prompt_id: str, max_wait_time: int = 600) -> bool:
        """Wait for workflow execution to complete"""
        print(f"⏳ Waiting for workflow completion: {prompt_id}")
        print(f"   Max wait time: {max_wait_time}s")
        
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > max_wait_time:
                print(f"⏰ Timeout reached ({max_wait_time}s)")
                return False
            
            # Get history
            history = self.get_history(prompt_id)
            if history and 'outputs' in history:
                print(f"✅ Workflow completed successfully! ({elapsed:.1f}s)")
                return True
            
            # Show progress every 10 seconds
            if int(elapsed) % 10 == 0:
                print(f"   ⏳ Still waiting... ({elapsed:.0f}s elapsed)")
            
            time.sleep(2)  # Poll every 2 seconds
    
    def download_results(self, prompt_id: str) -> bool:
        """Download workflow results to CONJURE data folders"""
        print("💾 Downloading workflow results...")
        
        history = self.get_history(prompt_id)
        if not history or 'outputs' not in history:
            print("❌ No outputs found in history")
            return False
        
        outputs = history['outputs']
        success = True
        
        try:
            # Download IMAGE EXPORT (node 9) -> flux.png
            if "9" in outputs and "images" in outputs["9"]:
                image_info = outputs["9"]["images"][0]
                filename = image_info["filename"]
                subfolder = image_info.get("subfolder", "")
                
                # Download the image
                params = {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": "output"
                }
                
                # Construct download URL
                url_params = "&".join([f"{k}={v}" for k, v in params.items()])
                download_url = f"{self.comfyui_url}/view?{url_params}"
                
                print(f"📥 Downloading FLUX image: {filename}")
                
                with urllib.request.urlopen(download_url) as response:
                    image_data = response.read()
                
                # Save as flux.png
                flux_path = self.flux_output_dir / "flux.png"
                with open(flux_path, 'wb') as f:
                    f.write(image_data)
                
                print(f"✅ Saved FLUX image: {flux_path}")
            else:
                print("⚠️ No image output found (node 9)")
                success = False
            
            # Handle GLB mesh file - try API first, then direct file copy
            mesh_downloaded = False
            
            # Try downloading through ComfyUI API first
            if "22" in outputs and "files" in outputs["22"]:
                try:
                    file_info = outputs["22"]["files"][0]
                    filename = file_info["filename"]
                    subfolder = file_info.get("subfolder", "")
                    
                    # Download the mesh file
                    params = {
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": "output"
                    }
                    
                    url_params = "&".join([f"{k}={v}" for k, v in params.items()])
                    download_url = f"{self.comfyui_url}/view?{url_params}"
                    
                    print(f"📥 Downloading 3D mesh via API: {filename}")
                    
                    with urllib.request.urlopen(download_url) as response:
                        mesh_data = response.read()
                    
                    # Save as partpacker_result_0.glb
                    mesh_path = self.mesh_output_dir / "partpacker_result_0.glb"
                    with open(mesh_path, 'wb') as f:
                        f.write(mesh_data)
                    
                    print(f"✅ Saved 3D mesh via API: {mesh_path}")
                    mesh_downloaded = True
                    
                except Exception as api_error:
                    print(f"⚠️ API download failed: {api_error}")
                    mesh_downloaded = False
            
            # If API download failed, try direct file copy from ComfyUI output folder
            if not mesh_downloaded:
                print("📁 Attempting direct file copy from ComfyUI output folder...")
                mesh_downloaded = self.copy_mesh_from_output_folder()
            
            if not mesh_downloaded:
                print("❌ Failed to retrieve mesh file through both API and direct copy")
                success = False
                
        except Exception as e:
            print(f"❌ Error downloading results: {e}")
            success = False
        
        return success
    
    def copy_mesh_from_output_folder(self) -> bool:
        """Copy the most recent GLB file from ComfyUI output folder"""
        try:
            # Try to find ComfyUI output directory
            possible_paths = [
                Path("C:/ComfyUI/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/output"),
                Path("C:/ComfyUI/output"),
                Path("../ComfyUI/output"),
                Path("./ComfyUI/output"),
                Path("output")
            ]
            
            comfyui_output_dir = None
            for path in possible_paths:
                if path.exists():
                    comfyui_output_dir = path
                    break
            
            if not comfyui_output_dir:
                print("❌ Could not find ComfyUI output directory")
                return False
            
            print(f"📁 Searching for GLB files in: {comfyui_output_dir}")
            
            # Find the most recent GLB file
            glb_files = list(comfyui_output_dir.glob("*.glb"))
            if not glb_files:
                print("❌ No GLB files found in ComfyUI output directory")
                return False
            
            # Sort by modification time, get most recent
            most_recent_glb = max(glb_files, key=lambda f: f.stat().st_mtime)
            print(f"📄 Found most recent GLB: {most_recent_glb.name}")
            
            # Copy to CONJURE mesh output directory
            mesh_path = self.mesh_output_dir / "partpacker_result_0.glb"
            shutil.copy2(most_recent_glb, mesh_path)
            
            print(f"✅ Copied GLB file: {mesh_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error copying mesh file: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if local ComfyUI service is available."""
        return self.check_comfyui_connection()
    
    def generate_flux_mesh(self, **kwargs) -> Dict[str, Any]:
        """
        Generate FLUX image and 3D mesh using local ComfyUI
        
        Uses the same data flow as other generation modes:
        - Input: userPrompt.txt + render.png (from gestureCamera)
        - Output: flux.png + partpacker_result_0.glb
        """
        print("🚀 Starting LOCAL ComfyUI generation...")
        
        try:
            # 1. Check ComfyUI connection
            if not self.check_comfyui_connection():
                return {
                    "success": False,
                    "error": "ComfyUI server not accessible"
                }
            
            # 2. Load workflow
            workflow = self.load_workflow()
            
            # 3. Prepare inputs
            prepared_workflow = self.prepare_workflow_inputs(workflow)
            
            # 4. Queue prompt
            prompt_id = self.queue_prompt(prepared_workflow)
            if not prompt_id:
                return {
                    "success": False,
                    "error": "Failed to queue workflow"
                }
            
            # 5. Wait for completion
            if not self.wait_for_completion(prompt_id):
                return {
                    "success": False,
                    "error": "Workflow execution timeout"
                }
            
            # 6. Download results
            if not self.download_results(prompt_id):
                return {
                    "success": False,
                    "error": "Failed to download results"
                }
            
            # 7. Verify outputs exist
            flux_path = self.flux_output_dir / "flux.png"
            mesh_path = self.mesh_output_dir / "partpacker_result_0.glb"
            
            if flux_path.exists() and mesh_path.exists():
                print("✅ LOCAL ComfyUI generation completed successfully!")
                return {
                    "success": True,
                    "flux_image": str(flux_path),
                    "mesh_model": str(mesh_path),
                    "prompt_id": prompt_id
                }
            else:
                return {
                    "success": False,
                    "error": "Output files not found after download"
                }
                
        except Exception as e:
            print(f"❌ LOCAL ComfyUI generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Required methods from GenerationService base class
    def generate_flux_image(self, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate FLUX image (part of the unified generate_flux_mesh)"""
        result = self.generate_flux_mesh(**kwargs)
        if result["success"]:
            return {
                "success": True,
                "image_path": result["flux_image"]
            }
        else:
            return result
    
    def generate_flux_depth_image(self, control_image_path: str, prompt: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate depth-controlled image (part of the unified generate_flux_mesh)"""
        result = self.generate_flux_mesh(**kwargs)
        if result["success"]:
            return {
                "success": True,
                "image_path": result["flux_image"]
            }
        else:
            return result
    
    def generate_3d_model(self, image_path: str, seed: int = 0, **kwargs) -> Dict[str, Any]:
        """Generate 3D model (part of the unified generate_flux_mesh)"""
        result = self.generate_flux_mesh(**kwargs)
        if result["success"]:
            return {
                "success": True,
                "model_path": result["mesh_model"]
            }
        else:
            return result
