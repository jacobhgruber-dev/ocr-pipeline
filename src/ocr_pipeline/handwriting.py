"""TrOCR handwriting recognition engine.

Uses Microsoft's TrOCR model (``microsoft/trocr-base-handwritten``)
for high-quality handwriting OCR via HuggingFace Transformers.

TrOCR is a pure Transformer model (ViT encoder + RoBERTa decoder)
pre-trained on 17.9M synthetic handwritten text lines. It achieves
3.42% CER on the IAM handwriting benchmark.

**Limitations**:
- Text-line only — requires a text-detection frontend (Surya or EasyOCR).
- CPU inference is slow (~2-5 seconds per text line).  GPU recommended.
- Not suitable for high-throughput batch processing without GPU.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Default TrOCR model (MIT license, 334M params)
_DEFAULT_TROCR_MODEL = "microsoft/trocr-base-handwritten"

# Minimum confidence threshold for accepting a text line
_MIN_CONFIDENCE = 0.3

# Maximum text lines to process per page (safety cap for CPU)
_MAX_LINES_PER_PAGE = 50


def detect_text_lines(image_path: Path, detector: str = "surya") -> list[dict]:
    """Detect text lines in an image using Surya or EasyOCR.

    Args:
        image_path: Path to the page image (PNG recommended).
        detector: ``"surya"`` (default) or ``"easyocr"``.

    Returns:
        List of dicts with keys: ``bbox`` (x0, y0, x1, y1), ``image`` (PIL crop).
    """
    img = Image.open(image_path).convert("RGB")

    if detector == "surya":
        try:
            from surya.detection import DetectionPredictor

            predictor = DetectionPredictor()
            results = predictor([img])

            lines: list[dict] = []
            for result in results:
                for line in result.text_lines:
                    bbox = line.bbox  # (x0, y0, x1, y1)
                    crop = img.crop(bbox)
                    lines.append({"bbox": bbox, "image": crop})
            return lines
        except ImportError:
            logger.debug("Surya not available — falling back to EasyOCR detector")
            detector = "easyocr"

    if detector == "easyocr":
        try:
            import easyocr

            reader = easyocr.Reader(["en"], gpu=False)
            # Use EasyOCR's CRAFT detector only (skip recognizer)
            results = reader.detect(str(image_path))
            if not results or not results[0]:
                return []

            lines: list[dict] = []
            for box in results[0]:
                x0, y0 = int(box[0][0]), int(box[0][1])
                x1, y1 = int(box[2][0]), int(box[2][1])
                crop = img.crop((x0, y0, x1, y1))
                lines.append({"bbox": (x0, y0, x1, y1), "image": crop})
            return lines
        except ImportError:
            logger.warning("Neither Surya nor EasyOCR available for text detection.")
            return [{"bbox": (0, 0, img.width, img.height), "image": img}]

    return [{"bbox": (0, 0, img.width, img.height), "image": img}]


def recognize_handwriting(
    image_path: Path,
    model_name: str = _DEFAULT_TROCR_MODEL,
    detector: str = "surya",
    quantize: bool = False,
) -> tuple[str, list[dict]]:
    """Recognize handwriting in an image using TrOCR.

    Args:
        image_path: Path to the page image.
        model_name: HuggingFace model ID for TrOCR.
        detector: Text-line detector to use (``"surya"`` or ``"easyocr"``).
        quantize: If True, load model in 8-bit for CPU.

    Returns:
        ``(full_text, line_results)`` where:
        - *full_text* is the concatenated recognized text.
        - *line_results* is a list of ``{"text": str, "bbox": tuple, "confidence": float}``.
    """
    t0 = time.perf_counter()

    try:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except ImportError:
        logger.warning("transformers not installed — install with: pip install transformers")
        return "", []

    # Load model (cached after first use)
    try:
        processor = TrOCRProcessor.from_pretrained(model_name)
        load_kwargs = {}
        if quantize:
            load_kwargs["load_in_8bit"] = True
        model = VisionEncoderDecoderModel.from_pretrained(model_name, **load_kwargs)
    except Exception as exc:
        logger.warning("Failed to load TrOCR model '%s': %s", model_name, exc)
        return "", []

    # Detect text lines
    lines = detect_text_lines(image_path, detector=detector)
    if len(lines) > _MAX_LINES_PER_PAGE:
        logger.info("TrOCR: capping %d lines to %d", len(lines), _MAX_LINES_PER_PAGE)
        lines = lines[:_MAX_LINES_PER_PAGE]

    results: list[dict] = []
    text_parts: list[str] = []

    for i, line in enumerate(lines):
        try:
            crop = line["image"]
            pixel_values = processor(images=crop, return_tensors="pt").pixel_values
            generated_ids = model.generate(pixel_values, max_new_tokens=128)
            line_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            # Estimate confidence from generation probability
            confidence = 1.0 if len(generated_ids[0]) > 2 else 0.5

            if line_text.strip():
                results.append({
                    "text": line_text.strip(),
                    "bbox": line["bbox"],
                    "confidence": confidence,
                })
                text_parts.append(line_text.strip())
        except Exception as exc:
            logger.debug("TrOCR failed on line %d: %s", i, exc)

    elapsed = time.perf_counter() - t0
    logger.info(
        "TrOCR: %d lines in %.1fs (model=%s, detector=%s)",
        len(results),
        elapsed,
        model_name,
        detector,
    )

    return "\n".join(text_parts), results
