# Docker Setup for Vibes ImGen

This document explains how to run Vibes ImGen using Docker containers.

---

## Prerequisites

- **Docker Desktop** installed and running
- **Docker Compose** (included with Docker Desktop)
- At least one **ComfyUI instance** running on network (e.g., 192.168.0.20:8188)

---

## Quick Start

### 1. Update GPU Configuration

Edit `config/gpus.yaml` with your actual ComfyUI instance IPs:

```yaml
nodes:
  - id: gpu-premium
    name: "RTX 5060 Ti"
    host: "192.168.0.20"  # Update this
    port: 8188
    # ... rest of config
```

### 2. Build and Start Containers

```bash
# Build images and start services
docker-compose up -d

# View logs
docker-compose logs -f

# View backend logs only
docker-compose logs -f backend

# View frontend logs only
docker-compose logs -f frontend
```

### 3. Access the Application

- **Frontend**: http://localhost (port 80)
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health

### 4. Stop Containers

```bash
# Stop containers (keep data)
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

---

## Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Host (Windows)                                       │
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐         │
│  │ Frontend         │         │ Backend          │         │
│  │ (nginx:alpine)   │────────▶│ (python:3.11)    │         │
│  │ Port: 80         │  proxy  │ Port: 8001       │         │
│  └─────────────────┘         └──────────────────┘         │
│          │                            │                     │
│          │                            │                     │
│          │                            ▼                     │
│          │                    ┌──────────────┐             │
│          │                    │ data/ volume │             │
│          │                    │ - vibes.db   │             │
│          │                    │ - images/    │             │
│          │                    │ - uploads/   │             │
│          │                    └──────────────┘             │
└─────────────────────────────────────────────────────────────┘
                                 │
                                 │ HTTP/WS
                                 │
                ┌────────────────┼────────────────────┐
                │                │                    │
                ▼                ▼                    ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ ComfyUI      │  │ ComfyUI      │  │ ComfyUI      │
        │ 192.168.0.20 │  │ 192.168.x.x  │  │ 192.168.x.x  │
        │ :8188        │  │ :8188        │  │ :8188        │
        └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Service Details

### Backend Container

- **Image**: Custom Python 3.11 image
- **Port**: 8001 (mapped to host 8001)
- **Volumes**:
  - `./data:/app/data` — Persistent storage (database + images)
  - `./config:/app/config:ro` — GPU configuration (read-only)
  - `./backend/app/templates:/app/app/templates:ro` — Workflow templates (read-only)
- **Health Check**: Polls `/health` endpoint every 30s
- **Restart Policy**: Unless stopped manually

**Environment Variables**:
- `PYTHONUNBUFFERED=1` — Real-time log output
- `DATABASE_URL=sqlite+aiosqlite:////app/data/vibes.db` — Database path

### Frontend Container

- **Image**: Multi-stage build (Node 20.12.2 builder → nginx:alpine)
- **Port**: 80 (mapped to host 80)
- **Nginx Configuration**:
  - Serves React SPA from `/usr/share/nginx/html`
  - Proxies `/api/*` requests to backend:8001
  - Proxies `/ws/*` WebSocket connections to backend:8001
  - SPA fallback: All routes return `index.html`
- **Depends On**: Backend (waits for health check)
- **Restart Policy**: Unless stopped manually

---

## Common Commands

### Build & Start

```bash
# Build images (first time or after code changes)
docker-compose build

# Start services in background
docker-compose up -d

# Build and start in one command
docker-compose up -d --build

# Start with live log output (foreground)
docker-compose up
```

### Logs & Debugging

```bash
# View all logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# View last 100 lines
docker-compose logs --tail=100

# Check container status
docker-compose ps

# Execute command in running container
docker-compose exec backend bash
docker-compose exec backend python -c "print('test')"
```

### Stop & Clean

```bash
# Stop containers (keep data)
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

# Stop and remove images
docker-compose down --rmi all

# Full cleanup (containers, volumes, images)
docker-compose down -v --rmi all
```

### Rebuild After Code Changes

```bash
# Backend changes
docker-compose build backend
docker-compose up -d backend

# Frontend changes
docker-compose build frontend
docker-compose up -d frontend

# Both
docker-compose up -d --build
```

---

## Development Workflow

### Option 1: Hot Reload with Docker (Not Implemented Yet)

To enable hot reload, modify `docker-compose.yml`:

```yaml
services:
  backend:
    volumes:
      - ./backend:/app  # Mount source code
    command: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

  frontend:
    volumes:
      - ./frontend/src:/app/src  # Mount source code
    command: npm run dev
```

### Option 2: Hybrid (Recommended for Now)

Run backend/frontend locally for development, use Docker for production:

```bash
# Development (local)
cd backend && uvicorn app.main:app --reload --port 8001
cd frontend && npm run dev

# Production (Docker)
docker-compose up -d --build
```

---

## Troubleshooting

### Backend won't start — health check fails

**Symptom**: Backend container restarts repeatedly, logs show "unhealthy"

**Fix**:
```bash
# Check backend logs
docker-compose logs backend

# Common issues:
# - ComfyUI not reachable: Check config/gpus.yaml
# - Database locked: Stop containers, delete data/vibes.db, restart
# - Port conflict: Another service using 8001

# Test backend manually
docker-compose exec backend curl http://localhost:8001/health
```

### Frontend shows "502 Bad Gateway"

**Symptom**: Frontend loads but API calls fail

**Fix**:
```bash
# Check if backend is healthy
docker-compose ps

# If backend is unhealthy, check logs
docker-compose logs backend

# Test backend from frontend container
docker-compose exec frontend wget -O- http://backend:8001/health
```

