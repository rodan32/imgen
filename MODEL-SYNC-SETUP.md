# Model Sync Setup Guide

## Architecture: Hybrid NAS + Local Cache

Your setup:
- **NAS:** Synology at `192.168.0.103` (master copies)
- **GPU Nodes:** 4 machines with ComfyUI on port 8188
- **Strategy:** NAS stores all models, nodes cache based on usage

## Setup Steps

### 1. Create NAS Share

On your Synology NAS (192.168.0.103):

1. **Create shared folder:**
   ```
   Control Panel → Shared Folder → Create
   Name: comfyui
   Path: /volume1/comfyui
   ```

2. **Set permissions:**
   ```
   - Read/Write access for your user account
   - NFS permissions: Enable NFS for this folder
   - NFS Rule: Allow access from 192.168.0.0/24
   ```

3. **Directory structure:**
   ```
   /volume1/comfyui/
     models/
       checkpoints/
         sd15/              # SD1.5 models for 3050Ti
         sdxl/              # SDXL models for better GPUs
       loras/               # All LoRAs (SD1.5 + SDXL)
       controlnet/          # ControlNet models (depth, canny, openpose, etc.)
       embeddings/          # Textual Inversions
       ipadapter/           # IP-Adapter models
       upscale_models/      # ESRGAN, Real-ESRGAN, etc.
       vae/                 # VAE models
       clip/                # CLIP models
       clip_vision/         # CLIP vision encoders (for IP-Adapter)
       text_encoders/       # Text encoders (T5, CLIP-L, etc.)
       ultralytics/         # Segmentation models (bbox, segment)
     output/                # Optional: shared output
   ```

### 2. Mount NAS on Each ComfyUI Node

On **each GPU machine** (all 4 nodes):

#### Option A: NFS Mount (Recommended for Linux)

```bash
# Install NFS client (if not already installed)
sudo apt-get install nfs-common  # Debian/Ubuntu
sudo yum install nfs-utils       # CentOS/RHEL

# Create mount point
sudo mkdir -p /mnt/comfyui

# Test mount
sudo mount -t nfs 192.168.0.103:/volume1/comfyui /mnt/comfyui

# If successful, add to /etc/fstab for automatic mounting
echo "192.168.0.103:/volume1/comfyui /mnt/comfyui nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab

# Verify
ls /mnt/comfyui/models
```

#### Option B: SMB/CIFS Mount (For Windows nodes)

```bash
# Install CIFS utils
sudo apt-get install cifs-utils

# Create credentials file
sudo nano /etc/cifs-credentials
# Add:
# username=your_nas_user
# password=your_nas_password

sudo chmod 600 /etc/cifs-credentials

# Mount
sudo mount -t cifs //192.168.0.103/comfyui /mnt/comfyui -o credentials=/etc/cifs-credentials

# Add to /etc/fstab
echo "//192.168.0.103/comfyui /mnt/comfyui cifs credentials=/etc/cifs-credentials,_netdev 0 0" | sudo tee -a /etc/fstab
```

### 3. Configure ComfyUI on Each Node

Two approaches - choose one:

#### Approach A: Symlink (Simple, Direct NAS Access)

```bash
cd ~/ComfyUI

# Backup existing models
mv models models.backup

# Create symlink to NAS
ln -s /mnt/comfyui/models models

# Verify
ls ~/ComfyUI/models/checkpoints
```

**Pros:** Simple, always in sync
**Cons:** Network I/O on every model load (minimal impact, loaded once into VRAM)

#### Approach B: Local Cache + Sync Script (Performance)

```bash
cd ~/ComfyUI

# Keep local models directory
# Models will be synced from NAS to here

# Install sync script dependencies
pip install httpx

# Make sync script executable
chmod +x ~/imgen/scripts/sync_models.py
```

**Pros:** Fast local access, no network I/O
**Cons:** Need to run sync script periodically

### 4. Initial Model Population

On **one machine**, copy your existing models to NAS:

```bash
# Copy checkpoints
rsync -avh --progress ~/ComfyUI/models/checkpoints/ /mnt/comfyui/models/checkpoints/

# Copy LoRAs
rsync -avh --progress ~/ComfyUI/models/loras/ /mnt/comfyui/models/loras/

# Other model types
rsync -avh --progress ~/ComfyUI/models/controlnet/ /mnt/comfyui/models/controlnet/
```

Now all nodes can access these models!

### 5. Setup Automated Sync (If Using Approach B)

On **each GPU node**, create a cron job:

```bash
# Edit crontab
crontab -e

# Add (runs every 2 hours):
0 */2 * * * /usr/bin/python3 ~/imgen/scripts/sync_models.py --node gpu-premium --backend http://192.168.0.40:8001 >> /var/log/model-sync.log 2>&1

# For each node, adjust the --node parameter:
# gpu-draft (3050Ti)    - Syncs only SD1.5 models
# gpu-standard (3060)   - Syncs SD1.5 + SDXL
# gpu-quality (4060Ti)  - Syncs SD1.5 + SDXL
# gpu-premium (5060Ti)  - Syncs everything
```

