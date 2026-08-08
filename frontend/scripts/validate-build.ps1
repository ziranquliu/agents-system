# Frontend Build Validation Script
# Usage: .\scripts\validate-build.ps1
# Runs after npm install to verify TypeScript compilation and Vite build

$ErrorActionPreference = "Stop"
$frontendDir = Join-Path $PSScriptRoot ".."

Write-Host "=== Frontend Build Validation ===" -ForegroundColor Cyan

# Step 1: Check node_modules
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "[ERROR] node_modules not found. Run 'npm install' first." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] node_modules exists" -ForegroundColor Green

# Step 2: Check critical dependencies
$criticalDeps = @("antd", "react", "react-dom", "zustand", "vite", "@vitejs/plugin-react")
foreach ($dep in $criticalDeps) {
    $pkgJson = Join-Path $nodeModules "$dep\package.json"
    if (-not (Test-Path $pkgJson)) {
        Write-Host "[WARN] $dep missing package.json - reinstall needed" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] $dep installed" -ForegroundColor Green
    }
}

# Step 3: TypeScript check
Write-Host "`n--- TypeScript Check ---" -ForegroundColor Cyan
Set-Location $frontendDir
$tscResult = npx tsc --noEmit 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] TypeScript check passed" -ForegroundColor Green
} else {
    Write-Host "[FAIL] TypeScript errors found:" -ForegroundColor Red
    $tscResult | Select-Object -Last 30
}

# Step 4: Vite build
Write-Host "`n--- Vite Build ---" -ForegroundColor Cyan
$buildResult = npx vite build 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Vite build succeeded" -ForegroundColor Green
    # Check dist output
    $distDir = Join-Path $frontendDir "dist"
    if (Test-Path $distDir) {
        $fileCount = (Get-ChildItem $distDir -Recurse -File).Count
        $totalSize = (Get-ChildItem $distDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  dist/ files: $fileCount, total size: $([math]::Round($totalSize, 2)) MB" -ForegroundColor Gray
    }
} else {
    Write-Host "[FAIL] Vite build failed:" -ForegroundColor Red
    $buildResult | Select-Object -Last 30
}

Write-Host "`n=== Validation Complete ===" -ForegroundColor Cyan
