import sys
import threading
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox, 
                             QStackedWidget, QFileDialog, QFrame, QScrollArea,
                             QSizePolicy, QGridLayout,QLineEdit,QCheckBox)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal,QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QImage, QPixmap
import cv2
import numpy as np
from datetime import datetime
from objectTracking import YOLODetector, ObjectTracker
import threading
import time
import traceback
import objectTracking

# --- Color Palette & Styles ---
BACKGROUND_COLOR = "#111827"  # Dark background
CARD_COLOR = "#1f2937"        # Slightly lighter card
PRIMARY_COLOR = "#0ea5e9"     # Bright Blue
TEXT_COLOR = "#f3f4f6"        # White-ish
SECONDARY_TEXT = "#9ca3af"    # Grey
DANGER_COLOR = "#ef4444"      # Red
ACTIVE_COLOR = "#EF4444"      # Red
HOVER_COLOR = "#2563EB"       # Darker blue for hover
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
    model_loaded_signal = pyqtSignal(list)  # new signal to emit class names

    def __init__(self, source=0, model_path="epoch31.pt", ui_label=None):
        super().__init__()
        self.source = source
        self.model_path = model_path
        self.ui_label = ui_label
        self.running = True
        self._updating = False
        self.backendUI = None

        # thread that will run backendUI.run()
        self._backend_run_thread = None
        self._backend_ready_event = threading.Event()

        # store pending mode requests from UI before backend is ready
        self._pending_mode = None

    def _start_backend_run_thread(self):
        """Start backendUI.run() inside a standard Python thread (daemon)."""
        def target():
            try:
                # backendUI.run() may block forever; it runs in this separate thread
                self.backendUI.run()
            except Exception as e:
                # emit log and print trace to console for debugging
                self.log_signal.emit(f"❌ backend run error: {e}")
                traceback.print_exc()
            finally:
                # mark backend as finished
                self._backend_ready_event.clear()

        self._backend_run_thread = threading.Thread(target=target, daemon=True)
        self._backend_run_thread.start()

    def run(self):
        """Qt thread main — create backend, start its run() in a Python thread,
           then remain alive until stopped. Frames arrive via on_frame_from_backend.
        """
        try:
            from objectTracking import UI
        except Exception as e:
            self.log_signal.emit(f"❌ import error: {e}")
            return

        # Try to instantiate backend (with retry for network sources)
        connected = False
        while not connected and self.running:
            try:
                self.backendUI = UI(source=self.source, model_path=self.model_path)
                # tell backend to call our method when frames are ready
                self.backendUI.backend.frame_callback = self.on_frame_from_backend
                connected = True
                self._backend_ready_event.set()
                # Emit class names for UI
                try:
                    class_names = list(self.backendUI.backend.Detector.model.names.values())
                    self.model_loaded_signal.emit(class_names)
                except Exception as e:
                    self.log_signal.emit(f"❌ Error emitting model classes: {e}")
            except Exception as e:
                self.log_signal.emit(f"❌ Failed to Connect With The Camera Source:\n {e}")
                traceback.print_exc()
                # retry only for network-like sources
                if isinstance(self.source, str) and ("http" in self.source.lower() or "rtsp" in self.source.lower()):
                    time.sleep(1.0)
                    continue
                else:
                    return

        if not self.running:
            # user requested stop while connecting
            try:
                if self.backendUI:
                    self.backendUI.stop_all_modes()
            except Exception:
                pass
            return

        self.log_signal.emit(f"✅ Backend instantiated for source: {self.source}")

        # Apply any pending mode (requested by UI before backend ready)
        if self._pending_mode:
            try:
                self.backendUI.setMode(self._pending_mode)
                self._pending_mode = None
            except Exception:
                pass

        # Start backend.run() inside a normal Python thread so it doesn't block Qt thread control flow.
        try:
            self._start_backend_run_thread()
        except Exception as e:
            self.log_signal.emit(f"❌ Failed to start backend thread: {e}")
            traceback.print_exc()
            return

        # Keep this QThread alive until told to stop. Backend pushes frames to on_frame_from_backend.
        try:
            while self.running:
                # Sleep small amount to stay responsive to stop() signal
                time.sleep(0.05)
        except Exception as e:
            self.log_signal.emit(f"❌ Error in VideoThread main loop: {e}")
            traceback.print_exc()
        finally:
            # Clean up: ask backend to stop, wait for backend thread to finish (with timeout)
            try:
                if self.backendUI:
                    try:
                        self.backendUI.stop_all_modes()
                    except Exception:
                        pass
                    # If backend has a stop() or similar, try it
                    if hasattr(self.backendUI, "stop"):
                        try:
                            self.backendUI.stop()
                        except Exception:
                            pass
            except Exception:
                pass

            # wait for backend run thread to exit (timeout to avoid hanging indefinitely)
            if self._backend_run_thread and self._backend_run_thread.is_alive():
                self.log_signal.emit("⏳ waiting for backend thread to finish...")
                self._backend_run_thread.join(timeout=2.0)

            self.log_signal.emit("🔌 VideoThread exiting cleanly.")
    
    def on_frame_from_backend(self, frame):
        """Frame callback called by the backend (frame is expected to be RGB numpy)."""
        try:
            if not self.running:
                return
            # guard against re-entrancy
            if self._updating:
                return
            # some backends may give BGR — if you expect RGB ensure backend provides RGB.
            # We assume backend gives RGB since your previous code used Format_RGB888.
            if frame is None:
                return

            # Quick validation
            if not hasattr(frame, "shape") or len(frame.shape) < 3:
                return

            self._updating = True
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # If ui_label does not exist or is hidden (e.g., during resize/minimize), do not emit
            if self.ui_label is None or self.ui_label.isHidden():
                return

            # throttle frame emission to avoid flooding UI during resize (limit to ~20 FPS)
            now = time.time()
            if not hasattr(self, "_last_emit"):
                self._last_emit = 0
            if now - self._last_emit < (1.0 / 20.0):
                return
            self._last_emit = now

            # scale image to label in this thread before emitting (QImage is safe to pass)
            label_w = max(1, self.ui_label.width())
            label_h = max(1, self.ui_label.height())
            scaled_image = qt_image.scaled(label_w, label_h,
                                          Qt.KeepAspectRatioByExpanding,
                                          Qt.SmoothTransformation)

            # emit to UI
            try:
                self.change_pixmap_signal.emit(scaled_image)
            except Exception:
                # disconnected signals or closed UI may raise — swallow safely
                pass

        except Exception as e:
            # log full traceback to console and emit user-visible log
            print("Exception in on_frame_from_backend():", e)
            traceback.print_exc()
            try:
                self.log_signal.emit(f"Error processing frame: {e}")
            except Exception:
                pass
        finally:
            self._updating = False

    def set_mode(self, mode):
        # If backend exists, set mode immediately; otherwise store pending mode
        try:
            if self.backendUI:
                try:
                    self.backendUI.setMode(mode)
                    self.log_signal.emit(f"Mode set to {mode}")
                except Exception as e:
                    self.log_signal.emit(f"Failed to set mode: {e}")
            else:
                self._pending_mode = mode
        except Exception:
            pass

    def stop(self):
        """Stop the thread and the backend safely."""
        self.running = False

        # disconnect signals on the Qt side to avoid deliveries to destroyed slots
        try:
            self.change_pixmap_signal.disconnect()
        except Exception:
            pass
        try:
            self.log_signal.disconnect()
        except Exception:
            pass

        # Ask backend to stop if possible
        try:
            if self.backendUI:
                try:
                    self.backendUI.stop_all_modes()
                except Exception:
                    pass
                if hasattr(self.backendUI, "stop"):
                    try:
                        self.backendUI.stop()
                    except Exception:
                        pass
        except Exception:
            pass

        # Wait for the QThread event loop to finish (caller will call wait())
        # Backend run thread is joined in run() finalizer

class ConnectionScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        self.model_path = "epoch31.pt"   # default model
        self.selected_source = "webcam"  # default
        self.video_path = None
        self.ip_url = None
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

        # Icon
        icon_label = QLabel("📷")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        card_layout.addWidget(icon_label)

        # Title
        title = QLabel("PPE Safety Monitor")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Connect to a camera source to begin monitoring\nworkplace safety")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        # Tabs
        tabs_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Video")
        self.btn_upload.setObjectName("TabButton")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.clicked.connect(lambda: self.set_tab("video"))

        self.btn_webcam = QPushButton("System Webcam")
        self.btn_webcam.setObjectName("TabButton")
        self.btn_webcam.setCursor(Qt.PointingHandCursor)
        self.btn_webcam.clicked.connect(lambda: self.set_tab("webcam"))

        self.btn_ipcam = QPushButton("IP Camera")
        self.btn_ipcam.setObjectName("TabButton")
        self.btn_ipcam.setCursor(Qt.PointingHandCursor)
        self.btn_ipcam.clicked.connect(lambda: self.set_tab("ip_camera"))

        tabs_layout.addWidget(self.btn_upload)
        tabs_layout.addWidget(self.btn_webcam)
        tabs_layout.addWidget(self.btn_ipcam)
        card_layout.addLayout(tabs_layout)

        # Input Area
        self.input_area = QVBoxLayout()
        card_layout.addLayout(self.input_area)
        # --- Model Selection ---
        model_label = QLabel("Select Model")
        model_label.setObjectName("Subtitle")
        card_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Default Model (epoch31.pt)",
            "Custom Model..."
        ])
        self.model_combo.currentIndexChanged.connect(self.on_model_change)
        card_layout.addWidget(self.model_combo)


        # Activate Button
        self.btn_activate = QPushButton("Activate Camera")
        self.btn_activate.setObjectName("PrimaryButton")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.clicked.connect(self.handle_activate)
        card_layout.addWidget(self.btn_activate)

        layout.addWidget(card)

        # Initialize default tab
        self.set_tab("webcam")

    def set_tab(self, mode):
        self.selected_source = mode

        # Update Tab Styles
        self.btn_upload.setProperty("active", mode == "video")
        self.btn_webcam.setProperty("active", mode == "webcam")
        self.btn_ipcam.setProperty("active", mode == "ip_camera")
        for btn in [self.btn_upload, self.btn_webcam, self.btn_ipcam]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Clear Input Area
        for i in reversed(range(self.input_area.count())):
            widget = self.input_area.itemAt(i).widget()
            if widget:
                widget.setParent(None)

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

        elif mode == "ip_camera":
            lbl = QLabel("Enter IP Camera URL")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)
        
            # Container frame for styling
            input_container = QFrame()
            input_container.setStyleSheet("background-color: black; border-radius: 8px;")
            container_layout = QVBoxLayout(input_container)
            container_layout.setContentsMargins(5, 5, 5, 5)
        
            # IP input field
            self.ip_input = QLineEdit()
            self.ip_input.setPlaceholderText("e.g., http://192.168.1.100:8080/video")
            self.ip_input.setStyleSheet("color: white; background-color: black; border: 1px solid #374151; padding: 5px;")
            container_layout.addWidget(self.ip_input)
        
            self.input_area.addWidget(input_container)
            self.btn_activate.setText("Activate IP Camera")

    def browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Video', 'c:\\', "Video files (*.mp4 *.avi)")
        if fname:
            self.video_path = fname
            self.file_btn.setText(fname.split('/')[-1])
    
    def handle_activate(self):
        source = None
        if self.selected_source == "video":
            if not self.video_path:
                return
            source = self.video_path
        elif self.selected_source == "webcam":
            source = 0  # Default webcam
        elif self.selected_source == "ip_camera":
            ip_url = self.ip_input.text().strip()
            if not ip_url:
                return
            source = ip_url  # IP camera URL

        #self.switch_callback(source)
        self.switch_callback(source, self.model_path)


    def on_model_change(self, index):
        if index == 1:  # Custom Model
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select YOLO Model",
                "",
                "YOLO Model (*.pt)"
            )
            if file_path:
                self.model_path = file_path
                self.model_combo.setItemText(
                    1, f"Custom: {file_path.split('/')[-1]}"
                )
            else:
                # user canceled → revert to default
                self.model_combo.setCurrentIndex(0)
                self.model_path = "epoch31.pt"
        else:
            self.model_path = "epoch31.pt"

class MonitorScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        
        self.thread = None

        # Checkbox container and layout
        self.class_checkboxes = {}  # will hold QCheckBox objects
        self.class_checkbox_container = QWidget()
        self.class_layout = QVBoxLayout(self.class_checkbox_container)
        self.class_layout.setContentsMargins(0, 0, 0, 0)
        self.class_layout.setSpacing(5)

        # will initialize after model loads
        self.selected_class_handler = None 
        # Initialize UI
        self.init_ui()

    def stop_stream(self):
        if self.thread:
            self.thread.running = False  # signal the thread to stop
            self.thread.wait()           # wait for thread to finish safely
            self.thread = None
            self.switch_callback()

    def get_selected_classes(self):
        return [name for name, cb in self.class_checkboxes.items() if cb.isChecked()]

    def start_stream(self, source, model_path):
        if self.thread:
            self.disconnect_camera()  # ensures the old thread is stopped
        #self.thread = VideoThread(source, ui_label=self.video_frame)
        self.thread = VideoThread(source=source,model_path=model_path,ui_label=self.video_frame)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.log_signal.connect(self.append_log)
        self.thread.model_loaded_signal.connect(self.show_model_classes)
        self.thread.start()

    def update_image(self, qt_img):
        # Always scale into a FIXED space (860x665)
        fixed_width = 950
        fixed_height = 540
    
        scaled = qt_img.scaled(fixed_width, fixed_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_frame.setPixmap(QPixmap.fromImage(scaled))

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

    def show_model_classes(self, class_names):
        print("📦 DEBUG: show_model_classes() called")
        print("📦 thread:", self.thread)
        print("📦 backendUI:", getattr(self.thread, "backendUI", None))
        print("📦 backend.Detector:", getattr(self.thread.backendUI, "Detector", None))
    
        # Clear old checkboxes
        for i in reversed(range(self.class_layout.count())):
            widget = self.class_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
    
        # Create new checkboxes
        self.class_checkboxes = {}
        for cls_name in class_names:
            cb = QCheckBox(cls_name)
            cb.setStyleSheet("color: white;")
            cb.setChecked(cls_name.lower() == "person")  # default selection
            self.class_layout.addWidget(cb)
            self.class_checkboxes[cls_name] = cb
    
        # Only create SelectedClassesHandler if Detector exists
        backend_detector = getattr(self.thread.backendUI.backend, "Detector", None)
        if backend_detector is not None:
            self.selected_class_handler = SelectedClassesHandler(
                checkboxes=self.class_checkboxes,
                backend_detector=backend_detector
            )
        else:
            # Retry later or when backend.Detector becomes available
            print("❌ Detector not ready yet — cannot create SelectedClassesHandler")
   
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
        btn_disconnect.clicked.connect(self.disconnect_camera)
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
        # --- Button Styles ---
        self.active_style = (
            "background-color: #DC2626; color: white; padding: 12px; border-radius: 6px;"
        )  # Red Active Button
        
        self.default_detect_style = (
            f"background-color: {PRIMARY_COLOR}; color: white; padding: 12px; border-radius: 6px;"
        )
        
        self.default_track_style = (
            f"background-color: {CARD_COLOR}; color: white; padding: 12px; border-radius: 6px;"
        )
        
        self.default_full_style = (
            f"background-color: {PRIMARY_COLOR}; color: white; padding: 12px; border-radius: 6px;"
        )

        # Bottom Controls
        controls_layout = QHBoxLayout()
        # Detect Button
        self.btn_detect = QPushButton("▶ Start Detection")
        self.btn_detect.setObjectName("PrimaryButton")
        self.btn_detect.setStyleSheet(self.default_detect_style)
        '''self.btn_detect.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: {TEXT_COLOR};
                padding: 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {HOVER_COLOR};
            }}
        """)'''
        self.btn_detect.clicked.connect(lambda: self.handle_mode("detection"))
        # Track Button
        self.btn_track = QPushButton("◎ Start Tracking")
        self.btn_track.setStyleSheet(self.default_detect_style)
        '''self.btn_track.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_COLOR};
                color: {TEXT_COLOR};
                padding: 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #4B5563;
            }}
        """)'''
        self.btn_track.clicked.connect(lambda: self.handle_mode("tracking"))
        # Full Monitor Button
        self.btn_full = QPushButton("💾 Full Monitor")
        '''self.btn_full.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: {TEXT_COLOR};
                padding: 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {HOVER_COLOR};
            }}
        """)'''
        self.btn_full.setStyleSheet(self.default_full_style)
        self.btn_full.clicked.connect(lambda: self.handle_mode("full_monitor"))

        # --- Class Selection (Dynamic for loaded model) ---
        self.class_selection_label = QLabel("Select classes to detect:")
        self.class_selection_label.setStyleSheet("color: white; font-weight: bold;")
        left_layout.addWidget(self.class_selection_label)
        
        # Container for checkboxes
       # self.class_checkbox_container = QWidget()
       # self.class_layout = QVBoxLayout(self.class_checkbox_container)
       # self.class_layout.setContentsMargins(0, 0, 0, 0)
        #self.class_layout.setSpacing(5)
        # Dictionary to store QCheckBox widgets
       # self.class_checkboxes = {}

        
        # --- Initialize the handler AFTER checkboxes exist ---
        #self.selected_class_handler = SelectedClassesHandler(
            #checkboxes=self.class_checkboxes,
           # backend_detector=self.Detector)

        # Scroll area to hold checkboxes (in case of many classes)
        class_scroll = QScrollArea()
        class_scroll.setWidgetResizable(True)
        class_scroll.setWidget(self.class_checkbox_container)
        class_scroll.setStyleSheet("background-color: black; border: 1px solid #374151;")
        left_layout.addWidget(class_scroll)
        main_layout.addWidget(left_widget, stretch=3)
        

        controls_layout.addWidget(self.btn_detect)
        controls_layout.addWidget(self.btn_track)
        controls_layout.addWidget(self.btn_full)
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
    
    def handle_mode(self, mode):
        """
        Handles starting/stopping Detection, Tracking, Full Monitor.
        Clicking an active (red) button stops the corresponding mode.
        """
        full_active = self.btn_full.styleSheet() == self.active_style
        detect_active = self.btn_detect.styleSheet() == self.active_style
        track_active = self.btn_track.styleSheet() == self.active_style
    
        # ----------------- DETECTION -----------------
        if mode == "detection":
            if full_active:
                return  # Cannot stop detection while full monitor is active
    
            if detect_active:
                # Stop detection
                self.btn_detect.setStyleSheet(self.default_detect_style)
                # Check if tracking is running
                if track_active:
                    self.thread.set_mode("tracking")  # Keep tracking running
                else:
                    self.thread.set_mode("idle")      # No detection or tracking
                self.append_log("🛑 Detection stopped.")
            else:
                # Start detection only
                self.reset_buttons()
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("detection")
                self.append_log("▶ Detection started.")
    
        # ----------------- TRACKING -----------------
        elif mode == "tracking":
            if full_active:
                return  # Cannot stop tracking while full monitor is active
    
            if track_active:
                # Stop tracking only, detection may continue
                self.btn_track.setStyleSheet(self.default_track_style)
                if detect_active:
                    self.thread.set_mode("detection")  # Go back to detection only
                else:
                    self.thread.set_mode("idle")      # Nothing running
                self.append_log("🛑 Tracking stopped. Detection still running.")
            else:
                # Start tracking → detection is required automatically
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_track.setStyleSheet(self.active_style)
                self.btn_full.setStyleSheet(self.default_full_style)
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("tracking")
                self.append_log("◎ Tracking started.")
    
        # ----------------- FULL MONITOR -----------------
        elif mode == "full_monitor":
            if self.btn_full.styleSheet() == self.active_style:
                # Stop everything
                self.reset_buttons()
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("idle")
                self.append_log("🛑 Full Monitoring stopped.")
            else:
                # Start monitoring → requires detection + tracking
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_track.setStyleSheet(self.active_style)
                self.btn_full.setStyleSheet(self.active_style)
                self.btn_detect.setEnabled(False)
                self.btn_track.setEnabled(False)
                self.btn_full.setEnabled(True)
                # Backend: tracking (detection is implicit)
                self.thread.set_mode("tracking")
                self.append_log("💾 Full Monitoring started.")
    
    def reset_buttons(self):
        """Reset all buttons to default style and enable them."""
        self.btn_detect.setStyleSheet(self.default_detect_style)
        self.btn_track.setStyleSheet(self.default_track_style)
        self.btn_full.setStyleSheet(self.default_full_style)
        self.btn_detect.setEnabled(True)
        self.btn_track.setEnabled(True)
        self.btn_full.setEnabled(True)

    def disconnect_camera(self):
        if self.thread:
            try:
                # Stop backend modes first
                self.thread.backendUI.stop_all_modes()
            except Exception as e:
                print("Error stopping backend modes:", e)
                import traceback; traceback.print_exc()
    
            # IMPORTANT: disconnect signals BEFORE killing the thread
            try:
                self.thread.change_pixmap_signal.disconnect()
            except:
                pass
    
            try:
                self.thread.log_signal.disconnect()
            except:
                pass
    
            # Tell the thread to stop
            self.thread.running = False
    
            # Wait for it to finish
            self.thread.wait()
    
            # Fully remove thread reference
            self.thread = None
    
        self.reset_buttons()
    
    def get_selected_class_ids(self):
        """
        Convert selected checkbox names into YOLO class IDs.
        """
        if not self.thread or not self.thread.backendUI:
            return []

        selected_names = [name for name, cb in self.class_checkboxes.items() if cb.isChecked()]
        model = self.thread.backendUI.Detector.model
        selected_ids = [cls_id for cls_id, cls_name in model.names.items() if cls_name in selected_names]
        return selected_ids

    def closeEvent(self, event):
        if self.thread:
            self.thread.stop()  # safely stop the VideoThread
            self.thread = None
        event.accept()

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

    #def go_to_monitor(self, source):
        #self.monitor_screen.start_stream(source)
        #self.stack.setCurrentWidget(self.monitor_screen)

    def go_to_monitor(self, source, model_path):
        self.monitor_screen.start_stream(source, model_path)
        self.stack.setCurrentWidget(self.monitor_screen)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.connection_screen)
    

