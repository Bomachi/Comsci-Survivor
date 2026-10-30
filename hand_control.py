"""Hand control: steer the player with one hand in front of the webcam.

    open hand   -> walk; the palm's offset from the centre of the camera image
                   is a virtual joystick (further = faster, up to full speed)
    fist        -> stop
    F8          -> re-centre the joystick on where your hand is now

Pipeline (background thread, so the game loop never waits for the camera):
    webcam (OpenCV) -> mirror + downscale -> MediaPipe HandLandmarker (21
    landmarks per hand, VIDEO mode) -> palm centre and fist test -> smoothed
    analog direction that Game reads every frame.

Optional feature: needs `pip install -r requirements-hand.txt` and the model
file assets/models/hand_landmarker.task (install_hand.bat downloads both).
"""
import math
import os
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "assets", "models", "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")

PALM = (0, 5, 9, 13, 17)                  # wrist + finger bases
FINGERS = ((8, 6), (12, 10), (16, 14), (20, 18))   # (tip, middle joint) for 4 fingers
DEAD_ZONE = 0.06                           # in image fractions: hand this close to centre = stand still
FULL_SPEED = 0.22                          # offset that reaches full speed
LOST_TIMEOUT = 0.35                        # stop if the hand disappears for this long
PREVIEW_SIZE = (192, 144)


def palm_center(landmarks):
    xs = [landmarks[i][0] for i in PALM]
    ys = [landmarks[i][1] for i in PALM]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def is_fist(landmarks):
    """A finger is folded when its tip is closer to the wrist than its middle joint."""
    wx, wy = landmarks[0]
    folded = 0
    for tip, joint in FINGERS:
        tip_d = math.hypot(landmarks[tip][0] - wx, landmarks[tip][1] - wy)
        joint_d = math.hypot(landmarks[joint][0] - wx, landmarks[joint][1] - wy)
        if tip_d < joint_d:
            folded += 1
    return folded >= 3


def joystick(point, anchor, dead_zone=DEAD_ZONE, full=FULL_SPEED):
    """Map a palm position to a direction vector with length 0..1 (analog speed)."""
    dx, dy = point[0] - anchor[0], point[1] - anchor[1]
    dist = math.hypot(dx, dy)
    if dist <= dead_zone:
        return (0.0, 0.0)
    strength = min(1.0, (dist - dead_zone) / (full - dead_zone))
    return (dx / dist * strength, dy / dist * strength)


class HandController:
    """Owns the camera thread. Call poll() every frame from the game loop."""

    def __init__(self, camera_index=0, detector=None):
        self.camera_index = camera_index
        self.detector = detector          # tests inject a fake: callable(rgb, ms) -> landmarks or None
        self.status = "off"               # off, loading, tracking, no hand, error
        self.error = ""
        self.anchor = (0.5, 0.5)
        self.direction = (0.0, 0.0)
        self.landmarks = None
        self.fist = False
        self.fps = 0.0
        self.preview = None               # small RGB numpy array for the HUD
        self._smoothed = None
        self._last_seen = 0.0
        self._recenter = False
        self._running = False
        self._landmarker = None
        self._lock = threading.Lock()

    # ----- game API -----
    def toggle(self):
        if self.status in ("off", "error"):
            self.start()
        else:
            self.stop()

    def start(self):
        self.status, self.error = "loading", ""
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False
        self.status = "off"
        self.direction = (0.0, 0.0)
        self.landmarks = None

    def recenter(self):
        self._recenter = True

    def poll(self):
        with self._lock:
            if self.status == "tracking" and time.perf_counter() - self._last_seen > LOST_TIMEOUT:
                self.status, self.direction, self.landmarks = "no hand", (0.0, 0.0), None
            return self.direction

    # ----- per-frame logic (pure, unit-tested) -----
    def process(self, landmarks, now):
        """Update state from one frame's landmarks (list of (x, y) in 0..1) or None."""
        with self._lock:
            if not landmarks:
                if now - self._last_seen > LOST_TIMEOUT:
                    self.status, self.direction, self.landmarks = "no hand", (0.0, 0.0), None
                return self.direction
            self._last_seen = now
            self.status = "tracking"
            self.landmarks = landmarks
            center = palm_center(landmarks)
            if self._recenter:
                self.anchor, self._recenter = center, False
            # Exponential smoothing removes camera jitter (about 2 frames of lag).
            if self._smoothed is None:
                self._smoothed = center
            else:
                self._smoothed = (self._smoothed[0] * 0.5 + center[0] * 0.5,
                                  self._smoothed[1] * 0.5 + center[1] * 0.5)
            self.fist = is_fist(landmarks)
            self.direction = (0.0, 0.0) if self.fist else joystick(self._smoothed, self.anchor)
            return self.direction

    # ----- camera thread -----
    def _load_detector(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError("hand model missing: run install_hand.bat")
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5)
        landmarker = vision.HandLandmarker.create_from_options(options)
        self._landmarker = landmarker

        def detect(rgb, timestamp_ms):
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, timestamp_ms)
            if not result.hand_landmarks:
                return None
            return [(p.x, p.y) for p in result.hand_landmarks[0]]
        return detect

    def _run(self):
        try:
            import cv2
            if self.detector is None:
                self.detector = self._load_detector()
            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cam = cv2.VideoCapture(self.camera_index, backend)
            if not cam.isOpened():
                raise RuntimeError("no camera found")
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except Exception as exc:
            self.status, self.error = "error", f"{type(exc).__name__}: {exc}"[:120]
            self._running = False
            return
        self.status = "no hand"
        start = time.perf_counter()
        last_ms, frames, fps_t = -1, 0, start
        try:
            while self._running:
                ok, frame = cam.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                frame = cv2.flip(frame, 1)                      # mirror: move hand right -> go right
                small = cv2.resize(frame, (320, 240))
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                now = time.perf_counter()
                ms = max(last_ms + 1, int((now - start) * 1000))  # strictly increasing timestamps
                last_ms = ms
                self.process(self.detector(rgb, ms), now)
                self.preview = cv2.resize(rgb, PREVIEW_SIZE)
                frames += 1
                if now - fps_t >= 1.0:
                    self.fps, frames, fps_t = frames / (now - fps_t), 0, now
        except Exception as exc:
            self.status, self.error = "error", f"{type(exc).__name__}: {exc}"[:120]
        finally:
            cam.release()
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception:
                    pass
                self._landmarker = None
                self.detector = None
            self._running = False
            if self.status != "error":
                self.status = "off"
