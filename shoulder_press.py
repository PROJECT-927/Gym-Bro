import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading

# --- Function to handle speaking in a separate thread ---
def speak(engine, text):
    engine.say(text)
    engine.runAndWait()

# Function to calculate angle
def calculate_angle(a, b, c):
    a = np.array(a); b = np.array(b); c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360-angle
    return angle

# --- Initialize ONE engine instance for the whole application ---
tts_engine = pyttsx3.init()

mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv.VideoCapture(0)

# --- State Machine & Rep Counter Variables ---
rep_counter = 0
stage = 'DOWN'

# --- NEW Smart Feedback Variables ---
persistent_error = None
error_start_time = None
ERROR_DURATION_THRESHOLD = 2.0  # Hold an error for 2 seconds to trigger
VOICE_COOLDOWN = 5.0            # Wait 5 seconds between voice alerts
last_voice_alert_time = 0

# Setup for full screen
WINDOW_NAME = "Shoulder Press AI Coach"
cv.namedWindow(WINDOW_NAME, cv.WINDOW_NORMAL)
cv.setWindowProperty(WINDOW_NAME, cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

while True:
    success, img = cap.read()
    if not success: break
    
    img = cv.flip(img, 1)
    imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    results = pose.process(imgRGB)
    
    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Get coordinates
            rshoulder, relbow, rwrist, rhip = ([landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y], 
                                               [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y], 
                                               [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y], 
                                               [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y])
            lshoulder, lelbow, lwrist, lhip = ([landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y], 
                                               [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y], 
                                               [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y], 
                                               [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y])

            # Calculate angles
            r_elbow_angle = calculate_angle(rshoulder, relbow, rwrist)
            l_elbow_angle = calculate_angle(lshoulder, lelbow, lwrist)
            r_shoulder_angle = calculate_angle(rhip, rshoulder, relbow)
            l_shoulder_angle = calculate_angle(lhip, lshoulder, lelbow)
            shoulder_level_diff = abs(rshoulder[1] - lshoulder[1])

            # State Machine & Rep Counter Logic
            if r_elbow_angle > 160 and l_elbow_angle > 160 and stage == 'DOWN':
                rep_counter += 1
                stage = 'UP'
            elif r_elbow_angle < 90 and l_elbow_angle < 90:
                stage = 'DOWN'
            
            # --- Determine current error for both voice and visual ---
            current_error = None
            if shoulder_level_diff > 0.05:
                current_error = "Keep shoulders level"
            elif r_shoulder_angle < 70 or l_shoulder_angle < 70:
                current_error = "Bring your elbows up"
            elif (r_elbow_angle > 110 and r_shoulder_angle < 115) or \
                 (l_elbow_angle > 110 and l_shoulder_angle < 115):
                current_error = "Tuck your elbows in"
            elif r_elbow_angle < 50 or l_elbow_angle < 50:
                current_error = "Elbows too close to shoulders"

            # =====================================================================
            # --- NEW VOICE FEEDBACK LOGIC ---
            # =====================================================================
            if current_error:
                # If this is a new error, start its timer
                if current_error != persistent_error:
                    persistent_error = current_error
                    error_start_time = time.time()
                
                # Check if the error has been held long enough
                if time.time() - error_start_time >= ERROR_DURATION_THRESHOLD:
                    # Check if the global voice cooldown has passed
                    if time.time() - last_voice_alert_time >= VOICE_COOLDOWN:
                        thread = threading.Thread(target=speak, args=(tts_engine, persistent_error))
                        thread.start()
                        last_voice_alert_time = time.time() # Reset the global cooldown timer
            else:
                # If there's no error, reset the persistence tracker
                persistent_error = None
                error_start_time = None

            # --- Visual Feedback Logic (State-Dependent) ---
            visual_feedback = "Good Form"
            if stage == 'DOWN' and current_error:
                visual_feedback = current_error
            
            # --- Drawing and UI ---
            overlay = img.copy()
            alpha = 0.6
            cv.rectangle(overlay, (10, 10), (340, 130), (20, 20, 20), -1)
            img = cv.addWeighted(overlay, alpha, img, 1 - alpha, 0)
            
            feedback_color = (0, 255, 0) if visual_feedback == "Good Form" else (0, 0, 255)
            cv.putText(img, "REPS", (30, 40), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, str(rep_counter), (35, 85), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv.LINE_AA)
            cv.putText(img, "STAGE", (130, 40), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, stage.upper(), (130, 85), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv.LINE_AA)
            cv.putText(img, "COACH", (30, 120), cv.FONT_HERSHEY_SIMPLEX, 0.7, feedback_color, 2, cv.LINE_AA)
            cv.putText(img, visual_feedback, (130, 120), cv.FONT_HERSHEY_SIMPLEX, 0.7, feedback_color, 2, cv.LINE_AA)
            
            mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)
            
    except Exception as e:
        pass

    cv.imshow(WINDOW_NAME, img)
    
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()
tts_engine.stop()