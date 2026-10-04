import glob
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource, Member1Context

# Default path relative to this file: backend/member2 -> backend/data/CrisisLexT26
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CRISISLEX_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data", "CrisisLexT26")
)

_CACHED_EVENTS: Optional[List[Dict[str, Any]]] = None


def load_reference_events(data_dir: Optional[str] = None, force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    Loads and caches event-level metadata from the local CrisisLexT26 corpus.
    Deterministic, offline, and lightweight.
    """
    global _CACHED_EVENTS
    if _CACHED_EVENTS is not None and not force_reload and data_dir is None:
        return _CACHED_EVENTS

    target_dir = data_dir or DEFAULT_CRISISLEX_DIR
    if not os.path.isdir(target_dir):
        return []

    event_files = sorted(glob.glob(os.path.join(target_dir, "*", "*-event_description.json")))
    events: List[Dict[str, Any]] = []

    for file_path in event_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        folder_name = os.path.basename(os.path.dirname(file_path))
        time_info = data.get("time", {}) or {}
        loc_info = data.get("location", {}) or {}
        cat_info = data.get("categorization", {}) or {}

        # Parse start and approximate end date
        start_day_str = time_info.get("start_day")
        start_date: Optional[date] = None
        end_date: Optional[date] = None
        duration = time_info.get("duration")

        if start_day_str:
            try:
                start_date = datetime.strptime(start_day_str, "%Y-%m-%d").date()
                if duration and isinstance(duration, (int, float)) and duration > 0:
                    end_date = start_date + timedelta(days=int(duration))
                else:
                    end_date = start_date
            except ValueError:
                pass

        events.append({
            "folder_name": folder_name,
            "name": data.get("name") or folder_name,
            "year": time_info.get("year"),
            "month": time_info.get("month"),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "duration_days": duration,
            "country": loc_info.get("country"),
            "location_description": loc_info.get("location_description"),
            "incident_type": cat_info.get("type"),
            "category": cat_info.get("category"),
            "sub_category": cat_info.get("sub_category"),
            "keywords": [k.lower() for k in data.get("keywords", []) if isinstance(k, str)]
        })

    if data_dir is None:
        _CACHED_EVENTS = events
    return events


def get_event_metadata(event_identifier: str, data_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves metadata for a specific event by folder name or event name.
    """
    events = load_reference_events(data_dir=data_dir)
    target = event_identifier.strip().lower()
    for ev in events:
        if ev["folder_name"].lower() == target or ev["name"].lower() == target:
            return ev
    return None


def find_matching_events(
    text: str,
    incident_type: Optional[str] = None,
    location: Optional[str] = None,
    data_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Finds CrisisLex historical events matching name, keywords, or location/type in the text.
    """
    if not text or not isinstance(text, str):
        return []

    events = load_reference_events(data_dir=data_dir)
    lower_text = text.lower()
    matched = []

    for ev in events:
        score = 0
        ev_name_clean = ev["name"].lower().replace("_", " ")
        ev_folder_clean = ev["folder_name"].lower().replace("_", " ")

        # Match by name or folder
        if ev_name_clean in lower_text or ev_folder_clean in lower_text:
            score += 2
        elif any(part in lower_text for part in ev_name_clean.split() if len(part) > 3):
            # Partial name overlap
            matching_parts = [p for p in ev_name_clean.split() if len(p) > 3 and p in lower_text]
            if len(matching_parts) >= 2:
                score += 1.5

        # Match by location description
        loc_desc = (ev["location_description"] or "").lower()
        if loc_desc and loc_desc in lower_text and len(loc_desc) > 3:
            score += 1

        # Match by keyword
        matched_kws = [kw for kw in ev["keywords"] if kw in lower_text and len(kw) > 3]
        if matched_kws:
            score += min(len(matched_kws) * 0.5, 2.0)

        # Contextual incident type match
        if incident_type and ev["incident_type"]:
            if incident_type.lower() in ev["incident_type"].lower():
                score += 0.5

        if score >= 1.5:
            matched.append((score, ev))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [ev for _, ev in matched]


def extract_reference_evidence(
    text: str,
    temporal_items: Optional[List[EvidenceItem]] = None,
    member1_context: Optional[Member1Context] = None,
    data_dir: Optional[str] = None
) -> List[EvidenceItem]:
    """
    Generates supporting reference-corpus evidence by comparing text and temporal clues
    against historical CrisisLex disaster metadata.
    """
    if not text or not isinstance(text, str):
        return []

    matched_events = find_matching_events(
        text=text,
        incident_type=member1_context.incident_type if member1_context else None,
        data_dir=data_dir
    )

    if not matched_events:
        return []

    evidence: List[EvidenceItem] = []
    top_event = matched_events[0]
    event_year = top_event.get("year")
    event_name = top_event.get("name")

    # Check if temporal items mention the historical year of the matched event
    has_matching_year = False
    if temporal_items:
        for t_item in temporal_items:
            details = t_item.details or {}
            item_year = details.get("year")
            if item_year and event_year and int(item_year) == int(event_year):
                has_matching_year = True
                break

    if has_matching_year:
        evidence.append(
            EvidenceItem(
                source=EvidenceSource.REFERENCE_CORPUS,
                finding=f"Event reference '{event_name}' aligns with historical CrisisLex occurrence ({event_year})",
                polarity=EvidencePolarity.OLD,
                weight=0.65,
                details={
                    "matched_event": top_event["folder_name"],
                    "event_name": event_name,
                    "event_year": event_year,
                    "start_date": top_event.get("start_date")
                }
            )
        )
    else:
        # Contextual match without explicit temporal confirmation
        evidence.append(
            EvidenceItem(
                source=EvidenceSource.REFERENCE_CORPUS,
                finding=f"Context references known historical event corpus entry '{event_name}'",
                polarity=EvidencePolarity.NEUTRAL,
                weight=0.35,
                details={
                    "matched_event": top_event["folder_name"],
                    "event_name": event_name,
                    "event_year": event_year
                }
            )
        )

    return evidence
