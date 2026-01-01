import cv2
import time
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import os
import sys
import os
from boxmot import StrongSort
import queue
import datetime
import threading
import time
from collections import defaultdict
import warnings
import torch

# Fix for NumPy deprecation
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int

class VideoLoader:
    def __init__(self, source,log_callback=None):
        self.log_callback=log_callback
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise IOError(f"❌ Could not open video source: {source}")
        
        self.is_live = isinstance(source, int) or str(source).startswith(("rtsp://", "http://"))
        
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not self.fps or self.fps <= 1 or self.fps > 120:
            self.fps = 30
        
        self.frame_interval_ms = int(1000 / self.fps)
        self.last_frame_time = 0
        
        if isinstance(source, int):
            self.send_log(f"Webcam {source} Activated")
        elif str(source).startswith(("http://", "rtsp://")):
            self.send_log(f"IP Camera Connected: {source}")
        else:
            self.send_log(f"Video File Loaded ({self.fps:.2f} FPS)")

    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass
        
    def read_frame(self):     
        if not self.is_live:
            now = time.time()
            elapsed = (now - self.last_frame_time) * 1000
            
            if elapsed < self.frame_interval_ms:
                time.sleep((self.frame_interval_ms - elapsed) / 1000.0)
            
            self.last_frame_time = time.time()
        
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        self.cap.release()

class YOLODetector:
    def __init__(self, Model_path, confidence=0.3,device='cpu',log_callback=None):
        self.log_callback=log_callback
        self.device = device
        self.model = YOLO(Model_path)
        self.model.to(device)  # Move model to device
        self.confidence = confidence
        self.save_enabled = False
        self.output_dir = "Saved/monitor_outputs"
        self.run_name = None
        self.send_log("✅ YOLO model loaded")
        
        self.person_class_ids = [
            class_id for class_id, name in self.model.names.items()
            if name.lower() == "person"
        ]
        
        self.selected_class_ids = set([0]) 
    
    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass

    def update_selected_classes_for_backend(self, class_ids):
        self.selected_class_ids = set(class_ids)
        print(f"🔹 YOLODetector received selected class IDs: {self.selected_class_ids}")
        
    def predict(self, frame):
        return self.model.predict(frame,conf=self.confidence,save=self.save_enabled,project=self.output_dir if self.save_enabled else None,name=self.run_name,classes=list(self.selected_class_ids),verbose=False)

