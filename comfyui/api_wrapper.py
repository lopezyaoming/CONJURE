"""
This module provides a wrapper for interacting with the ComfyUI API.

It handles:
- Reading workflow JSON files.
- Connecting to the ComfyUI server via HTTP.
- Queueing prompts for execution.
- Polling for the results of the execution.

This implementation uses a simple HTTP polling mechanism, which is robust and
avoids the complexities of managing a persistent websocket connection,
mirroring the successful approach from the VIBE project.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import random
import uuid

COMFYUI_SERVER_ADDRESS = "127.0.0.1:8188"

def queue_prompt(prompt_workflow: dict, client_id: str) -> str | None:
    """
    Queues a workflow prompt on the ComfyUI server.

    Args:
        prompt_workflow: A dictionary representing the ComfyUI workflow.
        client_id: A unique string to identify the client session.

    Returns:
        The prompt ID if successfully queued, otherwise None.
    """
    try:
        # Prepare the data for the POST request
        data = {
            "prompt": prompt_workflow,
            "client_id": client_id
        }
        json_data = json.dumps(data).encode('utf-8')

        # Send the request to the ComfyUI server
        url = f"http://{COMFYUI_SERVER_ADDRESS}/prompt"
        req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
        
        print(f"Queueing prompt on {url}...")
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            
            if "prompt_id" in result:
                print(f"Successfully queued prompt with ID: {result['prompt_id']}")
                return result['prompt_id']
            else:
                print(f"Error queueing prompt: {result.get('error')}")
                return None

    except Exception as e:
        print(f"ERROR: Could not queue prompt on ComfyUI server: {e}")
        return None

def get_history(prompt_id: str) -> dict | None:
    """
    Retrieves the execution history for a given prompt ID.

    Args:
        prompt_id: The ID of the prompt to check.

    Returns:
        A dictionary containing the history, or None if an error occurs.
    """
    try:
        url = f"http://{COMFYUI_SERVER_ADDRESS}/history/{prompt_id}"
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"ERROR: Could not retrieve history for prompt {prompt_id}: {e}")
        return None

def run_workflow(workflow_data: dict, client_id: str, max_poll_time: int = 300) -> bool:
    """
    Runs a ComfyUI workflow and waits for it to complete.

    Args:
        workflow_data: The dictionary containing the workflow to run.
        client_id: A unique string to identify the client session.
        max_poll_time: The maximum time in seconds to wait for completion.

    Returns:
        True if the workflow completed successfully, False otherwise.
    """
    # Queue the prompt
    prompt_id = queue_prompt(workflow_data, client_id)
    if not prompt_id:
        return False

    start_time = time.time()
    print(f"Waiting for prompt {prompt_id} to complete...")

    # Poll the history endpoint until the prompt is processed
    while True:
        # Check for timeout
        if time.time() - start_time > max_poll_time:
            print(f"ERROR: Timed out waiting for prompt {prompt_id} to complete.")
            return False

        history = get_history(prompt_id)
        if history and prompt_id in history:
            # Check if the prompt's outputs are present, indicating completion
            if 'outputs' in history[prompt_id]:
                print(f"Prompt {prompt_id} completed successfully.")
                # You can optionally process outputs here if needed
                # outputs = history[prompt_id]['outputs']
                return True
        
        # Wait for a short interval before polling again
        time.sleep(1)

def load_workflow(workflow_path: str) -> dict | None:
    """
    Loads a ComfyUI workflow from a JSON file.

    Args:
        workflow_path: The full path to the workflow .json file.

    Returns:
        A dictionary representing the workflow, or None if an error occurs.
    """
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Workflow file not found at {workflow_path}")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in workflow file: {workflow_path}")
        return None

def modify_workflow_paths(workflow: dict, modifications: dict) -> dict:
    """
    Modifies specific node inputs in a loaded workflow dictionary.
    This is useful for dynamically setting file paths or other parameters.

    Example modifications dictionary:
    {
        "NODE_ID_1": {"input_name_1": "new_value_1"},
        "NODE_ID_2": {"input_name_2": "new_value_2"}
    }
    
    Args:
        workflow: The workflow dictionary to modify.
        modifications: A dictionary defining the changes to make.
    
    Returns:
        The modified workflow dictionary.
    """
    for node_id, inputs in modifications.items():
        if node_id in workflow:
            for input_name, new_value in inputs.items():
                if input_name in workflow[node_id]["inputs"]:
                    workflow[node_id]["inputs"][input_name] = new_value
                    print(f"Modified workflow: Node {node_id}, Input '{input_name}' set to '{new_value}'")
                else:
                    print(f"WARNING: Input '{input_name}' not found in Node {node_id}")
        else:
            print(f"WARNING: Node {node_id} not found in workflow")
    
    # Ensure a random seed for every run to avoid cached results
    for node_id, node_data in workflow.items():
        if "seed" in node_data["inputs"]:
            node_data["inputs"]["seed"] = random.randint(0, 9999999999)
            print(f"Randomized seed for Node {node_id}")
            
    return workflow

if __name__ == '__main__':
    # This is an example of how to use the wrapper.
    # This part will not run when the module is imported elsewhere.

    # 1. Define the path to your workflow
    # Assuming this script is in 'comfyui/' and workflows are in 'comfyui/workflows/'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(current_dir, 'workflows', 'promptMaker.json')

    # 2. Load the workflow
    print(f"Loading workflow: {workflow_path}")
    workflow = load_workflow(workflow_path)

    if workflow:
        # 3. (Optional) Modify the workflow before running
        # For example, let's change the input image and the user prompt text file path
        # In promptMaker.json:
        #  - Node 122 is LoadImage
        #  - Node 134 is Load Text File
        project_root = os.path.abspath(os.path.join(current_dir, '..'))
        
        # IMPORTANT: ComfyUI needs relative paths from its own directory structure.
        # The paths below assume ComfyUI's 'input' and CONJURE's 'data' are at specific relative locations.
        # This is typically handled by the launcher. For this example, we construct a plausible relative path.
        
        # This relative path assumes ComfyUI is running in a directory parallel to CONJURE,
        # or that CONJURE's data directory is symlinked into ComfyUI's input directory.
        # A more robust launcher would calculate this precisely.
        
        modifications = {
            "122": { # LoadImage node
                "image": "render.png" # Assuming it's in the default ComfyUI input folder
            },
            "134": { # Load Text File node
                "file_path": "../../data/generated_text/userPrompt.txt" # Path relative to workflow file
            },
        }
        
        # Let's assume we have a way to set the user prompt content first.
        prompt_path = os.path.join(project_root, 'data', 'generated_text', 'userPrompt.txt')
        os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
        with open(prompt_path, 'w') as f:
            f.write("A beautiful futuristic sculpture, cinematic lighting.")
        print(f"Created dummy prompt file at {prompt_path}")
        
        workflow = modify_workflow_paths(workflow, modifications)
        
        # 4. Run the workflow
        client_id = f"conjure_wrapper_test_{uuid.uuid4()}"
        success = run_workflow(workflow, client_id)

        if success:
            print("\nWorkflow execution completed successfully!")
        else:
            print("\nWorkflow execution failed.") 