class SelectedClassesHandler:
    """
    Handles dynamically sending selected class IDs to the backend.
    Works with any number of checkboxes (model-agnostic).
    """
    def __init__(self, checkboxes, backend_detector):
        """
        checkboxes: dict of {class_name: QCheckBox}
        backend_detector: YOLODetector instance
        """
        self.checkboxes = checkboxes
        self.backend = backend_detector
        self.prev_state = {name: cb.isChecked() for name, cb in self.checkboxes.items()}

        # Connect signal with checkbox name
        for name, cb in self.checkboxes.items():
            cb.stateChanged.connect(lambda state, n=name: self.on_checkbox_changed(n, state))

        # Send initial selection
        self.send_selected_classes()

    def on_checkbox_changed(self, name, state):
        """Called instantly when any checkbox changes."""
        print(f"🔘 Checkbox '{name}' is now {'checked' if state else 'unchecked'}")
        self.send_selected_classes()
    
    def send_selected_classes(self):
        selected_names = [
            name for name, cb in self.checkboxes.items() if cb.isChecked()
        ]
    
        detector = self.backend
        if detector is None:
            print("❌ Backend detector not initialized yet")
            return
    
        # Convert names to IDs
        selected_ids = [
            cls_id for cls_id, cls_name in detector.model.names.items()
            if cls_name in selected_names
        ]
    
        # Send to backend detector
        detector.update_selected_classes(selected_ids)
    
        print("📤 UI sent selected class IDs:", selected_ids)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())