import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import threading
import queue
import logging
import sys
import json

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Text-to-Speech (engine runs in background thread)
engine = pyttsx3.init()
tts_queue = queue.Queue()

def _tts_worker(q, engine):
    while True:
        text = q.get()
        if text is None:
            break
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            logging.exception('TTS failed')

threading.Thread(target=_tts_worker, args=(tts_queue, engine), daemon=True).start()

def calculate_angle(a, b, c):
    a = np.array(a); b = np.array(b); c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

mpDraw = mp.solutions.drawing_utils
mpPose = mp.solutions.pose
pose = mpPose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv.VideoCapture(0)
if not cap.isOpened():
    logging.error('Camera not available. Check camera connection and permissions.')
    sys.exit(1)

# State
stage = None
counter = 0

# Debounce counters
down_frames = 0
up_frames = 0
MIN_CONSECUTIVE = 3

# Visibility threshold
VIS_THRESHOLD = 0.5

# TTS cooldown to avoid spam (seconds)
last_spoken = 0
TTS_COOLDOWN = 1.0

# Algorithm thresholds (tune these if detection seems off)
DEBUG_ANGLES = True  # show measured angles on-screen for debugging

# Angle thresholds (degrees)
ELBOW_DOWN_THRESHOLD = 90
ELBOW_UP_THRESHOLD = 160
BODY_ANGLE_MIN = 150
KNEE_ANGLE_MIN = 160
ELBOW_TORSO_FLARE = 100
ELBOW_TORSO_TUCK = 50
NOT_LOW_ENOUGH_ELBOW = 110

# Smoothing
SMOOTHING_ALPHA = 0.5  # EMA alpha (0..1), lower = smoother

# Calibration
CALIBRATE_ON_START = False
CALIBRATION_CAPTURE_SECS = 3
CONFIG_FILE = 'pushups_config.json'

# Runtime smoothing storage
smoothed_coords = {}

# Calibration runtime state
calibrating = False
calib_stage = 0
calib_start_time = 0.0
calib_top_body = []
calib_top_knee = []
calib_bottom_body = []
calib_bottom_knee = []
calib_top_elbow = []
calib_bottom_elbow = []

# Persistent feedback: if same feedback persists this many seconds, force voice
FEEDBACK_PERSISTENCE_SECONDS = 4.0
# When persistent feedback is spoken, repeat interval (seconds)
PERSISTENT_TTS_REPEAT = 4.0

# Runtime state for persistent feedback
persistent_last_feedback = None
persistent_feedback_start = 0.0
persistent_last_spoken = 0.0

logging.info('Starting Push-up Counter')

def load_config(path=CONFIG_FILE):
    try:
        with open(path, 'r') as f:
            cfg = json.load(f)
            logging.info('Loaded config %s', path)
            return cfg
    except Exception:
        return None

def save_config(cfg, path=CONFIG_FILE):
    try:
        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2)
            logging.info('Saved config to %s', path)
    except Exception:
        logging.exception('Failed to save config')

# Try load existing config
cfg = load_config() or {}
ELBOW_DOWN_THRESHOLD = cfg.get('ELBOW_DOWN_THRESHOLD', ELBOW_DOWN_THRESHOLD)
ELBOW_UP_THRESHOLD = cfg.get('ELBOW_UP_THRESHOLD', ELBOW_UP_THRESHOLD)
BODY_ANGLE_MIN = cfg.get('BODY_ANGLE_MIN', BODY_ANGLE_MIN)
KNEE_ANGLE_MIN = cfg.get('KNEE_ANGLE_MIN', KNEE_ANGLE_MIN)
ELBOW_TORSO_FLARE = cfg.get('ELBOW_TORSO_FLARE', ELBOW_TORSO_FLARE)
ELBOW_TORSO_TUCK = cfg.get('ELBOW_TORSO_TUCK', ELBOW_TORSO_TUCK)
NOT_LOW_ENOUGH_ELBOW = cfg.get('NOT_LOW_ENOUGH_ELBOW', NOT_LOW_ENOUGH_ELBOW)


