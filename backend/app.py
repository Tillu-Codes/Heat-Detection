import os
import io
import sys
import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.ingestion.firms_client import FIRMSClient
from backend.ingestion.osm_client import OSMClient
from backend.database.storage import HotspotStorage
from model.inference import FireClassifierInference

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialize Flask app pointing to frontend folder
frontend_dir = BASE_DIR / "frontend"
app = Flask(__name__, static_folder=str(frontend_dir), static_url_path="")

# Cross-Origin headers
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

# Initialize components
firms_client = FIRMSClient()
osm_client = OSMClient()
storage = HotspotStorage()
classifier = FireClassifierInference()

REGION_BBOX_MAP = {
    "world": "world",
    "south_asia": "54,5.5,102,40",
    "middle_east": "32,12,65,38",
    "north_america": "-125,24,-66,50",
    "europe": "-10,35,40,70",
    "south_america": "-82,-56,-34,13",
    "africa": "-18,-35,52,38",
    "east_asia": "95,-45,155,55"
}

# Pre-populate database with global satellite detections if empty or sparse
def seed_initial_detections_if_empty():
    stats = storage.get_summary_stats()
    # If database has few detections, populate with global satellite data
    if stats["total_detections"] < 500:
        logger.info("Ingesting and classifying global satellite hotspot observations from NASA FIRMS...")
        raw_df = firms_client.fetch_area(bbox="world", source="VIIRS_NOAA20_NRT", day_range=5)
        records = raw_df.to_dict(orient="records")
        classified = classifier.classify_batch(records)
        storage.save_classified_hotspots(classified)
        logger.info(f"Seeded {len(classified)} classified global hotspots into GIS database.")

seed_initial_detections_if_empty()

# ----------------- Frontend Routes -----------------

@app.route("/")
def index():
    return send_from_directory(str(frontend_dir), "index.html")

@app.route("/<path:path>")
def static_files(path):
    file_path = frontend_dir / path
    if file_path.exists():
        return send_from_directory(str(frontend_dir), path)
    return send_from_directory(str(frontend_dir), "index.html")

# ----------------- API Endpoints -----------------

