"""
Image generation module for RPG Engine.
Generates scene images using OpenAI's API or local Stable Diffusion.
"""

import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

# Local SD pipeline (lazy loaded)
_local_pipe = None
_local_model_loading = False


def is_local_model(model: str) -> bool:
    """Check if model is a local model."""
    return "local" in model.lower() or model.startswith("sd-")


def get_local_pipeline():
    """Get or create the local Stable Diffusion pipeline."""
    global _local_pipe, _local_model_loading

    if _local_pipe is not None:
        return _local_pipe

    if _local_model_loading:
        return None

    _local_model_loading = True

    try:
        import torch
        from diffusers import StableDiffusionPipeline

        logger.info("Loading Stable Diffusion model...")

        # Use float16 for faster inference on GPU
        _local_pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16,
            safety_checker=None,  # Disable NSFW filter for speed
            requires_safety_checker=False,
        )

        # Move to GPU
        if torch.cuda.is_available():
            _local_pipe = _local_pipe.to("cuda")
            logger.info("Stable Diffusion loaded on CUDA")
        else:
            logger.warning("CUDA not available, using CPU (will be slow)")

        # Enable memory optimizations
        _local_pipe.enable_attention_slicing()

        return _local_pipe

    except ImportError as e:
        logger.error(f"Failed to import diffusers/torch: {e}")
        logger.error("Install with: pip install diffusers torch --index-url https://download.pytorch.org/whl/cu121")
        _local_model_loading = False
        return None
    except Exception as e:
        logger.error(f"Failed to load local SD model: {e}")
        _local_model_loading = False
        return None


def preload_local_model():
    """Preload the local model (call from title screen)."""
    if _local_pipe is None:
        get_local_pipeline()


def is_local_model_ready() -> bool:
    """Check if local model is loaded and ready."""
    return _local_pipe is not None


def generate_local_image(
    prompt: str,
    steps: int = 20,
    width: int = 512,
    height: int = 512,
    guidance_scale: float = 7.5,
    negative_prompt: str = "",
    progress_callback=None
) -> bytes | None:
    """Generate image using local Stable Diffusion.

    Args:
        prompt: The image prompt
        steps: Number of inference steps
        width: Image width
        height: Image height
        guidance_scale: CFG scale (how closely to follow prompt)
        negative_prompt: What to avoid in the image
        progress_callback: Optional callback(step, total_steps) for progress updates
    """
    pipe = get_local_pipeline()
    if pipe is None:
        logger.error("Local SD pipeline not available")
        return None

    try:
        # SD 1.5 works best with shorter prompts
        if len(prompt) > 300:
            prompt = prompt[:300]

        logger.debug(f"Local SD prompt: {prompt[:100]}...")
        logger.debug(f"Local SD params: {width}x{height}, CFG={guidance_scale}, steps={steps}")

        # Create a callback wrapper for the diffusers pipeline
        def step_callback(pipe, step, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(step + 1, steps)  # step is 0-indexed
            return callback_kwargs

        # Generate image
        result = pipe(
            prompt,
            negative_prompt=negative_prompt if negative_prompt else None,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            callback_on_step_end=step_callback,
        )

        image = result.images[0]

        # Convert to bytes
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_data = buffer.getvalue()

        logger.info(f"Local SD generated image: {len(image_data)} bytes")
        return image_data

    except Exception as e:
        logger.error(f"Local image generation failed: {e}")
        return None


def generate_scene_image(
    narrative: str,
    character: str,
    style: str,
    client,
    model: str = "dall-e-3",
    quality: str = "low",
    size: str = "1024x1024",
    progress_callback=None,
    # Local SD settings
    local_resolution: str = "512x512",
    local_guidance: str = "medium (7.5)",
    local_negative_prompt: str = "",
) -> bytes | None:
    """Generate an image for the current scene.

    Args:
        narrative: The current narrative/scene description
        character: The character description
        style: Art style prefix (e.g., "fantasy illustration")
        client: OpenAI client instance (unused for local models)
        model: Image model to use
        quality: Image quality (low, medium, high) - affects steps for local
        size: Image size (ignored for local)
        progress_callback: Optional callback(step, total_steps) for local model progress
        local_resolution: Resolution for local SD (e.g., "512x512")
        local_guidance: Guidance scale preset for local SD
        local_negative_prompt: Negative prompt for local SD

    Returns:
        Image bytes (PNG) or None if generation failed
    """
    # Build the image prompt from narrative context
    scene_excerpt = narrative[-800:] if len(narrative) > 800 else narrative
    prompt = f"{style}, {character}. Scene: {scene_excerpt}"

    # Truncate for API limits
    if len(prompt) > 4000:
        prompt = prompt[:4000]

    logger.debug(f"Image generation prompt: {prompt[:200]}...")

    # Handle local models
    if is_local_model(model):
        # Map quality to inference steps (lower = faster but less detail)
        steps_map = {"low": 10, "medium": 20, "high": 35}
        steps = steps_map.get(quality, 15)

        # Parse resolution
        try:
            width, height = map(int, local_resolution.split("x"))
        except:
            width, height = 512, 512

        # Parse guidance scale from preset string like "medium (7.5)"
        guidance_map = {"low (5)": 5.0, "medium (7.5)": 7.5, "high (10)": 10.0, "very high (15)": 15.0}
        guidance_scale = guidance_map.get(local_guidance, 7.5)

        return generate_local_image(
            prompt,
            steps=steps,
            width=width,
            height=height,
            guidance_scale=guidance_scale,
            negative_prompt=local_negative_prompt,
            progress_callback=progress_callback
        )

    # API models
    try:
        if model.startswith("gpt-image-1"):
            response = client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size=size,
                quality=quality,
            )
            image_data = base64.b64decode(response.data[0].b64_json)
        else:
            # DALL-E 2/3
            dalle_quality = "standard" if quality == "low" else ("hd" if quality == "high" else "standard")
            response = client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size=size,
                quality=dalle_quality if model == "dall-e-3" else "standard",
                response_format="b64_json"
            )
            image_data = base64.b64decode(response.data[0].b64_json)

        logger.info(f"Generated image: {len(image_data)} bytes")
        return image_data

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None


def generate_test_image(
    quality: str = "low",
    local_resolution: str = "512x512",
    local_guidance: str = "medium (7.5)",
    local_negative_prompt: str = "",
    progress_callback=None
) -> tuple[bytes | None, float]:
    """Generate a test image to benchmark local SD settings.

    Returns:
        Tuple of (image_bytes, generation_time_seconds)
    """
    import time

    test_prompt = "fantasy landscape, mountains, river, sunset, detailed illustration"

    # Map quality to inference steps
    steps_map = {"low": 10, "medium": 20, "high": 35}
    steps = steps_map.get(quality, 15)

    # Parse resolution
    try:
        width, height = map(int, local_resolution.split("x"))
    except:
        width, height = 512, 512

    # Parse guidance scale
    guidance_map = {"low (5)": 5.0, "medium (7.5)": 7.5, "high (10)": 10.0, "very high (15)": 15.0}
    guidance_scale = guidance_map.get(local_guidance, 7.5)

    logger.info(f"Generating test image: {width}x{height}, steps={steps}, CFG={guidance_scale}")

    start_time = time.time()
    image_data = generate_local_image(
        test_prompt,
        steps=steps,
        width=width,
        height=height,
        guidance_scale=guidance_scale,
        negative_prompt=local_negative_prompt,
        progress_callback=progress_callback
    )
    elapsed = time.time() - start_time

    logger.info(f"Test image generated in {elapsed:.1f}s")
    return image_data, elapsed
