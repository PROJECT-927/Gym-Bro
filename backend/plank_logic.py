import numpy as np
import mediapipe as mp
import time
import json
import math
from utils import calculate_angle

mpPose = mp.solutions.pose

# --- Algorithm thresholds ---
VIS_THRESHOLD = 0.5
BODY_ANGLE_MIN = 160      # Straight body alignment
KNEE_ANGLE_MIN = 160      # Legs should be straight
HIP_SAG_THRESHOLD = 0.08  # Ratio of torso length for hip sag detection
HIP_PIKE_THRESHOLD = 0.08 # Ratio of torso length for pike detection
ELBOW_SHOULDER_ALIGNMENT = 0.15  # Max horizontal distance ratio
HEAD_ALIGNMENT_THRESHOLD = 0.2   # Head should align with spine
SMOOTHING_ALPHA = 0.5
MIN_HOLD_FRAMES = 15     # Frames to count as valid hold (1 second at 30fps)
FORM_BREAK_FRAMES = 15    # Consecutive bad form frames before breaking hold
MIN_GROUND_CLEARANCE = 0.15  # Minimum ratio of torso length that body should be off ground
PLANK_ELBOW_ANGLE_MIN = 70   # Minimum elbow bend for forearm plank
PLANK_ELBOW_ANGLE_MAX = 110  # Maximum elbow bend for forearm plank

