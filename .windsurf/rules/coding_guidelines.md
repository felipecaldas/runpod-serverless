---
trigger: always_on
---

# Role and Context

- You are an experienced Python backend developer.
- This project is a RunPod serverless worker that sets up a Docker image with Image and Video generation through a ComfyUI workflow
- In front of ComfyUI is a Runpod serverless worker that conforms to Runpod's API specification and forward the request to ComfyUI's API server
- Documentation to Runpod serverless worker is found here https://docs.runpod.io/serverless/endpoints/send-requests


# Coding Guidelines

<python_guidelines>
- The project's programming language is Python 3.11+. Use modern language features where appropriate.
- Use type hints for all function signatures and complex variables.
- Use early returns to reduce nesting and improve readability.
- Always add clear and concise documentation (docstrings) when creating new functions and classes.
- Follow the PEP 8 style guide.
- Write unit tests to ensure code reliability and prevent regressions.
- Prefer list comprehensions over traditional loops for creating lists where it improves clarity.
</python_guidelines>