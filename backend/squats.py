import cv2
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading
import queue
import random

# ---------------------- Text-to-Speech ----------------------
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
            # Create a new engine instance for every message → prevents blocking
            temp_engine = pyttsx3.init()
            temp_engine.setProperty('rate', 175)
            temp_engine.say(text)
            temp_engine.runAndWait()
            temp_engine.stop()
        except Exception as e:
            print("TTS Error:", e)

threading.Thread(target=tts_worker, args=(tts_queue, engine), daemon=True).start()

def speak(msg):
    """Always speak immediately (non-blocking)"""
    tts_queue.put(msg)

# ---------------------- Helper Functions ----------------------
def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle

# ---------------------- Mediapipe Setup ----------------------
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)

cap = cv2.VideoCapture(0)

# ---------------------- State Variables ----------------------
counter = 0
stage = "not ready"
feedback = ""
color = (255, 255, 255)
ready = False
aligned = False
last_warning = 0
COOLDOWN = 2.0

motivational_lines = [
    "More more! Keep going!",
    "You're crushing it!",
    "Push yourself!",
    "Amazing form, keep it up!",
    "Nice one! Don’t stop!",
    "Perfect squat! Let's go again!"
]

# ---------------------- Main Loop ----------------------
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

            # Key front-facing points
            left_shoulder = [lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            right_shoulder = [lm[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
            left_hip = [lm[mp_pose.PoseLandmark.LEFT_HIP.value].x, lm[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            right_hip = [lm[mp_pose.PoseLandmark.RIGHT_HIP.value].x, lm[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
            left_knee = [lm[mp_pose.PoseLandmark.LEFT_KNEE.value].x, lm[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            left_ankle = [lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]

            # Alignment detection (front view)
            shoulder_diff = abs(left_shoulder[0] - right_shoulder[0])
            hip_diff = abs(left_hip[0] - right_hip[0])

            now = time.time()
            if shoulder_diff > 0.25 or hip_diff > 0.25:
                aligned = False
                feedback = "⚠ Face front and align straight!"
                color = (0, 0, 255)
                if now - last_warning > COOLDOWN:
                    speak("Go back and align straight")
                    last_warning = now
                ready = False
            else:
                aligned = True

            if aligned:
                # Angle calculation
                knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
                hip_angle = calculate_angle(left_shoulder, left_hip, left_knee)

                feedback = ""
                color = (255, 255, 255)

                # Ready position
                if knee_angle > 150:
                    feedback = "🏋 Ready position — Start squats"
                    color = (200, 200, 200)
                    if not ready:
                        ready = True
                        stage = "up"
                        speak("Ready position detected. Start squats!")

                # Go deeper
                elif ready and knee_angle > 120:
                    feedback = "⬇ Go deeper!"
                    color = (0, 255, 255)
                    speak("Go deeper")

                # Perfect squat
                elif ready and 80 < knee_angle <= 110 and hip_angle < 100:
                    feedback = "✅ Perfect squat!"
                    color = (0, 255, 0)
                    speak("Perfect squat")
                    speak(random.choice(motivational_lines))

                # Bottom position
                elif ready and knee_angle < 90:
                    stage = "down"

                # Rep counting logic
                if ready and stage == "down" and knee_angle > 150:
                    stage = "up"
                    counter += 1
                    feedback = f"Good rep {counter} ✅"
                    color = (0, 255, 0)
                    speak(f"Good rep {counter}")
                    speak(random.choice(motivational_lines))

            # Draw pose
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=3),
                mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2),
            )

            # ---------------------- UI ----------------------
            cv2.rectangle(frame, (20, 20), (320, 130), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, "REPS", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(frame, str(counter), (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255,255,255), 3)
            cv2.putText(frame, "STAGE", (160, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(frame, stage.upper(), (160, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)

            cv2.rectangle(frame, (20, h-60), (720, h-20), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, f"FEEDBACK: {feedback}", (40, h-30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

            cv2.putText(frame, f"Knee: {int(knee_angle)}°", (w-200, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
            cv2.putText(frame, f"Hip: {int(hip_angle)}°", (w-200, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)

    except Exception as e:
        pass

    cv2.imshow("Squat Tracker - Front View (Gym Posture AI)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()