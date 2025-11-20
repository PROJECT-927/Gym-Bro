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
    
    # --- NEW: Retrieve fixed shin length from state ---
    fixed_shin_len = state.get('fixed_shin_len', None)

    KNEE_DOWN = 110
    KNEE_UP = 150
    KNEE_DEEP = 70
    VIS_THRESH = 0.6
    DEPTH_THRESHOLD = 140 # Relaxed threshold

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

        # We calculate current length just for debugging/logging, 
        # but we won't use it for math while moving.
        current_shin_len = np.linalg.norm(np.array(knee) - np.array(ankle))

        if lm[s_idx].visibility < VIS_THRESH or lm[a_idx].visibility < VIS_THRESH:
            error = "Full body not visible"
        else:
            knee_ang = calculate_angle(hip, knee, ankle)

            if not ready:
                if knee_ang > 160:
                    # --- LATCHING PHASE ---
                    # Only set shin length when standing straight
                    ready = True
                    fixed_shin_len = current_shin_len 
                    init_ankle_y = ankle[1]
                    
                    feedback = "Start Squat"
                    stage = "up"
                    print(f"System Ready. Shin Length Locked at: {fixed_shin_len:.4f}")
                else:
                    feedback = "Stand Straight"
            else:
                # Use the LOCKED shin length for all error checks
                reference_len = fixed_shin_len if fixed_shin_len else current_shin_len

                # --- 1. DETECT ERRORS ---
                if knee_ang < 160: # Only check errors when actually moving
                    print("angle", abs(knee[0] - ankle[0]))
                    # Knees Caving (Fixed logic)
                    if abs(knee[0] - ankle[0]) < (0.1) and stage == "down":
                        error = "Knees caving in"
                        print(error)
                    # Not Deep Enough
                    # Heels Lifting (Using locked length)
                    elif init_ankle_y and (init_ankle_y - ankle[1]) > (reference_len * 0.20) and stage == "down":
                        error = "Heels lifting"
                        print(error)
                    
                    # Hips Rising
                    elif stage == "up" and hip_start_y and sh_start_y:
                        hip_rise = hip_start_y - hip[1]
                        sh_rise = sh_start_y - sh[1]
                        if abs(sh_rise) > 0.01 and abs(hip_rise)/abs(sh_rise) > 1.5:
                            error = "Hips rising too fast"

                # --- 2. STATE MACHINE ---
                if knee_ang < KNEE_DOWN:
                    stage = "down"
                    max_depth = min(max_depth, knee_ang)
                    
                    if not error:
                        feedback = "Go Deeper"
                        if knee_ang <= KNEE_DEEP: feedback = "Perfect Depth"
                        elif 70 <= knee_ang <= 100: feedback = "Good Parallel"
                    
                    hip_start_y = hip[1]
                    sh_start_y = sh[1]

                # GOING UP (FINISHING REP)
                elif knee_ang > KNEE_UP and stage == "down":
                    stage = "up"
                    
                    # REPAIRED REP COUNTING LOGIC
                    if error and error != "Not deep enough":
                        # Count the rep but mark it imperfect
                        reps += 1
                        perfect = False
                        feedback = f"Rep: {error}"
                    else:
                        if max_depth > DEPTH_THRESHOLD:
                            feedback = "Squat Deeper!"
                            perfect = False
                        else:
                            reps += 1
                            perfect = True
                            feedback = "Good Rep!"
                    
                    # Reset rep vars
                    max_depth = 180
                    hip_start_y = None
                    sh_start_y = None

    else:
        error = "Not tracking"

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
        'sh_start_y': sh_start_y,
        'fixed_shin_len': fixed_shin_len # Save the locked length to state
    }
    return json.dumps(data), new_state