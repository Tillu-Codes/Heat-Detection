# NTRO Industrial Fire & Persistent Thermal Source AI System
## Technical Architecture & Mathematical Formulation Report
**Problem Statement ID:** 26162
**Organisation:** National Technical Research Organisation (NTRO)
**Department:** Geospatial Intelligence & Disaster Management

---

## 1. Executive Summary
Spaceborne thermal radiometers such as the **Visible Infrared Imaging Radiometer Suite (VIIRS)** aboard Suomi-NPP, NOAA-20, NOAA-21, and the **Moderate Resolution Imaging Spectroradiometer (MODIS)** aboard Terra and Aqua provide near-real-time global coverage of surface thermal anomalies. However, standard NASA FIRMS products (MCD14DL, VNP14IMGTDL) treat all hotspots as generic thermal anomalies.

This platform implements an intelligent multi-sensor geospatial fusion architecture that resolves the fundamental challenge set by NTRO:
1. **Accidental Industrial Fires & Explosions:** Catastrophic heat releases inside high-risk refineries, petrochemical hubs, or LNG facilities.
2. **Persistent Industrial Operational Sources:** Steady, regulated elevated/ground gas flares, blast furnaces, and smelter tapholes.
3. **Forest & Canopy Wildfires:** Spreading biomass combustion fronts across forest biomes.
4. **Agricultural Stubble Burning:** Diurnal, transient crop residue fires in agricultural belts.
5. **Mining & Coal Seam Smoldering:** Continuous low-to-medium thermal emission in open-cast coal basins.

---

## 2. Mathematical Formulation & Physical Modeling

### 2.1 Dozier Bi-Spectral Sub-Pixel Inversion
A typical satellite pixel (e.g. 375m for VIIRS I-bands or 1km for MODIS) is rarely filled entirely by flaming combustion. Instead, a sub-pixel fire occupies a fractional area $p \in (0, 1)$ with flame temperature $T_f$, while the ambient background occupies $(1 - p)$ at temperature $T_b$.

According to Planck's blackbody radiation law, the spectral radiance $L_\lambda(T)$ at wavelength $\lambda$ is:
$$L_\lambda(T) = \frac{2 h c^2}{\lambda^5 \left( \exp\left(\frac{h c}{\lambda k_B T}\right) - 1 \right)}$$

For dual channels—Channel 4 ($\lambda_4 \approx 3.9\,\mu\text{m}$, Middle Infrared) and Channel 5 ($\lambda_5 \approx 11\,\mu\text{m}$, Thermal Infrared)—the observed pixel radiances satisfy Dozier's system:
$$L_4(T_4) = p \cdot L_4(T_f) + (1 - p) \cdot L_4(T_b)$$
$$L_5(T_5) = p \cdot L_5(T_f) + (1 - p) \cdot L_5(T_b)$$

Because $L_4$ scales strongly with high temperatures ($\sim T^{10}$ around 800K), while $L_5$ scales moderately ($\sim T^4$), the temperature difference:
$$\Delta T = T_4 - T_5$$
acts as a powerful discriminator:
- **Gas flares & blast furnaces:** Small footprint ($p \ll 0.01$), extremely high temperature ($T_f > 1000\text{ K}$), resulting in large $\Delta T > 45\text{ K}$.
- **Wildfire fronts:** Moderate footprint ($p \approx 0.01 - 0.05$), temperature $T_f \approx 700 - 850\text{ K}$, moderate $\Delta T \approx 15 - 35\text{ K}$.
- **Coal smoldering & agricultural stubble:** Low flame temperature ($T_f \approx 500 - 650\text{ K}$), low $\Delta T \le 12\text{ K}$.

### 2.2 Spatio-Temporal Persistence Clustering
Persistent industrial sources maintain stationary emission at precise geographic coordinates. We calculate a continuous persistence score $P_s \in [0, 1]$ over historical passes:
$$P_s = \frac{1}{1 + \exp\left(-\kappa \left(N_{\text{hits}} - x_0\right)\right)} \times \left(1 + 0.15 \cdot \mathbb{I}(N_{\text{night}} > 0)\right)$$
where $N_{\text{hits}}$ is the recurrent count within a 1.0 km radius, $\kappa = 0.6$, and $x_0 = 4.0$.

Industrial flares exhibit a balanced or night-skewed diurnal ratio:
$$R_{\text{diurnal}} = \frac{N_{\text{night}}}{\max(1, N_{\text{day}})}$$
Conversely, agricultural stubble burning occurs almost exclusively during daylight hours ($R_{\text{diurnal}} \approx 0$).

### 2.3 Statistical Surge Anomaly Detector
For hotspots located within the buffer radius $R_B$ of an industrial facility, we compute the standardized radiative surge:
$$Z = \frac{\text{FRP}_{\text{obs}} - \mu_{\text{fac}}}{\sigma_{\text{fac}}}$$
- If $Z \ge 2.5$ or $\text{FRP}_{\text{obs}} > 140\text{ MW}$, the event is flagged as **INDUSTRIAL_ACCIDENTAL_FIRE** (Critical Emergency Alert).
- If $Z < 1.5$ and $P_s \ge 0.50$, the event is classified as **INDUSTRIAL_PERSISTENT_SOURCE** (Routine Operational).

---

## 3. Geospatial & Infrastructure Integration (OSM)
The system interfaces with OpenStreetMap (OSM) Overpass API to dynamically retrieve industrial land-use polygons and points of interest:
```overpass
[out:json][timeout:10];
(
  node["landuse"="industrial"](around:5000, lat, lon);
  way["landuse"="industrial"](around:5000, lat, lon);
  node["man_made"="flare"](around:5000, lat, lon);
  node["power"="plant"](around:5000, lat, lon);
  node["industrial"](around:5000, lat, lon);
);
out tags center;
```
Geodesic distance to the nearest polygon boundary is computed using the Vincenty/Haversine spherical metric.

---

## 4. Model Architecture & Cross-Validation
- **Ensemble Strategy:** Soft Voting Classifier combining an optimized **Random Forest** (150 trees, max depth 12) with a **Gradient Boosting Classifier** (120 stages, learning rate 0.08).
- **Stratification:** 5-Fold Stratified Cross-Validation on balanced multi-regional datasets.
- **Explainability:** Real-time generation of natural-language tactical briefings indicating why an event was categorized and recommending mitigation procedures to NTRO decision-makers.
