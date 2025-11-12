import cv2
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading
import queue
import random

# ==================== Text-to-Speech Setup ====================
engine = pyttsx3.init()
engine.setProperty('rate', 170)
engine.setProperty('volume', 1.0)
tts_queue = queue.Queue()

def tts_worker(q, engine):
    while True:
        text = q.get()
        if text is None:
            break
        try:
            temp_engine = pyttsx3.init()
            temp_engine.setProperty('rate', 175)
            temp_engine.say(text)
            temp_engine.runAndWait()
            temp_engine.stop()
        except Exception as e:
            print("TTS Error:", e)

threading.Thread(target=tts_worker, args=(tts_queue, engine), daemon=True).start()

def speak(msg):
    """Non-blocking TTS"""
    tts_queue.put(msg)

# ==================== Helper Functions ====================
def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle

# ==================== Mediapipe Setup ====================
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)

cap = cv2.VideoCapture(0)

# ==================== State Variables ====================
counter = 0
stage = "not ready"
feedback = ""
color = (255, 255, 255)
ready = False
last_spoken = 0
TTS_COOLDOWN = 1.5

# Debounce counters - REDUCED for faster response
down_frames = 0
up_frames = 0
ready_frames = 0
MIN_CONSECUTIVE = 2  # Reduced for faster transitions

# Visibility threshold
VIS_THRESHOLD = 0.6

# Form thresholds (degrees) - ADJUSTED
KNEE_DOWN_THRESHOLD = 110    # Must go below this to be "down"
KNEE_UP_THRESHOLD = 150      # Must go above this to be "up" (increased!)
KNEE_DEEP_MAX = 70           # Deep squat
KNEE_PARALLEL_MIN = 70       # Parallel squat range
KNEE_PARALLEL_MAX = 100

# Smoothing
SMOOTHING_ALPHA = 0.6
smoothed_coords = {}

motivational_lines = [
    "Keep it up!",
    "You're crushing it!",
    "Amazing form!",
    "Perfect! One more!",
    "Nice work! Keep going!",
    "Excellent squat!"
]

print("Starting Squat Counter - Side View")
print("Position yourself in SIDE VIEW (not front facing)")
print("Press 'Q' to quit")

