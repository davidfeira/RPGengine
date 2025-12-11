"""
Image generation module for RPG Engine.
Generates scene images using OpenAI's API or local Stable Diffusion.

Supports:
- SDXL Turbo: Fast, high quality, 1-4 steps, 8GB VRAM
- SD 1.5: Older but lightweight, 20+ steps, 4-6GB VRAM
- OpenAI API models: DALL-E 2/3, GPT-Image-1
"""

import base64
import logging
from io import BytesIO

from prompts import VISUAL_DIRECTOR_PROMPT

logger = logging.getLogger(__name__)

# Local SD pipelines (lazy loaded)
_local_pipe = None
_local_model_name = None  # Track which model is loaded
_local_model_loading = False
_last_error = None  # Store last error for UI display


def get_last_error() -> str | None:
    """Get the last image generation error message."""
    return _last_error


def clear_last_error():
    """Clear the last error."""
    global _last_error
    _last_error = None


def is_local_model(model: str) -> bool:
    """Check if model is a local model."""
    return "local" in model.lower() or model.startswith("sd-") or model.startswith("sdxl")


def get_local_pipeline(model: str = "sdxl-turbo"):
    """Get or create the local Stable Diffusion pipeline.

    Args:
        model: Model identifier - "sdxl-turbo" or "sd-1.5"
    """
    global _local_pipe, _local_model_name, _local_model_loading

    # Normalize model name
    if "sdxl" in model.lower() or "turbo" in model.lower():
        model_key = "sdxl-turbo"
    else:
        model_key = "sd-1.5"

    # Return existing pipeline if same model
    if _local_pipe is not None and _local_model_name == model_key:
        return _local_pipe

    # Unload previous model if different
    if _local_pipe is not None and _local_model_name != model_key:
        logger.info(f"Unloading {_local_model_name} to load {model_key}...")
        _local_pipe = None
        _local_model_name = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if _local_model_loading:
        return None

    _local_model_loading = True

    try:
        import torch

        if model_key == "sdxl-turbo":
            from diffusers import AutoPipelineForText2Image

            logger.info("Loading SDXL Turbo model...")

            _local_pipe = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/sdxl-turbo",
                torch_dtype=torch.float16,
                variant="fp16",
            )
        else:
            from diffusers import StableDiffusionPipeline

            logger.info("Loading Stable Diffusion 1.5 model...")

            _local_pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16,
                safety_checker=None,
                requires_safety_checker=False,
            )

        # Move to GPU
        if torch.cuda.is_available():
            _local_pipe = _local_pipe.to("cuda")
            logger.info(f"{model_key} loaded on CUDA")
        else:
            logger.warning("CUDA not available, using CPU (will be slow)")

        # Enable memory optimizations
        _local_pipe.enable_attention_slicing()

        _local_model_name = model_key
        _local_model_loading = False
        return _local_pipe

    except ImportError as e:
        logger.error(f"Failed to import diffusers/torch: {e}")
        logger.error("Install with: pip install diffusers torch accelerate --index-url https://download.pytorch.org/whl/cu121")
        _local_model_loading = False
        return None
    except Exception as e:
        logger.error(f"Failed to load local model: {e}")
        _local_model_loading = False
        return None


def preload_local_model(model: str = "sdxl-turbo"):
    """Preload the local model (call from title screen)."""
    if _local_pipe is None or _local_model_name != model:
        get_local_pipeline(model)


def is_local_model_ready() -> bool:
    """Check if local model is loaded and ready."""
    return _local_pipe is not None


