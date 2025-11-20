import mediapipe as mp
import json
import numpy as np
from utils import calculate_angle

mpPose = mp.solutions.pose

def process_squats(results, state):
    reps = state.get('rep_counter', 0)
    stage = state.get('stage', 'not ready')
    ready = state.get('ready', False)
    max_depth = state.get('max_depth', 180)
    init_ankle_y = state.get('init_ankle_y', None)
    hip_start_y = state.get('hip_start_y', None)
    sh_start_y = state.get('sh_start_y', None)


    KNEE_DOWN = 110
    KNEE_UP = 150
    KNEE_DEEP = 70
    VIS_THRESH = 0.6

    feedback = ""
    error = ""
    perfect = False

    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark
        
       
        l_vis = lm[mpPose.PoseLandmark.LEFT_SHOULDER.value].visibility
        r_vis = lm[mpPose.PoseLandmark.RIGHT_SHOULDER.value].visibility
        
        if l_vis > r_vis:
            s_idx = mpPose.PoseLandmark.LEFT_SHOULDER.value
            h_idx = mpPose.PoseLandmark.LEFT_HIP.value
            k_idx = mpPose.PoseLandmark.LEFT_KNEE.value
            a_idx = mpPose.PoseLandmark.LEFT_ANKLE.value
        else:
            s_idx = mpPose.PoseLandmark.RIGHT_SHOULDER.value
            h_idx = mpPose.PoseLandmark.RIGHT_HIP.value
            k_idx = mpPose.PoseLandmark.RIGHT_KNEE.value
            a_idx = mpPose.PoseLandmark.RIGHT_ANKLE.value

        sh = [lm[s_idx].x, lm[s_idx].y]
        hip = [lm[h_idx].x, lm[h_idx].y]
        knee = [lm[k_idx].x, lm[k_idx].y]
        ankle = [lm[a_idx].x, lm[a_idx].y]

        # --- Calculate Body Scale ---
        shin_len = np.linalg.norm(np.array(knee) - np.array(ankle))

        if lm[s_idx].visibility < VIS_THRESH or lm[a_idx].visibility < VIS_THRESH:
            error = "Full body not visible"
        else:
            knee_ang = calculate_angle(hip, knee, ankle)

            if not ready:
                if knee_ang > 160:
                    ready = True
                    feedback = "Start Squat"
                    stage = "up"
                    init_ankle_y = ankle[1]
                else:
                    feedback = "Stand Straight"
            else:
                # --- 1. DETECT ERRORS ---
                # These are calculated regardless of what happens next
                
                # Knees Caving
                if abs(knee[0] - ankle[0]) > (shin_len * 0.50) and stage == "down":
                    error = "Knees caving in"
                
                # Heels Lifting
                elif init_ankle_y and (init_ankle_y - ankle[1]) > (shin_len * 0.15) and stage == "down":
                    error = "Heels lifting"
                
                # Hips Rising
                elif stage == "up" and hip_start_y and sh_start_y:
                    hip_rise = hip_start_y - hip[1]
                    sh_rise = sh_start_y - sh[1]
                    if abs(sh_rise) > 0.01 and abs(hip_rise)/abs(sh_rise) > 1.5:
                        error = "Hips rising too fast"

                # --- 2. STATE MACHINE (FIXED) ---
                # We process stage changes even if there is an error, so you don't get stuck.

                # GOING DOWN
                if knee_ang < KNEE_DOWN:
                    stage = "down"
                    max_depth = min(max_depth, knee_ang)
                    
                    # Only show depth feedback if there isn't a more serious error
                    if not error:
                        feedback = "Go Deeper"
                        if knee_ang <= KNEE_DEEP: feedback = "Perfect Depth"
                        elif 70 <= knee_ang <= 100: feedback = "Good Parallel"
                    
                    hip_start_y = hip[1]
                    sh_start_y = sh[1]

                # GOING UP (FINISHING REP)
                elif knee_ang > KNEE_UP and stage == "down":
                    stage = "up" # Force stage reset immediately
                    
                    # Now decide if we count the rep
                    if error:
                        # If there was an error during the movement, don't count it
                        feedback = "Fix Form"
                        perfect = False
                    else:
                        # If no error, check depth
                        if max_depth > 130:
                            error = "Not deep enough"
                            perfect = False
                        else:
                            reps += 1
                            perfect = True
                            feedback = "Good Rep!"
                    
                    # Reset variables for next rep regardless of success/failure
                    max_depth = 180
                    hip_start_y = None
                    sh_start_y = None

    else:
        error = "Not tracking"

    # If we have an error, the feedback usually matches the error
    final_feedback = feedback
    if error:
        final_feedback = error

    data = { 
        "reps": reps, 
        "error": error, 
        "adjustment": final_feedback, 
        "perfect_rep": perfect 
    }
    
    new_state = { 
        'rep_counter': reps, 
        'stage': stage, 
        'ready': ready, 
        'max_depth': max_depth, 
        'init_ankle_y': init_ankle_y, 
        'hip_start_y': hip_start_y, 
        'sh_start_y': sh_start_y 
    }
    return json.dumps(data), new_state