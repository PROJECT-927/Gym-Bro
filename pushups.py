import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import pyttsx3

# Text-to-Speech
engine = pyttsx3.init()

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

stage = None
counter = 0
last_feedback = None

while True:
    success, img = cap.read()
    if not success:
        break

    img = cv.flip(img, 1)
    imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    results = pose.process(imgRGB)

    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            # Choose side automatically by visibility
            left_shoulder_vis = landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].visibility
            right_shoulder_vis = landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].visibility

            if left_shoulder_vis > right_shoulder_vis:
                shoulder = [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y]
                elbow = [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y]
                wrist = [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y]
                hip = [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y]
            else:
                shoulder = [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y]
                elbow = [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y]
                wrist = [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y]
                hip = [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y]

            elbow_angle = calculate_angle(shoulder, elbow, wrist)
            body_angle = calculate_angle(shoulder, hip, [hip[0], hip[1]+0.1])

            feedback = ""

            # Heuristic: elbow angle < 90 -> down, >160 -> up
            if elbow_angle < 90:
                if stage == 'up' or stage is None:
                    stage = 'down'
                    feedback = 'Down'
            if elbow_angle > 160:
                if stage == 'down':
                    stage = 'up'
                    counter += 1
                    feedback = f'Good rep {counter}'

            # Simple form checks
            if body_angle < 140:
                feedback = 'Keep your body straight'

            # Voice feedback
            if feedback and feedback != last_feedback:
                engine.say(feedback)
                engine.runAndWait()
                last_feedback = feedback

            # Draw UI
            h, w, _ = img.shape
            cv.rectangle(img, (10,10), (350,120), (0,0,0), cv.FILLED)
            cv.putText(img, 'PUSH-UP COUNTER', (20,40), cv.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
            cv.putText(img, f'REPS: {counter}', (20,85), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)
            cv.putText(img, f'STAGE: {stage or "-"}', (200,85), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

            mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)

    except Exception:
        pass

    cv.imshow('Push-up Counter', img)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()
