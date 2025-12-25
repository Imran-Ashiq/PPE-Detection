# 🐳 Docker Setup Guide for PPE Detection App

This guide will help you run the **PPE Detection Application** inside a Docker container on Windows. Since this is a graphical (GUI) application, it requires a few special steps to display the window on your screen.

## ✅ Prerequisites

Before you begin, make sure you have the following installed:

1.  **Docker Desktop**: [Download & Install](https://www.docker.com/products/docker-desktop/)
2.  **VcXsrv (Windows X Server)**: [Download from SourceForge](https://sourceforge.net/projects/vcxsrv/)
    *   *Required to show the app's window on Windows.*
3.  **Git**: To clone the repository.

---

## 🚀 Step 1: Configure X Server (VcXsrv)

You must run this **every time** before starting the Docker container.

1.  Open **XLaunch** (installed with VcXsrv).
2.  **Display Settings**: Select **"Multiple windows"** → Click **Next**.
3.  **Client Startup**: Select **"Start no client"** → Click **Next**.
4.  **Extra Settings**:
    *   **IMPORTANT:** Check the box **"Disable access control"**.
    *   Click **Next**.
5.  Click **Finish**. You should see an "X" icon in your system tray.

---

## 📥 Step 2: Setup the Project

1.  **Clone the Repository:**
    ```powershell
    git clone https://github.com/Imran-Ashiq/PPE-Detection.git
    cd PPE-Detection
    ```

2.  **Create Environment File:**
    Create a file named `.env` in the root folder and add your Supabase credentials:
    ```env
    SUPABASE_URL=your_supabase_url_here
    SUPABASE_KEY=your_supabase_anon_key_here
    ```

3.  **Create Storage Folder:**
    Ensure a folder named `Saved_Detections` exists in the project root. This is where videos will be saved and where you can drop files to upload.
    ```powershell
    mkdir Saved_Detections
    ```

---

## 🛠️ Step 3: Build the Docker Image

Open your terminal (PowerShell) in the project folder and run:

```powershell
docker build -t ppe-detection-app .
```

*Note: This may take a few minutes the first time as it downloads Python, OpenCV, and PyTorch.*

---

## ▶️ Step 4: Run the Application

Run the following command in PowerShell to start the app:

```powershell
docker run -it --rm `
  -e DISPLAY=host.docker.internal:0.0 `
  --env-file .env `
  -v ${PWD}/Saved_Detections:/app/Saved_Detections `
  ppe-detection-app
```

### 📝 Command Explanation:
*   `-e DISPLAY=host.docker.internal:0.0`: Tells the app to send its GUI to your Windows X Server.
*   `--env-file .env`: Passes your API keys to the container.
*   `-v ...:/app/Saved_Detections`: Links your local `Saved_Detections` folder to the container. Any video you put here will be visible in the app.

---

## 🎥 How to Test with a Video

1.  Copy a video file (e.g., `test.mp4`) into your local `Saved_Detections` folder.
2.  In the App, go to **"Upload Video"**.
3.  Click **"Browse"**. It will open directly to the folder where your video is.
4.  Select the video and click **"Load Video"**.

---

## ❓ Troubleshooting

**Issue: The app starts but no window appears.**
*   **Fix:** Ensure **VcXsrv** is running and **"Disable access control"** was checked during setup.

**Issue: "qt.qpa.plugin: Could not load the Qt platform plugin 'xcb'"**
*   **Fix:** This usually means the image needs a rebuild. Run:
    ```powershell
    docker build --no-cache -t ppe-detection-app .
    ```

**Issue: "ModuleNotFoundError: No module named 'cv2'"**
*   **Fix:** Ensure `requirements.txt` uses `opencv-python-headless` and rebuild the image.