def process_plank(results, state):
    """
    Processes MediaPipe results for Plank holds.
    """
    
    # --- Unpack state ---
    is_holding = state.get('is_holding', False)
    good_form_frames = state.get('good_form_frames', 0)
    bad_form_frames = state.get('bad_form_frames', 0)
    last_timestamp = state.get('last_timestamp', time.time())
    smoothed_coords = state.get('smoothed_coords', {})
    reps_count = state.get('reps_count', 0)  # Counts seconds of good hold
    frames_in_current_second = state.get('frames_in_current_second', 0)
    
    # --- Frame variables ---
    current_error = ""
    visual_feedback = "Get into plank position"
    in_plank_position = False
    good_form = False
    current_timestamp = time.time()
    delta_time = current_timestamp - last_timestamp

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
                    'nose': mpPose.PoseLandmark.NOSE.value,
                }
            else:
                idxs = {
                    'shoulder': mpPose.PoseLandmark.RIGHT_SHOULDER.value,
                    'elbow': mpPose.PoseLandmark.RIGHT_ELBOW.value,
                    'wrist': mpPose.PoseLandmark.RIGHT_WRIST.value,
                    'hip': mpPose.PoseLandmark.RIGHT_HIP.value,
                    'knee': mpPose.PoseLandmark.RIGHT_KNEE.value,
                    'ankle': mpPose.PoseLandmark.RIGHT_ANKLE.value,
                    'nose': mpPose.PoseLandmark.NOSE.value,
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
                good_form_frames = 0
                bad_form_frames += 1
                frames_in_current_second = 0
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
                nose = smoothed_coords['nose']

                # --- Calculations ---
                knee_angle = calculate_angle(hip, knee, ankle)
                body_angle = calculate_angle(shoulder, hip, ankle)
                torso_len = math.dist(shoulder, hip)
                elbow_angle = calculate_angle(shoulder, elbow, wrist)

                # --- PRIORITY 1: Check leg straightness FIRST ---
                if knee_angle < KNEE_ANGLE_MIN:
                    current_error = "Straighten your legs"
                    visual_feedback = current_error
                    good_form_frames = 0
                    bad_form_frames += 1
                    frames_in_current_second = 0
                    in_plank_position = False
                    
                # --- PRIORITY 2: Check body alignment (hips sagging/piking) ---
                elif body_angle < BODY_ANGLE_MIN:
                    midpoint_y = (shoulder[1] + ankle[1]) / 2
                    if hip[1] < (midpoint_y - (HIP_PIKE_THRESHOLD * torso_len)):
                        current_error = "Hips too high - lower them"
                    elif hip[1] > (midpoint_y + (HIP_SAG_THRESHOLD * torso_len)):
                        current_error = "Hips sagging - engage your core"
                    else:
                        current_error = "Keep body straight"
                    
                    visual_feedback = current_error
                    good_form_frames = 0
                    bad_form_frames += 1
                    frames_in_current_second = 0
                    in_plank_position = False
                
                # --- PRIORITY 3: Check if lying down (body too close to ground) ---
                elif True:
                    # In a proper plank, hips should be significantly elevated
                    # If hip is at similar Y level as ankle, person is likely lying down
                    hip_ankle_vertical_dist = abs(hip[1] - ankle[1])
                    is_lying_down = hip_ankle_vertical_dist < (MIN_GROUND_CLEARANCE * torso_len)
                    
                    # Also check if wrists are at similar level to shoulders (lying flat)
                    wrist_shoulder_vertical_dist = abs(wrist[1] - shoulder[1])
                    is_flat = wrist_shoulder_vertical_dist < (0.1 * torso_len)
                    
                  
                    if is_lying_down or is_flat:
                        in_plank_position = False
                        current_error = "Get up into plank position"
                        visual_feedback = "Not in plank - body too low"
                        good_form_frames = 0
                        bad_form_frames += 1
                        frames_in_current_second = 0
                    else:
                        # --- Check if in plank position ---
                        is_forearm_plank = PLANK_ELBOW_ANGLE_MIN <= elbow_angle <= PLANK_ELBOW_ANGLE_MAX
                        
                        # Check if body is properly elevated and horizontal-ish
                        is_elevated = hip[1] < shoulder[1] + (0.2 * torso_len)  # Hips not way below shoulders
                        
                        in_plank_position = is_forearm_plank and is_elevated
                        
                        if in_plank_position:
                            # --- Form Validation ---
                            good_form = True
                            
                            # Elbow alignment check
                            elbow_shoulder_x_diff = abs(elbow[0] - shoulder[0])
                            if elbow_shoulder_x_diff > (torso_len * ELBOW_SHOULDER_ALIGNMENT):
                                current_error = "Position elbows under shoulders"
                                good_form = False
                            
                            # Head/neck alignment check
                            if good_form:
                                expected_head_y = shoulder[1] - (0.1 * torso_len)
                                if abs(nose[1] - expected_head_y) > (HEAD_ALIGNMENT_THRESHOLD * torso_len):
                                    if nose[1] < expected_head_y - (0.1 * torso_len):
                                        current_error = "Don't look up - neutral neck"
                                        good_form = False
                                    else:
                                        current_error = "Don't drop your head"
                                        good_form = False
                        
                        # Update form tracking
                        if good_form:
                           
                           
                           
                           good_form_frames += 1
                           bad_form_frames = 0
                           frames_in_current_second += 1
                           visual_feedback = "Perfect form! Keep holding"
                            
                            # Increment reps (seconds) when we've held good form for ~30 frames (1 second)
                           if frames_in_current_second >= 30:
                                
                                
                                reps_count += 1
                                frames_in_current_second = 0
                        else:


                            good_form_frames = 0
                            bad_form_frames += 1
                            frames_in_current_second = 0
                            visual_feedback = current_error
                        
                        # --- Hold State Tracking ---
                        if good_form_frames >= MIN_HOLD_FRAMES:

                            is_holding = True
                        elif bad_form_frames >= FORM_BREAK_FRAMES:

                            is_holding = False
                    
                        else:

                            # Not in proper plank position but not lying down either
                            visual_feedback = "Get into forearm plank position"
                            # current_error = "Bend elbows to 90 degrees"
                            good_form_frames = 0
                            bad_form_frames += 1
                            frames_in_current_second = 0
                            
                            if is_holding and bad_form_frames >= FORM_BREAK_FRAMES:

                                is_holding = False
        
        else: 
            current_error = "Not tracking. Are you in frame?"
            visual_feedback = "Not tracking"
            good_form_frames = 0
            bad_form_frames += 1
            frames_in_current_second = 0
            if is_holding and bad_form_frames >= FORM_BREAK_FRAMES:

                is_holding = False

    except Exception as e:
        print(f"Landmark error (Plank): {e}")
        current_error = "Make sure you are fully in frame"
        visual_feedback = "Make sure you are fully in frame"
        good_form_frames = 0
        bad_form_frames += 1
        frames_in_current_second = 0
        if is_holding and bad_form_frames >= FORM_BREAK_FRAMES:
            is_holding = False
    
    # --- Prepare JSON & State ---
    feedback_data = {
        "reps": reps_count,  # Now represents seconds of good hold
        "is_holding": is_holding,
        "in_position": in_plank_position,
        "good_form": good_form,
        "error": current_error,
        "adjustment": visual_feedback
    }

    updated_state = {
        'is_holding': is_holding,
        'good_form_frames': good_form_frames,
        'bad_form_frames': bad_form_frames,
        'last_timestamp': current_timestamp,
        'smoothed_coords': smoothed_coords,
        'reps_count': reps_count,
        'frames_in_current_second': frames_in_current_second
    }
    
    return json.dumps(feedback_data), updated_state