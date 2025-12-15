import cv2
import time
import torch
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from boxmot import StrongSort
import queue
import threading
import time
from collections import defaultdict
# Fix for NumPy deprecation
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int

class VideoLoader:
    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise IOError(f"❌ Could not open video source: {source}")
        if isinstance(source, int):
            print(f"📷 Webcam {source} activated")
        elif source.startswith("http://") or source.startswith("rtsp://"):
            print(f"🌐 IP Camera connected: {source}")
        else:
            print(f"📼 Loaded video file: {source}")

    def read_frame(self):
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        self.cap.release()

class YOLODetector:
    def __init__(self, Model_path, confidence=0.1):
        self.model = YOLO(Model_path)
        self.confidence = confidence
        print("✅ YOLO model loaded")
        self.person_class_ids = [
            class_id for class_id, name in self.model.names.items()
            if name.lower() == "person"
        ]
        self.selected_class_ids = set([0]) 
    
    def update_selected_classes(self, class_ids):
        self.selected_class_ids = set(class_ids)
        print(f"🔹 YOLODetector received selected class IDs: {self.selected_class_ids}")
    
    def predict(self, frame):
        return self.model.predict(frame, conf=self.confidence) 

class ObjectTracker:
    def __init__(self):
        self.tracker = StrongSort(
            reid_weights=Path("osnet_ain_x1_0_market1501_256x128_amsgrad_ep100_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"),
            device="cpu",
            half=False
        )

    def track(self, detections, frame):
        return self.tracker.update(detections, frame)

class FPSCounter:
    def __init__(self):
        self.prev_time = time.time()

    def update(self):
        current_time = time.time()
        fps = 1 / (current_time - self.prev_time)
        self.prev_time = current_time
        return fps

