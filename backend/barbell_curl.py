import cv2
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading

def speak(engine, text):
    """Function to handle text-to-speech in a separate thread."""
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass

def calculate_angle(a, b, c):
    """Calculates the angle between three points."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

def calculate_distance(a, b):
    """Calculates the Euclidean distance between two points."""
    return np.linalg.norm(np.array(a) - np.array(b))

# --- Initialization ---
tts_engine = pyttsx3.init()
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0)

# --- State & Counter Variables ---
rep_counter = 0
stage = 'DOWN'
current_error = None
last_rep_time = 0
MIN_REP_DURATION = 2  # Minimum seconds for a valid rep
SYMMETRY_THRESHOLD = 10 # Max allowable angle difference between arms
# --- Feedback & Alert Variables ---
persistent_error = None
error_start_time = None
ERROR_DURATION_THRESHOLD = 1.0  # Hold an error for 1s to trigger voice
VOICE_COOLDOWN = 4.0
last_voice_alert_time = 0

# --- UI Setup ---
WINDOW_NAME = "barbell Curl AI Coach"
# cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
# cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# --- Main Loop ---
while cap.isOpened():
    success, image = cap.read()
    if not success:
        break

    image = cv2.flip(image, 1)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)
    
    current_error = None  # Reset error at the start of each frame

    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Get Coordinates ---
            r_shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
            r_elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
            r_wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
            r_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]

            l_shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            l_elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            l_wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            l_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]

            # --- Calculate Angles and Distances ---
            r_elbow_angle = calculate_angle(r_shoulder, r_elbow, r_wrist)
            l_elbow_angle = calculate_angle(l_shoulder, l_elbow, l_wrist)
            
            r_shoulder_angle = calculate_angle(r_hip, r_shoulder, r_elbow)
            l_shoulder_angle = calculate_angle(l_hip, l_shoulder, l_elbow)
            
            shoulder_dist = calculate_distance(l_shoulder, r_shoulder)
            elbow_dist = calculate_distance(l_elbow, r_elbow)
            elbow_shoulder_ratio = elbow_dist / shoulder_dist
            arm_angle_diff = abs(r_shoulder_angle - l_shoulder_angle)
# --- Rule-Based Error Detection ---
            if r_shoulder_angle > 35 or l_shoulder_angle > 35:
                current_error = "PIN YOUR ELBOWS"
            elif arm_angle_diff > SYMMETRY_THRESHOLD:
                current_error = "UNEVEN ARMS"
            
            if r_shoulder_angle > 35 or l_shoulder_angle > 35:
                current_error = "PIN YOUR ELBOWS"
            elif elbow_shoulder_ratio > 1.4:
                current_error = "ARMS TOO WIDE"
            elif elbow_shoulder_ratio < 0.8:
                 current_error = "ARMS TOO NARROW"

            # --- Rep Counter & State Machine ---
            if current_error is None:
                if r_elbow_angle < 40 and l_elbow_angle < 40 and stage == 'DOWN':
                    if (time.time() - last_rep_time) < MIN_REP_DURATION:
                        current_error = "TOO FAST"
                    else:
                        rep_counter += 1
                        last_rep_time = time.time()
                        stage = 'UP'
                elif r_elbow_angle > 150 and l_elbow_angle > 150 and stage == 'UP':
                    stage = 'DOWN'
            
            # --- Voice Feedback Logic ---
            if current_error:
                if current_error != persistent_error:
                    persistent_error = current_error
                    error_start_time = time.time()
                
                if time.time() - error_start_time >= ERROR_DURATION_THRESHOLD:
                    if time.time() - last_voice_alert_time >= VOICE_COOLDOWN:
                        thread = threading.Thread(target=speak, args=(tts_engine, persistent_error))
                        thread.start()
                        last_voice_alert_time = time.time()
            else:
                persistent_error = None
                error_start_time = None

            # --- Visual Feedback & UI ---
            visual_feedback = "GOOD"
            feedback_color = (0, 255, 0) # Green

            if current_error:
                visual_feedback = current_error
                feedback_color = (0, 0, 255) # Red
            elif stage == 'DOWN':
                visual_feedback = "CURL UP"
            elif stage == 'UP':
                visual_feedback = "LOWER SLOWLY"
            
            overlay = image.copy()
            cv2.rectangle(overlay, (0, 0), (image.shape[1], 90), (20, 20, 20), -1)
            image = cv2.addWeighted(overlay, 0.7, image, 0.3, 0)

            # Display Reps
            cv2.putText(image, "REPS", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(image, str(rep_counter), (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

            # Display Stage
            cv2.putText(image, "STAGE", (200, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(image, stage, (200, 75), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
            
            # Display Feedback
            cv2.putText(image, "FEEDBACK", (400, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(image, visual_feedback, (400, 75), cv2.FONT_HERSHEY_SIMPLEX, 1.2, feedback_color, 2)
            
            # Draw landmarks
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

    except Exception as e:
        # print(f"An error occurred: {e}") # Uncomment for debugging
        pass

    cv2.imshow(WINDOW_NAME,image)
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# --- Cleanup ---
cap.release()
cv2.destroyAllWindows()
# Ensure the TTS engine loop is properly terminated
tts_thread = threading.Thread(target=speak, args=(tts_engine, ""))
tts_thread.start()
tts_thread.join()
