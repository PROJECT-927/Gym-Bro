import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading
import queue
import logging
import sys

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Text-to-Speech (engine runs in background thread)
engine = pyttsx3.init()
tts_queue = queue.Queue()

def _tts_worker(q, engine):
    while True:
        text = q.get()
        if text is None:
            break
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            logging.exception('TTS failed')

threading.Thread(target=_tts_worker, args=(tts_queue, engine), daemon=True).start()

def calculate_angle(a, b, c):
    a = np.array(a); b = np.array(b); c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv.VideoCapture(0)
if not cap.isOpened():
    logging.error('Camera not available. Check camera connection and permissions.')
    sys.exit(1)

# State
stage = None
counter = 0

# Debounce counters
down_frames = 0
up_frames = 0
MIN_CONSECUTIVE = 3

# Visibility threshold
VIS_THRESHOLD = 0.5

# TTS cooldown to avoid spam (seconds)
last_spoken = 0
TTS_COOLDOWN = 1.0

logging.info('Starting Push-up Counter')

try:
    while True:
        success, img = cap.read()
        if not success:
            logging.warning('Failed to read from camera frame')
            break

        img = cv.flip(img, 1)
        imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        results = pose.process(imgRGB)

        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Decide dominant side by shoulder visibility
                left_sh = landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value]
                right_sh = landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value]
                use_left = left_sh.visibility >= right_sh.visibility

                if use_left:
                    idxs = {
                        'shoulder': mpPose.PoseLandmark.LEFT_SHOULDER.value,
                        'elbow': mpPose.PoseLandmark.LEFT_ELBOW.value,
                        'wrist': mpPose.PoseLandmark.LEFT_WRIST.value,
                        'hip': mpPose.PoseLandmark.LEFT_HIP.value,
                        'ankle': mpPose.PoseLandmark.LEFT_ANKLE.value,
                    }
                else:
                    idxs = {
                        'shoulder': mpPose.PoseLandmark.RIGHT_SHOULDER.value,
                        'elbow': mpPose.PoseLandmark.RIGHT_ELBOW.value,
                        'wrist': mpPose.PoseLandmark.RIGHT_WRIST.value,
                        'hip': mpPose.PoseLandmark.RIGHT_HIP.value,
                        'ankle': mpPose.PoseLandmark.RIGHT_ANKLE.value,
                    }

                # check visibility for key landmarks
                vis_ok = True
                coords = {}
                for name, idx in idxs.items():
                    lm = landmarks[idx]
                    if lm.visibility < VIS_THRESHOLD:
                        vis_ok = False
                        break
                    coords[name] = [lm.x, lm.y]

                if not vis_ok:
                    # skip unreliable frame
                    down_frames = up_frames = 0
                else:
                    shoulder = coords['shoulder']
                    elbow = coords['elbow']
                    wrist = coords['wrist']
                    hip = coords['hip']
                    ankle = coords['ankle']

                    elbow_angle = calculate_angle(shoulder, elbow, wrist)
                    body_angle = calculate_angle(shoulder, hip, ankle)

                    # Debounce logic
                    if elbow_angle < 90:
                        down_frames += 1
                        up_frames = 0
                    elif elbow_angle > 160:
                        up_frames += 1
                        down_frames = 0
                    else:
                        down_frames = max(0, down_frames - 1)
                        up_frames = max(0, up_frames - 1)

                    # state transitions
                    now = time.time()
                    if down_frames >= MIN_CONSECUTIVE and stage != 'down':
                        stage = 'down'
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put('Down')
                            last_spoken = now

                    if up_frames >= MIN_CONSECUTIVE and stage == 'down':
                        stage = 'up'
                        counter += 1
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put(f'Good rep {counter}')
                            last_spoken = now

                    # Form feedback (don't override rep announcement)
                    if body_angle < 150 and (now - last_spoken > TTS_COOLDOWN):
                        tts_queue.put('Keep your body straight')
                        last_spoken = now

                # Draw UI
                h, w, _ = img.shape
                cv.rectangle(img, (10,10), (380,130), (0,0,0), cv.FILLED)
                cv.putText(img, 'PUSH-UP COUNTER', (20,45), cv.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
                cv.putText(img, f'REPS: {counter}', (20,95), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)
                cv.putText(img, f'STAGE: {stage or "-"}', (230,95), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

                mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)

        except Exception as e:
            logging.exception('Processing frame failed: %s', e)

        cv.imshow('Push-up Counter', img)
        if cv.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    # Clean up
    try:
        tts_queue.put(None)
    except Exception:
        pass
    cap.release()
    cv.destroyAllWindows()

