import json
import urllib.request

def test_endpoint(path):
    url = f"http://127.0.0.1:5000{path}"
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode("utf-8"))
    print(f"[PASS] {path} -> HTTP {req.status}")
    return data

if __name__ == "__main__":
    print("--- Testing NTRO System Endpoints ---")
    s = test_endpoint("/api/status")
    print(f"  Service: {s['service']}")
    print(f"  Status: {s['status']}")
    print(f"  Model Loaded: {s['model_loaded']}")

    h = test_endpoint("/api/hotspots")
    print(f"  Hotspots in Database: {h['count']}")

    p = test_endpoint("/api/persistent-sources")
    print(f"  Industrial Facilities in Catalog: {p['count']}")

    m = test_endpoint("/api/model/metrics")
    print(f"  Holdout Test Accuracy: {m['accuracy'] * 100:.1f}%")
    print(f"  Macro F1: {m['f1_macro']}")
    print(f"  CV F1 Mean: {m['cv_f1_macro_mean'] * 100:.1f}%")

    a = test_endpoint("/api/analytics")
    print(f"  Total Active Hotspots: {a['total_active']}")
    print(f"  Active Emergencies: {a['summary']['active_emergencies']}")

    g = test_endpoint("/api/export?format=geojson")
    print(f"  GeoJSON FeatureCollection Points: {len(g['features'])}")

    # Test incident briefing generation
    if h['count'] > 0:
        first_id = h['hotspots'][0]['id']
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/incident/report",
            data=json.dumps({"id": first_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        rep = json.loads(resp.read().decode("utf-8"))
        print(f"[PASS] /api/incident/report -> Generated report: {rep['report_id']} ({rep['alert_level']})")

    print("\n[SUCCESS] All API endpoints verified successfully!")
