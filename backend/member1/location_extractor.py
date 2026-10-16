import re
import time
import requests

from difflib import SequenceMatcher


# ============================================================
# CONFIGURATION
# ============================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {"User-Agent": "ResQSense-CrisisIntelligence/2.0 (contact: admin@resqsense.org)"}


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
# MAJOR INDIAN CITIES & PRE-CALCULATED COORDINATES
# ============================================================

# (City Name, State Name, Latitude, Longitude)
_CITY_REGISTRY = [
    # Andhra Pradesh
    ("Vijayawada", "Andhra Pradesh", 16.5062, 80.6480),
    ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185),
    ("Guntur", "Andhra Pradesh", 16.3067, 80.4365),
    ("Nellore", "Andhra Pradesh", 14.4426, 79.9865),
    ("Kurnool", "Andhra Pradesh", 15.8281, 78.0373),
    ("Rajahmundry", "Andhra Pradesh", 17.0005, 81.8040),
    ("Tirupati", "Andhra Pradesh", 13.6288, 79.4192),
    ("Kadapa", "Andhra Pradesh", 14.4673, 78.8242),
    ("Kakinada", "Andhra Pradesh", 16.9891, 82.2475),
    ("Anantapur", "Andhra Pradesh", 14.6819, 77.6006),
    ("Vizianagaram", "Andhra Pradesh", 18.1067, 83.3956),
    ("Eluru", "Andhra Pradesh", 16.7107, 81.0952),
    ("Ongole", "Andhra Pradesh", 15.5057, 80.0499),

    # Rajasthan
    ("Jaisalmer", "Rajasthan", 26.9157, 70.9083),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Jodhpur", "Rajasthan", 26.2389, 73.0243),
    ("Kota", "Rajasthan", 25.2138, 75.8648),
    ("Bikaner", "Rajasthan", 28.0229, 73.3119),
    ("Ajmer", "Rajasthan", 26.4499, 74.6399),
    ("Udaipur", "Rajasthan", 24.5854, 73.7125),
    ("Bhilwara", "Rajasthan", 25.3407, 74.6313),
    ("Alwar", "Rajasthan", 27.5530, 76.6346),
    ("Sikar", "Rajasthan", 27.6094, 75.1398),
    ("Bharatpur", "Rajasthan", 27.2152, 77.5030),

    # Karnataka
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Mysuru", "Karnataka", 12.2958, 76.6394),
    ("Mangaluru", "Karnataka", 12.9141, 74.8560),
    ("Hubballi", "Karnataka", 15.3647, 75.1240),
    ("Dharwad", "Karnataka", 15.4589, 75.0078),
    ("Belagavi", "Karnataka", 15.8497, 74.4977),
    ("Kalaburagi", "Karnataka", 17.3297, 76.8343),
    ("Ballari", "Karnataka", 15.1394, 76.9214),
    ("Davanagere", "Karnataka", 14.4644, 75.9218),
    ("Shivamogga", "Karnataka", 13.9299, 75.5681),

    # Maharashtra
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("Nagpur", "Maharashtra", 21.1458, 79.0882),
    ("Thane", "Maharashtra", 19.2183, 72.9781),
    ("Nashik", "Maharashtra", 19.9975, 73.7898),
    ("Chhatrapati Sambhajinagar", "Maharashtra", 19.8762, 75.3433),
    ("Solapur", "Maharashtra", 17.6599, 75.9064),
    ("Navi Mumbai", "Maharashtra", 19.0330, 73.0297),
    ("Amravati", "Maharashtra", 20.9374, 77.7796),
    ("Kolhapur", "Maharashtra", 16.7050, 74.2433),

    # Delhi
    ("Delhi", "Delhi", 28.6139, 77.2090),
    ("New Delhi", "Delhi", 28.6139, 77.2090),

    # Tamil Nadu
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Coimbatore", "Tamil Nadu", 11.0168, 76.9558),
    ("Madurai", "Tamil Nadu", 9.9252, 78.1198),
    ("Tiruchirappalli", "Tamil Nadu", 10.7905, 78.7047),
    ("Salem", "Tamil Nadu", 11.6643, 78.1460),
    ("Tirunelveli", "Tamil Nadu", 8.7139, 77.7567),
    ("Vellore", "Tamil Nadu", 12.9165, 79.1325),
    ("Erode", "Tamil Nadu", 11.3410, 77.7172),

    # Telangana
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Warangal", "Telangana", 17.9689, 79.5941),
    ("Nizamabad", "Telangana", 18.6725, 78.0941),
    ("Karimnagar", "Telangana", 18.4386, 79.1288),
    ("Khammam", "Telangana", 17.2473, 80.1514),

    # West Bengal
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Howrah", "West Bengal", 22.5958, 88.2636),
    ("Siliguri", "West Bengal", 26.7271, 88.3953),
    ("Durgapur", "West Bengal", 23.5204, 87.3119),
    ("Asansol", "West Bengal", 23.6739, 86.9524),

    # Gujarat
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Surat", "Gujarat", 21.1702, 72.8311),
    ("Vadodara", "Gujarat", 22.3072, 73.1812),
    ("Rajkot", "Gujarat", 22.3039, 70.8022),
    ("Bhavnagar", "Gujarat", 21.7645, 72.1519),
    ("Jamnagar", "Gujarat", 22.4707, 70.0577),
    ("Gandhinagar", "Gujarat", 23.2156, 72.6369),

    # Uttar Pradesh
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
    ("Kanpur", "Uttar Pradesh", 26.4499, 80.3319),
    ("Ghaziabad", "Uttar Pradesh", 28.6692, 77.4538),
    ("Agra", "Uttar Pradesh", 27.1767, 78.0081),
    ("Meerut", "Uttar Pradesh", 28.9845, 77.7064),
    ("Varanasi", "Uttar Pradesh", 25.3176, 82.9739),
    ("Prayagraj", "Uttar Pradesh", 25.4358, 81.8463),
    ("Bareilly", "Uttar Pradesh", 28.3670, 79.4304),
    ("Aligarh", "Uttar Pradesh", 27.8974, 78.0880),
    ("Moradabad", "Uttar Pradesh", 28.8354, 78.7747),
    ("Noida", "Uttar Pradesh", 28.5355, 77.3910),
    ("Gorakhpur", "Uttar Pradesh", 26.7606, 83.3732),

    # Madhya Pradesh
    ("Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126),
    ("Jabalpur", "Madhya Pradesh", 23.1815, 79.9864),
    ("Gwalior", "Madhya Pradesh", 26.2183, 78.1828),
    ("Ujjain", "Madhya Pradesh", 23.1765, 75.7885),

    # Bihar
    ("Patna", "Bihar", 25.6127, 85.1589),
    ("Gaya", "Bihar", 24.7914, 85.0002),
    ("Bhagalpur", "Bihar", 25.2425, 86.9842),
    ("Muzaffarpur", "Bihar", 26.1209, 85.3647),
    ("Darbhanga", "Bihar", 26.1542, 85.8918),

    # Kerala
    ("Thiruvananthapuram", "Kerala", 8.5241, 76.9366),
    ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Kozhikode", "Kerala", 11.2588, 75.7804),
    ("Thrissur", "Kerala", 10.5276, 76.2144),
    ("Kollam", "Kerala", 8.8932, 76.6141),
    ("Kannur", "Kerala", 11.8745, 75.3704),

    # Punjab & Haryana
    ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    ("Ludhiana", "Punjab", 30.9010, 75.8573),
    ("Amritsar", "Punjab", 31.6340, 74.8723),
    ("Jalandhar", "Punjab", 31.3260, 75.5762),
    ("Patiala", "Punjab", 30.3398, 76.3869),
    ("Faridabad", "Haryana", 28.4089, 77.3178),
    ("Gurugram", "Haryana", 28.4595, 77.0266),

    # Odisha
    ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Cuttack", "Odisha", 20.4625, 85.8828),
    ("Rourkela", "Odisha", 22.2604, 84.8536),
    ("Puri", "Odisha", 19.8135, 85.8312),

    # Assam & Northeast
    ("Guwahati", "Assam", 26.1445, 91.7362),
    ("Dispur", "Assam", 26.1433, 91.7898),
    ("Silchar", "Assam", 24.8170, 92.7993),
    ("Dibrugarh", "Assam", 27.4728, 94.9120),
    ("Shillong", "Meghalaya", 25.5788, 91.8933),
    ("Imphal", "Manipur", 24.8170, 93.9368),
    ("Aizawl", "Mizoram", 23.7271, 92.7176),
    ("Agartala", "Tripura", 23.8315, 91.2868),
    ("Kohima", "Nagaland", 25.6751, 94.1086),
    ("Gangtok", "Sikkim", 27.3389, 88.6065),
    ("Itanagar", "Arunachal Pradesh", 27.0844, 93.6053),

    # Other States
    ("Ranchi", "Jharkhand", 23.3441, 85.3096),
    ("Jamshedpur", "Jharkhand", 22.8046, 86.2029),
    ("Dhanbad", "Jharkhand", 23.7957, 86.4304),
    ("Raipur", "Chhattisgarh", 21.2514, 81.6296),
    ("Bilaspur", "Chhattisgarh", 22.0797, 82.1409),
    ("Dehradun", "Uttarakhand", 30.3165, 78.0322),
    ("Panaji", "Goa", 15.4909, 73.8278),
    ("Srinagar", "Jammu and Kashmir", 34.0837, 74.7973),
    ("Jammu", "Jammu and Kashmir", 32.7266, 74.8570),
    ("Shimla", "Himachal Pradesh", 31.1048, 77.1734),
]