### WebSocket connection fails

**Symptom**: No real-time progress updates, browser console shows "WebSocket failed"

**Fix**:
```bash
# Check nginx proxy config
docker-compose exec frontend cat /etc/nginx/conf.d/default.conf

# Check browser console for exact error
# Should connect to ws://localhost/ws/session/{id}

# Test WebSocket manually
# Install wscat: npm i -g wscat
wscat -c ws://localhost/ws/session/test-id
```

### "Out of memory" during frontend build

**Symptom**: Docker build fails with "JavaScript heap out of memory"

**Fix**:
```bash
# Increase Docker memory limit (Docker Desktop → Settings → Resources)
# Recommended: 4 GB RAM minimum

# Or build frontend locally, then copy dist/
cd frontend
npm run build
docker-compose build frontend --no-cache
```

### Changes not reflected after rebuild

**Symptom**: Code changes don't appear in running container

**Fix**:
```bash
# Full rebuild without cache
docker-compose build --no-cache

# Or force recreate containers
docker-compose up -d --force-recreate

# Check if correct image is running
docker-compose images
```

### Permission denied errors (data directory)

**Symptom**: Backend can't write to `data/` directory

**Fix**:
```bash
# On Windows with WSL2, ensure directory exists
mkdir -p data/images data/uploads

# Check permissions (if using WSL/Linux)
ls -la data/
chmod -R 755 data/

# Or delete and let Docker create it
docker-compose down
rm -rf data/
docker-compose up -d
```

---

## Environment Variables

Create `.env` file in project root (optional):

```bash
# Backend
DATABASE_URL=sqlite+aiosqlite:////app/data/vibes.db
LOG_LEVEL=INFO

# Frontend (build-time only)
VITE_API_URL=http://localhost:8001
```

Reference in `docker-compose.yml`:

```yaml
services:
  backend:
    env_file:
      - .env
```

---

## Production Deployment

### Security Considerations

1. **Change default ports** (avoid 80/8001 if public)
2. **Add authentication** to backend API
3. **Enable HTTPS** (add Traefik/Caddy reverse proxy)
4. **Restrict CORS** (update `backend/app/main.py`)
5. **Use secrets** for sensitive config (Docker secrets)

### Example Production docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    image: vibes-imgen-backend:latest
    restart: always
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/vibes.db
      - LOG_LEVEL=WARNING
    volumes:
      - /mnt/nas/vibes-data:/app/data
      - /mnt/nas/vibes-config:/app/config:ro
    networks:
      - vibes-network
    healthcheck:
      interval: 60s
      timeout: 10s
      retries: 5

  frontend:
    image: vibes-imgen-frontend:latest
    restart: always
    depends_on:
      - backend
    networks:
      - vibes-network

  # Reverse proxy (optional)
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - vibes-network

networks:
  vibes-network:
    driver: bridge
```

---

## Backup & Restore

### Backup

```bash
# Stop containers
docker-compose down

# Backup data directory
tar -czf vibes-backup-$(date +%Y%m%d).tar.gz data/

# Copy to safe location
cp vibes-backup-*.tar.gz /path/to/backup/
```

### Restore

```bash
# Stop containers
docker-compose down

# Restore data
tar -xzf vibes-backup-20260209.tar.gz

# Restart
docker-compose up -d
```

---

## Performance Tuning

### Docker Desktop Settings (Windows)

1. **Resources → Memory**: 4 GB minimum, 8 GB recommended
2. **Resources → CPU**: 2 cores minimum, 4 cores recommended
3. **Resources → Disk Image Size**: 32 GB minimum (for images + models)
4. **General → Use WSL 2**: Enable for better performance

### Image Size Optimization

```bash
# View image sizes
docker images

# Current sizes (approximate):
# vibes-imgen-backend: ~1.2 GB (Python + deps)
# vibes-imgen-frontend: ~50 MB (nginx + static files)

# Optimize frontend (already using multi-stage build)
# Optimize backend (use python:3.11-slim, not full image)
```

---

## Network Configuration

### Accessing from Other Devices on LAN

By default, containers are accessible only from localhost. To access from other devices:

1. **Update docker-compose.yml** ports:
```yaml
services:
  frontend:
    ports:
      - "0.0.0.0:80:80"  # Allow external access
```

2. **Restart containers**:
```bash
docker-compose down
docker-compose up -d
```

3. **Access from other devices**:
```
http://<your-machine-ip>
```

4. **Update frontend API URL** (if needed):
Frontend makes requests to `/api/*` which nginx proxies to backend. This works for same-host access. For cross-device, you may need to update the API URL.

---

## FAQ

**Q: Can I run just the backend in Docker and frontend locally?**

A: Yes! Comment out the frontend service in `docker-compose.yml` and run:
```bash
docker-compose up -d backend
cd frontend && npm run dev
```

**Q: How do I update to latest code from GitHub?**

A:
```bash
git pull origin main
docker-compose down
docker-compose up -d --build
```

**Q: Do I need to rebuild after changing `config/gpus.yaml`?**

A: No, it's mounted as a volume. Just restart:
```bash
docker-compose restart backend
```

**Q: Can I use PostgreSQL instead of SQLite?**

A: Yes, update `DATABASE_URL` in docker-compose.yml and add a postgres service:
```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: vibes
      POSTGRES_USER: vibes
      POSTGRES_PASSWORD: password
  backend:
    environment:
      DATABASE_URL: postgresql+asyncpg://vibes:password@postgres/vibes
    depends_on:
      - postgres
```

**Q: How do I check container resource usage?**

A:
```bash
docker stats
```

---

**Last Updated**: 2026-02-09
