# TruthLens AI — Autonomous Demonstration and Verification Script (PowerShell)
# Verifies test suite, model artifacts, server launch, health endpoint, and API prediction.

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " TruthLens AI -- Verification and Demonstration Check " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

$allPassed = $true

# Check 1: Automated Test Suite (pytest)
Write-Host "`n[1/6] Running automated pytest test suite..." -ForegroundColor Yellow
$pytestOut = & $pythonExe -m pytest -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "[PASS] Pytest test suite executed and passed." -ForegroundColor Green
    Write-Host "       Result: $pytestOut" -ForegroundColor Gray
} else {
    Write-Host "[FAIL] Pytest test suite failed with exit code $LASTEXITCODE." -ForegroundColor Red
    $allPassed = $false
}

# Check 2: Model and Evaluation Artifacts
Write-Host "`n[2/6] Verifying model and evaluation artifacts..." -ForegroundColor Yellow
$modelPath = Join-Path $projectRoot "models\truthlens_model.joblib"
$metaPath = Join-Path $projectRoot "models\model_metadata.json"
$evalPath = Join-Path $projectRoot "results\evaluation_report.json"

if ((Test-Path $modelPath) -and (Test-Path $metaPath) -and (Test-Path $evalPath)) {
    $meta = Get-Content $metaPath -Raw | ConvertFrom-Json
    Write-Host "[PASS] Model artifact exists: $modelPath" -ForegroundColor Green
    Write-Host "       Model: $($meta.model_name)" -ForegroundColor Gray
    Write-Host "       Held-out Test Accuracy: $([math]::Round($meta.held_out_test_metrics.accuracy * 100, 2))%" -ForegroundColor Gray
} else {
    Write-Host "[FAIL] Missing required model or evaluation artifacts." -ForegroundColor Red
    $allPassed = $false
}

# Check 3: Launch Local Server and Verify /health
Write-Host "`n[3/6] Starting application server (.\.venv\Scripts\python.exe -m src.app) and verifying /health..." -ForegroundColor Yellow
$serverProcess = Start-Process -FilePath $pythonExe -ArgumentList "-m", "src.app" -PassThru -NoNewWindow
Start-Sleep -Seconds 4

try {
    $healthResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method Get -TimeoutSec 5
    if ($healthResp.status -eq "healthy" -and $healthResp.model_loaded -eq $true) {
        Write-Host "[PASS] /health endpoint returned HTTP 200 with model_loaded = true." -ForegroundColor Green
        Write-Host "       Environment: $($healthResp.environment)" -ForegroundColor Gray
    } else {
        Write-Host "[FAIL] /health returned unexpected payload." -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "[FAIL] Could not connect to http://127.0.0.1:5000/health." -ForegroundColor Red
    $allPassed = $false
}

# Check 4: Verify API Text Prediction
Write-Host "`n[4/6] Testing automated prediction via /api/predict (English)..." -ForegroundColor Yellow
try {
    $body = '{"text": "The Senate Finance Committee held a formal hearing on infrastructure grants on Wednesday."}'
    $apiResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/predict" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5
    if ($apiResp.status -eq "success" -and $apiResp.predicted_label) {
        Write-Host "[PASS] /api/predict returned valid prediction:" -ForegroundColor Green
        Write-Host "       Predicted Label: $($apiResp.predicted_label)" -ForegroundColor Gray
        Write-Host "       Decision Score: $($apiResp.decision_score_percentage)%" -ForegroundColor Gray
        Write-Host "       Model Explanation Available: $($apiResp.explanation.available)" -ForegroundColor Gray
    } else {
        Write-Host "[FAIL] /api/predict returned unexpected status." -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "[FAIL] Error invoking /api/predict." -ForegroundColor Red
    $allPassed = $false
}

# Check 5: Verify Language Safety (Stage 5 Hindi Input)
Write-Host "`n[5/6] Testing language safety via /api/predict (Hindi non-English input)..." -ForegroundColor Yellow
try {
    # Unicode escaped Hindi text to ensure compatibility with Windows PowerShell parser
    $hindiBody = '{"text": "\u092d\u093e\u0930\u0924 \u0938\u0930\u0915\u093e\u0930 \u0928\u0947 \u0915\u093f\u0938\u093e\u0928\u094b\u0902 \u0915\u0947 \u0932\u093f\u090f \u090f\u0915 \u0928\u0908 \u092f\u094b\u091c\u0928\u093e \u0915\u0940 \u0918\u094b\u0937\u0923\u093e \u0915\u0940 \u0939\u0948\u0964"}'
    $hindiResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/predict" -Method Post -Body $hindiBody -ContentType "application/json" -TimeoutSec 5
    $expectedMsg = "Unable to assess: this model was trained on English news."
    if ($hindiResp.status -eq "unsupported_language" -and $hindiResp.message -eq $expectedMsg) {
        Write-Host "[PASS] Language safety verified: returned exact expected message." -ForegroundColor Green
        Write-Host "       Detected: $($hindiResp.detected_language)" -ForegroundColor Gray
        Write-Host "       Message: $($hindiResp.message)" -ForegroundColor Gray
    } else {
        Write-Host "[FAIL] Language safety returned unexpected response: $($hindiResp.status)" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "[FAIL] Error invoking /api/predict with Hindi input." -ForegroundColor Red
    $allPassed = $false
}

# Check 6: Web Dashboard Verification (GET /)
Write-Host "`n[6/6] Testing Web Dashboard (GET /)..." -ForegroundColor Yellow
try {
    $homeResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/" -Method Get -TimeoutSec 30
    if ($homeResp -match "TruthLens") {
        Write-Host "[PASS] Dashboard GET / returned HTTP 200 with complete interface." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Dashboard returned unexpected content." -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "[FAIL] Error fetching Dashboard GET /: $($_.Exception.Message)" -ForegroundColor Red
    $allPassed = $false
}

# Cleanup Server Process
if ($serverProcess -and -not $serverProcess.HasExited) {
    Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "`nStopped test server process (PID $($serverProcess.Id))." -ForegroundColor Gray
}

Write-Host "`n============================================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host " ALL CHECKS PASSED -- TRUTHLENS AI READY FOR DEMONSTRATION " -ForegroundColor Green
} else {
    Write-Host " VERIFICATION COMPLETED WITH FAILURES " -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor Cyan
