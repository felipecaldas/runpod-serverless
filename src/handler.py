"""
Enhanced RunPod serverless worker handler for ComfyUI.
Combines official worker-comfyui architecture with our optimizations.

Features:
- Robust validation and error handling
- Advanced logging and telemetry
- Resource monitoring (memory, disk, CPU)
- Runtime model downloads support
- Production-grade reliability
"""

import os
import shutil
import time
import requests
import traceback
import json
import base64
import uuid
import logging
import logging.handlers
from io import BytesIO
import runpod
from runpod.serverless.utils.rp_validator import validate
from runpod.serverless.modules.rp_logger import RunPodLogger
from requests.adapters import HTTPAdapter, Retry
from typing import Dict, Any, List, Optional
import tempfile
import socket
import websocket
from PIL import Image


# Configuration constants
APP_NAME = 'runpod-serverless-comfyui'
BASE_URI = 'http://127.0.0.1:8188'  # ComfyUI default port
LOG_FILE = 'comfyui-worker.log'
TIMEOUT = 600
LOG_LEVEL = 'INFO'
DISK_MIN_FREE_BYTES = 500 * 1024 * 1024  # 500MB in bytes
COMFY_API_AVAILABLE_INTERVAL_MS = 50
COMFY_API_AVAILABLE_MAX_RETRIES = 500
WEBSOCKET_RECONNECT_ATTEMPTS = int(os.environ.get("WEBSOCKET_RECONNECT_ATTEMPTS", 5))
WEBSOCKET_RECONNECT_DELAY_S = int(os.environ.get("WEBSOCKET_RECONNECT_DELAY_S", 3))

# Enable websocket trace if requested
if os.environ.get("WEBSOCKET_TRACE", "false").lower() == "true":
    websocket.enableTrace(True)

# Input schema for validation
INPUT_SCHEMA = {
    'prompt': {
        'type': str,
        'required': True,
        'constraints': lambda prompt: isinstance(prompt, str) and len(prompt) > 0
    },
    'image': {
        'type': str,
        'required': True,
        'constraints': lambda image: isinstance(image, str) and len(image) > 0
    },
    'width': {
        'type': int,
        'required': False,
        'default': 480
    },
    'height': {
        'type': int,
        'required': False,
        'default': 640
    },
    'length': {
        'type': int,
        'required': False,
        'default': 81
    },
    'comfy_org_api_key': {
        'type': str,
        'required': False
    }
}


