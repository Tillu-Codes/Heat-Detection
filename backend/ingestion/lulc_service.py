import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LULCService:
    """
    Land Use / Land Cover (LULC) Classification Service.
    Determines likely land cover type (Forest, Cropland, Industrial/Built-up, Mining, Water)
    based on geographic coordinates, biome extents, and industrial proximity.
    """

    def __init__(self, osm_client=None):
        self.osm_client = osm_client

    def estimate_land_cover(self, lat: float, lon: float, nearest_facility_dist: float) -> Dict[str, Any]:
        """
        Estimate land cover class and confidence.
        Classes:
        - INDUSTRIAL_ZONE
        - MINING_ZONE
        - CROPLAND_AGRICULTURE
        - DENSE_FOREST_WOODLAND
        - BARREN_SHRUBLAND
        - URBAN_SETTLEMENT
        """
        # If very close to known industrial complex
        if nearest_facility_dist < 2500:
            if "coal" in (self.osm_client.get_nearest_industrial_facility(lat, lon).get("facility_type") or ""):
                return {
                    "lulc_class": "MINING_ZONE",
                    "confidence": 0.95,
                    "description": "Open-cast mining and coal pit excavation area"
                }
            return {
                "lulc_class": "INDUSTRIAL_ZONE",
                "confidence": 0.96,
                "description": "Heavy industrial manufacturing / refinery / petrochemical complex"
            }

        # India / South Asia geographic heuristic zones
        # 1. Major agricultural breadbaskets (Punjab, Haryana, UP plains)
        if 28.0 <= lat <= 32.5 and 74.0 <= lon <= 78.5:
            return {
                "lulc_class": "CROPLAND_AGRICULTURE",
                "confidence": 0.88,
                "description": "Intensive agricultural farmland (Paddy/Wheat cropping belt)"
            }

        # 2. Dense forest reserves (Simlipal, Western Ghats, Central Indian forests, Himalayan belt)
        # Western Ghats
        if 8.5 <= lat <= 15.5 and 73.5 <= lon <= 76.5:
            return {
                "lulc_class": "DENSE_FOREST_WOODLAND",
                "confidence": 0.85,
                "description": "Tropical moist evergreen and deciduous forest canopy"
            }
        # Central Highlands / Simlipal / Dandakaranya
        if 18.0 <= lat <= 23.5 and 80.0 <= lon <= 87.0 and nearest_facility_dist > 8000:
            return {
                "lulc_class": "DENSE_FOREST_WOODLAND",
                "confidence": 0.82,
                "description": "Protected forest reserve and wildlife biosphere"
            }
        # Himalayan foothills
        if lat >= 29.5 and 77.5 <= lon <= 82.0:
            return {
                "lulc_class": "DENSE_FOREST_WOODLAND",
                "confidence": 0.90,
                "description": "Subtropical pine and montane temperate forest"
            }

        # 3. Barren / scrubland (e.g. Thar desert or arid zones)
        if 24.0 <= lat <= 28.5 and 69.5 <= lon <= 73.5:
            return {
                "lulc_class": "BARREN_SHRUBLAND",
                "confidence": 0.78,
                "description": "Arid / semi-arid scrub and barren terrain"
            }

        # Default fallback
        if nearest_facility_dist < 6000:
            return {
                "lulc_class": "INDUSTRIAL_PERIPHERY",
                "confidence": 0.70,
                "description": "Mixed industrial buffer and logistics zone"
            }

        return {
            "lulc_class": "MIXED_RURAL_VEGETATION",
            "confidence": 0.65,
            "description": "Mixed rural vegetation, mosaic farmland, and grasslands"
        }
