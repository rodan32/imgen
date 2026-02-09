#!/usr/bin/env python3
"""
ComfyUI Setup Script for Vibes ImGen

Automates ComfyUI installation and model downloads for each GPU tier.
Run on each machine with the appropriate tier flag:

    python setup_comfyui.py --tier draft      # 3050 Ti (4GB) - SD1.5 only
    python setup_comfyui.py --tier standard   # 3060 (12GB) - SD1.5 + SDXL
    python setup_comfyui.py --tier quality    # 4060 Ti (8GB) - SD1.5 + SDXL
    python setup_comfyui.py --tier premium    # 5060 Ti (16GB) - Everything

Options:
    --install-dir PATH   Where to install ComfyUI (default: ./ComfyUI)
    --skip-comfyui       Skip ComfyUI installation, only download models
    --skip-models        Skip model downloads, only install ComfyUI
    --dry-run            Show what would be downloaded without downloading
"""

import argparse
import os
import subprocess
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field

# ============================================================================
# Model Definitions
# ============================================================================

@dataclass
class ModelDownload:
    filename: str
    url: str
    size_mb: int
    dest_subdir: str  # relative to ComfyUI/models/
    description: str


# --- Checkpoints ---

SD15_CHECKPOINT = ModelDownload(
    filename="v1-5-pruned-emaonly.safetensors",
    url="https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
    size_mb=4000,
    dest_subdir="checkpoints",
    description="Stable Diffusion 1.5 (inference only)",
)

SDXL_CHECKPOINT = ModelDownload(
    filename="sd_xl_base_1.0.safetensors",
    url="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
    size_mb=6100,
    dest_subdir="checkpoints",
    description="Stable Diffusion XL Base 1.0",
)

FLUX_CHECKPOINT = ModelDownload(
    filename="flux1-dev-fp8.safetensors",
    url="https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors",
    size_mb=12000,
    dest_subdir="checkpoints",
    description="Flux.1 Dev (FP8 quantized, 16GB VRAM friendly)",
)

# --- ControlNet ---

CONTROLNET_OPENPOSE = ModelDownload(
    filename="OpenPoseXL2.safetensors",
    url="https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors",
    size_mb=5000,
    dest_subdir="controlnet",
    description="ControlNet OpenPose for SDXL (pose control)",
)

CONTROLNET_DEPTH = ModelDownload(
    filename="diffusion_pytorch_model.fp16.safetensors",
    url="https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0-small/resolve/main/diffusion_pytorch_model.fp16.safetensors",
    size_mb=750,
    dest_subdir="controlnet",
    description="ControlNet Depth for SDXL (small variant)",
)

CONTROLNET_CANNY = ModelDownload(
    filename="diffusion_pytorch_model_canny.fp16.safetensors",
    url="https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0-small/resolve/main/diffusion_pytorch_model.fp16.safetensors",
    size_mb=750,
    dest_subdir="controlnet",
    description="ControlNet Canny for SDXL (small variant)",
)

# --- IP-Adapter ---

IPADAPTER_PLUS = ModelDownload(
    filename="ip-adapter-plus_sdxl_vit-h.bin",
    url="https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.bin",
    size_mb=96,
    dest_subdir="ipadapter",
    description="IP-Adapter Plus for SDXL (style transfer)",
)

IPADAPTER_FACEID = ModelDownload(
    filename="ip-adapter-faceid-plusv2_sdxl.bin",
    url="https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin",
    size_mb=1500,
    dest_subdir="ipadapter",
    description="IP-Adapter FaceID PlusV2 for SDXL",
)

IPADAPTER_FACEID_LORA = ModelDownload(
    filename="ip-adapter-faceid-plusv2_sdxl_lora.safetensors",
    url="https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl_lora.safetensors",
    size_mb=372,
    dest_subdir="loras",
    description="IP-Adapter FaceID LoRA for SDXL",
)

# --- CLIP Vision ---

CLIP_VIT_H = ModelDownload(
    filename="CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    url="https://huggingface.co/laion/CLIP-ViT-H-14-laion2B-s32B-b79K/resolve/main/open_clip_pytorch_model.safetensors",
    size_mb=2500,
    dest_subdir="clip_vision",
    description="CLIP ViT-H (required for IP-Adapter)",
)