INDIAN_CITIES = {}
KNOWN_CITY_COORDINATES = {}

for _c_name, _s_name, _lat, _lon in _CITY_REGISTRY:
    _key = _c_name.lower()
    INDIAN_CITIES[_key] = (_c_name, _s_name)
    KNOWN_CITY_COORDINATES[_key] = (_lat, _lon, _c_name, _s_name)

# Common city aliases
_ALIASES_MAP = {
    "bangalore": ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    "vizag": ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185),
    "calicut": ("Kozhikode", "Kerala", 11.2588, 75.7804),
    "trichy": ("Tiruchirappalli", "Tamil Nadu", 10.7905, 78.7047),
    "aurangabad": ("Chhatrapati Sambhajinagar", "Maharashtra", 19.8762, 75.3433),
    "mysore": ("Mysuru", "Karnataka", 12.2958, 76.6394),
    "mangalore": ("Mangaluru", "Karnataka", 12.9141, 74.8560),
    "gurgaon": ("Gurugram", "Haryana", 28.4595, 77.0266),
    "benaras": ("Varanasi", "Uttar Pradesh", 25.3176, 82.9739),
    "kashi": ("Varanasi", "Uttar Pradesh", 25.3176, 82.9739),
    "allahabad": ("Prayagraj", "Uttar Pradesh", 25.4358, 81.8463),
}