# ==================== Main Loop ====================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(img_rgb)
    h, w, _ = frame.shape

    try:
        if results.pose_landmarks:
            lm = results.pose_landmarks.landmark

            # Determine dominant side (better visibility)
            left_sh = lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            right_sh = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            use_left = left_sh.visibility >= right_sh.visibility

            # Select landmarks based on dominant side
            if use_left:
                shoulder_idx = mp_pose.PoseLandmark.LEFT_SHOULDER.value
                hip_idx = mp_pose.PoseLandmark.LEFT_HIP.value
                knee_idx = mp_pose.PoseLandmark.LEFT_KNEE.value
                ankle_idx = mp_pose.PoseLandmark.LEFT_ANKLE.value
            else:
                shoulder_idx = mp_pose.PoseLandmark.RIGHT_SHOULDER.value
                hip_idx = mp_pose.PoseLandmark.RIGHT_HIP.value
                knee_idx = mp_pose.PoseLandmark.RIGHT_KNEE.value
                ankle_idx = mp_pose.PoseLandmark.RIGHT_ANKLE.value

            # Extract coordinates
            shoulder = [lm[shoulder_idx].x, lm[shoulder_idx].y]
            hip = [lm[hip_idx].x, lm[hip_idx].y]
            knee = [lm[knee_idx].x, lm[knee_idx].y]
            ankle = [lm[ankle_idx].x, lm[ankle_idx].y]

            # Check visibility
            vis_ok = (lm[shoulder_idx].visibility >= VIS_THRESHOLD and
                     lm[hip_idx].visibility >= VIS_THRESHOLD and
                     lm[knee_idx].visibility >= VIS_THRESHOLD and
                     lm[ankle_idx].visibility >= VIS_THRESHOLD)

            if not vis_ok:
                feedback = "⚠ Come closer - full body in frame"
                color = (0, 0, 255)
                down_frames = up_frames = ready_frames = 0
                ready = False
            else:
                # Apply smoothing
                coords = {'shoulder': shoulder, 'hip': hip, 'knee': knee, 'ankle': ankle}
                for k, v in coords.items():
                    if k not in smoothed_coords:
                        smoothed_coords[k] = v.copy()
                    else:
                        smoothed_coords[k][0] = SMOOTHING_ALPHA * v[0] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][0]
                        smoothed_coords[k][1] = SMOOTHING_ALPHA * v[1] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][1]

                # Use smoothed coordinates
                shoulder = smoothed_coords['shoulder']
                hip = smoothed_coords['hip']
                knee = smoothed_coords['knee']
                ankle = smoothed_coords['ankle']

                # Calculate angles
                knee_angle = calculate_angle(hip, knee, ankle)
                hip_angle = calculate_angle(shoulder, hip, knee)
                back_angle = calculate_angle(shoulder, hip, ankle)

                now = time.time()

                # ==================== Ready Position Detection ====================
                if knee_angle > 140 and hip_angle > 130:
                    ready_frames += 1
                    
                    if ready_frames >= MIN_CONSECUTIVE and not ready:
                        ready = True
                        stage = "up"
                        feedback = "🏋 Ready position — Start squats"
                        color = (0, 255, 200)
                        down_frames = up_frames = 0  # Reset counters
                        if now - last_spoken > TTS_COOLDOWN:
                            speak("Ready position detected. Start squatting!")
                            last_spoken = now
                else:
                    ready_frames = 0
                
                # Auto-ready if user is already squatting
                if not ready and knee_angle < 120:
                    ready = True
                    stage = "down"
                    feedback = "🏋 Continuing from squat position"
                    color = (0, 255, 200)

                # ==================== Squat Detection (FIXED LOGIC) ====================
                if ready:
                    # CLEAR STATE MACHINE: Down if below threshold, Up if above threshold
                    
                    # Going DOWN: knee angle goes below threshold
                    if knee_angle < KNEE_DOWN_THRESHOLD:
                        if stage == "up":  # Transition from up to down
                            stage = "down"
                            down_frames = MIN_CONSECUTIVE  # Immediately set to min
                            up_frames = 0
                            
                            # Check depth and give feedback
                            if knee_angle <= KNEE_DEEP_MAX:
                                feedback = "💪 Deep squat — Excellent!"
                                color = (0, 255, 0)
                            elif KNEE_PARALLEL_MIN <= knee_angle <= KNEE_PARALLEL_MAX:
                                feedback = "✅ Good depth — Parallel"
                                color = (0, 200, 100)
                            else:
                                feedback = "⬇ Going down..."
                                color = (0, 165, 255)
                        else:
                            # Already down, keep incrementing
                            down_frames += 1
                            up_frames = 0
                    
                    # Going UP: knee angle goes above threshold
                    elif knee_angle > KNEE_UP_THRESHOLD:
                        if stage == "down":  # Transition from down to up - COUNT REP!
                            stage = "up"
                            up_frames = MIN_CONSECUTIVE  # Immediately set to min
                            down_frames = 0
                            
                            # COUNT THE REP
                            counter += 1
                            feedback = f"✅ Rep {counter} complete!"
                            color = (0, 255, 0)
                            
                            if now - last_spoken > TTS_COOLDOWN:
                                speak(f"Rep {counter}")
                                speak(random.choice(motivational_lines))
                                last_spoken = now
                        else:
                            # Already up, keep incrementing
                            up_frames += 1
                            down_frames = 0
                    
                    # In between - maintain current state but show position
                    else:
                        if stage == "down":
                            feedback = f"⬇ In squat position ({int(knee_angle)}°)"
                            color = (255, 200, 0)
                        else:
                            feedback = f"⬆ Standing ({int(knee_angle)}°)"
                            color = (200, 255, 200)

                else:
                    feedback = "🏋 Stand straight to begin"
                    color = (200, 200, 200)

            # Draw pose landmarks
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=3),
                mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2),
            )

            # ==================== UI Drawing ====================
            # Header box
            cv2.rectangle(frame, (20, 20), (420, 130), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, "REPS", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(frame, str(counter), (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0,255,200), 3)
            cv2.putText(frame, "STAGE", (180, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(frame, stage.upper(), (180, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)

            # Feedback bar
            cv2.rectangle(frame, (20, h-60), (w-20, h-20), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, f"FEEDBACK: {feedback}", (40, h-30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

            # Debug angles (top right) - ADDED DEBUG INFO
            if vis_ok:
                cv2.putText(frame, f"Knee: {int(knee_angle)}°", (w-250, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                cv2.putText(frame, f"Hip: {int(hip_angle)}°", (w-250, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                cv2.putText(frame, f"Stage: {stage}", (w-250, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
                cv2.putText(frame, f"Down: {down_frames} Up: {up_frames}", (w-250, 130),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,0), 2)

    except Exception as e:
        print(f"Error: {e}")

    cv2.imshow("Squat Tracker - Side View (Gym Posture AI)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Cleanup
tts_queue.put(None)
cap.release()
cv2.destroyAllWindows()
print(f"Session complete. Total reps: {counter}")