# --- Upscaler ---

UPSCALER_ULTRASHARP = ModelDownload(
    filename="4x-UltraSharp.pth",
    url="https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth",
    size_mb=67,
    dest_subdir="upscale_models",
    description="4x UltraSharp ESRGAN upscaler",
)


# ============================================================================
# Tier Definitions
# ============================================================================

TIER_MODELS: dict[str, list[ModelDownload]] = {
    "draft": [
        SD15_CHECKPOINT,
    ],
    "standard": [
        SD15_CHECKPOINT,
        SDXL_CHECKPOINT,
    ],
    "quality": [
        SD15_CHECKPOINT,
        SDXL_CHECKPOINT,
    ],
    "premium": [
        SD15_CHECKPOINT,
        SDXL_CHECKPOINT,
        FLUX_CHECKPOINT,
        CONTROLNET_OPENPOSE,
        CONTROLNET_DEPTH,
        CONTROLNET_CANNY,
        IPADAPTER_PLUS,
        IPADAPTER_FACEID,
        IPADAPTER_FACEID_LORA,
        CLIP_VIT_H,
        UPSCALER_ULTRASHARP,
    ],
}

TIER_DESCRIPTIONS = {
    "draft": "3050 Ti (4GB) — SD1.5 only, fast drafts",
    "standard": "3060 (12GB) — SD1.5 + SDXL",
    "quality": "4060 Ti (8GB) — SD1.5 + SDXL",
    "premium": "5060 Ti (16GB) — Everything (SD1.5, SDXL, Flux, ControlNet, IP-Adapter, Upscaler)",
}

# Custom nodes to install
CUSTOM_NODES = [
    {
        "name": "ComfyUI-Manager",
        "url": "https://github.com/ltdrdata/ComfyUI-Manager.git",
        "description": "Node manager for easy installation of other custom nodes",
    },
    {
        "name": "ComfyUI_IPAdapter_plus",
        "url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git",
        "description": "IP-Adapter nodes for style transfer and face identity",
    },
]


# ============================================================================
# Helper Functions
# ============================================================================

def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(text: str) -> None:
    print(f"  -> {text}")


