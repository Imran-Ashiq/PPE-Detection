# Docker Deployment Guide 🐳

Complete guide for deploying the PPE Detection System using Docker.

## 📋 Prerequisites

- **Docker Desktop** installed and running
  - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Mac: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: Install Docker Engine and Docker Compose

- **X11 Server** (for GUI display)
  - Windows: [VcXsrv](https://sourceforge.net/projects/vcxsrv/)
  - Mac: [XQuartz](https://www.xquartz.org/)
  - Linux: Built-in X11 server

## 🚀 Quick Start

### Method 1: Using Docker Compose (Recommended)

1. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

2. **Start VcXsrv (Windows) or XQuartz (Mac)**

3. **Build and run:**
   ```bash
   docker-compose up --build
   ```

4. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Method 2: Using Helper Scripts

**Windows:**
```powershell
.\run-docker.ps1
```

**Linux/Mac:**
```bash
chmod +x run-docker.sh
./run-docker.sh
```

### Method 3: Manual Docker Commands

**Build the image:**
```bash
docker build -t ppe-detection-app .
```

**Run the container:**

**Windows:**
```powershell
docker run -it --rm `
  -e DISPLAY=host.docker.internal:0 `
  -v "${PWD}\Saved_Detections:/app/Saved_Detections" `
  -v "${PWD}\.env:/app/.env:ro" `
  --name ppe-app `
  ppe-detection-app python app.py
```

**Linux/Mac:**
```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$(pwd)/Saved_Detections:/app/Saved_Detections" \
  -v "$(pwd)/.env:/app/.env:ro" \
  --name ppe-app \
  ppe-detection-app python app.py
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### Volume Mounts

The container uses two volume mounts:

1. **Saved_Detections/** - Stores recorded videos and detection frames
2. **.env** - Environment variables for authentication

## 🖥️ X11 Server Setup

### Windows (VcXsrv)

1. Install VcXsrv from [SourceForge](https://sourceforge.net/projects/vcxsrv/)
2. Launch XLaunch with these settings:
   - Display number: `0`
   - Start no client: ✓
   - Disable access control: ✓
   - Additional parameters: `-ac`

### Mac (XQuartz)

1. Install XQuartz: `brew install --cask xquartz`
2. Start XQuartz: `open -a XQuartz`
3. In XQuartz preferences:
   - Security tab → Enable "Allow connections from network clients"
4. Allow connections:
   ```bash
   xhost +localhost
   ```

### Linux

X11 is built-in. Just allow Docker connections:
```bash
xhost +local:docker
```

## 🐛 Troubleshooting

### GUI Not Displaying

**Windows:**
- Ensure VcXsrv is running before starting the container
- Check Windows Firewall allows VcXsrv
- Try: `docker run ... -e DISPLAY=host.docker.internal:0.0`

**Mac:**
- Run `xhost +localhost` before starting container
- Check XQuartz is running: `ps aux | grep XQuartz`

**Linux:**
- Run `xhost +local:docker`
- Check `echo $DISPLAY` returns `:0` or similar

### Permission Denied on .env

The `.env` file is mounted read-only (`:ro`). This is intentional for security.

### Webcam Not Working

Docker on Mac/Windows doesn't support direct webcam access. Use:
- IP Camera feed
- Video file upload
- Run app locally (not in Docker) for webcam

### Build Taking Too Long

First build downloads all dependencies (~1.9GB). Subsequent builds use cache.

Use `--no-cache` to force rebuild:
```bash
docker build --no-cache -t ppe-detection-app .
```

## 📦 Docker Compose Commands

**Build and start:**
```bash
docker-compose up --build
```

**Run in background:**
```bash
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f
```

**Stop services:**
```bash
docker-compose down
```

**Remove volumes:**
```bash
docker-compose down -v
```

## 🔍 Useful Docker Commands

**List running containers:**
```bash
docker ps
```

**Stop container:**
```bash
docker stop ppe-app
```

**View logs:**
```bash
docker logs ppe-app
```

**Execute command in running container:**
```bash
docker exec -it ppe-app /bin/bash
```

**Remove image:**
```bash
docker rmi ppe-detection-app
```

**Clean up unused resources:**
```bash
docker system prune -a
```

## 🚀 Production Deployment

For production environments:

1. Use docker-compose with restart policies:
   ```yaml
   restart: unless-stopped
   ```

2. Set resource limits:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 4G
   ```

3. Use environment file instead of .env:
   ```bash
   docker-compose --env-file production.env up -d
   ```

4. Enable health checks (already in docker-compose.yml)

## 📊 Performance Optimization

**For faster builds:**
- Use `.dockerignore` to exclude unnecessary files
- Multi-stage builds (advanced)

**For better runtime:**
- Enable GPU support (requires nvidia-docker)
- Increase memory allocation in Docker Desktop settings
- Use SSD for volume mounts

## 🔒 Security Best Practices

1. **Never commit .env to git**
   - Always use `.env.example` as template
   
2. **Use read-only mounts** where possible:
   ```bash
   -v "$(pwd)/.env:/app/.env:ro"
   ```

3. **Run as non-root user** (add to Dockerfile):
   ```dockerfile
   RUN useradd -m appuser
   USER appuser
   ```

4. **Scan images for vulnerabilities:**
   ```bash
   docker scan ppe-detection-app
   ```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [VcXsrv X Server](https://sourceforge.net/projects/vcxsrv/)
- [Project README](README.md)
