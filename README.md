# PPE Detection System 👷‍♂️🚧

A real-time **Personal Protective Equipment (PPE) Detection** desktop application built with **Python**, **YOLOv8**, **StrongSORT**, and **PyQt5**. This system is designed to monitor construction sites and industrial environments to ensure safety compliance by detecting workers and their safety gear (helmets, vests, etc.).

## 🌟 Features

*   **Real-time Detection**: Detects Persons, Helmets, Vests, and other PPE classes using a custom-trained YOLOv8 model.
*   **Object Tracking**: Tracks individuals across frames using StrongSORT algorithm, assigning unique IDs to each person.
*   **Interactive Dashboard**: Professional GUI built with PyQt5 featuring:
    *   Webcam & Video File support.
    *   Live Detection Logs.
    *   Status Indicators.
*   **Full Monitor Mode**: Automatically records the session and logs safety events.

## 🛠️ Tech Stack

*   **Language**: Python 3.11+
*   **GUI Framework**: PyQt5
*   **AI/ML**: Ultralytics YOLOv8, PyTorch
*   **Tracking**: BoxMOT (StrongSORT)
*   **Computer Vision**: OpenCV

## 🚀 Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/Imran-Ashiq/PPE-Detection.git
    cd PPE-Detection
    ```

2.  **Create a Virtual Environment** (Recommended)
    ```bash
    python -m venv ppe
    # Windows
    .\ppe\Scripts\activate
    # Linux/Mac
    source ppe/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If you encounter issues with PyTorch on Windows, install the CPU version:*
    ```bash
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    ```

4.  **Download Model Weights**
    *   Due to file size limits, the trained model `epoch31.pt` is not included in this repo.
    *   [Download epoch31.pt here](#) (Add your Google Drive link here)
    *   Place the file in the root directory of the project.

## 💻 Usage

Run the main application:

```bash
python app.py
```

1.  **Select Source**: Choose "System Webcam" or upload a video file (e.g., `1.mp4`).
2.  **Activate**: Click "Activate Camera".
3.  **Start Detection**: Click "Start Detection" to see bounding boxes.
4.  **Start Tracking**: Click "Start Tracking" to assign IDs to workers.
5.  **Full Monitor**: Click "Full Monitor" to start recording and logging.

## 📂 Project Structure

```
PPE-Detection/
├── app.py              # Main GUI Application entry point
├── objectTracking.py   # Core logic for YOLO detection and StrongSORT tracking
├── requirements.txt    # Python dependencies
├── epoch31.pt          # YOLOv8 Model Weights (External Download)
└── ...
```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 📝 License

This project is for educational purposes.
