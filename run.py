#!/usr/bin/env python3
"""
NTRO Industrial Fire AI - Main System Launcher
Problem Statement ID: 26162
National Technical Research Organisation (NTRO)
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import Config

def print_banner():
    banner = r"""
========================================================================================
   _   _ _____ ____   ___    ___           _           _        _       _      _ 
  | \ | |_   _|  _ \ / _ \  |_ _|         | |         | |      (_)     | |    (_)
  |  \| | | | | |_) | | | |  | | _ __   __| |_   _ ___| |_ _ __ _  __ _| |     _ 
  | . ` | | | |  _ <| | | |  | || '_ \ / _` | | | / __| __| '__| |/ _` | |    | |
  | |\  | | | | |_) | |_| | _| || | | | (_| | |_| \__ \ |_| |  | | (_| | |____| |
  |_| \_| |_| |____/ \___/ |___|_| |_|\__,_|\__,_|___/\__|_|  |_|\__,_|\_____/|_|
========================================================================================
 AI-Based Detection & Classification of Industrial Fires & Persistent Thermal Sources
 Problem Statement ID: 26162 | National Technical Research Organisation (NTRO)
 Theme: Disaster Management | NASA FIRMS + OpenStreetMap (OSM) + Bi-Spectral Satellite AI
========================================================================================
"""
    print(banner)

def main():
    print_banner()
    
    # Check model artifact
    model_artifact = Config.ARTIFACTS_DIR / "fire_classifier.joblib"
    if not model_artifact.exists():
        print("[+] Model artifacts not found. Initiating AI training pipeline...")
        from model.train import train_and_evaluate
        train_and_evaluate()
        print("[+] Training completed successfully!\n")
    else:
        print(f"[+] Loaded existing trained AI model: {model_artifact}\n")

    # Check MAP_KEY status
    if Config.is_firms_key_valid():
        print(f"[+] NASA FIRMS MAP_KEY detected. System is running in LIVE SATELLITE MODE.")
    else:
        print("[!] NOTICE: FIRMS_MAP_KEY is currently empty in .env.")
        print("    System will run in SIMULATED SATELLITE TELEMETRY MODE with high-fidelity benchmark feeds.")
        print("    You can add your MAP_KEY anytime in .env or via the in-app Settings modal!\n")

    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    print(f"[+] Launching NTRO Geospatial Command Center at: http://{host}:{port}")
    print("    Press Ctrl+C to stop the server.\n")

    from backend.app import app
    app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    main()
