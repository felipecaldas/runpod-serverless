#!/usr/bin/env python3
"""
Local API server for testing RunPod serverless worker.
This provides FastAPI endpoints that forward requests to ComfyUI.
"""

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import requests
import json
import os
import traceback
import sys
import threading
import time
import uuid
from typing import Dict, Any
from enum import Enum

app = FastAPI(title='RunPod Serverless Worker API')

COMFY_API_BASE = "http://127.0.0.1:8188"

WORKFLOW_TEMPLATES: Dict[str, str] = {
    "video_wan2_2_14B_i2v": "video_wan2_2_14B_i2v.json",
    "T2I_ChromaAnimaAIO": "T2I_ChromaAnimaAIO.json",
    "qwen-image-fast-runpod": "qwen-image-fast-runpod.json",
    "crayon-drawing": "crayon-drawing.json",
    "I2V-Wan-2.2-Lightning-runpod": "I2V-Wan-2.2-Lightning-runpod.json"
}


def load_workflow_template(workflow_name: str) -> Dict[str, Any]:
    """Load workflow template from local workflows directory."""
    template_file = WORKFLOW_TEMPLATES.get(workflow_name)
    if not template_file:
        raise ValueError(f"Unknown workflow '{workflow_name}'")

    template_path = os.path.join(os.path.dirname(__file__), "..", "workflows", template_file)
    try:
        with open(template_path, "r", encoding="utf-8") as workflow_file:
            return json.load(workflow_file)
    except FileNotFoundError as exc:
        raise ValueError(f"Workflow template not found at {template_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in workflow template: {exc}") from exc

class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# In-memory storage for job status (in production, use Redis or database)
job_status_store: Dict[str, Dict[str, Any]] = {}
job_results: Dict[str, Dict[str, Any]] = {}


