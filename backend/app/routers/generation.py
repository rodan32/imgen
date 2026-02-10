"""Generation routes - single and batch image generation."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_session
from ..models.orm import GenerationORM, SessionORM
from ..models.schemas import (
    BatchGenerationRequest,
    BatchGenerationResponse,
    GenerationRequest,
    GenerationResponse,
    GenerationResultResponse,
)
from ..services.task_router import TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generation"])


@router.post("", response_model=GenerationResponse)
async def generate_image(
    req: GenerationRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Queue a single image generation."""
    # Verify session exists
    result = await db.execute(select(SessionORM).where(SessionORM.id == req.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get services from app state
    task_router = request.app.state.task_router
    workflow_engine = request.app.state.workflow_engine
    client_pool = request.app.state.client_pool
    image_store = request.app.state.image_store
    aggregator = request.app.state.progress_aggregator
    gpu_registry = request.app.state.gpu_registry

    # Route to GPU
    task_type = TaskType(req.task_type.value)
    try:
        gpu_node = await task_router.route(
            task_type, req.preferred_gpu, req.model_family.value
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Select workflow template
    template_name = req.workflow_template or workflow_engine.select_template(
        req.model_family.value,
        is_img2img=req.source_image_id is not None,
        has_loras=len(req.loras) > 0,
    )

    # Create generation record
    generation_id = str(uuid.uuid4())
    gen_record = GenerationORM(
        id=generation_id,
        session_id=req.session_id,
        stage=session.current_stage,
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        model_family=req.model_family.value,
        checkpoint=req.checkpoint,
        task_type=req.task_type.value,
        parameters={
            "width": req.width,
            "height": req.height,
            "steps": req.steps,
            "cfg_scale": req.cfg_scale,
            "denoise_strength": req.denoise_strength,
            "sampler": req.sampler,
            "scheduler": req.scheduler,
        },
        loras=[l.model_dump() for l in req.loras],
        gpu_id=gpu_node.id,
        seed=req.seed if req.seed != -1 else random.randint(0, 2**32 - 1),
        width=req.width,
        height=req.height,
        steps=req.steps,
        cfg_scale=req.cfg_scale,
        denoise_strength=req.denoise_strength,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    db.add(gen_record)
    await db.commit()

    # Build workflow
    params = {
        "prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "model_family": req.model_family.value,
        "checkpoint": req.checkpoint,
        "width": req.width,
        "height": req.height,
        "steps": req.steps,
        "cfg_scale": req.cfg_scale,
        "denoise_strength": req.denoise_strength,
        "sampler": req.sampler,
        "scheduler": req.scheduler,
        "seed": gen_record.seed,
        "filename_prefix": f"imgen_{req.session_id}_{generation_id}",
        "loras": [l.model_dump() for l in req.loras],
    }

    # Handle img2img: upload source image to ComfyUI
    if req.source_image_id:
        source_gen = await db.execute(
            select(GenerationORM).where(GenerationORM.id == req.source_image_id)
        )
        source = source_gen.scalar_one_or_none()
        if source and source.image_path:
            source_bytes = await image_store.get_image(source.image_path)
            client = client_pool.get_client(gpu_node.id)
            upload_result = await client.upload_image(
                source_bytes, f"{generation_id}_source.png"
            )
            params["source_image_filename"] = upload_result.get("name", f"{generation_id}_source.png")

    workflow = workflow_engine.build_workflow(template_name, params, gpu_node)

    # Submit to ComfyUI in background
    asyncio.create_task(
        _run_generation(
            generation_id, req.session_id, session.current_stage,
            gpu_node.id, workflow,
            request.app,
        )
    )

    return GenerationResponse(
        id=generation_id,
        session_id=req.session_id,
        status="queued",
        gpu_id=gpu_node.id,
    )


@router.post("/batch", response_model=BatchGenerationResponse)
async def generate_batch(
    req: BatchGenerationRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Queue a batch of image generations distributed across GPUs."""
    # Verify session
    result = await db.execute(select(SessionORM).where(SessionORM.id == req.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    task_router = request.app.state.task_router
    lora_discovery = request.app.state.lora_discovery
    checkpoint_learning = request.app.state.checkpoint_learning
    preference_learning = request.app.state.preference_learning
    task_type = TaskType(req.task_type.value)

    # Auto-LoRA: Discover relevant LoRAs if enabled and no LoRAs specified
    discovered_loras = []
    if req.auto_lora and not req.loras:
        available_loras = lora_discovery.get_cached_loras(None)
        if available_loras:
            lora_specs = lora_discovery.suggest_lora_specs(req.prompt, available_loras, count=3)
            discovered_loras = lora_specs
            logger.info(
                "Auto-LoRA discovered %d LoRAs for prompt: %s",
                len(discovered_loras),
                [l["name"] for l in discovered_loras]
            )

    # Checkpoint Selection: Context-aware via PreferenceLearning
    checkpoints_to_test = []
    if req.explore_mode and not req.checkpoint:
        # Get available checkpoints for this tier
        tier = req.task_type.value
        pool_key = f"{req.model_family.value}_{tier}"
        available_checkpoints = checkpoint_learning.checkpoint_pools.get(pool_key, [])

        if not available_checkpoints:
            # Fallback to default
            default = "beenyouLite_l15.safetensors" if req.model_family.value == "sd15" else "epicrealismXL_pureFix.safetensors"
            checkpoints_to_test = [default]
            logger.info("No checkpoint pool for %s, using default: %s", pool_key, default)
        else:
            # Use PreferenceLearning to recommend best checkpoint for this prompt
            recommended_checkpoint, confidence = await preference_learning.recommend_checkpoint(
                db=db,
                prompt=req.prompt,
                available_checkpoints=available_checkpoints,
            )

            logger.info(
                "Context-aware checkpoint recommendation: %s (confidence: %.2f) for prompt: %s",
                recommended_checkpoint, confidence, req.prompt[:60]
            )

            if confidence > 0.5 and tier != "draft":
                # High confidence + not draft stage: exploit best checkpoint
                checkpoints_to_test = [recommended_checkpoint]
                logger.info("High confidence (%.2f), using single checkpoint: %s", confidence, recommended_checkpoint)
            elif confidence > 0.3:
                # Medium confidence: exploit best + explore 1 backup
                checkpoints_to_test = [recommended_checkpoint]
                # Add a second checkpoint for exploration
                for ckpt in available_checkpoints:
                    if ckpt != recommended_checkpoint:
                        checkpoints_to_test.append(ckpt)
                        break
                logger.info("Medium confidence (%.2f), testing top 2: %s", confidence, checkpoints_to_test)
            else:
                # Low confidence: explore multiple checkpoints (original behavior)
                checkpoints_to_test = available_checkpoints[:3]
                logger.info("Low confidence (%.2f), exploring %d checkpoints: %s", confidence, len(checkpoints_to_test), checkpoints_to_test)
    else:
        # Use single checkpoint (specified or default)
        checkpoints_to_test = [req.checkpoint] if req.checkpoint else [None]

    # Distribute batch across checkpoints
    checkpoint_distribution = checkpoint_learning.distribute_batch_across_checkpoints(
        req.count, checkpoints_to_test
    )

    # Get GPU distribution
    try:
        assignments = await task_router.route_batch(
            task_type, req.count, req.model_family.value
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    batch_id = str(uuid.uuid4())

    # Generate seed sequence
    base_seed = req.seed_start if req.seed_start != -1 else random.randint(0, 2**32 - 1)

    gpu_assignments = {node.id: count for node, count in assignments}

    # Assign checkpoints to each generation index
    checkpoint_assignments = []
    for checkpoint, count in checkpoint_distribution.items():
        checkpoint_assignments.extend([checkpoint] * count)

    # Create individual generation tasks
    index = 0
    for gpu_node, count in assignments:
        for i in range(count):
            seed = base_seed + index
            generation_id = str(uuid.uuid4())

            # Get checkpoint for this generation
            assigned_checkpoint = checkpoint_assignments[index] if index < len(checkpoint_assignments) else req.checkpoint

            # Determine LoRAs: use discovered LoRAs or specified LoRAs
            loras_to_use = req.loras if req.loras else discovered_loras

            gen_record = GenerationORM(
                id=generation_id,
                session_id=req.session_id,
                stage=session.current_stage,
                batch_id=batch_id,
                batch_index=index,
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                model_family=req.model_family.value,
                checkpoint=assigned_checkpoint,
                task_type=req.task_type.value,
                loras=[l if isinstance(l, dict) else l for l in loras_to_use],
                gpu_id=gpu_node.id,
                seed=seed,
                width=req.width,
                height=req.height,
                steps=req.steps,
                cfg_scale=req.cfg_scale,
                denoise_strength=1.0,
                status="queued",
                created_at=datetime.now(timezone.utc),
            )
            db.add(gen_record)

            # Build workflow for this specific generation
            params = {
                "prompt": req.prompt,
                "negative_prompt": req.negative_prompt,
                "model_family": req.model_family.value,
                "checkpoint": assigned_checkpoint,
                "width": req.width,
                "height": req.height,
                "steps": req.steps,
                "cfg_scale": req.cfg_scale,
                "denoise_strength": 1.0,
                "sampler": req.sampler,
                "scheduler": req.scheduler,
                "seed": seed,
                "filename_prefix": f"imgen_{req.session_id}_{generation_id}",
                "loras": [l if isinstance(l, dict) else l for l in loras_to_use],
            }

            workflow_engine = request.app.state.workflow_engine
            template_name = workflow_engine.select_template(
                req.model_family.value, is_img2img=False, has_loras=len(req.loras) > 0
            )
            workflow = workflow_engine.build_workflow(template_name, params, gpu_node)

            # Launch each generation as a background task
            asyncio.create_task(
                _run_generation(
                    generation_id, req.session_id, session.current_stage,
                    gpu_node.id, workflow,
                    request.app,
                    batch_id=batch_id,
                    batch_index=index,
                    batch_total=req.count,
                )
            )
            index += 1

    await db.commit()

    return BatchGenerationResponse(
        batch_id=batch_id,
        session_id=req.session_id,
        total_count=req.count,
        gpu_assignments=gpu_assignments,
    )


@router.get("/{generation_id}", response_model=GenerationResultResponse)
async def get_generation(
    generation_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Get details of a single generation."""
    result = await db.execute(
        select(GenerationORM).where(GenerationORM.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")

    return GenerationResultResponse(
        id=gen.id,
        session_id=gen.session_id,
        stage=gen.stage,
        prompt=gen.prompt or "",
        negative_prompt=gen.negative_prompt or "",
        image_url=f"/api/generate/{gen.id}/image",
        thumbnail_url=f"/api/generate/{gen.id}/thumbnail",
        gpu_id=gen.gpu_id,
        generation_time_ms=gen.generation_time_ms,
        parameters=gen.parameters,
        seed=gen.seed,
        created_at=gen.created_at,
    )


@router.get("/{generation_id}/image")
async def get_generation_image(
    generation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Get the full-size generated image."""
    result = await db.execute(
        select(GenerationORM).where(GenerationORM.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen or not gen.image_path:
        raise HTTPException(status_code=404, detail="Image not found")

    image_store = request.app.state.image_store
    image_bytes = await image_store.get_image(gen.image_path)
    return Response(content=image_bytes, media_type="image/png")


@router.get("/{generation_id}/thumbnail")
async def get_generation_thumbnail(
    generation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Get the thumbnail of a generated image."""
    result = await db.execute(
        select(GenerationORM).where(GenerationORM.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen or not gen.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    image_store = request.app.state.image_store
    image_bytes = await image_store.get_image(gen.thumbnail_path)
    return Response(content=image_bytes, media_type="image/jpeg")


# --- Background task ---

async def _run_generation(
    generation_id: str,
    session_id: str,
    stage: int,
    gpu_id: str,
    workflow: dict,
    app,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_total: int | None = None,
) -> None:
    """
    Background task: submit workflow to ComfyUI, wait for completion,
    fetch images, save to disk, update DB.
    """
    client_pool = app.state.client_pool
    gpu_registry = app.state.gpu_registry
    image_store = app.state.image_store
    aggregator = app.state.progress_aggregator

    client = client_pool.get_client(gpu_id)
    gpu_registry.increment_load(gpu_id)

    try:
        # Submit to ComfyUI
        start_time = time.monotonic()
        prompt_id = await client.queue_prompt(workflow)

        # Register for progress tracking
        aggregator.register_prompt(prompt_id, session_id, generation_id, gpu_id)

        # Update DB status
        async with app.state.db_session() as db:
            result = await db.execute(
                select(GenerationORM).where(GenerationORM.id == generation_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = "generating"
                gen.prompt_comfy_id = prompt_id
                await db.commit()

        # Wait for completion
        history = await client.poll_until_complete(prompt_id, timeout=300.0)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Fetch output images
        images = await client.get_output_images(history)
        if not images:
            raise Exception("No images in ComfyUI output")

        # Save first output image
        filename, img_bytes = images[0]
        image_path, thumb_path = await image_store.save_image(
            session_id, stage, generation_id, img_bytes
        )

        # Update DB with results
        async with app.state.db_session() as db:
            result = await db.execute(
                select(GenerationORM).where(GenerationORM.id == generation_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = "complete"
                gen.image_path = image_path
                gen.thumbnail_path = thumb_path
                gen.generation_time_ms = elapsed_ms
                await db.commit()

        # Send completion event to frontend
        complete_msg = {
            "type": "generation_complete",
            "generationId": generation_id,
            "imageUrl": f"/api/generate/{generation_id}/image",
            "thumbnailUrl": f"/api/generate/{generation_id}/thumbnail",
            "seed": gen.seed if gen else 0,
            "generationTimeMs": elapsed_ms,
            "gpuId": gpu_id,
            "stage": gen.stage if gen else 0,
        }

        if batch_id is not None:
            # Count completed in this batch
            async with app.state.db_session() as db:
                from sqlalchemy import func
                result = await db.execute(
                    select(func.count()).where(
                        GenerationORM.batch_id == batch_id,
                        GenerationORM.status == "complete",
                    )
                )
                completed = result.scalar() or 0

            complete_msg = {
                "type": "batch_progress",
                "batchId": batch_id,
                "completed": completed,
                "total": batch_total or 0,
                "latestResult": {
                    "generationId": generation_id,
                    "imageUrl": f"/api/generate/{generation_id}/image",
                    "thumbnailUrl": f"/api/generate/{generation_id}/thumbnail",
                    "index": batch_index or 0,
                    "stage": gen.stage if gen else 0,
                },
            }

            if completed >= (batch_total or 0):
                # Also send batch_complete
                await aggregator._send_to_session(session_id, complete_msg)
                complete_msg = {
                    "type": "batch_complete",
                    "batchId": batch_id,
                    "total": batch_total or 0,
                    "totalTimeMs": elapsed_ms,  # approximate
                }

        await aggregator._send_to_session(session_id, complete_msg)

        logger.info(
            "Generation %s complete on %s in %dms",
            generation_id, gpu_id, elapsed_ms,
        )

    except Exception as e:
        logger.exception("Generation %s failed on %s", generation_id, gpu_id)

        # Update DB with error
        async with app.state.db_session() as db:
            result = await db.execute(
                select(GenerationORM).where(GenerationORM.id == generation_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = "error"
                gen.error_message = str(e)
                await db.commit()

        # Notify frontend
        await aggregator._send_to_session(session_id, {
            "type": "error",
            "generationId": generation_id,
            "message": str(e),
        })

    finally:
        gpu_registry.decrement_load(gpu_id)
        aggregator.unregister_prompt(prompt_id if 'prompt_id' in dir() else "")
