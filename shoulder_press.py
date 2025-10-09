import cv2 as cv
import mediapipe as mp
import numpy as np

# Function to calculate angle between three points (in degrees)
def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b
    dot_product = np.dot(ba, bc)
    magnitude_ba = np.linalg.norm(ba)
    magnitude_bc = np.linalg.norm(bc)
    if magnitude_ba == 0 or magnitude_bc == 0:
        return 0.0
    cosine_angle = dot_product / (magnitude_ba * magnitude_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle = np.arccos(cosine_angle)
    return np.degrees(angle)

mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
pose = mpPose.Pose()

cap = cv.VideoCapture(0)

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
            
            # Right side landmarks (front view)
            rshoulder = [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y]
            relbow = [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y]
            rwrist = [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y]
            rhip = [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y]
            # Left side landmarks
            lshoulder = [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y]
            lelbow = [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y]
            lwrist = [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y]
            lhip = [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y]

            # Calculate elbow angles (shoulder - elbow - wrist)
            r_elbow_angle = calculate_angle(rshoulder, relbow, rwrist)
            l_elbow_angle = calculate_angle(lshoulder, lelbow, lwrist)
            rhip_angle = calculate_angle(rhip, rshoulder, relbow)
            lhip_angle = calculate_angle(lhip, lshoulder, lelbow)

            # Calculate shoulder alignment (horizontal distance between shoulders)
            # We use y difference to check if shoulders are level frontally
            shoulder_level_diff = abs(landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y - landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y)

            h, w, _ = img.shape
            
            # Convert to pixels for drawing
            rshoulder_px = (int(rshoulder[0] * w), int(rshoulder[1] * h))
            relbow_px = (int(relbow[0] * w), int(relbow[1] * h))
            rwrist_px = (int(rwrist[0] * w), int(rwrist[1] * h))
            rhip_px = (int(rhip[0] * w), int(rhip[1] * h))

            lshoulder_px = (int(lshoulder[0] * w), int(lshoulder[1] * h))
            lelbow_px = (int(lelbow[0] * w), int(lelbow[1] * h))
            lwrist_px = (int(lwrist[0] * w), int(lwrist[1] * h))
            lhip_px = (int(lhip[0] * w), int(lhip[1] * h))

            # Draw circles on landmarks
            for px in [rshoulder_px, relbow_px, rwrist_px, lshoulder_px, lelbow_px, lwrist_px, rhip_px, lhip_px]:
                cv.circle(img, px, 10, (0, 255, 0), cv.FILLED)

            # Display elbow angles on image
            cv.putText(img, f"Right Elbow: {int(r_elbow_angle)}°", (30, 90),
                       cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            cv.putText(img, f"Left Elbow: {int(l_elbow_angle)}°", (30, 130),
                       cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            # cv.putText(img, f"Right hip: {int(rhip_angle)}°", (200, 90),
            #            cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)
            # cv.putText(img, f"Left hip: {int(lhip_angle)}°", (200, 130),
            #            cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv.LINE_AA)

            warnings = []

            # Warning if elbow angles indicate excessive flare or rigid lock
            if r_elbow_angle > 100 and rhip_angle < 115:
                warnings.append("Right elbow flare too wide!")
            if l_elbow_angle > 100 and lhip_angle < 115:
                warnings.append("Left elbow flare too wide!")
            if r_elbow_angle < 40:
                warnings.append("Right elbow too close to body!")
            if l_elbow_angle < 40:
                warnings.append("Left elbow too close to body!")
            if rhip_angle < 70:
                warnings.append("Right arm too far down!")
            if lhip_angle < 70:
                warnings.append("Left arm too far down!")

            # Warning if shoulders are uneven (threshold depends on normalized coordinates, e.g., >0.03)
            if shoulder_level_diff > 0.03:
                warnings.append("Shoulders not level!")

            # Display warnings
            y0 = 170
            for i, w_msg in enumerate(warnings):
                cv.putText(img, w_msg, (30, y0 + i * 30), cv.FONT_HERSHEY_SIMPLEX,
                           0.7, (0, 0, 255), 2, cv.LINE_AA)

            mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)

    except Exception:
        pass

    cv.imshow("Shoulder Press Front View Monitoring", img)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()
