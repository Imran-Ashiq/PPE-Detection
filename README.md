# PPE Detection System 👷‍♂️🚧

A real-time **Personal Protective Equipment (PPE) Detection** desktop application built with **Python**, **YOLOv8**, **StrongSORT**, and **PyQt5**. This system is designed to monitor construction sites and industrial environments to ensure safety compliance by detecting workers and their safety gear (helmets, vests, etc.).

## 👥 Authors

*   **Muhammad Imran** - *Frontend Development & Integration*
*   **Hamza Ramzan** - *Model Training & Backend Logic*

## 🌟 Features

### Core Detection & Tracking
*   **Real-time Detection**: Detects Persons, Helmets, Vests, and other PPE classes using a custom-trained YOLOv8 model.
*   **Object Tracking**: Tracks individuals across frames using StrongSORT algorithm, assigning unique IDs to each person.
*   **GPU Acceleration**: Optional CUDA/GPU support for faster processing.
*   **Tracking Model Selection**: Choose between different tracking models (OSNet by default).

### Safety Monitoring
*   **Violation Detection**: Real-time PPE compliance checking with severity levels (LOW/MEDIUM/HIGH/CRITICAL).
*   **Email Alert System**: Automated SMTP email notifications for safety violations.
*   **Alert Throttling**: Prevents alert spam with configurable time-based throttling.
*   **Violation Data Capture**: Saves violation images (cropped + full frame) with JSON metadata.

### User Interface
*   **Professional Dashboard**: Modern dark-themed GUI built with PyQt5 featuring:
    *   Custom PPE logo and branding
    *   Login/Signup system with Supabase authentication
    *   Webcam, Video File, and IP Camera support
    *   Live Detection Logs with filtering (INFO/ERROR/WARNING/VIOLATION)
    *   Class selection panel for customizable detection
    *   Status indicators and real-time FPS counter
*   **Violation Screen**: Dedicated monitoring window for safety compliance.
*   **Full Monitor Mode**: Automatically starts detection, tracking, and recording together.

### Recording & Data Management
*   **Video Recording**: Save monitoring sessions as MP4 files.
*   **Frame Capture**: Save individual detection frames.
*   **Organized Storage**: Automatic folder creation with timestamps.

## 🛠️ Tech Stack

*   **Language**: Python 3.11+
*   **GUI Framework**: PyQt5
*   **AI/ML**: Ultralytics YOLOv8, PyTorch
*   **Tracking**: BoxMOT (StrongSORT)
*   **Computer Vision**: OpenCV
*   **Authentication**: Supabase
*   **Email**: SMTP (smtplib)
*   **Containerization**: Docker
*   **Environment Management**: python-dotenv

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

4.  **Configure Environment Variables**
    Create a `.env` file in the root directory:
    ```env
    SUPABASE_URL=your_supabase_project_url
    SUPABASE_KEY=your_supabase_anon_key
    ```

