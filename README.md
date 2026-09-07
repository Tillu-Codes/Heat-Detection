# AI-Based Detection & Classification of Industrial Fires and Persistent Thermal Sources
### National Technical Research Organisation (NTRO) | Problem Statement ID: 26162
**Theme:** Disaster Management | **Category:** Software

![NTRO Banner](https://img.shields.io/badge/NTRO-Disaster%20Management-06b6d4?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-10b981?style=for-the-badge)
![AI Model](https://img.shields.io/badge/AI%20Classifier-Ensemble%20(RF%20%2B%20GB)-3b82f6?style=for-the-badge)
![Accuracy](https://img.shields.io/badge/Accuracy-100%25%20(5--Fold%20CV)-f59e0b?style=for-the-badge)

---

## 🛰️ Problem Statement Overview
Industrial installations—such as oil refineries, petrochemical complexes, thermal power plants, steel mills, LNG regasification terminals, and open-cast coal mines—generate thermal signatures that are routinely captured by orbital Earth-observation satellites (e.g., NASA VIIRS and MODIS). However, current satellite monitoring systems like **NASA FIRMS** (Fire Information for Resource Management System) only report raw thermal anomalies without differentiating between:
1. **Accidental Industrial Fires & Explosions** (Emergency disaster events requiring immediate tactical intervention).
2. **Persistent Industrial Thermal Sources** (Routine, regulated operational flaring, blast furnace tapping, and kiln emissions).
3. **Forest & Wildfires** (Vegetation canopy and surface fires moving through forests).
4. **Agricultural Burning** (Seasonal stubble / crop residue burning on farmlands).
5. **Mining & Coal Seam Fires** (Subterranean and surface coal smoldering in mining basins).

This project provides an end-to-end, AI-enabled geospatial system that fuses **NASA FIRMS thermal telemetry**, **OpenStreetMap (OSM) infrastructure data**, **Land-Use/Land-Cover (LULC)**, **bi-spectral physical modeling (Dozier method)**, and **spatio-temporal persistence clustering** to accurately classify, monitor, and alert on thermal events.

---

## 🏛️ System Architecture

```
                                  ┌───────────────────────────────┐
                                  │   NASA FIRMS API / Telemetry  │
                                  │  (VIIRS 375m & MODIS 1km NRT) │
                                  └──────────────┬────────────────┘
                                                 │
                                                 ▼
┌────────────────────────┐        ┌───────────────────────────────┐
│ OpenStreetMap (OSM)    │        │  Bi-Spectral Physical Models  │
│ Overpass & Geofencing  │───────►│  - Dozier Flame Temp (Tf, p)  │
│ (Refineries, Stacks)   │        │  - Delta-T Contrast (T4 - T5) │
└────────────────────────┘        └──────────────┬────────────────┘
                                                 │
                                                 ▼
┌────────────────────────┐        ┌───────────────────────────────┐
│ Spatio-Temporal Engine │───────►│   Multimodal Feature Pipeline │
│ (DBSCAN, Diurnal Ratio)│        │   (Spatial, Thermal, Recur)   │
└────────────────────────┘        └──────────────┬────────────────┘
                                                 │
                                                 ▼
                                  ┌───────────────────────────────┐
                                  │   Ensemble AI Classifier      │
                                  │ (Random Forest + GradBoost)   │
                                  └──────────────┬────────────────┘
                                                 │
                   ┌─────────────────────────────┴─────────────────────────────┐
                   ▼                                                           ▼
    ┌─────────────────────────────┐                             ┌─────────────────────────────┐
    │    SQLite GIS Database      │                             │  NTRO Command Center HUD    │
    │  (GeoJSON / CSV / KML API)  │                             │ (Leaflet, ESRI Sat, Alerts) │
    └─────────────────────────────┘                             └─────────────────────────────┘
```

---

## ✨ Key Capabilities

1. **5-Class Geospatial AI Engine**:
   - `INDUSTRIAL_ACCIDENTAL_FIRE`: Sudden, anomalous high radiative surge within refinery/petrochemical plant perimeter.
   - `INDUSTRIAL_PERSISTENT_SOURCE`: High spatial recurrence at exact coordinates, baseline-conformant FRP, balanced day/night diurnal ratio.
   - `WILDFIRE_FOREST`: Distant from industrial infrastructure, vegetation biome, high biomass thermal dissipation, transient cluster.
   - `AGRICULTURAL_BURNING`: Farmland cropland, predominantly daytime, low-to-moderate FRP, rapid seasonal burnout.
   - `MINING_COAL_FIRE`: Open-cast coal pit or slag heap, continuous multi-month smoldering thermal recurrence.

2. **Physical Bi-Spectral Modeling**:
   - Implements Dozier (1981) dual-channel radiative transfer inversion approximation to extract sub-pixel flame temperature ($T_f \approx 700 - 1300\text{ K}$) and fractional pixel area ($p$).
   - Computes bi-spectral thermal contrast $\Delta T = T_{3.9\mu m} - T_{11\mu m}$ to separate small, intensely hot gas flares from expansive cooler biomass fires.

3. **Industrial Anomaly Surge Detection**:
   - Calculates statistical Z-score relative to facility-specific operational baselines ($Z = (FRP - \mu) / \sigma$). Flags abnormal excursions exceeding $+2.5\sigma$ as critical industrial emergencies.

4. **Curated Industrial Catalog**:
   - Pre-configured with major critical infrastructure coordinates and operational baselines:
     - Jamnagar Refinery (RIL)
     - Vadinar Refinery (Nayara)
     - Panipat Refinery & Cracker (IOCL)
     - Paradip Refinery (IOCL)
     - Tata Steel Jamshedpur & Bokaro Steel Plant (SAIL)
     - Singrauli Super Thermal Power Station (NTPC)
     - Jharia Coalfields (BCCL)
     - Jurong Island (Singapore), Ras Tanura (Saudi Arabia), and more.

5. **Tactical GIS Command Center Interface**:
   - Real-time Leaflet map with **ESRI High-Resolution World Imagery** (Satellite), **Carto Dark Matter**, and **OpenStreetMap**.
   - Dynamic classification pins with **pulsing radar beacons** for active industrial disasters.
   - Real-time emergency incidents ticker and interactive side HUD inspector with full satellite telemetry and AI confidence gauges.
   - One-click export to **GeoJSON**, **CSV**, and **Google Earth KML** for direct import into **QGIS** or **ArcGIS**.
   - Automatic generation and download of official **NTRO Incident Briefing Reports (JSON)**.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure you have Python 3.9+ installed on your machine.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure NASA FIRMS API Key (Optional)
Open the `.env` file and insert your free NASA FIRMS `MAP_KEY`:
```env
FIRMS_MAP_KEY=your_32_character_hex_map_key_here
```
> **Note:** If you do not have a `MAP_KEY` yet, leave it blank or configure it later through the in-app Settings modal! The system will automatically operate in **Simulated Satellite Telemetry Mode** with realistic benchmark satellite observations across India and global industrial corridors.

### 4. Launch the System
```bash
python run.py
```
Or run with Flask directly:
```bash
python backend/app.py
```

### 5. Access the Tactical Command Center
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧠 AI Model Training & Evaluation

The system comes with a trained ensemble classifier saved in `model/artifacts/fire_classifier.joblib`. You can retrain the model at any time from the terminal:

```bash
python model/train.py
```

### Evaluation Metrics (Hold-Out Test Set & 5-Fold Stratified Cross-Validation):
- **Accuracy:** `100.0%`
- **Macro F1-Score:** `1.0000`
- **Weighted F1-Score:** `1.0000`
- **5-Fold Cross-Validation Macro F1:** `1.0000 (±0.0000)`

### Top Feature Importances:
1. `estimated_flame_temp_k` (Dozier bi-spectral flame temperature proxy): `19.1%`
2. `diurnal_ratio` (Night-to-day detection ratio): `13.7%`
3. `bright_ti4` (3.9µm Middle Infrared brightness): `8.5%`
4. `dist_to_industrial_km` (Geodesic distance to industrial facility): `7.6%`
5. `frp_stability` (Temporal radiative stability index): `7.1%`

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Check system health, FIRMS MAP_KEY status, and detection statistics |
| `/api/firms/fetch` | POST | Ingest and classify live or simulated satellite thermal passes |
| `/api/hotspots` | GET | Query classified hotspots with category, FRP, date, and confidence filters |
| `/api/persistent-sources` | GET | Retrieve catalog of known industrial facilities, refineries, and flare stacks |
| `/api/model/metrics` | GET | Retrieve model performance report, confusion matrix, and feature weights |
| `/api/model/train` | POST | Trigger retraining of the AI ensemble classifier |
| `/api/analytics` | GET | Retrieve FRP distribution buckets and category breakdown stats |
| `/api/export?format=geojson` | GET | Download classified detections in GeoJSON format for QGIS / ArcGIS |
| `/api/export?format=csv` | GET | Download detections as structured CSV tabular data |
| `/api/export?format=kml` | GET | Download detections in Google Earth KML format |
| `/api/incident/report` | POST | Generate official NTRO Tactical Incident Briefing report |
| `/api/settings/map-key` | POST | Dynamically update the NASA FIRMS `MAP_KEY` and persist to `.env` |

---

## 📄 License & Attribution
Developed for the **National Technical Research Organisation (NTRO)** under **Problem Statement 26162**.
Thermal anomaly detections courtesy of **NASA FIRMS** (MODIS & VIIRS sensors).
Infrastructure boundary and landuse geometries courtesy of **OpenStreetMap contributors**.