for _a_key, (_c_name, _s_name, _lat, _lon) in _ALIASES_MAP.items():
    INDIAN_CITIES[_a_key] = (_c_name, _s_name)
    KNOWN_CITY_COORDINATES[_a_key] = (_lat, _lon, _c_name, _s_name)


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
    "building",
    "buildings",
    "house",
    "houses",
    "hospital",
    "hospitals",
    "school",
    "schools",
    "shop",
    "shops",
    "room",
    "rooms",
    "floor",
    "apartment",
    "apartments",
    "ground",
    "field",
    "site",
    "complex",
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
        or address.get("state_district")
        or address.get("district")
        or address.get("county")
        or address.get("suburb")
        or result.get("name")
        or "Unknown"
    )

    state = address.get("state") or address.get("province") or "Unknown"
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
        r"(?:reported\s+)?location\s*:\s*([A-Za-z0-9\s,\-\.]{2,50})",
        r"\bcity\s*:\s*([A-Za-z0-9\s,\-\.]{2,50})",
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
            # Stop at delimiters, punctuation, and sentence/context words
            # ------------------------------------------------
            candidate = re.split(r"[,;:\.\!\?\(\)\[\]\{\}\n\r\t]", candidate)[0].strip()

            candidate = re.split(
                r"\b("
                r"and|people|there|where|who|with|"
                r"are|is|was|were|need|needed|requiring|"
                r"reported|reports|have|has|suffering|"
                r"for|because|due|after|before|"
                r"since|until|till|today|yesterday|tomorrow|"
                r"night|morning|evening|afternoon|days|hours|now|ago"
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

    normalized = normalize_text(location_name)
    if normalized in KNOWN_CITY_COORDINATES:
        lat, lon, city_name, state_name = KNOWN_CITY_COORDINATES[normalized]
        return {
            "text": location_name,
            "location_type": "city",
            "display_name": f"{city_name}, {state_name}, India",
            "city": city_name,
            "state": state_name,
            "country": "India",
            "latitude": float(lat),
            "longitude": float(lon),
        }

    if "," in location_name:
        first_part = normalize_text(location_name.split(",")[0])
        if first_part in KNOWN_CITY_COORDINATES:
            lat, lon, city_name, state_name = KNOWN_CITY_COORDINATES[first_part]
            return {
                "text": location_name,
                "location_type": "city",
                "display_name": f"{city_name}, {state_name}, India",
                "city": city_name,
                "state": state_name,
                "country": "India",
                "latitude": float(lat),
                "longitude": float(lon),
            }

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
