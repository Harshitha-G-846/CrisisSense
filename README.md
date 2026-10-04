# CrisisSense

An Agentic Multimodal Crisis Intelligence and Response Support System.

---

## Member 2: Multimodal & Currentness Verification

Member 2 is responsible for extracting multimodal evidence from fragmented crisis inputs (text, images, videos, audio) and performing explainable currentness verification.

### Pipeline Architecture

```
Input (Text, Image, Video, Audio, Context)
  │
  ├── Temporal Claim Extraction (temporal.py)
  ├── Contextual Corpus Alignment (reference.py)
  ├── Image Metadata & Visual OCR (ocr.py)
  ├── Video Frame Sampling & OCR (video.py)
  ├── Spoken Audio Speech-to-Text Claims (audio.py)
  └── Perceptual Reused-Media Detection (reuse.py)
        │
        ▼
   Evidence Aggregation (List[EvidenceItem])
        │
        ▼
   Deterministic Evidence Fusion (fusion.py)
        │
        ▼
   CurrentnessResult
   ├── Verdict: CURRENT | OLD | UNCERTAIN
   ├── Confidence: [0.0, 1.0] (heuristic)
   ├── Action: ALLOW | HUMAN_VERIFICATION_REQUIRED
   ├── Conflicts Detected: List[str]
   └── Full Evidence Provenance
```

### Core Technologies
- **Python**: Core runtime and Pydantic schemas.
- **OpenCV (`cv2`)**: Video decoding, frame sampling, and metadata inspection.
- **Pillow (`PIL`)**: Image loading, EXIF extraction, and format conversions.
- **Tesseract / `pytesseract`**: Optical character recognition for image and video frame timestamps/tickers.
- **`faster-whisper`**: Local, offline speech-to-text transcription for spoken temporal assertions.
- **Perceptual Hashing (`imagehash`)**: pHash computation and Hamming distance matching for reused/recycled media detection.

### Dataset Scope & Research Limitations
- **CrisisMMD**: Used strictly for multimodal crisis understanding and multimodal text+image evaluation. CrisisMMD does **not** provide ground-truth temporal currentness labels and is not treated as a direct currentness dataset.
- **CrisisLexT26**: Used as a local reference corpus for historical crisis event metadata and contextual alignment.
- **Heuristic Fusion**: Decision boundaries, source reliability weights, and confidence values are deterministic heuristic baselines designed for safety; empirical calibration is conducted in Phase 11.
