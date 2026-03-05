# LUNA Robotic Arm – Complete Installation Guide

This guide will help you install and configure the LUNA robotic arm system on a fresh system with nothing pre-installed.

---

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Prerequisites Installation](#prerequisites-installation)
   - [Windows](#windows)
   - [Linux (Ubuntu/Debian)](#linux-ubuntudebian)
   - [macOS](#macos)
3. [Python Environment Setup](#python-environment-setup)
4. [Database Setup (Supabase)](#database-setup-supabase)
5. [Arduino & ESP32 Setup](#arduino--esp32-setup)
6. [Project Configuration](#project-configuration)
7. [Running the System](#running-the-system)
8. [Troubleshooting](#troubleshooting)
9. [Next Steps](#next-steps)

---

## 1. System Requirements

### Minimum Hardware
- **Host Computer:** Any modern laptop/desktop with 8GB+ RAM
- **GPU (Recommended):** NVIDIA RTX 2060 or better (for AI acceleration)
- **Camera:** USB webcam (720p+)
- **Arduino:** Arduino Mega 2560
- **ESP32:** ESP32 development board
- **Motors:** DS-series servos (DS51150, DS5180) + 6V finger servos
- **Sensors:** VL53L0X (distance), MPU6050 (accelerometer)

### Software Requirements
- **OS:** Windows 10/11, Ubuntu 20.04+, or macOS 12+
- **Python:** 3.10 or higher
- **Git:** For cloning the repository
- **Arduino IDE:** For uploading firmware
- **Node.js (optional):** For some development tools

---

## 2. Prerequisites Installation

### Windows

#### Install Python
1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Run installer – **CHECK** "Add Python to PATH"
3. Verify installation:
   ```cmd
   python --version
   pip --version
   ```

#### Install Git
1. Download Git from [git-scm.com](https://git-scm.com)
2. Run installer (default options are fine)
3. Verify:
   ```cmd
   git --version
   ```

#### Install Visual C++ Build Tools (Required for some packages)
1. Download from [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/)
2. Run installer, select "C++ build tools"
3. Complete installation (may take 10-15 minutes)

#### Install Arduino IDE
1. Download from [arduino.cc](https://www.arduino.cc)
2. Run installer
3. Install required libraries (see Arduino Setup)

---

### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install Python and development tools
sudo apt install -y python3 python3-pip python3-venv git build-essential

# Install system dependencies for OpenCV and audio
sudo apt install -y libopencv-dev portaudio19-dev python3-pyaudio

# Install Arduino IDE
sudo snap install arduino

# Verify installations
python3 --version
git --version
```

---

### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.10

# Install Git
brew install git

# Install system dependencies
brew install portaudio
brew install opencv

# Install Arduino IDE
brew install --cask arduino
```

---

## 3. Python Environment Setup

### Clone the Repository
```bash
git clone https://github.com/your-repo/LUNA_ROBOTIC_ARM.git
cd LUNA_ROBOTIC_ARM
```

### Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Install Python Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

### Verify Installation
Create a test script to verify key packages:

```python
# test_imports.py
try:
    import flask
    import cv2
    import torch
    from ultralytics import YOLO
    import serial
    import speech_recognition as sr
    import pyttsx3
    print("✅ All packages imported successfully")
except Exception as e:
    print(f"❌ Import error: {e}")
```

Run it:
```bash
python test_imports.py
```

---

## 4. Database Setup (Supabase)

### Create Supabase Account
1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project
3. Note your project URL and anon key

### Set Up Database Schema
1. Open Supabase SQL Editor
2. Run the provided `database_schema.sql` file:
   - Navigate to SQL Editor in Supabase dashboard
   - Copy contents of `database_schema.sql`
   - Paste and execute

This will create:
- `users` table (authentication and profiles)
- `team_members` table (team page content)
- `site_content` table (dynamic content)
- `mission_logs` table (robot action history)

### Configure .env File
Create a `.env` file in the project root:

```env
# Flask Secret Key (change this!)
SECRET_KEY=your-very-secret-key-change-this-please

# Supabase Database URL
# Format: postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
DATABASE_URL=postgresql://postgres.abcdefg:your-password@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Google Gemini API Key (for voice commands)
# Get from: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your-gemini-api-key-here

# Optional: Serial port (auto-detected if commented out)
# SERIAL_PORT=COM3
```

### Create Admin User
```bash
python create_admin.py
```

This creates the first admin user. Note the credentials shown in console.

---

## 5. Arduino & ESP32 Setup

### Install Required Libraries

In Arduino IDE:
1. Go to **Tools → Manage Libraries**
2. Install:
   - Adafruit PWM Servo Driver Library
   - Adafruit MPU6050
   - Adafruit VL53L0X

### Upload Arduino Firmware

1. Open `firmware/arduino_main/arduino_main.ino` in Arduino IDE
2. Select board: **Arduino Mega 2560**
3. Select correct port
4. Click **Upload**

### Upload ESP32 Firmware

1. Open `firmware/esp32_sensor_hub/esp32_sensor_hub.ino` in Arduino IDE
2. Select board: **ESP32 Dev Module**
3. Select port
4. Click **Upload**

### Hardware Connections

#### Arduino Mega ↔ ESP32
| Arduino Mega | ESP32 | Component |
|--------------|-------|-----------|
| RX1 (19) | TX | Via level shifter |
| TX1 (18) | RX | Via level shifter |
| 5V | VIN | Power |
| GND | GND | Common ground |

#### ESP32 ↔ Sensors
| ESP32 | Sensor | Pin |
|-------|--------|-----|
| SCL | MPU6050 | SCL |
| SDA | MPU6050 | SDA |
| SCL | VL53L0X | SCL |
| SDA | VL53L0X | SDA |
| 3.3V | Both sensors | VIN |

---

## 6. Project Configuration

### Configure Motor Settings (Optional)
Edit `config.py` to adjust:

```python
# Joystick sensitivity
JOYSTICK_SPEED_FACTOR = 2.0  # Degrees per update
JOYSTICK_DEADZONE = 0.1

# Safety distance
EMERGENCY_STOP_DISTANCE = 10  # cm

# Target objects for tracking
TARGET_OBJECTS = ['cup', 'bottle', 'book', 'cell phone']
```

### Download YOLO Models

```bash
# Create models directory
mkdir -p models

# Download pretrained models
# For Windows (PowerShell):
Invoke-WebRequest -Uri "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt" -OutFile "models/yolov8m.pt"
Invoke-WebRequest -Uri "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-pose.pt" -OutFile "models/yolov8n-hand.pt"

# For Linux/macOS:
wget -P models/ https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt
wget -P models/ https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-pose.pt
mv models/yolov8n-pose.pt models/yolov8n-hand.pt
```

Or use the provided script:
```bash
python download_models.py
```

### Create Uploads Directory
```bash
mkdir -p web_interface/static/uploads
```

---

## 7. Running the System

### Start the Server

```bash
# Activate virtual environment (if not already)
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

python app.py
```

### Access the Web Interface

Open browser and go to: **http://localhost:5000**

Login with admin credentials (from `create_admin.py`)

You should see the dashboard with video feed.

### Test Basic Functionality

1. **Check connection:** Status indicator should show "🟢 ONLINE"
2. **Test joystick:** Move virtual joystick, motors should respond
3. **Test gamepad:** Connect USB controller, status should update
4. **Test voice:** Click "START UPLINK" and speak "open hand"

---

## 8. Troubleshooting

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Database connection error | Check `.env` `DATABASE_URL` format and Supabase settings |
| Camera not working | Try different camera index in `app.py` (change `cv2.VideoCapture(0)` to `1`) |
| Serial port not found | Check device manager (Windows) or `ls /dev/tty*` (Linux) |
| Motors not moving | Verify power connections and emergency stop not active |
| YOLO model not loading | Ensure models are in `models/` directory |
| Voice not working | Check microphone permissions and `GEMINI_API_KEY` |

### Check Logs

- **Python console:** Shows server logs and errors
- **Browser console:** F12 → Console for frontend errors
- **Arduino Serial Monitor:** Set baud rate 115200 to see debug output

### MediaPipe Issues

If you see `module 'mediapipe' has no attribute 'solutions'`:

```bash
pip uninstall mediapipe -y
pip install mediapipe==0.10.9
```

### Gemini API Issues

If voice commands fail with "API key expired":

1. Get new API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Update `GEMINI_API_KEY` in `.env` file
3. Restart the server

---

## 9. Next Steps

### After Successful Installation

1. **Change default admin password** via Profile page
2. **Add team members** in Admin Panel → Team
3. **Customize site content** in Admin Panel → Site Content
4. **Train custom YOLO models** (optional) – see `models/training/` scripts
5. **Add your own 3D model** – place `luna_arm.glb` in `web_interface/static/models/`

### Recommended Reading

- [FEATURES.md](FEATURES.md) – All features explained
- [README.md](README.md) – Project overview
- Source code comments for advanced customization

### Support

If you encounter issues not covered here:

1. Check browser console for errors
2. Check Python console for exceptions
3. Verify all connections
4. Open an issue on GitHub

---

## Quick Start Commands (Cheat Sheet)

```bash
# Clone and enter project
git clone https://github.com/your-repo/LUNA_ROBOTIC_ARM.git
cd LUNA_ROBOTIC_ARM

# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure .env file (edit with your details)
cp .env.example .env
nano .env

# Create database tables and admin user
python create_admin.py

# Download YOLO models
python download_models.py

# Start the server
python app.py
```

Then open **http://localhost:5000** in your browser.

---

**Congratulations!** You now have a fully functional LUNA robotic arm system.

For feature details, see [FEATURES.md](FEATURES.md).