@app.post('/run')
async def run_endpoint(request: Request):
    """
    Async job submission endpoint.
    Accepts a workflow and submits it to ComfyUI.
    """
    try:
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse JSON body: {e}", file=sys.stderr)
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        
        print(f"Received /run request: {json.dumps(body)[:200]}...")
        
        # Validate input shape
        if not isinstance(body, dict) or 'input' not in body:
            raise HTTPException(status_code=400, detail="'input' is required in request body")
        
        job_input = body.get('input')
        if not isinstance(job_input, dict):
            raise HTTPException(status_code=400, detail="'input' must be an object")

        workflow_name = job_input.get('comfyui_workflow_name', 'video_wan2_2_14B_i2v')
        try:
            workflow = load_workflow_template(workflow_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        
        print(f"Submitting workflow '{workflow_name}' to ComfyUI: {json.dumps(workflow)[:200]}...")
        
        # Forward to ComfyUI - wrap workflow in 'prompt' key as ComfyUI expects
        comfy_payload = {"prompt": workflow}
        comfy_url = f'{COMFY_API_BASE}/prompt'
        response = requests.post(comfy_url, json=comfy_payload, timeout=30)
        
        print(f"ComfyUI response status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"ComfyUI response: {json.dumps(result)[:200]}...")
            except Exception as e:
                print(f"ERROR: Failed to parse ComfyUI JSON response: {e}", file=sys.stderr)
                raise HTTPException(
                    status_code=502, 
                    detail=f"Invalid JSON from ComfyUI: {response.text[:500]}"
                )
            
            # Check for errors in ComfyUI response
            if 'error' in result:
                error_detail = result.get('error')
                print(f"ComfyUI returned error: {error_detail}", file=sys.stderr)
                raise HTTPException(
                    status_code=400, 
                    detail=f"ComfyUI error: {json.dumps(error_detail)}"
                )
            
            prompt_id = result.get('prompt_id')
            
            # Generate a job ID for tracking
            job_id = str(uuid.uuid4())
            
            # Store initial job status
            job_status_store[job_id] = {
                "status": JobStatus.QUEUED.value,
                "prompt_id": prompt_id,
                "created_at": time.time(),
                "updated_at": time.time()
            }
            
            # Start background monitoring
            monitor_thread = threading.Thread(target=monitor_job, args=(job_id, prompt_id))
            monitor_thread.daemon = True
            monitor_thread.start()
            
            return {'id': job_id, 'status': 'QUEUED'}
        elif response.status_code == 400:
            # ComfyUI returned 400 - this is a client error (bad workflow)
            print(f"ComfyUI returned 400 Bad Request", file=sys.stderr)
            print(f"Response body: {response.text[:500]}", file=sys.stderr)
            try:
                error_body = response.json()
                raise HTTPException(
                    status_code=400,
                    detail=f"ComfyUI validation error: {json.dumps(error_body)}"
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"ComfyUI validation error: {response.text[:500]}"
                )
        else:
            # Other non-200 status codes are gateway/server errors
            print(f"ERROR: ComfyUI returned non-200 status: {response.status_code}", file=sys.stderr)
            print(f"Response body: {response.text[:500]}", file=sys.stderr)
            raise HTTPException(
                status_code=502, 
                detail=f"ComfyUI error (HTTP {response.status_code}): {response.text[:500]}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Unhandled exception in /run endpoint:", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post('/runsync')
async def runsync_endpoint(request: Request):
    """
    Sync job submission endpoint.
    Accepts a workflow, submits it to ComfyUI, and waits for completion.
    """
    try:
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            print(f"ERROR: Failed to parse JSON body: {e}", file=sys.stderr)
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        
        print(f"Received /runsync request: {json.dumps(body)[:200]}...")
        
        # Validate input shape
        if not isinstance(body, dict) or 'input' not in body:
            raise HTTPException(status_code=400, detail="'input' is required in request body")
        
        job_input = body.get('input')
        if not isinstance(job_input, dict):
            raise HTTPException(status_code=400, detail="'input' must be an object")

        workflow_name = job_input.get('comfyui_workflow_name', 'video_wan2_2_14B_i2v')
        try:
            workflow = load_workflow_template(workflow_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        print(f"Submitting workflow '{workflow_name}' to ComfyUI (sync): {json.dumps(workflow)[:200]}...")
        
        # Forward to ComfyUI - wrap workflow in 'prompt' key as ComfyUI expects
        comfy_payload = {"prompt": workflow}
        comfy_url = f'{COMFY_API_BASE}/prompt'
        response = requests.post(comfy_url, json=comfy_payload, timeout=30)
        
        print(f"ComfyUI response status (sync): {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"ComfyUI response (sync): {json.dumps(result)[:200]}...")
            except Exception as e:
                print(f"ERROR: Failed to parse ComfyUI JSON response: {e}", file=sys.stderr)
                raise HTTPException(
                    status_code=502, 
                    detail=f"Invalid JSON from ComfyUI: {response.text[:500]}"
                )
            
            # Check for errors in ComfyUI response
            if 'error' in result:
                error_detail = result.get('error')
                print(f"ComfyUI returned error: {error_detail}", file=sys.stderr)
                raise HTTPException(
                    status_code=400, 
                    detail=f"ComfyUI error: {json.dumps(error_detail)}"
                )
            
            prompt_id = result.get('prompt_id')
            return {'status': 'completed', 'prompt_id': prompt_id, 'result': 'test'}
        elif response.status_code == 400:
            # ComfyUI returned 400 - this is a client error (bad workflow)
            print(f"ComfyUI returned 400 Bad Request (sync)", file=sys.stderr)
            print(f"Response body: {response.text[:500]}", file=sys.stderr)
            try:
                error_body = response.json()
                raise HTTPException(
                    status_code=400,
                    detail=f"ComfyUI validation error: {json.dumps(error_body)}"
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"ComfyUI validation error: {response.text[:500]}"
                )
        else:
            # Other non-200 status codes are gateway/server errors
            print(f"ERROR: ComfyUI returned non-200 status: {response.status_code}", file=sys.stderr)
            print(f"Response body: {response.text[:500]}", file=sys.stderr)
            raise HTTPException(
                status_code=502, 
                detail=f"ComfyUI error (HTTP {response.status_code}): {response.text[:500]}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Unhandled exception in /runsync endpoint:", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


def monitor_job(job_id: str, prompt_id: str):
    """
    Background function to monitor ComfyUI job progress and update status.
    """
    try:
        print(f"Starting background monitoring for job {job_id} (prompt {prompt_id})")
        
        # Update status to running
        job_status_store[job_id] = {
            "status": JobStatus.RUNNING.value,
            "prompt_id": prompt_id,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        
        # Poll ComfyUI history endpoint to check job status
        max_attempts = 300  # 5 minutes with 1 second intervals
        for attempt in range(max_attempts):
            try:
                history_url = f'{COMFY_API_BASE}/history/{prompt_id}'
                response = requests.get(history_url, timeout=10)
                
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        prompt_data = history[prompt_id]
                        outputs = prompt_data.get('outputs', {})
                        
                        if outputs:
                            # Job completed successfully
                            print(f"Job {job_id} completed successfully")
                            job_status_store[job_id]["status"] = JobStatus.COMPLETED.value
                            job_status_store[job_id]["updated_at"] = time.time()
                            
                            # Process outputs (similar to runsync endpoint)
                            result_images = []
                            for node_id, node_output in outputs.items():
                                if "images" in node_output:
                                    for image_info in node_output["images"]:
                                        filename = image_info.get("filename")
                                        if filename:
                                            # For now, just return the filename (in production, fetch actual image data)
                                            result_images.append({
                                                "filename": filename,
                                                "type": "filename",  # Simplified for local testing
                                                "data": filename
                                            })
                            
                            job_results[job_id] = {
                                "status": "completed",
                                "output": {"images": result_images}
                            }
                            return
                        else:
                            # Check for execution errors
                            if prompt_data.get('status', {}).get('errors'):
                                error_msg = f"ComfyUI execution error: {prompt_data['status']['errors']}"
                                print(f"Job {job_id} failed: {error_msg}")
                                job_status_store[job_id]["status"] = JobStatus.FAILED.value
                                job_status_store[job_id]["error"] = error_msg
                                job_status_store[job_id]["updated_at"] = time.time()
                                job_results[job_id] = {
                                    "status": "failed",
                                    "error": error_msg
                                }
                                return
                
                # Job still running, continue polling
                time.sleep(1)
                
            except requests.RequestException as e:
                print(f"Error polling job {job_id}: {e}")
                time.sleep(1)
                
        # Job timed out
        print(f"Job {job_id} timed out after {max_attempts} seconds")
        job_status_store[job_id]["status"] = JobStatus.FAILED.value
        job_status_store[job_id]["error"] = "Job timed out"
        job_status_store[job_id]["updated_at"] = time.time()
        job_results[job_id] = {
            "status": "failed",
            "error": "Job timed out"
        }
        
    except Exception as e:
        print(f"Unexpected error monitoring job {job_id}: {e}")
        job_status_store[job_id]["status"] = JobStatus.FAILED.value
        job_status_store[job_id]["error"] = f"Monitoring error: {str(e)}"
        job_status_store[job_id]["updated_at"] = time.time()
        job_results[job_id] = {
            "status": "failed",
            "error": f"Monitoring error: {str(e)}"
        }


@app.get('/status/{job_id}')
async def status_endpoint(job_id: str):
    """
    Get the status of an asynchronous job.
    Returns job status and results if completed.
    """
    try:
        print(f"Status check for job {job_id}")
        
        if job_id not in job_status_store:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job_info = job_status_store[job_id]
        response_data = {
            "id": job_id,
            "status": job_info["status"].upper(),  # Match RunPod format (COMPLETED, FAILED, etc.)
            "created_at": job_info.get("created_at"),
            "updated_at": job_info.get("updated_at")
        }
        
        # Include error if job failed
        if job_info["status"] == JobStatus.FAILED.value and "error" in job_info:
            response_data["error"] = job_info["error"]
        
        # Include output if job completed
        if job_info["status"] == JobStatus.COMPLETED.value and job_id in job_results:
            response_data["output"] = job_results[job_id].get("output")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Unhandled exception in /status endpoint:", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")


@app.get('/health')
async def health_endpoint():
    """
    Health check endpoint.
    Verifies that ComfyUI is accessible and responding.
    """
    try:
        print("Health check: Checking ComfyUI connectivity...")
        response = requests.get(f'{COMFY_API_BASE}/system_stats', timeout=5)
        
        print(f"Health check response status: {response.status_code}")
        
        if response.status_code == 200:
            return {'status': 'healthy', 'comfyui': 'connected'}
        else:
            print(f"ERROR: ComfyUI health check failed with status {response.status_code}", file=sys.stderr)
            raise HTTPException(
                status_code=503, 
                detail=f"ComfyUI health check failed (HTTP {response.status_code})"
            )
    
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to connect to ComfyUI: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=503, 
            detail=f"ComfyUI disconnected: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Unhandled exception in /health endpoint:", file=sys.stderr)
        print(error_trace, file=sys.stderr)
        raise HTTPException(status_code=503, detail=f"Health check error: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch any unhandled exceptions.
    """
    error_trace = traceback.format_exc()
    print(f"ERROR: Unhandled exception:", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


if __name__ == '__main__':
    print("Starting RunPod API server on http://0.0.0.0:3000")
    print(f"ComfyUI API base: {COMFY_API_BASE}")
    uvicorn.run(app, host='0.0.0.0', port=3000, log_level="info")
