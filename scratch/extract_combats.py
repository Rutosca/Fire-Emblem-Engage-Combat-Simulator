# pyrefly: ignore [missing-import]
import cv2
import numpy as np
import os

video_path = r"C:\Users\rutos\.gemini\antigravity-ide\brain\88639c71-0383-45db-b6a5-6a3e84bea8aa\scratch\cap7_video.mp4"
out_dir = r"C:\Users\rutos\.gemini\antigravity-ide\brain\88639c71-0383-45db-b6a5-6a3e84bea8aa\scratch\combats"
os.makedirs(out_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 28.19
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"Scanning {total_frames} frames at {fps:.2f} FPS...")

step = int(fps * 0.5)  # Check every 0.5s (~14 frames)
frame_idx = 0

events = []
current_event = []

def is_combat_forecast(frame):
    if frame is None or frame.shape[0] < 600 or frame.shape[1] < 1200:
        return False
    # Left banner: y 410-440, x 50-200
    lb = frame[410:440, 50:200].mean(axis=(0,1)) # B, G, R
    # Right banner: y 410-440, x 1080-1230
    rb = frame[410:440, 1080:1230].mean(axis=(0,1))
    
    # Case 1: Player initiates (Left Blue > Red + 40, Right Red > Blue + 40)
    is_player = (lb[0] > lb[2] + 40) and (rb[2] > rb[0] + 40)
    # Case 2: Enemy initiates (Left Red > Blue + 40, Right Blue > Red + 40)
    is_enemy = (lb[2] > lb[0] + 40) and (rb[0] > rb[2] + 40)
    
    # Check center table exists (dark gradient around 570:640, 600:680)
    center = frame[570:640, 600:680].mean(axis=(0,1))
    is_center_dark = (center[0] < 120 and center[1] < 110 and center[2] < 100)
    
    return (is_player or is_enemy) and is_center_dark

saved_count = 0
last_save_sec = -999

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    if frame_idx % step == 0:
        sec = frame_idx / fps
        if is_combat_forecast(frame):
            # Only record if separated by at least 3 seconds from previous combat
            if sec - last_save_sec > 3.0:
                m, s = divmod(int(sec), 60)
                saved_count += 1
                filename = f"combat_{saved_count:02d}_{m:02d}m{s:02d}s.jpg"
                filepath = os.path.join(out_dir, filename)
                cv2.imwrite(filepath, frame)
                last_save_sec = sec
                print(f"[{m:02d}:{s:02d}] Found combat forecast -> {filename}")
                
    frame_idx += 1

cap.release()
print(f"Finished! Extracted {saved_count} unique combat forecast screens to {out_dir}")
