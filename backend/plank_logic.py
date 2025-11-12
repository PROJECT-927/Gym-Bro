import numpy as np
import mediapipe as mp
import time
import json
from utils import calculate_angle

mpPose = mp.solutions.pose

def process_plank(results, state):
    """
    Processes MediaPipe results for Plank.
    """
    
    # --- Unpack state variables ---
    stage = state.get('stage', 'resting')
    start_time = state.get('start_time', 0)
    pause_start_time = state.get('pause_start_time', 0)
    total_paused_time = state.get('total_paused_time', 0)
    
    # --- Frame variables ---
    current_time = time.time()
    elapsed_time = 0
    current_error = ""
    visual_feedback = "Get into plank position"
    perfect_rep = False # We'll use this to mean "Good Form"

    # --- Calculate elapsed time ---
    if start_time > 0:
        # Calculate time paused *this* frame, if we are resting
        current_paused_time = current_time - pause_start_time if stage == "resting" and pause_start_time > 0 else 0
        # Total time is now - start - total paused - current pause
        elapsed_time = current_time - start_time - total_paused_time - current_paused_time
        
        # If we just resumed, current_paused_time will be large, so cap elapsed_time at its last known value
        if elapsed_time < 0:
             elapsed_time = state.get('last_elapsed_time', 0)


    try:
        # --- Crash-Proof Landmark Access ---
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Automatic Side Detection ---
            left_hip_visibility = landmarks[mpPose.PoseLandmark.LEFT_HIP.value].visibility
            right_hip_visibility = landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].visibility
            
            if left_hip_visibility > right_hip_visibility:
                # Get LEFT side landmarks
                shoulder, elbow, wrist, hip, ankle = (
                    [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y],
                    [landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.LEFT_ANKLE.value].y]
                )
            else:
                # Get RIGHT side landmarks
                shoulder, elbow, wrist, hip, ankle = (
                    [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y],
                    [landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ANKLE.value].y]
                )

            # --- Angle Calculations for Form Analysis ---
            body_angle = calculate_angle(shoulder, hip, ankle)
            arm_pit_angle = calculate_angle(hip, shoulder, elbow) # Measures if elbows are under shoulders
            elbow_angle = calculate_angle(shoulder, elbow, wrist) # Measures forearm angle

            # --- State Machine for Form and Timer ---
            if body_angle > 160: # Body is straight enough
                if stage == "resting":
                    # Transitioning from resting to planking
                    if start_time == 0: start_time = current_time
                    else: total_paused_time += current_time - pause_start_time
                
                stage = "planking"
                
                # --- Prioritized Form Feedback ---
                if arm_pit_angle < 75 or arm_pit_angle > 105:
                    current_error = "Align shoulders over elbows"
                elif elbow_angle < 75 or elbow_angle > 105:
                    current_error = "Keep forearms flat"
                else:
                    current_error = "" # Good Form!
            
            elif 140 < body_angle <= 160: # Hips are slightly sagging
                stage = "warning"
                current_error = "Warning: Hips are sagging"
            
            else: # body_angle <= 140, COMPLETE STOP
                if stage != "resting": 
                    pause_start_time = current_time # Record time we started resting
                stage = "resting"
                current_error = "Timer Paused - Get Back Up!"

        else: # No landmarks detected
            current_error = "Not tracking. Are you in frame?"
            if stage != "resting": 
                pause_start_time = current_time # Pause timer if person walks away
            stage = "resting"
            perfect_rep = False

    except Exception as e:
        print(f"Landmark error (Plank): {e}")
        current_error = "Make sure you are fully in frame"
        if stage != "resting": 
            pause_start_time = current_time
        stage = "resting"
        perfect_rep = False

    # --- Set final feedback ---
    if current_error:
        visual_feedback = current_error
        perfect_rep = False
    else:
        visual_feedback = "Good Form!"
        perfect_rep = True

    # --- Prepare Response ---
    feedback_data = {
        "reps": int(elapsed_time), # <-- Sending elapsed time as "reps"
        "error": current_error,
        "adjustment": visual_feedback,
        "perfect_rep": perfect_rep
    }

    # --- Prepare Updated State ---
    updated_state = {
        'stage': stage,
        'start_time': start_time,
        'pause_start_time': pause_start_time,
        'total_paused_time': total_paused_time,
        'last_elapsed_time': elapsed_time # Save last good time
    }

    return json.dumps(feedback_data), updated_state