class ObjectTracker:
    def __init__(self,log_callback=None, model_path=None,device='cpu',max_retries=3):
        self.log_callback=log_callback
        
        if model_path is None:
            model_path = Path("osnet_ain_x1_0_market1501_256x128_amsgrad_ep100_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth")
        else:
            model_path=Path(model_path)
            self.send_log(f"Tracking Model Loaded{model_path}")
        
        self.device = device
        
        warnings.filterwarnings('ignore', message='.*does not have an acceptable suffix.*')
        
        for attempt in range(max_retries):
            try:
                self.tracker = StrongSort(
                    reid_weights=model_path,
                    device=device,
                    half=False
                )
                #self.log_signal.emit(f"StrongSort tracker initialized on {device} With (attempt {attempt + 1})")
                break
            except Exception as e:
                print(f"⚠️ Tracker init attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    print("❌ Failed to initialize tracker after all retries")
                    raise
                time.sleep(0.5)

    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass

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
    def __init__(self, Video_path, Model_path,tracking_path,use_gpu,QueueSize,log_callback=None):
        self.log_callback = log_callback
        
        if use_gpu and torch.cuda.is_available():
            self.device = 'cuda'
            self.send_log(f"🚀 Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = 'cpu'
        
        self.send_log("💻 Using CPU")
        
        self.Video = VideoLoader(Video_path,log_callback=log_callback)
        self.Detector = YOLODetector(Model_path,device=self.device,log_callback=log_callback)
        self.Tracker = ObjectTracker(log_callback=log_callback,model_path=tracking_path,device=self.device)
        self.FPS_Counter = FPSCounter()
        
        self.Frame_Count = 0
        self.running = True
        
        self.frame_queue = queue.Queue(maxsize=QueueSize)
        self.det_queue = queue.Queue(maxsize=QueueSize)
        self.track_queue = queue.Queue(maxsize=QueueSize)
        
        self.Mode = None
        self.mode_lock = threading.Lock()
        
        # Two frame callbacks
        self.frame_callback = None
        self.violation_frame_callback = None
        
        
        # Initialize ViolationDetector
        self.ViolationDetector = ViolationDetector(
            model_names_dict=self.Detector.model.names,
            log_callback=self.log_callback
        )
        
        # Saving options
        self.save_enabled = False
        self.save_type = "frames"
        self.save_folder = None
        self.video_writer = None
        
        # Frame storage for violation capture
        self.latest_frame = None
        self.latest_violation_frame = None
        self.frame_lock = threading.Lock()
        
        # Keep rate limiting ONLY for overload)
        self._last_frame_callback_time = 0
        self._callback_interval = 1.0 / 30.0
        
        print("✅ Main_App initialized with real-time violation detection")
    
    def set_mode(self, mode):
        with self.mode_lock:
            if mode not in ["detection", "tracking", "idle"]:
                print(f"❌ Invalid mode: {mode}")
                return
            
            if mode == "full_monitor":
                self.Mode = "tracking"
                print("🔄 Mode changed to: tracking (full monitor)")
            else:
                self.Mode = mode
                print(f"🔄 Mode changed to: {self.Mode}")
    
    def capture_batch_violation_data(self, violations_list, data_manager):
        """
        Capture multiple violations from the same frame
        
        Args:
            violations_list: list of violation dicts
            data_manager: ViolationDataManager instance
        
        Returns:
            batch_id: unique ID for this batch
            cropped_paths: list of cropped image paths
        """
        try:
            frames_acquired = False
            full_frame = None
            violation_frame = None
            
            for attempt in range(5):
                try:
                    if self.frame_lock.acquire(blocking=True, timeout=0.2):
                        try:
                            if self.latest_frame is not None and self.latest_violation_frame is not None:
                                full_frame = self.latest_frame.copy()
                                violation_frame = self.latest_violation_frame.copy()
                                frames_acquired = True
                        finally:
                            self.frame_lock.release()
                        
                        if frames_acquired:
                            break
                        else:
                            time.sleep(0.05)
                except Exception as e:
                    print(f"⚠️ Frame lock error (attempt {attempt+1}): {e}")
                    time.sleep(0.05)
            
            if not frames_acquired:
                return None, []
            
            batch_id, cropped_paths = data_manager.capture_batch_violation(
                violations_list=violations_list,
                full_frame=full_frame,
                detection_frame=violation_frame
            )
            
            return batch_id, cropped_paths
            
        except Exception as e:
            print(f"❌ Error capturing batch violation data: {e}")
            import traceback
            traceback.print_exc()
            return None, []
    
    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass

    def set_violation_classes(self, class_names):
        if not isinstance(class_names, (list, set)):
            print(f"❌ Invalid class names: {class_names}")
            return
        
        self.ViolationDetector.required_classes = set(class_names)
        print(f"✅ Required PPE set: {class_names}")
        self.send_log(f"✅ Required PPE set: {', '.join(class_names)}")

    def enable_violation_detection(self, enabled=True):
        self.ViolationDetector.enabled = enabled
        status = "enabled" if enabled else "disabled"
        print(f"🔔 Violation detection {status}")
        self.send_log(f"🔔 Violation detection {status}")

    def set_violation_callback(self, callback_fn):
        self.ViolationDetector.violation_callback = callback_fn
        print("✅ Violation callback set")

    def set_violation_frame_callback(self, callback_fn):
        self.violation_frame_callback = callback_fn
        print("✅ Violation frame callback set")

    def VideoFrameReader(self):
        while self.running:
            ret, frame = self.Video.read_frame()
            if not ret:
                self.send_log("❌ Failed to read frame")
                break
            try:
                self.frame_queue.put(frame, timeout=1)
            except queue.Full:
                pass
    
    def ObjectDetection(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except queue.Empty:
                continue
            if frame is None:
                break
            
            results = self.Detector.predict(frame)
            self.det_queue.put((frame, results))
    
    def ObjectTracking(self):
        while self.running:
            try:
                item = self.det_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:
                break
            
            frame, results = item
            
            with self.mode_lock:
                current_mode = self.Mode
            
            if current_mode == "tracking":
                try:
                    detections = []
                    for result in results:
                        for box in result.boxes:
                            cx, cy, w, h = box.xywh[0].cpu().numpy()
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            
                            if cls not in self.Detector.selected_class_ids:
                                continue
                            
                            x1 = int(cx - w/2)
                            y1 = int(cy - h/2)
                            x2 = int(cx + w/2)
                            y2 = int(cy + h/2)
                            detections.append([x1, y1, x2, y2, conf, cls])
                    
                    detections = np.array(detections)
                    outputs_track = self.Tracker.track(detections, frame)
                except Exception as e:
                    self.send_log(f"❌ Tracking error: {e}")
                    print(e)
                    outputs_track = []
            else:
                outputs_track = []
            
            self.track_queue.put((frame, outputs_track, results))
    
    def BoundingBox(self):
        """ Real-time violation frame updates without rate limiting"""
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
            
            clean_frame = frame.copy()
            
            with self.mode_lock:
                current_mode = self.Mode
            
            if current_mode == "detection":
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cls = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = f"{self.Detector.model.names[cls]} {conf:.2f}"
                        
                        if cls in self.Detector.person_class_ids:
                            cv2.rectangle(clean_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(clean_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)
            
            if current_mode == "tracking":
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cls = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = f"{self.Detector.model.names[cls]} {conf:.2f}"
                        
                        if cls in self.Detector.person_class_ids:
                            cv2.rectangle(clean_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(clean_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)
                
                for t in outputs:
                    x1, y1, x2, y2, tid, cls = t[:6].astype(int)
                    cv2.rectangle(clean_frame, (x1, y1), (x2, y2), (225, 200, 0), 2)
                    cv2.putText(clean_frame, f"Person {tid}", (x1, max(0, y1-5)),
                                cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 200, 0), 3)
            
            with self.frame_lock:
                self.latest_frame = frame.copy()
            
            cv2.putText(clean_frame, f"FPS: {int(fps)}", (0, 30),
                        cv2.FONT_HERSHEY_PLAIN, 2, (0, 225, 0), 5)
            cv2.putText(clean_frame, f"Frame: {self.Frame_Count}", (0, 60),
                        cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 0), 5)
            
            violations = []
            
            if self.ViolationDetector.enabled:
                # ✅ Check violations EVERY FRAME (no cooldown)
                violations = self.ViolationDetector.check_violations(
                    yolo_results=results,
                    frame_shape=frame.shape[:2]
                )
                
                # ✅ Send violation frame callback EVERY FRAME (removed rate limiting)
                if self.violation_frame_callback:
                    violation_frame = frame.copy()
                    
                    persons = []
                    for result in results:
                        for box in result.boxes:
                            cls = int(box.cls[0])
                            if cls in self.Detector.person_class_ids:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                persons.append({
                                    "bbox": (x1, y1, x2, y2),
                                    "confidence": float(box.conf[0])
                                })
                    
                    if violations:
                        violation_frame = self.ViolationDetector.draw_violations(
                            violation_frame, violations
                        )
                    elif persons:
                        violation_frame = self.ViolationDetector.draw_compliant_frame(
                            violation_frame, persons
                        )
                    
                    with self.frame_lock:
                        self.latest_violation_frame = violation_frame.copy()
                    
                    try:
                        rgb_violation = cv2.cvtColor(violation_frame, cv2.COLOR_BGR2RGB)
                        self.violation_frame_callback(rgb_violation)
                    except Exception as e:
                        self.send_log(f"⚠️ Violation callback error: {e}")
            
            if self.save_enabled:
                if self.save_type == "frames":
                    ts = datetime.datetime.now().strftime("%H-%M-%S-%f")[:-3]
                    frame_path = os.path.join(self.save_folder, f"{ts}.jpg")
                    cv2.imwrite(frame_path, clean_frame)
                
                elif self.save_type == "video":
                    if self.video_writer is None:
                        h, w, _ = clean_frame.shape
                        video_path = os.path.join(self.save_folder, "detection_output.mp4")
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        self.video_writer = cv2.VideoWriter(video_path, fourcc, 30, (w, h))
                        
                        if not self.video_writer.isOpened():
                            self.send_log("❌ Failed to open VideoWriter")
                            self.video_writer = None
                        else:
                            self.send_log(f"🎥 VideoWriter started ({w}x{h})")
                    
                    if self.video_writer:
                        self.video_writer.write(clean_frame)
            
            current_time = time.time()
            if self.frame_callback and \
               (current_time - self._last_frame_callback_time >= self._callback_interval):
                
                self._last_frame_callback_time = current_time
                
                try:
                    rgb_clean = cv2.cvtColor(clean_frame, cv2.COLOR_BGR2RGB)
                    self.frame_callback(rgb_clean)
                except Exception as e:
                    print(f"⚠️ Frame callback error: {e}")
    
    def set_save_options(self, enabled: bool, save_type=None, save_folder=None):
        if enabled and save_type and save_type != self.save_type:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
                print("🔄 VideoWriter released (save type changed)")
        
        self.save_enabled = enabled
        self.save_type = save_type
        self.save_folder = save_folder
        
        if not enabled:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.send_log("🛑 Saving disabled")
            return
        
        if enabled:
            self.send_log(f"💾 Saving enabled → type={save_type}, folder={save_folder}")
    
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
        self.send_log("✅ Backend exited cleanly.")

class ViolationDetector:
    """ 
    Real-time violation detection without rate limiting
    No more flickering between compliant/violation states
    """
    
    def __init__(self, model_names_dict,log_callback=None):
        self.model_names = model_names_dict
        self.log_callback=log_callback
        self.enabled = False
        self.required_classes = set()
        self.violation_callback = None
        
        self.person_class_ids = [
            cls_id for cls_id, name in model_names_dict.items()
            if name.lower() == "person"
        ]
        
        self.total_violations = 0
    
    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass

    def is_negative_class(self, class_name):
        negative_prefixes = ["no-", "not-"]
        class_lower = class_name.lower()
        return any(class_lower.startswith(prefix) for prefix in negative_prefixes)
    
    def check_violations(self, yolo_results, frame_shape=None):
        """
        ✅ FIXED: Real-time violation checking without rate limiting
        Checks every frame to prevent flickering between states
        """
        if not self.enabled or not self.required_classes:
            return []
        
        detected_classes = set()
        persons = []
        
        for result in yolo_results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = self.model_names[cls_id]
                conf = float(box.conf[0])
                
                detected_classes.add(cls_name)
                
                if cls_name.lower() == "person":
                    persons.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": conf
                    })
        
        violations = []
        missing_items = []
        
        for required_class in self.required_classes:
            is_detected = required_class in detected_classes
            
            is_negative = self.is_negative_class(required_class)
            
            if is_negative:
                if is_detected:
                    missing_items.append(required_class)
            else:
                if not is_detected:
                    missing_items.append(required_class)
        
        if missing_items and persons:
            for person in persons:
                violation = {
                    "type": "missing_ppe",
                    "missing_items": missing_items,
                    "person_bbox": person["bbox"],
                    "person_confidence": person["confidence"],
                    "severity": self._calculate_severity_from_count(len(missing_items)),
                    "timestamp": datetime.datetime.now(),
                    "frame_shape": frame_shape,
                    "state_changed": True
                }
                violations.append(violation)
                self.total_violations += 1
        
        if len(violations) > 10:
            violations = violations[:10]
        
        if violations and self.violation_callback:
            try:
                self.violation_callback(violations)
            except Exception as e:
                self.send_log(f"❌ Violation callback error: {e}")
        
        return violations
    
    def draw_violations(self, frame, violations):
        if not violations:
            return frame
        
        person_violations = {}
        
        for violation in violations:
            bbox = violation["person_bbox"]
            bbox_key = tuple(bbox)
            
            if bbox_key not in person_violations:
                person_violations[bbox_key] = {
                    "bbox": bbox,
                    "missing": [],
                    "confidence": violation["person_confidence"]
                }
            
            for item in violation["missing_items"]:
                if item not in person_violations[bbox_key]["missing"]:
                    person_violations[bbox_key]["missing"].append(item)
        
        for person_data in person_violations.values():
            x1, y1, x2, y2 = person_data["bbox"]
            missing_items = person_data["missing"]
            
            severity = self._calculate_severity_from_count(len(missing_items))
            
            if severity == "CRITICAL":
                color = (0, 0, 255)
            elif severity == "HIGH":
                color = (0, 100, 255)
            elif severity == "MEDIUM":
                color = (0, 165, 255)
            else:
                color = (0, 255, 255)
            
            thickness = 3
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            header_text = f"{severity} VIOLATION"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            font_thickness = 2
            
            line_spacing = 25
            y_offset = y1 - 10
            
            if y_offset < 50:
                y_offset = y2 + 25
            
            max_text_width = 0
            for item in missing_items:
                text_size = cv2.getTextSize(f"  • Missing {item}", font, font_scale, font_thickness)[0]
                max_text_width = max(max_text_width, text_size[0])
            
            bg_x1 = x1
            bg_y1 = y_offset - line_spacing
            bg_x2 = x1 + max_text_width + 20
            bg_y2 = y_offset + (len(missing_items) * line_spacing) + 10
            
            overlay = frame.copy()
            cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            cv2.putText(frame, header_text, (x1 + 5, y_offset),
                        font, font_scale, (255, 255, 255), font_thickness)
            y_offset += line_spacing
            
            for i, missing_item in enumerate(missing_items):
                violation_text = f"  • Missing {missing_item}"
                
                cv2.putText(frame, violation_text, (x1 + 5, y_offset),
                            font, font_scale - 0.1, (255, 255, 255), font_thickness - 1)
                y_offset += line_spacing
        
        total_violations = sum(len(p["missing"]) for p in person_violations.values())
        count_text = f"Active Violations: {total_violations} | Persons: {len(person_violations)}"
        
        text_size = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        text_x = 10
        text_y = frame.shape[0] - 20
        
        cv2.rectangle(frame, (text_x - 5, text_y - text_size[1] - 5),
                      (text_x + text_size[0] + 5, text_y + 5), (0, 0, 255), -1)
        
        cv2.putText(frame, count_text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame
    
    def draw_compliant_frame(self, frame, persons):
        for person in persons:
            x1, y1, x2, y2 = person["bbox"]
            
            color = (0, 255, 0)
            thickness = 3
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            label_text = "✓ COMPLIANT"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            font_thickness = 2
            
            text_size = cv2.getTextSize(label_text, font, font_scale, font_thickness)[0]
            text_x = x1
            text_y = y1 - 10
            
            if text_y < 20:
                text_y = y2 + 20
            
            cv2.rectangle(frame, (text_x, text_y - text_size[1] - 5), (text_x + text_size[0] + 10, text_y + 5), color, -1)
            
            cv2.putText(frame, label_text, (text_x + 5, text_y), font, font_scale, (255, 255, 255), font_thickness)
        
        return frame
    
    def _calculate_severity_from_count(self, count):
        if count >= 4:
            return "CRITICAL"
        elif count >= 3:
            return "HIGH"
        elif count >= 2:
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_statistics(self):
        return {
            "total_violations": self.total_violations,
            "enabled": self.enabled,
            "required_classes": list(self.required_classes)
        }
    
    def reset_statistics(self):
        self.total_violations = 0
        self.send_log("📊 Violation statistics reset")

class UI:
    def __init__(self, source=0, model_path="Local_2.pt",tracking_path=None, use_gpu=False,log_callback=None):
        self.log_callback=log_callback
        self.Mode = None
        self.active_mode = None
        self.backend = Main_App(Video_path=source, Model_path=model_path,tracking_path=tracking_path,use_gpu=use_gpu,QueueSize=5,log_callback=log_callback)
    
    def set_violation_classes(self, class_names):
        self.backend.set_violation_classes(class_names)
    
    def enable_violation_detection(self, enabled=True):
        self.backend.enable_violation_detection(enabled)
    
    def send_log(self, message, log_type="INFO"):
        """Internal logging method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except:
                pass

    def set_violation_callback(self, callback_fn):
        self.backend.set_violation_callback(callback_fn)
    
    def set_violation_frame_callback(self, callback_fn):
        self.backend.set_violation_frame_callback(callback_fn)
    
    def get_violation_statistics(self):
        return self.backend.ViolationDetector.get_statistics()
    
    def start_mode(self, mode):
        self.Mode = mode
        self.active_mode = mode
        self.send_log(f"▶ {mode} started")
    
    def stop_mode(self, mode):
        if mode == "full_monitor":
            if self.Mode == "tracking":
                self.Mode = None
            self.send_log("🛑 Full Monitoring stopped")
            self.send_log("🛑 Detection stopped")
            self.send_log("🛑 Tracking stopped")
        elif mode == "tracking":
            if self.Mode == "tracking":
                self.Mode = "detection"
            self.send_log("🛑 Tracking stopped")
        elif mode == "detection":
            if self.Mode == "detection":
                self.Mode = None
            self.send_log("🛑 Detection stopped")
    
    def stop_all_modes(self):
        self.Mode = None
        self.active_mode = None
        self.send_log("🛑 All modes stopped")

    def setMode(self, mode):
        self.send_log("BACKEND RECEIVED MODE:", mode)
        self.backend.set_mode(mode)

    def run(self):
        self.backend.run()
   
    def set_save_enabled(self, enabled: bool):
        if self.backend:
            self.backend.set_save_options(enabled)
    
    def stop(self):
        self.backend.running = False
        self.backend.Video.release()
        self.backend.run()
