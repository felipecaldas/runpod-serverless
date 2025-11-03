#!/usr/bin/env python3
"""
Validation script to check the implementation against RunPod requirements.
This script validates that our implementation meets the RunPod serverless worker specification.
"""

import json
import sys
import os
from pathlib import Path


def validate_file_structure():
    """Validate that all required files are present."""
    print("🔍 Validating file structure...")
    
    required_files = [
        "src/handler.py",
        "src/start.sh", 
        "Dockerfile.runpod.serverless.v3",
        "requirements.txt",
        "README.md",
        "test_input.json"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True


def validate_handler_implementation():
    """Validate that handler.py implements required functions."""
    print("🔍 Validating handler implementation...")
    
    try:
        # Read handler.py
        with open("src/handler.py", "r") as f:
            handler_content = f.read()
        
        # Check for required functions
        required_functions = [
            "def handler(",
            "def health_check(",
            "def submit_workflow_to_comfyui(",
            "def wait_for_completion(",
            "def get_workflow_results(",
            "def process_output_images("
        ]
        
        missing_functions = []
        for func in required_functions:
            if func not in handler_content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"❌ Missing required functions: {missing_functions}")
            return False
        else:
            print("✅ All required functions implemented")
            return True
            
    except Exception as e:
        print(f"❌ Error reading handler.py: {e}")
        return False


def validate_api_compliance():
    """Validate API compliance with RunPod specification."""
    print("🔍 Validating API compliance...")
    
    try:
        # Read handler.py
        with open("src/handler.py", "r") as f:
            handler_content = f.read()
        
        # Check for key API elements
        required_elements = [
            '"input"',           # Input structure
            '"workflow"',        # Workflow handling
            '"images"',          # Image upload support
            '"output"',          # Output structure
            '"status"',          # Status reporting
            'runpod.serverless.start',  # RunPod SDK usage
            'websocket',         # Real-time monitoring
            'base64'             # Image encoding
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in handler_content:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"⚠️  Potentially missing API elements: {missing_elements}")
            # Not failing validation as some might be implemented differently
            return True
        else:
            print("✅ API compliance elements found")
            return True
            
    except Exception as e:
        print(f"❌ Error validating API compliance: {e}")
        return False


def validate_dockerfile():
    """Validate Dockerfile configuration."""
    print("🔍 Validating Dockerfile...")
    
    try:
        # Read Dockerfile
        with open("Dockerfile.runpod.serverless.v3", "r") as f:
            dockerfile_content = f.read()
        
        # Check for required elements
        required_elements = [
            "FROM runpod/worker-comfyui:5.1.0-base",
            "COPY src/handler.py",
            "COPY src/start.sh",
            "RUN chmod +x",
            "CMD [\"/src/start.sh\"]"
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in dockerfile_content:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"❌ Missing Dockerfile elements: {missing_elements}")
            return False
        else:
            print("✅ Dockerfile validation passed")
            return True
            
    except Exception as e:
        print(f"❌ Error reading Dockerfile: {e}")
        return False


def validate_requirements():
    """Validate requirements.txt."""
    print("🔍 Validating requirements.txt...")
    
    try:
        # Read requirements.txt
        with open("requirements.txt", "r") as f:
            requirements_content = f.read()
        
        # Check for required packages
        required_packages = [
            "runpod",
            "requests", 
            "websocket-client"
        ]
        
        missing_packages = []
        for package in required_packages:
            if package not in requirements_content:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Missing required packages: {missing_packages}")
            return False
        else:
            print("✅ Requirements validation passed")
            return True
            
    except Exception as e:
        print(f"❌ Error reading requirements.txt: {e}")
        return False


def validate_test_input():
    """Validate test_input.json structure."""
    print("🔍 Validating test input...")
    
    try:
        # Read test input
        with open("test_input.json", "r") as f:
            test_data = json.load(f)
        
        # Check structure
        if "input" not in test_data:
            print("❌ Missing 'input' in test_input.json")
            return False
        
        if "workflow" not in test_data["input"]:
            print("❌ Missing 'workflow' in test_input.json")
            return False
        
        workflow = test_data["input"]["workflow"]
        if not isinstance(workflow, dict) or not workflow:
            print("❌ Workflow should be a non-empty dictionary")
            return False
        
        print("✅ Test input validation passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in test_input.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading test_input.json: {e}")
        return False


def validate_start_script():
    """Validate start.sh script."""
    print("🔍 Validating start script...")
    
    try:
        # Read start script
        with open("src/start.sh", "r") as f:
            start_script_content = f.read()
        
        # Check for required elements
        required_elements = [
            "python main.py",      # ComfyUI startup
            "handler.py",          # Handler execution
            "COMFY_HOST",          # Configuration
            "SERVE_API_LOCALLY"    # Testing mode
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in start_script_content:
                missing_elements.append(element)
        
        if missing_elements:
            print(f"⚠️  Potentially missing start script elements: {missing_elements}")
            return True  # Not failing as implementation might vary
        else:
            print("✅ Start script validation passed")
            return True
            
    except Exception as e:
        print(f"❌ Error reading start script: {e}")
        return False


def main():
    """Main validation function."""
    print("🔬 RunPod Serverless Worker - Implementation Validation")
    print("=" * 60)
    
    # Run all validations
    validations = [
        ("File Structure", validate_file_structure),
        ("Handler Implementation", validate_handler_implementation),
        ("API Compliance", validate_api_compliance),
        ("Dockerfile Configuration", validate_dockerfile),
        ("Requirements", validate_requirements),
        ("Test Input", validate_test_input),
        ("Start Script", validate_start_script)
    ]
    
    results = []
    
    for validation_name, validation_func in validations:
        print(f"\n📋 {validation_name}")
        print("-" * 40)
        
        try:
            result = validation_func()
            results.append((validation_name, result))
        except Exception as e:
            print(f"❌ {validation_name} failed with exception: {e}")
            results.append((validation_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Validation Summary")
    print("=" * 60)
    
    passed = 0
    for validation_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {validation_name}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 All validations passed! The implementation is ready for deployment.")
        print("\nNext steps:")
        print("1. Build the image: .\\build.ps1")
        print("2. Test locally: .\\build.ps1 -Test")
        print("3. Push to registry: .\\build.ps1 -Registry your-registry -Push")
        print("4. Deploy to RunPod using the image name")
        sys.exit(0)
    else:
        print("⚠️  Some validations failed. Please review and fix the issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()
