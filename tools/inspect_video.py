import cv2
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Inspect Video")
    parser.add_argument('--video', type=str, required=True, help='Path to video')
    args = parser.parse_args()
    
    if not os.path.exists(args.video):
        print(f"File not found: {args.video}")
        return
        
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Failed to open video: {args.video}")
        return
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    duration = frame_count / fps if fps > 0 else 0
    
    print(f"Video: {args.video}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps:.2f}")
    print(f"Frame Count: {frame_count}")
    print(f"Duration: {duration:.2f} seconds")
    
    cap.release()

if __name__ == '__main__':
    main()
