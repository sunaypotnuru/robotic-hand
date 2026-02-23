#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Initialize Drivers
Adafruit_PWMServoDriver pcaArm = Adafruit_PWMServoDriver(0x40); // Arm motors
Adafruit_PWMServoDriver pcaHand = Adafruit_PWMServoDriver(0x41); // Hand motors

// Safety Vars
int distance = 9999;
bool emergencyStop = false;

// Motor state tracking
int motorAngles[10] = {0}; // IDs 0-9 (0-1 unused, but array for indexing)

void setup() {
  Serial.begin(115200);  // USB to Laptop
  Serial1.begin(115200); // RX1/TX1 to ESP32 (via TXB0104)

  // Initialize PCA9685 boards
  pcaArm.begin();
  pcaArm.setPWMFreq(50);
  pcaHand.begin();
  pcaHand.setPWMFreq(50);

  // Initialize all motors to safe position
  for (int i = 2; i <= 9; i++) {
    if (i < 5) {
      motorAngles[i] = 90; // Center position for arm
    } else {
      motorAngles[i] = 0;   // Open position for fingers
    }
    moveServo(i, motorAngles[i]);
  }

  Serial.println("SYSTEM: LUNA Robot Initialized");
  Serial.println("MOTOR MAP: ID 2=Pivot, 3=WristPitch, 4=WristRoll, 5-9=Fingers");
}

void loop() {
  // 1. Listen to ESP32 (Safety Layer)
  if (Serial1.available()) {
    String packet = Serial1.readStringUntil('>');
    
    // Parse sensor data: "<D:150,AX:0.5>"
    if (packet.indexOf("D:") >= 0) {
      // Extract distance
      int dStart = packet.indexOf("D:") + 2;
      int dEnd = packet.indexOf(",", dStart);
      if (dEnd < 0) dEnd = packet.length();
      
      distance = packet.substring(dStart, dEnd).toInt();
      
      // Forward to Laptop for processing
      Serial.println("SENSOR DATA: <" + packet + ">");
      
      // Safety check: Emergency stop if too close
      if (distance < 10 && !emergencyStop) {
        emergencyStop = true;
        Serial.println("EMERGENCY: Distance < 10cm - STOPPING");
        // Move to safe position
        moveServo(2, 90);
        moveServo(3, 90);
        moveServo(4, 90);
      } else if (distance >= 10 && emergencyStop) {
        emergencyStop = false;
        Serial.println("EMERGENCY CLEARED: Distance safe");
      }
    }
  }

  // 2. Listen to Laptop (Command Layer)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (!emergencyStop || cmd.startsWith("RESET")) {
      parseCommand(cmd);
    } else {
      Serial.println("BLOCKED: Emergency stop active");
    }
  }
}

void parseCommand(String cmd) {
  // Single motor command: "M:ID:ANGLE"
  if (cmd.startsWith("M:")) {
    int firstDivider = cmd.indexOf(':');
    int secondDivider = cmd.lastIndexOf(':');

    if (firstDivider >= 0 && secondDivider > firstDivider) {
      int motorID = cmd.substring(firstDivider + 1, secondDivider).toInt();
      int angle = cmd.substring(secondDivider + 1).toInt();
      
      // Safety: Block IDs 0 and 1 (removed shoulder)
      if (motorID == 0 || motorID == 1) {
        Serial.println("ERROR: Motor ID " + String(motorID) + " is removed");
        return;
      }
      
      // Validate range
      if (motorID >= 2 && motorID <= 9 && angle >= 0 && angle <= 180) {
        moveServo(motorID, angle);
      } else {
        Serial.println("ERROR: Invalid motor ID or angle");
      }
    }
  }
  // Batch command: "B:ID:ANGLE:ID:ANGLE:..."
  else if (cmd.startsWith("B:")) {
    parseBatchCommand(cmd);
  }
  // Emergency reset
  else if (cmd.startsWith("RESET")) {
    emergencyStop = false;
    Serial.println("EMERGENCY RESET");
  }
  else {
    Serial.println("ERROR: Unknown command format");
  }
}

void parseBatchCommand(String cmd) {
  // Format: "B:2:90:3:45:4:90"
  int startIdx = 2; // Skip "B:"
  
  while (startIdx < cmd.length()) {
    int colon1 = cmd.indexOf(':', startIdx);
    int colon2 = cmd.indexOf(':', colon1 + 1);
    
    if (colon1 < 0 || colon2 < 0) break;
    
    int motorID = cmd.substring(colon1 + 1, colon2).toInt();
    
    // Find next colon or end of string
    int nextStart = cmd.indexOf(':', colon2 + 1);
    int angle;
    if (nextStart < 0) {
      angle = cmd.substring(colon2 + 1).toInt();
    } else {
      angle = cmd.substring(colon2 + 1, nextStart).toInt();
    }
    
    // Safety: Block IDs 0 and 1
    if (motorID != 0 && motorID != 1 && motorID >= 2 && motorID <= 9 && angle >= 0 && angle <= 180) {
      moveServo(motorID, angle);
    }
    
    if (nextStart < 0) break;
    startIdx = nextStart;
  }
  
  Serial.println("BATCH: Commands executed");
}

void moveServo(int id, int angle) {
  // CRITICAL SAFETY: Split-Logic PWM Mapping
  // DS-Series motors (7.4V) have physical stops - over-driving causes stall current
  int pulse;
  
  if (id >= 2 && id <= 4) {
    // High-Torque DS-Series Motors (DS51150, DS5180 @ 7.4V)
    // SAFE RANGE: 102-512 PWM counts (prevents stalling)
    pulse = map(angle, 0, 180, 102, 512);
  }
  else if (id >= 5 && id <= 9) {
    // Standard Finger Servos (6V)
    // STANDARD RANGE: 150-600 PWM counts
    pulse = map(angle, 0, 180, 150, 600);
  }
  else {
    Serial.println("ERROR: Invalid motor ID " + String(id));
    return;
  }
  
  // Store angle
  motorAngles[id] = angle;

  // Route to appropriate PCA board
  if (id >= 2 && id <= 4) {
    // Arm motors (PCA Board #1)
    // ID 2 = Main Pivot (Channel 2) - DS51150
    // ID 3 = Wrist Pitch (Channel 3) - DS5180
    // ID 4 = Wrist Roll (Channel 4) - DS5180
    pcaArm.setPWM(id, 0, pulse);
    Serial.println("ARM: Motor " + String(id) + " -> " + String(angle) + "° (PWM: " + String(pulse) + ")");
  } 
  else if (id >= 5 && id <= 9) {
    // Hand motors (PCA Board #2)
    // IDs 5-9 map to channels 0-4
    int channel = id - 5;
    pcaHand.setPWM(channel, 0, pulse);
    Serial.println("HAND: Motor " + String(id) + " (Ch" + String(channel) + ") -> " + String(angle) + "° (PWM: " + String(pulse) + ")");
  }
}