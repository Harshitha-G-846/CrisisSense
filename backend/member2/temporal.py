import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .schemas import EvidenceItem, EvidencePolarity, EvidenceSource

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "a": 1, "an": 1
}


def _spans_overlap(span1: Tuple[int, int], span2: Tuple[int, int]) -> bool:
    return max(span1[0], span2[0]) < min(span1[1], span2[1])


def extract_temporal_evidence(
    text: Optional[str],
    reference_date: Optional[date] = None,
    source: EvidenceSource = EvidenceSource.TEXT
) -> List[EvidenceItem]:
    """
    Deterministically extracts structured temporal evidence from raw crisis text.
    Uses reference_date (defaults to UTC today) for relative and historical evaluation.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    evidence_items: List[EvidenceItem] = []
    claimed_spans: List[Tuple[int, int]] = []

    def is_covered(start: int, end: int) -> bool:
        return any(_spans_overlap((start, end), span) for span in claimed_spans)

    def record_evidence(
        finding: str,
        polarity: EvidencePolarity,
        weight: float,
        details: Dict[str, Any],
        span: Tuple[int, int]
    ) -> None:
        details["span"] = list(span)
        evidence_items.append(
            EvidenceItem(
                source=source,
                finding=finding,
                polarity=polarity,
                weight=weight,
                details=details
            )
        )
        claimed_spans.append(span)

    # 1. Historical explicit modifiers ("old video", "happened in 2021", "from 2021")
    historical_patterns = [
        (
            r"\b(?:old|archived?|throwback)\s+(?:video|clip|footage|photo|image|picture|post)\b",
            "historical_media_flag",
            0.90,
            None
        ),
        (
            r"\b(?:happened|occurred|recorded)\s+in\s+(19\d{2}|20\d{2})\b",
            "historical_event_statement",
            0.90,
            1
        ),
        (
            r"\bfrom\s+(19\d{2}|20\d{2})\b",
            "historical_origin_year",
            0.85,
            1
        )
    ]
    for pattern, claim_type, base_weight, group_idx in historical_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            span = match.span()
            if is_covered(*span):
                continue
            matched_text = match.group(0)
            year_val = int(match.group(group_idx)) if group_idx else None
            
            polarity = EvidencePolarity.OLD
            if year_val is not None:
                if year_val < reference_date.year:
                    polarity = EvidencePolarity.OLD
                elif year_val == reference_date.year:
                    polarity = EvidencePolarity.CURRENT

            finding = f"Historical indicator detected: '{matched_text}'"
            if year_val:
                finding += f" indicating year {year_val}"

            record_evidence(
                finding=finding,
                polarity=polarity,
                weight=base_weight,
                details={"claim": matched_text, "type": claim_type, "year": year_val},
                span=span
            )

    # 2. Ongoing / Breaking / Immediate Crisis Claims
    ongoing_patterns = [
        (r"\bhappening\s+now\b", "Immediate ongoing claim", 0.90),
        (r"\bhappening\s+today\b", "Active current claim", 0.85),
        (r"\bjust\s+happened\b", "Recent occurrence claim", 0.85),
        (r"\bbreaking(?:\s+news)?\b", "Breaking event claim", 0.80),
        (r"\bongoing\s+(?:incident|crisis|emergency|fire|flood|situation)\b", "Ongoing situation", 0.85),
        (r"\bongoing\b", "Ongoing indicator", 0.75),
        (r"\bright\s+now\b", "Immediate indicator", 0.85),
        (r"\b(?:earlier\s+today|this\s+morning|this\s+afternoon|this\s+evening)\b", "Intra-day temporal claim", 0.75),
    ]
    for pattern, desc, weight in ongoing_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            span = match.span()
            if is_covered(*span):
                continue
            matched_text = match.group(0)
            record_evidence(
                finding=f"{desc}: '{matched_text}'",
                polarity=EvidencePolarity.CURRENT,
                weight=weight,
                details={"claim": matched_text, "type": "ongoing_marker"},
                span=span
            )

    # 3. Explicit Absolute Dates
    # ISO Format: YYYY-MM-DD
    iso_pattern = r"\b(19\d{2}|20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b"
    for match in re.finditer(iso_pattern, text):
        span = match.span()
        if is_covered(*span):
            continue
        try:
            yr, mo, dy = int(match.group(1)), int(match.group(2)), int(match.group(3))
            extracted_date = date(yr, mo, dy)
            diff_days = (reference_date - extracted_date).days
            polarity = EvidencePolarity.OLD if diff_days > 7 else (
                EvidencePolarity.CURRENT if 0 <= diff_days <= 7 else EvidencePolarity.NEUTRAL
            )
            weight = 0.95 if diff_days > 7 else 0.85
            record_evidence(
                finding=f"Explicit absolute date detected: '{match.group(0)}' ({extracted_date.isoformat()})",
                polarity=polarity,
                weight=weight,
                details={
                    "claim": match.group(0),
                    "type": "absolute_date_iso",
                    "date": extracted_date.isoformat(),
                    "days_from_reference": diff_days
                },
                span=span
            )
        except (ValueError, OverflowError):
            pass

    # Month Names Sorted by length descending
    sorted_months = sorted(MONTH_MAP.keys(), key=len, reverse=True)
    months_re = "|".join(sorted_months)
    year_re = r"(?:19\d{2}|20\d{2})"

    # Day-Month-Year: e.g. "12 June 2021" / "12th June, 2021"
    d_m_y_pattern = rf"\b(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+({months_re})[,\s]+({year_re})\b"
    for match in re.finditer(d_m_y_pattern, text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        try:
            dy = int(match.group(1))
            mo = MONTH_MAP[match.group(2).lower()]
            yr = int(match.group(3))
            extracted_date = date(yr, mo, dy)
            diff_days = (reference_date - extracted_date).days
            polarity = EvidencePolarity.OLD if diff_days > 7 else EvidencePolarity.CURRENT
            record_evidence(
                finding=f"Explicit date detected: '{match.group(0)}' ({extracted_date.isoformat()})",
                polarity=polarity,
                weight=0.90,
                details={
                    "claim": match.group(0),
                    "type": "absolute_date_text",
                    "date": extracted_date.isoformat(),
                    "days_from_reference": diff_days
                },
                span=span
            )
        except (ValueError, OverflowError):
            pass

    # Month-Day-Year: e.g. "June 12, 2021" / "June 12th 2021"
    m_d_y_pattern = rf"\b({months_re})\s+(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[,\s]+({year_re})\b"
    for match in re.finditer(m_d_y_pattern, text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        try:
            mo = MONTH_MAP[match.group(1).lower()]
            dy = int(match.group(2))
            yr = int(match.group(3))
            extracted_date = date(yr, mo, dy)
            diff_days = (reference_date - extracted_date).days
            polarity = EvidencePolarity.OLD if diff_days > 7 else EvidencePolarity.CURRENT
            record_evidence(
                finding=f"Explicit date detected: '{match.group(0)}' ({extracted_date.isoformat()})",
                polarity=polarity,
                weight=0.90,
                details={
                    "claim": match.group(0),
                    "type": "absolute_date_text",
                    "date": extracted_date.isoformat(),
                    "days_from_reference": diff_days
                },
                span=span
            )
        except (ValueError, OverflowError):
            pass

    # Month-Year: e.g. "June 2021"
    m_y_pattern = rf"\b({months_re})[,\s]+({year_re})\b"
    for match in re.finditer(m_y_pattern, text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        try:
            mo = MONTH_MAP[match.group(1).lower()]
            yr = int(match.group(2))
            is_past_month = (yr < reference_date.year) or (yr == reference_date.year and mo < reference_date.month)
            is_current_month = (yr == reference_date.year and mo == reference_date.month)
            polarity = EvidencePolarity.OLD if is_past_month else (
                EvidencePolarity.CURRENT if is_current_month else EvidencePolarity.NEUTRAL
            )
            record_evidence(
                finding=f"Month/Year reference detected: '{match.group(0)}'",
                polarity=polarity,
                weight=0.85,
                details={
                    "claim": match.group(0),
                    "type": "month_year",
                    "year": yr,
                    "month": mo
                },
                span=span
            )
        except (ValueError, OverflowError):
            pass

    # Standalone Year: "2021" / "in 2021"
    standalone_year_pattern = r"\b(?:in\s+|during\s+)?(19\d{2}|20\d{2})\b"
    for match in re.finditer(standalone_year_pattern, text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        try:
            yr = int(match.group(1))
            matched_text = match.group(0)
            if yr < reference_date.year:
                polarity = EvidencePolarity.OLD
                weight = 0.85
            elif yr == reference_date.year:
                polarity = EvidencePolarity.CURRENT
                weight = 0.60
            else:
                polarity = EvidencePolarity.NEUTRAL
                weight = 0.40
            record_evidence(
                finding=f"Explicit year mention: '{matched_text}' ({yr})",
                polarity=polarity,
                weight=weight,
                details={
                    "claim": matched_text,
                    "type": "standalone_year",
                    "year": yr
                },
                span=span
            )
        except (ValueError, OverflowError):
            pass

    # 4. Relative Temporal Expressions
    # "today"
    for match in re.finditer(r"\btoday\b", text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        record_evidence(
            finding="Relative temporal claim 'today' indicates active reporting",
            polarity=EvidencePolarity.CURRENT,
            weight=0.80,
            details={"claim": "today", "type": "relative_today"},
            span=span
        )

    # "yesterday"
    for match in re.finditer(r"\byesterday\b", text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        record_evidence(
            finding="Relative temporal claim 'yesterday' (1 day prior)",
            polarity=EvidencePolarity.CURRENT,
            weight=0.70,
            details={"claim": "yesterday", "type": "relative_yesterday", "offset_days": -1},
            span=span
        )

    # "last year" / "last year's"
    for match in re.finditer(r"\blast\s+year(?:'s)?\b", text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        record_evidence(
            finding="Relative temporal claim indicates previous year ('last year')",
            polarity=EvidencePolarity.OLD,
            weight=0.85,
            details={"claim": match.group(0), "type": "relative_last_year"},
            span=span
        )

    # "last week" / "last month"
    for match in re.finditer(r"\blast\s+(week|month)\b", text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        unit = match.group(1).lower()
        record_evidence(
            finding=f"Relative past indicator: 'last {unit}'",
            polarity=EvidencePolarity.OLD,
            weight=0.75,
            details={"claim": match.group(0), "type": f"relative_last_{unit}"},
            span=span
        )

    # "two days ago" / "N days ago" / "N weeks ago" / "N months ago" / "N years ago"
    num_words_or_digits = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an)"
    ago_pattern = rf"\b{num_words_or_digits}\s+(days?|weeks?|months?|years?)\s+ago\b"
    for match in re.finditer(ago_pattern, text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        raw_num = match.group(1).lower()
        unit = match.group(2).lower()
        num_val = int(raw_num) if raw_num.isdigit() else WORD_TO_NUM.get(raw_num, 1)

        if "day" in unit and num_val <= 2:
            polarity = EvidencePolarity.CURRENT
            weight = 0.65
        else:
            polarity = EvidencePolarity.OLD
            weight = 0.80 if ("year" in unit or "month" in unit or num_val > 7) else 0.70

        record_evidence(
            finding=f"Relative elapsed time expression: '{match.group(0)}'",
            polarity=polarity,
            weight=weight,
            details={
                "claim": match.group(0),
                "type": "relative_ago",
                "quantity": num_val,
                "unit": unit
            },
            span=span
        )

    # "recently" / "lately" (Vague with uncertainty)
    for match in re.finditer(r"\b(recently|lately)\b", text, re.IGNORECASE):
        span = match.span()
        if is_covered(*span):
            continue
        record_evidence(
            finding=f"Vague temporal indicator: '{match.group(0)}' (contains inherent temporal uncertainty)",
            polarity=EvidencePolarity.NEUTRAL,
            weight=0.35,
            details={
                "claim": match.group(0),
                "type": "vague_temporal",
                "uncertainty": True
            },
            span=span
        )

    return evidence_items
