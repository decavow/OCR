# Debug utilities for PaddleOCR-VL pipeline inspection
#
# Controlled by DEBUG_OCR env var. When enabled, saves to:
#   {TEMP_DIR}/{job_id}/debug/
#     page_N_input.png            — original image
#     page_N_prepared.png         — after upscaling (if changed)
#     page_N_raw_{tier}.json      — raw PPStructure/PaddleOCR output
#     page_N_regions_{tier}.json  — extracted structured regions
#     page_N_debug_boxes.png      — bounding boxes drawn on image
#     pipeline_log.json           — step-by-step pipeline summary

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageDraw

from app.config import settings
from app.core.context import job_id_ctx

logger = logging.getLogger(__name__)

# Bounding box colors per region type (RGB)
REGION_COLORS = {
    "title":  (220, 50, 50),
    "text":   (50, 100, 220),
    "table":  (50, 180, 50),
    "figure": (220, 180, 50),
    "list":   (160, 50, 200),
}
DEFAULT_COLOR = (128, 128, 128)


class DebugContext:
    """Collects and saves intermediate pipeline data when DEBUG_OCR=true.

    All public methods are no-ops when debug is disabled, so callers
    don't need conditional checks.
    """

    def __init__(self):
        self.enabled = settings.debug_ocr
        self.job_id = job_id_ctx.get() or "unknown"
        self.pipeline_steps: List[Dict] = []
        self._start_time = time.monotonic()
        self._input_saved: set = set()

        if self.enabled:
            self.debug_dir = Path(settings.temp_dir) / self.job_id / "debug"
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[DEBUG] Output dir: {self.debug_dir}")
        else:
            self.debug_dir = None

    def _log_step(self, step: str, data: dict) -> None:
        elapsed = round(time.monotonic() - self._start_time, 3)
        entry = {"step": step, "elapsed_s": elapsed, **data}
        self.pipeline_steps.append(entry)
        logger.info(f"[DEBUG] {step}: {json.dumps(data, default=str)[:500]}")

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def save_input_image(self, image: np.ndarray, page_idx: int) -> None:
        """Save original input image (once per page)."""
        if not self.enabled or page_idx in self._input_saved:
            return
        self._input_saved.add(page_idx)
        try:
            path = self.debug_dir / f"page_{page_idx + 1}_input.png"
            Image.fromarray(image).save(path)
            h, w = image.shape[:2]
            self._log_step("input_image", {
                "page": page_idx + 1, "size": f"{w}x{h}",
            })
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save input image p{page_idx + 1}: {e}")

    def save_prepared_image(
        self, original: np.ndarray, prepared: np.ndarray, page_idx: int
    ) -> None:
        """Save prepared image if dimensions changed from original."""
        if not self.enabled:
            return
        try:
            oh, ow = original.shape[:2]
            ph, pw = prepared.shape[:2]
            if (oh, ow) != (ph, pw):
                path = self.debug_dir / f"page_{page_idx + 1}_prepared.png"
                Image.fromarray(prepared).save(path)
                self._log_step("prepare_image", {
                    "page": page_idx + 1,
                    "original": f"{ow}x{oh}",
                    "prepared": f"{pw}x{ph}",
                    "scale": round(pw / ow, 2),
                })
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save prepared image p{page_idx + 1}: {e}")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def save_raw_engine_output(
        self, raw_result: list, page_idx: int, tier: str
    ) -> None:
        """Save raw PPStructure/PaddleOCR output as JSON."""
        if not self.enabled:
            return
        try:
            serializable = _make_serializable(raw_result)
            path = self.debug_dir / f"page_{page_idx + 1}_raw_{tier}.json"
            path.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

            type_counts = {}
            if raw_result:
                for item in raw_result:
                    rtype = item.get("type", "?") if isinstance(item, dict) else "?"
                    type_counts[rtype] = type_counts.get(rtype, 0) + 1

            self._log_step(f"raw_output_{tier}", {
                "page": page_idx + 1,
                "raw_regions": len(raw_result) if raw_result else 0,
                "types": type_counts,
            })
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save raw output p{page_idx + 1}: {e}")

    # ------------------------------------------------------------------
    # Postprocessing
    # ------------------------------------------------------------------

    def save_extracted_regions(
        self, page_result: dict, page_idx: int, tier: str
    ) -> None:
        """Save extracted region data as JSON with statistics."""
        if not self.enabled:
            return
        try:
            path = self.debug_dir / f"page_{page_idx + 1}_regions_{tier}.json"
            path.write_text(
                json.dumps(page_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            regions = page_result.get("regions", [])
            type_counts = {}
            confidences = []
            for r in regions:
                t = r.get("type", "?")
                type_counts[t] = type_counts.get(t, 0) + 1
                if "confidence" in r:
                    confidences.append(r["confidence"])

            avg_conf = (
                round(sum(confidences) / len(confidences), 4) if confidences else 0.0
            )
            self._log_step(f"regions_{tier}", {
                "page": page_idx + 1,
                "total": len(regions),
                "by_type": type_counts,
                "avg_confidence": avg_conf,
            })
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save regions p{page_idx + 1}: {e}")

    def save_debug_image(
        self, image: np.ndarray, page_result: dict, page_idx: int
    ) -> None:
        """Draw labeled bounding boxes on image and save as PNG.

        Overwrites on each tier — final file shows boxes from last tier.
        """
        if not self.enabled:
            return
        try:
            pil_img = Image.fromarray(image).copy()
            draw = ImageDraw.Draw(pil_img)

            for region in page_result.get("regions", []):
                bbox = region.get("bbox", [0, 0, 0, 0])
                rtype = region.get("type", "text")
                color = REGION_COLORS.get(rtype, DEFAULT_COLOR)

                x1, y1, x2, y2 = bbox
                draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

                # Label
                label = rtype.upper()
                if "confidence" in region:
                    label += f" {region['confidence']:.2f}"

                label_y = max(y1 - 16, 0)
                text_bbox = draw.textbbox((x1 + 2, label_y), label)
                draw.rectangle(text_bbox, fill=color)
                draw.text((x1 + 2, label_y), label, fill=(255, 255, 255))

            path = self.debug_dir / f"page_{page_idx + 1}_debug_boxes.png"
            pil_img.save(path)
            self._log_step("debug_image", {"page": page_idx + 1})
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save debug image p{page_idx + 1}: {e}")

    # ------------------------------------------------------------------
    # Quality & fallback tracking
    # ------------------------------------------------------------------

    def log_quality_assessment(
        self, pages: list, passed: bool, tier: str
    ) -> None:
        total = sum(len(p.get("regions", [])) for p in pages)
        self._log_step("quality_check", {
            "tier": tier, "passed": passed, "total_regions": total,
        })

    def log_fallback(self, from_tier: str, to_tier: str, reason: str) -> None:
        self._log_step("fallback", {
            "from": from_tier, "to": to_tier, "reason": reason,
        })

    # ------------------------------------------------------------------
    # Pipeline summary
    # ------------------------------------------------------------------

    def save_pipeline_summary(self) -> None:
        """Save complete pipeline log to JSON."""
        if not self.enabled:
            return
        try:
            elapsed = round(time.monotonic() - self._start_time, 3)
            summary = {
                "job_id": self.job_id,
                "total_elapsed_s": elapsed,
                "total_steps": len(self.pipeline_steps),
                "steps": self.pipeline_steps,
            }
            path = self.debug_dir / "pipeline_log.json"
            path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info(f"[DEBUG] Pipeline log saved: {path} ({elapsed}s)")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save pipeline summary: {e}")


def _make_serializable(obj) -> Any:
    """Convert PPStructure output to JSON-serializable form.

    Handles numpy arrays (large ones summarized as shape string),
    numpy scalars, nested dicts/lists, and arbitrary objects.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        # Small arrays (coords, bboxes) → full list; large arrays (images) → summary
        if obj.size <= 50:
            return obj.tolist()
        return f"<ndarray shape={obj.shape} dtype={obj.dtype}>"
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    return str(obj)
