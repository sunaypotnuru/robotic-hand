# 🤖 LUNA Robotic Arm Control System

[![CI](https://github.com/sunaypotnuru/robotic-hand/actions/workflows/ci.yml/badge.svg)](https://github.com/sunaypotnuru/robotic-hand/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**LUNA** (Linked Universal Neural Arm) is an advanced 4-DOF robotic arm system powered by AI. It features real-time control, computer vision, voice commands, gesture recognition, and a modern web dashboard with SPA navigation.

---

## ✨ Key Features

- **🎮 Multi-Modal Control:** Virtual joystick, gamepad, voice, gestures
- **👁️ Computer Vision:** YOLOv8 object detection + MediaPipe hand tracking
- **🧠 Gemini AI Integration:** Natural language understanding
- **📊 Real-Time Telemetry:** Distance, accelerometer, motor angles
- **🔐 Role-Based Access:** Operators and admins with secure login
- **📝 Mission Logging:** Complete action history
- **🖥️ Admin Panel:** User/content management
- **🤖 Digital Twin:** 3D model visualization
- **🎯 Motion Recording:** Record and playback sequences
- **🛡️ Safety Systems:** Emergency stop, distance monitoring, input validation

📖 **Full feature details:** [FEATURES.md](docs/FEATURES.md)

---

## 🚀 Quick Start (5 Minutes)

```bash
# Clone repository
git clone https://github.com/sunaypotnuru/robotic-hand.git
cd robotic-hand

# Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure (edit .env with your keys)
cp .env.example .env
nano .env

# Initialize database and admin user
python utils/create_admin.py

# Download YOLO models
python utils/download_models.py

# Start server
python app.py
```

Then open **http://localhost:5000** in your browser.

📚 **Detailed installation:** [INSTALLATION.md](docs/INSTALLATION.md)

---

## 🏗️ System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │────▶│   Flask Server  │────▶│  Arduino Mega   │
│ (SPA + Three.js)│     │   (Socket.IO)   │     │  (Motor Control)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         │                       │                        │
         ▼                       ▼                        ▼
  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
  │   Supabase DB   │     │   AI Modules    │     │    ESP32 Hub    │
  │  (PostgreSQL)   │     │(YOLOv8, MediaPipe│     │  (Sensors)      │
  └─────────────────┘     │   Gemini, TTS)  │     └─────────────────┘
                          └─────────────────┘
```

---

## 📁 Project Structure

```
LUNA_ROBOTIC_ARM/
├── app.py                 # Main Flask application
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── database_schema.sql    # Database setup script
├── models/                # YOLO models
├── firmware/              # Arduino/ESP32 code
├── web_interface/
│   ├── ai_modules/        # AI processing modules
│   ├── static/            # CSS, JS, images
│   └── templates/         # HTML templates
├── tests/                 # Unit tests
├── utils/                 # Validation utilities
└── docs/
    ├── FEATURES.md        # Complete feature documentation
    └── INSTALLATION.md    # Installation guide
```

---

## 🛠️ Technologies Used

- **Backend:** Flask, Flask-SocketIO, SQLAlchemy, Flask-Login
- **Database:** Supabase (PostgreSQL)
- **AI/ML:** YOLOv8, MediaPipe, Google Gemini, Whisper
- **Frontend:** Three.js, Chart.js, Lottie, vanilla JS (SPA)
- **Hardware:** Arduino Mega, ESP32, PCA9685, VL53L0X, MPU6050
- **Security:** Flask-Limiter, Flask-Talisman, bcrypt

---

## 🎯 Hardware Configuration

### Motor Mapping

- **ID 2:** Main Pivot (Elbow) - DS51150, 7.4V
- **ID 3:** Wrist Pitch - DS5180, 7.4V
- **ID 4:** Wrist Roll - DS5180, 7.4V
- **ID 5-9:** Fingers (Thumb to Pinky) - 6V servos

**⚠️ IMPORTANT:** Motor IDs 0 and 1 are **REMOVED** (shoulder assembly). The system blocks commands to these IDs.

### Power Zones

- **Zone B (7.4V):** PCA9685 Board #1 (Arm motors)
- **Zone C (6V):** PCA9685 Board #2 (Hand motors)
- **Zone D (5V):** Arduino, sensors, logic

---

## 🎮 Control Methods

1. **Virtual Joystick** - On-screen velocity control
2. **Manual Sliders** - Precise individual motor control
3. **Gamepad Support** - Xbox/PlayStation controllers
4. **Voice Commands** - Natural language via Gemini AI
5. **Gesture Recognition** - Hand tracking with MediaPipe
6. **Object Tracking** - Automatic pointing with YOLOv8

---

## 🔒 Security Features

- **Rate Limiting:** 5 login attempts/min, 100 motor commands/min
- **Security Headers:** CSP, HSTS, X-Frame-Options
- **Input Validation:** Comprehensive validation for all inputs
- **Role-Based Access:** Operator and admin levels
- **Password Hashing:** Werkzeug security
- **Emergency Stop:** Multiple trigger methods

---

## 📊 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

**Test Results:** 22/22 tests passing (100% success rate)

---

## 📄 Documentation

- **[FEATURES.md](docs/FEATURES.md)** - Complete feature documentation with testing instructions
- **[INSTALLATION.md](docs/INSTALLATION.md)** - Step-by-step installation guide
- **[database_schema.sql](database_schema.sql)** - Database setup script

---

## 👤 Author

**Potnuru Sunay**  
Team Lead & AI Engineer  
Universal AI University, Karjat

Specializing in computer vision, AI integration, and robotic control systems.

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/sunaypotnuru/robotic-hand/issues)
- **Documentation:** See docs/FEATURES.md and docs/INSTALLATION.md
- **Email:** [contact@example.com](mailto:contact@example.com)

---

## 📜 License

This project is for educational and research purposes. See [LICENSE](LICENSE) for details.

---

## ⚠️ Safety Warning

**ALWAYS maintain safe distance from moving parts. Emergency stop must be accessible at all times. Never operate the system without proper safety measures in place.**

---

## 🙏 Acknowledgments

- Universal AI University for project support
- YOLOv8 by Ultralytics
- MediaPipe by Google
- Flask and Python communities

---

**Built with ❤️ for robotics education and research**