def generate_local_image(
    prompt: str,
    model: str = "sdxl-turbo",
    steps: int = 4,
    width: int = 512,
    height: int = 512,
    guidance_scale: float = 0.0,
    negative_prompt: str = "",
    progress_callback=None
) -> bytes | None:
    """Generate image using local Stable Diffusion.

    Args:
        prompt: The image prompt
        model: Model to use - "sdxl-turbo" or "sd-1.5"
        steps: Number of inference steps (1-4 for SDXL Turbo, 10-35 for SD 1.5)
        width: Image width
        height: Image height
        guidance_scale: CFG scale (0.0 for SDXL Turbo, 5-15 for SD 1.5)
        negative_prompt: What to avoid in the image (ignored for SDXL Turbo)
        progress_callback: Optional callback(step, total_steps) for progress updates
    """
    pipe = get_local_pipeline(model)
    if pipe is None:
        logger.error("Local pipeline not available")
        return None

    # Determine if using SDXL Turbo
    is_turbo = "sdxl" in model.lower() or "turbo" in model.lower()

    try:
        # Truncate long prompts
        max_len = 200 if is_turbo else 300
        if len(prompt) > max_len:
            prompt = prompt[:max_len]

        logger.debug(f"Local {'SDXL Turbo' if is_turbo else 'SD 1.5'} prompt: {prompt[:100]}...")
        logger.debug(f"Params: {width}x{height}, CFG={guidance_scale}, steps={steps}")

        # Create a callback wrapper for the diffusers pipeline
        def step_callback(pipe, step, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(step + 1, steps)
            return callback_kwargs

        # Generate image - SDXL Turbo uses different params
        if is_turbo:
            # SDXL Turbo: no negative prompt, guidance_scale=0.0, 1-4 steps
            result = pipe(
                prompt,
                num_inference_steps=steps,
                guidance_scale=0.0,  # SDXL Turbo requires 0.0
                width=width,
                height=height,
                callback_on_step_end=step_callback,
            )
        else:
            # SD 1.5: standard params
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

        logger.info(f"Generated image: {len(image_data)} bytes")
        return image_data

    except Exception as e:
        global _last_error
        error_str = str(e)
        # Simplify common errors for display
        if "out of memory" in error_str.lower() or "CUDA" in error_str:
            _last_error = "GPU out of memory - try lower resolution"
        else:
            _last_error = error_str[:80]  # Truncate long errors
        logger.error(f"Local image generation failed: {e}")
        return None


def generate_visual_prompt(
    character_visual: str,
    recent_narrative: str,
    style: str,
    client,
    model: str = "gpt-4o-mini",
) -> tuple[str, dict]:
    """Use LLM to generate an optimized image prompt from story context.

    Args:
        character_visual: Visual description of the character
        recent_narrative: Recent story text (last 2-3 turns)
        style: Art style for the image
        client: OpenAI client instance
        model: LLM model to use for prompt generation

    Returns:
        Tuple of (generated_prompt, token_usage_dict)
    """
    prompt = VISUAL_DIRECTOR_PROMPT.format(
        character_visual=character_visual,
        recent_narrative=recent_narrative,
        style=style,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
        )

        generated_prompt = response.choices[0].message.content.strip()
        token_usage = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
        }

        logger.info(f"Visual director generated prompt: {generated_prompt[:100]}...")
        return generated_prompt, token_usage

    except Exception as e:
        logger.error(f"Visual director failed: {e}")
        # Fall back to simple truncation
        fallback = f"{style}, {recent_narrative[-200:]}"
        return fallback, {"prompt": 0, "completion": 0}