try:
    while True:
        success, img = cap.read()
        if not success:
            logging.warning('Failed to read from camera frame')
            break

        img = cv.flip(img, 1)
        imgRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        results = pose.process(imgRGB)

        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Decide dominant side by shoulder visibility
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

                # check visibility for key landmarks
                vis_ok = True
                coords = {}
                for name, idx in idxs.items():
                    lm = landmarks[idx]
                    if lm.visibility < VIS_THRESHOLD:
                        vis_ok = False
                        break
                    coords[name] = [lm.x, lm.y]

                feedback_text = None
                feedback_color = (0, 255, 0)

                if not vis_ok:
                    # skip unreliable frame
                    down_frames = up_frames = 0
                    feedback_text = 'Come closer / step into frame'
                    feedback_color = (0, 0, 255)
                else:
                    shoulder = coords['shoulder']
                    elbow = coords['elbow']
                    wrist = coords['wrist']
                    hip = coords['hip']
                    ankle = coords['ankle']

                    # initialize smoothed coords if missing
                    for k, v in coords.items():
                        if k not in smoothed_coords:
                            smoothed_coords[k] = v.copy()
                        else:
                            smoothed_coords[k][0] = SMOOTHING_ALPHA * v[0] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][0]
                            smoothed_coords[k][1] = SMOOTHING_ALPHA * v[1] + (1-SMOOTHING_ALPHA) * smoothed_coords[k][1]

                    # use smoothed coords for calculations
                    shoulder = smoothed_coords['shoulder']
                    elbow = smoothed_coords['elbow']
                    wrist = smoothed_coords['wrist']
                    hip = smoothed_coords['hip']
                    ankle = smoothed_coords['ankle']
                    knee = smoothed_coords['knee']

                    elbow_angle = calculate_angle(shoulder, elbow, wrist)
                    # angle between shoulder-elbow-hip (how flared the elbow is)
                    elbow_torso_angle = calculate_angle(shoulder, elbow, hip)
                    knee = coords['knee']
                    knee_angle = calculate_angle(hip, knee, ankle)
                    body_angle = calculate_angle(shoulder, hip, ankle)

                    # Debounce logic
                    if elbow_angle < ELBOW_DOWN_THRESHOLD:
                        down_frames += 1
                        up_frames = 0
                    elif elbow_angle > ELBOW_UP_THRESHOLD:
                        up_frames += 1
                        down_frames = 0
                    else:
                        down_frames = max(0, down_frames - 1)
                        up_frames = max(0, up_frames - 1)

                    # state transitions
                    now = time.time()
                    if down_frames >= MIN_CONSECUTIVE and stage != 'down':
                        stage = 'down'
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put('Down')
                            last_spoken = now

                    if up_frames >= MIN_CONSECUTIVE and stage == 'down':
                        # ensure good form before counting
                        form_ok = (body_angle >= BODY_ANGLE_MIN) and (knee_angle >= KNEE_ANGLE_MIN)
                        stage = 'up'
                        if form_ok:
                            counter += 1
                            feedback_text = f'Good rep {counter}'
                            feedback_color = (0, 200, 0)
                            if now - last_spoken > TTS_COOLDOWN:
                                tts_queue.put(f'Good rep {counter}')
                                last_spoken = now
                        else:
                            # do not count rep; give actionable feedback
                            if knee_angle < KNEE_ANGLE_MIN:
                                feedback_text = 'Straighten your legs'
                                feedback_color = (0, 0, 255)
                                if now - last_spoken > TTS_COOLDOWN:
                                    tts_queue.put('Straighten your legs')
                                    last_spoken = now
                            elif body_angle < BODY_ANGLE_MIN:
                                feedback_text = 'Keep your body straight'
                                feedback_color = (0, 165, 255)
                                if now - last_spoken > TTS_COOLDOWN:
                                    tts_queue.put('Keep your body straight')
                                    last_spoken = now

                    # Form feedback and wrong-form detection
                    # body_angle low -> sagging hips
                    if body_angle < BODY_ANGLE_MIN and (feedback_text is None):
                        feedback_text = 'Keep your body straight'
                        feedback_color = (0, 165, 255)
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put('Keep your body straight')
                            last_spoken = now

                    # Knee bent -> legs not straight
                    if knee_angle < KNEE_ANGLE_MIN and (feedback_text is None):
                        feedback_text = 'Straighten your legs'
                        feedback_color = (0, 0, 255)
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put('Straighten your legs')
                            last_spoken = now

                    # Elbow flare / tuck checks (evaluate during down position / general)
                    # Larger elbow_torso_angle -> elbow flared outwards; small -> tucked.
                    if (down_frames >= 1 or stage == 'down') and (feedback_text is None):
                        if elbow_torso_angle > ELBOW_TORSO_FLARE:
                            feedback_text = "Don't flare your elbows"
                            feedback_color = (0, 0, 255)
                            if now - last_spoken > TTS_COOLDOWN:
                                tts_queue.put("Don't flare your elbows")
                                last_spoken = now
                        elif elbow_torso_angle < ELBOW_TORSO_TUCK:
                            feedback_text = 'Tuck your elbows closer to your body'
                            feedback_color = (0, 165, 255)
                            if now - last_spoken > TTS_COOLDOWN:
                                tts_queue.put('Tuck your elbows closer')
                                last_spoken = now

                    # Not lowering enough: stuck in up stage without down frames
                    if stage == 'up' and down_frames == 0 and elbow_angle > NOT_LOW_ENOUGH_ELBOW and (feedback_text is None):
                        # user isn't going low enough
                        feedback_text = 'Go lower: lower your chest toward the floor'
                        feedback_color = (0, 0, 255)
                        if now - last_spoken > TTS_COOLDOWN:
                            tts_queue.put('Go lower')
                            last_spoken = now

                # Draw UI
                h, w, _ = img.shape
                cv.rectangle(img, (10,10), (w-10,140), (0,0,0), cv.FILLED)
                cv.putText(img, 'PUSH-UP COUNTER', (20,45), cv.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
                cv.putText(img, f'REPS: {counter}', (20,95), cv.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)
                cv.putText(img, f'STAGE: {stage or "-"}', (280,95), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

                # Feedback bar (always shown when set)
                if feedback_text:
                    # draw a filled rectangle for feedback
                    cv.rectangle(img, (10, h-70), (w-10, h-10), feedback_color, cv.FILLED)
                    cv.putText(img, feedback_text, (20, h-30), cv.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)

                # Persistent feedback handling: if same feedback persists seconds, force voice
                now = time.time()
                if feedback_text:
                    if feedback_text == persistent_last_feedback:
                        # still the same feedback
                        if persistent_feedback_start == 0.0:
                            persistent_feedback_start = now
                        elapsed_persist = now - persistent_feedback_start
                        # Speak if held long enough and cooldown since last persistent speak
                        if elapsed_persist >= FEEDBACK_PERSISTENCE_SECONDS and (now - persistent_last_spoken) >= PERSISTENT_TTS_REPEAT:
                            tts_queue.put(feedback_text)
                            persistent_last_spoken = now
                    else:
                        # new feedback started
                        persistent_last_feedback = feedback_text
                        persistent_feedback_start = now
                        persistent_last_spoken = 0.0
                else:
                    persistent_last_feedback = None
                    persistent_feedback_start = 0.0
                    persistent_last_spoken = 0.0

                # Debug overlay: show measured angles and visibility
                if DEBUG_ANGLES and vis_ok:
                    debug_x = w - 280
                    debug_y = 30
                    cv.putText(img, f'elbow: {int(elbow_angle)}', (debug_x, debug_y), cv.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                    cv.putText(img, f'body: {int(body_angle)}', (debug_x, debug_y+20), cv.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                    cv.putText(img, f'knee: {int(knee_angle)}', (debug_x, debug_y+40), cv.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                    cv.putText(img, f'elbow_torso: {int(elbow_torso_angle)}', (debug_x, debug_y+60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                    # show visibilities for shoulder/elbow/wrist (approx) - use direct landmark values
                    shoulder_vis = int(landmarks[idxs['shoulder']].visibility*100)
                    elbow_vis = int(landmarks[idxs['elbow']].visibility*100)
                    wrist_vis = int(landmarks[idxs['wrist']].visibility*100)
                    cv.putText(img, f'vis S/E/W: {shoulder_vis}/{elbow_vis}/{wrist_vis}%', (debug_x, debug_y+85), cv.FONT_HERSHEY_SIMPLEX, 0.5, (180,180,180), 1)

                # Calibration handling: press 'c' to start a 3s capture for top/bottom
                if cv.waitKey(1) & 0xFF == ord('c'):
                    calibrating = True
                    calib_stage = 0
                    calib_start_time = time.time()
                    calib_top_body.clear(); calib_top_knee.clear(); calib_bottom_body.clear(); calib_bottom_knee.clear()
                    logging.info('Calibration started: follow on-screen prompts')

                if calibrating and vis_ok:
                    # stage 0: capture top posture for CALIBRATION_CAPTURE_SECS
                    tnow = time.time()
                    if calib_stage == 0:
                        cv.putText(img, 'Calibration: hold TOP position', (20, h-100), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
                        calib_top_body.append(body_angle); calib_top_knee.append(knee_angle); calib_top_elbow.append(elbow_torso_angle)
                        if tnow - calib_start_time > CALIBRATION_CAPTURE_SECS:
                            calib_stage = 1; calib_start_time = tnow
                    elif calib_stage == 1:
                        cv.putText(img, 'Calibration: hold BOTTOM position', (20, h-100), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
                        calib_bottom_body.append(body_angle); calib_bottom_knee.append(knee_angle); calib_bottom_elbow.append(elbow_torso_angle)
                        if tnow - calib_start_time > CALIBRATION_CAPTURE_SECS:
                            # finalize calibration
                            avg_top_body = np.mean(calib_top_body) if calib_top_body else BODY_ANGLE_MIN
                            avg_top_knee = np.mean(calib_top_knee) if calib_top_knee else KNEE_ANGLE_MIN
                            avg_bottom_body = np.mean(calib_bottom_body) if calib_bottom_body else BODY_ANGLE_MIN
                            avg_bottom_knee = np.mean(calib_bottom_knee) if calib_bottom_knee else KNEE_ANGLE_MIN
                            avg_top_elbow = np.mean(calib_top_elbow) if calib_top_elbow else ELBOW_TORSO_FLARE
                            avg_bottom_elbow = np.mean(calib_bottom_elbow) if calib_bottom_elbow else ELBOW_TORSO_TUCK
                            # set thresholds conservatively between top and bottom
                            BODY_ANGLE_MIN = min(avg_top_body, avg_bottom_body) * 0.95
                            KNEE_ANGLE_MIN = min(avg_top_knee, avg_bottom_knee) * 0.95
                            # elbow torso thresholds: flare threshold slightly above max observed, tuck slightly below min
                            ELBOW_TORSO_FLARE = max(avg_top_elbow, avg_bottom_elbow) * 1.05
                            ELBOW_TORSO_TUCK = min(avg_top_elbow, avg_bottom_elbow) * 0.95
                            # save
                            cfg_update = {
                                'BODY_ANGLE_MIN': BODY_ANGLE_MIN,
                                'KNEE_ANGLE_MIN': KNEE_ANGLE_MIN,
                                'ELBOW_TORSO_FLARE': ELBOW_TORSO_FLARE,
                                'ELBOW_TORSO_TUCK': ELBOW_TORSO_TUCK
                            }
                            save_config(cfg_update)
                            calibrating = False
                            logging.info('Calibration complete. New BODY_ANGLE_MIN=%.1f KNEE_ANGLE_MIN=%.1f', BODY_ANGLE_MIN, KNEE_ANGLE_MIN)

                mpDraw.draw_landmarks(img, results.pose_landmarks, mpPose.POSE_CONNECTIONS)

        except Exception as e:
            logging.exception('Processing frame failed: %s', e)

        cv.imshow('Push-up Counter', img)
        if cv.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    # Clean up
    try:
        tts_queue.put(None)
    except Exception:
        pass
    cap.release()
    cv.destroyAllWindows()

