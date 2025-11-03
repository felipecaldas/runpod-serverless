"""
RunPod serverless worker handler for ComfyUI.

This module implements the RunPod handler function that processes incoming
jobs from the RunPod platform and forwards them to the ComfyUI server.
"""

import os
import json
import base64
import uuid
import requests
import websocket
import time
from typing import Dict, Any, List, Optional
import runpod


# ComfyUI server configuration
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")
COMFY_API_BASE = f"http://{COMFY_HOST}"

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main handler function for RunPod serverless worker.
    
    Args:
        job: RunPod job dictionary containing input data
        
    Returns:
        Dictionary containing the job results
    """
    try:
        job_input = job.get("input", {})
        
        # Extract workflow and images from job input
        workflow = job_input.get("workflow")
        images = job_input.get("images", [])
        comfy_org_api_key = job_input.get("comfy_org_api_key")
        
        if not workflow:
            raise ValueError("Workflow is required in job input")
        
        # Set Comfy.org API key if provided
        if comfy_org_api_key:
            os.environ["COMFY_ORG_API_KEY"] = comfy_org_api_key
        
        # Upload input images to ComfyUI if provided
        for image_data in images:
            upload_image_to_comfyui(image_data)
        
        # Generate unique client ID for this job
        client_id = str(uuid.uuid4())
        
        # Submit workflow to ComfyUI
        prompt_id = submit_workflow_to_comfyui(workflow, client_id)
        
        # Monitor workflow execution using websocket
        wait_for_completion(client_id, prompt_id)
        
        # Get results from ComfyUI
        result = get_workflow_results(prompt_id)
        
        # Process output images
        output_images = process_output_images(result, job.get("id", "unknown"))
        
        return {
            "output": {
                "images": output_images
            }
        }
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error in handler: {str(e)}")
        return {
            "output": {
                "errors": [str(e)]
            }
        }


def upload_image_to_comfyui(image_data: Dict[str, Any]) -> None:
    """
    Upload an image to ComfyUI's input directory.
    
    Args:
        image_data: Dictionary containing image name and base64 data
    """
    try:
        name = image_data.get("name")
        image_b64 = image_data.get("image")
        
        if not name or not image_b64:
            raise ValueError("Image name and data are required")
        
        # Remove data URI prefix if present
        if image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_b64)
        
        # Upload to ComfyUI
        files = {"image": (name, image_bytes, "image/png")}
        response = requests.post(f"{COMFY_API_BASE}/upload/image", files=files)
        response.raise_for_status()
        
        print(f"Successfully uploaded image: {name}")
        
    except Exception as e:
        print(f"Error uploading image {name}: {str(e)}")
        raise


def submit_workflow_to_comfyui(workflow: Dict[str, Any], client_id: str) -> str:
    """
    Submit a workflow to ComfyUI for execution.
    
    Args:
        workflow: ComfyUI workflow JSON
        client_id: Unique client ID for this job
        
    Returns:
        Prompt ID from ComfyUI
    """
    try:
        payload = {
            "prompt": workflow,
            "client_id": client_id
        }
        
        response = requests.post(f"{COMFY_API_BASE}/prompt", json=payload)
        response.raise_for_status()
        
        result = response.json()
        prompt_id = result.get("prompt_id")
        
        if not prompt_id:
            raise ValueError("No prompt_id returned from ComfyUI")
        
        print(f"Submitted workflow to ComfyUI, prompt_id: {prompt_id}")
        return prompt_id
        
    except Exception as e:
        print(f"Error submitting workflow to ComfyUI: {str(e)}")
        raise


def wait_for_completion(client_id: str, prompt_id: str) -> None:
    """
    Wait for workflow completion using ComfyUI websocket API.
    
    Args:
        client_id: Unique client ID for this job
        prompt_id: Prompt ID to monitor
    """
    try:
        ws_url = f"ws://{COMFY_HOST}/ws?clientId={client_id}"
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        
        print(f"Connected to ComfyUI websocket: {ws_url}")
        
        while True:
            message = ws.recv()
            data = json.loads(message)
            
            # Check if this is the completion message for our prompt
            if (data.get("type") == "executing" and 
                data.get("data", {}).get("prompt_id") == prompt_id and
                data.get("data", {}).get("node") is None):
                
                print(f"Workflow completed for prompt_id: {prompt_id}")
                break
                
        ws.close()
        
    except Exception as e:
        print(f"Error monitoring workflow completion: {str(e)}")
        raise


def get_workflow_results(prompt_id: str) -> Dict[str, Any]:
    """
    Get the results of a completed workflow from ComfyUI.
    
    Args:
        prompt_id: Prompt ID to get results for
        
    Returns:
        Workflow history/results from ComfyUI
    """
    try:
        response = requests.get(f"{COMFY_API_BASE}/history/{prompt_id}")
        response.raise_for_status()
        
        history = response.json()
        
        if not history or prompt_id not in history:
            raise ValueError(f"No history found for prompt_id: {prompt_id}")
        
        return history[prompt_id]
        
    except Exception as e:
        print(f"Error getting workflow results: {str(e)}")
        raise


def process_output_images(history: Dict[str, Any], job_id: str) -> List[Dict[str, Any]]:
    """
    Process output images from ComfyUI workflow results.
    
    Args:
        history: Workflow history from ComfyUI
        job_id: RunPod job ID for S3 upload
        
    Returns:
        List of processed image dictionaries
    """
    output_images = []
    
    try:
        outputs = history.get("outputs", {})
        
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for image_info in node_output["images"]:
                    filename = image_info.get("filename")
                    subfolder = image_info.get("subfolder", "")
                    image_type = image_info.get("type", "output")
                    
                    if not filename:
                        continue
                    
                    # Get image data from ComfyUI
                    image_data = get_image_data(filename, subfolder, image_type)
                    
                    # Check if S3 upload is configured
                    if os.environ.get("BUCKET_ENDPOINT_URL"):
                        # Upload to S3
                        s3_url = upload_to_s3(image_data, filename, job_id)
                        output_images.append({
                            "filename": filename,
                            "type": "s3_url",
                            "data": s3_url
                        })
                    else:
                        # Return as base64
                        image_b64 = base64.b64encode(image_data).decode("utf-8")
                        output_images.append({
                            "filename": filename,
                            "type": "base64",
                            "data": image_b64
                        })
        
        print(f"Processed {len(output_images)} output images")
        return output_images
        
    except Exception as e:
        print(f"Error processing output images: {str(e)}")
        raise


def get_image_data(filename: str, subfolder: str, image_type: str) -> bytes:
    """
    Get image data from ComfyUI view endpoint.
    
    Args:
        filename: Image filename
        subfolder: Subfolder path
        image_type: Image type (output, input, temp)
        
    Returns:
        Raw image bytes
    """
    try:
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": image_type
        }
        
        response = requests.get(f"{COMFY_API_BASE}/view", params=params)
        response.raise_for_status()
        
        return response.content
        
    except Exception as e:
        print(f"Error getting image data for {filename}: {str(e)}")
        raise


def upload_to_s3(image_data: bytes, filename: str, job_id: str) -> str:
    """
    Upload image data to S3 using RunPod's upload utility.
    
    Args:
        image_data: Raw image bytes
        filename: Original filename
        job_id: RunPod job ID
        
    Returns:
        S3 URL of uploaded image
    """
    try:
        import tempfile
        from runpod import upload_image
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name
        
        try:
            # Upload using RunPod's utility
            s3_url = upload_image(job_id, temp_file_path)
            print(f"Uploaded {filename} to S3: {s3_url}")
            return s3_url
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except Exception as e:
        print(f"Error uploading {filename} to S3: {str(e)}")
        raise


# Health check endpoint handler
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for RunPod.
    
    Returns:
        Health status response
    """
    try:
        # Check if ComfyUI is accessible
        response = requests.get(f"{COMFY_API_BASE}/system_stats", timeout=5)
        response.raise_for_status()
        
        return {"status": "healthy"}
        
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}


# Start the RunPod serverless worker
if __name__ == "__main__":
    print("Starting RunPod serverless worker for ComfyUI...")
    runpod.serverless.start({"handler": handler})
