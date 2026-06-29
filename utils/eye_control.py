import sys
import time
import cv2
import pyautogui

pyautogui.FAILSAFE = False
print("[Eye] Opening camera...", flush=True)

# Try camera 1 first (usually external camera or secondary index on Mac), fallback to 0
cam = cv2.VideoCapture(1)
if not cam or not cam.isOpened():
    print("[Eye] Camera 1 failed, trying 0...", flush=True)
    cam = cv2.VideoCapture(0)

if not cam or not cam.isOpened():
    print("[Eye] ERROR: Cannot open any camera.", flush=True)
    sys.exit(1)

print("[Eye] Camera opened. Loading mediapipe (may take a moment)...", flush=True)
import mediapipe as mp

face_mesh = mp.solutions.face_mesh.FaceMesh(refine_landmarks=True)
screen_w, screen_h = pyautogui.size()
last_click_time = 0

print("[Eye] Started. Press ESC to stop.", flush=True)

while True:
    _, frame = cam.read()
    if frame is None:
        continue
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    output = face_mesh.process(rgb_frame)
    landmark_points = output.multi_face_landmarks
    frame_h, frame_w, _ = frame.shape
    if landmark_points:
        landmarks = landmark_points[0].landmark
        for id, landmark in enumerate(landmarks[474:478]):
            x = int(landmark.x * frame_w)
            y = int(landmark.y * frame_h)
            cv2.circle(frame, (x, y), 3, (0, 255, 0))
            if id == 1:
                screen_x = screen_w * landmark.x
                screen_y = screen_h * landmark.y
                pyautogui.moveTo(screen_x, screen_y)
        left = [landmarks[145], landmarks[159]]
        for landmark in left:
            x = int(landmark.x * frame_w)
            y = int(landmark.y * frame_h)
            cv2.circle(frame, (x, y), 3, (0, 255, 255))
        if (left[0].y - left[1].y) < 0.004:
            current_time = time.time()
            if current_time - last_click_time > 1.0:
                pyautogui.click()
                last_click_time = current_time
    cv2.imshow('Eye Controlled Mouse', frame)
    key = cv2.waitKey(1)
    if key == 27:
        break

cam.release()
cv2.destroyAllWindows()
print("[Eye] Stopped.", flush=True)
