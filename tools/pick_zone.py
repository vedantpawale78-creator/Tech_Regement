import cv2
import argparse
import yaml
import os

points = []

def mouse_callback(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print(f"Added point: ({x}, {y})")

def main():
    parser = argparse.ArgumentParser(description="Pick Zone Tool")
    parser.add_argument('--video', type=str, required=True, help='Path to video')
    args = parser.parse_args()
    
    cap = cv2.VideoCapture(args.video)
    ret, frame = cap.read()
    if not ret:
        print("Failed to read video")
        return
        
    cv2.namedWindow('Pick Zone')
    cv2.setMouseCallback('Pick Zone', mouse_callback)
    
    print("Click on the image to select points.")
    print("Press 'f' to save the first two points as a fence.")
    print("Press 'p' to save all points as a polygon.")
    print("Press 'q' to quit.")
    
    while True:
        display = frame.copy()
        for i, p in enumerate(points):
            cv2.circle(display, p, 5, (0, 0, 255), -1)
            if i > 0:
                cv2.line(display, points[i-1], p, (0, 255, 0), 2)
                
        cv2.imshow('Pick Zone', display)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('f'):
            if len(points) >= 2:
                print(f"Fence: p1={points[0]}, p2={points[1]}")
            else:
                print("Need at least 2 points for a fence")
        elif key == ord('p'):
            if len(points) >= 3:
                print(f"Polygon: {points}")
            else:
                print("Need at least 3 points for a polygon")
                
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
