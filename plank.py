import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import pyttsx3

# --- Text-to-Speech Engine Initialization ---
engine = pyttsx3.init()

# Function to calculate angle
def calculate_angle(a, b, c):
    a = np.array(a); b = np.array(b); c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360-angle
    return angle

# --- MediaPipe Initialization ---
mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv.VideoCapture(0)

# --- Plank Timer and State Variables ---
stage = "resting"
start_time = 0
pause_start_time = 0
total_paused_time = 0
feedback = "Get into plank position"
last_feedback = None # Variable to track the last spoken message

# --- Main Loop ---
while True:
    success, img = cap.read()
    if not success: break
    
    img = cv.flip(img, 1)
    imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    results = pose.process(imgRGB)
    
    elapsed_time = 0
    if start_time > 0:
        current_paused_time = time.time() - pause_start_time if stage == "resting" and pause_start_time > 0 else 0
        elapsed_time = time.time() - start_time - total_paused_time - current_paused_time

    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Automatic Side Detection
            left_hip_visibility = landmarks[mpPose.PoseLandmark.LEFT_HIP.value].visibility
            right_hip_visibility = landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].visibility
            
            if left_hip_visibility > right_hip_visibility:
                # Get LEFT side landmarks
                shoulder, elbow, wrist, hip, ankle = (
                    [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].y]
                )
            else:
                # Get RIGHT side landmarks
                shoulder, elbow, wrist, hip, ankle = (
                    [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].y]
                )

            # --- Angle Calculations for Form Analysis ---
            body_angle = calculate_angle(shoulder, hip, ankle)
            arm_pit_angle = calculate_angle(hip, shoulder, elbow) # Measures if elbows are under shoulders
            elbow_angle = calculate_angle(shoulder, elbow, wrist) # Measures forearm angle

            # --- State Machine for Form and Timer ---
            if body_angle > 160: # Body is straight enough to be considered a plank
                if stage == "resting":
                    # Transitioning from resting to planking
                    if start_time == 0: start_time = time.time()
                    else: total_paused_time += time.time() - pause_start_time
                
                stage = "planking"
                # --- Detailed Form Feedback ---
                if arm_pit_angle < 75 or arm_pit_angle > 105:
                    feedback = "Align shoulders over elbows"
                elif elbow_angle < 75 or elbow_angle > 105:
                    feedback = "Keep forearms flat"
                else:
                    feedback = "Good Form!"
            
            elif 140 < body_angle <= 160: # Hips are slightly sagging
                stage = "warning"
                feedback = "Warning: Hips are sagging"
            
            else: # body_angle <= 140, COMPLETE STOP
                if stage != "resting": pause_start_time = time.time()
                stage = "resting"
                feedback = "Timer Paused - Get Back Up!"

            # --- VOICE FEEDBACK LOGIC ---
            if feedback != last_feedback:
                engine.say(feedback)
                engine.runAndWait()
                last_feedback = feedback

            # --- Drawing and UI ---
            h, w, _ = img.shape
            feedback_color = (0, 255, 0) if feedback == "Good Form!" else ((0, 165, 255) if stage == "warning" else (0, 0, 255))
            
            cv.rectangle(img, (20, 20), (620, 130), (0, 0, 0), cv.FILLED)
            cv.putText(img, "FOREARM PLANK TIMER", (40, 60), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, f"{int(elapsed_time)} S", (400, 100), cv.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3, cv.LINE_AA)
            cv.putText(img, f"STAGE: {stage.upper()}", (40, 100), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            
            cv.rectangle(img, (20, h - 80), (620, h - 20), (0, 0, 0), cv.FILLED)
            cv.putText(img, f"FEEDBACK: {feedback}", (40, h - 45), cv.FONT_HERSHEY_SIMPLEX, 1, feedback_color, 2, cv.LINE_AA)
            mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)

    except Exception as e:
        pass

    cv.imshow("Forearm Plank Corrector", img)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()