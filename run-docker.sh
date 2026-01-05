#!/bin/bash

# PPE Detection System - Docker Run Script for Linux/Mac
# This script starts the PPE Detection application in Docker with X11 forwarding

echo "🚀 Starting PPE Detection System in Docker..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating template..."
    cat > .env << EOF
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
EOF
    echo "✅ Template .env created. Please update it with your Supabase credentials."
    exit 1
fi

# Create Saved_Detections folder if it doesn't exist
mkdir -p Saved_Detections

# Allow X11 connections (Linux only)
xhost +local:docker > /dev/null 2>&1

echo "📦 Running PPE Detection container..."

# Run the Docker container
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$(pwd)/Saved_Detections:/app/Saved_Detections" \
  -v "$(pwd)/.env:/app/.env:ro" \
  --name ppe-app \
  ppe-detection-app python app.py

# Revoke X11 access
xhost -local:docker > /dev/null 2>&1

echo "✅ PPE Detection System stopped."
