import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from backend.config import Config

logger = logging.getLogger(__name__)

class HotspotStorage:
    """
    SQLite & GeoJSON GIS Storage Layer for Fire Detections,
    Classifications, and Tactical Incident Records.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables and spatial query indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hotspots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_uid TEXT UNIQUE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                acq_date TEXT,
                acq_time TEXT,
                satellite TEXT,
                instrument TEXT,
                bright_ti4 REAL,
                bright_ti5 REAL,
                delta_t REAL,
                frp REAL,
                daynight TEXT,
                confidence_str TEXT,
                predicted_class TEXT NOT NULL,
                confidence REAL,
                alert_level TEXT,
                nearest_facility TEXT,
                facility_type TEXT,
                dist_to_industrial_km REAL,
                is_inside_buffer INTEGER,
                persistence_score REAL,
                recurrence_count INTEGER,
                frp_zscore REAL,
                is_anomaly INTEGER,
                tactical_explanation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotspots_lat_lon ON hotspots (latitude, longitude);
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotspots_class ON hotspots (predicted_class);
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotspots_date ON hotspots (acq_date);
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotspots_frp ON hotspots (frp);
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_code TEXT UNIQUE,
                facility_name TEXT,
                latitude REAL,
                longitude REAL,
                severity TEXT,
                predicted_class TEXT,
                frp REAL,
                zscore REAL,
                status TEXT DEFAULT 'ACTIVE',
                details TEXT,
                dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()

    def clear_all_hotspots(self):
        """Clear all hotspots from database to load a fresh official NASA FIRMS snapshot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hotspots")
            conn.commit()
            logger.info("Cleared existing hotspot records for official NASA FIRMS synchronization.")

    def save_classified_hotspots(self, hotspots: List[Dict[str, Any]]) -> int:
        """Insert or update batch of classified satellite hotspots."""
        inserted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for idx, h in enumerate(hotspots):
                uid = h.get("detection_uid") or f"{h.get('latitude', 0):.5f}_{h.get('longitude', 0):.5f}_{h.get('acq_date','')}_{h.get('acq_time','')}_{h.get('satellite','')}_{idx}"
                try:
                    cursor.execute("""
                    INSERT INTO hotspots (
                        detection_uid, latitude, longitude, acq_date, acq_time,
                        satellite, instrument, bright_ti4, bright_ti5, delta_t,
                        frp, daynight, confidence_str, predicted_class, confidence,
                        alert_level, nearest_facility, facility_type, dist_to_industrial_km,
                        is_inside_buffer, persistence_score, recurrence_count,
                        frp_zscore, is_anomaly, tactical_explanation
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?
                    )
                    ON CONFLICT(detection_uid) DO UPDATE SET
                        predicted_class=excluded.predicted_class,
                        confidence=excluded.confidence,
                        alert_level=excluded.alert_level,
                        frp_zscore=excluded.frp_zscore,
                        is_anomaly=excluded.is_anomaly,
                        tactical_explanation=excluded.tactical_explanation;
                    """, (
                        uid,
                        h.get("latitude"),
                        h.get("longitude"),
                        h.get("acq_date"),
                        h.get("acq_time"),
                        h.get("satellite"),
                        h.get("instrument", "VIIRS"),
                        h.get("bright_ti4"),
                        h.get("bright_ti5"),
                        h.get("delta_t"),
                        h.get("frp", 0.0),
                        h.get("daynight"),
                        str(h.get("confidence", "")),
                        h.get("predicted_class", "AGRICULTURAL_BURNING"),
                        h.get("classification_confidence", 0.95),
                        h.get("alert_level", "NORMAL"),
                        h.get("nearest_facility"),
                        h.get("facility_type"),
                        h.get("dist_to_industrial_km"),
                        1 if h.get("is_inside_buffer") else 0,
                        h.get("persistence_score"),
                        h.get("recurrence_count", 1),
                        h.get("frp_zscore", 0.0),
                        1 if h.get("is_anomaly") else 0,
                        h.get("tactical_explanation")
                    ))
                    inserted_count += 1
                except Exception as e:
                    logger.debug(f"Row insert skipped: {e}")

            conn.commit()
        return inserted_count

    def query_hotspots(
        self,
        category: Optional[str] = None,
        min_frp: float = 0.0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 200000
    ) -> List[Dict[str, Any]]:
        """Query hotspots with multi-dimensional filtering."""
        query = "SELECT * FROM hotspots WHERE frp >= ? AND confidence >= ?"
        params = [min_frp, min_confidence]

        if category and category != "ALL":
            query += " AND predicted_class = ?"
            params.append(category)

        if start_date:
            query += " AND acq_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND acq_date <= ?"
            params.append(end_date)

        query += " ORDER BY frp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Aggregate statistics for tactical dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total hotspots
            cursor.execute("SELECT COUNT(*) FROM hotspots")
            total_count = cursor.fetchone()[0]

            # Breakdown by category
            cursor.execute("""
            SELECT predicted_class, COUNT(*), AVG(frp), MAX(frp)
            FROM hotspots GROUP BY predicted_class
            """)
            breakdown = {}
            for row in cursor.fetchall():
                breakdown[row[0]] = {
                    "count": row[1],
                    "avg_frp": round(row[2] or 0.0, 1),
                    "max_frp": round(row[3] or 0.0, 1)
                }

            # Emergency active alerts count
            cursor.execute("""
            SELECT COUNT(*) FROM hotspots
            WHERE predicted_class = 'INDUSTRIAL_ACCIDENTAL_FIRE'
               OR alert_level LIKE '%CRITICAL%'
            """)
            emergency_count = cursor.fetchone()[0]

            # Highest FRP incident
            cursor.execute("""
            SELECT nearest_facility, predicted_class, frp, acq_date, latitude, longitude
            FROM hotspots ORDER BY frp DESC LIMIT 1
            """)
            peak_row = cursor.fetchone()
            peak_hotspot = dict(peak_row) if peak_row else None

            return {
                "total_detections": total_count,
                "category_breakdown": breakdown,
                "active_emergencies": emergency_count,
                "peak_hotspot": peak_hotspot
            }

    def to_geojson(self, category: Optional[str] = None, min_frp: float = 0.0) -> Dict[str, Any]:
        """Export classified detections into standard GIS GeoJSON format for QGIS / ArcGIS."""
        records = self.query_hotspots(category=category, min_frp=min_frp, limit=5000)
        features = []
        for r in records:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [r["longitude"], r["latitude"]]
                },
                "properties": {
                    "id": r["id"],
                    "category": r["predicted_class"],
                    "confidence": r["confidence"],
                    "alert_level": r["alert_level"],
                    "frp_mw": r["frp"],
                    "bright_ti4": r["bright_ti4"],
                    "bright_ti5": r["bright_ti5"],
                    "delta_t": r["delta_t"],
                    "date": r["acq_date"],
                    "time": r["acq_time"],
                    "satellite": r["satellite"],
                    "nearest_facility": r["nearest_facility"],
                    "facility_type": r["facility_type"],
                    "dist_km": r["dist_to_industrial_km"],
                    "persistence_score": r["persistence_score"],
                    "zscore": r["frp_zscore"],
                    "explanation": r["tactical_explanation"]
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
            "features": features
        }

    def to_kml(self, category: Optional[str] = None) -> str:
        """Export detections to Google Earth KML format."""
        records = self.query_hotspots(category=category, limit=2000)
        kml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '<Document>',
            '<name>NTRO Industrial Fire &amp; Thermal Sources</name>'
        ]
        for r in records:
            name = f"{r['predicted_class']} ({r['frp']} MW)"
            desc = f"Facility: {r['nearest_facility']}&lt;br/&gt;FRP: {r['frp']} MW&lt;br/&gt;Date: {r['acq_date']} {r['acq_time']}&lt;br/&gt;Alert: {r['alert_level']}"
            kml.append('<Placemark>')
            kml.append(f'<name>{name}</name>')
            kml.append(f'<description>{desc}</description>')
            kml.append('<Point>')
            kml.append(f'<coordinates>{r["longitude"]},{r["latitude"]},0</coordinates>')
            kml.append('</Point>')
            kml.append('</Placemark>')
        kml.append('</Document>')
        kml.append('</kml>')
        return "\n".join(kml)
