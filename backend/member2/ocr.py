import os
import shutil
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Union
from PIL import Image, ExifTags, ImageEnhance, ImageFilter

import pytesseract

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from .temporal import extract_temporal_evidence


def is_tesseract_available() -> bool:
    """Checks whether the system tesseract binary is installed and executable."""
    if shutil.which("tesseract") is not None:
        return True
    common_paths = [
        r"C:\msys64\ucrt64\bin\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def load_image(image_input: Union[str, os.PathLike, Image.Image]) -> Optional[Image.Image]:
    """
    Safely opens and validates an image from a file path or PIL Image instance.
    Returns None if image cannot be loaded.
    """
    if isinstance(image_input, Image.Image):
        return image_input
    if not isinstance(image_input, (str, os.PathLike)):
        return None
    if not os.path.isfile(image_input):
        return None
    try:
        img = Image.open(image_input)
        img.verify()  # Verify integrity
        # Reopen for actual processing after verify
        return Image.open(image_input)
    except Exception:
        return None


def extract_image_metadata(
    image_input: Union[str, os.PathLike, Image.Image],
    reference_date: Optional[date] = None
) -> List[EvidenceItem]:
    """
    Extracts EXIF temporal metadata from an image.
    Produces EvidenceItem with source=METADATA.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    evidence: List[EvidenceItem] = []
    img = None

    if isinstance(image_input, (str, os.PathLike)) and os.path.isfile(image_input):
        try:
            img = Image.open(image_input)
        except Exception:
            img = None
    elif isinstance(image_input, Image.Image):
        img = image_input

    if img is None:
        evidence.append(
            EvidenceItem(
                source=EvidenceSource.METADATA,
                finding="Invalid or missing image; metadata unavailable",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.10
            )
        )
        return evidence

    exif_data: Dict[str, Any] = {}
    try:
        raw_exif = img.getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                exif_data[tag_name] = value
    except Exception:
        pass

    # Look for standard datetime fields: DateTimeOriginal, DateTime, DateTimeDigitized
    datetime_str = (
        exif_data.get("DateTimeOriginal")
        or exif_data.get("DateTime")
        or exif_data.get("DateTimeDigitized")
    )

    if datetime_str and isinstance(datetime_str, str):
        # Format usually: "YYYY:MM:DD HH:MM:SS"
        parsed_dt: Optional[datetime] = None
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d", "%Y-%m-%d"):
            try:
                parsed_dt = datetime.strptime(datetime_str.strip()[:19], fmt)
                break
            except ValueError:
                continue

        if parsed_dt:
            exif_date = parsed_dt.date()
            diff_days = (reference_date - exif_date).days
            if diff_days > 7:
                polarity = EvidencePolarity.OLD
                weight = 0.85
            elif 0 <= diff_days <= 7:
                polarity = EvidencePolarity.CURRENT
                weight = 0.80
            else:
                polarity = EvidencePolarity.NEUTRAL
                weight = 0.40

            evidence.append(
                EvidenceItem(
                    source=EvidenceSource.METADATA,
                    finding=f"Image EXIF timestamp detected: '{datetime_str}' ({exif_date.isoformat()})",
                    polarity=polarity,
                    weight=weight,
                    details={
                        "exif_datetime": datetime_str,
                        "date": exif_date.isoformat(),
                        "days_from_reference": diff_days
                    }
                )
            )
            return evidence

    # If no temporal EXIF was found
    evidence.append(
        EvidenceItem(
            source=EvidenceSource.METADATA,
            finding="No EXIF temporal metadata found in image",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.20
        )
    )
    return evidence


def preprocess_image_for_ocr(img: Image.Image) -> List[Image.Image]:
    """
    Produces candidate preprocessed PIL images to optimize OCR text extraction:
    1. Base image (upscaled if resolution is low).
    2. Grayscale with enhanced contrast.
    3. Contrast enhanced + sharpened.
    4. Contrast enhanced + binarized thresholding.
    """
    candidates = []

    # Ensure RGB or L
    base = img.convert("RGB") if img.mode not in ("RGB", "L") else img.copy()

    # 1. Upscale if low resolution to help Tesseract detect small fonts / banners
    w, h = base.size
    if w < 1000 or h < 600:
        scale_factor = max(1.5, min(2.5, 1200.0 / max(w, 1)))
        new_w, new_h = int(w * scale_factor), int(h * scale_factor)
        base = base.resize((new_w, new_h), Image.Resampling.LANCZOS)

    candidates.append(base)

    # 2. Grayscale + high contrast
    gray = base.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    contrast_img = enhancer.enhance(2.0)
    candidates.append(contrast_img)

    # 3. Sharpened contrast
    sharpened = contrast_img.filter(ImageFilter.SHARPEN)
    candidates.append(sharpened)

    # 4. Binary thresholding for overlay / ticker text
    threshold_img = contrast_img.point(lambda p: 255 if p > 130 else 0)
    candidates.append(threshold_img)

    return candidates


def run_ocr_with_status(image_input: Union[str, os.PathLike, Image.Image]) -> Dict[str, Any]:
    """
    Runs Tesseract OCR with adaptive preprocessing and multiple PSM segmentation modes.
    Returns:
      {
        "status": "SUCCESS" | "EXECUTED_NO_TEXT" | "UNAVAILABLE" | "FAILED",
        "text": str,
        "error": Optional[str]
      }
    """
    if not is_tesseract_available():
        return {
            "status": "UNAVAILABLE",
            "text": "",
            "error": "Tesseract binary not installed or not in system PATH"
        }

    img = load_image(image_input)
    if img is None:
        return {
            "status": "FAILED",
            "text": "",
            "error": "Invalid or unreadable image file/data"
        }

    best_text = ""
    last_error = None
    executed_cleanly = False
    try:
        candidates = preprocess_image_for_ocr(img)
        psm_modes = ["--psm 3", "--psm 11", "--psm 6"]

        for cand in candidates:
            for psm in psm_modes:
                try:
                    text = pytesseract.image_to_string(cand, config=psm).strip()
                    executed_cleanly = True
                    if len(text) > len(best_text):
                        best_text = text
                        if len(best_text) >= 25:
                            break
                except Exception as exc:
                    last_error = exc
                    continue
            if len(best_text) >= 25:
                break

        if best_text:
            return {
                "status": "SUCCESS",
                "text": best_text,
                "error": None
            }
        elif executed_cleanly:
            return {
                "status": "EXECUTED_NO_TEXT",
                "text": "",
                "error": None
            }
        else:
            return {
                "status": "FAILED",
                "text": "",
                "error": str(last_error or "OCR processing failed across all passes")
            }
    except Exception as exc:
        return {
            "status": "FAILED",
            "text": "",
            "error": str(exc)
        }


def extract_ocr_text(image_input: Union[str, os.PathLike, Image.Image]) -> str:
    """
    Runs Tesseract OCR on the given image.
    Returns extracted text string, or empty string on failure / unavailable binary / no text.
    """
    res = run_ocr_with_status(image_input)
    return res.get("text", "")


def extract_ocr_evidence(
    image_input: Union[str, os.PathLike, Image.Image],
    reference_date: Optional[date] = None,
    ocr_text_override: Optional[str] = None
) -> List[EvidenceItem]:
    """
    Extracts OCR text from an image and runs it through the temporal evidence extractor.
    Returns list of EvidenceItem with source=OCR, preserving status and extracted text.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    if ocr_text_override is not None:
        text = ocr_text_override.strip()
        status = "SUCCESS" if text else "EXECUTED_NO_TEXT"
        error_msg = None
    else:
        res = run_ocr_with_status(image_input)
        text = res["text"]
        status = res["status"]
        error_msg = res["error"]

    if status == "UNAVAILABLE":
        return [
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding="OCR engine is unavailable (Tesseract not installed or not in system PATH)",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.0,
                details={"status": "UNAVAILABLE", "ocr_text": "", "error": error_msg}
            )
        ]

    if status == "FAILED":
        return [
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding=f"OCR execution failed: {error_msg or 'Unknown error'}",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.0,
                details={"status": "FAILED", "ocr_text": "", "error": error_msg}
            )
        ]

    if not text:
        return [
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding="OCR executed successfully: no readable text detected in media",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.20,
                details={"status": "EXECUTED_NO_TEXT", "ocr_text": ""}
            )
        ]

    # Process extracted text through Phase 2 temporal extractor
    temporal_items = extract_temporal_evidence(
        text=text,
        reference_date=reference_date,
        source=EvidenceSource.OCR
    )

    if not temporal_items:
        return [
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding=f"OCR extracted text '{text[:60]}...' but no temporal expressions were found",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.25,
                details={"status": "SUCCESS", "ocr_text": text}
            )
        ]

    # Enhance finding prefix to clarify it originated from OCR visual inspection
    for item in temporal_items:
        item.finding = f"Visual OCR evidence: {item.finding}"
        if item.details is not None:
            item.details["status"] = "SUCCESS"
            item.details["ocr_text"] = text
        else:
            item.details = {"status": "SUCCESS", "ocr_text": text}

    return temporal_items


def extract_image_evidence(
    image_input: Union[str, os.PathLike, Image.Image],
    reference_date: Optional[date] = None,
    ocr_text_override: Optional[str] = None
) -> List[EvidenceItem]:
    """
    Combined multimodal image evidence extractor:
    - Metadata / EXIF temporal evidence
    - OCR text & visual temporal claim evidence
    """
    metadata_evidence = extract_image_metadata(image_input, reference_date=reference_date)
    ocr_evidence = extract_ocr_evidence(
        image_input,
        reference_date=reference_date,
        ocr_text_override=ocr_text_override
    )
    return metadata_evidence + ocr_evidence
