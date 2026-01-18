## .\build_custom.ps1 -ImageName "fcaldas/tabario.com" -ImageTag "1.5"
param(
    [string]$ImageName = "fcaldas/tabario.com",
    [string]$ImageTag = "1.4",
    [string]$Dockerfile = "Dockerfile.custom"
)

$ErrorActionPreference = "Stop"

Write-Host "Building custom ComfyUI RunPod serverless worker (CUDA base + optimizations)..."
Write-Host "Building image: $ImageName`:$ImageTag"
Write-Host "Using Dockerfile: $Dockerfile"

python "scripts\normalize_line_endings.py"
if ($LASTEXITCODE -ne 0) {
    throw "Line-ending normalization failed"
}

$buildArgs = @(
    "--build-arg", "GGUF_REF=main",
    "--build-arg", "VFI_REF=main",
    "--build-arg", "VHS_REF=main"
)

docker build `
    --platform linux/amd64 `
    -f $Dockerfile `
    -t "${ImageName}:${ImageTag}" `
    @buildArgs `
    .

Write-Host "Build completed successfully!"
