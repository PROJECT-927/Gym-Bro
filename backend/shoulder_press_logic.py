import numpy as np
import mediapipe as mp
import time
import json
from utils import calculate_angle # Import from utils

mpPose = mp.solutions.pose

def process_shoulder_press(results, state):
    """
    Processes MediaPipe results for Shoulder Press using the original logic.
    """
    
    # --- Unpack state variables ---
    rep_counter = state.get('rep_counter', 0)
    stage = state.get('stage', 'DOWN')
    last_print_time = state.get('last_print_time', 0)
    
    # --- Frame variables ---
    errors = [] 
    visual_feedback = "Good Form"
    perfect_rep = False
    current_error = "" 

    try:
        # --- Crash-Proof Landmark Access ---
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Get coordinates ---
            rshoulder = [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y]
            relbow = [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y]
            rwrist = [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y]
            rhip = [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y]
            lshoulder = [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y]
            lelbow = [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y]
            lwrist = [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y]
            lhip = [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y]

            # --- Calculate angles ---
            r_elbow_angle = calculate_angle(rshoulder, relbow, rwrist)
            l_elbow_angle = calculate_angle(lshoulder, lelbow, lwrist)
            r_shoulder_angle = calculate_angle(rhip, rshoulder, relbow)
            l_shoulder_angle = calculate_angle(lhip, lshoulder, lelbow)
            
            # --- Shoulder Level Calculation (from your old code) ---
            shoulder_radians = np.arctan2(rshoulder[1] - lshoulder[1], rshoulder[0] - lshoulder[0])
            shoulder_angle = np.abs(np.degrees(shoulder_radians))
            
            # Using your original 93/87 values
            is_shoulders_level = (shoulder_angle < 93) and (shoulder_angle > 87) 
            # ----------------------------------------

            # Debug print
            current_time = time.time()
            if (current_time - last_print_time) > 2.0: 
                print(f"shoulder angles: {r_shoulder_angle}, {l_shoulder_angle}")
                last_print_time = current_time
            
            # --- Prioritized Error Checking (Using your original thresholds) ---
            
            # Priority 1: "Bring your elbows up"
            if r_shoulder_angle < 55 or l_shoulder_angle < 55:
                errors.append("Bring your elbows up")
            
            # Priority 2: "Tuck your elbows in"
            elif (r_elbow_angle > 110 and r_shoulder_angle < 115) or \
                 (l_elbow_angle > 110 and l_shoulder_angle < 115):
                errors.append("Tuck your elbows in")

            # Priority 3: "Keep shoulders level"
            elif not is_shoulders_level:
                errors.append("Keep shoulders level")
            
            # Priority 4: "Elbows too close"
            elif r_elbow_angle < 45 or l_elbow_angle < 45:
                errors.append("Elbows too close to shoulders")
            
            # --- Rep Counter (Using your original thresholds) ---
            if r_elbow_angle > 160 and l_elbow_angle > 160 and stage == 'DOWN':
                rep_counter += 1
                stage = 'UP'
                if not errors: # Rep is perfect only if no errors were found
                    perfect_rep = True
            elif r_elbow_angle < 90 and l_elbow_angle < 90:
                stage = 'DOWN'

            # --- Select the single highest-priority error ---
            if errors:
                current_error = errors[0]
                visual_feedback = current_error
                perfect_rep = False 
            else:
                visual_feedback = "Good Form"
                if stage != 'UP': 
                     perfect_rep = False
        
        else:
            # This happens if no person is detected at all
            current_error = "Not tracking. Are you in frame?"
            visual_feedback = "Not tracking"
            perfect_rep = False

    except Exception as e:
        # This happens if a landmark (like an elbow) goes off-screen
        print(f"Landmark error (Shoulder Press): {e}")
        current_error = "Make sure you are fully in frame"
        visual_feedback = "Make sure you are fully in frame"
        perfect_rep = False

    # --- Prepare Response ---
    feedback_data = {
        "reps": rep_counter,
        "error": current_error, # Send the single highest-priority error, or ""
        "adjustment": visual_feedback,
        "perfect_rep": perfect_rep
    }

    # --- Prepare Updated State ---
    updated_state = {
        'rep_counter': rep_counter,
        'stage': stage,
        'last_print_time': last_print_time
    }

    return json.dumps(feedback_data), updated_state