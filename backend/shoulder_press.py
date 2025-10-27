# import cv2 as cv
# import mediapipe as mp
# import numpy as np
# import time
# import pyttsx3
# import threading
# from queue import Queue

# # --- Thread-safe queue for TTS ---
# tts_queue = Queue()

# def tts_worker(engine):
#     """Background thread that handles all TTS calls"""
#     while True:
#         text = tts_queue.get()
#         if text is None:  # Sentinel value to stop thread
#             break
#         try:
#             engine.say(text)
#             engine.runAndWait()
#         except:
#             pass

# # Function to calculate angle
# def calculate_angle(a, b, c):
#     a = np.array(a); b = np.array(b); c = np.array(c)
#     radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
#     angle = np.abs(radians*180.0/np.pi)
#     if angle > 180.0:
#         angle = 360-angle
#     return angle

# # --- Initialize TTS engine and worker thread ---
# tts_engine = pyttsx3.init()
# tts_engine.setProperty('rate', 150)  # Slower speech for clarity
# tts_thread = threading.Thread(target=tts_worker, args=(tts_engine,), daemon=True)
# tts_thread.start()

# mpDraw = mp.solutions.drawing_utils
# mpPose = mp.solutions.pose
# pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# cap = cv.VideoCapture(0)

# # --- State Machine & Rep Counter Variables ---
# rep_counter = 0
# stage = 'DOWN'

# # --- Smart Feedback Variables ---
# persistent_error = None
# error_start_time = None
# last_voice_alert_time = 0

# ERROR_DURATION_THRESHOLD = 2.0  # 2 seconds before voice alert
# VOICE_COOLDOWN = 5.0            # 5 seconds between alerts for SAME error

# # Setup for full screen
# WINDOW_NAME = "Shoulder Press AI Coach"
# cv.namedWindow(WINDOW_NAME, cv.WINDOW_NORMAL)
# cv.setWindowProperty(WINDOW_NAME, cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

# while True:
#     success, img = cap.read()
#     if not success: break
    
#     img = cv.flip(img, 1)
#     imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
#     results = pose.process(imgRGB)
    
#     try:
#         if results.pose_landmarks:
#             landmarks = results.pose_landmarks.landmark
            
#             # Get coordinates
#             rshoulder, relbow, rwrist, rhip = ([landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y])
#             lshoulder, lelbow, lwrist, lhip = ([landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y], 
#                                                [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y])

#             # Calculate angles
#             r_elbow_angle = calculate_angle(rshoulder, relbow, rwrist)
#             l_elbow_angle = calculate_angle(lshoulder, lelbow, lwrist)
#             r_shoulder_angle = calculate_angle(rhip, rshoulder, relbow)
#             l_shoulder_angle = calculate_angle(lhip, lshoulder, lelbow)
#             shoulder_level_diff = abs(rshoulder[1] - lshoulder[1])

#             # State Machine & Rep Counter Logic
#             if r_elbow_angle > 160 and l_elbow_angle > 160 and stage == 'DOWN':
#                 rep_counter += 1
#                 stage = 'UP'
#             elif r_elbow_angle < 90 and l_elbow_angle < 90:
#                 stage = 'DOWN'
            
#             # --- Determine current error ---
#             current_error = None
#             if shoulder_level_diff > 0.05:
#                 current_error = "Keep shoulders level"
#             elif r_shoulder_angle < 70 or l_shoulder_angle < 70:
#                 current_error = "Bring your elbows up"
#             elif (r_elbow_angle > 110 and r_shoulder_angle < 115) or \
#                  (l_elbow_angle > 110 and l_shoulder_angle < 115):
#                 current_error = "Tuck your elbows in"
#             elif r_elbow_angle < 50 or l_elbow_angle < 50:
#                 current_error = "Elbows too close to shoulders"

#             # =====================================================================
#             # --- FIXED VOICE FEEDBACK LOGIC ---
#             # =====================================================================
#             current_time = time.time()
            
#             if current_error:
#                 # If error changed, reset timer
#                 if current_error != persistent_error:
#                     persistent_error = current_error
#                     error_start_time = current_time
                
#                 # Check if error has persisted for 2+ seconds
#                 error_duration = current_time - error_start_time
#                 if error_duration >= ERROR_DURATION_THRESHOLD:
#                     # Check if enough time has passed since last alert for THIS error
#                     if current_time - last_voice_alert_time >= VOICE_COOLDOWN:
#                         tts_queue.put(persistent_error)
#                         last_voice_alert_time = current_time
#             else:
#                 # No current error, reset
#                 persistent_error = None
#                 error_start_time = None

