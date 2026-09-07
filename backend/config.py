import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

class Config:
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / 'data'
    MODEL_DIR = BASE_DIR / 'model'
    ARTIFACTS_DIR = BASE_DIR / 'model' / 'artifacts'
    DATABASE_PATH = BASE_DIR / 'data' / 'hotspots.db'
    CATALOG_PATH = BASE_DIR / 'data' / 'industrial_catalog.json'
    
    # NASA FIRMS API
    FIRMS_MAP_KEY = os.getenv('FIRMS_MAP_KEY', '').strip()
    FIRMS_BASE_URL = 'https://firms.modaps.eosdis.nasa.gov'
    
    # Server settings
    FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    
    # Defaults
    DEFAULT_SENSOR = os.getenv('DEFAULT_SENSOR', 'VIIRS_NOAA20_NRT')
    DEFAULT_DAY_RANGE = int(os.getenv('DEFAULT_DAY_RANGE', 3))
    
    # Thresholds
    CLUSTER_RADIUS_KM = float(os.getenv('CLUSTER_RADIUS_KM', 1.0))
    PERSISTENCE_MIN_HITS = int(os.getenv('PERSISTENCE_MIN_HITS', 3))
    ANOMALY_ZSCORE_THRESHOLD = float(os.getenv('ANOMALY_ZSCORE_THRESHOLD', 2.5))
    
    @classmethod
    def is_firms_key_valid(cls) -> bool:
        return bool(cls.FIRMS_MAP_KEY and cls.FIRMS_MAP_KEY != 'your_firms_map_key_here' and len(cls.FIRMS_MAP_KEY) >= 16)
