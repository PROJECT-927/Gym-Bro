import numpy as np
import mediapipe as mp
import time
import json
from utils import calculate_angle

mpPose = mp.solutions.pose

# --- Algorithm thresholds (from your original script) ---
VIS_THRESHOLD = 0.5
ELBOW_DOWN_THRESHOLD = 90
ELBOW_UP_THRESHOLD = 160
BODY_ANGLE_MIN = 150
KNEE_ANGLE_MIN = 160
ELBOW_TORSO_FLARE = 100
ELBOW_TORSO_TUCK = 50
NOT_LOW_ENOUGH_ELBOW = 110 # Elbow angle when "up" but not fully down
SMOOTHING_ALPHA = 0.5
MIN_CONSECUTIVE = 3 # Debounce frames

def process_pushups(results, state):
    """
    Processes MediaPipe results for Pushups.
    """
    
    # --- Unpack state ---
    stage = state.get('stage', 'UP') # Start in UP stage
    counter = state.get('counter', 0)
    down_frames = state.get('down_frames', 0)
    up_frames = state.get('up_frames', 0)
    smoothed_coords = state.get('smoothed_coords', {})
    
    # --- Frame variables ---
    current_error = ""
    visual_feedback = "Good Form"
    perfect_rep = False

    try:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Side Detection ---
            left_sh = landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value]
            right_sh = landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value]
            use_left = left_sh.visibility >= right_sh.visibility

            if use_left:
                idxs = {
                    'shoulder': mpPose.PoseLandmark.LEFT_SHOULDER.value,
                    'elbow': mpPose.PoseLandmark.LEFT_ELBOW.value,
                    'wrist': mpPose.PoseLandmark.LEFT_WRIST.value,
                    'hip': mpPose.PoseLandmark.LEFT_HIP.value,
                    'knee': mpPose.PoseLandmark.LEFT_KNEE.value,
                    'ankle': mpPose.PoseLandmark.LEFT_ANKLE.value,
                }
            else:
                idxs = {
                    'shoulder': mpPose.PoseLandmark.RIGHT_SHOULDER.value,
                    'elbow': mpPose.PoseLandmark.RIGHT_ELBOW.value,
                    'wrist': mpPose.PoseLandmark.RIGHT_WRIST.value,
                    'hip': mpPose.PoseLandmark.RIGHT_HIP.value,
                    'knee': mpPose.PoseLandmark.RIGHT_KNEE.value,
                    'ankle': mpPose.PoseLandmark.RIGHT_ANKLE.value,
                }
            
            # --- Visibility Check ---
            vis_ok = True
            coords = {}
            for name, idx in idxs.items():
                lm = landmarks[idx]
                if lm.visibility < VIS_THRESHOLD:
                    vis_ok = False
                    break
                coords[name] = [lm.x, lm.y]
            
            if not vis_ok:
                current_error = "Come closer / step into frame"
                visual_feedback = "Not tracking"
                down_frames = 0 # Reset debounce
                up_frames = 0
            else:
                # --- Get Coords (with smoothing) ---
                for k, v in coords.items():
                    if k not in smoothed_coords:
                        smoothed_coords[k] = v.copy()
                    else:
                        smoothed_coords[k][0] = SMOOTHING_ALPHA * v[0] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][0]
                        smoothed_coords[k][1] = SMOOTHING_ALPHA * v[1] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][1]
                
                shoulder = smoothed_coords['shoulder']
                elbow = smoothed_coords['elbow']
                wrist = smoothed_coords['wrist']
                hip = smoothed_coords['hip']
                ankle = smoothed_coords['ankle']
                knee = smoothed_coords['knee']

                # --- Calculations ---
                elbow_angle = calculate_angle(shoulder, elbow, wrist)
                elbow_torso_angle = calculate_angle(shoulder, elbow, hip)
                knee_angle = calculate_angle(hip, knee, ankle)
                body_angle = calculate_angle(shoulder, hip, ankle)

                # --- Debounce Logic ---
                if elbow_angle < ELBOW_DOWN_THRESHOLD:
                    down_frames += 1
                    up_frames = 0
                elif elbow_angle > ELBOW_UP_THRESHOLD:
                    up_frames += 1
                    down_frames = 0
                else:
                    down_frames = max(0, down_frames - 1)
                    up_frames = max(0, up_frames - 1)

                # --- State Machine & Error Checking ---
                form_ok = True
                
                if stage == 'UP':
                    if down_frames >= MIN_CONSECUTIVE:
                        stage = 'DOWN'
                    # Check for errors while in 'UP' state
                    elif body_angle < BODY_ANGLE_MIN:
                        current_error = 'Keep your body straight'
                    elif knee_angle < KNEE_ANGLE_MIN:
                        current_error = 'Straighten your legs'
                        
                elif stage == 'DOWN':
                    if up_frames >= MIN_CONSECUTIVE:
                        stage = 'UP'
                        # Check form ON THE WAY UP to count the rep
                        if body_angle < BODY_ANGLE_MIN:
                            current_error = "Keep your body straight"
                            form_ok = False
                        elif knee_angle < KNEE_ANGLE_MIN:
                            current_error = "Straighten your legs"
                            form_ok = False
                        
                        if form_ok:
                            counter += 1
                            perfect_rep = True
                            visual_feedback = "Good Rep!"
                        else:
                            visual_feedback = current_error # Show the error
                            
                    # Check for errors while in 'DOWN' state
                    if current_error == "":
                        if elbow_torso_angle > ELBOW_TORSO_FLARE:
                            current_error = "Don't flare your elbows"
                        elif elbow_torso_angle < ELBOW_TORSO_TUCK:
                            current_error = "Tuck your elbows closer"
        
        else: # No landmarks
            current_error = "Not tracking. Are you in frame?"
            visual_feedback = "Not tracking"

    except Exception as e:
        print(f"Landmark error (Pushups): {e}")
        current_error = "Make sure you are fully in frame"
        visual_feedback = "Make sure you are fully in frame"
    
    # --- Final Feedback ---
    if current_error:
        visual_feedback = current_error
        perfect_rep = False
    elif not perfect_rep: # Don't overwrite "Good Rep!"
        visual_feedback = "Good Form"

    # --- Prepare JSON & State ---
    feedback_data = {
        "reps": counter,
        "error": current_error,
        "adjustment": visual_feedback,
        "perfect_rep": perfect_rep
    }

    updated_state = {
        'stage': stage,
        'counter': counter,
        'down_frames': down_frames,
        'up_frames': up_frames,
        'smoothed_coords': smoothed_coords
    }
    
    return json.dumps(feedback_data), updated_state