import math
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from backend.config import Config
from backend.ingestion.osm_client import haversine_distance_meters

class PersistenceEngine:
    """
    Spatio-Temporal Persistence Engine.
    Quantifies the temporal permanence and recurrence of thermal anomalies.
    Continuous industrial emitters (flares, blast furnaces, kiln heads) persist
    at the exact same geospatial coordinates across months, whereas biomass/forest
    fires migrate or dissipate within days.
    """

    def __init__(self, cluster_radius_km: float = 1.0):
        self.cluster_radius_meters = cluster_radius_km * 1000.0
        # In-memory historical registry of detection clusters
        # key: cluster_id, value: list of detection dicts
        self.history: List[Dict[str, Any]] = []

    def load_historical_detections(self, detections: List[Dict[str, Any]]):
        """Seed engine with historical satellite observations."""
        self.history.extend(detections)

    def calculate_persistence_metrics(self, lat: float, lon: float, current_frp: float = 20.0, current_daynight: str = "D") -> Dict[str, Any]:
        """
        Calculate persistence metrics for a candidate hotspot against historical observations.
        Returns:
        - recurrence_count: Total observations within cluster radius
        - persistence_score: Normalized permanence score [0.0 to 1.0]
        - day_count: Total daytime hits
        - night_count: Total nighttime hits
        - diurnal_ratio: Night / Day ratio (High night/day indicates 24/7 industrial flaring)
        - frp_mean: Mean historical FRP in cluster
        - frp_std: Standard deviation of FRP
        - frp_stability: Inverse of coefficient of variation
        - is_persistent_cluster: Boolean indicating long-term operational emitter
        """
        nearby_hits = []
        for h in self.history:
            h_lat = h.get("latitude")
            h_lon = h.get("longitude")
            if h_lat is None or h_lon is None:
                continue
            dist = haversine_distance_meters(lat, lon, h_lat, h_lon)
            if dist <= self.cluster_radius_meters:
                nearby_hits.append(h)

        hit_count = len(nearby_hits)
        # Include current detection
        total_hits = hit_count + 1

        day_count = sum(1 for h in nearby_hits if h.get("daynight") == "D") + (1 if current_daynight == "D" else 0)
        night_count = sum(1 for h in nearby_hits if h.get("daynight") == "N") + (1 if current_daynight == "N" else 0)

        diurnal_ratio = round(night_count / max(1, day_count), 2)

        # FRP statistics
        all_frps = [h.get("frp", 20.0) for h in nearby_hits] + [current_frp]
        frp_mean = sum(all_frps) / len(all_frps)
        variance = sum((x - frp_mean) ** 2 for x in all_frps) / len(all_frps)
        frp_std = math.sqrt(variance)

        # Stability: Low CV (std/mean < 0.4) indicates steady industrial flaring
        cv = frp_std / max(1.0, frp_mean)
        frp_stability = max(0.0, min(1.0, 1.0 - (cv / 2.0)))

        # Sigmoid-based persistence score based on total hits and day/night balance
        # 1 hit -> 0.05, 3 hits -> 0.45, 6 hits -> 0.85, 10+ hits -> 0.98
        k = 0.6
        x0 = 4.0
        persistence_score = 1.0 / (1.0 + math.exp(-k * (total_hits - x0)))

        # Nighttime presence strongly boosts industrial confidence
        if night_count > 0:
            persistence_score = min(1.0, persistence_score * 1.15)

        is_persistent = (total_hits >= Config.PERSISTENCE_MIN_HITS) and (persistence_score >= 0.50)

        return {
            "recurrence_count": total_hits,
            "persistence_score": round(persistence_score, 3),
            "day_count": day_count,
            "night_count": night_count,
            "diurnal_ratio": diurnal_ratio,
            "frp_mean": round(frp_mean, 2),
            "frp_std": round(frp_std, 2),
            "frp_stability": round(frp_stability, 3),
            "is_persistent_cluster": is_persistent
        }
