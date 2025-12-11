import cv2         # For video capture, drawing, display
import time        # For timing and FPS calculation
import torch       # For tensor processing used in DeepSORT
import numpy as np # For numerical operations and data structure handling
from ultralytics import YOLO  # Ultralytics' YOLOv8 object detection library
from pathlib import Path
from boxmot import StrongSort
import queue,threading

# Fix for NumPy type deprecation
if not hasattr(np, 'float'):
    np.float = float



if not hasattr(np, 'int'):
    np.int = int



class VideoLoader:
    def __init__(self, path: str):
        self.cap = cv2.VideoCapture(path)  # Load video file from disk
        if not self.cap.isOpened():
            raise IOError(f"❌ Could not open video file: {path}")  # Handle loading error
        print(f"📼 Loaded video: {path}")

    def read_frame(self):
        ret, frame = self.cap.read()  # Read the next frame from the video
        if not ret or frame is None:
            return ret, frame
        return ret,frame

    def release(self):
        self.cap.release()  # Free up video file resources



class YOLODetector:
    def __init__(self, Model_path: str, confidence: float = 0.1):
        self.model = YOLO(Model_path)   # Load the YOLOv8 model with given weights
        self.confidence = confidence      # Set detection confidence threshold
        print("✅ YOLO model loaded")

    def predict(self, frame):
        return self.model.predict(frame, conf=self.confidence)  # Run object detection
    

  
class ObjectTracker:
    def __init__(self):
        self.tracker = StrongSort(
            
            reid_weights=Path("osnet_ain_x1_0_market1501_256x128_amsgrad_ep100_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"),
            device="cpu",
            half=False
        )
    def track(self, detections, frame):
        """
        detections: YOLO detections in the format [x1, y1, x2, y2, conf, class]
        frame: the current frame (numpy array)
        """
        # Update tracker with YOLO detections + frame
        tracks = self.tracker.update(detections, frame)
        return tracks
    def draw(self, frame, bbox_xyxy, identities, class_ids):
        self.Tracker.draw_boxes(frame, bbox_xyxy, identities, class_ids)  # Draw tracked objects



class FPSCounter:
    def __init__(self):
        self.prev_time = time.time()  # Save initial timestamp

    def update(self):
        current_time = time.time()                      # Get current time
        fps = 1 / (current_time - self.prev_time)       # Calculate FPS
        self.prev_time = current_time                   # Update timestamp
        return fps