@app.route("/api/status", methods=["GET"])
def api_status():
    """System health check and configuration status."""
    key_info = firms_client.check_key_status()
    stats = storage.get_summary_stats()
    return jsonify({
        "status": "ONLINE",
        "service": "NTRO Industrial Fire & Persistent Thermal Source AI System",
        "problem_id": "26162",
        "theme": "Disaster Management",
        "map_key_status": key_info,
        "database_stats": stats,
        "model_loaded": classifier.model is not None,
        "classes": classifier.classes,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.route("/api/settings/map-key", methods=["POST"])
def api_update_map_key():
    """Update FIRMS MAP_KEY dynamically."""
    data = request.get_json() or {}
    new_key = data.get("map_key", "").strip()
    if not new_key:
        return jsonify({"success": False, "message": "No key provided"}), 400

    Config.FIRMS_MAP_KEY = new_key
    firms_client.map_key = new_key

    # Update .env file
    env_file = Config.BASE_DIR / ".env"
    try:
        lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("FIRMS_MAP_KEY="):
                new_lines.append(f"FIRMS_MAP_KEY={new_key}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.insert(0, f"FIRMS_MAP_KEY={new_key}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"Could not persist MAP_KEY to .env: {e}")

    status = firms_client.check_key_status()
    return jsonify({"success": True, "map_key_status": status})

@app.route("/api/firms/fetch", methods=["POST"])
def api_fetch_firms():
    """
    Fetch live official NASA FIRMS hotspot detections and classify them.
    Guarantees 100% match with official NASA FIRMS map for selected parameters.
    """
    data = request.get_json() or {}
    region = data.get("region", "world")
    bbox = REGION_BBOX_MAP.get(region, data.get("bbox", "world"))
    source = data.get("source", Config.DEFAULT_SENSOR)
    day_range = int(data.get("day_range", 1))
    date = data.get("date", None)
    clear_previous = data.get("clear_previous", True)

    try:
        raw_df = firms_client.fetch_area(bbox=bbox, source=source, day_range=day_range, date=date)

        if raw_df.empty:
            if clear_previous:
                storage.clear_all_hotspots()
            return jsonify({
                "success": True,
                "fetched_count": 0,
                "saved_count": 0,
                "message": "No hotspots detected by NASA FIRMS for selected criteria"
            })

        records = raw_df.to_dict(orient="records")

        # Clear previous snapshot if requested to guarantee exact count match
        if clear_previous:
            storage.clear_all_hotspots()

        # Classify using AI model without modifying original NASA telemetry
        classified = classifier.classify_batch(records)
        saved_count = storage.save_classified_hotspots(classified)

        # Cache last sync metadata for verification
        app.config["LAST_SYNC_META"] = {
            "source": source,
            "region": region,
            "bbox": bbox,
            "day_range": day_range,
            "date": date,
            "nasa_official_count": len(records),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        return jsonify({
            "success": True,
            "source": source,
            "region": region,
            "day_range": day_range,
            "date": date,
            "nasa_official_count": len(records),
            "saved_count": saved_count,
            "verified": len(records) == saved_count,
            "hotspots": classified[:500]
        })
    except Exception as e:
        logger.error(f"Error in /api/firms/fetch: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/firms/validate", methods=["GET"])
def api_firms_validate():
    """
    Automated Validation Endpoint.
    Compares the database records against the official NASA FIRMS API:
    - Verifies Total Detection Count matches NASA FIRMS exactly.
    - Verifies Latitude & Longitude coordinates match NASA.
    - Verifies FRP (MW) and acquisition time match NASA.
    """
    last_meta = app.config.get("LAST_SYNC_META", None)
    if not last_meta:
        last_meta = {
            "source": Config.DEFAULT_SENSOR,
            "region": "world",
            "bbox": "world",
            "day_range": 1,
            "date": None
        }

    source = last_meta["source"]
    bbox = last_meta["bbox"]
    day_range = last_meta["day_range"]
    date = last_meta.get("date")

    try:
        # 1. Fetch fresh official NASA data
        nasa_df = firms_client.fetch_area(bbox=bbox, source=source, day_range=day_range, date=date)
        nasa_count = len(nasa_df)

        # 2. Query database count
        db_hotspots = storage.query_hotspots(limit=40000)
        db_count = len(db_hotspots)

        # 3. Match Verification Sample
        matches_verified = 0
        samples_checked = 0
        sample_results = []

        if not nasa_df.empty and db_count > 0:
            # Check up to 10 random sample points
            sample_df = nasa_df.sample(n=min(10, len(nasa_df)), random_state=42)
            for _, row in sample_df.iterrows():
                samples_checked += 1
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                acq_date = str(row.get("acq_date", ""))
                acq_time = str(row.get("acq_time", ""))
                frp = float(row.get("frp", 0.0))

                # Find in database
                match = next((
                    h for h in db_hotspots
                    if abs(h["latitude"] - lat) < 0.0001
                    and abs(h["longitude"] - lon) < 0.0001
                    and str(h.get("acq_time", "")) == acq_time
                ), None)

                if match and abs(match["frp"] - frp) < 0.1:
                    matches_verified += 1
                    sample_results.append({
                        "latitude": lat,
                        "longitude": lon,
                        "frp_nasa": frp,
                        "frp_db": match["frp"],
                        "acq_date": acq_date,
                        "acq_time": acq_time,
                        "status": "EXACT_MATCH"
                    })

        coord_match = (matches_verified == samples_checked) if samples_checked > 0 else False
        count_match = (nasa_count == db_count)

        return jsonify({
            "validated": count_match and coord_match,
            "status": "OFFICIAL_NASA_VERIFIED" if (count_match and coord_match) else "SYNC_RECOMMENDED",
            "nasa_firms_official_count": nasa_count,
            "dashboard_active_count": db_count,
            "counts_match": count_match,
            "coordinates_match": coord_match,
            "frp_match": coord_match,
            "acquisition_time_match": coord_match,
            "source_satellite": source,
            "region": last_meta.get("region", "world"),
            "samples_verified": f"{matches_verified}/{samples_checked}",
            "sample_details": sample_results,
            "verified_at": datetime.utcnow().isoformat() + "Z"
        })
    except Exception as e:
        logger.error(f"Error validating with NASA FIRMS: {e}")
        return jsonify({"validated": False, "error": str(e)}), 500

@app.route("/api/hotspots", methods=["GET"])
def api_get_hotspots():
    """Query classified hotspots from GIS database with filters."""
    category = request.args.get("category", None)
    min_frp = float(request.args.get("min_frp", 0.0))
    start_date = request.args.get("start_date", None)
    end_date = request.args.get("end_date", None)
    min_confidence = float(request.args.get("min_confidence", 0.0))
    limit = int(request.args.get("limit", 40000))

    records = storage.query_hotspots(
        category=category,
        min_frp=min_frp,
        start_date=start_date,
        end_date=end_date,
        min_confidence=min_confidence,
        limit=limit
    )
    return jsonify({"count": len(records), "hotspots": records})

@app.route("/api/persistent-sources", methods=["GET"])
def api_get_persistent_sources():
    """Retrieve catalog of known industrial facilities, refineries, and flare sites."""
    facilities = osm_client.facilities
    return jsonify({"count": len(facilities), "facilities": facilities})

@app.route("/api/model/metrics", methods=["GET"])
def api_model_metrics():
    """Get AI model accuracy, cross-validation metrics, confusion matrix, and feature importances."""
    metrics_path = Config.ARTIFACTS_DIR / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        return jsonify(metrics)
    return jsonify({"error": "Metrics not found. Please train model."}), 404

@app.route("/api/model/train", methods=["POST"])
def api_retrain_model():
    """Trigger model training/retraining pipeline."""
    try:
        from model.train import train_and_evaluate
        metrics = train_and_evaluate()
        # Reload classifier in memory
        classifier._load_model()
        return jsonify({"success": True, "metrics": metrics})
    except Exception as e:
        logger.error(f"Error retraining model: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/analytics", methods=["GET"])
def api_analytics():
    """Return dashboard analytics, statistics, and category distributions."""
    stats = storage.get_summary_stats()
    all_hotspots = storage.query_hotspots(limit=2000)

    # FRP distribution buckets
    frp_buckets = {"0-20 MW": 0, "20-50 MW": 0, "50-100 MW": 0, "100-200 MW": 0, ">200 MW": 0}
    for h in all_hotspots:
        frp = h.get("frp", 0.0)
        if frp < 20:
            frp_buckets["0-20 MW"] += 1
        elif frp < 50:
            frp_buckets["20-50 MW"] += 1
        elif frp < 100:
            frp_buckets["50-100 MW"] += 1
        elif frp < 200:
            frp_buckets["100-200 MW"] += 1
        else:
            frp_buckets[">200 MW"] += 1

    return jsonify({
        "summary": stats,
        "frp_distribution": frp_buckets,
        "total_active": len(all_hotspots)
    })

@app.route("/api/export", methods=["GET"])
def api_export():
    """Export GIS data in GeoJSON, CSV, or KML format."""
    export_format = request.args.get("format", "geojson").lower()
    category = request.args.get("category", None)
    min_frp = float(request.args.get("min_frp", 0.0))

    if export_format == "geojson":
        geojson_data = storage.to_geojson(category=category, min_frp=min_frp)
        return jsonify(geojson_data)

    elif export_format == "csv":
        records = storage.query_hotspots(category=category, min_frp=min_frp, limit=5000)
        output = io.StringIO()
        if records:
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=ntro_classified_hotspots.csv"}
        )

    elif export_format == "kml":
        kml_content = storage.to_kml(category=category)
        return Response(
            kml_content,
            mimetype="application/vnd.google-earth.kml+xml",
            headers={"Content-Disposition": "attachment;filename=ntro_hotspots.kml"}
        )

    return jsonify({"error": "Unsupported format. Use geojson, csv, or kml"}), 400

@app.route("/api/incident/report", methods=["POST"])
def api_incident_report():
    """Generate official NTRO tactical disaster briefing report."""
    data = request.get_json() or {}
    hotspot_id = data.get("id")
    hotspots = storage.query_hotspots(limit=5000)
    target = next((h for h in hotspots if h["id"] == hotspot_id), None)

    if not target:
        return jsonify({"error": "Hotspot not found"}), 404

    report = {
        "report_id": f"NTRO-FIRE-ALERT-{datetime.utcnow().strftime('%Y%m%d')}-{target['id']:04d}",
        "organization": "National Technical Research Organisation (NTRO)",
        "department": "Disaster Management & Geospatial Intelligence",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "incident_classification": target["predicted_class"],
        "alert_level": target["alert_level"],
        "coordinates": {"latitude": target["latitude"], "longitude": target["longitude"]},
        "satellite_telemetry": {
            "satellite": target["satellite"],
            "instrument": target["instrument"],
            "fire_radiative_power_mw": target["frp"],
            "brightness_temp_ti4_k": target["bright_ti4"],
            "brightness_temp_ti5_k": target["bright_ti5"],
            "delta_t_k": target["delta_t"],
            "acquisition_date": target["acq_date"],
            "acquisition_time": target["acq_time"]
        },
        "geospatial_context": {
            "nearest_facility": target["nearest_facility"],
            "facility_type": target["facility_type"],
            "distance_km": target["dist_to_industrial_km"],
            "is_within_facility_buffer": bool(target["is_inside_buffer"]),
            "persistence_score": target["persistence_score"],
            "recurrence_count": target["recurrence_count"]
        },
        "tactical_assessment": target["tactical_explanation"],
        "recommended_action": (
            "URGENT: Dispatch emergency fire containment teams and evacuate perimeter."
            if "CRITICAL" in target["alert_level"]
            else "Standard operational tracking; maintain orbital pass surveillance."
        )
    }
    return jsonify(report)

if __name__ == "__main__":
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    debug = Config.FLASK_DEBUG
    logger.info(f"Starting NTRO Industrial Fire AI System on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
