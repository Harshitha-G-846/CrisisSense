import requests
import re
import time

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "CrisisSense/1.0"
}


# --------------------------------------------------
# Known Bengaluru location aliases
# --------------------------------------------------

LOCATION_ALIASES = {
    "rr nagar": "Rajarajeshwari Nagar",
    "r r nagar": "Rajarajeshwari Nagar",
    "raj rajeshwari nagar": "Rajarajeshwari Nagar",
    "rajarajeshwari nagar": "Rajarajeshwari Nagar",

    "whitefield": "Whitefield",
    "electronic city": "Electronic City",
    "electroniccity": "Electronic City",

    "koramangala": "Koramangala",
    "indiranagar": "Indiranagar",
    "jayanagar": "Jayanagar",
    "hebbal": "Hebbal",
    "yelahanka": "Yelahanka",
    "marathahalli": "Marathahalli",
    "btm layout": "BTM Layout",
    "btm": "BTM Layout",
    "hsr layout": "HSR Layout",
    "hsr": "HSR Layout",
    "banashankari": "Banashankari",
    "rajajinagar": "Rajajinagar",
    "malleshwaram": "Malleshwaram",
    "basavanagudi": "Basavanagudi",
    "vijayanagar": "Vijayanagar",
    "kengeri": "Kengeri",
    "peenya": "Peenya",
    "yashwanthpur": "Yeshwanthpur",
    "yeshwanthpur": "Yeshwanthpur",
    "frazer town": "Frazer Town",
    "richmond town": "Richmond Town",
    "mg road": "MG Road",
    "brigade road": "Brigade Road",
    "rt nagar": "RT Nagar",
    "cooke town": "Cooke Town",
    "kammanahalli": "Kammanahalli",
    "hoodi": "Hoodi",
    "bellandur": "Bellandur",
    "sarjapur": "Sarjapur",
    "sarjapur road": "Sarjapur Road",
    "bommanahalli": "Bommanahalli",
    "begur": "Begur",
    "attibele": "Attibele",
    "kr puram": "KR Puram",
    "k r puram": "KR Puram",
    "devanahalli": "Devanahalli",
    "majestic": "Majestic",
}


# --------------------------------------------------
# Extract possible location phrases
# --------------------------------------------------

def extract_location_phrases(text):

    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)

    phrases = []

    # First check known location aliases
    lower_text = text.lower()

    for alias, official_name in LOCATION_ALIASES.items():

        pattern = r"\b" + re.escape(alias) + r"\b"

        if re.search(pattern, lower_text):
            phrases.append(official_name)

    # Generate 4, 3 and 2 word phrases
    # We intentionally avoid generic one-word searches here.
    for size in [4, 3, 2]:

        for i in range(len(words) - size + 1):

            phrase = " ".join(words[i:i + size])

            if phrase not in phrases:
                phrases.append(phrase)

    return phrases


# --------------------------------------------------
# Search location using Nominatim
# --------------------------------------------------

def search_nominatim(location_name):

    params = {
        "q": f"{location_name}, Bengaluru, Karnataka, India",
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "in"
    }

    try:

        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code != 200:
            return []

        return response.json()

    except requests.RequestException:
        return []


# --------------------------------------------------
# Extract useful address information
# --------------------------------------------------

def get_address_data(result):

    address = result.get("address", {})

    city = (
        address.get("city")
        or address.get("town")
        or address.get("municipality")
        or address.get("village")
        or address.get("city_district")
        or "Unknown"
    )

    state = address.get(
        "state",
        "Unknown"
    )

    return city, state


# --------------------------------------------------
# Main location extraction function
# --------------------------------------------------

def extract_locations(text):

    phrases = extract_location_phrases(text)

    for phrase in phrases:

        results = search_nominatim(phrase)

        # Respect Nominatim usage by avoiding rapid requests
        time.sleep(1)

        if not results:
            continue

        # Take the first suitable result
        result = results[0]

        latitude = result.get("lat")
        longitude = result.get("lon")

        if not latitude or not longitude:
            continue

        city, state = get_address_data(result)

        location = {
            "text": phrase,
            "display_name": result.get(
                "display_name",
                phrase
            ),
            "city": city,
            "state": state,
            "latitude": float(latitude),
            "longitude": float(longitude)
        }

        return [location]

    return []


# --------------------------------------------------
# Test the location extractor
# --------------------------------------------------

if __name__ == "__main__":

    print("\n========== CrisisSense Location Extractor ==========")

    text = input("\nEnter crisis text: ")

    locations = extract_locations(text)

    print("\nLocations:")

    if locations:

        for location in locations:

            print("\nLocation:", location["text"])
            print("Display Name:", location["display_name"])
            print("City:", location["city"])
            print("State:", location["state"])
            print("Latitude:", location["latitude"])
            print("Longitude:", location["longitude"])

    else:

        print("No location detected.")