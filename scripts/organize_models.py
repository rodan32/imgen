#!/usr/bin/env python3
"""
Organize downloaded IP-Adapter, ControlNet, and CLIP Vision models.

Helps move models from Downloads folder to correct ComfyUI directories.
"""

import os
import shutil
from pathlib import Path

# Model file mappings: (source pattern, destination folder)
MODEL_PATTERNS = {
    # IP-Adapter models
    "ip-adapter": "ipadapter",
    "ip_adapter": "ipadapter",

    # ControlNet models
    "control_": "controlnet",
    "controlnet": "controlnet",
    "diffusers_xl": "controlnet",
    "thibaud_xl": "controlnet",

    # CLIP Vision models
    "CLIP-ViT": "clip_vision",
    "clip_vision": "clip_vision",

    # VAE models
    "vae": "vae",

    # Upscale models
    "upscale": "upscale_models",
    "esrgan": "upscale_models",
    "realesrgan": "upscale_models",
}

def find_comfyui_path():
    """Try to locate ComfyUI installation."""
    common_paths = [
        Path.home() / "ComfyUI",
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI"),
        Path("/opt/ComfyUI"),
        Path.cwd() / "ComfyUI",
    ]

    for path in common_paths:
        if path.exists() and (path / "models").exists():
            return path

    return None

def categorize_model(filename: str) -> str | None:
    """Determine which folder a model belongs in based on filename."""
    lower_name = filename.lower()

    for pattern, folder in MODEL_PATTERNS.items():
        if pattern.lower() in lower_name:
            return folder

    # Check by extension
    if filename.endswith(('.safetensors', '.pth', '.bin', '.ckpt')):
        if 'xl' in lower_name or 'sdxl' in lower_name:
            # Could be checkpoint, LoRA, or ControlNet
            if 'lora' in lower_name:
                return 'loras'
            elif any(x in lower_name for x in ['control', 'canny', 'depth', 'openpose']):
                return 'controlnet'
            else:
                return 'checkpoints'
        elif 'sd15' in lower_name or 'v1-5' in lower_name:
            if 'lora' in lower_name:
                return 'loras'
            elif any(x in lower_name for x in ['control', 'canny', 'depth', 'openpose']):
                return 'controlnet'
            else:
                return 'checkpoints'

    return None

def organize_models(source_dir: Path, comfyui_path: Path, dry_run: bool = True):
    """Organize models from source directory to ComfyUI folders."""
    models_dir = comfyui_path / "models"

    if not models_dir.exists():
        print(f"ERROR: Models directory not found: {models_dir}")
        return

    # Find all model files
    model_extensions = ('.safetensors', '.pth', '.bin', '.ckpt', '.pt')
    model_files = []

    for ext in model_extensions:
        model_files.extend(source_dir.glob(f"*{ext}"))
        model_files.extend(source_dir.glob(f"**/*{ext}"))  # Recursive

    print(f"Found {len(model_files)} model files in {source_dir}")
    print()

    # Categorize and move
    moved = 0
    skipped = 0

    for model_file in model_files:
        category = categorize_model(model_file.name)

        if category:
            dest_dir = models_dir / category
            dest_file = dest_dir / model_file.name

            # Create directory if it doesn't exist
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)

            # Check if file already exists
            if dest_file.exists():
                print(f"⏭️  SKIP (exists): {model_file.name}")
                skipped += 1
                continue

            # Move or simulate move
            if dry_run:
                print(f"📋 WOULD MOVE: {model_file.name}")
                print(f"   → {dest_dir}")
            else:
                try:
                    shutil.copy2(model_file, dest_file)
                    print(f"✅ MOVED: {model_file.name}")
                    print(f"   → {dest_dir}")
                    moved += 1
                except Exception as e:
                    print(f"❌ ERROR: {model_file.name} - {e}")
                    continue
        else:
            print(f"❓ UNKNOWN: {model_file.name} (skipping)")
            skipped += 1

        print()

    print("\n" + "="*60)
    if dry_run:
        print("DRY RUN COMPLETE - No files were actually moved")
        print(f"Would move: {moved} files")
    else:
        print("ORGANIZATION COMPLETE")
        print(f"Moved: {moved} files")
    print(f"Skipped: {skipped} files")
    print()

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Organize downloaded models for ComfyUI")
    parser.add_argument("source", type=Path, help="Directory containing downloaded models")
    parser.add_argument("--comfyui", type=Path, help="Path to ComfyUI installation (auto-detected if not provided)")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry-run)")

    args = parser.parse_args()

    # Validate source directory
    if not args.source.exists():
        print(f"ERROR: Source directory not found: {args.source}")
        return 1

    # Find ComfyUI installation
    comfyui_path = args.comfyui
    if not comfyui_path:
        comfyui_path = find_comfyui_path()
        if not comfyui_path:
            print("ERROR: Could not find ComfyUI installation.")
            print("Please specify path with --comfyui flag")
            return 1
        print(f"Found ComfyUI at: {comfyui_path}")

    if not comfyui_path.exists():
        print(f"ERROR: ComfyUI directory not found: {comfyui_path}")
        return 1

    # Organize models
    dry_run = not args.execute
    if dry_run:
        print("\n🔍 DRY RUN MODE - No files will be moved")
        print("Use --execute flag to actually move files\n")

    organize_models(args.source, comfyui_path, dry_run=dry_run)

    return 0

if __name__ == "__main__":
    exit(main())
