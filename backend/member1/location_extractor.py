import re
import time
import requests

from difflib import SequenceMatcher


# ============================================================
# CONFIGURATION
# ============================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {"User-Agent": "CrisisSense/1.0"}


# ============================================================
# CACHE
# ============================================================

LOCATION_CACHE = {}


# ============================================================
# FUZZY MATCH SETTINGS
# ============================================================

# Minimum similarity required for typo correction
FUZZY_THRESHOLD = 0.80


# ============================================================
# INDIAN STATES AND UNION TERRITORIES
# ============================================================

INDIAN_STATES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    # Union Territories
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "chandigarh": "Chandigarh",
    "dadra and nagar haveli and daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry",
}


# ============================================================
# MAJOR INDIAN CITIES
# ============================================================

INDIAN_CITIES = {
    "bengaluru": ("Bengaluru", "Karnataka"),
    "bangalore": ("Bengaluru", "Karnataka"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "mumbai": ("Mumbai", "Maharashtra"),
    "delhi": ("Delhi", "Delhi"),
    "new delhi": ("New Delhi", "Delhi"),
    "hyderabad": ("Hyderabad", "Telangana"),
    "pune": ("Pune", "Maharashtra"),
    "kolkata": ("Kolkata", "West Bengal"),
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "surat": ("Surat", "Gujarat"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "indore": ("Indore", "Madhya Pradesh"),
    "bhopal": ("Bhopal", "Madhya Pradesh"),
    "patna": ("Patna", "Bihar"),
    "vadodara": ("Vadodara", "Gujarat"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "kochi": ("Kochi", "Kerala"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "bhubaneswar": ("Bhubaneswar", "Odisha"),
    "guwahati": ("Guwahati", "Assam"),
    "thiruvananthapuram": ("Thiruvananthapuram", "Kerala"),
    "mysuru": ("Mysuru", "Karnataka"),
    "mysore": ("Mysuru", "Karnataka"),
    "mangaluru": ("Mangaluru", "Karnataka"),
    "mangalore": ("Mangaluru", "Karnataka"),
    "hubballi": ("Hubballi", "Karnataka"),
    "dharwad": ("Dharwad", "Karnataka"),
    "agra": ("Agra", "Uttar Pradesh"),
    "varanasi": ("Varanasi", "Uttar Pradesh"),
    "prayagraj": ("Prayagraj", "Uttar Pradesh"),
    "chandigarh": ("Chandigarh", "Chandigarh"),
    "dehradun": ("Dehradun", "Uttarakhand"),
    "ranchi": ("Ranchi", "Jharkhand"),
    "raipur": ("Raipur", "Chhattisgarh"),
    "panaji": ("Panaji", "Goa"),
}


# ============================================================
# BENGALURU LOCALITY ALIASES
# ============================================================

LOCATION_ALIASES = {
    "rr nagar": "Rajarajeshwari Nagar, Bengaluru",
    "r r nagar": "Rajarajeshwari Nagar, Bengaluru",
    "raj rajeshwari nagar": "Rajarajeshwari Nagar, Bengaluru",
    "rajarajeshwari nagar": "Rajarajeshwari Nagar, Bengaluru",
    "whitefield": "Whitefield, Bengaluru",
    "electronic city": "Electronic City, Bengaluru",
    "electroniccity": "Electronic City, Bengaluru",
    "koramangala": "Koramangala, Bengaluru",
    "indiranagar": "Indiranagar, Bengaluru",
    "jayanagar": "Jayanagar, Bengaluru",
    "hebbal": "Hebbal, Bengaluru",
    "yelahanka": "Yelahanka, Bengaluru",
    "marathahalli": "Marathahalli, Bengaluru",
    "btm layout": "BTM Layout, Bengaluru",
    "btm": "BTM Layout, Bengaluru",
    "hsr layout": "HSR Layout, Bengaluru",
    "hsr": "HSR Layout, Bengaluru",
    "banashankari": "Banashankari, Bengaluru",
    "rajajinagar": "Rajajinagar, Bengaluru",
    "malleshwaram": "Malleshwaram, Bengaluru",
    "basavanagudi": "Basavanagudi, Bengaluru",
    "vijayanagar": "Vijayanagar, Bengaluru",
    "kengeri": "Kengeri, Bengaluru",
    "peenya": "Peenya, Bengaluru",
    "yashwanthpur": "Yeshwanthpur, Bengaluru",
    "yeshwanthpur": "Yeshwanthpur, Bengaluru",
    "frazer town": "Frazer Town, Bengaluru",
    "richmond town": "Richmond Town, Bengaluru",
    "mg road": "MG Road, Bengaluru",
    "brigade road": "Brigade Road, Bengaluru",
    "rt nagar": "RT Nagar, Bengaluru",
    "cooke town": "Cooke Town, Bengaluru",
    "kammanahalli": "Kammanahalli, Bengaluru",
    "hoodi": "Hoodi, Bengaluru",
    "bellandur": "Bellandur, Bengaluru",
    "sarjapur": "Sarjapur, Bengaluru",
    "sarjapur road": "Sarjapur Road, Bengaluru",
    "bommanahalli": "Bommanahalli, Bengaluru",
    "begur": "Begur, Bengaluru",
    "attibele": "Attibele, Bengaluru",
    "kr puram": "KR Puram, Bengaluru",
    "k r puram": "KR Puram, Bengaluru",
    "devanahalli": "Devanahalli, Bengaluru",
    "majestic": "Majestic, Bengaluru",
}


# ============================================================
# GENERIC WORDS
# ============================================================

GENERIC_WORDS = {
    "area",
    "place",
    "location",
    "city",
    "state",
    "road",
    "street",
    "near",
    "at",
    "in",
    "on",
    "from",
    "to",
    "around",
    "here",
    "there",
    "today",
    "yesterday",
    "tomorrow",
    "people",
    "person",
    "victims",
    "victim",
    "rescue",
    "help",
    "needed",
    "need",
    "urgent",
    "emergency",
    "fire",
    "flood",
    "rain",
    "heavy",
    "massive",
    "severe",
    "damage",
    "damaged",
    "incident",
    "accident",
    "explosion",
    "earthquake",
    "cyclone",
    "landslide",
    "wildfire",
    "and",
    "are",
    "is",
    "was",
    "were",
    "with",
    "who",
    "which",
    "that",
    "has",
    "have",
}


# ============================================================
# NORMALIZE TEXT
# ============================================================


def normalize_text(text):

    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# FUZZY SIMILARITY
# ============================================================


def similarity(a, b):

    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ============================================================
# FIND FUZZY LOCATION
# ============================================================


def fuzzy_match_location(candidate):

    candidate = normalize_text(candidate)

    if not candidate:
        return None

    # --------------------------------------------------------
    # Create one dictionary containing all known locations
    # --------------------------------------------------------

    known_locations = {}

    # States
    for key, value in INDIAN_STATES.items():
        known_locations[key] = {"name": value, "type": "state"}

    # Cities
    for key, value in INDIAN_CITIES.items():
        city_name, state_name = value
        known_locations[key] = {"name": f"{city_name}, {state_name}", "type": "city"}

    # Bengaluru localities
    for key, value in LOCATION_ALIASES.items():
        known_locations[key] = {"name": value, "type": "locality"}

    best_match = None
    best_score = 0.0

    # --------------------------------------------------------
    # Compare candidate against known locations
    # --------------------------------------------------------

    for known_name, location_data in known_locations.items():
        score = similarity(candidate, known_name)
        if score > best_score:
            best_score = score
            best_match = {
                "input": candidate,
                "matched_name": location_data["name"],
                "location_type": location_data["type"],
                "score": score,
            }

    # --------------------------------------------------------
    # Accept only strong matches
    # --------------------------------------------------------

    if best_match is not None and best_match["score"] >= FUZZY_THRESHOLD:
        return best_match

    return None


# ============================================================
# IDENTIFY LOCATION TYPE
# ============================================================


def identify_location_type(location_name):

    normalized = normalize_text(location_name)
    if normalized in INDIAN_STATES:
        return "state"

    if normalized in INDIAN_CITIES:
        return "city"

    if normalized in LOCATION_ALIASES:
        return "locality"

    return "unknown"


# ============================================================
# SEARCH NOMINATIM
# ============================================================


def search_nominatim(location_name, location_type="unknown"):

    cache_key = normalize_text(location_name)

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    if cache_key in LOCATION_CACHE:
        return LOCATION_CACHE[cache_key]

    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    time.sleep(1)

    params = {
        "q": f"{location_name}, India",
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "in",
    }

    try:

        response = requests.get(
            NOMINATIM_URL, params=params, headers=HEADERS, timeout=10
        )

        if response.status_code != 200:
            print("Nominatim error:", response.status_code)
            return []

        data = response.json()

        if not isinstance(data, list):
            return []

        # Save result
        LOCATION_CACHE[cache_key] = data
        return data

    except requests.RequestException as e:
        print("Nominatim request failed:", e)
        return []


# ============================================================
# GET ADDRESS DATA
# ============================================================


def get_address_data(result):

    address = result.get("address", {})

    city = (
        address.get("city")
        or address.get("town")
        or address.get("municipality")
        or address.get("village")
        or address.get("city_district")
        or address.get("county")
        or "Unknown"
    )

    state = address.get("state") or "Unknown"
    country = address.get("country") or "India"
    return city, state, country


# ============================================================
# VALID CANDIDATE
# ============================================================


def is_valid_candidate(candidate):

    candidate = normalize_text(candidate)

    if not candidate:
        return False

    words = candidate.split()

    if len(words) == 1 and words[0] in GENERIC_WORDS:
        return False

    if all(word in GENERIC_WORDS for word in words):
        return False

    return True


# ============================================================
# FIND EXACT KNOWN LOCATIONS
# ============================================================


def find_known_locations(text):

    normalized_text = normalize_text(text)
    found_locations = []

    # --------------------------------------------------------
    # Localities
    # --------------------------------------------------------

    for alias, full_name in LOCATION_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, normalized_text):

            found_locations.append(
                {"text": alias, "location_name": full_name, "location_type": "locality"}
            )

    # --------------------------------------------------------
    # States
    # --------------------------------------------------------

    for state_key, state_name in INDIAN_STATES.items():

        pattern = r"\b" + re.escape(state_key) + r"\b"
        if re.search(pattern, normalized_text):

            found_locations.append(
                {
                    "text": state_name,
                    "location_name": state_name,
                    "location_type": "state",
                }
            )

    # --------------------------------------------------------
    # Cities
    # --------------------------------------------------------

    for city_key, city_data in INDIAN_CITIES.items():

        pattern = r"\b" + re.escape(city_key) + r"\b"

        if re.search(pattern, normalized_text):
            city_name, state_name = city_data

            found_locations.append(
                {
                    "text": city_name,
                    "location_name": f"{city_name}, {state_name}",
                    "location_type": "city",
                }
            )

    return found_locations


# ============================================================
# EXTRACT POSSIBLE LOCATIONS AFTER KEYWORDS
# ============================================================


def extract_after_location_keyword(text):

    patterns = [
        r"\bnear\s+to\s+([A-Za-z][A-Za-z\s]{1,40})",
        r"\bnear\s+([A-Za-z][A-Za-z\s]{1,40})",
        r"\bin\s+([A-Za-z][A-Za-z\s]{1,40})",
        r"\bat\s+([A-Za-z][A-Za-z\s]{1,40})",
        r"\baround\s+([A-Za-z][A-Za-z\s]{1,40})",
        r"\bfrom\s+([A-Za-z][A-Za-z\s]{1,40})",
    ]

    candidates = []

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)

        for match in matches:
            candidate = match.strip()

            # ------------------------------------------------
            # Stop at sentence/context words
            # ------------------------------------------------

            candidate = re.split(
                r"\b("
                r"and|people|there|where|who|with|"
                r"are|is|was|were|need|needed|requiring|"
                r"reported|reports|have|has|suffering|"
                r"for|because|due|after|before"
                r")\b",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

            candidate = clean_location_candidate(candidate)

            if is_valid_candidate(candidate):
                candidates.append(candidate)

    return candidates


# ============================================================
# CLEAN LOCATION
# ============================================================


def clean_location_candidate(candidate):

    candidate = normalize_text(candidate)
    words = candidate.split()
    cleaned_words = []
    for word in words:

        if word in {"the", "a", "an", "area", "place", "location"}:
            continue

        cleaned_words.append(word)

    return " ".join(cleaned_words).strip()


# ============================================================
# CONVERT NOMINATIM RESULT
# ============================================================


def convert_nominatim_result(result, location_name, location_type):

    geometry = result.get("geometry", {})
    coordinates = geometry.get("coordinates", [])

    if len(coordinates) >= 2:

        longitude = coordinates[0]
        latitude = coordinates[1]

    else:

        latitude = result.get("lat")
        longitude = result.get("lon")

    if latitude is None or longitude is None:
        return None

    city, state, country = get_address_data(result)

    return {
        "text": location_name,
        "location_type": location_type,
        "display_name": result.get("display_name", location_name),
        "city": city,
        "state": state,
        "country": country,
        "latitude": float(latitude),
        "longitude": float(longitude),
    }


# ============================================================
# GEOCODE LOCATION
# ============================================================


def geocode_location(location_name, location_type="unknown"):

    results = search_nominatim(location_name, location_type)
    if not results:
        return None

    for result in results:

        converted = convert_nominatim_result(result, location_name, location_type)

        if converted is not None:
            return converted

    return None


# ============================================================
# REMOVE DUPLICATES
# ============================================================


def remove_duplicate_locations(locations):

    unique = []

    seen = set()

    for location in locations:

        key = (
            location.get("city"),
            location.get("state"),
            round(location.get("latitude", 0), 4),
            round(location.get("longitude", 0), 4),
        )

        if key not in seen:
            seen.add(key)
            unique.append(location)

    return unique


# ============================================================
# MAIN LOCATION EXTRACTION
# ============================================================


def extract_locations(text):

    if not text or not text.strip():
        return []

    locations = []

    # ========================================================
    # STEP 1
    # EXACT KNOWN LOCATION
    # ========================================================

    known_locations = find_known_locations(text)

    for location in known_locations:
        result = geocode_location(location["location_name"], location["location_type"])

        if result:
            result["text"] = location["text"]
            locations.append(result)

    # ========================================================
    # STEP 2
    # EXTRACT POSSIBLE LOCATION PHRASES
    # ========================================================

    candidates = extract_after_location_keyword(text)

    for candidate in candidates:
        candidate = clean_location_candidate(candidate)

        if not candidate:
            continue

        # ----------------------------------------------------
        # Already detected?
        # ----------------------------------------------------

        already_found = False

        for location in locations:

            if location["text"].lower() == candidate.lower():
                already_found = True
                break

        if already_found:
            continue

        # ====================================================
        # STEP 3
        # EXACT MATCH
        # ====================================================

        candidate_type = identify_location_type(candidate)

        if candidate_type != "unknown":
            corrected_name = candidate
            corrected_type = candidate_type
            corrected_text = candidate

        else:

            # =================================================
            # STEP 4
            # FUZZY SPELLING CORRECTION
            # =================================================

            fuzzy_result = fuzzy_match_location(candidate)

            if fuzzy_result is not None:
                corrected_name = fuzzy_result["matched_name"]
                corrected_type = fuzzy_result["location_type"]
                corrected_text = candidate

                print(
                    f"Fuzzy location correction: "
                    f"'{candidate}' -> "
                    f"'{corrected_name}' "
                    f"(score={fuzzy_result['score']:.2f})"
                )

            else:

                # =============================================
                # STEP 5
                # UNKNOWN LOCATION → NOMINATIM
                # =============================================

                corrected_name = candidate
                corrected_type = "unknown"
                corrected_text = candidate

        # ====================================================
        # STEP 6
        # GEOCODE
        # ====================================================

        result = geocode_location(corrected_name, corrected_type)

        if result:

            # Keep user's original spelling
            result["text"] = corrected_text

            # Add corrected location
            result["corrected_location"] = corrected_name

            locations.append(result)

    # ========================================================
    # STEP 7
    # REMOVE DUPLICATES
    # ========================================================

    locations = remove_duplicate_locations(locations)

    return locations


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    test_sentences = [
        # Correct spelling
        "fire near Whitefield",
        # Typo
        "fire near Whitefeild",
        # City typo
        "heavy flood near Chenai",
        # Hyderabad typo
        "earthquake in Hydrabad",
        # Mumbai typo
        "flood in Mumabi",
        # Bengaluru typo
        "fire in Banglore",
        # Locality typo
        "massive flood in Rajarajeshwari Nagr",
        # State
        "heavy rain at Assam",
        # Correct city
        "cyclone near Chennai",
        # Correct locality
        "fire near Electronic City",
        # Multiple locations
        "heavy flood in Mumbai and Chennai",
        # Original problematic example
        "heavy rain at assam and people are suffering a lot, needed rescue department",
    ]

    for sentence in test_sentences:

        print("\n")
        print("=" * 70)

        print("INPUT:")
        print(sentence)

        print("\nLOCATION RESULT:")

        result = extract_locations(sentence)

        for location in result:

            print(location)
