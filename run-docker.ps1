# PPE Detection System - Docker Run Script for Windows
# This script starts the PPE Detection application in Docker with VcXsrv X11 forwarding

Write-Host "🚀 Starting PPE Detection System in Docker..." -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Warning: .env file not found. Creating template..." -ForegroundColor Yellow
    @"
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
"@ | Out-File -FilePath ".env" -Encoding utf8
    Write-Host "✅ Template .env created. Please update it with your Supabase credentials." -ForegroundColor Green
    exit 1
}

# Create Saved_Detections folder if it doesn't exist
if (-not (Test-Path "Saved_Detections")) {
    New-Item -ItemType Directory -Path "Saved_Detections" | Out-Null
}

# Check if VcXsrv is running
$vcxsrvRunning = Get-Process -Name "vcxsrv" -ErrorAction SilentlyContinue
if (-not $vcxsrvRunning) {
    Write-Host "⚠️  VcXsrv is not running. Starting VcXsrv..." -ForegroundColor Yellow
    
    # Try to start VcXsrv
    $vcxsrvPath = "C:\Program Files\VcXsrv\vcxsrv.exe"
    if (Test-Path $vcxsrvPath) {
        Start-Process $vcxsrvPath -ArgumentList ":0 -ac -terminate -lesspointer -multiwindow -clipboard -wgl -dpi auto"
        Start-Sleep -Seconds 3
        Write-Host "✅ VcXsrv started." -ForegroundColor Green
    } else {
        Write-Host "❌ VcXsrv not found at: $vcxsrvPath" -ForegroundColor Red
        Write-Host "   Please install VcXsrv or start it manually." -ForegroundColor Red
        exit 1
    }
}

Write-Host "📦 Running PPE Detection container..." -ForegroundColor Cyan

# Run the Docker container
docker run -it --rm `
  -e DISPLAY=host.docker.internal:0 `
  -v "${PWD}\Saved_Detections:/app/Saved_Detections" `
  -v "${PWD}\.env:/app/.env:ro" `
  --name ppe-app `
  ppe-detection-app python app.py

Write-Host "✅ PPE Detection System stopped." -ForegroundColor Green
