"""
Input schema for RunPod serverless ComfyUI worker validation.
"""

INPUT_SCHEMA = {
    'workflow': {
        'type': dict,
        'required': True,
        'constraints': lambda workflow: isinstance(workflow, dict) and workflow
    },
    'images': {
        'type': list,
        'required': False,
        'default': []
    },
    'comfy_org_api_key': {
        'type': str,
        'required': False,
        'default': ''
    }
}
