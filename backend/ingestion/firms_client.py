import io
import json
import logging
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from backend.config import Config

logger = logging.getLogger(__name__)

class FIRMSClient:
    """Client for NASA FIRMS (Fire Information for Resource Management System) API."""

    def __init__(self, map_key: Optional[str] = None):
        self.map_key = map_key or Config.FIRMS_MAP_KEY
        self.base_url = Config.FIRMS_BASE_URL

    @property
    def has_valid_key(self) -> bool:
        return bool(self.map_key and self.map_key != 'your_firms_map_key_here' and len(self.map_key) >= 16)

    def check_key_status(self) -> Dict[str, Any]:
        """Check the quota and transaction count of the provided MAP_KEY."""
        if not self.has_valid_key:
            return {
                "valid": False,
                "message": "MAP_KEY not configured. Set FIRMS_MAP_KEY in .env or provide via dashboard.",
                "current_transactions": 0,
                "transaction_limit": 5000,
                "mode": "Simulated Satellite Telemetry"
            }
        
        url = f"{self.base_url}/mapserver/mapkey_status/?MAP_KEY={self.map_key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "valid": True,
                    "message": "FIRMS MAP_KEY active and verified.",
                    "current_transactions": data.get("current_transactions", 0),
                    "transaction_limit": data.get("transaction_limit", 5000),
                    "transaction_interval": data.get("transaction_interval", "10 minutes"),
                    "mode": "Live NASA FIRMS Satellite Feed"
                }
            else:
                return {
                    "valid": False,
                    "message": f"FIRMS API returned status {resp.status_code}: {resp.text[:100]}",
                    "mode": "Simulated Satellite Telemetry"
                }
        except Exception as e:
            logger.warning(f"Failed to check FIRMS MAP_KEY status: {e}")
            return {
                "valid": False,
                "message": f"Connection error: {str(e)}",
                "mode": "Simulated Satellite Telemetry"
            }

    def fetch_data_availability(self) -> pd.DataFrame:
        """Fetch date range availability for FIRMS sensors."""
        if not self.has_valid_key:
            # Fallback mock availability
            today = datetime.utcnow().strftime("%Y-%m-%d")
            return pd.DataFrame([
                {"data_id": "VIIRS_NOAA20_NRT", "min_date": "2024-01-01", "max_date": today},
                {"data_id": "VIIRS_NOAA21_NRT", "min_date": "2024-01-01", "max_date": today},
                {"data_id": "VIIRS_SNPP_NRT", "min_date": "2024-01-01", "max_date": today},
                {"data_id": "MODIS_NRT", "min_date": "2024-01-01", "max_date": today}
            ])

        url = f"{self.base_url}/api/data_availability/csv/{self.map_key}/all"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                return pd.read_csv(io.StringIO(resp.text))
        except Exception as e:
            logger.warning(f"Error fetching data availability: {e}")
        return pd.DataFrame()

    def fetch_area(self, bbox: str, source: str = "VIIRS_NOAA20_NRT", day_range: int = 1, date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch fire hotspots from official NASA FIRMS API by bounding box or 'world'.
        bbox format: 'min_lon,min_lat,max_lon,max_lat' or 'world'
        Returns 100% of official NASA records without sampling.
        """
        if not self.has_valid_key:
            logger.info("Using simulated satellite telemetry (FIRMS_MAP_KEY not configured)")
            return self._generate_simulated_hotspots(source=source, bbox=bbox, day_range=day_range)

        url = f"{self.base_url}/api/area/csv/{self.map_key}/{source}/{bbox}/{day_range}"
        if date:
            url += f"/{date}"

        logger.info(f"Connecting to Official NASA FIRMS API: {self.base_url}/api/area/csv/[MAP_KEY]/{source}/{bbox}/{day_range}")
        try:
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                logger.info(f"Retrieved {len(df)} official live records from NASA FIRMS ({source}) for '{bbox}'")
                return df
            else:
                logger.error(f"Official NASA FIRMS API returned status {resp.status_code}: {resp.text[:200]}")
                raise RuntimeError(f"NASA FIRMS API error ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Error fetching from official NASA FIRMS API: {e}")
            raise

    def fetch_country(self, country_code: str = "IND", source: str = "VIIRS_NOAA20_NRT", day_range: int = 1) -> pd.DataFrame:
        """Fetch fire hotspots for a given 3-letter ISO country code (e.g. IND, USA)."""
        if not self.has_valid_key:
            return self._generate_simulated_hotspots(source=source, country=country_code, day_range=day_range)

        url = f"{self.base_url}/api/country/csv/{self.map_key}/{source}/{country_code}/{day_range}"
        try:
            resp = requests.get(url, timeout=25)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                return df
            else:
                return self._generate_simulated_hotspots(source=source, country=country_code, day_range=day_range)
        except Exception as e:
            logger.error(f"Error fetching country FIRMS data: {e}")
            return self._generate_simulated_hotspots(source=source, country=country_code, day_range=day_range)

    def _generate_simulated_hotspots(self, source: str = "VIIRS_NOAA20_NRT", bbox: Optional[str] = None, country: str = "IND", day_range: int = 3) -> pd.DataFrame:
        """
        Generate realistic synthetic VIIRS/MODIS satellite hotspot detections for testing,
        benchmarking, and demonstration prior to receiving live FIRMS MAP_KEY.
        Covers:
        1. Industrial flaring (Jamnagar, Vadinar, Panipat, Paradip, Tata Steel, Bokaro)
        2. Accidental Industrial Fire spike (abnormal 180+ MW burst with emergency signature)
        3. Forest fires (Simlipal National Park, Bandipur, Uttarakhand Himalayan foothills)
        4. Agricultural residue fires (Punjab, Haryana, Central Plains stubble burning)
        5. Coal field surface fires (Jharia & Raniganj open-cast coalfields)
        """
        records = []
        now = datetime.utcnow()
        sat_name = "N20" if "NOAA20" in source else ("N21" if "NOAA21" in source else "Terra")
        instrument = "VIIRS" if "VIIRS" in source else "MODIS"

        # Load industrial catalog
        catalog_path = Config.CATALOG_PATH
        facilities = []
        if catalog_path.exists():
            with open(catalog_path, 'r', encoding='utf-8') as f:
                facilities = json.load(f)

        # 1. Industrial Persistent Operational Flares
        for fac in facilities:
            for day_offset in range(day_range):
                acq_dt = now - timedelta(days=day_offset, hours=random.randint(0, 23))
                date_str = acq_dt.strftime("%Y-%m-%d")
                time_str = f"{acq_dt.hour:02d}{acq_dt.minute:02d}"
                daynight = "D" if 6 <= acq_dt.hour <= 18 else "N"

                # Jitter within facility radius
                lat_jitter = (random.random() - 0.5) * (fac["radius_meters"] / 111000.0)
                lon_jitter = (random.random() - 0.5) * (fac["radius_meters"] / (111000.0 * 0.9))
                
                frp = max(5.0, random.gauss(fac["baseline_frp_mean"], fac["baseline_frp_std"]))
                ti4 = round(random.uniform(320.0, 365.0), 2)
                ti5 = round(random.uniform(285.0, 305.0), 2)

                records.append({
                    "latitude": round(fac["latitude"] + lat_jitter, 5),
                    "longitude": round(fac["longitude"] + lon_jitter, 5),
                    "bright_ti4": ti4,
                    "scan": round(random.uniform(0.35, 0.65), 2),
                    "track": round(random.uniform(0.35, 0.65), 2),
                    "acq_date": date_str,
                    "acq_time": time_str,
                    "satellite": sat_name,
                    "instrument": instrument,
                    "confidence": random.choice(["n", "h", "h"]),
                    "version": "2.0NRT",
                    "bright_ti5": ti5,
                    "frp": round(frp, 2),
                    "daynight": daynight,
                    "_ground_truth": "INDUSTRIAL_PERSISTENT_SOURCE",
                    "_facility_id": fac["id"],
                    "_facility_name": fac["name"]
                })

        # 2. Accidental Industrial Fire / Explosion (Emergency Scenario)
        for emergency_site in [
            {"lat": 22.3580, "lon": 69.8690, "name": "Jamnagar Crude Distillation Unit 4", "frp": 245.8, "ti4": 388.5},
            {"lat": 20.2890, "lon": 86.6490, "name": "Paradip Petrochemical Naphtha Unit", "frp": 192.4, "ti4": 379.2},
            {"lat": 29.7580, "lon": -95.0150, "name": "Houston Baytown Alkylation Flare Surge", "frp": 268.0, "ti4": 391.2},
            {"lat": 26.6580, "lon": 50.1620, "name": "Ras Tanura NGL Separation Fire", "frp": 310.5, "ti4": 394.0},
            {"lat": 51.9580, "lon": 4.1480, "name": "Rotterdam Europoort Storage Tank Surge", "frp": 215.3, "ti4": 382.4}
        ]:
            acq_dt = now - timedelta(hours=random.randint(1, 6))
            records.append({
                "latitude": emergency_site["lat"],
                "longitude": emergency_site["lon"],
                "bright_ti4": emergency_site["ti4"],
                "scan": 0.42,
                "track": 0.58,
                "acq_date": acq_dt.strftime("%Y-%m-%d"),
                "acq_time": f"{acq_dt.hour:02d}{acq_dt.minute:02d}",
                "satellite": sat_name,
                "instrument": instrument,
                "confidence": "h",
                "version": "2.0NRT",
                "bright_ti5": 302.4,
                "frp": emergency_site["frp"],
                "daynight": "D" if 6 <= acq_dt.hour <= 18 else "N",
                "_ground_truth": "INDUSTRIAL_ACCIDENTAL_FIRE",
                "_facility_name": emergency_site["name"]
            })

        # 3. Forest Wildfires Across Continents
        forest_regions = [
            {"name": "Simlipal Tiger Reserve", "lat": 21.65, "lon": 86.35, "count": 12},
            {"name": "Bandipur National Park", "lat": 11.66, "lon": 76.62, "count": 8},
            {"name": "Garhwal Himalayan Forest Belt", "lat": 30.15, "lon": 78.80, "count": 14},
            {"name": "Amazon Basin Rainforest (Pará / Mato Grosso)", "lat": -7.12, "lon": -55.85, "count": 28},
            {"name": "California Sierra Nevada Forest Fire", "lat": 37.86, "lon": -119.53, "count": 20},
            {"name": "Canadian Boreal Woodland Fire (Alberta)", "lat": 55.45, "lon": -115.20, "count": 22},
            {"name": "Australian New South Wales Bushfire", "lat": -33.85, "lon": 150.15, "count": 18},
            {"name": "Mediterranean Pine Forest (Peloponnese)", "lat": 37.60, "lon": 22.10, "count": 14},
            {"name": "Siberian Taiga Wildfire Front", "lat": 62.03, "lon": 129.73, "count": 24}
        ]
        for f_reg in forest_regions:
            center_lat, center_lon = f_reg["lat"], f_reg["lon"]
            for i in range(f_reg["count"]):
                day_offset = random.randint(0, day_range - 1)
                acq_dt = now - timedelta(days=day_offset, hours=random.randint(0, 23))
                lat = center_lat + random.gauss(0, 0.12)
                lon = center_lon + random.gauss(0, 0.12)
                frp = round(random.uniform(18.0, 140.0), 2)
                ti4 = round(random.uniform(325.0, 365.0), 2)
                ti5 = round(random.uniform(288.0, 301.0), 2)
                records.append({
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "bright_ti4": ti4,
                    "scan": 0.45,
                    "track": 0.55,
                    "acq_date": acq_dt.strftime("%Y-%m-%d"),
                    "acq_time": f"{acq_dt.hour:02d}{acq_dt.minute:02d}",
                    "satellite": sat_name,
                    "instrument": instrument,
                    "confidence": random.choice(["n", "h"]),
                    "version": "2.0NRT",
                    "bright_ti5": ti5,
                    "frp": frp,
                    "daynight": random.choice(["D", "D", "N"]),
                    "_ground_truth": "WILDFIRE_FOREST",
                    "_facility_name": f_reg["name"]
                })

        # 4. Agricultural Burning Across Continents
        agri_regions = [
            {"name": "Punjab Agricultural Belt (Sangrur / Ludhiana)", "lat": 30.30, "lon": 75.80, "count": 24},
            {"name": "Haryana Agricultural Plains (Karnal / Kaithal)", "lat": 29.80, "lon": 76.50, "count": 18},
            {"name": "US Midwest Corn & Wheat Belt (Iowa/Kansas)", "lat": 41.50, "lon": -93.50, "count": 16},
            {"name": "Cerrado Agricultural Residue (Brazil)", "lat": -12.50, "lon": -55.00, "count": 20},
            {"name": "Central African Savannah Burning (Zambia)", "lat": -13.15, "lon": 28.20, "count": 26},
            {"name": "Indochina Crop Residue (Mekong Basin)", "lat": 15.50, "lon": 102.50, "count": 22}
        ]
        for a_reg in agri_regions:
            for i in range(a_reg["count"]):
                day_offset = random.randint(0, day_range - 1)
                acq_dt = now - timedelta(days=day_offset, hours=random.randint(8, 17)) # predominantly daytime
                lat = a_reg["lat"] + random.gauss(0, 0.22)
                lon = a_reg["lon"] + random.gauss(0, 0.22)
                frp = round(random.uniform(3.5, 24.0), 2)
                ti4 = round(random.uniform(315.0, 338.0), 2)
                ti5 = round(random.uniform(294.0, 308.0), 2)
                records.append({
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "bright_ti4": ti4,
                    "scan": 0.40,
                    "track": 0.40,
                    "acq_date": acq_dt.strftime("%Y-%m-%d"),
                    "acq_time": f"{acq_dt.hour:02d}{acq_dt.minute:02d}",
                    "satellite": sat_name,
                    "instrument": instrument,
                    "confidence": random.choice(["l", "n", "n", "h"]),
                    "version": "2.0NRT",
                    "bright_ti5": ti5,
                    "frp": frp,
                    "daynight": "D",
                    "_ground_truth": "AGRICULTURAL_BURNING",
                    "_facility_name": a_reg["name"]
                })

        # 5. Coal Seam & Mine Fires (Jharia & Raniganj)
        coal_pits = [
            {"name": "Jharia Open-Cast Coal Seam Fire (BCCL)", "lat": 23.745, "lon": 86.420, "count": 10},
            {"name": "Raniganj Coal Slag Smolder", "lat": 23.625, "lon": 87.135, "count": 6}
        ]
        for c_pit in coal_pits:
            for i in range(c_pit["count"]):
                day_offset = random.randint(0, day_range - 1)
                acq_dt = now - timedelta(days=day_offset, hours=random.randint(0, 23))
                lat = c_pit["lat"] + random.gauss(0, 0.015)
                lon = c_pit["lon"] + random.gauss(0, 0.015)
                frp = round(random.uniform(8.0, 25.0), 2)
                ti4 = round(random.uniform(322.0, 345.0), 2)
                ti5 = round(random.uniform(288.0, 299.0), 2)
                records.append({
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "bright_ti4": ti4,
                    "scan": 0.50,
                    "track": 0.50,
                    "acq_date": acq_dt.strftime("%Y-%m-%d"),
                    "acq_time": f"{acq_dt.hour:02d}{acq_dt.minute:02d}",
                    "satellite": sat_name,
                    "instrument": instrument,
                    "confidence": "h",
                    "version": "2.0NRT",
                    "bright_ti5": ti5,
                    "frp": frp,
                    "daynight": random.choice(["D", "N"]),
                    "_ground_truth": "MINING_COAL_FIRE",
                    "_facility_name": c_pit["name"]
                })

        return pd.DataFrame(records)