# ---------------------------------------------------------------------------- #
#                               Custom Log Handler                             #
# ---------------------------------------------------------------------------- #
class SnapLogHandler(logging.Handler):
    """Enhanced log handler with RunPod integration and external API support."""
    
    def __init__(self, app_name: str):
        super().__init__()
        self.app_name = app_name
        self.rp_logger = RunPodLogger()
        self.rp_logger.set_level(LOG_LEVEL)
        
        # RunPod environment variables
        self.runpod_endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID')
        self.runpod_cpu_count = os.getenv('RUNPOD_CPU_COUNT')
        self.runpod_pod_id = os.getenv('RUNPOD_POD_ID')
        self.runpod_gpu_size = os.getenv('RUNPOD_GPU_SIZE')
        self.runpod_mem_gb = os.getenv('RUNPOD_MEM_GB')
        self.runpod_gpu_count = os.getenv('RUNPOD_GPU_COUNT')
        self.runpod_pod_hostname = os.getenv('RUNPOD_POD_HOSTNAME')
        self.runpod_debug_level = os.getenv('RUNPOD_DEBUG_LEVEL')
        self.runpod_dc_id = os.getenv('RUNPOD_DC_ID')
        self.runpod_gpu_name = os.getenv('RUNPOD_GPU_NAME')
        
        # External logging configuration
        self.log_api_endpoint = os.getenv('LOG_API_ENDPOINT')
        self.log_api_timeout = os.getenv('LOG_API_TIMEOUT', 5)
        self.log_api_timeout = int(self.log_api_timeout)
        self.log_token = os.getenv('LOG_API_TOKEN')

    def emit(self, record):
        """Emit a log record to both RunPod logger and external API if configured."""
        runpod_job_id = os.getenv('RUNPOD_JOB_ID')

        try:
            # Handle string formatting and extra arguments
            if hasattr(record, 'msg') and hasattr(record, 'args'):
                if record.args:
                    try:
                        if isinstance(record.args, dict):
                            message = record.msg % record.args if '%' in str(record.msg) else str(record.msg)
                        else:
                            message = str(record.msg) % record.args if '%' in str(record.msg) else str(record.msg)
                    except (TypeError, ValueError):
                        message = str(record.msg)
                else:
                    message = str(record.msg)
            else:
                message = str(record)

            # Only log to RunPod logger if the length is reasonable
            if len(message) <= 1000:
                level_mapping = {
                    logging.DEBUG: self.rp_logger.debug,
                    logging.INFO: self.rp_logger.info,
                    logging.WARNING: self.rp_logger.warn,
                    logging.ERROR: self.rp_logger.error,
                    logging.CRITICAL: self.rp_logger.error
                }

                rp_logger = level_mapping.get(record.levelno, self.rp_logger.info)

                if runpod_job_id:
                    rp_logger(message, runpod_job_id)
                else:
                    rp_logger(message)

            # Send to external logging API if configured
            if self.log_api_endpoint:
                try:
                    headers = {'Authorization': f'Bearer {self.log_token}'}

                    log_payload = {
                        'app_name': self.app_name,
                        'log_asctime': self.formatter.formatTime(record),
                        'log_levelname': record.levelname,
                        'log_message': message,
                        'runpod_endpoint_id': self.runpod_endpoint_id,
                        'runpod_pod_id': self.runpod_pod_id,
                        'runpod_job_id': runpod_job_id,
                        'runpod_gpu_size': self.runpod_gpu_size,
                        'runpod_mem_gb': self.runpod_mem_gb,
                        'runpod_gpu_count': self.runpod_gpu_count,
                        'runpod_gpu_name': self.runpod_gpu_name,
                        'runpod_pod_hostname': self.runpod_pod_hostname,
                    }

                    requests.post(
                        self.log_api_endpoint,
                        headers=headers,
                        json=log_payload,
                        timeout=self.log_api_timeout
                    )
                except Exception as e:
                    # Don't let logging failures break the main application
                    print(f"Failed to send log to external API: {str(e)}")

        except Exception as e:
            print(f"Logging error: {str(e)}")


# ---------------------------------------------------------------------------- #
#                              Telemetry functions                             #
# ---------------------------------------------------------------------------- #
def get_container_memory_info(job_id=None):
    """Get memory information using cgroups. Returns stats in GB."""
    try:
        mem_info = {}

        # Try host memory info as fallback
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.readlines()

            for line in meminfo:
                if 'MemTotal:' in line:
                    mem_info['total'] = int(line.split()[1]) / (1024 * 1024)
                elif 'MemAvailable:' in line:
                    mem_info['available'] = int(line.split()[1]) / (1024 * 1024)
                elif 'MemFree:' in line:
                    mem_info['free'] = int(line.split()[1]) / (1024 * 1024)

            if 'total' in mem_info and 'free' in mem_info:
                mem_info['used'] = mem_info['total'] - mem_info['free']
        except Exception as e:
            logging.warning(f"Failed to read host memory info: {str(e)}", job_id)

        # Try cgroups v2 path first (modern Docker)
        try:
            with open('/sys/fs/cgroup/memory.max', 'r') as f:
                max_mem = f.read().strip()
                if max_mem != 'max':
                    mem_info['limit'] = int(max_mem) / (1024 * 1024 * 1024)

            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                mem_info['used'] = int(f.read().strip()) / (1024 * 1024 * 1024)

        except FileNotFoundError:
            # Fall back to cgroups v1 paths (older Docker)
            try:
                with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                    mem_limit = int(f.read().strip())
                    if mem_limit < 2**63:
                        mem_info['limit'] = mem_limit / (1024 * 1024 * 1024)

                with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                    mem_info['used'] = int(f.read().strip()) / (1024 * 1024 * 1024)

            except FileNotFoundError:
                pass  # Use host memory info as fallback

        return mem_info

    except Exception as e:
        logging.error(f"Error getting memory info: {str(e)}", job_id)
        return {}