def run_cmd(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"     $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=False)


def download_file(url: str, dest: Path, size_mb: int) -> bool:
    """Download a file using the best available method."""
    if dest.exists():
        existing_mb = dest.stat().st_size / (1024 * 1024)
        if existing_mb > size_mb * 0.9:  # within 10% of expected size
            print(f"     Already exists ({existing_mb:.0f} MB), skipping")
            return True
        else:
            print(f"     Exists but incomplete ({existing_mb:.0f}/{size_mb} MB), re-downloading")

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Try wget first (common on Windows via Git Bash or chocolatey)
    try:
        run_cmd(["wget", "-c", "-O", str(dest), url], check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Try curl
    try:
        run_cmd(["curl", "-L", "-C", "-", "-o", str(dest), url], check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fall back to Python urllib
    print("     Using Python urllib (no resume support)...")
    import urllib.request
    try:
        urllib.request.urlretrieve(url, str(dest))
        return True
    except Exception as e:
        print(f"     ERROR: Download failed: {e}")
        return False


def install_comfyui(install_dir: Path) -> bool:
    """Clone and set up ComfyUI."""
    if (install_dir / "main.py").exists():
        print_step("ComfyUI already installed, skipping clone")
        return True

    print_step("Cloning ComfyUI...")
    try:
        run_cmd(["git", "clone", "https://github.com/comfyanonymous/ComfyUI.git", str(install_dir)])
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"  ERROR: Failed to clone ComfyUI: {e}")
        print("  Make sure git is installed and in PATH")
        return False

    print_step("Installing Python dependencies...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(install_dir / "requirements.txt")]
    try:
        run_cmd(pip_cmd)
    except subprocess.CalledProcessError:
        print("  WARNING: pip install failed. You may need to install dependencies manually.")
        print(f"  Run: {' '.join(pip_cmd)}")

    return True


def install_custom_nodes(comfyui_dir: Path, tier: str) -> None:
    """Install required custom nodes."""
    custom_nodes_dir = comfyui_dir / "custom_nodes"
    custom_nodes_dir.mkdir(exist_ok=True)

    for node in CUSTOM_NODES:
        # Skip IP-Adapter on draft tier (no SDXL)
        if node["name"] == "ComfyUI_IPAdapter_plus" and tier == "draft":
            print_step(f"Skipping {node['name']} (not needed for draft tier)")
            continue

        node_dir = custom_nodes_dir / node["name"]
        if node_dir.exists():
            print_step(f"{node['name']} already installed, skipping")
            continue

        print_step(f"Installing {node['name']}...")
        try:
            run_cmd(["git", "clone", node["url"], str(node_dir)])
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  WARNING: Failed to install {node['name']}: {e}")

    # Install insightface for FaceID support (premium tier)
    if tier == "premium":
        print_step("Installing insightface for FaceID support...")
        try:
            run_cmd([sys.executable, "-m", "pip", "install", "insightface", "onnxruntime"])
        except subprocess.CalledProcessError:
            print("  WARNING: insightface install failed.")
            print("  You may need Visual C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/")


def download_models(comfyui_dir: Path, tier: str, dry_run: bool = False) -> None:
    """Download all models for the given tier."""
    models = TIER_MODELS[tier]
    models_dir = comfyui_dir / "models"

    total_size = sum(m.size_mb for m in models)
    print_step(f"Models to download: {len(models)} files, ~{total_size/1024:.1f} GB total\n")

    for i, model in enumerate(models, 1):
        dest = models_dir / model.dest_subdir / model.filename
        status = "EXISTS" if dest.exists() else "DOWNLOAD"
        print(f"  [{i}/{len(models)}] {model.description}")
        print(f"         {model.filename} ({model.size_mb} MB) [{status}]")
        print(f"         -> {model.dest_subdir}/")

        if dry_run:
            continue

        success = download_file(model.url, dest, model.size_mb)
        if not success:
            print(f"  WARNING: Failed to download {model.filename}")
        print()


def verify_installation(comfyui_dir: Path, tier: str) -> None:
    """Verify that all expected files exist."""
    print_header("Verification")
    models = TIER_MODELS[tier]
    models_dir = comfyui_dir / "models"

    all_ok = True
    for model in models:
        dest = models_dir / model.dest_subdir / model.filename
        if dest.exists():
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  OK   {model.dest_subdir}/{model.filename} ({size_mb:.0f} MB)")
        else:
            print(f"  MISS {model.dest_subdir}/{model.filename}")
            all_ok = False

    # Check custom nodes
    custom_nodes_dir = comfyui_dir / "custom_nodes"
    for node in CUSTOM_NODES:
        if node["name"] == "ComfyUI_IPAdapter_plus" and tier == "draft":
            continue
        node_dir = custom_nodes_dir / node["name"]
        if node_dir.exists():
            print(f"  OK   custom_nodes/{node['name']}")
        else:
            print(f"  MISS custom_nodes/{node['name']}")
            all_ok = False

    if all_ok:
        print("\n  All files verified successfully!")
    else:
        print("\n  WARNING: Some files are missing. Re-run the script to retry downloads.")

    print(f"\n  To start ComfyUI for network access:")
    print(f"    cd {comfyui_dir}")
    print(f"    python main.py --listen 0.0.0.0 --port 8188")


def generate_gpu_config(tier: str, host: str = "127.0.0.1", port: int = 8188) -> dict:
    """Generate a GPU node config entry for config/gpus.yaml."""
    tier_to_gpu = {
        "draft": {"name": "RTX 3050 Ti", "vram_gb": 4, "max_resolution": 512, "max_batch": 1,
                   "capabilities": ["sd15"]},
        "standard": {"name": "RTX 3060", "vram_gb": 12, "max_resolution": 1024, "max_batch": 2,
                      "capabilities": ["sd15", "sdxl", "pony", "illustrious"]},
        "quality": {"name": "RTX 4060 Ti", "vram_gb": 8, "max_resolution": 1024, "max_batch": 4,
                     "capabilities": ["sd15", "sdxl", "pony", "illustrious"]},
        "premium": {"name": "RTX 5060 Ti", "vram_gb": 16, "max_resolution": 1536, "max_batch": 4,
                     "capabilities": ["sd15", "sdxl", "pony", "illustrious", "flux", "flux_fp8",
                                       "upscale", "controlnet", "ipadapter", "faceid"]},
    }
    gpu = tier_to_gpu[tier]
    return {
        "id": f"gpu-{tier}",
        "name": gpu["name"],
        "vram_gb": gpu["vram_gb"],
        "tier": tier,
        "host": host,
        "port": port,
        "capabilities": gpu["capabilities"],
        "max_resolution": gpu["max_resolution"],
        "max_batch": gpu["max_batch"],
    }


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Setup ComfyUI with models for Vibes ImGen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tiers:
  draft     - 3050 Ti (4GB):  SD1.5 only (~4 GB downloads)
  standard  - 3060 (12GB):    SD1.5 + SDXL (~10 GB downloads)
  quality   - 4060 Ti (8GB):  SD1.5 + SDXL (~10 GB downloads)
  premium   - 5060 Ti (16GB): Everything (~40 GB downloads)
        """,
    )
    parser.add_argument("--tier", required=True, choices=["draft", "standard", "quality", "premium"],
                        help="GPU tier for this machine")
    parser.add_argument("--install-dir", type=Path, default=Path("./ComfyUI"),
                        help="ComfyUI installation directory (default: ./ComfyUI)")
    parser.add_argument("--skip-comfyui", action="store_true",
                        help="Skip ComfyUI installation, only download models")
    parser.add_argument("--skip-models", action="store_true",
                        help="Skip model downloads, only install ComfyUI + custom nodes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded without downloading")
    parser.add_argument("--host", default="127.0.0.1",
                        help="This machine's LAN IP (for GPU config generation)")
    parser.add_argument("--port", type=int, default=8188,
                        help="ComfyUI port (default: 8188)")

    args = parser.parse_args()

    print_header(f"Vibes ImGen - ComfyUI Setup ({args.tier} tier)")
    print(f"  Tier: {args.tier} - {TIER_DESCRIPTIONS[args.tier]}")
    print(f"  Install dir: {args.install_dir.resolve()}")
    if args.dry_run:
        print("  ** DRY RUN - no changes will be made **")

    # Step 1: Install ComfyUI
    if not args.skip_comfyui and not args.dry_run:
        print_header("Step 1: Install ComfyUI")
        if not install_comfyui(args.install_dir):
            print("  Failed to install ComfyUI. Exiting.")
            sys.exit(1)
    else:
        print_header("Step 1: Install ComfyUI (skipped)")

    # Step 2: Install custom nodes
    if not args.skip_comfyui and not args.dry_run:
        print_header("Step 2: Install Custom Nodes")
        install_custom_nodes(args.install_dir, args.tier)
    else:
        print_header("Step 2: Install Custom Nodes (skipped)")

    # Step 3: Download models
    if not args.skip_models:
        print_header(f"Step 3: Download Models ({args.tier} tier)")
        download_models(args.install_dir, args.tier, dry_run=args.dry_run)
    else:
        print_header("Step 3: Download Models (skipped)")

    # Step 4: Verify
    if not args.dry_run:
        verify_installation(args.install_dir, args.tier)

    # Step 5: Generate GPU config snippet
    print_header("GPU Config (add to config/gpus.yaml)")
    config = generate_gpu_config(args.tier, args.host, args.port)
    # Pretty print as YAML-ish
    print(f"  - id: {config['id']}")
    print(f"    name: \"{config['name']}\"")
    print(f"    vram_gb: {config['vram_gb']}")
    print(f"    tier: {config['tier']}")
    print(f"    host: \"{config['host']}\"")
    print(f"    port: {config['port']}")
    print(f"    capabilities: {config['capabilities']}")
    print(f"    max_resolution: {config['max_resolution']}")
    print(f"    max_batch: {config['max_batch']}")

    print(f"\n  Copy the above into your config/gpus.yaml on the backend server.")
    print(f"\n  Done! Run ComfyUI with:")
    print(f"    cd {args.install_dir.resolve()}")
    print(f"    python main.py --listen 0.0.0.0 --port {args.port}")


if __name__ == "__main__":
    main()