class Main_App:
    def __init__(self, Video_path: str, Model_path: str,QueueSize:int):
        self.Video = VideoLoader(Video_path)        # Initialize video reader
        self.Detector = YOLODetector(Model_path)  # Load YOLO model
        self.Tracker = ObjectTracker()              # Initialize Tracker
        self.FPS_Counter = FPSCounter()             # Initialize FPS Tracker
        self.Frame_Count = 0                        # Frame counter
        self.running = True
        self.frame_queue = queue.Queue(maxsize=QueueSize)
        self.det_queue = queue.Queue(maxsize=QueueSize)
        self.track_queue = queue.Queue(maxsize=QueueSize)



    def VideoFrameReader(self):
        while self.running:
            ret ,frame=self.Video.read_frame()
            if not ret:
                self.running=False
                self.frame_queue.put(None)          # push sentinel to stop other threads  
                break
            self.frame_queue.put(frame)




    def ObjectDetection(self):
        while self.running:
            try:
                item=self.frame_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:  # sentinel received
                self.det_queue.put(None)
                break
            frame = item
            try:
                results = self.Detector.predict(frame)
                self.det_queue.put((frame,results))
            except Exception as e:
                print(f"❌ Detection error: {e}")
                continue




    def ObjectTracking(self):
        while self.running:
            try:
                item=self.det_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:  # sentinel received
                self.track_queue.put(None)
                break
            frame,results = item
            xywh_bboxs__15, confs__15, class_ids__15 = [], [], []  # Prepare list for Id:15 Tracking
            detections_to_draw = []                     # ✅ Store all detections for drawing
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])  # Bounding box corners
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)  # Center
                    w, h = abs(x2 - x1), abs(y2 - y1)  # Width and height
                    confs=float(box.conf[0])
                    class_ids=int(box.cls[0])
                    class_name = self.Detector.model.names.get(class_ids, f"cls{class_ids}")
                    # Save all detections (for drawing PPE + persons)
                    detections_to_draw.append((x1, y1, x2, y2, confs, class_ids,class_name))
                    if class_ids==11:
                        xywh_bboxs__15.append([cx, cy, w, h])         # Format for DeepSORT
                        confs__15.append(confs)
                        class_ids__15.append(class_ids)
            outputs_track__15 = []  # ✅ tracking results for class 15 (persons only)     
            try:
                # Convert xywh → xyxy detections for StrongSort
                detections = []
                for (cx, cy, w, h), conf, cls in zip(xywh_bboxs__15, confs__15, class_ids__15):
                    x1 = int(cx - w / 2)
                    y1 = int(cy - h / 2)
                    x2 = int(cx + w / 2)
                    y2 = int(cy + h / 2)
                    detections.append([x1, y1, x2, y2, conf, cls])
                detections = np.array(detections)  # shape: (N, 6)
                outputs_track__15 = self.Tracker.track(detections, frame)
            except Exception as e:
                print(f"❌ Tracking error (class 15 only): {e}")
                outputs_track__15 = []
            self.track_queue.put((frame, outputs_track__15, detections_to_draw))
    
    
    
    def BoundingBox(self):
        while self.running:
            try:
                item=self.track_queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:
                break
            frame, outputs_track__15, detections_to_draw = item   # ✅ Now we unpack person-tracking + all detections
            self.Frame_Count += 1
            fps = self.FPS_Counter.update()
            if outputs_track__15 is not None and len(outputs_track__15) > 0:
                for t in outputs_track__15:
                    x1, y1, x2, y2, tid, cls = t[:6].astype(int)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (225, 200, 0), 2)
                    cv2.putText(frame, f"Person {tid}", (x1, max(0, y1-5)),cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 200, 0), 3)

            # 2️⃣ YOLO detections: draw everything except "person"
            for (x1, y1, x2, y2, confs, class_ids, class_name) in detections_to_draw:
                if class_name.lower() == "person":
                    continue  # ❌ skip drawing YOLO "person" boxes
                # ✅ draw YOLO for all other classes
                label = f"{class_name}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)


            cv2.putText(frame, f"FPS: {int(fps)}", (0, 30),cv2.FONT_HERSHEY_PLAIN, 2, (0, 225, 0), 5)
            cv2.putText(frame, f"Frame Count: {int(self.Frame_Count)}", (0, 60),cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 0), 5)
            cv2.imshow("Tracking", frame)
            if cv2.waitKey(1) & 0xFF == ord('1'):
                self.running = False
                self.track_queue.put(None)
                print("🛑 Stopping early via keypress.")
                break



    def run(self):
        # Create threads
        threads=[
            threading.Thread(target=self.VideoFrameReader,daemon=True),
            threading.Thread(target=self.ObjectDetection,daemon=True),
            threading.Thread(target=self.ObjectTracking,daemon=True),
            threading.Thread(target=self.BoundingBox,daemon=True)

        ]
        for t in threads:
            t.start()

        try:
            while self.running and any(t.is_alive() for t in threads):
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("🛑 Interrupted by user")
            self.running = False
            # push sentinels so threads unblock
            self.frame_queue.put(None)
            self.det_queue.put(None)
            self.track_queue.put(None)

        self.Video.release()
        cv2.destroyAllWindows()
        print("✅ Cleaned up and exited.")



if __name__ == "__main__":
    app = Main_App(Video_path="1.mp4", Model_path="epoch31.pt",QueueSize=5)  # Initialize app with file paths
    app.run()  # Start processing video





