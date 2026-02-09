"""
Image Store - manages generated images on the filesystem.

Directory structure:
  data/images/{session_id}/stage_{N}/{generation_id}.png
  data/images/{session_id}/stage_{N}/{generation_id}_thumb.jpg
  data/uploads/{session_id}/{filename}
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (256, 256)


class ImageStore:
    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.images_dir = self.base_dir / "images"
        self.uploads_dir = self.base_dir / "uploads"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def _session_stage_dir(self, session_id: str, stage: int) -> Path:
        d = self.images_dir / session_id / f"stage_{stage}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save_image(
        self,
        session_id: str,
        stage: int,
        generation_id: str,
        image_bytes: bytes,
    ) -> tuple[str, str]:
        """
        Save full image and generate thumbnail.
        Returns (image_path, thumbnail_path) relative to base_dir.
        """
        stage_dir = self._session_stage_dir(session_id, stage)

        # Save full image
        image_path = stage_dir / f"{generation_id}.png"
        image_path.write_bytes(image_bytes)

        # Generate and save thumbnail
        thumb_path = stage_dir / f"{generation_id}_thumb.jpg"
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(str(thumb_path), "JPEG", quality=85)
        except Exception:
            logger.exception("Failed to create thumbnail for %s", generation_id)
            thumb_path = image_path  # fallback to full image

        rel_image = str(image_path.relative_to(self.base_dir))
        rel_thumb = str(thumb_path.relative_to(self.base_dir))
        return rel_image, rel_thumb

    async def get_image(self, relative_path: str) -> bytes:
        """Read image bytes from a path relative to base_dir."""
        full_path = self.base_dir / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Image not found: {relative_path}")
        return full_path.read_bytes()

    async def save_upload(
        self,
        session_id: str,
        filename: str,
        image_bytes: bytes,
    ) -> str:
        """Save an uploaded image for img2img. Returns path relative to base_dir."""
        upload_dir = self.uploads_dir / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / filename
        dest.write_bytes(image_bytes)
        return str(dest.relative_to(self.base_dir))

    async def delete_stage_unselected(
        self,
        session_id: str,
        stage: int,
        keep_ids: set[str],
    ) -> int:
        """
        Delete unselected images from a stage. Returns count of deleted files.
        Keeps images whose generation_id is in keep_ids.
        """
        stage_dir = self.images_dir / session_id / f"stage_{stage}"
        if not stage_dir.exists():
            return 0

        deleted = 0
        for f in stage_dir.iterdir():
            # Extract generation_id from filename (e.g., "abc123.png" or "abc123_thumb.jpg")
            gen_id = f.stem.replace("_thumb", "")
            if gen_id not in keep_ids:
                f.unlink()
                deleted += 1

        return deleted

    async def delete_session(self, session_id: str) -> int:
        """Delete all images for a session. Returns count of deleted files."""
        deleted = 0
        for d in [self.images_dir / session_id, self.uploads_dir / session_id]:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                        deleted += 1
                # Remove empty directories
                for sub in sorted(d.rglob("*"), reverse=True):
                    if sub.is_dir():
                        try:
                            sub.rmdir()
                        except OSError:
                            pass
                try:
                    d.rmdir()
                except OSError:
                    pass

        return deleted

    async def get_session_disk_usage(self, session_id: str) -> int:
        """Return total bytes used by a session's images."""
        total = 0
        for d in [self.images_dir / session_id, self.uploads_dir / session_id]:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
        return total
