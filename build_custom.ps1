## Option B build (base + app) for Docker Desktop on Windows.
##
## Base image (rare rebuild):
##   .\build_custom.ps1 -Target base -ImageName "fcaldas/tabario.com" -BaseImageTag "base-1.0" -Push
##
## App image (frequent rebuild for python-only changes):
##   .\build_custom.ps1 -Target app -ImageName "fcaldas/tabario.com" -BaseImageTag "base-1.0" -ImageTag "1.5.0" -Push
##
## Both:
##   .\build_custom.ps1 -Target both -ImageName "fcaldas/tabario.com" -BaseImageTag "base-1.0" -ImageTag "1.5.0" -Push
param(
    [string]$ImageName = "fcaldas/tabario.com",
    [string]$ImageTag = "1.5.0",
    [string]$BaseImageTag = "base-1.0",
    [ValidateSet("app", "base", "both")]
    [string]$Target = "app",
    [switch]$Push
)

$ErrorActionPreference = "Stop"

Write-Host "Building ComfyUI RunPod serverless worker images (Option B base/app split)..."
Write-Host "App image:  $ImageName`:$ImageTag"
Write-Host "Base image: $ImageName`:$BaseImageTag"

python "scripts\normalize_line_endings.py"
if ($LASTEXITCODE -ne 0) {
    throw "Line-ending normalization failed"
}

$baseBuildArgs = @(
    "--build-arg", "GGUF_REF=main",
    "--build-arg", "VFI_REF=main",
    "--build-arg", "VHS_REF=main"
)

if ($Target -eq "base" -or $Target -eq "both") {
    docker build `
        --platform linux/amd64 `
        -f "Dockerfile.base" `
        -t "${ImageName}:${BaseImageTag}" `
        @baseBuildArgs `
        .

    if ($Push) {
        docker push "${ImageName}:${BaseImageTag}"
    }
}

if ($Target -eq "app" -or $Target -eq "both") {
    docker build `
        --platform linux/amd64 `
        -f "Dockerfile.app" `
        --build-arg "BASE_IMAGE=${ImageName}:${BaseImageTag}" `
        -t "${ImageName}:${ImageTag}" `
        .

    if ($Push) {
        docker push "${ImageName}:${ImageTag}"
    }
}

Write-Host "Build completed successfully!"
