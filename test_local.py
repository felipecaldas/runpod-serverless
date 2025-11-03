#!/usr/bin/env python3
"""
Test script for local development and validation of the RunPod serverless worker.
This script simulates RunPod API calls to test the handler implementation.
"""

import json
import requests
import time
import sys
from pathlib import Path


def load_test_workflow():
    """Load the test workflow from test_input.json."""
    try:
        with open("test_input.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: test_input.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing test_input.json: {e}")
        sys.exit(1)


def test_health_endpoint(base_url="http://localhost:3000"):
    """Test the health check endpoint."""
    try:
        print("Testing health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health check passed: {health_data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check error: {e}")
        return False


def test_sync_endpoint(base_url="http://localhost:3000"):
    """Test the synchronous workflow execution endpoint."""
    try:
        print("Testing sync endpoint...")
        workflow_data = load_test_workflow()
        
        print("Submitting workflow...")
        start_time = time.time()
        
        response = requests.post(
            f"{base_url}/runsync",
            json=workflow_data,
            timeout=300  # 5 minute timeout
        )
        
        execution_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Sync execution completed in {execution_time:.2f}s")
            print(f"Status: {result.get('status')}")
            print(f"Job ID: {result.get('id')}")
            
            # Check for output images
            output = result.get("output", {})
            images = output.get("images", [])
            
            if images:
                print(f"Generated {len(images)} image(s):")
                for img in images:
                    print(f"  - {img.get('filename')} ({img.get('type')})")
                    if img.get('type') == 'base64':
                        # Show first 50 chars of base64 data
                        data_preview = img.get('data', '')[:50] + '...'
                        print(f"    Data preview: {data_preview}")
                    else:
                        print(f"    URL: {img.get('data')}")
            else:
                print("⚠️  No images generated")
            
            # Check for errors
            errors = output.get("errors", [])
            if errors:
                print("⚠️  Errors reported:")
                for error in errors:
                    print(f"  - {error}")
            
            return True
            
        else:
            print(f"❌ Sync execution failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Sync execution error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON response: {e}")
        return False


def test_async_endpoint(base_url="http://localhost:3000"):
    """Test the asynchronous workflow execution endpoint."""
    try:
        print("Testing async endpoint...")
        workflow_data = load_test_workflow()
        
        print("Submitting workflow...")
        response = requests.post(
            f"{base_url}/run",
            json=workflow_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("id")
            
            if job_id:
                print(f"✅ Async job submitted: {job_id}")
                print("Note: Full async testing would require polling /status endpoint")
                return True
            else:
                print("❌ No job ID returned")
                return False
                
        else:
            print(f"❌ Async submission failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Async submission error: {e}")
        return False


def wait_for_server(base_url="http://localhost:3000", max_wait=60):
    """Wait for the server to be ready."""
    print(f"Waiting for server at {base_url}...")
    
    for i in range(max_wait):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"Attempt {i+1}/{max_wait}: Server not ready yet...")
        time.sleep(1)
    
    print("❌ Server failed to start within expected time")
    return False


def main():
    """Main test function."""
    print("🧪 RunPod Serverless Worker - Local Test Suite")
    print("=" * 50)
    
    base_url = "http://localhost:3000"
    
    # Check if server is running
    if not wait_for_server(base_url):
        print("\n💡 Make sure the server is running with:")
        print("   docker run -e SERVE_API_LOCALLY=true -p 3000:3000 your-image")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    
    # Run tests
    tests = [
        ("Health Check", test_health_endpoint),
        ("Async Submission", test_async_endpoint),
        ("Sync Execution", test_sync_endpoint),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        print("-" * 30)
        
        try:
            result = test_func(base_url)
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 All tests passed! The implementation is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
