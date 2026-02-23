# 🤖 LUNA Robotic Arm Control System

Advanced AI-powered 4-DOF robotic arm control system with web dashboard, computer vision, and voice commands.

## System Architecture

- **Host (Laptop)**: Flask web server with AI modules (YOLOv8, MediaPipe, Whisper)
- **Client (Arduino Mega)**: Motor control via PCA9685 drivers
- **Hub (ESP32)**: Sensor telemetry (MPU6050, VL53L0X)

## Hardware Configuration

### Motor Mapping
- **ID 2**: Main Pivot (Elbow) - DS51150, 7.4V
- **ID 3**: Wrist Pitch - DS5180, 7.4V
- **ID 4**: Wrist Roll - DS5180, 7.4V
- **ID 5-9**: Fingers (Thumb to Pinky) - 6V servos

**⚠️ IMPORTANT**: Motor IDs 0 and 1 are **REMOVED** (shoulder assembly). The system will block any commands to these IDs.

### Power Zones
- **Zone B (7.4V)**: PCA9685 Board #1 (Arm motors)
- **Zone C (6V)**: PCA9685 Board #2 (Hand motors)
- **Zone D (5V)**: Arduino, sensors, logic

## Installation

### 1. Python Environment

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Arduino Firmware

1. Open `firmware/arduino_main/arduino_main.ino` in Arduino IDE
2. Install required libraries:
   - Adafruit PWM Servo Driver Library
3. Select board: **Arduino Mega 2560**
4. Upload to Arduino

### 3. ESP32 Firmware

1. Open `firmware/esp32_sensor_hub/esp32_sensor_hub.ino` in Arduino IDE
2. Install required libraries:
   - Adafruit MPU6050
   - Adafruit VL53L0X
3. Select board: **ESP32 Dev Module**
4. Upload to ESP32

## Usage

### Starting the System

1. **Connect Hardware**:
   - Connect Arduino Mega to laptop via USB
   - Ensure ESP32 is connected to Arduino via Serial1 (TXB0104 level shifter)
   - Connect camera (USB webcam)

2. **Configure Serial Port** (if needed):
   - Edit `app.py` and set `SERIAL_PORT = 'COM3'` (Windows) or `/dev/ttyUSB0` (Linux)
   - Or let the system auto-detect (recommended)

3. **Run the Server**:
   ```bash
   python app.py
   ```

4. **Access Dashboard**:
   - Open browser: `http://localhost:5000`
   - Video feed: `http://localhost:5000/video_feed`

## Control Methods

### 1. Virtual Joystick
- **Left/Right**: Control Wrist Roll (ID 4)
- **Up/Down**: Control Main Pivot (ID 2)
- Uses velocity control (incremental movement)

### 2. Manual Sliders
- Adjust individual motor angles using sliders
- Real-time feedback and state updates

### 3. Object Detection (Click-to-Pick)
- YOLOv8 detects objects in camera feed
- Click on detected object bounding box
- Arm pivots to point at object's vertical position

### 4. Hand Gesture Mimicry
- MediaPipe tracks hand gestures
- Finger fold ratios mapped to hand servos (IDs 5-9)
- Real-time gesture copying

### 5. Voice Commands
- Click "Start Listening" button
- Supported commands:
  - "Arm Up" / "Arm Down"
  - "Wrist Up" / "Wrist Down"
  - "Open Hand" / "Close Hand"
  - "Home" / "Reset"
  - "Stop" / "Emergency"

### 6. Quick Actions
- **Home Position**: Move all motors to safe center position
- **Emergency Stop**: Immediately stop all movement

## Safety Features

- **Distance Monitoring**: ESP32 continuously monitors distance
- **Emergency Stop**: Automatically triggered if distance < 10cm
- **Motor ID Validation**: Blocks commands to removed motors (0, 1)
- **Angle Limits**: All angles clamped to 0-180°

## Serial Communication Protocol

### Single Motor Command
```
M:ID:ANGLE
```
Example: `M:2:90` (Move motor 2 to 90°)

### Batch Command
```
B:ID:ANGLE:ID:ANGLE:...
```
Example: `B:2:90:3:45:4:90` (Move multiple motors)

### Sensor Data (from ESP32)
```
<D:150,AX:0.5,AY:0.2,AZ:9.8>
```
- `D`: Distance in mm
- `AX`, `AY`, `AZ`: Accelerometer values

## Troubleshooting

### Serial Connection Issues
- Check COM port in Device Manager (Windows) or `ls /dev/tty*` (Linux)
- Ensure no other program is using the serial port
- Verify baud rate: 115200

### Camera Not Working
- Check camera permissions
- Try different camera index (change `CAMERA_INDEX` in code)
- Verify camera is not being used by another application

### AI Models Not Loading
- YOLOv8 will auto-download on first run
- Whisper models may take time to download
- Check internet connection for first-time setup

### Motors Not Moving
- Verify PCA9685 I2C addresses (0x40, 0x41)
- Check power connections (7.4V, 6V, 5V)
- Ensure emergency stop is not active
- Check serial communication in Arduino Serial Monitor

## Project Structure

```
LUNA_ROBOTIC_ARM/
├── app.py                      # Main Flask application
├── config.py                   # Configuration file
├── requirements.txt            # Python dependencies
├── firmware/
│   ├── arduino_main/          # Arduino Mega firmware
│   └── esp32_sensor_hub/      # ESP32 firmware
├── web_interface/
│   ├── ai_modules/            # AI processing modules
│   │   ├── kinematics.py      # 1-link arm math
│   │   ├── object_detect.py   # YOLOv8 detection
│   │   ├── hand_tracking.py   # MediaPipe gestures
│   │   └── voice_cmd.py       # Whisper voice
│   ├── templates/
│   │   └── index.html         # Dashboard HTML
│   └── static/
│       ├── script.js          # Frontend JavaScript
│       └── style.css          # Dashboard styles
└── hardware/                  # Hardware documentation
```

## Development Notes

- **No Shoulder**: System is designed for 4-DOF (no base rotation or shoulder)
- **Pivot-Only**: Arm can only pivot up/down, cannot extend forward/backward
- **1-Link Kinematics**: Simple trigonometry, no inverse kinematics needed
- **Real-time Updates**: Socket.IO for low-latency communication

## License

This project is for educational and research purposes.

## Support

For issues or questions, check:
1. Serial Monitor output (Arduino)
2. Python console output (Flask server)
3. Browser console (F12) for frontend errors

---

**⚠️ SAFETY WARNING**: Always ensure proper safety measures when operating the robotic arm. Keep clear of moving parts and maintain emergency stop access.

