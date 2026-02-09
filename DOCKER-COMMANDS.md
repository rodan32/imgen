# Docker Commands Quick Reference

## Essential Commands

### Build & Start
```bash
# Build images and start services
docker-compose up -d --build

# Start services (if already built)
docker-compose up -d

# View logs (follow mode)
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop & Clean
```bash
# Stop containers (keep data)
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

# Full cleanup (containers, volumes, images)
docker-compose down -v --rmi all
```

### Status & Monitoring
```bash
# Check container status
docker-compose ps

# View resource usage
docker stats

# Check logs (last 100 lines)
docker-compose logs --tail=100
```

### Rebuild After Changes
```bash
# Rebuild specific service
docker-compose build backend
docker-compose up -d backend

# Rebuild all services
docker-compose up -d --build
```

### Execute Commands in Containers
```bash
# Open bash shell in backend
docker-compose exec backend bash

# Run Python command
docker-compose exec backend python -c "print('test')"

# Check backend health
docker-compose exec backend curl http://localhost:8001/health

# Open shell in frontend (nginx doesn't have bash, use sh)
docker-compose exec frontend sh
```

## Troubleshooting Commands

### Backend Issues
```bash
# Check backend is running
docker-compose ps backend

# View backend logs
docker-compose logs -f backend

# Test backend health from inside container
docker-compose exec backend curl http://localhost:8001/health

# Test backend health from host
curl http://localhost:8001/health

# Restart backend
docker-compose restart backend
```

### Frontend Issues
```bash
# Check frontend is running
docker-compose ps frontend

# View frontend logs
docker-compose logs -f frontend

# Test frontend from host
curl http://localhost

# Check nginx config
docker-compose exec frontend cat /etc/nginx/conf.d/default.conf

# Test backend connection from frontend container
docker-compose exec frontend wget -O- http://backend:8001/health
```

### Network Issues
```bash
# List Docker networks
docker network ls

# Inspect vibes-network
docker network inspect imgen_vibes-network

# Test connectivity between containers
docker-compose exec frontend ping backend
docker-compose exec backend ping frontend
```

### Volume Issues
```bash
# List volumes
docker volume ls

# Inspect data volume
docker volume inspect imgen_data

# Check data directory from backend
docker-compose exec backend ls -la /app/data

# Check if database exists
docker-compose exec backend ls -la /app/data/vibes.db
```

### Build Cache Issues
```bash
# Force rebuild without cache
docker-compose build --no-cache

# Remove all unused images
docker image prune -a

# Remove all unused volumes
docker volume prune
```

## Development Workflow

### Local Development (Hybrid)
```bash
# Run backend locally
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Run frontend locally (in separate terminal)
cd frontend
npm install
npm run dev

# Both accessible at:
# Backend: http://localhost:8001
# Frontend: http://localhost:5173
```

### Docker Development
```bash
# Build and start
docker-compose up -d --build

# Watch logs
docker-compose logs -f

# Make changes to code
# Rebuild affected service
docker-compose build backend  # or frontend
docker-compose up -d backend  # or frontend

# Accessible at:
# Backend: http://localhost:8001
# Frontend: http://localhost (port 80)
```

### Testing Changes
```bash
# Test backend API
curl http://localhost:8001/health
curl http://localhost:8001/api/gpus

# Test frontend
curl http://localhost

# Open browser
open http://localhost  # Mac
start http://localhost  # Windows
xdg-open http://localhost  # Linux
```

## Production Commands

### Deployment
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Backup
```bash
# Stop containers
docker-compose down

# Backup data directory
tar -czf vibes-backup-$(date +%Y%m%d).tar.gz data/

# Restart
docker-compose up -d
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

### Update
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose down
docker-compose up -d
```

## Useful One-Liners

```bash
# Restart everything
docker-compose restart

# View real-time logs for all services
docker-compose logs -f --tail=100

# Check if backend is healthy
docker-compose exec backend curl -f http://localhost:8001/health && echo "OK" || echo "FAILED"

# Check disk usage
docker system df

# Clean up everything Docker-related (use with caution!)
docker system prune -a --volumes

# Export backend image
docker save vibes-imgen-backend:latest | gzip > backend-image.tar.gz

# Import backend image
docker load < backend-image.tar.gz

# Get container IP address
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' vibes-imgen-backend

# Follow logs for specific keyword
docker-compose logs -f | grep "ERROR"

# Count log lines by level
docker-compose logs | grep -c "ERROR"
docker-compose logs | grep -c "INFO"
```

## Port Reference

| Service | Container Port | Host Port | URL |
|---------|---------------|-----------|-----|
| Frontend | 80 | 80 | http://localhost |
| Backend | 8001 | 8001 | http://localhost:8001 |
| Backend API Docs | 8001 | 8001 | http://localhost:8001/docs |
| ComfyUI (external) | 8188 | 8188 | http://192.168.0.20:8188 |

## Environment Variables

Set in `docker-compose.yml` or create `.env` file:

```env
# Backend
DATABASE_URL=sqlite+aiosqlite:////app/data/vibes.db
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Frontend (build-time only)
VITE_API_URL=http://localhost:8001
```

## Common Issues & Fixes

### Port 80 already in use
```bash
# Find process using port 80
# Windows:
netstat -ano | findstr :80

# Kill process (use PID from above)
taskkill /PID <PID> /F

# Or change port in docker-compose.yml:
ports:
  - "8080:80"  # Access frontend at http://localhost:8080
```

### Port 8001 already in use
```bash
# Find and kill process
# Windows:
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# Or change port in docker-compose.yml:
ports:
  - "8002:8001"  # Access backend at http://localhost:8002
```

### Database locked
```bash
# Stop containers
docker-compose down

# Remove database file
rm data/vibes.db

# Restart (new DB will be created)
docker-compose up -d
```

### Out of disk space
```bash
# Clean up unused Docker resources
docker system prune -a --volumes

# Check disk usage
docker system df

# Remove specific images
docker rmi <image-id>
```

### Container keeps restarting
```bash
# Check logs for error
docker-compose logs backend

# Common causes:
# - Health check failing (check /health endpoint)
# - Missing dependencies (check requirements.txt)
# - Config error (check config/gpus.yaml)
# - Port conflict (change port in docker-compose.yml)
```

---

**Last Updated**: 2026-02-09
