#!/usr/bin/env python3
"""
RunComfy Serverless API Client
Processes render.png and userPrompt.txt to generate 3D mesh and image outputs
"""

import requests
import time
import os
import base64
import random
from pathlib import Path
from typing import Dict, Any, Optional

class RunComfyClient:
    def __init__(self, api_token: str, deployment_id: str):
        self.api_token = api_token
        self.deployment_id = deployment_id
        self.base_url = "https://api.runcomfy.net/prod/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 data URI"""
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded_string}"
    
    def submit_request(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Submit inference request to RunComfy API"""
        url = f"{self.base_url}/deployments/{self.deployment_id}/inference"
        payload = {"overrides": overrides}
        
        print("Submitting request to RunComfy API...")
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print(f"Request submitted successfully. Request ID: {result['request_id']}")
        return result
    
    def check_status(self, request_id: str) -> Dict[str, Any]:
        """Check the status of a request"""
        url = f"{self.base_url}/deployments/{self.deployment_id}/requests/{request_id}/status"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_results(self, request_id: str) -> Dict[str, Any]:
        """Get the results of a completed request"""
        url = f"{self.base_url}/deployments/{self.deployment_id}/requests/{request_id}/result"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, request_id: str, poll_interval: int = 10) -> Dict[str, Any]:
        """Wait for request to complete and return results"""
        print("Waiting for processing to complete...")
        
        while True:
            status = self.check_status(request_id)
            current_status = status.get("status")
            
            if current_status == "in_queue":
                queue_position = status.get("queue_position", "unknown")
                print(f"Status: In queue (position: {queue_position})")
            elif current_status == "in_progress":
                print("Status: Processing...")
            elif current_status == "completed":
                print("Status: Completed!")
                return self.get_results(request_id)
            elif current_status in ["failed", "canceled"]:
                print(f"Status: {current_status}")
                return self.get_results(request_id)
            else:
                print(f"Status: {current_status}")
            
            time.sleep(poll_interval)
    
    def download_file(self, url: str, output_path: str) -> None:
        """Download a file from URL to local path"""
        print(f"Downloading {url} to {output_path}")
        response = requests.get(url)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded: {output_path}")


def main():
    # Configuration from serverlessruncomfyinfo.txt
    API_TOKEN = "78356331-a9ec-49c2-a412-59140b32b9b3"  # API token 1
    DEPLOYMENT_ID = "dfcf38cd-0a09-4637-a067-5059dc9e444e"
    
    # File paths
    RENDER_IMAGE_PATH = "data/input/render.png"
    USER_PROMPT_PATH = "data/input/userPrompt.txt"
    OUTPUT_DIR = "data/output"
    
    # Verify input files exist
    if not os.path.exists(RENDER_IMAGE_PATH):
        raise FileNotFoundError(f"Input image not found: {RENDER_IMAGE_PATH}")
    if not os.path.exists(USER_PROMPT_PATH):
        raise FileNotFoundError(f"User prompt file not found: {USER_PROMPT_PATH}")
    
    # Read user prompt
    with open(USER_PROMPT_PATH, "r", encoding="utf-8") as f:
        user_prompt = f.read().strip()
    print(f"User prompt: {user_prompt}")
    
    # Initialize client
    client = RunComfyClient(API_TOKEN, DEPLOYMENT_ID)
    
    # Encode input image
    image_base64 = client.encode_image_to_base64(RENDER_IMAGE_PATH)
    
    # Generate random seed
    noise_seed = random.randint(1, 1000000000)
    print(f"Generated noise seed: {noise_seed}")
    
    # Prepare overrides based on workflow analysis
    overrides = {
        "16": {  # INPUTIMAGE - LoadImage node
            "inputs": {
                "image": image_base64
            }
        },
        "40": {  # FLUXCLIP - PrimitiveStringMultiline (empty for now)
            "inputs": {
                "value": ""
            }
        },
        "41": {  # FLUXT5XXL - PrimitiveStringMultiline (user prompt)
            "inputs": {
                "value": user_prompt
            }
        },
        "42": {  # NOISESEED - PrimitiveInt
            "inputs": {
                "value": noise_seed
            }
        }
    }
    
    try:
        # Submit request
        response = client.submit_request(overrides)
        request_id = response["request_id"]
        
        # Wait for completion
        results = client.wait_for_completion(request_id)
        
        # Process results
        if results.get("status") == "succeeded":
            outputs = results.get("outputs", {})
            print("\nProcessing completed successfully!")
            
            # Create output directory
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            
            # Download all output files
            for node_id, node_outputs in outputs.items():
                print(f"\nProcessing outputs from node {node_id}:")
                
                # Handle different output types
                if "images" in node_outputs:
                    for i, image_info in enumerate(node_outputs["images"]):
                        filename = image_info.get("filename", f"output_{node_id}_{i}.png")
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        client.download_file(image_info["url"], output_path)
                
                if "mesh" in node_outputs:
                    for i, mesh_info in enumerate(node_outputs["mesh"]):
                        filename = mesh_info.get("filename", f"output_{node_id}_{i}.glb")
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        client.download_file(mesh_info["url"], output_path)
                
                # Handle any other output types
                for output_type, output_list in node_outputs.items():
                    if output_type not in ["images", "mesh"] and isinstance(output_list, list):
                        for i, output_info in enumerate(output_list):
                            if isinstance(output_info, dict) and "url" in output_info:
                                filename = output_info.get("filename", f"output_{node_id}_{output_type}_{i}")
                                output_path = os.path.join(OUTPUT_DIR, filename)
                                client.download_file(output_info["url"], output_path)
            
            print(f"\nAll outputs saved to: {OUTPUT_DIR}")
            
        else:
            print(f"\nRequest failed with status: {results.get('status')}")
            if "error" in results:
                print(f"Error: {results['error']}")
                
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