### 6. Manual Sync Commands

```bash
# Sync recommended hot models for this node
python sync_models.py --node gpu-premium

# Force re-sync everything
python sync_models.py --node gpu-premium --force

# Sync and remove cold models (cache eviction)
python sync_models.py --node gpu-premium --evict-cold

# Use different NAS path
python sync_models.py --node gpu-premium --nas-path /mnt/comfyui --local-path ~/ComfyUI
```

## Node-Specific Configuration

### gpu-draft (3050Ti, 4GB VRAM)
- **Cache only:** SD1.5 models
- **Max cache size:** 10GB
- **Recommended:** Keep 2-3 checkpoints, 10-15 LoRAs locally

```bash
# Cron entry for gpu-draft
0 */4 * * * python3 ~/imgen/scripts/sync_models.py --node gpu-draft --backend http://192.168.0.40:8001
```

### gpu-standard (3060, 12GB VRAM)
- **Cache:** SD1.5 + light SDXL models
- **Max cache size:** 30GB
- **Recommended:** 3-4 SDXL checkpoints, 20-30 LoRAs

### gpu-quality (4060Ti, 8GB VRAM)
- **Cache:** SD1.5 + SDXL models
- **Max cache size:** 30GB

### gpu-premium (5060Ti, 16GB VRAM)
- **Cache:** Everything, prioritize SDXL
- **Max cache size:** 50GB
- **Recommended:** All hot models, full LoRA library

## Backend Integration

The backend automatically tracks:
- Which models are on NAS (source of truth)
- Which models each node has cached
- Usage patterns (hot vs cold models)
- Recommendations for what to cache

API endpoints:
```bash
# Get sync status
curl http://localhost:8001/api/models/sync-status

# Get cache recommendations for a node
curl http://localhost:8001/api/models/recommend-cache?node_id=gpu-premium

# Get hot models (frequently used)
curl http://localhost:8001/api/models/hot-models?days=7
```

## Workflow

### Adding a New Model

1. **Download to NAS:**
   ```bash
   # On any machine with NAS mounted
   wget https://example.com/model.safetensors -O /mnt/comfyui/models/checkpoints/sdxl/new_model.safetensors
   ```

2. **Immediate availability (if using symlinks):**
   - All nodes see it immediately
   - No sync needed

3. **If using local cache:**
   - Wait for next cron sync (2 hours), OR
   - Run manual sync: `python sync_models.py --node gpu-premium`

4. **Backend auto-discovers:**
   - Next LoRA poll (5 minutes)
   - Model shows up in available list

### Removing a Model

1. **Delete from NAS:**
   ```bash
   rm /mnt/comfyui/models/checkpoints/old_model.safetensors
   ```

2. **If using local cache:**
   - Run sync with eviction: `python sync_models.py --node gpu-premium --evict-cold`

## Troubleshooting

### Models not appearing in ComfyUI

```bash
# Check NAS mount
ls /mnt/comfyui/models

# Check ComfyUI can see models
ls ~/ComfyUI/models/checkpoints

# Restart ComfyUI to refresh model list
# (ComfyUI caches model list on startup)
```

### Sync script fails

```bash
# Check backend is reachable
curl http://192.168.0.40:8001/health

# Check NAS is mounted
mount | grep comfyui

# Run sync with verbose logging
python sync_models.py --node gpu-premium -v
```

### Out of disk space

```bash
# Check cache usage
df -h ~/ComfyUI/models

# Evict cold models
python sync_models.py --node gpu-premium --evict-cold

# Manually remove old models
rm ~/ComfyUI/models/checkpoints/old_model.safetensors
```

## Performance Considerations

### Symlink Approach (Direct NAS)
- **Pro:** Always in sync, no disk space used
- **Con:** ~50-200ms latency on model load (one-time per generation)
- **Recommended for:** Gigabit LAN with low latency

### Local Cache Approach
- **Pro:** Zero network latency, fastest
- **Con:** Uses local disk, needs periodic sync
- **Recommended for:** Large model collections, slower networks

### Hybrid Best Practice
1. **Hot models** (used daily): Keep cached locally
2. **Warm models** (used weekly): Sync periodically
3. **Cold models** (rarely used): Access from NAS as needed

## Next Steps

1. ✅ Create NAS share at `192.168.0.103:/volume1/comfyui`
2. ✅ Mount on all 4 GPU nodes
3. ✅ Choose symlink or cache approach
4. ✅ Copy existing models to NAS
5. ✅ Test with backend integration
6. ✅ Set up cron jobs (if using cache approach)
