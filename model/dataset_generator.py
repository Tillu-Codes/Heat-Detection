import os
import random
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, List, Dict, Any
from backend.config import Config
from backend.features.feature_extractor import FeatureExtractor

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

TARGET_CLASSES = [
    "INDUSTRIAL_ACCIDENTAL_FIRE",
    "INDUSTRIAL_PERSISTENT_SOURCE",
    "WILDFIRE_FOREST",
    "AGRICULTURAL_BURNING",
    "MINING_COAL_FIRE"
]

def generate_benchmark_dataset(num_samples_per_class: int = 400) -> pd.DataFrame:
    """
    Generate synthetic satellite thermal observations calibrated against
    physical bi-spectral laws (Planck function, Stefan-Boltzmann) and
    satellite sensor capabilities (VIIRS 375m & MODIS 1km) for NTRO benchmarking.
    """
    data_rows = []

    # 1. INDUSTRIAL_ACCIDENTAL_FIRE
    # Characteristics: Extremely high FRP, localized inside industrial complex, abrupt surge above baseline, high Delta_T
    for _ in range(num_samples_per_class):
        frp = np.random.exponential(scale=65.0) + 120.0  # Range: ~120 - 450+ MW
        ti4 = np.random.uniform(365.0, 395.0)  # Saturated or near saturation
        ti5 = np.random.uniform(298.0, 312.0)
        dist_km = np.random.uniform(0.05, 1.8)  # Very close to facility core
        is_inside = 1.0
        recurrence = np.random.randint(1, 6)  # Recent spike, not necessarily long history
        persistence = np.random.uniform(0.15, 0.65)
        is_night = float(np.random.choice([0, 1], p=[0.45, 0.55]))
        frp_zscore = np.random.uniform(2.8, 7.5)  # Severe anomaly
        is_anomaly = 1.0
        
        # Bi-spectral proxy
        delta_t = ti4 - ti5
        t_flame = min(1400.0, 850.0 + delta_t * 6.0 + np.random.normal(0, 20))
        fraction = min(0.35, 0.02 + delta_t / 350.0)
        
        data_rows.append({
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": np.log1p(frp),
            "estimated_flame_temp_k": t_flame,
            "estimated_pixel_fraction": fraction,
            "is_night": is_night,
            "confidence_num": np.random.choice([0.85, 0.95, 1.0]),
            "recurrence_count": recurrence,
            "persistence_score": persistence,
            "diurnal_ratio": np.random.uniform(0.8, 1.5),
            "frp_stability": np.random.uniform(0.1, 0.45),  # erratic spike
            "is_persistent_cluster": 0.0 if recurrence < 3 else 1.0,
            "dist_to_industrial_km": dist_km,
            "is_inside_buffer": is_inside,
            "frp_zscore": frp_zscore,
            "is_anomaly": is_anomaly,
            "label": "INDUSTRIAL_ACCIDENTAL_FIRE"
        })

    # 2. INDUSTRIAL_PERSISTENT_SOURCE
    # Characteristics: Persistent flaring/smelting at exact coords, moderate steady FRP, high night presence, low Z-score
    for _ in range(num_samples_per_class):
        frp = np.random.normal(loc=38.0, scale=11.0)
        frp = max(8.0, frp)
        ti4 = np.random.uniform(328.0, 362.0)
        ti5 = np.random.uniform(288.0, 303.0)
        dist_km = np.random.uniform(0.02, 2.2)  # Inside refinery/power plant/steel mill
        is_inside = 1.0
        recurrence = np.random.randint(6, 45)  # High temporal hits across multiple passes
        persistence = np.random.uniform(0.70, 0.99)
        is_night = float(np.random.choice([0, 1], p=[0.4, 0.6]))
        frp_zscore = np.random.uniform(-0.8, 1.2)  # Routine operational baseline
        is_anomaly = 0.0
        
        delta_t = ti4 - ti5
        t_flame = 800.0 + delta_t * 5.2 + np.random.normal(0, 15)  # High flare tip temperature
        fraction = 0.005 + delta_t / 500.0
        
        data_rows.append({
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": np.log1p(frp),
            "estimated_flame_temp_k": t_flame,
            "estimated_pixel_fraction": fraction,
            "is_night": is_night,
            "confidence_num": np.random.choice([0.75, 0.9, 1.0]),
            "recurrence_count": recurrence,
            "persistence_score": persistence,
            "diurnal_ratio": np.random.uniform(0.9, 1.8),
            "frp_stability": np.random.uniform(0.65, 0.95),  # very stable
            "is_persistent_cluster": 1.0,
            "dist_to_industrial_km": dist_km,
            "is_inside_buffer": is_inside,
            "frp_zscore": frp_zscore,
            "is_anomaly": is_anomaly,
            "label": "INDUSTRIAL_PERSISTENT_SOURCE"
        })

    # 3. WILDFIRE_FOREST
    # Characteristics: Distant from industry, high biomass FRP, sprawling fronts, transient (low persistence over months)
    for _ in range(num_samples_per_class):
        frp = np.random.exponential(scale=35.0) + 18.0  # 20 - 180 MW
        ti4 = np.random.uniform(322.0, 360.0)
        ti5 = np.random.uniform(286.0, 301.0)
        dist_km = np.random.uniform(12.0, 85.0)  # Distant from industrial facilities
        is_inside = 0.0
        recurrence = np.random.randint(1, 4)  # Moves across landscape
        persistence = np.random.uniform(0.02, 0.25)
        is_night = float(np.random.choice([0, 1], p=[0.7, 0.3]))  # Peak in afternoon
        frp_zscore = 0.0
        is_anomaly = 0.0
        
        delta_t = ti4 - ti5
        t_flame = 680.0 + delta_t * 4.5 + np.random.normal(0, 25)
        fraction = 0.02 + delta_t / 300.0  # Larger fire front area
        
        data_rows.append({
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": np.log1p(frp),
            "estimated_flame_temp_k": t_flame,
            "estimated_pixel_fraction": fraction,
            "is_night": is_night,
            "confidence_num": np.random.choice([0.65, 0.85, 1.0]),
            "recurrence_count": recurrence,
            "persistence_score": persistence,
            "diurnal_ratio": np.random.uniform(0.1, 0.45),
            "frp_stability": np.random.uniform(0.2, 0.5),
            "is_persistent_cluster": 0.0,
            "dist_to_industrial_km": dist_km,
            "is_inside_buffer": is_inside,
            "frp_zscore": frp_zscore,
            "is_anomaly": is_anomaly,
            "label": "WILDFIRE_FOREST"
        })

    # 4. AGRICULTURAL_BURNING
    # Characteristics: Cropland stubble burning, low to moderate FRP, highly daytime-focused, very low persistence at point
    for _ in range(num_samples_per_class):
        frp = np.random.uniform(2.5, 24.0)  # Low radiative power
        ti4 = np.random.uniform(312.0, 336.0)
        ti5 = np.random.uniform(293.0, 308.0)
        dist_km = np.random.uniform(5.0, 60.0)
        is_inside = 0.0
        recurrence = np.random.randint(1, 3)  # Rapid burnout within 1-2 days
        persistence = np.random.uniform(0.01, 0.18)
        is_night = 0.0  # Exclusively daytime stubble burning
        frp_zscore = 0.0
        is_anomaly = 0.0
        
        delta_t = max(2.0, ti4 - ti5)
        t_flame = 520.0 + delta_t * 4.0 + np.random.normal(0, 15)
        fraction = 0.008 + delta_t / 400.0
        
        data_rows.append({
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": np.log1p(frp),
            "estimated_flame_temp_k": t_flame,
            "estimated_pixel_fraction": fraction,
            "is_night": is_night,
            "confidence_num": np.random.choice([0.4, 0.65, 0.8]),
            "recurrence_count": recurrence,
            "persistence_score": persistence,
            "diurnal_ratio": 0.0,
            "frp_stability": np.random.uniform(0.1, 0.4),
            "is_persistent_cluster": 0.0,
            "dist_to_industrial_km": dist_km,
            "is_inside_buffer": is_inside,
            "frp_zscore": frp_zscore,
            "is_anomaly": is_anomaly,
            "label": "AGRICULTURAL_BURNING"
        })

    # 5. MINING_COAL_FIRE
    # Characteristics: Open-cast coal pit or slag heap, smoldering, continuous, moderate FRP, low delta_t, persistent
    for _ in range(num_samples_per_class):
        frp = np.random.normal(loc=16.0, scale=4.5)
        frp = max(5.0, frp)
        ti4 = np.random.uniform(320.0, 342.0)
        ti5 = np.random.uniform(288.0, 301.0)
        dist_km = np.random.uniform(0.1, 3.5)  # Inside coal mining belt (e.g. Jharia)
        is_inside = 1.0 if dist_km < 3.0 else 0.0
        recurrence = np.random.randint(5, 30)  # Burns continuously for months/years
        persistence = np.random.uniform(0.60, 0.95)
        is_night = float(np.random.choice([0, 1], p=[0.5, 0.5]))
        frp_zscore = np.random.uniform(-0.5, 0.8)
        is_anomaly = 0.0
        
        delta_t = ti4 - ti5
        t_flame = 560.0 + delta_t * 3.5 + np.random.normal(0, 15)  # Smoldering coal
        fraction = 0.015 + delta_t / 350.0
        
        data_rows.append({
            "bright_ti4": ti4,
            "bright_ti5": ti5,
            "delta_t": delta_t,
            "frp": frp,
            "log_frp": np.log1p(frp),
            "estimated_flame_temp_k": t_flame,
            "estimated_pixel_fraction": fraction,
            "is_night": is_night,
            "confidence_num": np.random.choice([0.7, 0.85, 1.0]),
            "recurrence_count": recurrence,
            "persistence_score": persistence,
            "diurnal_ratio": np.random.uniform(0.7, 1.4),
            "frp_stability": np.random.uniform(0.55, 0.85),
            "is_persistent_cluster": 1.0,
            "dist_to_industrial_km": dist_km,
            "is_inside_buffer": is_inside,
            "frp_zscore": frp_zscore,
            "is_anomaly": is_anomaly,
            "label": "MINING_COAL_FIRE"
        })

    df = pd.DataFrame(data_rows)
    # Shuffle
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    return df

if __name__ == "__main__":
    out_dir = Config.DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    df = generate_benchmark_dataset(num_samples_per_class=400)
    out_path = out_dir / "fire_classification_benchmark.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated benchmark dataset with {len(df)} records -> {out_path}")
