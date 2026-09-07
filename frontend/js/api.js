/**
 * NTRO Industrial Fire AI - API Client Service
 */

const API_BASE = '/api';

export const API = {
  async getStatus() {
    const res = await fetch(`${API_BASE}/status`);
    return await res.json();
  },

  async updateMapKey(key) {
    const res = await fetch(`${API_BASE}/settings/map-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ map_key: key })
    });
    return await res.json();
  },

  async fetchFirmsData(params = {}) {
    const res = await fetch(`${API_BASE}/firms/fetch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    return await res.json();
  },

  async getHotspots(filters = {}) {
    const query = new URLSearchParams();
    if (filters.category) query.append('category', filters.category);
    if (filters.min_frp) query.append('min_frp', filters.min_frp);
    if (filters.start_date) query.append('start_date', filters.start_date);
    if (filters.end_date) query.append('end_date', filters.end_date);
    if (filters.min_confidence) query.append('min_confidence', filters.min_confidence);

    const res = await fetch(`${API_BASE}/hotspots?${query.toString()}`);
    return await res.json();
  },

  async getPersistentSources() {
    const res = await fetch(`${API_BASE}/persistent-sources`);
    return await res.json();
  },

  async getModelMetrics() {
    const res = await fetch(`${API_BASE}/model/metrics`);
    return await res.json();
  },

  async retrainModel() {
    const res = await fetch(`${API_BASE}/model/train`, { method: 'POST' });
    return await res.json();
  },

  async getAnalytics() {
    const res = await fetch(`${API_BASE}/analytics`);
    return await res.json();
  },

  async generateIncidentReport(hotspotId) {
    const res = await fetch(`${API_BASE}/incident/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: hotspotId })
    });
    return await res.json();
  },

  async validateFirms() {
    const res = await fetch(`${API_BASE}/firms/validate`);
    return await res.json();
  },

  getExportUrl(format = 'geojson', category = null, minFrp = 0) {
    let url = `${API_BASE}/export?format=${format}&min_frp=${minFrp}`;
    if (category && category !== 'ALL') {
      url += `&category=${encodeURIComponent(category)}`;
    }
    return url;
  }
};
