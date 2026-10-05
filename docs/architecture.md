# Architecture

The system follows a linear pipeline architecture optimized for edge processing.

1. **Frame Capture**: Reads frames from webcam or video file using OpenCV.
2. **Detection & Tracking**: Uses YOLOv8n to detect objects and ByteTrack to assign consistent IDs across frames.
3. **Rules Engine**: 
   - Uses geometric algorithms (ray casting, line intersection) to evaluate object paths against configured zones.
4. **Alert Verification**: Filters out false positives based on track age, confidence thresholds, and cooldown timers.
5. **Storage Layer**: Persists verified alerts and system metrics to a local SQLite database.
6. **Presentation Layer**: A Streamlit dashboard reads from the SQLite database to display alerts, metrics, and bandwidth analysis.
