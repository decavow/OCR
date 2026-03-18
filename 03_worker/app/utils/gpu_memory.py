# GPU memory management utilities
# Prevents OOM during model initialization and processing

import logging
import os

logger = logging.getLogger(__name__)

# Default max GPU memory fraction (0.0-1.0). Set via GPU_MEMORY_FRACTION env var.
_DEFAULT_MEMORY_FRACTION = 0.85


def get_gpu_memory_info() -> dict:
    """Get current GPU memory usage.

    Returns dict with keys:
        allocated_mb, reserved_mb, free_mb, total_mb, utilization_pct
    Returns empty dict if GPU not available.
    """
    try:
        import paddle
        if not paddle.device.is_compiled_with_cuda():
            return {}

        allocated = paddle.device.cuda.memory_allocated() / (1024 ** 2)
        reserved = paddle.device.cuda.memory_reserved() / (1024 ** 2)

        # Try to get total GPU memory via nvidia-smi or paddle
        total_mb = _get_total_gpu_memory_mb()
        free_mb = total_mb - reserved if total_mb > 0 else 0
        utilization = (reserved / total_mb * 100) if total_mb > 0 else 0

        return {
            "allocated_mb": round(allocated, 1),
            "reserved_mb": round(reserved, 1),
            "free_mb": round(free_mb, 1),
            "total_mb": round(total_mb, 1),
            "utilization_pct": round(utilization, 1),
        }
    except Exception as e:
        logger.debug(f"Cannot get GPU memory info: {e}")
        return {}


def _get_total_gpu_memory_mb() -> float:
    """Get total GPU memory in MB."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return float(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    return 0.0


def log_gpu_memory(context: str = "") -> None:
    """Log current GPU memory usage."""
    info = get_gpu_memory_info()
    if not info:
        return
    prefix = f"[{context}] " if context else ""
    logger.info(
        f"{prefix}GPU memory: "
        f"allocated={info['allocated_mb']:.0f}MB, "
        f"reserved={info['reserved_mb']:.0f}MB, "
        f"free={info['free_mb']:.0f}MB, "
        f"total={info['total_mb']:.0f}MB "
        f"({info['utilization_pct']:.1f}% used)"
    )


def set_gpu_memory_fraction() -> None:
    """Set GPU memory fraction limit to prevent OOM.

    Reads GPU_MEMORY_FRACTION env var (default: 0.85).
    Must be called BEFORE any model initialization.
    """
    fraction = float(os.getenv("GPU_MEMORY_FRACTION", str(_DEFAULT_MEMORY_FRACTION)))
    fraction = max(0.1, min(1.0, fraction))

    try:
        import paddle
        if not paddle.device.is_compiled_with_cuda():
            logger.info("CUDA not available, skipping GPU memory fraction")
            return

        # PaddlePaddle: set memory fraction via flags
        os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", str(fraction))
        # Also set initial allocation size to avoid large upfront reservation
        os.environ.setdefault("FLAGS_initial_gpu_memory_in_mb", "256")
        # Enable garbage collection to reclaim unused memory
        os.environ.setdefault("FLAGS_eager_delete_tensor_gb", "0.0")

        logger.info(f"GPU memory fraction set to {fraction:.0%}")
    except ImportError:
        logger.debug("PaddlePaddle not installed, skipping GPU memory config")
    except Exception as e:
        logger.warning(f"Failed to set GPU memory fraction: {e}")


def check_gpu_available(min_free_mb: float = 512) -> bool:
    """Check if enough GPU memory is available for model loading.

    Args:
        min_free_mb: Minimum free GPU memory required (default 512MB).

    Returns:
        True if enough memory available or if GPU info unavailable.
    """
    info = get_gpu_memory_info()
    if not info or info["total_mb"] == 0:
        # Cannot determine — assume available
        return True

    if info["free_mb"] < min_free_mb:
        logger.warning(
            f"Low GPU memory: {info['free_mb']:.0f}MB free "
            f"(need {min_free_mb:.0f}MB). OOM risk!"
        )
        return False

    logger.info(f"GPU memory check OK: {info['free_mb']:.0f}MB free")
    return True


def cleanup_gpu_memory() -> None:
    """Aggressively free GPU memory.

    Clears CUDA cache and runs Python garbage collection.
    """
    # Python GC first
    import gc
    gc.collect()

    try:
        import paddle
        if paddle.device.is_compiled_with_cuda():
            paddle.device.cuda.empty_cache()
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"GPU cache cleanup failed: {e}")
