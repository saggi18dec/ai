import os
import sys

if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    sys.path.append(sys.path.pop(0))

import requests
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp_server = MCPServer("google-maps", log_level="ERROR")

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")


def _tool(**kwargs):
    def decorator(fn):
        try:
            return mcp_server.tool(structured_output=False, **kwargs)(fn)
        except TypeError:
            return mcp_server.tool(**kwargs)(fn)
    return decorator


@_tool()
def maps_search_places(query: str, location: str = ""):
    """Search for places (e.g., coffee shops, restaurants, landmarks) using Google Maps."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", API_KEY)
    
    # Merge location if specified separately
    if location and location.lower() not in query.lower():
        query = f"{query} in {location}"

    # Try Google Places API (New v1)
    v1_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.websiteUri,places.nationalPhoneNumber",
    }
    resp = requests.post(v1_url, json={"textQuery": query}, headers=headers, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        places = data.get("places", [])
        if places:
            results = []
            for p in places[:10]:
                name = p.get("displayName", {}).get("text", "Unknown")
                addr = p.get("formattedAddress", "N/A")
                rating = p.get("rating", "N/A")
                reviews = p.get("userRatingCount", 0)
                phone = p.get("nationalPhoneNumber", "N/A")
                website = p.get("websiteUri", "N/A")
                results.append(
                    f"- {name} (Rating: {rating}/5 from {reviews} reviews)\n"
                    f"  Address: {addr}\n"
                    f"  Phone: {phone} | Website: {website}"
                )
            return "\n".join(results)

    # Fallback to Google Places Text Search API (Legacy)
    legacy_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    resp = requests.get(legacy_url, params={"query": query, "key": api_key}, timeout=15)
    data = resp.json()
    if data.get("status") == "OK":
        results = []
        for p in data.get("results", [])[:10]:
            name = p.get("name", "Unknown")
            addr = p.get("formatted_address", "N/A")
            rating = p.get("rating", "N/A")
            reviews = p.get("user_ratings_total", 0)
            place_id = p.get("place_id", "")
            results.append(
                f"- {name} (Rating: {rating}/5 from {reviews} reviews)\n"
                f"  Address: {addr} | place_id: {place_id}"
            )
        return "\n".join(results)

    return f"Google Maps API response: {data}"


@_tool()
def maps_geocode(address: str):
    """Convert an address or place name into latitude and longitude coordinates."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", API_KEY)
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(url, params={"address": address, "key": api_key}, timeout=15)
    data = resp.json()
    if data.get("status") == "OK" and data.get("results"):
        top = data["results"][0]
        loc = top["geometry"]["location"]
        return f"Formatted Address: {top.get('formatted_address')}\nLat: {loc['lat']}, Lng: {loc['lng']}"
    return f"Geocoding failed: {data}"


@_tool()
def maps_directions(origin: str, destination: str, mode: str = "driving"):
    """Get directions, distance, and duration between origin and destination."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", API_KEY)

    # 1. Try Google Routes API (New v2)
    routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    travel_mode_map = {
        "driving": "DRIVE",
        "walking": "WALK",
        "bicycling": "BICYCLE",
        "transit": "TRANSIT",
    }
    t_mode = travel_mode_map.get(mode.lower(), "DRIVE")
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.description,routes.legs",
    }
    body = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": t_mode,
    }
    try:
        resp = requests.post(routes_url, json=body, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            if routes:
                top = routes[0]
                legs = top.get("legs", [{}])[0]
                dist_km = round(top.get("distanceMeters", 0) / 1000, 2)
                duration_sec = int(str(top.get("duration", "0s")).replace("s", ""))
                duration_min = round(duration_sec / 60)
                desc = top.get("description", "Fastest route")
                steps = []
                for s in legs.get("steps", [])[:8]:
                    instr = s.get("navigationInstruction", {}).get("instructions")
                    if instr:
                        steps.append(instr)
                steps_str = "; ".join(steps) if steps else "Follow route via " + desc
                return (
                    f"From: {origin}\n"
                    f"To: {destination}\n"
                    f"Distance: {dist_km} km | Duration: {duration_min} mins (via {desc})\n"
                    f"Directions: {steps_str}"
                )
    except Exception:
        pass

    # 2. Fallback to Google Directions API (Legacy)
    url = "https://maps.googleapis.com/maps/api/directions/json"
    resp = requests.get(
        url,
        params={"origin": origin, "destination": destination, "mode": mode, "key": api_key},
        timeout=15,
    )
    data = resp.json()
    if data.get("status") == "OK" and data.get("routes"):
        leg = data["routes"][0]["legs"][0]
        steps = [s.get("html_instructions", "") for s in leg.get("steps", [])]
        return (
            f"From: {leg.get('start_address')}\n"
            f"To: {leg.get('end_address')}\n"
            f"Distance: {leg.get('distance', {}).get('text')} | Duration: {leg.get('duration', {}).get('text')}\n"
            f"Steps: {'; '.join(steps[:8])}"
        )
    return f"Directions failed: {data}"


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
