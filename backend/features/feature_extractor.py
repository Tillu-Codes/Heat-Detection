import math
import numpy as np
from typing import Dict, Any, List, Optional
from backend.ingestion.osm_client import OSMClient
from backend.features.persistence_engine import PersistenceEngine
from backend.features.anomaly_detector import AnomalyDetector
from backend.ingestion.lulc_service import LULCService

class FeatureExtractor:
    """
    Multimodal Geospatial & Bi-Spectral Feature Extraction Engine.
    Converts raw FIRMS satellite detections and geospatial metadata
    into rich feature vectors for AI classification.
    """

    def __init__(self, osm_client: Optional[OSMClient] = None, persistence_engine: Optional[PersistenceEngine] = None):
        self.osm_client = osm_client or OSMClient()
        self.persistence_engine = persistence_engine or PersistenceEngine()
        self.anomaly_detector = AnomalyDetector()
        self.lulc_service = LULCService(osm_client=self.osm_client)

    def estimate_dozier_subpixel_fire(self, ti4: float, ti5: float) -> Dict[str, float]:
        """
        Dozier (1981) Bi-Spectral Satellite Fire Inversion Approximation.
        Estimates sub-pixel flame temperature (T_f in Kelvin) and fraction of pixel area (p).
        TI4 (3.9um MIR) is sensitive to high temperature (700-1200K),
        TI5 (11um TIR) is dominated by ambient background (290-310K).
        """
        delta_t = max(0.1, ti4 - ti5)
        # Empirical approximation calibrated against Dozier inversion curves
        # High delta_t (> 40K) typically indicates small, extremely hot emitter (e.g. gas flare / blast furnace: 800-1200K)
        # Moderate delta_t (15-35K) corresponds to wider flaming biomass/forest front (650-850K)
        # Low delta_t (< 10K) corresponds to smoldering coal/stubble (450-650K)
        if delta_t > 50.0:
            t_flame = min(1300.0, 750.0 + delta_t * 6.5)
            fraction = min(0.15, 0.001 + (delta_t / 500.0))
        elif delta_t > 25.0:
            t_flame = 650.0 + delta_t * 5.0
            fraction = 0.005 + (delta_t / 400.0)
        else:
            t_flame = 500.0 + delta_t * 6.0
            fraction = 0.01 + (delta_t / 300.0)

        return {
            "estimated_flame_temp_k": round(t_flame, 1),
            "estimated_pixel_fraction": round(min(1.0, fraction), 4)
        }

    def extract_features_single(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Extract complete multi-source feature dictionary from a single FIRMS detection."""
        lat = float(detection.get("latitude", 0.0))
        lon = float(detection.get("longitude", 0.0))
        
        # Brightness temperatures
        ti4 = float(detection.get("bright_ti4") or detection.get("brightness", 320.0))
        ti5 = float(detection.get("bright_ti5") or detection.get("bright_t31", 295.0))
        frp = float(detection.get("frp", 15.0))
        scan = float(detection.get("scan", 0.5))
        track = float(detection.get("track", 0.5))
        daynight = str(detection.get("daynight", "D")).upper()
        confidence_str = str(detection.get("confidence", "n")).lower()

        # Numeric confidence
        if confidence_str == "h":
            conf_num = 1.0
        elif confidence_str == "l":
            conf_num = 0.3
        else:
            try:
                conf_num = float(confidence_str) / 100.0
            except ValueError:
                conf_num = 0.65

        # 1. Spatial OSM features
        industrial_info = self.osm_client.get_nearest_industrial_facility(lat, lon)
        dist_km = industrial_info["distance_meters"] / 1000.0
        is_inside_buffer = industrial_info["is_inside_buffer"]
        baseline_mean = industrial_info["nominal_frp_mean"]
        baseline_std = industrial_info["nominal_frp_std"]

        # 2. Land Cover estimation
        lulc = self.lulc_service.estimate_land_cover(lat, lon, industrial_info["distance_meters"])

        # 3. Spatio-Temporal Persistence features
        persistence_info = self.persistence_engine.calculate_persistence_metrics(lat, lon, current_frp=frp, current_daynight=daynight)

        # 4. Thermal & Bi-Spectral features
        delta_t = round(ti4 - ti5, 2)
        dozier = self.estimate_dozier_subpixel_fire(ti4, ti5)

        # 5. Anomaly detection
        anomaly_info = self.anomaly_detector.evaluate_anomaly(
            current_frp=frp,
            ti4=ti4,
            ti5=ti5,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            is_inside_industrial=is_inside_buffer
        )

        # Build feature vector dictionary
        is_night = 1.0 if daynight == "N" else 0.0
        log_frp = math.log1p(max(0.1, frp))
        pixel_area_km2 = scan * track * 0.14  # VIIRS 375m nadir is ~0.14 km^2

        features = {
            # Identification & Geospatial
            "latitude": lat,
            "longitude": lon,
            "acq_date": str(detection.get("acq_date", "")),
            "acq_time": str(detection.get("acq_time", "")),
            "satellite": str(detection.get("satellite", "")),
            "instrument": str(detection.get("instrument", "")),

            # Thermal & Physical Features
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": round(log_frp, 4),
            "pixel_area_km2": round(pixel_area_km2, 4),
            "estimated_flame_temp_k": dozier["estimated_flame_temp_k"],
            "estimated_pixel_fraction": dozier["estimated_pixel_fraction"],

            # Temporal & Observation Features
            "is_night": is_night,
            "confidence_num": conf_num,
            "recurrence_count": persistence_info["recurrence_count"],
            "persistence_score": persistence_info["persistence_score"],
            "diurnal_ratio": persistence_info["diurnal_ratio"],
            "frp_stability": persistence_info["frp_stability"],
            "is_persistent_cluster": 1.0 if persistence_info["is_persistent_cluster"] else 0.0,

            # Geospatial & Infrastructure Proximity Features
            "dist_to_industrial_km": round(dist_km, 3),
            "is_inside_buffer": 1.0 if is_inside_buffer else 0.0,
            "nearest_facility_name": industrial_info["nearest_facility"],
            "facility_type": industrial_info["facility_type"],
            "baseline_frp_mean": baseline_mean,

            # LULC
            "lulc_class": lulc["lulc_class"],
            "lulc_confidence": lulc["confidence"],

            # Anomaly Metrics
            "frp_zscore": anomaly_info["zscore"],
            "is_anomaly": 1.0 if anomaly_info["is_anomaly"] else 0.0,
            "anomaly_severity": anomaly_info["anomaly_severity"],
            "anomaly_explanation": anomaly_info["explanation"]
        }

        return features

    @classmethod
    def get_model_feature_names(cls) -> List[str]:
        """Ordered list of numeric feature names used for machine learning training and inference."""
        return [
            "bright_ti4",
            "bright_ti5",
            "delta_t",
            "frp",
            "log_frp",
            "estimated_flame_temp_k",
            "estimated_pixel_fraction",
            "is_night",
            "confidence_num",
            "recurrence_count",
            "persistence_score",
            "diurnal_ratio",
            "frp_stability",
            "is_persistent_cluster",
            "dist_to_industrial_km",
            "is_inside_buffer",
            "frp_zscore",
            "is_anomaly"
        ]
