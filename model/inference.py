import sys
import json
import logging
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.features.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)

class FireClassifierInference:
    """
    Production AI Inference Engine for Industrial Fire & Persistent Thermal Source Classification.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or (Config.ARTIFACTS_DIR / "fire_classifier.joblib")
        self.model_bundle = None
        self.model = None
        self.classes = []
        self.feature_names = []
        self.feature_extractor = FeatureExtractor()
        self._load_model()

    def _load_model(self):
        """Load trained model bundle or trigger automated training if missing."""
        if not self.model_path.exists():
            logger.warning("Trained model artifact not found. Triggering automated initial training...")
            from model.train import train_and_evaluate
            train_and_evaluate()

        try:
            self.model_bundle = joblib.load(self.model_path)
            self.model = self.model_bundle["model"]
            self.classes = self.model_bundle["classes"]
            self.feature_names = self.model_bundle["feature_names"]
            logger.info(f"Loaded classifier model successfully. Classes: {self.classes}")
        except Exception as e:
            logger.error(f"Error loading classifier model: {e}")
            raise

    def classify_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a single satellite detection record."""
        # 1. Feature extraction
        feat_dict = self.feature_extractor.extract_features_single(detection)
        
        # 2. Prepare tabular feature row
        feat_vector = [feat_dict[col] for col in self.feature_names]
        X = pd.DataFrame([feat_vector], columns=self.feature_names)

        # 3. Model inference
        probs = self.model.predict_proba(X)[0]
        pred_idx = int(np.argmax(probs))
        predicted_class = self.classes[pred_idx]
        confidence = float(probs[pred_idx])

        # Probabilities dictionary
        prob_dict = {cls_name: round(float(probs[i]), 4) for i, cls_name in enumerate(self.classes)}

        # 4. Synthesize tactical alert level and explanation
        alert_info = self._generate_tactical_alert(predicted_class, confidence, feat_dict)

        result = {
            # Core prediction
            "predicted_class": predicted_class,
            "confidence": round(confidence, 4),
            "probabilities": prob_dict,
            "alert_level": alert_info["alert_level"],
            "tactical_explanation": alert_info["explanation"],
            "recommended_action": alert_info["recommended_action"],

            # Physical & Geospatial Enrichment
            "latitude": feat_dict["latitude"],
            "longitude": feat_dict["longitude"],
            "acq_date": feat_dict["acq_date"],
            "acq_time": feat_dict["acq_time"],
            "satellite": feat_dict["satellite"],
            "frp": feat_dict["frp"],
            "bright_ti4": feat_dict["bright_ti4"],
            "bright_ti5": feat_dict["bright_ti5"],
            "delta_t": feat_dict["delta_t"],
            "estimated_flame_temp_k": feat_dict["estimated_flame_temp_k"],
            "estimated_pixel_fraction": feat_dict["estimated_pixel_fraction"],
            
            # Geospatial & Persistence Context
            "nearest_facility": feat_dict["nearest_facility_name"],
            "facility_type": feat_dict["facility_type"],
            "dist_to_industrial_km": feat_dict["dist_to_industrial_km"],
            "is_inside_buffer": bool(feat_dict["is_inside_buffer"]),
            "persistence_score": feat_dict["persistence_score"],
            "recurrence_count": feat_dict["recurrence_count"],
            "is_persistent_cluster": bool(feat_dict["is_persistent_cluster"]),
            "lulc_class": feat_dict["lulc_class"],
            "frp_zscore": feat_dict["frp_zscore"],
            "is_anomaly": bool(feat_dict["is_anomaly"]),
            "anomaly_severity": feat_dict["anomaly_severity"]
        }
        return result

    def classify_batch(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Vectorized batch classify multiple satellite detections."""
        if not detections:
            return []

        # 1. Extract feature dictionaries
        feat_dicts = [self.feature_extractor.extract_features_single(d) for d in detections]

        # 2. Build single combined feature matrix
        matrix = [[fd[col] for col in self.feature_names] for fd in feat_dicts]
        X = pd.DataFrame(matrix, columns=self.feature_names)

        # 3. Single vectorized model inference
        all_probs = self.model.predict_proba(X)
        pred_indices = np.argmax(all_probs, axis=1)

        results = []
        for i, (feat_dict, probs, pred_idx) in enumerate(zip(feat_dicts, all_probs, pred_indices)):
            predicted_class = self.classes[pred_idx]
            confidence = float(probs[pred_idx])
            prob_dict = {cls_name: round(float(probs[j]), 4) for j, cls_name in enumerate(self.classes)}
            alert_info = self._generate_tactical_alert(predicted_class, confidence, feat_dict)

            results.append({
                "predicted_class": predicted_class,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "alert_level": alert_info["alert_level"],
                "tactical_explanation": alert_info["explanation"],
                "recommended_action": alert_info["recommended_action"],
                "latitude": feat_dict["latitude"],
                "longitude": feat_dict["longitude"],
                "acq_date": feat_dict["acq_date"],
                "acq_time": feat_dict["acq_time"],
                "satellite": feat_dict["satellite"],
                "frp": feat_dict["frp"],
                "bright_ti4": feat_dict["bright_ti4"],
                "bright_ti5": feat_dict["bright_ti5"],
                "delta_t": feat_dict["delta_t"],
                "estimated_flame_temp_k": feat_dict["estimated_flame_temp_k"],
                "estimated_pixel_fraction": feat_dict["estimated_pixel_fraction"],
                "nearest_facility": feat_dict["nearest_facility_name"],
                "facility_type": feat_dict["facility_type"],
                "dist_to_industrial_km": feat_dict["dist_to_industrial_km"],
                "is_inside_buffer": bool(feat_dict["is_inside_buffer"]),
                "persistence_score": feat_dict["persistence_score"],
                "recurrence_count": feat_dict["recurrence_count"],
                "is_persistent_cluster": bool(feat_dict["is_persistent_cluster"]),
                "lulc_class": feat_dict["lulc_class"],
                "frp_zscore": feat_dict["frp_zscore"],
                "is_anomaly": bool(feat_dict["is_anomaly"]),
                "anomaly_severity": feat_dict["anomaly_severity"]
            })

        return results

    def _generate_tactical_alert(self, predicted_class: str, confidence: float, feat: Dict[str, Any]) -> Dict[str, str]:
        """Generate human-readable tactical reasoning for NTRO disaster monitoring operators."""
        frp = feat["frp"]
        dist = feat["dist_to_industrial_km"]
        fac = feat["nearest_facility_name"]
        rec = feat["recurrence_count"]
        zscore = feat["frp_zscore"]

        if predicted_class == "INDUSTRIAL_ACCIDENTAL_FIRE":
            return {
                "alert_level": "CRITICAL_DISASTER_ALERT",
                "explanation": (
                    f"EMERGENCY: Sudden massive thermal surge ({frp} MW, Z-score +{zscore}σ) detected within {dist:.2f} km "
                    f"of critical industrial facility '{fac}'. Thermal footprint indicates catastrophic industrial fire or explosion!"
                ),
                "recommended_action": "Immediately dispatch NTRO emergency task force, alert State Disaster Management Authority (SDMA), and notify plant safety control."
            }
        elif predicted_class == "INDUSTRIAL_PERSISTENT_SOURCE":
            return {
                "alert_level": "ROUTINE_OPERATIONAL",
                "explanation": (
                    f"Routine operational thermal emitter at '{fac}' ({dist:.2f} km). High spatial persistence "
                    f"({rec} recurrent satellite passes), stable thermal contrast (ΔT={feat['delta_t']}K), and baseline-conformant FRP ({frp} MW)."
                ),
                "recommended_action": "Log in persistent industrial registry; no emergency intervention required."
            }
        elif predicted_class == "WILDFIRE_FOREST":
            return {
                "alert_level": "HIGH_VEGETATION_ALERT" if frp > 50 else "MODERATE_FOREST_ALERT",
                "explanation": (
                    f"Active vegetation/forest canopy fire detected in {feat['lulc_class']} ({dist:.1f} km from any industrial zones). "
                    f"Radiative power is {frp} MW with flame temperature proxy ~{feat['estimated_flame_temp_k']}K."
                ),
                "recommended_action": "Notify Divisional Forest Officer (DFO) and initiate fire perimeter spread tracking."
            }
        elif predicted_class == "AGRICULTURAL_BURNING":
            return {
                "alert_level": "AGRICULTURAL_MONITORING",
                "explanation": (
                    f"Transient crop residue / stubble burning detected in cropland zone. Characteristic low FRP ({frp} MW), "
                    f"daytime occurrence, and low persistence score ({feat['persistence_score']})."
                ),
                "recommended_action": "Record in seasonal agricultural emissions inventory for air quality index (AQI) modeling."
            }
        elif predicted_class == "MINING_COAL_FIRE":
            return {
                "alert_level": "MINING_HAZARD_WARNING",
                "explanation": (
                    f"Subterranean/surface coal seam smoldering detected near mining pit '{fac}' ({dist:.2f} km). "
                    f"Persistent thermal recurrence ({rec} hits) with continuous day/night radiative emission."
                ),
                "recommended_action": "Alert Directorate General of Mines Safety (DGMS) and local coal mining authority."
            }
        else:
            return {
                "alert_level": "UNCLASSIFIED",
                "explanation": f"Thermal anomaly classified as {predicted_class} with confidence {confidence * 100:.1f}%.",
                "recommended_action": "Continuous monitoring and cross-verification with next orbital pass."
            }
