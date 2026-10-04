import os
import shutil
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Union
from PIL import Image, ExifTags

import pytesseract

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource
from .temporal import extract_temporal_evidence


def is_tesseract_available() -> bool:
    """Checks whether the system tesseract binary is installed and executable."""
    return shutil.which("tesseract") is not None


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


def extract_ocr_text(image_input: Union[str, os.PathLike, Image.Image]) -> str:
    """
    Runs Tesseract OCR on the given image.
    Returns extracted text string, or empty string on failure / unavailable binary.
    """
    if not is_tesseract_available():
        return ""

    img = load_image(image_input)
    if img is None:
        return ""

    try:
        # Convert to RGB if needed for consistent OCR
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        return text.strip() if text else ""
    except Exception:
        return ""


def extract_ocr_evidence(
    image_input: Union[str, os.PathLike, Image.Image],
    reference_date: Optional[date] = None,
    ocr_text_override: Optional[str] = None
) -> List[EvidenceItem]:
    """
    Extracts OCR text from an image and runs it through the temporal evidence extractor.
    Returns list of EvidenceItem with source=OCR.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    text = ocr_text_override if ocr_text_override is not None else extract_ocr_text(image_input)

    if not text or not text.strip():
        return [
            EvidenceItem(
                source=EvidenceSource.OCR,
                finding="No readable text detected in image via OCR",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.20
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
                details={"ocr_text": text}
            )
        ]

    # Enhance finding prefix to clarify it originated from OCR visual inspection
    for item in temporal_items:
        item.finding = f"Visual OCR evidence: {item.finding}"

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
