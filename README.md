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


# Member 3: Incident and Resource Management

## Responsibilities

- Store reports and preserve Member 1 and Member 2 outputs.
- Consolidate related reports into incidents.
- Update incident needs, severity, and timestamps.
- Store synthetic response resources.
- Recommend available nearby resources and response departments.
- Provide incident, resource, and lifecycle APIs.

## Setup on Windows

Run these commands from the backend folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m member3.init_db
.\.venv\Scripts\python.exe -m member3.import_resources
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Place synthetic_resources.csv and anchors.csv in backend/data.

The first model use may require downloads. OCR also requires the
external Tesseract application; installing pytesseract alone does
not install it.

Swagger documentation: http://127.0.0.1:8000/docs

init_db creates missing tables without deleting existing records.
It does not migrate existing table columns.

The resource importer inserts missing IDs and preserves existing
records and availability on repeated runs.

## APIs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /analyze-text | Analyze, save, and consolidate a text report |
| POST | /analyze | Analyze optional media; save and consolidate when text is supplied |
| GET | /incidents | List incidents and report counts |
| GET | /incidents/{incident_id} | Read incident details and linked report evidence |
| GET | /resources | Browse resources with pagination and filters |
| GET | /incidents/{incident_id}/resources | Recommend resources and departments |
| PATCH | /incidents/{incident_id}/status | Update lifecycle status |

Resource browsing parameters:
limit (1–100), offset, resource_type, availability.

Recommendation parameters:
radius_km (greater than 0, up to 100), per_need (1–10).

## Consolidation rules

Candidates must be OPEN or IN_PROGRESS and not REJECTED.
They must have the same incident type, matching location names,
and coordinates within 1 km.

Candidate reports must have been received during the preceding
24 hours. This uses receipt time, not verified event time.

A unique exact-text match is preferred. Otherwise, a unique
incident with a report similarity score of at least 0.80 is used.

The distance, time, and similarity settings are provisional.
They have not been validated as operational thresholds.

Non-crisis and OLD reports remain saved without an incident.
Multiple possible matches currently lead to a new PENDING
incident; there is no dedicated ambiguity-review workflow yet.

Newly linked reports combine needs, retain the highest reported
severity, and update the timestamp.

## Resource recommendations

Recommendations use capabilities, availability, straight-line
distance, and initial resource-type suitability rules.

The default radius is 25 km. Only AVAILABLE resources qualify.
Unfulfilled needs appear in unmet_needs.

For fire incidents:
- Fire suppression requires a fire unit.
- Rescue candidates are fire units or rescue teams.
- Medical candidates are ambulances or medical teams.

Candidate lists do not allocate or reserve resources. One resource
can appear under multiple needs. Recommendations require human
approval and do not trigger dispatch.

Departments are prototype categories, not verified local offices.

## Member 4 integration

Lifecycle values: OPEN, IN_PROGRESS, RESOLVED.

Verification values expected by this module:
PENDING, VERIFIED, REJECTED.

IN_PROGRESS requires verification_status to be VERIFIED.
Member 4 must implement the authorized human-verification
workflow and agree on these values before integration.

Status updates currently have no authentication, authorization,
or audit history. They are intended for local prototype testing.

Incident-detail timestamps explicitly include the UTC offset.
The frontend can convert them to IST for display.

## Dataset

synthetic_resources.csv contains 5,006 fictional resources.
anchors.csv provides supporting geographic metadata.

Resource availability is simulated. Coordinates are illustrative
and unverified. Regional coverage does not establish exhaustive
coverage or nationwide operational effectiveness.

The current importer stores only fields supported by Resource.
Additional state, capacity, and provenance fields remain in CSV.

## Known limitations

- Media-only submissions are analyzed but not stored.
- Original uploaded media is deleted after processing.
- Unassigned reports have no dedicated review-list API.
- Locality coordinates may represent multiple separate events.
- Similarity thresholds need labelled evaluation.
- Incident updates do not invalidate earlier human verification.
- Resource suitability rules are incomplete for other scenarios.
- Recommendations do not consider road travel time or capacity.
- Incident lists and linked-report responses are not paginated.
- Concurrent submissions may create duplicate incidents.

## Checks

```powershell
.\.venv\Scripts\python.exe -m member3.test_location_matching
.\.venv\Scripts\python.exe -m member3.test_incident_update
.\.venv\Scripts\python.exe -m member3.test_similarity
```

The similarity script prints example scores; it is not a benchmark.
test_save_report writes a sample report into the configured database.

Manual API checks covered repeated and reworded reports, separate
locations, resource filtering, shortages, lifecycle restrictions,
incident details, and a text-and-image submission.
These checks establish prototype behavior for the tested cases,
not real-world accuracy or publication readiness.