def get_container_cpu_info(job_id=None):
    """Get CPU information using cgroups."""
    try:
        cpu_info = {}

        # Try cgroups v2 path first
        try:
            with open('/sys/fs/cgroup/cpu.max', 'r') as f:
                cpu_max = f.read().strip()
                if cpu_max != 'max':
                    quota, period = cpu_max.split()
                    cpu_info['limit'] = int(quota) / int(period)
                else:
                    cpu_info['limit'] = os.cpu_count()

            with open('/sys/fs/cgroup/cpu.stat', 'r') as f:
                for line in f:
                    if line.startswith('usage_usec '):
                        cpu_info['usage_usec'] = int(line.split()[1])
                        break

        except FileNotFoundError:
            # Fall back to cgroups v1 paths
            try:
                with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as f:
                    quota = int(f.read().strip())
                    if quota > 0:
                        with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as f:
                            period = int(f.read().strip())
                            cpu_info['limit'] = quota / period
                    else:
                        cpu_info['limit'] = os.cpu_count()

            except FileNotFoundError:
                cpu_info['limit'] = os.cpu_count()

        return cpu_info

    except Exception as e:
        logging.error(f"Error getting CPU info: {str(e)}", job_id)
        return {'limit': os.cpu_count()}


def get_container_disk_info(job_id=None):
    """Get disk information for the container."""
    try:
        disk_info = {}
        stat = os.statvfs('/')

        disk_info['total'] = stat.f_frsize * stat.f_blocks
        disk_info['free'] = stat.f_frsize * stat.f_bavail
        disk_info['used'] = disk_info['total'] - disk_info['free']

        return disk_info

    except Exception as e:
        logging.error(f"Error getting disk info: {str(e)}", job_id)
        return {}


# ---------------------------------------------------------------------------- #
#                           HTTP Session Management                            #
# ---------------------------------------------------------------------------- #
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)


def send_get_request(endpoint):
    """Send GET request to ComfyUI with retry logic."""
    return session.get(
        url=f'{BASE_URI}/{endpoint}',
        timeout=TIMEOUT
    )


def send_post_request(endpoint, payload):
    """Send POST request to ComfyUI with retry logic."""
    return session.post(
        url=f'{BASE_URI}/{endpoint}',
        json=payload,
        timeout=TIMEOUT
    )


# ---------------------------------------------------------------------------- #
#                           ComfyUI Helper Functions                           #
# ---------------------------------------------------------------------------- #
def check_server(url, retries=500, delay=50):
    """Check if ComfyUI server is reachable."""
    logging.info(f"Checking ComfyUI server at {url}")
    
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logging.info("ComfyUI server is reachable")
                return True
        except requests.RequestException:
            pass

        time.sleep(delay / 1000)

    logging.error(f"Failed to connect to ComfyUI server after {retries} attempts")
    return False


