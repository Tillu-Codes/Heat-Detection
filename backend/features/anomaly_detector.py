import math
from typing import Dict, Any, Optional
from backend.config import Config

class AnomalyDetector:
    """
    Industrial Thermal Anomaly & Emergency Surge Detector.
    Differentiates standard regulated industrial flaring from catastrophic
    accidental fires, explosions, and major leaks.
    """

    def __init__(self, zscore_threshold: float = Config.ANOMALY_ZSCORE_THRESHOLD):
        self.zscore_threshold = zscore_threshold

    def evaluate_anomaly(
        self,
        current_frp: float,
        ti4: float,
        ti5: float,
        baseline_mean: float,
        baseline_std: float,
        is_inside_industrial: bool
    ) -> Dict[str, Any]:
        """
        Evaluate if current thermal detection represents an industrial catastrophe / emergency fire.
        Returns:
        - zscore: Number of standard deviations above nominal baseline
        - is_anomaly: True if FRP or temperature exceeds safe operational boundaries
        - anomaly_severity: NONE, MODERATE, SEVERE, CRITICAL
        - delta_t: Temperature contrast (ti4 - ti5)
        - explanation: Clear diagnostic assessment for tactical NTRO operators
        """
        delta_t = round(ti4 - ti5, 2)

        if not is_inside_industrial:
            # For non-industrial, check general extreme fire intensity
            if current_frp > 150.0 or ti4 > 375.0:
                return {
                    "zscore": 0.0,
                    "is_anomaly": False,
                    "anomaly_severity": "NON_INDUSTRIAL_HIGH_INTENSITY",
                    "delta_t": delta_t,
                    "explanation": "High intensity thermal event in non-industrial zone (potential large wildfire)."
                }
            return {
                "zscore": 0.0,
                "is_anomaly": False,
                "anomaly_severity": "NONE",
                "delta_t": delta_t,
                "explanation": "Normal non-industrial thermal signature."
            }

        # Inside industrial zone
        effective_mean = max(10.0, baseline_mean)
        effective_std = max(5.0, baseline_std)

        zscore = round((current_frp - effective_mean) / effective_std, 2)

        # Extreme brightness saturation check (VIIRS 3.9um saturates around 367K-380K)
        is_saturated = ti4 >= 367.0

        if zscore >= 3.5 or (current_frp >= 140.0 and zscore >= 2.0) or (ti4 >= 380.0):
            return {
                "zscore": zscore,
                "is_anomaly": True,
                "anomaly_severity": "CRITICAL_EMERGENCY",
                "delta_t": delta_t,
                "explanation": f"CRITICAL SURGE: Thermal radiation ({current_frp} MW) is {zscore} standard deviations above baseline ({effective_mean} MW). High probability of major industrial fire/explosion!"
            }
        elif zscore >= self.zscore_threshold or current_frp >= 90.0:
            return {
                "zscore": zscore,
                "is_anomaly": True,
                "anomaly_severity": "SEVERE_ABNORMALITY",
                "delta_t": delta_t,
                "explanation": f"Abnormal industrial heat release: FRP exceeds normal operational flaring baseline by {zscore}σ. Elevated safety alert required."
            }
        elif zscore >= 1.5:
            return {
                "zscore": zscore,
                "is_anomaly": False,
                "anomaly_severity": "MODERATE_ELEVATION",
                "delta_t": delta_t,
                "explanation": "Operational flaring is slightly above average but within anticipated facility safety excursion bounds."
            }
        else:
            return {
                "zscore": zscore,
                "is_anomaly": False,
                "anomaly_severity": "ROUTINE_OPERATIONAL",
                "delta_t": delta_t,
                "explanation": "Nominal operational thermal signature consistent with continuous baseline flaring."
            }
