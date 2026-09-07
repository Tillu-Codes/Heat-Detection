/**
 * NTRO Industrial Fire AI - Leaflet GIS Map Visualization Module
 */

export class TacticalMap {
  constructor(containerId, onHotspotSelected) {
    this.containerId = containerId;
    this.onHotspotSelected = onHotspotSelected;
    this.map = null;
    
    // Layer Groups
    this.hotspotsLayer = null;
    this.facilitiesLayer = null;
    this.heatLayer = null;
    
    // Data stores
    this.currentHotspots = [];
    this.facilities = [];

    this.initMap();
  }

  initMap() {
    // Center globally by default for whole world coverage
    this.map = L.map(this.containerId, {
      center: [20.0, 10.0],
      zoom: 3,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false
    });

    // Zoom control at bottom left
    L.control.zoom({ position: 'bottomleft' }).addTo(this.map);

    // Basemaps
    const esriSatellite = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: 'Esri World Imagery, DigitalGlobe, GeoEye, Earthstar Geographics',
        maxZoom: 18
      }
    );

    const cartoDark = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
      }
    );

    const osmStandard = L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }
    );

    // Default to high-res ESRI Satellite for space-based visual verification
    esriSatellite.addTo(this.map);

    this.baseLayers = {
      satellite: esriSatellite,
      dark: cartoDark,
      osm: osmStandard
    };

    // Initialize layer groups
    this.facilitiesLayer = L.layerGroup().addTo(this.map);
    this.hotspotsLayer = L.layerGroup().addTo(this.map);
    this.heatLayer = L.layerGroup().addTo(this.map);

    // Live Cursor Coordinates Tracking HUD
    this.map.on('mousemove', (e) => {
      const lat = e.latlng.lat;
      const lon = e.latlng.lng;
      const latStr = `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? 'N' : 'S'}`;
      const lonStr = `${Math.abs(lon).toFixed(5)}° ${lon >= 0 ? 'E' : 'W'}`;
      const zoom = this.map.getZoom();

      const latEl = document.getElementById('cursor-lat');
      const lonEl = document.getElementById('cursor-lon');
      const zoomEl = document.getElementById('cursor-zoom');
      if (latEl) latEl.innerText = latStr;
      if (lonEl) lonEl.innerText = lonStr;
      if (zoomEl) zoomEl.innerText = zoom;
    });

    this.map.on('zoomend', () => {
      const zoomEl = document.getElementById('cursor-zoom');
      if (zoomEl) zoomEl.innerText = this.map.getZoom();
    });
  }

  flyToRegion(region) {
    const regionCenters = {
      world: { center: [20.0, 10.0], zoom: 3 },
      south_asia: { center: [22.5, 78.5], zoom: 5 },
      middle_east: { center: [27.0, 48.0], zoom: 5 },
      north_america: { center: [39.0, -98.0], zoom: 4 },
      europe: { center: [50.0, 15.0], zoom: 4 },
      south_america: { center: [-15.0, -60.0], zoom: 4 },
      africa: { center: [0.0, 20.0], zoom: 4 },
      east_asia: { center: [30.0, 115.0], zoom: 4 }
    };
    if (regionCenters[region]) {
      const rc = regionCenters[region];
      this.map.flyTo(rc.center, rc.zoom, { duration: 1.5 });
    }
  }

  setBasemap(name) {
    Object.values(this.baseLayers).forEach(layer => this.map.removeLayer(layer));
    if (this.baseLayers[name]) {
      this.baseLayers[name].addTo(this.map);
    }
  }

  renderFacilities(facilities) {
    this.facilities = facilities;
    this.facilitiesLayer.clearLayers();

    facilities.forEach(fac => {
      const radius = fac.radius_meters || 3000;
      const lat = fac.latitude;
      const lon = fac.longitude;

      // Geofence buffer circle
      const circle = L.circle([lat, lon], {
        radius: radius,
        color: '#06b6d4',
        weight: 1.5,
        dashArray: '4, 6',
        fillColor: '#06b6d4',
        fillOpacity: 0.08
      });

      // Facility center marker
      const centerMarker = L.circleMarker([lat, lon], {
        radius: 4,
        color: '#06b6d4',
        fillColor: '#fff',
        fillOpacity: 0.9,
        weight: 2
      });

      const tooltipContent = `
        <div style="font-family: 'Inter', sans-serif; font-size: 11px;">
          <strong style="color: #06b6d4;">${fac.name}</strong><br/>
          <span style="color: #94a3b8;">Type: ${fac.type.replace(/_/g, ' ')}</span><br/>
          <span style="color: #94a3b8;">Nominal Flaring: ${fac.baseline_frp_mean} MW</span>
        </div>
      `;

      circle.bindTooltip(tooltipContent, { sticky: true, opacity: 0.9 });
      centerMarker.bindTooltip(tooltipContent, { sticky: true, opacity: 0.9 });

      circle.addTo(this.facilitiesLayer);
      centerMarker.addTo(this.facilitiesLayer);
    });
  }

  renderHotspots(hotspots) {
    this.currentHotspots = hotspots;
    this.hotspotsLayer.clearLayers();
    this.heatLayer.clearLayers();

    if (!this.canvasRenderer) {
      this.canvasRenderer = L.canvas({ padding: 0.5 });
    }

    hotspots.forEach(h => {
      const lat = parseFloat(h.latitude);
      const lon = parseFloat(h.longitude);
      if (isNaN(lat) || isNaN(lon)) return;

      const category = h.predicted_class;
      const frp = parseFloat(h.frp) || 0.0;
      const isCritical = category === 'INDUSTRIAL_ACCIDENTAL_FIRE' || (h.alert_level && h.alert_level.includes('CRITICAL'));

      // Icon colors
      let pinColor = '#10b981'; // Forest Wildfire
      let catLabel = 'FOREST WILDFIRE';

      if (category === 'INDUSTRIAL_ACCIDENTAL_FIRE') {
        pinColor = '#ff2a55';
        catLabel = 'INDUSTRIAL FIRE (EMERGENCY)';
      } else if (category === 'INDUSTRIAL_PERSISTENT_SOURCE') {
        pinColor = '#ff9800';
        catLabel = 'PERSISTENT THERMAL SOURCE';
      } else if (category === 'AGRICULTURAL_BURNING') {
        pinColor = '#eab308';
        catLabel = 'AGRICULTURAL BURNING';
      } else if (category === 'MINING_COAL_FIRE') {
        pinColor = '#a855f7';
        catLabel = 'COAL / MINING';
      }

      // Format confidence
      let confDisplay = 'Nominal';
      const cStr = String(h.confidence_str || '').toLowerCase();
      if (cStr === 'h') confDisplay = 'High';
      else if (cStr === 'l') confDisplay = 'Low';
      else if (cStr === 'n') confDisplay = 'Nominal';
      else if (h.confidence_str) confDisplay = `${h.confidence_str}%`;

      // Format time (e.g. 0631 -> 06:31 UTC)
      let timeStr = String(h.acq_time || '');
      if (timeStr.length === 3) timeStr = `0${timeStr}`;
      if (timeStr.length === 4) timeStr = `${timeStr.slice(0,2)}:${timeStr.slice(2)} UTC`;

      const daynightDisplay = (h.daynight === 'D') ? 'Day ☀️' : 'Night 🌙';
      const satDisplay = `${h.satellite || 'VIIRS'} (${h.instrument || 'NRT'})`;

      // Dynamic radius based on FRP
      const radius = Math.min(14, Math.max(4.5, Math.round(Math.log1p(frp) * 2.6)));

      // Circle marker on canvas renderer for high performance
      const marker = L.circleMarker([lat, lon], {
        renderer: this.canvasRenderer,
        radius: radius,
        fillColor: pinColor,
        color: isCritical ? '#ff2a55' : '#ffffff',
        weight: isCritical ? 2.5 : 1.0,
        opacity: 0.95,
        fillOpacity: 0.85
      });

      // Comprehensive NASA Popup matching FIRMS
      const popupHtml = `
        <div style="font-family: 'Inter', sans-serif; font-size: 11px; min-width: 220px; color: #f8fafc; line-height: 1.5;">
          <div style="background: rgba(255,255,255,0.08); padding: 4px 8px; border-radius: 4px; margin-bottom: 6px; font-weight: 700; color: ${pinColor}; text-transform: uppercase;">
            ${catLabel}
          </div>
          <div><b>Coordinates:</b> ${lat.toFixed(5)}, ${lon.toFixed(5)}</div>
          <div><b>Acquisition Date:</b> ${h.acq_date || 'N/A'}</div>
          <div><b>Acquisition Time:</b> ${timeStr}</div>
          <div><b>Satellite / Sensor:</b> ${satDisplay}</div>
          <div><b>FRP (Fire Radiative Power):</b> <span style="color: #ff9800; font-weight: 700;">${frp.toFixed(2)} MW</span></div>
          <div><b>Brightness Temp:</b> ${h.bright_ti4 || 'N/A'} K (TI4) / ${h.bright_ti5 || 'N/A'} K (TI5)</div>
          <div><b>Confidence:</b> ${confDisplay}</div>
          <div><b>Day / Night:</b> ${daynightDisplay}</div>
          <div style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 6px; padding-top: 4px; color: #06b6d4;">
            <b>Nearest Facility:</b> ${h.nearest_facility || 'None in immediate vicinity'}<br/>
            <b>Distance:</b> ${h.dist_to_industrial_km || 'N/A'} km
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, { className: 'tactical-map-popup' });

      // Click listener to select hotspot and open inspector
      marker.on('click', () => {
        if (this.onHotspotSelected) {
          this.onHotspotSelected(h);
        }
      });

      marker.addTo(this.hotspotsLayer);

      // If critical industrial emergency, also place animated pulsing radar marker
      if (isCritical) {
        const pulseIcon = L.divIcon({
          className: 'custom-thermal-pin',
          html: '<div class="radar-marker marker-ind-fire" style="width: 24px; height: 24px;"><div class="radar-marker-pulse"></div></div>',
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });
        const pulseMarker = L.marker([lat, lon], { icon: pulseIcon, interactive: false });
        pulseMarker.addTo(this.hotspotsLayer);
      }
    });
  }

  flyToCoordinates(lat, lon, zoom = 12) {
    this.map.flyTo([lat, lon], zoom, {
      duration: 1.2,
      easeLinearity: 0.25
    });
  }

  toggleLayer(layerName, visible) {
    if (layerName === 'hotspots') {
      if (visible) this.hotspotsLayer.addTo(this.map);
      else this.map.removeLayer(this.hotspotsLayer);
    } else if (layerName === 'facilities') {
      if (visible) this.facilitiesLayer.addTo(this.map);
      else this.map.removeLayer(this.facilitiesLayer);
    } else if (layerName === 'heat') {
      if (visible) this.heatLayer.addTo(this.map);
      else this.map.removeLayer(this.heatLayer);
    }
  }
}
