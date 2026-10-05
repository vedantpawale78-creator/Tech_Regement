import argparse
import cv2
import time
import os
import logging
from ultralytics import YOLO
from config_loader import load_config
from database import Database
from rules import RulesEngine
from alerts import AlertManager
from visualization import draw_zones, draw_tracks, draw_alerts
from utils import get_current_timestamp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Semantic Sentinel Detector")
    parser.add_argument('--source', type=str, default='0', help='Video source (0 for webcam, or path to video)')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config file')
    parser.add_argument('--no-display', action='store_true', help='Disable video display')
    parser.add_argument('--save-output', action='store_true', help='Save output video')
    parser.add_argument('--loop', action='store_true', help='Loop video')
    parser.add_argument('--camera-id', type=str, default=None, help='Override camera ID')
    return parser.parse_args()

def main():
    args = parse_args()
    config = load_config(args.config)
    
    if args.camera_id:
        config['camera']['id'] = args.camera_id
        
    db = Database(config.get('database', {}).get('path', 'data/sentinel.db'))
    rules = RulesEngine(config)
    alert_mgr = AlertManager(config, db)
    
    model_path = config.get('model', {}).get('path', 'yolov8n.pt')
    conf_thresh = config.get('model', {}).get('confidence', 0.40)
    
    logger.info(f"Loading model {model_path}...")
    model = YOLO(model_path)
    
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error(f"Failed to open source: {source}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    out = None
    if args.save_output:
        os.makedirs('results', exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter('results/output.mp4', fourcc, fps_video, (frame_width, frame_height))
        
    track_history = {} # track_id -> age
    
    frame_count = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            if args.loop and isinstance(source, str):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            break
            
        frame_count += 1
        loop_start = time.time()
        
        # Inference & Tracking
        results = model.track(frame, persist=True, conf=conf_thresh, verbose=False)
        
        tracks = []
        people_centers = []
        
        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            clss = results[0].boxes.cls.cpu().tolist()
            confs = results[0].boxes.conf.cpu().tolist()
            
            for box, track_id, cls, conf in zip(boxes, track_ids, clss, confs):
                cls_name = model.names[int(cls)]
                center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                
                track_history[track_id] = track_history.get(track_id, 0) + 1
                
                if cls_name == 'person':
                    people_centers.append(center)
                    
                tracks.append({
                    'bbox': box,
                    'track_id': track_id,
                    'class_name': cls_name,
                    'conf': conf,
                    'center': center
                })

        active_alerts = []
        
        # Apply Rules
        for trk in tracks:
            track_id = trk['track_id']
            center = trk['center']
            cls_name = trk['class_name']
            
            # 1. Fence Crossing
            if cls_name == 'person':
                event = rules.check_fence_crossing(track_id, center)
                if event:
                    event['track_id'] = track_id
                    event['object_class'] = cls_name
                    alert = alert_mgr.verify_and_generate(event, track_history[track_id], trk['conf'])
                    if alert.get('verified'): active_alerts.append(alert)
                    
            # 2. Loitering
            if cls_name == 'person':
                event = rules.check_loitering(track_id, center)
                if event:
                    event['track_id'] = track_id
                    event['object_class'] = cls_name
                    alert = alert_mgr.verify_and_generate(event, track_history[track_id], trk['conf'])
                    if alert.get('verified'): active_alerts.append(alert)
                    
            # 3. Abandoned Object
            event = rules.check_abandoned(track_id, center, cls_name, people_centers)
            if event:
                event['track_id'] = track_id
                event['object_class'] = cls_name
                alert = alert_mgr.verify_and_generate(event, track_history[track_id], trk['conf'])
                if alert.get('verified'): active_alerts.append(alert)

        # Draw
        if not args.no_display or args.save_output:
            draw_zones(frame, config)
            draw_tracks(frame, tracks)
            draw_alerts(frame, active_alerts)
            
            if args.save_output:
                out.write(frame)
                
            if not args.no_display:
                cv2.imshow('Semantic Sentinel', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        # Metrics
        if frame_count % 30 == 0:
            elapsed = time.time() - loop_start
            fps = 1.0 / elapsed if elapsed > 0 else 0
            db.insert_metric({
                "timestamp": get_current_timestamp(),
                "fps": fps,
                "processing_latency_ms": elapsed * 1000,
                "frame_count": frame_count,
                "detected_objects": len(tracks),
                "alerts_count": len(active_alerts)
            })

    cap.release()
    if out:
        out.release()
    cv2.destroyAllWindows()
    logger.info("Detection finished.")

if __name__ == '__main__':
    main()
