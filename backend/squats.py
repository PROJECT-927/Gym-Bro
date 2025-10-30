import cv2 as cv
import mediapipe as mp
import numpy as np

# Function to calculate angle between three points (in degrees)
def calculate_angle(a, b, c):
    """Calculates the angle between three points (in degrees)."""
    a = np.array(a)  # First point
    b = np.array(b)  # Middle point (vertex)
    c = np.array(c)  # End point
    
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

# --- Squat Counter and State Variables ---
counter = 0 
stage = 'up'
feedback = ''

# --- Main Loop ---
while True:
    success, img = cap.read()
    if not success:
        break
    
    # Flip the image horizontally for a later selfie-view display
    img = cv.flip(img, 1)
    
    # Convert the BGR image to RGB
    imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    results = pose.process(imgRGB)
    
    # --- Landmark Extraction and Processing ---
    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Automatic Side Detection (Left vs Right) ---
            # Use visibility of hips to determine which side is facing the camera
            left_hip_visibility = landmarks[mpPose.PoseLandmark.LEFT_HIP.value].visibility
            right_hip_visibility = landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].visibility

            if left_hip_visibility > right_hip_visibility:
                # Use LEFT side landmarks
                shoulder = [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y]
                hip = [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y]
                knee = [landmarks[mpPose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mpPose.PoseLandmark.LEFT_KNEE.value].y]
                ankle = [landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].y]
                toe = [landmarks[mpPose.PoseLandmark.LEFT_FOOT_INDEX.value].x, landmarks[mpPose.PoseLandmark.LEFT_FOOT_INDEX.value].y]
            else:
                # Use RIGHT side landmarks
                shoulder = [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y]
                hip = [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y]
                knee = [landmarks[mpPose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mpPose.PoseLandmark.RIGHT_KNEE.value].y]
                ankle = [landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].y]
                toe = [landmarks[mpPose.PoseLandmark.RIGHT_FOOT_INDEX.value].x, landmarks[mpPose.PoseLandmark.RIGHT_FOOT_INDEX.value].y]

            # --- Angle Calculations ---
            knee_angle = calculate_angle(hip, knee, ankle)
            hip_angle = calculate_angle(shoulder, hip, knee)
            torso_angle = calculate_angle(shoulder, hip, ankle)

            # --- Form Analysis & Feedback ---
            # Check for "Knees Past Toes" - compare x-coordinates
            if knee[0] > toe[0] + 0.05: # 0.05 is a buffer
                feedback = "Knees past toes!"
            # Check for "Back Straightness" - torso angle
            elif torso_angle < 70:
                feedback = "Keep your chest up!"
            else:
                feedback = "Good Form"

            # --- Repetition Counting Logic ---
            if knee_angle < 100 and hip_angle < 100:
                stage = "down"
            if knee_angle > 160 and hip_angle > 160 and stage == 'down':
                stage = "up"
                counter += 1
                feedback = "Rep Counted!"

            # --- Drawing and UI ---
            h, w, _ = img.shape
            
            # Status Box
            cv.rectangle(img, (20, 20), (350, 160), (0, 0, 0), cv.FILLED)
            cv.putText(img, "REPS", (40, 60), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, str(counter), (40, 120), cv.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3, cv.LINE_AA)
            
            cv.putText(img, "STAGE", (180, 60), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, stage.upper(), (180, 120), cv.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3, cv.LINE_AA)
            
            # Feedback Box
            cv.rectangle(img, (20, h - 80), (620, h - 20), (0, 0, 0), cv.FILLED)
            cv.putText(img, f"FEEDBACK: {feedback}", (40, h - 45), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv.LINE_AA)

            # Draw landmarks and connections
            mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS,
                                  mpDraw.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2), 
                                  mpDraw.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2))

    except Exception as e:
        # print(f"Error: {e}") # Uncomment to debug
        pass

    cv.imshow("Squat Form Analysis", img)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()