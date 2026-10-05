import cv2
import numpy as np

def draw_zones(frame, config):
    # Draw Fence
    fence = config.get('zones', {}).get('fence', {})
    if fence:
        p1 = tuple(fence['p1'])
        p2 = tuple(fence['p2'])
        cv2.line(frame, p1, p2, (0, 0, 255), 2)
        cv2.putText(frame, "Fence", (p1[0], p1[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
        
    # Draw Polygon
    poly = config.get('zones', {}).get('restricted_polygon', [])
    if poly:
        pts = np.array(poly, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, (0, 255, 255), 2)
        cv2.putText(frame, "Restricted Zone", (poly[0][0], poly[0][1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 2)

def draw_tracks(frame, tracks):
    for trk in tracks:
        bbox = trk['bbox'] # [x1, y1, x2, y2]
        x1, y1, x2, y2 = map(int, bbox)
        track_id = trk['track_id']
        cls_name = trk['class_name']
        conf = trk['conf']
        
        color = (0, 255, 0)
        if cls_name in ['backpack', 'handbag', 'suitcase']:
            color = (255, 0, 0)
            
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{track_id} {cls_name} {conf:.2f}"
        cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

def draw_alerts(frame, active_alerts):
    y_offset = 30
    for alert in active_alerts:
        text = f"ALERT: {alert['event_type']} (ID: {alert['track_id']})"
        cv2.putText(frame, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        y_offset += 30