class Main_App:
    def __init__(self, Video_path, Model_path, QueueSize):
        self.Video = VideoLoader(Video_path)
        self.Detector = YOLODetector(Model_path)
        self.Tracker = ObjectTracker()
        self.FPS_Counter = FPSCounter()
        self.Frame_Count = 0
        self.running = True
        self.frame_queue = queue.Queue(maxsize=QueueSize)
        self.det_queue = queue.Queue(maxsize=QueueSize)
        self.track_queue = queue.Queue(maxsize=QueueSize)
        # Mode: detection or tracking (tracking implies detection)
        self.Mode = None
        self.mode_lock = threading.Lock()
        # frontend can assign a function to receive frames
        self.frame_callback = None  
         # <--- ADD THIS
        self.log_callback = None
        self.log_interval = 10  # seconds
        self.last_log_time = time.time()
        self.log_counts = defaultdict(int)  # count of each detected item in interval
   
    def set_mode(self, mode):
        with self.mode_lock:
            if mode not in ["detection", "tracking", "idle"]:
                print(f"❌ Invalid mode: {mode}")
                return
            
            if mode == "full_monitor":
                # Full monitor implies tracking + detection
                self.Mode = "tracking"
                print("🔄 Mode changed to: tracking (full monitor)")
            else:
                self.Mode = mode
                print(f"🔄 Mode changed to: {self.Mode}")

    def VideoFrameReader(self):
        while self.running:
            ret, frame = self.Video.read_frame()
            if not ret:
                self.running = False
                self.frame_queue.put(None)
                break
            self.frame_queue.put(frame)
    
    def ObjectDetection(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except queue.Empty:
                continue
            if frame is None:
                self.det_queue.put(None)
                break

            with self.mode_lock:
                current_mode = self.Mode

            if current_mode in ["detection", "tracking"]:
                try:
                    results = self.Detector.predict(frame)
                    self.det_queue.put((frame, results))
                except Exception as e:
                    print(f"❌ Detection error: {e}")
                    continue
            else:
                self.det_queue.put((frame, []))

    def ObjectTracking(self):
        while self.running:
            try:
                item = self.det_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:
                self.track_queue.put(None)
                break

            frame, results = item
            outputs_track = []

            with self.mode_lock:
                current_mode = self.Mode

            if current_mode == "tracking":
                xywh_bboxs, confs, class_ids = [], [], []
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cx, cy = int((x1 + x2)/2), int((y1 + y2)/2)
                        w, h = abs(x2 - x1), abs(y2 - y1)
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls in self.Detector.person_class_ids:  # Only track persons
                            xywh_bboxs.append([cx, cy, w, h])
                            confs.append(conf)
                            class_ids.append(cls)
                try:
                    detections = []
                    for (cx, cy, w, h), conf, cls in zip(xywh_bboxs, confs, class_ids):
                        x1 = int(cx - w/2)
                        y1 = int(cy - h/2)
                        x2 = int(cx + w/2)
                        y2 = int(cy + h/2)
                        detections.append([x1, y1, x2, y2, conf, cls])
                    detections = np.array(detections)
                    outputs_track = self.Tracker.track(detections, frame)
                except Exception as e:
                    print(f"❌ Tracking error: {e}")
                    outputs_track = []
            else:
                outputs_track = []
            self.track_queue.put((frame, outputs_track, results))
    
    def BoundingBox(self):
        while self.running:
            try:
                item = self.track_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:
                break

            frame, outputs, results = item
            self.Frame_Count += 1
            fps = self.FPS_Counter.update()

            # Draw detection boxes
            with self.mode_lock:
                current_mode = self.Mode

            if current_mode in ["detection", "tracking"]:
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cls = int(box.cls[0])  # <--- defined here
                        label = self.Detector.model.names.get(int(box.cls[0]), f"cls{int(box.cls[0])}")
                        if cls in self.Detector.selected_class_ids and cls not in self.Detector.person_class_ids:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)

                for t in outputs:
                    x1, y1, x2, y2, tid, cls = t[:6].astype(int)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (225, 200, 0), 2)
                    cv2.putText(frame, f"Person {tid}", (x1, max(0, y1-5)), cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 200, 0), 3)

            cv2.putText(frame, f"FPS: {int(fps)}", (0, 30), cv2.FONT_HERSHEY_PLAIN, 2, (0, 225, 0), 5)
            cv2.putText(frame, f"Frame: {self.Frame_Count}", (0, 60), cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 0), 5)

            if self.frame_callback:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_callback(rgb_frame)
                time.sleep(0.01)
    
    def run(self):
        threads = [
            threading.Thread(target=self.VideoFrameReader, daemon=True),
            threading.Thread(target=self.ObjectDetection, daemon=True),
            threading.Thread(target=self.ObjectTracking, daemon=True),
            threading.Thread(target=self.BoundingBox, daemon=True)
        ]
        for t in threads:
            t.start()

        while self.running and any(t.is_alive() for t in threads):
            time.sleep(0.1)

        self.Video.release()
        cv2.destroyAllWindows()
        print("✅ Backend exited cleanly.")

class UI:
    def __init__(self, source=0, model_path="Local_2.pt"):
        self.Mode = None
        self.active_mode = None
        self.backend = Main_App(Video_path=source, Model_path=model_path, QueueSize=5)
    
    def start_mode(self, mode):
        self.Mode = mode
        self.active_mode = mode
        print(f"▶ {mode} started")
    
    def stop_mode(self, mode):
        if mode == "full_monitor":
            self.Mode = None
            self.active_mode = None
            print("🛑 Full monitor stopped, also stopping detection and tracking")
        elif mode == "tracking":
            if self.Mode == "tracking":
                self.Mode = "detection"  # tracking stopped, detection continues
            print("🛑 Tracking stopped")
        elif mode == "detection":
            if self.Mode == "detection":
                self.Mode = None
            print("🛑 Detection stopped")
    
    def stop_all_modes(self):
        self.Mode = None
        self.active_mode = None
        print("🛑 All modes stopped")

    def setMode(self, mode):
        print("BACKEND RECEIVED MODE:", mode)
        self.backend.set_mode(mode)  # forward mode to backend

    def run(self):
        self.backend.run()  # run the Main_App threads
   
    def stop(self):
        self.backend.running = False
        self.backend.Video.release()
        self.backend.run()  # run the Main_App threads