#             # --- Visual Feedback Logic (State-Dependent) ---
#             visual_feedback = "Good Form"
#             if stage == 'DOWN' and current_error:
#                 visual_feedback = current_error
            
#             # --- Drawing and UI ---
#             overlay = img.copy()
#             alpha = 0.6
#             cv.rectangle(overlay, (10, 10), (340, 130), (20, 20, 20), -1)
#             img = cv.addWeighted(overlay, alpha, img, 1 - alpha, 0)
            
#             feedback_color = (0, 255, 0) if visual_feedback == "Good Form" else (0, 0, 255)
#             cv.putText(img, "REPS", (30, 40), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv.LINE_AA)
#             cv.putText(img, str(rep_counter), (35, 85), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv.LINE_AA)
#             cv.putText(img, "STAGE", (130, 40), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv.LINE_AA)
#             cv.putText(img, stage.upper(), (130, 85), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv.LINE_AA)
#             cv.putText(img, "COACH", (30, 120), cv.FONT_HERSHEY_SIMPLEX, 0.7, feedback_color, 2, cv.LINE_AA)
#             cv.putText(img, visual_feedback, (130, 120), cv.FONT_HERSHEY_SIMPLEX, 0.7, feedback_color, 2, cv.LINE_AA)
            
#             mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)
            
#     except Exception as e:
#         pass

#     cv.imshow(WINDOW_NAME, img)5tghnmm
    
#     if cv.waitKey(1) & 0xFF == ord('q'):
#         break

# cap.release()
# cv.destroyAllWindows()
# tts_queue.put(None)  # Signal TTS thread to stop
# tts_thread.join()
# tts_engine.stop()



import asyncio
import websockets
import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import json
import base64

# --- MediaPipe Initialization (Global) ---
mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
# Initialize pose with a higher confidence to filter out noise
pose = mpPose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6)

# --- Angle Calculation Function (Unchanged) ---
def calculate_angle(a, b, c):
    a = np.array(a); b = np.array(b); c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360-angle
    return angle

# =====================================================================
# --- Core Processing Function ---
# This function contains all your logic, refactored from the while loop.
# It's now 'async' and uses 'asyncio.to_thread' to run the
# heavy MediaPipe processing without blocking the server.
# =====================================================================
async def process_frame(img, state):
    """
    Processes a single image frame and returns feedback and updated state.
    'state' is a dictionary holding per-connection variables like 'rep_counter'.
    """
    
    # --- Unpack state variables ---
    rep_counter = state.get('rep_counter', 0)
    stage = state.get('stage', 'DOWN')
    last_print_time = state.get('last_print_time', 0)
    # Feedback/Error variables
    current_error = None
    visual_feedback = "Good Form"
    perfect_rep = False

    try:
        # --- Image Processing ---
        # Flip the image (phones often send mirrored front-camera video)
        # img = cv.flip(img, 1)
        # Convert to RGB for MediaPipe
        imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        
        # Run MediaPipe processing in a separate thread
        results = await asyncio.to_thread(pose.process, imgRGB)
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- Get coordinates (Unchanged) ---
            rshoulder, relbow, rwrist, rhip = ([landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y], 
                                                [landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y], 
                                                [landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y], 
                                                [landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mpPose.PoseLandmark.RIGHT_HIP.value].y])
            lshoulder, lelbow, lwrist, lhip = ([landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y], 
                                                [landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y], 
                                                [landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y], 
                                                [landmarks[mpPose.PoseLandmark.LEFT_HIP.value].x, landmarks[mpPose.PoseLandmark.LEFT_HIP.value].y])

            # --- Calculate angles (Unchanged) ---
            r_elbow_angle = calculate_angle(rshoulder, relbow, rwrist)
            l_elbow_angle = calculate_angle(lshoulder, lelbow, lwrist)
            r_shoulder_angle = calculate_angle(rhip, rshoulder, relbow)
            l_shoulder_angle = calculate_angle(lhip, lshoulder, lelbow)
            shoulder_level_diff = abs(rshoulder[1] - lshoulder[1])

            current_time = time.time()
            if (current_time - last_print_time) > 2.0: # 2.0 seconds
                print(f"Shoulder Diff: {shoulder_level_diff:.4f}")
                last_print_time = current_time  # Update the time
            # --- State Machine & Rep Counter Logic (Unchanged) ---
            if r_elbow_angle > 160 and l_elbow_angle > 160 and stage == 'DOWN':
                rep_counter += 1
                stage = 'UP'
                # We only set perfect_rep to True on the frame a rep is completed
                perfect_rep = True 
            elif r_elbow_angle < 90 and l_elbow_angle < 90:
                stage = 'DOWN'
            
            # --- Error Detection Logic (Unchanged) ---
            if shoulder_level_diff > 0.05:
                current_error = "Keep shoulders level"
            elif r_shoulder_angle < 70 or l_shoulder_angle < 70:
                current_error = "Bring your elbows up"
            elif (r_elbow_angle > 110 and r_shoulder_angle < 115) or \
                 (l_elbow_angle > 110 and l_shoulder_angle < 115):
                current_error = "Tuck your elbows in"
            elif r_elbow_angle < 50 or l_elbow_angle < 50:
                current_error = "Elbows too close to shoulders"

            # --- Visual Feedback Logic (Slightly modified) ---
            if current_error:
                visual_feedback = current_error
                perfect_rep = False # An error invalidates a perfect rep
            else:
                visual_feedback = "Good Form"

    except Exception as e:
        print(f"Error during pose processing: {e}")
        visual_feedback = "Tracking error. Reposition."

    # --- Prepare Response ---
    # We map our Python variables to the JSON structure your Flutter app expects
    feedback_data = {
        "reps": rep_counter,
        "error": current_error if current_error else "",
        "adjustment": visual_feedback,
        "perfect_rep": perfect_rep
    }

    # --- Prepare Updated State ---
    # This dictionary is passed back to the handler and saved
    # for the *next* frame from this specific client
    updated_state = {
        'rep_counter': rep_counter,
        'stage': stage
    }

    return json.dumps(feedback_data), updated_state