5.  **Download Model Weights**
    *   Due to file size limits, the trained model `epoch31.pt` is not included in this repo.
    *   [Download Model Weights](https://drive.google.com/file/d/11R8K0ehtvpbYZ23l5lUBiH1Lvx94j9zH/view?usp=sharing) 
    *   Place the file in the root directory of the project.

## 💻 Usage

### Running Locally

Run the main application:

```bash
python app.py
```

1.  **Login/Signup**: Create an account or login with existing credentials.
2.  **Select Source**: Choose "System Webcam", upload a video file, or connect to an IP Camera.
3.  **Configure Settings**:
    *   Select YOLO model (default: `epoch31.pt`)
    *   Choose tracking model (default: OSNet)
    *   Enable GPU if available
4.  **Activate Camera**: Click "Activate Camera" to start the video feed.
5.  **Detection Controls**:
    *   **Start Detection**: Enable object detection with bounding boxes
    *   **Start Tracking**: Assign unique IDs to tracked persons
    *   **Full Monitor**: Enable detection + tracking + auto-recording + violation detection
    *   **Start Recording**: Manually start/stop session recording
6.  **Class Selection**: Use the left sidebar to choose which objects to detect.
7.  **Monitor Logs**: View real-time system logs in the right sidebar.

### Running with Docker

#### Quick Start with Docker Compose (Recommended)

1.  **Configure environment**:
    ```bash
    cp .env.example .env
    # Edit .env with your Supabase credentials
    ```

2.  **Start the application**:
    ```bash
    docker-compose up --build
    ```

#### Using Helper Scripts

**Windows:**
```powershell
.\run-docker.ps1
```

**Linux/Mac:**
```bash
chmod +x run-docker.sh
./run-docker.sh
```

#### Manual Docker Build & Run

1.  **Build the Docker Image**:
    ```bash
    docker build -t ppe-detection-app .
    ```

2.  **Start VcXsrv (Windows) or XQuartz (Mac)**

3.  **Run the Container**:
    
    **Windows:**
    ```powershell
    docker run -it --rm `
      -e DISPLAY=host.docker.internal:0 `
      -v "${PWD}\Saved_Detections:/app/Saved_Detections" `
      -v "${PWD}\.env:/app/.env:ro" `
      --name ppe-app `
      ppe-detection-app python app.py
    ```
    
    **Linux/Mac:**
    ```bash
    docker run -it --rm \
      -e DISPLAY=$DISPLAY \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      -v "$(pwd)/Saved_Detections:/app/Saved_Detections" \
      -v "$(pwd)/.env:/app/.env:ro" \
      --name ppe-app \
      ppe-detection-app python app.py
    ```

For comprehensive Docker setup and troubleshooting, see [DOCKER.md](DOCKER.md).

## 📂 Project Structure

```
PPE-Detection/
├── app.py                              # Main GUI Application (5901 lines)
├── objectTracking.py                   # YOLO detection & StrongSORT tracking (845 lines)
├── auth_manager.py                     # Supabase authentication manager
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Docker configuration
├── docker-compose.yml                  # Docker Compose configuration
├── .dockerignore                       # Docker build exclusions
├── .env.example                        # Environment variables template
├── .env                                # Environment variables (not in repo)
├── run-docker.ps1                      # Windows Docker run script
├── run-docker.sh                       # Linux/Mac Docker run script
├── DOCKER.md                           # Comprehensive Docker guide
├── how-to-containerize-your-project.md # Docker tutorial
├── README.md                           # This file
├── PPE.png                             # Application logo
├── epoch31.pt                          # YOLOv8 Model Weights (External Download)
├── osnet_ain_x1_0_*.pth               # Tracking model weights
├── Saved_Detections/                  # Output folder for recordings
└── ...
```

## 🔧 Configuration

### Email Alerts Setup
To enable email notifications for violations, configure SMTP settings in the Violation Screen:
*   SMTP Server (e.g., `smtp.gmail.com`)
*   SMTP Port (e.g., `587`)
*   Email credentials
*   Recipient email addresses

### Violation Detection
Configure required PPE classes in the Violation Screen to monitor compliance.

## 🐳 Docker Deployment

The application is fully containerized for easy deployment. The Docker setup includes:

*   **docker-compose.yml** - Orchestration configuration for easy deployment
*   **Dockerfile** - Multi-stage build with optimized layers
*   **run-docker.ps1** - Windows helper script with VcXsrv auto-start
*   **run-docker.sh** - Linux/Mac helper script with X11 setup
*   **.dockerignore** - Optimized build context
*   **.env.example** - Environment variables template

**What's included in the container:**
*   Python 3.11 runtime
*   All dependencies pre-installed (~1.9GB)
*   X11 forwarding support for GUI
*   Volume mounts for data persistence
*   Health checks for monitoring

**Quick deployment:**
```bash
docker-compose up --build
```

See [DOCKER.md](DOCKER.md) for comprehensive Docker deployment guide including troubleshooting and production best practices.


## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 📝 License

This project is for educational purposes.