def generate_scene_image(
    narrative: str,
    character: str,
    style: str,
    client,
    model: str = "sdxl-turbo (local)",
    quality: str = "low",
    size: str = "1024x1024",
    progress_callback=None,
    # Local SD settings
    local_resolution: str = "512x512",
    local_guidance: str = "medium (7.5)",
    local_negative_prompt: str = "",
    # Visual director prompt (if provided, use directly instead of building from narrative)
    visual_prompt: str = "",
) -> bytes | None:
    """Generate an image for the current scene.

    Args:
        narrative: The current narrative/scene description (unused if visual_prompt provided)
        character: The character description (unused if visual_prompt provided)
        style: Art style prefix (e.g., "fantasy illustration")
        client: OpenAI client instance (unused for local models)
        model: Image model to use
        quality: Image quality (low, medium, high) - affects steps for local
        size: Image size (ignored for local)
        progress_callback: Optional callback(step, total_steps) for local model progress
        local_resolution: Resolution for local SD (e.g., "512x512")
        local_guidance: Guidance scale preset for local SD
        local_negative_prompt: Negative prompt for local SD
        visual_prompt: Pre-built prompt from visual director (if provided, used directly)

    Returns:
        Image bytes (PNG) or None if generation failed
    """
    is_local = is_local_model(model)
    is_turbo = "sdxl" in model.lower() or "turbo" in model.lower()

    # If visual director provided a prompt, use it directly (it's already optimized)
    if visual_prompt:
        prompt = visual_prompt
        # Only truncate if absolutely necessary for model limits
        if is_turbo and len(prompt) > 250:
            prompt = prompt[:250]
        elif is_local and len(prompt) > 350:
            prompt = prompt[:350]
        elif len(prompt) > 4000:
            prompt = prompt[:4000]
    else:
        # Fallback: Build the image prompt from narrative context
        # Extract key scene elements (last 200 chars for local models, more for API)
        if is_local:
            # For local models, keep prompts shorter and more focused
            # Take last ~150 chars of narrative for scene context
            scene_excerpt = narrative[-150:] if len(narrative) > 150 else narrative
            # Put scene first, then style, then brief character mention
            # This ensures the scene actually influences the image
            prompt = f"{style}, {scene_excerpt}. Character: {character[:80]}"
        else:
            # API models can handle longer prompts
            scene_excerpt = narrative[-800:] if len(narrative) > 800 else narrative
            prompt = f"{style}, {character}. Scene: {scene_excerpt}"

        # Truncate for model limits
        if is_turbo:
            # SDXL Turbo works best with ~77 tokens, roughly 200 chars
            if len(prompt) > 200:
                prompt = prompt[:200]
        elif is_local:
            if len(prompt) > 300:
                prompt = prompt[:300]
        else:
            if len(prompt) > 4000:
                prompt = prompt[:4000]

    logger.debug(f"Image generation prompt: {prompt[:200]}...")

    # Handle local models
    if is_local:
        if is_turbo:
            # SDXL Turbo: 1-4 steps, quality affects step count
            steps_map = {"low": 1, "medium": 2, "high": 4}
            steps = steps_map.get(quality, 2)
            guidance_scale = 0.0  # SDXL Turbo requires 0.0
        else:
            # SD 1.5: 10-35 steps
            steps_map = {"low": 10, "medium": 20, "high": 35}
            steps = steps_map.get(quality, 15)
            # Parse guidance scale from preset string like "medium (7.5)"
            guidance_map = {"low (5)": 5.0, "medium (7.5)": 7.5, "high (10)": 10.0, "very high (15)": 15.0}
            guidance_scale = guidance_map.get(local_guidance, 7.5)

        # Parse resolution
        try:
            width, height = map(int, local_resolution.split("x"))
        except:
            width, height = 512, 512

        return generate_local_image(
            prompt,
            model=model,
            steps=steps,
            width=width,
            height=height,
            guidance_scale=guidance_scale,
            negative_prompt=local_negative_prompt if not is_turbo else "",
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
    model: str = "sdxl-turbo (local)",
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

    is_turbo = "sdxl" in model.lower() or "turbo" in model.lower()

    if is_turbo:
        # SDXL Turbo: 1-4 steps
        steps_map = {"low": 1, "medium": 2, "high": 4}
        steps = steps_map.get(quality, 2)
        guidance_scale = 0.0
    else:
        # SD 1.5: 10-35 steps
        steps_map = {"low": 10, "medium": 20, "high": 35}
        steps = steps_map.get(quality, 15)
        guidance_map = {"low (5)": 5.0, "medium (7.5)": 7.5, "high (10)": 10.0, "very high (15)": 15.0}
        guidance_scale = guidance_map.get(local_guidance, 7.5)

    # Parse resolution
    try:
        width, height = map(int, local_resolution.split("x"))
    except:
        width, height = 512, 512

    logger.info(f"Generating test image ({model}): {width}x{height}, steps={steps}, CFG={guidance_scale}")

    start_time = time.time()
    image_data = generate_local_image(
        test_prompt,
        model=model,
        steps=steps,
        width=width,
        height=height,
        guidance_scale=guidance_scale,
        negative_prompt=local_negative_prompt if not is_turbo else "",
        progress_callback=progress_callback
    )
    elapsed = time.time() - start_time

    logger.info(f"Test image generated in {elapsed:.1f}s")
    return image_data, elapsed
