# CrisisSense

An Agentic Multimodal Crisis Intelligence and Response Support System.

# Member 1: Crisis Analysis & Natural language processing

## Overview

Member 1 is responsible for the **text-based crisis analysis module** of CrisisSense.

This module processes unstructured crisis-related text and converts it into structured information that can be used by the rest of the CrisisSense system.

The module analyzes a text report and identifies:

* Whether the text is related to a crisis
* The type of incident
* The type of information contained in the report
* Severity of the incident
* Required assistance or needs
* Location mentioned in the report

The output is returned as structured JSON through the CrisisSense backend API.

---


### Main components

1. **Crisis Detection**

   * Determines whether the input text represents a crisis-related report.
   * Uses TF-IDF feature extraction with Logistic Regression.
   * Trained using the CrisisLexT26 dataset.

2. **Incident Type Classification**

   * Identifies the type of incident mentioned in the text.
   * Current categories include:

     * Building Collapse
     * Cyclone
     * Earthquake
     * Explosion
     * Fire
     * Flood
     * Landslide
     * Other
     * Road Accident
     * Wildfire

3. **Information Type Classification**

   * Identifies the type of information provided in a crisis-related message.
   * Categories include:

     * Affected individuals
     * Caution and advice
     * Donations and volunteering
     * Infrastructure and utilities
     * Other Useful Information
     * Sympathy and support

4. **Severity Detection**

   * Extracts the severity level from the text.
   * Current output levels:

     * LOW
     * MEDIUM
     * HIGH

5. **Needs Extraction**

   * Identifies assistance requested in the text.
   * Examples include:

     * Rescue
     * Medical assistance
     * Food
     * Water
     * Shelter

6. **Location Extraction**

   * Detects locations mentioned in crisis reports.
   * Supports Indian states, cities and predefined local locations.
   * Uses normalization for capitalization and spacing differences.
   * Uses fuzzy similarity matching to handle spelling mistakes.
   * Uses OpenStreetMap Nominatim for geocoding and coordinates.

---

## Pipeline

The Member 1 pipeline follows this flow:

```text
                Input Crisis Text
                       |
                       v
              Text Preprocessing
                       |
          +------------+------------+
          |            |            |
          v            v            v
   Crisis Detection  Incident   Information
                     Type        Type
                   Classification Classification
          |            |            |
          +------------+------------+
                       |
              +--------+--------+
              |        |        |
              v        v        v
          Severity   Needs    Location
              |        |        |
              +--------+--------+
                       |
                       v
              Structured JSON
                       |
                       v
                 FastAPI API
```

---

## Project Structure

```text
backend/
│
├── member1/
│   ├── __init__.py
│   ├── data_preprocessing.py
│   ├── crisis_classifier.py
│   ├── incident_classifier.py
│   ├── incident_type.py
│   ├── location_extractor.py
│   ├── severity.py
│   ├── needs_extractor.py
│   └── pipeline.py
│
├── data/
│   ├── CrisisLexT26/
│   └── crisissense_incident_type_dataset.csv
│
├── models/
│   ├── crisis_classifier.pkl
│   ├── tfidf_vectorizer.pkl
│   ├── information_type_classifier.pkl
│   ├── information_type_word_vectorizer.pkl
│   ├── information_type_char_vectorizer.pkl
│   ├── incident_type_classifier.pkl
│   └── incident_type_vectorizer.pkl
│
├── main.py
└── requirements.txt
```

---

## Dataset

### CrisisLexT26

The crisis detection and information-type classification components use the **CrisisLexT26** dataset.

The dataset contains crisis-related tweets collected from multiple real-world crisis events.

The preprocessing pipeline:

1. Loads the event CSV files.
2. Combines the datasets.
3. Removes duplicate tweets.
4. Cleans the text.
5. Processes crisis/informativeness labels.
6. Processes information-type labels.
7. Generates training data for the classification models.

### Dataset Statistics

After preprocessing:

```text
Original records:       27,933
Duplicate tweets:        2,625
Processed records:      25,245
```

The processed dataset contains information such as:

```text
Tweet Text
Information Source
Information Type
Informativeness
Event
Clean_Text
```

---

## Machine Learning Models

### 1. Crisis Classifier

```text
TF-IDF
   ↓
Logistic Regression
   ↓
Crisis / Not Crisis
```

Current test accuracy:

```text
92.76%
```

The model was trained using a stratified train/test split.

> Note: Accuracy alone does not represent the complete model performance because the classes are imbalanced. Recall and F1-score should also be considered.

---

### 2. Information Type Classifier

The information-type classifier uses both word-level and character-level TF-IDF features.

```text
                 Input Text
                     |
          +----------+----------+
          |                     |
     Word TF-IDF          Character TF-IDF
          |                     |
          +----------+----------+
                     |
                   HStack
                     |
                LinearSVC
                     |
                     v
             Information Type
```

Current test accuracy:

```text
71.42%
```

---

### 3. Incident Type Classifier

The incident classifier identifies the type of crisis event.

```text
Input Text
    ↓
TF-IDF
    ↓
Linear SVM
    ↓
Incident Type
```

The current prototype uses a labelled incident-type dataset containing ten incident categories.

---

## Location Extraction

Location extraction is designed to handle variations in how users mention locations.

### Exact matching

```text
Whitefield
Chennai
Assam
Rajarajeshwari Nagar
```

### Case normalization

The system treats different capitalization styles consistently:

```text
Whitefield
WHITEFIELD
whitefield
WhItEfIeLd
```

### Spacing variations

Location normalization can handle variations such as:

```text
Whitefield
White Field
```

### Spelling variations

Fuzzy similarity matching helps identify likely intended locations:

```text
Whitefeild  → Whitefield
Chenai      → Chennai
Hydrabad    → Hyderabad
Mumabi      → Mumbai
Banglore    → Bangalore
```

The similarity-based correction is applied against known location names rather than blindly correcting every word.

### Geocoding

After identifying a location, the system uses **OpenStreetMap Nominatim** to obtain:

* Display name
* City
* State
* Country
* Latitude
* Longitude

The system is not restricted to Bengaluru and can identify locations from different parts of India.

---

## Example

### Input

```text
A fire has occurred near Whitefeild and people need medical assistance.
```

### Processing

```text
Crisis Detection
       ↓
Crisis = True

Incident Classification
       ↓
Fire

Severity Detection
       ↓
High

Needs Extraction
       ↓
Medical assistance

Location Extraction
       ↓
Whitefeild
       ↓
Fuzzy matching
       ↓
Whitefield
       ↓
Geocoding
```

### Output

```json
{
  "is_crisis": true,
  "incident_type": "Fire",
  "information_type": "Affected individuals",
  "severity": "HIGH",
  "needs": [
    "medical"
  ],
  "locations": [
    {
      "text": "Whitefield",
      "city": "Bengaluru",
      "state": "Karnataka",
      "country": "India",
      "latitude": 12.9957428,
      "longitude": 77.7579489
    }
  ]
}
```

---

## API

The Member 1 pipeline is integrated with the CrisisSense FastAPI backend.

### Start the backend

From the `backend` directory:

```bash
uvicorn main:app --reload
```

The API is then available locally through the FastAPI server.

### Analyze text

```http
POST /analyze
```

Request:

```json
{
  "text": "A fire occurred near Whitefield and people need medical assistance."
}
```

The API returns the structured crisis analysis generated by the Member 1 pipeline.

---

## Technologies Used

| Technology              | Purpose                    |
| ----------------------- | -------------------------- |
| Python                  | Core development           |
| Scikit-learn            | Machine learning           |
| TF-IDF                  | Text feature extraction    |
| Logistic Regression     | Crisis classification      |
| LinearSVC               | Text classification        |
| Pandas                  | Dataset processing         |
| NumPy                   | Numerical operations       |
| SciPy                   | Sparse feature combination |
| Joblib                  | Model saving/loading       |
| FastAPI                 | Backend API                |
| Requests                | External API requests      |
| OpenStreetMap Nominatim | Location geocoding         |

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
