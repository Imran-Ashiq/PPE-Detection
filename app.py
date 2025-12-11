import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox, 
                             QStackedWidget, QFileDialog, QFrame, QScrollArea,
                             QSizePolicy, QGridLayout)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QImage, QPixmap
import cv2
import numpy as np
from datetime import datetime
from objectTracking import YOLODetector, ObjectTracker

# --- Color Palette & Styles ---
BACKGROUND_COLOR = "#111827"  # Dark background
CARD_COLOR = "#1f2937"        # Slightly lighter card
PRIMARY_COLOR = "#0ea5e9"     # Bright Blue
TEXT_COLOR = "#f3f4f6"        # White-ish
SECONDARY_TEXT = "#9ca3af"    # Grey
DANGER_COLOR = "#ef4444"      # Red

STYLESHEET = f"""
    QMainWindow {{
        background-color: {BACKGROUND_COLOR};
    }}
    QWidget {{
        color: {TEXT_COLOR};
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }}
    QFrame#Card {{
        background-color: {CARD_COLOR};
        border-radius: 12px;
        border: 1px solid #374151;
    }}
    QPushButton {{
        background-color: {CARD_COLOR};
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 8px 16px;
        color: {SECONDARY_TEXT};
    }}
    QPushButton:hover {{
        background-color: #374151;
        color: {TEXT_COLOR};
    }}
    QPushButton#PrimaryButton {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        font-weight: bold;
        padding: 12px;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: #0284c7;
    }}
    QPushButton#DangerButton {{
        background-color: transparent;
        border: 1px solid {DANGER_COLOR};
        color: {DANGER_COLOR};
    }}
    QPushButton#DangerButton:hover {{
        background-color: {DANGER_COLOR};
        color: white;
    }}
    QPushButton#TabButton {{
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: {SECONDARY_TEXT};
        padding-bottom: 10px;
    }}
    QPushButton#TabButton[active="true"] {{
        color: {PRIMARY_COLOR};
        border-bottom: 2px solid {PRIMARY_COLOR};
    }}
    QComboBox {{
        background-color: {BACKGROUND_COLOR};
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 8px;
        color: {TEXT_COLOR};
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QLabel#Title {{
        font-size: 24px;
        font-weight: bold;
    }}
    QLabel#Subtitle {{
        color: {SECONDARY_TEXT};
        font-size: 14px;
    }}
    QLabel#SectionTitle {{
        font-size: 16px;
        font-weight: bold;
        color: {PRIMARY_COLOR};
    }}
"""

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    log_signal = pyqtSignal(str)

    def __init__(self, source=0, model_path="epoch31.pt"):
        super().__init__()
        self.source = source
        self.running = True
        self.mode = "stream"
        self.model_path = model_path
        self.detector = None
        self.tracker = None
        self.writer = None
        self.frame_count = 0

    def set_mode(self, mode):
        self.mode = mode
        if mode == "detection":
            if self.detector is None:
                 self.detector = YOLODetector(self.model_path)
        elif mode in ["tracking", "full_monitor"]:
            if self.detector is None:
                self.detector = YOLODetector(self.model_path)
            if self.tracker is None:
                self.tracker = ObjectTracker()
        
        if mode != "full_monitor" and self.writer:
            self.writer.release()
            self.writer = None

    def run(self):
        cap = cv2.VideoCapture(self.source)
        while self.running:
            ret, frame = cap.read()
            if ret:
                self.frame_count += 1
                if self.mode == "detection" and self.detector:
                    results = self.detector.predict(frame)
                    for result in results:
                        for box in result.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            label = self.detector.model.names[cls]
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                elif self.mode in ["tracking", "full_monitor"] and self.detector and self.tracker:
                    results = self.detector.predict(frame)
                    
                    xywh_bboxs__15, confs__15, class_ids__15 = [], [], []
                    detections_to_draw = []
                    
                    for result in results:
                        for box in result.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                            w, h = abs(x2 - x1), abs(y2 - y1)
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            label = self.detector.model.names[cls]
                            
                            detections_to_draw.append((x1, y1, x2, y2, conf, cls, label))
                            
                            # Assuming class 11 is person as per original code
                            if cls == 11:
                                xywh_bboxs__15.append([cx, cy, w, h])
                                confs__15.append(conf)
                                class_ids__15.append(cls)
                    
                    # Run Tracker
                    outputs_track__15 = []
                    if len(xywh_bboxs__15) > 0:
                        detections = []
                        for (cx, cy, w, h), conf, cls in zip(xywh_bboxs__15, confs__15, class_ids__15):
                            x1_t = int(cx - w / 2)
                            y1_t = int(cy - h / 2)
                            x2_t = int(cx + w / 2)
                            y2_t = int(cy + h / 2)
                            detections.append([x1_t, y1_t, x2_t, y2_t, conf, cls])
                        detections = np.array(detections)
                        outputs_track__15 = self.tracker.track(detections, frame)
                    
                    # Draw Tracks
                    if len(outputs_track__15) > 0:
                        for t in outputs_track__15:
                            x1, y1, x2, y2, tid, cls = t[:6].astype(int)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (225, 200, 0), 2)
                            cv2.putText(frame, f"Person {tid}", (x1, max(0, y1-5)), cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 200, 0), 3)
                            
                    # Draw other detections
                    for (x1, y1, x2, y2, conf, cls, label) in detections_to_draw:
                        if label.lower() == "person": continue
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label}", (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 0), 2)

                    # Full Monitor Extras (Save & Log)
                    if self.mode == "full_monitor":
                        # Save
                        if self.writer is None:
                            h, w = frame.shape[:2]
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            filename = f'recording_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
                            self.writer = cv2.VideoWriter(filename, fourcc, 20.0, (w, h))
                            self.log_signal.emit(f"🔴 Recording started: {filename}")
                        self.writer.write(frame)
                        
                        # Log (Sampled)
                        if self.frame_count % 30 == 0:
                            person_count = len(outputs_track__15)
                            ts = datetime.now().strftime("%H:%M:%S")
                            self.log_signal.emit(f"[{ts}] Tracking {person_count} Persons")

                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                convert_to_qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                # Scale to fit the label, keeping aspect ratio
                p = convert_to_qt_format.scaled(1000, 600, Qt.KeepAspectRatio)
                self.change_pixmap_signal.emit(p)
            else:
                # Loop video if it's a file
                if isinstance(self.source, str): 
                     cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                else:
                    break
        cap.release()

    def stop(self):
        self.running = False
        self.wait()

class ConnectionScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        self.selected_source = "webcam" # or "video"
        self.video_path = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # --- Main Card ---
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(500)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(40, 40, 40, 40)

        # Icon (Placeholder text for now)
        icon_label = QLabel("📷")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        card_layout.addWidget(icon_label)

        # Title
        title = QLabel("PPE Safety Monitor")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("Connect to a camera source to begin monitoring\nworkplace safety")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        # Tabs (Upload Video / System Webcam)
        tabs_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Video")
        self.btn_upload.setObjectName("TabButton")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.clicked.connect(lambda: self.set_tab("video"))
        
        self.btn_webcam = QPushButton("System Webcam")
        self.btn_webcam.setObjectName("TabButton")
        self.btn_webcam.setCursor(Qt.PointingHandCursor)
        self.btn_webcam.clicked.connect(lambda: self.set_tab("webcam"))
        
        tabs_layout.addWidget(self.btn_upload)
        tabs_layout.addWidget(self.btn_webcam)
        card_layout.addLayout(tabs_layout)

        # Input Area (Dynamic)
        self.input_area = QVBoxLayout()
        card_layout.addLayout(self.input_area)

        # Activate Button
        self.btn_activate = QPushButton("Activate Camera")
        self.btn_activate.setObjectName("PrimaryButton")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.clicked.connect(self.handle_activate)
        card_layout.addWidget(self.btn_activate)

        layout.addWidget(card)
        
        # Initialize with Webcam tab
        self.set_tab("webcam")

    def set_tab(self, mode):
        self.selected_source = mode
        
        # Update Tab Styles
        self.btn_upload.setProperty("active", mode == "video")
        self.btn_webcam.setProperty("active", mode == "webcam")
        self.btn_upload.style().unpolish(self.btn_upload)
        self.btn_upload.style().polish(self.btn_upload)
        self.btn_webcam.style().unpolish(self.btn_webcam)
        self.btn_webcam.style().polish(self.btn_webcam)

        # Clear Input Area
        for i in reversed(range(self.input_area.count())): 
            self.input_area.itemAt(i).widget().setParent(None)

        if mode == "webcam":
            lbl = QLabel("Select Camera")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)
            
            combo = QComboBox()
            combo.addItems(["Built-in Webcam", "External USB Camera"])
            self.input_area.addWidget(combo)
            self.btn_activate.setText("Activate Camera")
            
        elif mode == "video":
            lbl = QLabel("Select Video File")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)
            
            self.file_btn = QPushButton("Browse File...")
            self.file_btn.clicked.connect(self.browse_file)
            self.input_area.addWidget(self.file_btn)
            self.btn_activate.setText("Load Video")

    def browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Video', 'c:\\', "Video files (*.mp4 *.avi)")
        if fname:
            self.video_path = fname
            self.file_btn.setText(fname.split('/')[-1])

    def handle_activate(self):
        source = 0
        if self.selected_source == "video":
            if not self.video_path:
                return 
            source = self.video_path
        elif self.selected_source == "webcam":
            source = 0 # Default to 0 for webcam
            
        self.switch_callback(source)


class MonitorScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        self.thread = None
        self.init_ui()

    def stop_stream(self):
        if self.thread:
            self.thread.stop()
            self.thread = None
        self.switch_callback()

    def start_stream(self, source):
        self.thread = VideoThread(source)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.log_signal.connect(self.append_log)
        self.thread.start()

    def update_image(self, qt_img):
        self.video_frame.setPixmap(QPixmap.fromImage(qt_img))

    def append_log(self, message):
        lbl = QLabel(message)
        lbl.setStyleSheet(f"color: {SECONDARY_TEXT}; border-bottom: 1px solid #374151; padding: 5px;")
        self.log_layout.insertWidget(0, lbl)
        # Keep log size manageable
        if self.log_layout.count() > 50:
            item = self.log_layout.itemAt(self.log_layout.count() - 1)
            if item.widget():
                item.widget().deleteLater()

    def set_mode(self, mode):
        if self.thread:
            self.thread.set_mode(mode)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left Content (Video & Controls) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("PPE Safety Monitor")
        title.setObjectName("Title")
        
        status_badge = QLabel("● Status: Connected")
        status_badge.setStyleSheet(f"color: #10b981; background-color: {CARD_COLOR}; padding: 5px 10px; border-radius: 15px;")
        
        btn_disconnect = QPushButton("Disconnect")
        btn_disconnect.setObjectName("DangerButton")
        btn_disconnect.setCursor(Qt.PointingHandCursor)
        btn_disconnect.clicked.connect(self.stop_stream)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(status_badge)
        header.addWidget(btn_disconnect)
        left_layout.addLayout(header)

        # Video Placeholder
        self.video_frame = QLabel("Video Stream Loading...")
        self.video_frame.setAlignment(Qt.AlignCenter)
        self.video_frame.setStyleSheet(f"background-color: black; border-radius: 12px; border: 2px solid #374151;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.video_frame)

        # Bottom Controls
        controls_layout = QHBoxLayout()
        
        btn_detect = QPushButton("▶ Start Detection")
        btn_detect.setObjectName("PrimaryButton")
        btn_detect.clicked.connect(lambda: self.set_mode("detection"))
        
        btn_track = QPushButton("◎ Start Tracking")
        btn_track.setStyleSheet(f"background-color: {CARD_COLOR}; color: white; padding: 12px; border-radius: 6px;")
        btn_track.clicked.connect(lambda: self.set_mode("tracking"))
        
        btn_full = QPushButton("💾 Full Monitor")
        btn_full.setStyleSheet(f"background-color: {PRIMARY_COLOR}; color: white; padding: 12px; border-radius: 6px;")
        btn_full.clicked.connect(lambda: self.set_mode("full_monitor"))

        controls_layout.addWidget(btn_detect)
        controls_layout.addWidget(btn_track)
        controls_layout.addWidget(btn_full)
        left_layout.addLayout(controls_layout)

        main_layout.addWidget(left_widget, stretch=3)

        # --- Right Sidebar (Logs) ---
        sidebar = QFrame()
        sidebar.setStyleSheet(f"background-color: {CARD_COLOR}; border-left: 1px solid #374151;")
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        
        log_title = QLabel("Live Detection Log")
        log_title.setObjectName("SectionTitle")
        sidebar_layout.addWidget(log_title)
        
        log_subtitle = QLabel("Real-time safety intelligence")
        log_subtitle.setObjectName("Subtitle")
        sidebar_layout.addWidget(log_subtitle)
        
        # Scrollable Log Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.addStretch()
        scroll.setWidget(self.log_container)
        sidebar_layout.addWidget(scroll)

        # Placeholder Empty State
        empty_state = QLabel("🛡️\nReady to Monitor")
        empty_state.setAlignment(Qt.AlignCenter)
        empty_state.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 16px;")
        self.log_layout.addWidget(empty_state)

        main_layout.addWidget(sidebar, stretch=1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPE Safety Monitor")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.connection_screen = ConnectionScreen(self.go_to_monitor)
        self.monitor_screen = MonitorScreen(self.go_to_connection)

        self.stack.addWidget(self.connection_screen)
        self.stack.addWidget(self.monitor_screen)

    def go_to_monitor(self, source):
        self.monitor_screen.start_stream(source)
        self.stack.setCurrentWidget(self.monitor_screen)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.connection_screen)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