def upload_image_to_comfyui(image_data_uri: str, job_id: str, width: int, height: int) -> str:
    """Upload a single base64 image to ComfyUI and return the uploaded filename.

    The image will be resized to the requested width/height to match Wan I2V requirements.
    """
    try:
        # Strip data URI prefix if present
        if "," in image_data_uri:
            base64_data = image_data_uri.split(",", 1)[1]
        else:
            base64_data = image_data_uri

        blob = base64.b64decode(base64_data)
        image = Image.open(BytesIO(blob)).convert("RGB")

        if image.size != (width, height):
            logging.info(
                f"Resizing input image from {image.size[0]}x{image.size[1]} to {width}x{height}",
                job_id
            )
            image = image.resize((width, height), Image.LANCZOS)

        # Generate unique filename
        filename = f"{uuid.uuid4()}.png"

        # Use temporary file approach
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            image.save(temp_file, format="PNG")
            temp_file_path = temp_file.name

        try:
            with open(temp_file_path, 'rb') as f:
                files = {"image": (filename, f, "image/png"), "overwrite": (None, "true")}
                response = requests.post(f"{BASE_URI}/upload/image", files=files, timeout=30)
                response.raise_for_status()

            logging.info(f"Successfully uploaded image as {filename}", job_id)
            return filename

        finally:
            os.unlink(temp_file_path)

    except Exception as e:
        error_msg = f"Error uploading image: {e}"
        logging.error(error_msg, job_id)
        raise Exception(error_msg)


def create_unique_filename_prefix(workflow):
    """Add unique filename prefix to prevent race conditions."""
    for key, value in workflow.items():
        class_type = value.get('class_type')
        if class_type == 'SaveImage':
            workflow[key]['inputs']['filename_prefix'] = str(uuid.uuid4())


def get_image_data(filename, subfolder, image_type):
    """Get image data from ComfyUI view endpoint."""
    try:
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": image_type
        }
        
        response = requests.get(f"{BASE_URI}/view", params=params, timeout=30)
        response.raise_for_status()
        
        return response.content
        
    except Exception as e:
        logging.error(f"Error getting image data for {filename}: {str(e)}")
        raise


def process_output_images(outputs, job_id):
    """Process output images from ComfyUI workflow results."""
    output_images = []
    
    try:
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for image_info in node_output["images"]:
                    filename = image_info.get("filename")
                    subfolder = image_info.get("subfolder", "")
                    image_type = image_info.get("type", "output")
                    
                    if not filename or image_type == "temp":
                        continue
                    
                    # Get image data
                    image_bytes = get_image_data(filename, subfolder, image_type)
                    
                    # Check if S3 upload is configured
                    if os.environ.get("BUCKET_ENDPOINT_URL"):
                        # Upload to S3
                        s3_url = upload_to_s3(image_bytes, filename, job_id)
                        output_images.append({
                            "filename": filename,
                            "type": "s3_url",
                            "data": s3_url
                        })
                    else:
                        # Return as base64
                        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                        output_images.append({
                            "filename": filename,
                            "type": "base64",
                            "data": image_b64
                        })
        
        logging.info(f"Processed {len(output_images)} output images")
        return output_images
        
    except Exception as e:
        logging.error(f"Error processing output images: {str(e)}")
        raise


def upload_to_s3(image_data, filename, job_id):
    """Upload image to S3 using RunPod's upload utility."""
    try:
        from runpod.serverless.utils import rp_upload
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name
        
        try:
            s3_url = rp_upload.upload_image(job_id, temp_file_path)
            logging.info(f"Uploaded {filename} to S3: {s3_url}")
            return s3_url
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        logging.error(f"Error uploading {filename} to S3: {str(e)}")
        raise


