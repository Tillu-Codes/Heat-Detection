import math
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from backend.config import Config

logger = logging.getLogger(__name__)

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance between two points on the Earth's surface in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class OSMClient:
    """
    OpenStreetMap and Industrial Geofencing Integration Client.
    Queries industrial landuse tags (refinery, chemical, oil, power, mine, flare)
    and computes spatial proximity to critical industrial infrastructure.
    """

    def __init__(self, catalog_path: Optional[str] = None):
        self.catalog_path = catalog_path or Config.CATALOG_PATH
        self.facilities: List[Dict[str, Any]] = []
        self._load_catalog()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _load_catalog(self):
        try:
            if Config.CATALOG_PATH.exists():
                with open(Config.CATALOG_PATH, 'r', encoding='utf-8') as f:
                    self.facilities = json.load(f)
                logger.info(f"Loaded {len(self.facilities)} industrial facilities from catalog.")
        except Exception as e:
            logger.warning(f"Could not load industrial catalog: {e}")
            self.facilities = []

    def get_nearest_industrial_facility(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Find nearest industrial facility from curated catalog and compute distance.
        Returns distance in meters, facility details, and whether it is within the active footprint.
        """
        cache_key = f"{round(lat, 4)}_{round(lon, 4)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.facilities:
            result = {
                "nearest_facility": None,
                "distance_meters": 999999.0,
                "is_inside_buffer": False,
                "facility_type": "unknown",
                "nominal_frp_mean": 0.0,
                "nominal_frp_std": 0.0
            }
            return result

        min_dist = float('inf')
        nearest = None

        for fac in self.facilities:
            dist = haversine_distance_meters(lat, lon, fac["latitude"], fac["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest = fac

        is_inside = False
        if nearest and min_dist <= nearest.get("radius_meters", 3000):
            is_inside = True

        result = {
            "nearest_facility": nearest["name"] if nearest else None,
            "facility_id": nearest["id"] if nearest else None,
            "distance_meters": round(min_dist, 1),
            "is_inside_buffer": is_inside,
            "facility_type": nearest["type"] if nearest else "unknown",
            "nominal_frp_mean": nearest.get("baseline_frp_mean", 0.0) if nearest else 0.0,
            "nominal_frp_std": nearest.get("baseline_frp_std", 0.0) if nearest else 0.0,
            "flare_stacks_count": nearest.get("flare_stacks_count", 0) if nearest else 0
        }

        self._cache[cache_key] = result
        return result

    def query_overpass_industrial_near(self, lat: float, lon: float, radius_meters: int = 5000) -> List[Dict[str, Any]]:
        """
        Query live OpenStreetMap Overpass API for industrial tags near a hotspot.
        (Gracefully falls back to local catalog if network is unavailable).
        """
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          node["landuse"="industrial"](around:{radius_meters},{lat},{lon});
          way["landuse"="industrial"](around:{radius_meters},{lat},{lon});
          node["man_made"="flare"](around:{radius_meters},{lat},{lon});
          node["power"="plant"](around:{radius_meters},{lat},{lon});
          node["industrial"](around:{radius_meters},{lat},{lon});
        );
        out tags center 5;
        """
        try:
            resp = requests.post(overpass_url, data={"data": query}, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                results = []
                for el in elements:
                    el_lat = el.get("lat") or el.get("center", {}).get("lat")
                    el_lon = el.get("lon") or el.get("center", {}).get("lon")
                    if el_lat and el_lon:
                        dist = haversine_distance_meters(lat, lon, el_lat, el_lon)
                        results.append({
                            "name": el.get("tags", {}).get("name", "Industrial Entity"),
                            "type": el.get("tags", {}).get("industrial") or el.get("tags", {}).get("landuse", "industrial"),
                            "distance_meters": round(dist, 1)
                        })
                return sorted(results, key=lambda x: x["distance_meters"])
        except Exception as e:
            logger.debug(f"Overpass query bypassed or timed out: {e}")

        # Fallback to local catalog
        near = self.get_nearest_industrial_facility(lat, lon)
        if near["nearest_facility"] and near["distance_meters"] <= radius_meters:
            return [{
                "name": near["nearest_facility"],
                "type": near["facility_type"],
                "distance_meters": near["distance_meters"]
            }]
        return []