# =====================================================================
# --- WebSocket Handler ---
# This function manages individual client connections
# =====================================================================
async def handler(websocket):
    print(f"Client connected from {websocket.remote_address}")
    
    # This state is unique to each connection
    connection_state = {
        'rep_counter': 0,
        'stage': 'DOWN'
    }

    try:
        # Loop that waits for messages from a single client
        async for message in websocket:
            # print("Received a frame from client!")
            # --- 1. Receive and Decode Frame ---
            # The message is JSON: {"frame": "base64...", "width": w, "height": h}
            data = json.loads(message)
            img_data = base64.b64decode(data['frame'])
            width = data['width']
            height = data['height']
            bytes_per_row = data['bytesPerRow']

            # Convert 1D byte buffer to 2D numpy array (grayscale)
            nparr = np.frombuffer(img_data, np.uint8)
            
            # Check for data corruption
          # Check if the buffer is at least large enough for the *useful* data.
                # The last pixel is at (height - 1) * stride + (width - 1).
            required_size = (height - 1) * bytes_per_row + width
            if nparr.size < required_size:
                print(f"Frame size error! Buffer is too small. Expected at least {required_size}, got {nparr.size}")
                continue
                
                # We can't use a simple reshape. We must manually 
                # reconstruct the image, stripping the padding from each row.

                # Create the destination array (unpadded)
            img_gray = np.empty((height, width), dtype=np.uint8)
                
                # Copy row by row, taking only 'width' bytes from each 'bytes_per_row' chunk
            for i in range(height):
                    row_start = i * bytes_per_row
                    row_end = row_start + width
                    img_gray[i, :] = nparr[row_start:row_end]
            
            # Convert grayscale to 3-channel BGR (which MediaPipe needs)
            img_bgr = cv.cvtColor(img_gray, cv.COLOR_GRAY2BGR)
            
            # --- 2. Process Frame ---
            response_json, connection_state = await process_frame(img_bgr, connection_state)
            
            # --- 3. Send Feedback ---
            await websocket.send(response_json)
            
    except json.JSONDecodeError:
                print("Failed to decode JSON from client")
    except KeyError as e:
                print(f"Missing key in JSON from client: {e}")
    except Exception as e:
                print(f"Error in handler loop: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Client disconnected: {e}")
    except Exception as e:
        print(f"An error occurred with client: {e}")
    finally:
        print("Connection closed.")



# =====================================================================
# --- Main Server Function ---
# =====================================================================
async def main():
    host = "0.0.0.0" # Listen on all network interfaces
    port = 8765
    print(f"Starting WebSocket server on ws://{host}:{port}")
    
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    # Install dependencies with:
    # pip install websockets opencv-python mediapipe numpy
    asyncio.run(main())