# ---------------------------------------------------------------------------- #
#                                Main Handler                                   #
# ---------------------------------------------------------------------------- #
def load_workflow_template() -> Dict[str, Any]:
    """Load the I2V workflow template from disk."""
    template_path = '/workflows/I2V-Wan-2.2-Lightning-runpod.json'
    try:
        with open(template_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Workflow template not found at {template_path}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in workflow template: {e}")


def substitute_workflow_placeholders(workflow: Dict[str, Any], prompt: str, image_filename: str) -> Dict[str, Any]:
    """Replace {{ VIDEO_PROMPT }} and {{ INPUT_IMAGE }} placeholders in workflow."""
    workflow_str = json.dumps(workflow)
    workflow_str = workflow_str.replace('{{ VIDEO_PROMPT }}', prompt)
    workflow_str = workflow_str.replace('{{ INPUT_IMAGE }}', image_filename)
    return json.loads(workflow_str)


def set_workflow_dimensions(workflow: Dict[str, Any], width: int, height: int, length: int) -> None:
    """Set dimensions in WanImageToVideo node."""
    for _, node in workflow.items():
        if isinstance(node, dict) and node.get('class_type') == 'WanImageToVideo':
            inputs = node.get('inputs', {})
            inputs['width'] = width
            inputs['height'] = height
            inputs['length'] = length
            logging.info(f"Set workflow dimensions: {width}x{height}, length={length}")
            return
    raise ValueError("WanImageToVideo node not found in workflow template")


def handler(event):
    """Main RunPod handler function with enhanced error handling and monitoring."""
    job_id = event['id']
    os.environ['RUNPOD_JOB_ID'] = job_id

    try:
        # Resource monitoring and validation
        logging.info(f"Starting job {job_id}")
        
        memory_info = get_container_memory_info(job_id)
        cpu_info = get_container_cpu_info(job_id)
        disk_info = get_container_disk_info(job_id)

        memory_available_gb = memory_info.get('available')
        disk_free_bytes = disk_info.get('free_bytes')

        # Resource checks
        if memory_available_gb is not None and memory_available_gb < 0.5:
            raise Exception(f'Insufficient available container memory: {memory_available_gb:.2f} GB available (minimum 0.5 GB required)')

        if disk_free_bytes is not None and disk_free_bytes < DISK_MIN_FREE_BYTES:
            free_gb = disk_free_bytes / (1024**3)
            raise Exception(f'Insufficient free container disk space: {free_gb:.2f} GB available (minimum 0.5 GB required)')

        # Input validation
        validated_input = validate(event['input'], INPUT_SCHEMA)
        if 'errors' in validated_input:
            return {
                'error': '\n'.join(validated_input['errors'])
            }

        job_input = validated_input['validated_input']
        prompt = job_input['prompt']
        image_b64 = job_input['image']
        width = job_input.get('width', 480)
        height = job_input.get('height', 640)
        length = job_input.get('length', 81)
        comfy_org_api_key = job_input.get('comfy_org_api_key')

        logging.info(f"Processing I2V workflow: prompt='{prompt[:50]}...', dimensions={width}x{height}, length={length}", job_id)

        # Set Comfy.org API key if provided
        if comfy_org_api_key:
            os.environ["COMFY_ORG_API_KEY"] = comfy_org_api_key

        # Ensure ComfyUI is ready
        if not check_server(BASE_URI, COMFY_API_AVAILABLE_MAX_RETRIES, COMFY_API_AVAILABLE_INTERVAL_MS):
            raise Exception("ComfyUI server is not ready")

        # Upload input image to ComfyUI
        logging.info("Uploading input image to ComfyUI", job_id)
        uploaded_filename = upload_image_to_comfyui(image_b64, job_id, width, height)

        # Load workflow template
        logging.info("Loading I2V workflow template", job_id)
        workflow = load_workflow_template()

        # Substitute placeholders
        logging.info("Substituting workflow placeholders", job_id)
        workflow = substitute_workflow_placeholders(workflow, prompt, uploaded_filename)

        # Set dimensions
        set_workflow_dimensions(workflow, width, height, length)

        # Add unique filename prefix to prevent race conditions
        create_unique_filename_prefix(workflow)

        # Submit workflow to ComfyUI
        logging.info("Queuing workflow to ComfyUI", job_id)
        queue_response = send_post_request('prompt', {'prompt': workflow})

        if queue_response.status_code == 200:
            resp_json = queue_response.json()
            prompt_id = resp_json['prompt_id']
            logging.info(f"Workflow queued successfully: {prompt_id}", job_id)

            # Wait for completion using websocket (more efficient than polling)
            result = monitor_workflow_with_websocket(prompt_id, job_id)
            
            if 'error' in result:
                return result

            # Process outputs
            outputs = result.get('outputs', {})
            if outputs:
                logging.info(f"Images generated successfully for prompt: {prompt_id}", job_id)
                output_images = process_output_images(outputs, job_id)
                
                return {
                    "output": {
                        "images": output_images
                    }
                }
            else:
                return {
                    "output": {
                        "images": []
                    }
                }
        else:
            raise Exception(f"Failed to queue workflow: {queue_response.text}")

    except Exception as e:
        error_msg = f"Handler error: {str(e)}"
        logging.error(error_msg, job_id)
        logging.error(traceback.format_exc(), job_id)
        
        return {
            "error": error_msg
        }


def monitor_workflow_with_websocket(prompt_id, job_id):
    """Monitor workflow execution using ComfyUI websocket API."""
    client_id = str(uuid.uuid4())
    ws_url = f"ws://127.0.0.1:8188/ws?clientId={client_id}"
    
    try:
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        logging.info(f"Connected to ComfyUI websocket for job {job_id}")
        
        while True:
            try:
                message = ws.recv()
                data = json.loads(message)
                
                # Handle different message types
                if data.get("type") == "executing":
                    data_content = data.get("data", {})
                    if data_content.get("prompt_id") == prompt_id:
                        if data_content.get("node") is None:
                            # Execution completed
                            logging.info(f"Workflow completed for prompt: {prompt_id}", job_id)
                            break
                        else:
                            logging.debug(f"Executing node: {data_content.get('node')}", job_id)
                
                elif data.get("type") == "execution_error":
                    data_content = data.get("data", {})
                    if data_content.get("prompt_id") == prompt_id:
                        error_details = f"Node Type: {data_content.get('node_type')}, Node ID: {data_content.get('node_id')}, Message: {data_content.get('exception_message')}"
                        logging.error(f"Workflow execution error: {error_details}", job_id)
                        return {"error": f"Workflow execution error: {error_details}"}
                
            except websocket.WebSocketTimeoutException:
                logging.debug("Websocket receive timed out, continuing...", job_id)
                continue
            except websocket.WebSocketConnectionClosedException:
                logging.warning("Websocket connection closed, attempting to reconnect...", job_id)
                try:
                    ws = websocket.WebSocket()
                    ws.connect(ws_url)
                    logging.info("Websocket reconnected successfully", job_id)
                    continue
                except Exception as reconnect_error:
                    logging.error(f"Failed to reconnect websocket: {reconnect_error}", job_id)
                    return {"error": f"Websocket connection lost: {reconnect_error}"}
        
        ws.close()
        
        # Get final results
        history_response = send_get_request(f'history/{prompt_id}')
        if history_response.status_code == 200:
            history = history_response.json()
            if prompt_id in history:
                return history[prompt_id]
        
        return {"error": f"No history found for completed prompt: {prompt_id}"}
        
    except Exception as e:
        logging.error(f"Websocket monitoring error: {str(e)}", job_id)
        return {"error": f"Monitoring error: {str(e)}"}


# ---------------------------------------------------------------------------- #
#                                Logging Setup                                 #
# ---------------------------------------------------------------------------- #
def setup_logging():
    """Setup enhanced logging with custom handler."""
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add custom handler
    custom_handler = SnapLogHandler(APP_NAME)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    custom_handler.setFormatter(formatter)
    logger.addHandler(custom_handler)
    
    # Also add console handler for local development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Initialize logging
logger = setup_logging()


# ---------------------------------------------------------------------------- #
#                                   Entry Point                                 #
# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    print(f"Starting {APP_NAME}...")
    
    # Log system information
    logger.info("Worker initialization started")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"RunPod SDK version: {runpod.__version__}")
    
    # Start the RunPod serverless worker
    runpod.serverless.start({"handler": handler})
