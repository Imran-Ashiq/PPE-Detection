# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required for OpenCV and PyQt5
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xinput0 \
    libxcb-xkb1 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# CRITICAL FIX: Delete the conflicting Qt plugins bundled with OpenCV
# This forces PyQt5 to use its own correct plugins
RUN rm -rf /usr/local/lib/python3.11/site-packages/cv2/qt

# Set environment variables for Qt
ENV QT_QPA_PLATFORM=xcb
ENV QT_LOGGING_RULES="qt.qpa.xcb=false"

# Copy the rest of the application code
COPY . .

# Set the command to run your app
CMD ["python", "app.py"]