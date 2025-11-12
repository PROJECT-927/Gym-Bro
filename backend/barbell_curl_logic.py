import numpy as np

import mediapipe as mp

import time

import json

from utils import calculate_angle, calculate_distance # Import from utils



mpPose = mp.solutions.pose



def process_barbell_curl(results, state):

    """

    Processes MediaPipe results for Barbell Curls.

    """

    # --- Unpack state variables ---

    rep_counter = state.get('rep_counter', 0)

    stage = state.get('stage', 'DOWN')

    last_rep_time = state.get('last_rep_time', 0)

    last_print_time = state.get('last_print_time', 0)



    # --- Frame variables ---

    errors = []

    visual_feedback = "Good Form"

    perfect_rep = False

    current_error = ""



    # --- Constants for Barbell Curl ---

    MIN_REP_DURATION = 1.5 # Minimum seconds between reps to avoid "TOO FAST"

    SYMMETRY_THRESHOLD = 15 # Max allowable angle difference between arms



    try:

        # --- Crash-Proof Landmark Access ---

        if results.pose_landmarks:

            landmarks = results.pose_landmarks.landmark



            # --- Get Coordinates ---

            r_shoulder = [landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y]

            r_elbow = [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y]

            r_wrist = [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y]

            r_hip = [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y]



            l_shoulder = [landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y]

            l_elbow = [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y]

            l_wrist = [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y]

            l_hip = [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y]



            # --- Calculate Angles and Distances ---

            r_elbow_angle = calculate_angle(r_shoulder, r_elbow, r_wrist)

            l_elbow_angle = calculate_angle(l_shoulder, l_elbow, l_wrist)

            r_shoulder_angle = calculate_angle(r_hip, r_shoulder, r_elbow) # Angle relative to hip

            l_shoulder_angle = calculate_angle(l_hip, l_shoulder, l_elbow) # Angle relative to hip



            # Symmetry Check

            arm_angle_diff = abs(r_elbow_angle - l_elbow_angle) # Compare elbow angles



            # --- Debug Print ---

            current_time = time.time()

            if (current_time - last_print_time) > 2.0:

                print(f"Elbow (R/L): {r_elbow_angle:.0f}/{l_elbow_angle:.0f}  Shoulder (R/L): {r_shoulder_angle:.0f}/{l_shoulder_angle:.0f} Arm Diff: {arm_angle_diff:.0f}")

                last_print_time = current_time



            # --- Prioritized Error Checking for Barbell Curl ---

            # Priority 1: Pin Your Elbows (Shoulder angle shouldn't change much)

            # Allow a small movement (e.g., < 30 degrees from vertical)

            # Using 35 from your old script

            if r_shoulder_angle > 35 or l_shoulder_angle > 35:

                 errors.append("Pin your elbows")



            # Priority 2: Uneven Arms (Elbow angles should be similar)

            # Using 15 from your websocket script (old one was 10)

            elif arm_angle_diff > SYMMETRY_THRESHOLD:

                 errors.append("Uneven arms")



            # --- Rep Counter & State Machine ---

            # Check for "TOO FAST" only if no other major error exists

            is_too_fast = False

            if not errors and (time.time() - last_rep_time) < MIN_REP_DURATION and stage == 'DOWN':

                 is_too_fast = True

                 errors.append("Too fast") # Add as lowest priority error





            if not errors: # Only count reps or change stage if no primary errors

                if r_elbow_angle < 40 and l_elbow_angle < 40 and stage == 'DOWN':

                    # Valid start of UP movement

                    rep_counter += 1

                    last_rep_time = time.time() # Record time rep *started*

                    stage = 'UP'

                    perfect_rep = True # Assume perfect unless an error occurs later

                elif r_elbow_angle > 150 and l_elbow_angle > 150 and stage == 'UP':

                    stage = 'DOWN'

                    perfect_rep = False # Reset perfect flag when going down



            # --- Select the single highest-priority error ---

            if errors:

                current_error = errors[0]

                visual_feedback = current_error

                perfect_rep = False # Any error invalidates perfect rep

            else:

                # Provide guidance based on stage if no error

                if stage == 'DOWN':

                     visual_feedback = "Curl Up"

                elif stage == 'UP':

                     visual_feedback = "Lower Slowly"

                # If perfect_rep was set during UP transition and still no errors, keep it true

                # Otherwise, it stays false or gets reset



        else: # No landmarks detected

            current_error = "Not tracking. Are you in frame?"

            visual_feedback = "Not tracking"

            perfect_rep = False



    except Exception as e: # Catch landmark access errors

        print(f"Landmark error (Barbell Curl): {e}")

        current_error = "Make sure you are fully in frame"

        visual_feedback = "Make sure you are fully in frame"

        perfect_rep = False



    # --- Prepare Response ---

    feedback_data = {

        "reps": rep_counter,

        "error": current_error,

        "adjustment": visual_feedback,

        "perfect_rep": perfect_rep and stage == 'UP' # Only truly perfect on the frame rep completes

    }



    # --- Prepare Updated State ---

    updated_state = {

        'rep_counter': rep_counter,

        'stage': stage,

        'last_rep_time': last_rep_time,

        'last_print_time': last_print_time

    }



    return json.dumps(feedback_data), updated_state