import sys
import time
import cv2
import pyautogui

pyautogui.FAILSAFE = False
print("[Hand] Opening camera...", flush=True)

# Try camera 1 first (usually external camera or secondary index on Mac), fallback to 0
cap = cv2.VideoCapture(1)
if not cap or not cap.isOpened():
    print("[Hand] Camera 1 failed, trying 0...", flush=True)
    cap = cv2.VideoCapture(0)
    
if not cap or not cap.isOpened():
    print("[Hand] ERROR: Cannot open any camera.", flush=True)
    sys.exit(1)

print("[Hand] Camera opened. Loading mediapipe (may take a moment)...", flush=True)
import mediapipe as mp

hand_detector = mp.solutions.hands.Hands()
drawing_utils = mp.solutions.drawing_utils
screen_width, screen_height = pyautogui.size()
index_y = 0
index_x = 0
last_click_time = 0

print("[Hand] Started. Press ESC to stop.", flush=True)

while True:
    _, frame = cap.read()
    if frame is None:
        continue
    frame = cv2.flip(frame, 1)
    frame_height, frame_width, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    output = hand_detector.process(rgb_frame)
    hands = output.multi_hand_landmarks
    if hands:
        for hand in hands:
            drawing_utils.draw_landmarks(frame, hand)
            landmarks = hand.landmark
            
            # Extract thumb tip (id 4) and index tip (id 8)
            thumb = landmarks[4]
            index = landmarks[8]
            
            # Scale index tip to screen coordinates
            index_x = int(screen_width * index.x)
            index_y = int(screen_height * index.y)
            
            # Draw visual feedback circles on the frame
            thumb_pixel_x = int(thumb.x * frame_width)
            thumb_pixel_y = int(thumb.y * frame_height)
            index_pixel_x = int(index.x * frame_width)
            index_pixel_y = int(index.y * frame_height)
            
            cv2.circle(img=frame, center=(thumb_pixel_x, thumb_pixel_y), radius=10, color=(0, 255, 255))
            cv2.circle(img=frame, center=(index_pixel_x, index_pixel_y), radius=10, color=(0, 255, 255))
            
            # Move mouse cursor continuously based on index finger position
            pyautogui.moveTo(index_x, index_y)
            
            # Calculate Euclidean distance between thumb and index in normalized coordinates
            dist = ((index.x - thumb.x)**2 + (index.y - thumb.y)**2)**0.5
            
            # Pinch detection (click when tips are extremely close)
            if dist < 0.04:
                current_time = time.time()
                if current_time - last_click_time > 1.0:
                    pyautogui.click()
                    last_click_time = current_time
    cv2.imshow('Virtual Mouse', frame)
    key = cv2.waitKey(1)
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()
print("[Hand] Stopped.", flush=True)
