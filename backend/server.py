import asyncio
import websockets
import cv2 as cv
import mediapipe as mp
import numpy as np
import json
import base64
import traceback

# --- Import our new logic modules ---
from shoulder_press_logic import process_shoulder_press
from barbell_curl_logic import process_barbell_curl
from plank_logic import process_plank
from pushups_logic import process_pushups
from squats_logic import process_squats

# --- MediaPipe Initialization (Global) ---
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6)

# =====================================================================
# --- WebSocket Handler ---
# =====================================================================
async def handler(websocket):
    print(f"Client connected from {websocket.remote_address}")

    connection_state = {}
    frame_processor = None

    try:
        # --- 1. Wait for the FIRST message (Exercise Selection) ---
        message = await websocket.recv()
        data = json.loads(message)

        if 'exercise' in data:
            exercise_name = data['exercise'].upper().strip()
            print(f"Client selected exercise: {exercise_name}")

            # --- Router Logic ---
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
            elif exercise_name == "PUSHUPS":
                frame_processor = process_pushups
                connection_state = {
                    'stage': 'UP',
                    'counter': 0,
                    'down_frames': 0,
                    'up_frames': 0,
                    'smoothed_coords': {}
                }
            elif exercise_name == "SQUATS":
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

        # --- 2. Process Subsequent Frames (Video Stream) ---
        async for message in websocket:
            try:
                # A. Parse JSON
                data = json.loads(message)

                # B. Get Base64 string
                b64_string = data.get('frame')
                if not b64_string:
                    continue

                # C. Decode Base64 -> Bytes -> Numpy Array
                img_data = base64.b64decode(b64_string)
                nparr = np.frombuffer(img_data, np.uint8)

                # D. Decode JPEG -> OpenCV Image (Fixes the crash)
                img_bgr = cv.imdecode(nparr, cv.IMREAD_COLOR)

                if img_bgr is None:
                    print("Error: Failed to decode image frame")
                    continue

                # E. Convert BGR to RGB for MediaPipe
                imgRGB = cv.cvtColor(img_bgr, cv.COLOR_BGR2RGB)

                # F. Run Pose Detection (in a thread to allow other clients)
                results = await asyncio.to_thread(pose.process, imgRGB)

                # G. Run Exercise Logic
                response_json, connection_state = frame_processor(results, connection_state)

                # H. Send Feedback
                await websocket.send(response_json)

            except json.JSONDecodeError:
                print("Failed to decode JSON from client")
            except Exception as e:
                print(f"Error processing frame: {e}")
                # traceback.print_exc()

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Client disconnected: {e.code} {e.reason}")
    except Exception as e:
        print(f"Handler error: {e}")
        traceback.print_exc()
    finally:
        print(f"Connection closed for {websocket.remote_address}")

# =====================================================================
# --- Main Server Function ---
# =====================================================================
async def main():
    host = "0.0.0.0"
    port = 8765
    print(f"Starting MAIN WebSocket server on ws://{host}:{port}")

    # max_size=None fixes the "Message too big" crash
    async with websockets.serve(handler, host, port, max_size=None):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())