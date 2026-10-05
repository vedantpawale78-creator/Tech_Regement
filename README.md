# Semantic Sentinel v2.0 — Offline AI Surveillance Command Center

<div align="center">

🛡️ **Semantic Sentinel**  
*Offline AI-powered surveillance and semantic alert system*

*Designed for high-altitude border patrols, caves, remote terrain, and disaster zones*

</div>

---

## Overview

Semantic Sentinel is a locally-runnable AI surveillance prototype that replaces
continuous video streaming with **compact structured text alerts**.  
This dramatically reduces the bandwidth required to communicate security events
over satellite links, radios, or other constrained channels.

> ⚠️ **Simulation-first design.** This is a software prototype. It does not require
> physical cameras, radio hardware, or cloud APIs.

---

## Architecture

```
Semantic-Sentinel/
│
├── app.py                     ← Streamlit command-center entry point
├── requirements.txt
├── README.md
├── config.yaml                ← Detection + rule thresholds (editable)
│
├── config/
│   └── settings.py            ← Central constants and defaults
│
├── core/
│   ├── detector.py            ← YOLOv8n wrapper (lazy-loading)
│   ├── event_engine.py        ← Zone entry, loitering, abandoned object
│   ├── contextual_verifier.py ← Explainable severity + verification state
│   └── semantic_alerts.py     ← Compact text alert generator + DB writer
│
├── modules/
│   ├── camera_manager.py      ← Multi-camera registration (DB-backed)
│   ├── virtual_fence.py       ← Polygon zone drawing + validation
│   └── bandwidth_simulator.py ← Transparent bandwidth simulation
│
├── database/
│   └── database.py            ← Extended SQLite wrapper (cameras, zones, BW log)
│
├── pages/
│   ├── overview.py            ← Overview dashboard
│   ├── live_surveillance.py   ← Real-time detection with zone overlay
│   ├── camera_network.py      ← Add / remove simulated cameras
│   ├── alert_center.py        ← Filtered alert feed with explanations + export
│   ├── event_history.py       ← Full audit trail
│   ├── bandwidth_analytics.py ← BW comparison + disconnected queue sim
│   ├── system_diagnostics.py  ← Health checks + performance metrics
│   └── settings_page.py       ← Threshold editor, zone editor, demo generator
│
├── tests/
│   └── test_sentinel_full.py  ← 30+ tests across all modules
│
├── data/                      ← SQLite database (auto-created)
├── clips/                     ← Place .mp4 / .avi video files here
├── models/                    ← (Optional) alternative model weights
└── yolov8n.pt                 ← YOLOv8n model weights (required)
```

---

## Full Workflow

```
Select Simulated Camera  →  Load Video  →  YOLOv8 Detection  →  ByteTrack
     ↓
Virtual Fence / Zone Rules  →  Contextual Verification  →  Semantic Alert
     ↓
SQLite Storage  →  Bandwidth Simulation  →  Monitoring Dashboard
```

---

## Installation

### Prerequisites

- Python 3.10+ (3.11 recommended)
- `yolov8n.pt` model file in the project root (included or auto-downloaded by ultralytics)

### Steps

```powershell
# 1. Clone / navigate to the project folder
cd "C:\Users\lenovo\OneDrive\Desktop\Hackathon"

# 2. (Optional) create a virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the dashboard
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## Quick Start (Demo)

1. Open the app and navigate to **⚙️ Settings → Demo Simulator**
2. Click **"Run Demo Simulation"** to generate synthetic events
3. Navigate to **🚨 Alert Center** to view alerts with explanations
4. Navigate to **📡 Bandwidth Analytics** to compare payload sizes
5. Navigate to **🌐 Camera Network**, add a video file, then try **📹 Live Surveillance**

---

## Running Tests

```powershell
python -m pytest tests/test_sentinel_full.py -v
```

---

## Implemented Features

| Feature | Status |
|---|---|
| YOLOv8n object detection | ✅ Implemented |
| ByteTrack object tracking | ✅ Via ultralytics .track() |
| Multi-camera simulation (video files) | ✅ Implemented |
| Virtual fence / restricted zones (polygon) | ✅ Implemented |
| Zone entry detection | ✅ Implemented |
| Loitering detection | ✅ Implemented |
| Abandoned object detection | ✅ Implemented |
| Event deduplication (cooldown) | ✅ Implemented |
| Explainable contextual verification | ✅ Implemented |
| Severity scoring (Low/Medium/High/Critical) | ✅ Implemented |
| Verification states | ✅ Implemented |
| Semantic alert generation | ✅ Implemented |
| SQLite persistence | ✅ Implemented |
| Alert Center with filters | ✅ Implemented |
| CSV / JSON export | ✅ Implemented |
| Bandwidth simulation (multiple presets) | ✅ Implemented |
| Disconnected queue + reconnect delivery | ✅ Implemented |
| Overview dashboard | ✅ Implemented |
| System diagnostics | ✅ Implemented |
| Settings / threshold editor | ✅ Implemented |
| Zone editor (manual polygon) | ✅ Implemented |
| Demo data generator | ✅ Implemented |
| 30+ unit tests | ✅ Implemented |

---

## Simulated (Not Real)

| Claimed | Reality |
|---|---|
| Multi-camera real-time feeds | Video files played back sequentially |
| Satellite / radio comms | Calculated transmission time estimates only |
| Military-grade accuracy | YOLOv8n is a general-purpose detector |
| Facial recognition | Not implemented and not claimed |
| Real-world field deployment | Software prototype only |

---

## Known Limitations

- Live Surveillance runs one camera at a time in Streamlit (single-thread)
- YOLOv8n is a nano model — accuracy depends on video quality
- Zone drawing is manual (text input of polygon coordinates)
- No audio or motion sensor integration

---

## Hackathon Demo Sequence

1. **Settings → Demo Simulator** — Generate 20 synthetic events
2. **Overview** — Show the dashboard populated with real data
3. **Alert Center** — Walk through a Critical loitering alert explanation
4. **Bandwidth Analytics** — Show semantic vs. video payload comparison (set to 1 kbps)
5. **Bandwidth Analytics → Disconnected Mode** — Queue 5 alerts, reconnect, drain
6. **Camera Network** — Add a sample video file
7. **Live Surveillance** — Start detection, show zone overlay and live alerts
8. **System Diagnostics** — Show health checks and performance metrics
