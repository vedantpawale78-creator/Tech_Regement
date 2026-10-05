import cv2
import numpy as np
import os

def generate_video(filename, text, color, frames=90):
    os.makedirs('clips', exist_ok=True)
    path = os.path.join('clips', filename)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, 30.0, (640, 480))
    
    for i in range(frames):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw moving object
        x = 100 + int(i * (400/frames))
        y = 200
        cv2.circle(frame, (x, y), 20, color, -1)
        cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)
        
    out.release()
    print(f"Generated {path}")

if __name__ == '__main__':
    generate_video('cross.mp4', 'Simulated Crossing', (0, 0, 255))
    generate_video('loiter.mp4', 'Simulated Loitering', (0, 255, 255))
    generate_video('bag.mp4', 'Simulated Abandoned Bag', (255, 0, 0))
    print("Note: These synthetic clips validate the video pipeline.")
    print("Real YOLO detection requires actual human/object footage.")
