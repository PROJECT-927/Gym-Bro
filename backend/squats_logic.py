import asyncio
import mediapipe as mp
import numpy as np
import json
from utils import calculate_angle # Import from utils.py

# --- MediaPipe Initialization (Global for this module) ---
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

async def process_squats(img, state):
    """
    Processes a single image frame for Squats and returns feedback.
    """
    
    # --- Unpack state variables ---
    counter = state.get('counter', 0) 
    stage = state.get('stage', 'up')
    
    # --- Frame variables ---
    errors = []
    visual_feedback = "Good Form"
    perfect_rep = False
    current_error = ""

    try:
        # --- Image Processing ---
        # Image is already BGR, convert to RGB for MediaPipe
        imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        results = await asyncio.to_thread(pose.process, imgRGB)
        
        # --- Crash-Proof Landmark Access ---
        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # --- Automatic Side Detection (Left vs Right) ---
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

                # --- Form Analysis & Feedback (Prioritized) ---
                # Check for "Knees Past Toes" - compare x-coordinates
                if knee[0] > toe[0] + 0.05: # 0.05 is a buffer
                    errors.append("Knees past toes!")
                # Check for "Back Straightness" - torso angle
                elif torso_angle < 70:
                    errors.append("Keep your chest up!")

                # --- Repetition Counting Logic ---
                if knee_angle < 100 and hip_angle < 100:
                    stage = "down"
                
                if knee_angle > 160 and hip_angle > 160 and stage == 'down':
                    stage = "up"
                    counter += 1
                    if not errors: # Only a perfect rep if no errors
                        perfect_rep = True

                # --- Select the single highest-priority error ---
                if errors:
                    current_error = errors[0]
                    visual_feedback = current_error
                    perfect_rep = False
                else:
                    if stage == 'up':
                        visual_feedback = "Squat Down"
                    elif stage == 'down':
                        visual_feedback = "Stand Up"
                    
                    if perfect_rep: # This gets set on the "up" motion
                         visual_feedback = "Rep Counted!"
                         
            else: # No landmarks detected
                current_error = "Not tracking. Are you in frame?"
                visual_feedback = "Not tracking"
                perfect_rep = False

        except Exception as e: # Catch landmark access errors
            print(f"Landmark error (Squats): {e}")
            current_error = "Make sure you are fully in frame"
            visual_feedback = "Make sure you are fully in frame"
            perfect_rep = False

    except Exception as e: # Catch other processing errors
        print(f"Outer processing error (Squats): {e}")
        visual_feedback = "Tracking error"
        current_error = "Tracking error"
        perfect_rep = False

    # --- Prepare Response ---
    feedback_data = {
        "reps": counter,
        "error": current_error,
        "adjustment": visual_feedback,
        "perfect_rep": perfect_rep
    }

    # --- Prepare Updated State ---
    updated_state = {
        'counter': counter,
        'stage': stage
    }

    return json.dumps(feedback_data), updated_state