import asyncio
import websockets
import cv2 as cv
import mediapipe as mp
import numpy as np
import json
import base64

# --- Import our new logic modules ---
from shoulder_press_logic import process_shoulder_press
from barbell_curl_logic import process_barbell_curl
from plank_logic import process_plank
from pushups_logic import process_pushups
from squats_logic import process_squats
# --- Add imports for your other exercises here ---
# from plank_logic import process_plank 

# --- MediaPipe Initialization (Global) ---
mpPose = mp.solutions.pose
# Create the pose object ONCE and reuse it
pose = mpPose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6)

# =====================================================================
# --- WebSocket Handler ---
# =====================================================================
async def handler(websocket):
    print(f"Client connected from {websocket.remote_address}")
    
    connection_state = {} # State will be initialized on first message
    frame_processor = None # This will hold the function to call

    try:
        # --- 1. Wait for the FIRST message (Exercise Selection) ---
        message = await websocket.recv()
        data = json.loads(message)
        
        if 'exercise' in data:
            exercise_name = data['exercise'].upper().strip()
            print(f"Client selected exercise: {exercise_name}")
            
            # --- This is the "Router" ---
            if exercise_name == "SHOULDER PRESS":
                frame_processor = process_shoulder_press
                connection_state = {'rep_counter': 0, 'stage': 'DOWN', 'last_print_time': 0}
            elif exercise_name == "BARBELL CURLS":
                frame_processor = process_barbell_curl
                connection_state = {'rep_counter': 0, 'stage': 'DOWN', 'last_rep_time': 0, 'last_print_time': 0}
            elif exercise_name == "PLANK":
                frame_processor = process_plank
                connection_state = {
                    'stage': 'resting', 
                    'start_time': 0, 
                    'pause_start_time': 0, 
                    'total_paused_time': 0,
                    'last_elapsed_time': 0
                }
            elif exercise_name == "PUSHUPS": # (or however it's named in your Flutter menu)
                frame_processor = process_pushups
                connection_state = {
                    'stage': 'UP',
                    'counter': 0,
                    'down_frames': 0,
                    'up_frames': 0,
                    'smoothed_coords': {}
                }
            
            elif exercise_name == "SQUATS": # (or however it's named in your Flutter menu)
                frame_processor = process_squats
                connection_state = {
                    'counter': 0,
                    'stage': 'up'
                }
            else:
                print(f"Unknown exercise: {exercise_name}")
                await websocket.close(reason="Unknown exercise")
                return
        
        if not frame_processor:
             print("No exercise selected by client. Closing connection.")
             await websocket.close(reason="No exercise selected")
             return

        # --- 2. Process Subsequent Frames ---
        async for message in websocket:
            try:
                data = json.loads(message)
                img_data = base64.b64decode(data['frame'])
                width, height, bytes_per_row = data['width'], data['height'], data['bytesPerRow']

                nparr = np.frombuffer(img_data, np.uint8)
                
                required_size = (height - 1) * bytes_per_row + width
                if nparr.size < required_size:
                    print(f"Frame size error! Buffer too small. Expected {required_size}, got {nparr.size}")
                    continue

                img_gray = np.empty((height, width), dtype=np.uint8)
                for i in range(height):
                    row_start = i * bytes_per_row
                    row_end = row_start + width
                    img_gray[i, :] = nparr[row_start:row_end]
                
                img_bgr = cv.cvtColor(img_gray, cv.COLOR_GRAY2BGR)
                imgRGB = cv.cvtColor(img_bgr, cv.COLOR_BGR2RGB)
                
                # Run pose detection
                results = await asyncio.to_thread(pose.process, imgRGB)
                
                # --- 3. Call the SELECTED logic function ---
                # We are passing the *results* and *state*
                response_json, connection_state = frame_processor(results, connection_state)
                
                await websocket.send(response_json)
                
            except json.JSONDecodeError: print("Failed to decode JSON from client")
            except KeyError as e: print(f"Missing key in JSON from client: {e}")
            except Exception as e: print(f"Error processing frame: {e}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Client disconnected: {e.code} {e.reason}")
    except Exception as e:
        print(f"Handler error: {e}")
    finally:
        print(f"Connection closed for {websocket.remote_address}")

# =====================================================================
# --- Main Server Function ---
# =====================================================================
async def main():
    host = "0.0.0.0" # Listen on all network interfaces
    port = 8765
    print(f"Starting MAIN WebSocket server on ws://{host}:{port}")
    
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())