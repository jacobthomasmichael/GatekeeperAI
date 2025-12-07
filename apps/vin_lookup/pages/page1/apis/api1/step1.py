import requests
import re

vin = Input1["value"]

# API keys
OPENCAGE_API_KEY = "579a195994ad4203827ffae8fa65d9b9"
GOOGLE_MAPS_EMBED_KEY = "AIzaSyAI-0TNyyt_de3Ohzd72ZHdTc3I4oPsTao"

# APIs
VIN_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/"
GEOCODE_API_URL = "https://api.opencagedata.com/geocode/v1/json"


# Decode VIN
def decode_vin(vin):
    response = requests.get(VIN_API_URL + vin, params={"format": "json"})
    response.raise_for_status()
    return response.json()


# Geocode with OpenCage
def geocode_location(query, api_key):
    response = requests.get(
        GEOCODE_API_URL, params={"q": query, "key": api_key, "limit": 1}
    )
    response.raise_for_status()
    data = response.json()
    if data["results"]:
        coords = data["results"][0]["geometry"]
        return {"lat": coords["lat"], "long": coords["lng"], "title": query}
    return None


try:
    decoded_vin = decode_vin(vin)
    results = decoded_vin.get("Results", [])
    if not results:
        return {
            "table_data": [],
            "coordinates": [],
            "map_url": None,
            "iframe_url": None,
            "error": "No VIN data found.",
        }

    result = results[0]

    # Build clean table
    excluded_values = ["", "0", "Not Applicable", None]
    table_data = [
        {"Field": k, "Value": v} for k, v in result.items() if v not in excluded_values
    ]

    # Extract location components
    manufacturer_raw = result.get("Manufacturer", "")
    city = result.get("PlantCity", "")
    state = result.get("PlantState", "")
    country = result.get("PlantCountry", "")

    # Clean manufacturer string for better geocoding
    manufacturer_clean = re.sub(r"[^A-Za-z\s]", "", manufacturer_raw).split()[
        0
    ]  # e.g., "Toyota"

    query = f"{manufacturer_clean} plant {city} {state} {country}".strip()
    coordinates = []
    map_url = None
    iframe_url = None

    # Attempt geocoding
    coord = geocode_location(query, OPENCAGE_API_KEY)
    if coord:
        lat = coord["lat"]
        long = coord["long"]
        coordinates = [coord]

        # Direct embed with lat/long
        iframe_url = (
            f"https://www.google.com/maps/embed/v1/view"
            f"?key={GOOGLE_MAPS_EMBED_KEY}"
            f"&center={lat},{long}"
            f"&zoom=16"
            f"&maptype=roadmap"
        )

        # Also create a direct link
        map_url = f"https://www.google.com/maps?q={lat},{long}"

    else:
        # Fallback to search embed
        search_query = query.replace(" ", "+")
        iframe_url = (
            f"https://www.google.com/maps/embed/v1/search"
            f"?key={GOOGLE_MAPS_EMBED_KEY}"
            f"&q={search_query}"
        )

    return {
        "table_data": table_data,
        "coordinates": coordinates,
        "map_url": map_url,
        "iframe_url": iframe_url,
        "error": None,
    }

except Exception as e:
    return {
        "table_data": [],
        "coordinates": [],
        "map_url": None,
        "iframe_url": None,
        "error": f"Error: {str(e)}",
    }
